"""
P15-S9 D7 — tests for ROI dashboard router.

Mocks ``acquire_for_tenant`` on the economics router module so the
in-memory mock conn powers the test (matches test_north_star.py
pattern). The persistence helpers (fetch_current_digest / fetch_trend)
run their real SQL against the mocked asyncpg conn → returns lists of
synthetic Records, and the route's response shape gets exercised end-
to-end without a Postgres container.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


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
    with patch("ai_orchestrator.routers.economics.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.economics as econ
        test_app = FastAPI(title="Kaori AI Orchestrator (test — D7)")
        test_app.include_router(econ.router)
        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


def _digest_record(*, month=date(2026, 4, 1), nov="20000000.0000",
                   revision=1, **overrides) -> MagicMock:
    """asyncpg Record-like object — supports row['col'] dict-style access."""
    base = {
        "enterprise_id": UUID(ENTERPRISE),
        "month_start": month,
        "revenue_vnd": Decimal("100000000.0000"),
        "cost_vnd": Decimal("80000000.0000"),
        "nov_vnd": Decimal(nov),
        "revenue_method": "pre_post",
        "revenue_confidence": Decimal("0.7000"),
        "people_cost_vnd": Decimal("40000000.0000"),
        "ai_cost_vnd": Decimal("5000000.0000"),
        "infra_cost_vnd": Decimal("20000000.0000"),
        "integration_cost_vnd": Decimal("15000000.0000"),
        "revision": revision,
    }
    base.update(overrides)
    rec = MagicMock()
    rec.__getitem__ = lambda _self, k: base[k]
    return rec


# ─── GET /economics/nov/current ─────────────────────────────────────


class TestCurrentNov:

    def test_returns_no_data_when_digest_missing(self, app_client, conn):
        """New tenant — no digest yet. Return 200 with current=null
        + classification=no_data so the dashboard can render an empty
        state instead of an error tile."""
        conn.fetchrow.return_value = None
        resp = app_client.get("/economics/nov/current", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["current"] is None
        assert body["classification"] == "no_data"

    def test_returns_positive_classification_when_nov_positive(self, app_client, conn):
        conn.fetchrow.return_value = _digest_record(nov="20000000.0000")
        resp = app_client.get("/economics/nov/current", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["classification"] == "positive"
        assert body["current"]["nov_vnd"] == "20000000.0000"
        assert body["current"]["is_negative"] is False
        assert body["current"]["month_start"] == "2026-04-01"
        assert body["current"]["revision"] == 1
        # Decimal precision preserved as string (no float lossy round-trip)
        assert body["current"]["revenue_vnd"] == "100000000.0000"

    def test_returns_negative_classification_when_nov_below_zero(self, app_client, conn):
        conn.fetchrow.return_value = _digest_record(nov="-5000000.0000")
        resp = app_client.get("/economics/nov/current", headers=HEADERS)
        body = resp.json()
        assert body["classification"] == "negative"
        assert body["current"]["is_negative"] is True

    def test_bad_enterprise_id_header_returns_400(self, app_client):
        """K-14 RFC 7807 problem — non-UUID header rejected at the
        router edge (not tunneled through pydantic 422 noise)."""
        resp = app_client.get(
            "/economics/nov/current",
            headers={"X-Enterprise-Id": "not-a-uuid"},
        )
        assert resp.status_code == 400
        body = resp.json()
        # FastAPI wraps detail dict under 'detail' key
        assert body["detail"]["title"].startswith("X-Enterprise-Id")


# ─── GET /economics/nov/trend ───────────────────────────────────────


class TestNovTrend:

    def test_default_returns_up_to_six_months_oldest_first(self, app_client, conn):
        # Persistence layer reverses DESC SQL order in Python → expect
        # oldest first in the response. Provide DESC mock data; helper
        # reverses to ASC.
        conn.fetch.return_value = [
            _digest_record(month=date(2026, 4, 1), nov="20000000.0000"),
            _digest_record(month=date(2026, 3, 1), nov="15000000.0000"),
            _digest_record(month=date(2026, 2, 1), nov="10000000.0000"),
        ]
        resp = app_client.get("/economics/nov/trend", headers=HEADERS)
        assert resp.status_code == 200
        months = resp.json()["months"]
        assert len(months) == 3
        # Oldest first
        assert [m["month_start"] for m in months] == [
            "2026-02-01", "2026-03-01", "2026-04-01",
        ]

    def test_explicit_months_param_passed_to_query(self, app_client, conn):
        """`?months=12` should reach the DB layer; pydantic Query bounds
        enforce 1 ≤ months ≤ 24."""
        conn.fetch.return_value = []
        resp = app_client.get(
            "/economics/nov/trend?months=12", headers=HEADERS,
        )
        assert resp.status_code == 200
        # The persistence helper SQL was called with months=12
        args = conn.fetch.await_args.args
        # asyncpg signature: fetch(query, *params); params include months
        assert 12 in args

    def test_months_out_of_range_returns_422(self, app_client):
        """Bound check — pydantic Query(ge=1, le=24) blocks abuse."""
        resp = app_client.get(
            "/economics/nov/trend?months=100", headers=HEADERS,
        )
        assert resp.status_code == 422


# ─── Persistence helper unit ────────────────────────────────────────


@pytest.mark.asyncio
async def test_persistence_fetch_current_returns_none_when_empty():
    """fetch_current_digest must return None (not raise) when the
    tenant has no digest yet — caller composes 'no_data' from None."""
    from ai_orchestrator.org_intel.economics.persistence import fetch_current_digest

    conn = AsyncMock()
    conn.fetchrow.return_value = None
    result = await fetch_current_digest(conn, enterprise_id=UUID(ENTERPRISE))
    assert result is None


@pytest.mark.asyncio
async def test_persistence_fetch_trend_reverses_to_ascending_order():
    """SQL returns DESC for index hit; Python reverses so the chart
    layer can plot left-to-right without sorting."""
    from ai_orchestrator.org_intel.economics.persistence import fetch_trend

    conn = AsyncMock()
    conn.fetch.return_value = [
        _digest_record(month=date(2026, 4, 1)),
        _digest_record(month=date(2026, 3, 1)),
        _digest_record(month=date(2026, 2, 1)),
    ]
    rows = await fetch_trend(conn, enterprise_id=UUID(ENTERPRISE), months=6)
    assert [r.month_start for r in rows] == [
        date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1),
    ]
