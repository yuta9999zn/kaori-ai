"""
Tests for GmailOutlookConnector — P15-S10 D1 (PM-EVT-004).

Real Gmail / Outlook OAuth adapters defer to P15-S11; this suite uses
a `FakeOAuthEmailClient` that yields synthetic `EmailMessageMeta` so
the connector contract is exercised end-to-end without standing up
google-api-python-client + msal.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

import pytest

from ingestion.connectors.gmail_outlook import (
    EmailMessageMeta,
    GmailOutlookConnector,
    StubOAuthEmailClient,
)
from ingestion.connectors.gmail_outlook.connector import (
    _derive_event_id,
    _hash_actor,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")
T0 = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)


# ─── Fakes ───────────────────────────────────────────────────────────


class FakeOAuthEmailClient:
    """Replays a pre-staged list. The connector's window filter is
    exercised by varying since/until in tests (NOT by filtering here)."""

    def __init__(self, messages: list[EmailMessageMeta]) -> None:
        self._messages = messages

    async def list_messages(
        self,
        *,
        mailbox: str,
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> AsyncIterator[EmailMessageMeta]:
        for m in self._messages:
            yield m


def _msg(
    *,
    provider_message_id: str = "g-001",
    thread_id: str = "thread-A",
    subject: str = "Báo giá tháng 5",
    from_email: str = "supplier@vendor.com",
    to_emails: tuple[str, ...] = ("anh@olist.vn",),
    occurred_at: datetime = T0,
    direction: str = "",
) -> EmailMessageMeta:
    return EmailMessageMeta(
        provider_message_id=provider_message_id,
        thread_id=thread_id,
        subject=subject,
        from_email=from_email,
        to_emails=to_emails,
        occurred_at=occurred_at,
        direction=direction,
    )


def _connector(messages: list[EmailMessageMeta], **extra) -> GmailOutlookConnector:
    config = {
        "channel": "gmail",
        "tenant_mailbox": "anh@olist.vn",
        "client": FakeOAuthEmailClient(messages),
    }
    config.update(extra)
    return GmailOutlookConnector(tenant_id=TENANT, config=config)


async def _collect(it: AsyncIterator) -> list:
    out = []
    async for ev in it:
        out.append(ev)
    return out


# ─── Config validation ───────────────────────────────────────────────


def test_requires_channel_in_valid_set():
    with pytest.raises(ValueError, match="channel"):
        GmailOutlookConnector(
            tenant_id=TENANT,
            config={"channel": "yahoo", "tenant_mailbox": "x@x.vn"},
        )


def test_requires_tenant_mailbox():
    with pytest.raises(ValueError, match="tenant_mailbox"):
        GmailOutlookConnector(
            tenant_id=TENANT,
            config={"channel": "gmail", "tenant_mailbox": ""},
        )


def test_accepts_both_gmail_and_outlook():
    for channel in ("gmail", "outlook"):
        conn = GmailOutlookConnector(
            tenant_id=TENANT,
            config={
                "channel": channel,
                "tenant_mailbox": "a@a.vn",
                "client": FakeOAuthEmailClient([]),
            },
        )
        assert conn.channel == channel
        assert conn.tenant_mailbox == "a@a.vn"


# ─── Default stub client raises ──────────────────────────────────────


def test_default_stub_client_raises_on_list_messages():
    """Misconfigured deploy (no client injected, real OAuth not yet
    wired) surfaces as NotImplementedError rather than emitting
    silent zero events."""
    conn = GmailOutlookConnector(
        tenant_id=TENANT,
        config={"channel": "gmail", "tenant_mailbox": "a@a.vn"},
    )
    assert isinstance(conn.client, StubOAuthEmailClient)
    with pytest.raises(NotImplementedError):
        asyncio.run(_collect(conn.extract_events()))


# ─── Event shape contract ────────────────────────────────────────────


def test_emits_normalised_event_per_message():
    conn = _connector([_msg(provider_message_id="g-1"), _msg(provider_message_id="g-2")])
    events = asyncio.run(_collect(conn.extract_events()))
    assert len(events) == 2
    assert all(ev.tenant_id == TENANT for ev in events)
    assert all(ev.source == "gmail_outlook" for ev in events)


def test_event_id_stable_per_provider_message_id():
    """Same provider_message_id under retry → same event_id (downstream
    dedup contract)."""
    conn1 = _connector([_msg(provider_message_id="g-1")])
    conn2 = _connector([_msg(provider_message_id="g-1")])
    ev1 = asyncio.run(_collect(conn1.extract_events()))[0]
    ev2 = asyncio.run(_collect(conn2.extract_events()))[0]
    assert ev1.event_id == ev2.event_id
    assert ev1.event_id.startswith("gmail_outlook:")


def test_case_id_uses_thread_id_for_sequence_reconstruction():
    """Process Mining groups by case_id — thread_id is the natural
    grouping for email workflows."""
    conn = _connector([_msg(thread_id="thread-7")])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.case_id == "thread-7"


# ─── Direction derivation ────────────────────────────────────────────


def test_direction_sent_when_tenant_mailbox_is_sender():
    """tenant_mailbox = from_email → direction='sent'."""
    conn = _connector([
        _msg(from_email="ANH@olist.vn", to_emails=("supplier@v.com",)),
    ])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.event_type == "email.sent"
    assert ev.payload["direction"] == "sent"


def test_direction_received_when_tenant_mailbox_is_recipient():
    conn = _connector([
        _msg(from_email="supplier@v.com", to_emails=("anh@olist.vn",)),
    ])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.event_type == "email.received"


def test_explicit_direction_in_meta_takes_precedence():
    """Adapter may already know the direction (Gmail labels INBOX/SENT)
    — connector trusts the explicit value."""
    conn = _connector([
        _msg(from_email="other@v.com", to_emails=("third@v.com",), direction="sent"),
    ])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.event_type == "email.sent"


# ─── PII boundary (K-5) ──────────────────────────────────────────────


def test_raw_email_never_in_payload():
    """from_email and to_emails are hashed; raw addresses must not
    leak through the payload (Bronze invariant per K-5)."""
    conn = _connector([
        _msg(from_email="ceo@enterprise.vn", to_emails=("cfo@enterprise.vn",)),
    ])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    flat_payload_str = repr(ev.payload).lower()
    assert "ceo@enterprise.vn" not in flat_payload_str
    assert "cfo@enterprise.vn" not in flat_payload_str
    assert ev.payload["from_actor_hash"] == _hash_actor("ceo@enterprise.vn")
    assert ev.payload["to_actor_hashes"] == [_hash_actor("cfo@enterprise.vn")]


def test_actor_is_hashed_not_raw():
    """ev.actor must be the from-hash, not the raw email."""
    conn = _connector([_msg(from_email="raw@x.vn")])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.actor == _hash_actor("raw@x.vn")
    assert "@" not in ev.actor


def test_hash_normalises_case_and_whitespace():
    """Same logical email different case → same hash so cross-message
    actor correlation works."""
    h1 = _hash_actor("ANH@olist.vn")
    h2 = _hash_actor("  anh@olist.vn  ")
    h3 = _hash_actor("anh@olist.vn")
    assert h1 == h2 == h3


# ─── Time window filtering ───────────────────────────────────────────


def test_filters_messages_before_since():
    conn = _connector([
        _msg(provider_message_id="early", occurred_at=T0 - timedelta(hours=1)),
        _msg(provider_message_id="ok", occurred_at=T0 + timedelta(hours=1)),
    ])
    events = asyncio.run(_collect(conn.extract_events(since=T0)))
    assert len(events) == 1
    assert events[0].payload["provider_message_id"] == "ok"


def test_filters_messages_at_or_after_until():
    """until is exclusive upper bound — message at exactly `until` is
    skipped so consecutive windows don't double-emit."""
    conn = _connector([
        _msg(provider_message_id="in", occurred_at=T0),
        _msg(provider_message_id="boundary", occurred_at=T0 + timedelta(hours=1)),
        _msg(provider_message_id="out", occurred_at=T0 + timedelta(hours=2)),
    ])
    events = asyncio.run(_collect(conn.extract_events(
        since=T0, until=T0 + timedelta(hours=1),
    )))
    ids = [ev.payload["provider_message_id"] for ev in events]
    assert ids == ["in"]


def test_unbounded_window_yields_all():
    conn = _connector([_msg(provider_message_id="g-1"), _msg(provider_message_id="g-2")])
    events = asyncio.run(_collect(conn.extract_events()))
    assert len(events) == 2


# ─── _derive_event_id determinism ────────────────────────────────────


def test_derive_event_id_deterministic():
    a = _derive_event_id("gmail", "msg-123")
    b = _derive_event_id("gmail", "msg-123")
    assert a == b
    assert a.startswith("gmail_outlook:")


def test_derive_event_id_distinct_across_channels():
    """Same provider_message_id under different channels must hash
    distinctly so a Gmail + Outlook collision is impossible."""
    a = _derive_event_id("gmail", "shared-id")
    b = _derive_event_id("outlook", "shared-id")
    assert a != b
