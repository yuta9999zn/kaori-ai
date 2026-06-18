"""
Tests for CalendarMetadataConnector — P15-S10 D2 (PM-EVT-005).

Same pattern as test_gmail_outlook_connector — a FakeOAuthCalendarClient
replays synthetic CalendarEventMeta so the connector contract is
exercised without standing up Google Calendar v3 / MS Graph SDK.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

import pytest

from ingestion.connectors.calendar_metadata import (
    CalendarEventMeta,
    CalendarMetadataConnector,
    StubOAuthCalendarClient,
)
from ingestion.connectors.calendar_metadata.connector import (
    _derive_event_id,
    _hash_actor,
)


TENANT = UUID("22222222-2222-2222-2222-222222222222")
T0 = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)


# ─── Fake client + fixtures ──────────────────────────────────────────


class FakeOAuthCalendarClient:
    def __init__(self, events: list[CalendarEventMeta]) -> None:
        self._events = events

    async def list_events(
        self,
        *,
        mailbox: str,
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> AsyncIterator[CalendarEventMeta]:
        for e in self._events:
            yield e


def _event(
    *,
    provider_event_id: str = "evt-001",
    title: str = "Weekly review meeting",
    organiser_email: str = "anh@olist.vn",
    attendee_emails: tuple[str, ...] = ("alice@olist.vn", "bob@vendor.com"),
    start_at: datetime = T0,
    duration_minutes: int = 30,
    event_kind: str = "event_created",
    recurrence_rule: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> CalendarEventMeta:
    return CalendarEventMeta(
        provider_event_id=provider_event_id,
        title=title,
        organiser_email=organiser_email,
        attendee_emails=attendee_emails,
        start_at=start_at,
        duration_minutes=duration_minutes,
        event_kind=event_kind,
        recurrence_rule=recurrence_rule,
        observed_at=observed_at,
    )


def _connector(events: list[CalendarEventMeta], **extra) -> CalendarMetadataConnector:
    config = {
        "channel": "google_calendar",
        "tenant_mailbox": "anh@olist.vn",
        "client": FakeOAuthCalendarClient(events),
    }
    config.update(extra)
    return CalendarMetadataConnector(tenant_id=TENANT, config=config)


async def _collect(it: AsyncIterator) -> list:
    out = []
    async for ev in it:
        out.append(ev)
    return out


# ─── Config validation ───────────────────────────────────────────────


def test_requires_channel_in_valid_set():
    with pytest.raises(ValueError, match="channel"):
        CalendarMetadataConnector(
            tenant_id=TENANT,
            config={"channel": "ical", "tenant_mailbox": "a@a.vn"},
        )


def test_accepts_both_google_and_outlook():
    for channel in ("google_calendar", "outlook_calendar"):
        conn = CalendarMetadataConnector(
            tenant_id=TENANT,
            config={
                "channel": channel,
                "tenant_mailbox": "a@a.vn",
                "client": FakeOAuthCalendarClient([]),
            },
        )
        assert conn.channel == channel


def test_default_stub_client_raises():
    conn = CalendarMetadataConnector(
        tenant_id=TENANT,
        config={"channel": "google_calendar", "tenant_mailbox": "a@a.vn"},
    )
    assert isinstance(conn.client, StubOAuthCalendarClient)
    with pytest.raises(NotImplementedError):
        asyncio.run(_collect(conn.extract_events()))


# ─── Event shape contract ────────────────────────────────────────────


def test_emits_normalised_event_per_calendar_event():
    conn = _connector([
        _event(provider_event_id="e-1"),
        _event(provider_event_id="e-2"),
    ])
    events = asyncio.run(_collect(conn.extract_events()))
    assert len(events) == 2
    assert all(ev.source == "calendar_metadata" for ev in events)


def test_event_type_carries_event_kind():
    conn = _connector([
        _event(provider_event_id="e-1", event_kind="event_created"),
        _event(provider_event_id="e-2", event_kind="event_updated"),
        _event(provider_event_id="e-3", event_kind="event_attended"),
    ])
    events = asyncio.run(_collect(conn.extract_events()))
    types = [ev.event_type for ev in events]
    assert types == [
        "calendar.event_created",
        "calendar.event_updated",
        "calendar.event_attended",
    ]


def test_unknown_event_kind_is_skipped():
    """Adapter may emit a kind we don't model yet — skip + warn,
    don't crash the whole scan."""
    conn = _connector([
        _event(provider_event_id="e-1", event_kind="event_unknown_kind"),
        _event(provider_event_id="e-2", event_kind="event_created"),
    ])
    events = asyncio.run(_collect(conn.extract_events()))
    assert len(events) == 1
    assert events[0].payload["provider_event_id"] == "e-2"


