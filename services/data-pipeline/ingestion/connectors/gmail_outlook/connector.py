"""
Gmail + Outlook metadata connector — PM-EVT-004 (P15-S10 D1).

Reads message metadata (subject + thread + actors + timestamps — NO body)
from a tenant's Gmail or Outlook account via OAuth-delegated access. The
Process Mining consumer reconstructs email-driven workflows (approvals,
quote requests, customer-service threads) from this stream.

What we capture (metadata only):
  - thread_id (provider conversation id) — for sequence reconstruction
  - subject (PII-masked downstream by K-5 redactor before publish)
  - from / to actor hashes (SHA-256 of email address) — never raw email
  - occurred_at (provider-reported send/receive timestamp)
  - channel ('gmail' | 'outlook')

What we DO NOT capture:
  - message body
  - attachments
  - inline images
  - profile photos / signatures

Why metadata-only: PII budget + Vietnam compliance. PM-PII-013 (mining
session approval) makes this scope explicit before the customer enables
the connector.

OAuth client injection
======================
The connector accepts an ``OAuthEmailClient`` protocol implementation
via config so unit tests can stub the provider call without standing
up a real Google/Microsoft OAuth flow. Phase 1.5 ships:

  * ``StubOAuthEmailClient`` — raises NotImplementedError on
    ``list_messages``; lets the connector contract surface compile +
    unit-test without real credentials.
  * Real Gmail (google-api-python-client) + Outlook (msal) adapters
    land in P15-S11 once customer OAuth onboarding + Vault path
    standardisation (S10 open Q2 — secret/tenant/{id}/connectors/
    gmail_oauth) are settled.

Bronze event shape per BACKLOG_V4 + S10_PLAN D1
================================================
  event_type:        'email.received' | 'email.sent'
  case_id:           thread_id (groups all messages in a thread for
                     Process Mining sequence reconstruction)
  actor:             from_actor_hash (the message sender — see PII
                     boundary below)
  payload:
    channel:                'gmail' | 'outlook'
    subject:                provider subject (PII-masked downstream)
    from_actor_hash:        SHA-256(lower(email)) — raw email never
                            in Bronze
    to_actor_hashes:        list[str] — hashed recipients
    thread_id:              provider conversation id (verbatim)
    provider_message_id:    provider's stable message id
    direction:              'received' | 'sent' — derived from whether
                            tenant's mailbox is in `from` (sent) or in
                            `to` (received)

PII boundary
============
Raw email addresses NEVER enter Bronze. The connector hashes via
SHA-256 at the connector boundary (this is a one-way derivation; the
K-5 redactor doesn't reverse it). Subject text passes through verbatim
and the redactor masks Vietnamese names / phone / email before Kafka
publish.

Config keys
===========
    channel               'gmail' | 'outlook'
    tenant_mailbox        the email address whose mailbox we read —
                          used to derive direction (received vs sent)
                          + the OAuth principal
    oauth_credential_path Vault path for the OAuth refresh token
                          (production); env override accepted for dev
    client                injected OAuthEmailClient instance (test
                          override; default StubOAuthEmailClient)
    poll_interval_seconds default 300s — caller (Process Mining
                          session runner) drives via cron
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Optional, Protocol
from uuid import UUID

import structlog

from ...base import Connector, NormalizedEvent

log = structlog.get_logger()


_VALID_CHANNELS = frozenset({"gmail", "outlook"})


@dataclass(frozen=True)
class EmailMessageMeta:
    """The metadata shape an OAuth client returns. Mirrors what both
    Gmail API and Microsoft Graph emit after we filter to metadata-only
    fields, so the connector code stays adapter-agnostic.

    Subject is the provider verbatim string; the K-5 redactor masks
    PII before Kafka publish. We do NOT hash the subject here because
    Process Mining downstream uses the masked-but-readable text for
    keyword classification.
    """

    provider_message_id: str
    thread_id: str
    subject: str
    from_email: str               # raw; hashed at connector boundary
    to_emails: tuple[str, ...]    # raw; hashed at connector boundary
    occurred_at: datetime
    direction: str                # 'received' | 'sent' — caller-derived


class OAuthEmailClient(Protocol):
    """Protocol for the OAuth-delegated email client.

    Implementations (deferred to P15-S11):
      * ``GmailOAuthClient``     wraps google-api-python-client
                                 + google-auth-oauthlib refresh flow
      * ``OutlookOAuthClient``   wraps msal token cache + MS Graph
                                 /me/messages endpoint with $select to
                                 metadata-only fields

    The protocol is sync-call-async-iterator so adapters can pump the
    upstream cursor / nextPageToken without buffering the whole window.
    """

    async def list_messages(
        self,
        *,
        mailbox: str,
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> AsyncIterator[EmailMessageMeta]:
        ...


class StubOAuthEmailClient:
    """Default client when none injected — raises so a misconfigured
    deployment surfaces immediately instead of silently emitting zero
    events.

    Ships only because the connector __init__ needs a default; tests
    inject a real-ish fake. P15-S11 swaps in Gmail / Outlook adapters.
    """

    async def list_messages(  # type: ignore[no-untyped-def]
        self,
        *,
        mailbox: str,
        since: Optional[datetime],
        until: Optional[datetime],
    ):
        raise NotImplementedError(
            "OAuthEmailClient.list_messages — real Gmail / Outlook "
            "adapters land in P15-S11 after customer OAuth onboarding + "
            "Vault path standardisation (S10 open Q2). Until then, "
            "tests inject a fake client via config['client']."
        )
        yield  # pragma: no cover — keeps async-generator typing happy


class GmailOutlookConnector(Connector):
    """OAuth-delegated mailbox metadata reader.

    The connector is provider-agnostic — Gmail and Outlook share a
    ``OAuthEmailClient`` protocol so the case_id / hashing / direction
    logic doesn't fork. The ``channel`` config key tags emitted events
    so Process Mining downstream can route per channel.
    """

    source = "gmail_outlook"

    def __init__(self, *, tenant_id: UUID, config: dict) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        channel = str(self.config.get("channel", "")).lower()
        if channel not in _VALID_CHANNELS:
            raise ValueError(
                f"gmail_outlook connector requires config['channel'] in "
                f"{sorted(_VALID_CHANNELS)}; got {channel!r}"
            )
        if not str(self.config.get("tenant_mailbox", "")).strip():
            raise ValueError(
                "gmail_outlook connector requires config['tenant_mailbox'] "
                "(the email address whose mailbox is being read)"
            )
        self.channel = channel
        self.tenant_mailbox = str(self.config["tenant_mailbox"]).strip().lower()
        self.client: OAuthEmailClient = self.config.get(
            "client", StubOAuthEmailClient(),
        )

    async def extract_events(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        """Pull message metadata in the [since, until) window via the
        injected OAuth client, normalise into NormalizedEvent."""
        since_dt = _coerce_aware_utc(since) if since else None
        until_dt = _coerce_aware_utc(until) if until else None

        log.info(
            "gmail_outlook.scan",
            tenant_id=str(self.tenant_id),
            channel=self.channel,
            mailbox=_hash_actor(self.tenant_mailbox),
            since=since_dt.isoformat() if since_dt else None,
            until=until_dt.isoformat() if until_dt else None,
        )

        message_iter = self.client.list_messages(
            mailbox=self.tenant_mailbox,
            since=since_dt,
            until=until_dt,
        )
        async for msg in message_iter:
            occurred_at = _coerce_aware_utc(msg.occurred_at)
            if since_dt is not None and occurred_at < since_dt:
                continue
            if until_dt is not None and occurred_at >= until_dt:
                continue

            direction = (msg.direction or "").lower()
            if direction not in {"received", "sent"}:
                direction = self._derive_direction(msg)

            from_hash = _hash_actor(msg.from_email)
            to_hashes = tuple(_hash_actor(e) for e in msg.to_emails)

            yield NormalizedEvent(
                tenant_id=self.tenant_id,
                event_id=_derive_event_id(self.channel, msg.provider_message_id),
                source=self.source,
                event_type=f"email.{direction}",
                occurred_at=occurred_at,
                actor=from_hash,
                case_id=msg.thread_id,
                payload={
                    "channel": self.channel,
                    "subject": msg.subject,
                    "from_actor_hash": from_hash,
                    "to_actor_hashes": list(to_hashes),
                    "thread_id": msg.thread_id,
                    "provider_message_id": msg.provider_message_id,
                    "direction": direction,
                },
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _derive_direction(self, msg: EmailMessageMeta) -> str:
        """Direction = 'sent' if the tenant mailbox is the sender,
        'received' if it's in the recipient list, else 'received'
        (defensive default — Process Mining treats unknown direction as
        inbound since outbound emails always have the mailbox in From).
        """
        if _normalise_email(msg.from_email) == self.tenant_mailbox:
            return "sent"
        if any(
            _normalise_email(e) == self.tenant_mailbox for e in msg.to_emails
        ):
            return "received"
        return "received"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _hash_actor(email: str) -> str:
    """SHA-256 over the normalised email. One-way derivation — raw
    email never enters Bronze. Same input deterministically same hash
    so Process Mining can correlate actors across messages."""
    normalised = _normalise_email(email).encode("utf-8")
    return hashlib.sha256(normalised).hexdigest()


def _normalise_email(email: str) -> str:
    """Lowercase + strip. Doesn't try to canonicalise plus-addressing
    (a+b@x.com vs a@x.com stay distinct hashes); deliberately
    conservative — Phase 2 may collapse plus-addresses after we see
    how customers use them."""
    return (email or "").strip().lower()


def _derive_event_id(channel: str, provider_message_id: str) -> str:
    """Stable event_id per (channel, provider_message_id). Same message
    re-pulled = same id so downstream deduplicates on retry."""
    raw = f"{channel}|{provider_message_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return f"gmail_outlook:{digest}"


def _coerce_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
