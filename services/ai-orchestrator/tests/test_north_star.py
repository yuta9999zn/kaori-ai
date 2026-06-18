"""
F-060 — tests for North Star tile + per-customer action endpoints.

Same mock-asyncpg pattern as test_decisions.py: patch
``acquire_for_tenant`` on the router module so the in-memory mock conn
powers the test instead of a real Postgres.

Cases:
  POST /customers/{id}/action — happy 200 + Kafka emit; 404 when row
    missing; Kafka failure does not break response.
  GET  /dashboard/north-star  — returns 4 numbers + recent_actions list.
  GET  /customers/at-risk     — happy + cursor + actioned filter +
    invalid cursor.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
HEADERS    = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    """Standalone TestClient mounting only the F-060 router."""
    with patch("ai_orchestrator.routers.north_star.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.north_star as ns
        test_app = FastAPI(title="Kaori AI Orchestrator (test — F-060)")
        test_app.include_router(ns.router)
        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


def _row(**overrides) -> MagicMock:
    base = {
        "customer_external_id": "CUST-001",
        "is_actioned":          False,
        "actioned_at":          None,
        "actioned_by_user":     None,
        "revenue_at_risk":      150_000_000.0,
        "last_purchase_at":     datetime(2026, 4, 1, tzinfo=timezone.utc),
        "purchase_count":       12,
        "computed_at":          datetime(2026, 5, 3, tzinfo=timezone.utc),
    }
    base.update(overrides)
    rec = MagicMock()
    rec.__getitem__ = lambda _self, k: base[k]
    rec.get = lambda k, default=None: base.get(k, default)
    return rec


# ===========================================================================
# POST /customers/{id}/action
# ===========================================================================

class TestUpsertCustomerAction:

    def test_404_when_customer_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.post(
            "/customers/UNKNOWN/action",
            headers=HEADERS, json={"is_actioned": True},
        )
        assert resp.status_code == 404
        assert "gold_features" in resp.json()["detail"]

    def test_happy_path_writes_row_and_emits_kafka(self, app_client, conn):
        ts = datetime(2026, 5, 3, 12, tzinfo=timezone.utc)
        conn.fetchrow.return_value = _row(
            is_actioned=True, actioned_at=ts,
            actioned_by_user=uuid.UUID(USER),
            revenue_at_risk=200_000_000.0,
        )

        with patch("ai_orchestrator.routers.north_star.emit",
                   new_callable=AsyncMock) as emit_mock:
            resp = app_client.post(
                "/customers/CUST-001/action",
                headers=HEADERS,
                json={"is_actioned": True, "notes": "Renewed yearly contract"},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["customer_external_id"] == "CUST-001"
        assert body["is_actioned"] is True
        assert body["actioned_at"].startswith("2026-05-03")
        assert body["revenue_at_risk"] == 200_000_000.0

        emit_mock.assert_awaited_once()
        topic, payload = emit_mock.await_args.args
        assert topic == "kaori.feedback.actions"
        assert payload["action"]        == "customer.actioned"
        assert payload["decision_type"] == "customer_action"
        assert payload["override_value"] == "true"
        assert payload["reason"] == "Renewed yearly contract"
        assert payload["user_id"] == USER

    def test_unaction_emits_unactioned_kafka(self, app_client, conn):
        conn.fetchrow.return_value = _row(
            is_actioned=False, actioned_at=None, actioned_by_user=None,
        )

        with patch("ai_orchestrator.routers.north_star.emit",
                   new_callable=AsyncMock) as emit_mock:
            resp = app_client.post(
                "/customers/CUST-001/action",
                headers=HEADERS,
                json={"is_actioned": False},
            )

        assert resp.status_code == 200
        assert resp.json()["is_actioned"] is False
        topic, payload = emit_mock.await_args.args
        assert payload["action"] == "customer.unactioned"
        assert payload["override_value"] == "false"

    def test_kafka_emit_failure_does_not_break_response(self, app_client, conn):
        conn.fetchrow.return_value = _row(
            is_actioned=True,
            actioned_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        )

        with patch("ai_orchestrator.routers.north_star.emit",
                   new_callable=AsyncMock) as emit_mock:
            emit_mock.side_effect = RuntimeError("kafka down")
            resp = app_client.post(
                "/customers/CUST-001/action",
                headers=HEADERS,
                json={"is_actioned": True},
            )

        # DB write succeeded; Kafka failure is logged + swallowed.
        assert resp.status_code == 200

    def test_validation_rejects_overlong_notes(self, app_client):
        resp = app_client.post(
            "/customers/CUST-001/action",
            headers=HEADERS,
            json={"is_actioned": True, "notes": "x" * 2001},
        )
        assert resp.status_code == 422


# ===========================================================================
# GET /dashboard/north-star
# ===========================================================================

class TestNorthStarTile:

    def test_zero_state_returns_zeros(self, app_client, conn):
        # First fetchrow = summary; fetch = recent_actions list.
        zero_summary = MagicMock()
        zero_summary.__getitem__ = lambda _self, k: {
            "total_at_risk":   0,
            "resolved":        0,
            "at_risk_count":   0,
            "actioned_count":  0,
        }[k]
        zero_summary.get = lambda k, default=None: 0

        conn.fetchrow.return_value = zero_summary
        conn.fetch.return_value = []

        resp = app_client.get("/dashboard/north-star", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_at_risk_vnd"]   == 0
        assert body["resolved_vnd"]        == 0
        assert body["resolution_rate_pct"] == 0
        assert body["at_risk_count"]       == 0
        assert body["actioned_count"]      == 0
        assert body["recent_actions"]      == []

    def test_partial_resolution_computes_rate(self, app_client, conn):
        summary = MagicMock()
        summary.__getitem__ = lambda _self, k: {
            "total_at_risk":   1_000_000_000.0,
            "resolved":          250_000_000.0,
            "at_risk_count":    20,
            "actioned_count":    5,
        }[k]
        summary.get = lambda k, default=None: None

        recent_row = MagicMock()
        recent_row.__getitem__ = lambda _self, k: {
            "customer_external_id": "CUST-001",
            "revenue_at_risk":      150_000_000.0,
            "actioned_at":          datetime(2026, 5, 3, tzinfo=timezone.utc),
            "actioned_by_user":     uuid.UUID(USER),
        }[k]

        conn.fetchrow.return_value = summary
        conn.fetch.return_value    = [recent_row]

        resp = app_client.get("/dashboard/north-star", headers=HEADERS)
        body = resp.json()
        assert body["total_at_risk_vnd"]   == 1_000_000_000.0
        assert body["resolved_vnd"]        ==   250_000_000.0
        assert body["resolution_rate_pct"] == 25.0
        assert body["at_risk_count"]       == 20
        assert body["actioned_count"]      == 5
        assert len(body["recent_actions"]) == 1
        assert body["recent_actions"][0]["customer_external_id"] == "CUST-001"


# ===========================================================================
# GET /customers/at-risk
# ===========================================================================

class TestAtRiskList:

    def test_empty_returns_no_cursor(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get("/customers/at-risk", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

    def test_returns_rows_and_cursor_when_more_exist(self, app_client, conn):
        rows = [_row(customer_external_id=f"CUST-{i:03d}",
                     revenue_at_risk=100_000_000.0 - i * 1_000_000)
                for i in range(3)]
        # +1 sentinel for has_more
        conn.fetch.return_value = rows
        resp = app_client.get("/customers/at-risk?limit=2", headers=HEADERS)
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["next_cursor"] is not None
        # Cursor encodes the last returned row.
        import base64
        decoded = base64.urlsafe_b64decode(
            body["next_cursor"] + "=" * (-len(body["next_cursor"]) % 4),
        ).decode()
        assert "CUST-001" in decoded

    def test_invalid_cursor_returns_400(self, app_client):
        resp = app_client.get(
            "/customers/at-risk?cursor=not-base64-at-all!!",
            headers=HEADERS,
        )
        assert resp.status_code == 400

    def test_actioned_filter_appends_where_clause(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            "/customers/at-risk?actioned=true",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        # Confirm the SQL captured by the mock includes the is_actioned filter.
        sql = conn.fetch.await_args.args[0]
        assert "is_actioned" in sql
        # Param bound at the right position (after enterprise_id).
        bound_params = conn.fetch.await_args.args[1:]
        assert True in bound_params

    def test_limit_above_max_returns_422(self, app_client):
        resp = app_client.get("/customers/at-risk?limit=1000", headers=HEADERS)
        assert resp.status_code == 422