def test_case_id_uses_provider_event_id_for_revision_grouping():
    """All revisions of the same meeting (created + later updated) share
    case_id so Process Mining sees them as one case."""
    conn = _connector([
        _event(provider_event_id="meet-7", event_kind="event_created"),
        _event(provider_event_id="meet-7", event_kind="event_updated"),
    ])
    events = asyncio.run(_collect(conn.extract_events()))
    assert all(ev.case_id == "meet-7" for ev in events)


def test_revisions_get_distinct_event_ids():
    """Same provider_event_id under different kinds → different event_id
    so dedup doesn't collapse the revision sequence."""
    conn = _connector([
        _event(provider_event_id="meet-7", event_kind="event_created"),
        _event(provider_event_id="meet-7", event_kind="event_updated"),
    ])
    events = asyncio.run(_collect(conn.extract_events()))
    assert events[0].event_id != events[1].event_id


# ─── PII boundary (K-5) ──────────────────────────────────────────────


def test_raw_organiser_email_never_in_payload():
    conn = _connector([_event(organiser_email="ceo@enterprise.vn")])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    flat = repr(ev.payload).lower()
    assert "ceo@enterprise.vn" not in flat
    assert ev.payload["organiser_actor_hash"] == _hash_actor("ceo@enterprise.vn")


def test_raw_attendee_emails_never_in_payload():
    conn = _connector([
        _event(attendee_emails=("a@x.vn", "b@y.vn", "c@z.vn")),
    ])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    flat = repr(ev.payload).lower()
    for raw in ("a@x.vn", "b@y.vn", "c@z.vn"):
        assert raw not in flat
    assert ev.payload["attendee_actor_hashes"] == [
        _hash_actor("a@x.vn"),
        _hash_actor("b@y.vn"),
        _hash_actor("c@z.vn"),
    ]


def test_actor_is_organiser_hash():
    """ev.actor surfaces the organiser hash — matches the email
    connector convention (actor = the message/event originator)."""
    conn = _connector([_event(organiser_email="anh@olist.vn")])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.actor == _hash_actor("anh@olist.vn")


# ─── Recurrence + duration ───────────────────────────────────────────


def test_recurrence_rule_passes_through():
    conn = _connector([
        _event(recurrence_rule="FREQ=WEEKLY;BYDAY=MO"),
    ])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.payload["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=MO"


def test_non_recurring_event_has_null_rule():
    conn = _connector([_event(recurrence_rule=None)])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.payload["recurrence_rule"] is None


def test_duration_passes_through_as_int():
    conn = _connector([_event(duration_minutes=45)])
    ev = asyncio.run(_collect(conn.extract_events()))[0]
    assert ev.payload["duration_minutes"] == 45
    assert isinstance(ev.payload["duration_minutes"], int)


# ─── Time window — filter by observed_at when present ────────────────


def test_filter_uses_observed_at_when_set():
    """A meeting next year edited today should appear in today's poll.
    The window filter compares observed_at (poll time) not start_at."""
    future_meeting_edited_today = _event(
        provider_event_id="future",
        start_at=T0 + timedelta(days=365),
        observed_at=T0 + timedelta(hours=1),
    )
    conn = _connector([future_meeting_edited_today])
    events = asyncio.run(_collect(conn.extract_events(
        since=T0, until=T0 + timedelta(hours=2),
    )))
    assert len(events) == 1
    assert events[0].payload["provider_event_id"] == "future"


def test_filter_falls_back_to_start_at_when_no_observed_at():
    """Adapter that doesn't surface observed_at → connector uses
    start_at for the window filter (degraded behaviour, documented)."""
    conn = _connector([
        _event(provider_event_id="too-early", start_at=T0 - timedelta(hours=1)),
        _event(provider_event_id="in-window", start_at=T0 + timedelta(hours=1)),
    ])
    events = asyncio.run(_collect(conn.extract_events(since=T0)))
    assert len(events) == 1
    assert events[0].payload["provider_event_id"] == "in-window"


# ─── _derive_event_id determinism ────────────────────────────────────


def test_derive_event_id_deterministic():
    a = _derive_event_id("google_calendar", "evt-1", "event_created")
    b = _derive_event_id("google_calendar", "evt-1", "event_created")
    assert a == b
    assert a.startswith("calendar_metadata:")


def test_derive_event_id_distinct_across_channels_and_kinds():
    google_created = _derive_event_id("google_calendar", "shared", "event_created")
    outlook_created = _derive_event_id("outlook_calendar", "shared", "event_created")
    google_updated = _derive_event_id("google_calendar", "shared", "event_updated")
    assert len({google_created, outlook_created, google_updated}) == 3
