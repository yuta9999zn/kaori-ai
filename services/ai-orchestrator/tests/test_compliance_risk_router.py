"""
Task 4 — HTTP-surface tests for /compliance/ai-uses (classify + read).

EU AI Act risk classification gate (ADR-0041, K-22). Mocks
acquire_for_tenant + record_ai_call; no Postgres.

Pattern mirrors test_industry_bootstrap_router.py.

Coverage focus:
  1. POST classify high-tier -> 201, controls contain K-23, status active,
     INSERT into ai_use_risk_register, record_ai_call awaited once.
  2. POST classify prohibited -> 201, status blocked, controls [].
  3. POST classify invalid tier 'banana' -> 422.
  4. GET ?workflow_id=... returns the latest row.
  5. POST without X-Enterprise-ID header -> 422.
"""
from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "55555555-5555-5555-5555-555555555555"
WORKFLOW_ID = "66666666-6666-6666-6666-666666666666"
AI_USE_ID = "88888888-8888-8888-8888-888888888888"

HEADERS = {"X-Enterprise-ID": ENTERPRISE_ID, "X-User-ID": USER_ID}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    conn.execute.return_value = "OK"
    return conn


def _ctx(conn):
    @asynccontextmanager
    async def _fake(*_args, **_kwargs):
        yield conn
    return _fake


def _risk_row(**overrides) -> MagicMock:
    """Canned row shaped like the INSERT ... RETURNING / SELECT columns."""
    base = dict(
        ai_use_id=UUID(AI_USE_ID),
        public_ref="airisk_01HZZZ",
        workflow_id=UUID(WORKFLOW_ID),
        use_name="churn scoring",
        risk_tier="high",
        annex_iii_category=None,
        rationale=None,
        controls_required=["K-23_HUMAN_OVERSIGHT", "K-25_MODEL_CARD",
                           "K-26_MONITORING", "K-6_AUDIT_LOG"],
        status="active",
        classified_at=datetime.datetime(2026, 6, 3),
    )
    base.update(overrides)
    return _row(**base)


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def record_mock():
    return AsyncMock(return_value=uuid4())


@pytest.fixture
def app_client(conn, record_mock):
    with patch("ai_orchestrator.routers.compliance_risk.acquire_for_tenant",
               _ctx(conn)), \
         patch("ai_orchestrator.routers.compliance_risk.record_ai_call",
               record_mock):
        import ai_orchestrator.routers.compliance_risk as cr
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(cr.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


# ─── classify ────────────────────────────────────────────────────────


def test_classify_high_tier_active_with_controls(app_client, conn, record_mock):
    conn.fetchrow.return_value = _risk_row()

    resp = app_client.post(
        "/compliance/ai-uses",
        json={"use_name": "churn scoring", "risk_tier": "high",
              "workflow_id": WORKFLOW_ID},
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "K-23_HUMAN_OVERSIGHT" in body["controls_required"]
    assert body["status"] == "active"

    # An INSERT into ai_use_risk_register must have been issued.
    insert_sql = conn.fetchrow.await_args.args[0]
    assert "INSERT INTO ai_use_risk_register" in insert_sql

    # K-6 audit: record_ai_call awaited exactly once for risk_classification.
    record_mock.assert_awaited_once()
    assert record_mock.await_args.kwargs["task_kind"] == "risk_classification"


def test_classify_prohibited_is_blocked_no_controls(app_client, conn, record_mock):
    conn.fetchrow.return_value = _risk_row(
        risk_tier="prohibited", controls_required=[], status="blocked",
    )

    resp = app_client.post(
        "/compliance/ai-uses",
        json={"use_name": "social scoring", "risk_tier": "prohibited"},
        headers=HEADERS,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["controls_required"] == []


def test_classify_invalid_tier_422(app_client, conn):
    resp = app_client.post(
        "/compliance/ai-uses",
        json={"use_name": "x", "risk_tier": "banana"},
        headers=HEADERS,
    )
    assert resp.status_code == 422, resp.text


def test_classify_missing_enterprise_header_422(app_client):
    resp = app_client.post(
        "/compliance/ai-uses",
        json={"use_name": "x", "risk_tier": "high"},
        headers={"X-User-ID": USER_ID},  # no X-Enterprise-ID
    )
    assert resp.status_code == 422


# ─── read ────────────────────────────────────────────────────────────


def test_get_latest_for_workflow_returns_row(app_client, conn):
    conn.fetchrow.return_value = _risk_row()

    resp = app_client.get(
        f"/compliance/ai-uses?workflow_id={WORKFLOW_ID}",
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["workflow_id"] == WORKFLOW_ID
    assert body["risk_tier"] == "high"
