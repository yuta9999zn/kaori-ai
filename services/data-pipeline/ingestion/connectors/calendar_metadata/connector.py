"""
Google Calendar + Outlook Calendar metadata connector — PM-EVT-005 (P15-S10 D2).

Reads meeting metadata (title + attendees + timing + recurrence — NO body /
notes / attachments) from a tenant's calendar via OAuth-delegated access.
Process Mining uses the stream to surface meeting-driven workflows
(approval reviews, daily stand-ups, supplier syncs) that don't show up
in any transactional system.

What we capture (metadata only):
  - provider event_id (for sequence reconstruction across edits)
  - title (PII-masked downstream by K-5 redactor before publish)
  - attendee actor hashes (SHA-256 over email)
  - start / duration
  - recurrence rule (iCal RRULE — pattern only, no instances)
  - channel ('google_calendar' | 'outlook_calendar')

What we DO NOT capture:
  - event description / notes
  - attached agenda documents
  - location free text (kept only if it's a room resource, not address)
  - decline reasons

Why metadata-only: same PII budget as the email connector (PM-PII-013).
Calendar titles can leak more PII than email subjects (employee names
land in 1:1 titles), so the K-5 redactor's Vietnamese-name pass is
especially load-bearing here.

OAuth client sharing
====================
Google Calendar and Gmail share an OAuth scope (Workspace), so the
upstream Gmail OAuth refresh token (S10 D1) covers both. Outlook
calendar and Outlook mail similarly share an MSAL token. The
``OAuthCalendarClient`` protocol is separate from
``OAuthEmailClient`` because the upstream APIs and event shapes differ
enough that pretending they're one wrapper would force one of the two
adapters to fight against its SDK.

Bronze event shape per BACKLOG_V4 + S10_PLAN D2
================================================
  event_type:  'calendar.event_created' | 'calendar.event_updated'
               | 'calendar.event_attended'
  case_id:     provider event_id (groups all revisions of the same
               meeting for Process Mining sequence reconstruction)
  actor:       organiser_actor_hash (the meeting organiser)
  payload:
    channel:                 'google_calendar' | 'outlook_calendar'
    title_masked:            provider title verbatim (downstream
                             redactor masks before publish)
    organiser_actor_hash:    SHA-256(lower(organiser_email))
    attendee_actor_hashes:   list[str] — hashed attendees
    provider_event_id:       provider's stable event id
    start_at:                ISO 8601 datetime
    duration_minutes:        int
    recurrence_rule:         iCal RRULE if recurring; else null

Config keys
===========
    channel               'google_calendar' | 'outlook_calendar'
    tenant_mailbox        the calendar owner's email (OAuth principal)
    oauth_credential_path Vault path (production); env override for dev
    client                injected OAuthCalendarClient (test override;
                          default StubOAuthCalendarClient)
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


_VALID_CHANNELS = frozenset({"google_calendar", "outlook_calendar"})
_VALID_EVENT_KINDS = frozenset(
    {"event_created", "event_updated", "event_attended"}
)


@dataclass(frozen=True)
class CalendarEventMeta:
    """The metadata shape an OAuth calendar client returns. Mirrors
    the intersection of Google Calendar v3 + Microsoft Graph /me/events.

    organiser_email + attendee_emails are RAW emails — the connector
    hashes them at the boundary. The K-5 redactor then masks any
    Vietnamese names + emails embedded in the title.
    """

    provider_event_id: str
    title: str
    organiser_email: str               # raw; hashed at connector boundary
    attendee_emails: tuple[str, ...]   # raw; hashed at connector boundary
    start_at: datetime
    duration_minutes: int
    event_kind: str                    # 'event_created' | 'event_updated' | 'event_attended'
    recurrence_rule: Optional[str] = None
    observed_at: Optional[datetime] = None  # when our poll noticed it


class OAuthCalendarClient(Protocol):
    """Protocol for the OAuth-delegated calendar client.

    Implementations (deferred to P15-S11):
      * ``GoogleCalendarOAuthClient``   wraps google-api-python-client
                                        Calendar v3 ``events().list``
                                        with ``updatedMin`` cursor
      * ``OutlookCalendarOAuthClient``  wraps MSAL + MS Graph
                                        ``/me/events`` with delta query

    Both adapters request only metadata fields via per-SDK projection
    (Google ``fields=``, Microsoft ``$select=``) so we don't ingest
    body / attendees-with-PII-bodies / attachments.
    """

    async def list_events(
        self,
        *,
        mailbox: str,
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> AsyncIterator[CalendarEventMeta]:
        ...


class StubOAuthCalendarClient:
    """Default client when none injected — raises so a misconfigured
    deployment surfaces immediately rather than silently emitting zero
    events.

    Ships only because the connector __init__ needs a default; tests
    inject a real-ish fake. P15-S11 swaps in Google / Outlook adapters.
    """

    async def list_events(  # type: ignore[no-untyped-def]
        self,
        *,
        mailbox: str,
        since: Optional[datetime],
        until: Optional[datetime],
    ):
        raise NotImplementedError(
            "OAuthCalendarClient.list_events — real Google Calendar / "
            "Outlook Calendar adapters land in P15-S11 after OAuth "
            "onboarding settles (shared scope with the Gmail/Outlook "
            "email connector — single per-tenant token covers both)."
        )
        yield  # pragma: no cover


class CalendarMetadataConnector(Connector):
    """OAuth-delegated calendar metadata reader.

    Provider-agnostic per ``OAuthCalendarClient`` injection. Emits one
    NormalizedEvent per upstream change (created / updated / attended)
    so Process Mining sees the full revision sequence for a meeting.
    """

    source = "calendar_metadata"

    def __init__(self, *, tenant_id: UUID, config: dict) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        channel = str(self.config.get("channel", "")).lower()
        if channel not in _VALID_CHANNELS:
            raise ValueError(
                f"calendar_metadata connector requires config['channel'] in "
                f"{sorted(_VALID_CHANNELS)}; got {channel!r}"
            )
        if not str(self.config.get("tenant_mailbox", "")).strip():
            raise ValueError(
                "calendar_metadata connector requires config['tenant_mailbox'] "
                "(the calendar owner's email — OAuth principal)"
            )
        self.channel = channel
        self.tenant_mailbox = str(self.config["tenant_mailbox"]).strip().lower()
        self.client: OAuthCalendarClient = self.config.get(
            "client", StubOAuthCalendarClient(),
        )

    async def extract_events(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        """Pull calendar event metadata via injected OAuth client +
        normalise into NormalizedEvent."""
        since_dt = _coerce_aware_utc(since) if since else None
        until_dt = _coerce_aware_utc(until) if until else None

        log.info(
            "calendar_metadata.scan",
            tenant_id=str(self.tenant_id),
            channel=self.channel,
            mailbox=_hash_actor(self.tenant_mailbox),
            since=since_dt.isoformat() if since_dt else None,
            until=until_dt.isoformat() if until_dt else None,
        )

        event_iter = self.client.list_events(
            mailbox=self.tenant_mailbox,
            since=since_dt,
            until=until_dt,
        )
        async for ev in event_iter:
            # Calendar events filter by their OBSERVED-AT timestamp (when
            # the API surfaced the change) not start_at — a meeting next
            # year that's edited today should appear in today's poll.
            window_anchor = _coerce_aware_utc(
                ev.observed_at or ev.start_at,
            )
            if since_dt is not None and window_anchor < since_dt:
                continue
            if until_dt is not None and window_anchor >= until_dt:
                continue

            if ev.event_kind not in _VALID_EVENT_KINDS:
                log.warning(
                    "calendar_metadata.unknown_event_kind",
                    tenant_id=str(self.tenant_id),
                    event_kind=ev.event_kind,
                    provider_event_id=ev.provider_event_id,
                )
                continue

            organiser_hash = _hash_actor(ev.organiser_email)
            attendee_hashes = tuple(
                _hash_actor(e) for e in ev.attendee_emails
            )

            yield NormalizedEvent(
                tenant_id=self.tenant_id,
                event_id=_derive_event_id(
                    self.channel, ev.provider_event_id, ev.event_kind,
                ),
                source=self.source,
                event_type=f"calendar.{ev.event_kind}",
                occurred_at=_coerce_aware_utc(ev.start_at),
                actor=organiser_hash,
                case_id=ev.provider_event_id,
                payload={
                    "channel": self.channel,
                    "title_masked": ev.title,
                    "organiser_actor_hash": organiser_hash,
                    "attendee_actor_hashes": list(attendee_hashes),
                    "provider_event_id": ev.provider_event_id,
                    "start_at": _coerce_aware_utc(ev.start_at).isoformat(),
                    "duration_minutes": int(ev.duration_minutes),
                    "recurrence_rule": ev.recurrence_rule,
                },
            )


# ---------------------------------------------------------------------------
# Module-level helpers — mirror gmail_outlook.connector helpers; kept
# separate (not shared via a `shared/` module) because Phase 2 may extract
# this connector into its own service where the helpers travel with it.
# ---------------------------------------------------------------------------


def _hash_actor(email: str) -> str:
    """SHA-256 over the normalised email. One-way; raw never in Bronze."""
    normalised = (email or "").strip().lower().encode("utf-8")
    return hashlib.sha256(normalised).hexdigest()


def _derive_event_id(
    channel: str, provider_event_id: str, event_kind: str,
) -> str:
    """Stable event_id per (channel, provider_event_id, kind). A meeting
    that's both created and later updated emits two distinct event_ids
    so Process Mining sees the revision sequence."""
    raw = f"{channel}|{provider_event_id}|{event_kind}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return f"calendar_metadata:{digest}"


def _coerce_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
