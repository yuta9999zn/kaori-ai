"""Tests for /process-mining/mine endpoint — P15-S11 Tuần 4."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Mount just the process_mining router on a fresh app — avoid the
    full ai-orchestrator lifespan (DB pool, Kafka, Temporal) for pure
    HTTP-surface tests."""
    import ai_orchestrator.routers.process_mining as pm_module

    test_app = FastAPI()
    test_app.include_router(pm_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def _ev(event_id: str, type_: str, hour: int, case_id: str = "case-1") -> dict:
    """Test event factory — hour in UTC offset from midnight 2026-01-01."""
    occurred = datetime(2026, 1, 1, hour, 0, 0, tzinfo=timezone.utc).isoformat()
    return {
        "event_id": event_id,
        "source": "test",
        "event_type": type_,
        "occurred_at": occurred,
        "case_id": case_id,
    }


def test_mine_returns_direct_follows_for_simple_chain(client: TestClient):
    """A→B→C in one case → 2 direct-follow edges."""
    body = {
        "events": [
            _ev("e1", "A", 0),
            _ev("e2", "B", 1),
            _ev("e3", "C", 2),
        ],
        "min_frequency": 1,
    }
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["case_count"] == 1
    assert payload["direct_follows"] == {"A|B": 1, "B|C": 1}
    assert payload["event_counts"] == {"A": 1, "B": 1, "C": 1}
    # Durations: A→B = 1h = 3600s, B→C = 3600s
    assert payload["avg_durations"]["A|B"] == pytest.approx(3600.0)
    assert payload["avg_durations"]["B|C"] == pytest.approx(3600.0)


def test_mine_aggregates_across_cases(client: TestClient):
    """Two cases with shared event types → counts add up across cases."""
    body = {
        "events": [
            _ev("c1e1", "view", 0, case_id="case-1"),
            _ev("c1e2", "checkout", 1, case_id="case-1"),
            _ev("c2e1", "view", 0, case_id="case-2"),
            _ev("c2e2", "abandon", 1, case_id="case-2"),
            _ev("c3e1", "view", 0, case_id="case-3"),
            _ev("c3e2", "checkout", 1, case_id="case-3"),
        ],
        "min_frequency": 1,
    }
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["case_count"] == 3
    assert payload["direct_follows"]["view|checkout"] == 2
    assert payload["direct_follows"]["view|abandon"] == 1


def test_mine_min_frequency_drops_rare_edges(client: TestClient):
    """min_frequency=2 → edges with count < 2 are dropped."""
    body = {
        "events": [
            _ev("c1e1", "view", 0, case_id="c1"),
            _ev("c1e2", "checkout", 1, case_id="c1"),
            _ev("c2e1", "view", 0, case_id="c2"),
            _ev("c2e2", "checkout", 1, case_id="c2"),
            _ev("c3e1", "view", 0, case_id="c3"),
            _ev("c3e2", "rare_event", 1, case_id="c3"),  # only 1 time
        ],
        "min_frequency": 2,
    }
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert "view|checkout" in payload["direct_follows"]
    assert "view|rare_event" not in payload["direct_follows"]


def test_mine_rejects_no_events_and_no_session(client: TestClient):
    body = {"events": [], "min_frequency": 1}
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 422


def test_mine_rejects_both_events_and_session(client: TestClient):
    body = {
        "events": [_ev("e1", "A", 0)],
        "session_id": "test-session",
        "min_frequency": 1,
    }
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 422


def test_mine_session_only_returns_501(client: TestClient):
    """Build Week period: session_id mode not yet wired."""
    body = {"events": [], "session_id": "test-session-uuid", "min_frequency": 1}
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 501
    payload = r.json()
    detail = payload.get("detail") or payload
    assert "session_id" in detail.get("detail", "") or "session_id" in str(detail)


def test_mine_rejects_bad_enterprise_id(client: TestClient):
    body = {"events": [_ev("e1", "A", 0)], "min_frequency": 1}
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "not-a-uuid"},
    )
    assert r.status_code == 400


def test_mine_handles_singleton_case(client: TestClient):
    """Single-event case → no direct_follows, but counts the event."""
    body = {"events": [_ev("e1", "lonely", 0)], "min_frequency": 1}
    r = client.post(
        "/process-mining/mine",
        json=body,
        headers={"X-Enterprise-Id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["event_counts"]["lonely"] == 1
    assert payload["direct_follows"] == {}
    assert payload["case_count"] == 1
