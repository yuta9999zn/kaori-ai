"""NOV-RPT-020 — CFO quarterly digest tests.

Pure-function tests on build_quarterly_digest + helpers + HTTP-surface
test on GET /economics/reports/manager-digest.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.economics import (
    MonthlyDigestRow,
    build_quarterly_digest,
    quarter_bounds,
    quarter_label,
)


T = UUID("11111111-1111-1111-1111-111111111111")


def _digest_row(month_start: date, *, revenue=100_000_000, cost=80_000_000,
                 people=30_000_000, ai=10_000_000, infra=20_000_000,
                 integration=20_000_000) -> MonthlyDigestRow:
    return MonthlyDigestRow(
        enterprise_id=T,
        month_start=month_start,
        revenue_vnd=Decimal(revenue),
        cost_vnd=Decimal(cost),
        nov_vnd=Decimal(revenue) - Decimal(cost),
        revenue_method="pre_post",
        revenue_confidence=Decimal("0.7"),
        people_cost_vnd=Decimal(people),
        ai_cost_vnd=Decimal(ai),
        infra_cost_vnd=Decimal(infra),
        integration_cost_vnd=Decimal(integration),
        revision=1,
    )


# ─── Helpers ────────────────────────────────────────────────────────


class TestQuarterHelpers:

    def test_quarter_label(self):
        assert quarter_label(date(2026, 1, 1))  == "2026-Q1"
        assert quarter_label(date(2026, 3, 31)) == "2026-Q1"
        assert quarter_label(date(2026, 4, 1))  == "2026-Q2"
        assert quarter_label(date(2026, 12, 31)) == "2026-Q4"

    def test_quarter_bounds_q1(self):
        s, e = quarter_bounds("2026-Q1")
        assert s == date(2026, 1, 1)
        assert e == date(2026, 3, 31)

    def test_quarter_bounds_q2(self):
        s, e = quarter_bounds("2026-Q2")
        assert s == date(2026, 4, 1)
        # Bounds approximated to 30 — fine for BETWEEN since 1st-of-month dates
        assert e == date(2026, 6, 30)

    def test_quarter_bounds_q4(self):
        s, e = quarter_bounds("2026-Q4")
        assert s == date(2026, 10, 1)
        assert e == date(2026, 12, 31)


# ─── build_quarterly_digest ─────────────────────────────────────────


class TestBuildQuarterlyDigest:

    def test_full_quarter_3_months(self):
        rows = [
            _digest_row(date(2026, 1, 1)),
            _digest_row(date(2026, 2, 1)),
            _digest_row(date(2026, 3, 1)),
        ]
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q1", monthly_rows=rows,
        )
        assert d.month_count == 3
        assert d.revenue_total_vnd == Decimal("300_000_000")
        assert d.cost_total_vnd == Decimal("240_000_000")
        assert d.nov_total_vnd == Decimal("60_000_000")
        assert d.monthly_run_rate_vnd == Decimal("80_000_000.0000")
        assert d.cost_breakdown.people_vnd == Decimal("90_000_000")
        assert d.qoq is None
        assert d.yoy is None
        assert any("3 tháng dữ liệu" in n for n in d.notes)

    def test_partial_quarter_1_month(self):
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q1",
            monthly_rows=[_digest_row(date(2026, 1, 1))],
        )
        assert d.month_count == 1
        assert d.monthly_run_rate_vnd == Decimal("80_000_000.0000")

    def test_empty_quarter(self):
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q1", monthly_rows=[],
        )
        assert d.month_count == 0
        assert d.revenue_total_vnd == Decimal("0")
        assert d.monthly_run_rate_vnd == Decimal("0")

    def test_filters_rows_outside_quarter(self):
        rows = [
            _digest_row(date(2025, 12, 1)),   # outside
            _digest_row(date(2026, 1, 1)),
            _digest_row(date(2026, 2, 1)),
            _digest_row(date(2026, 4, 1)),    # outside
        ]
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q1", monthly_rows=rows,
        )
        assert d.month_count == 2

    def test_qoq_modest_growth(self):
        this_q = [_digest_row(date(2026, 4, 1), cost=110_000_000)]
        prev_q = [_digest_row(date(2026, 1, 1), cost=100_000_000)]
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q2",
            monthly_rows=this_q, prev_quarter_rows=prev_q,
        )
        assert d.qoq is not None
        assert d.qoq.verdict == "modest"
        assert d.qoq.relative_delta == Decimal("0.1000")

    def test_qoq_major_swing(self):
        this_q = [_digest_row(date(2026, 4, 1), cost=200_000_000)]
        prev_q = [_digest_row(date(2026, 1, 1), cost=100_000_000)]
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q2",
            monthly_rows=this_q, prev_quarter_rows=prev_q,
        )
        assert d.qoq.verdict == "major"
        assert d.qoq.relative_delta == Decimal("1.0000")

    def test_yoy_comparison(self):
        this_q = [_digest_row(date(2026, 1, 1), cost=120_000_000)]
        yoy = [_digest_row(date(2025, 1, 1), cost=100_000_000)]
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q1",
            monthly_rows=this_q, same_quarter_last_year_rows=yoy,
        )
        assert d.yoy is not None
        # 20% lift → significant per band (15-30%)
        assert d.yoy.verdict == "significant"
        assert d.yoy.relative_delta == Decimal("0.2000")

    def test_amortized_setup_folded_in(self):
        rows = [_digest_row(date(2026, 1, 1)),
                 _digest_row(date(2026, 2, 1)),
                 _digest_row(date(2026, 3, 1))]
        d = build_quarterly_digest(
            enterprise_id=str(T), quarter="2026-Q1",
            monthly_rows=rows,
            amortized_setup_monthly_vnd=Decimal("1_000_000"),
        )
        # 1M × 3 months = 3M in the quarter
        assert d.amortized_setup_vnd == Decimal("3_000_000.0000")
        assert any("setup" in n.lower() or "phân bổ" in n for n in d.notes)


# ─── HTTP surface ───────────────────────────────────────────────────


@pytest.fixture
def client():
    from ai_orchestrator.routers import economics
    from ai_orchestrator.shared.errors import register_problem_handlers

    @asynccontextmanager
    async def _acq(_eid):
        conn = MagicMock()
        # First call (this quarter): 3 rows
        # Second (prev quarter): empty
        # Third (yoy): empty
        conn.fetch = AsyncMock(side_effect=[
            [_pg_row(date(2026, 1, 1)),
             _pg_row(date(2026, 2, 1)),
             _pg_row(date(2026, 3, 1))],
            [],
            [],
        ])
        yield conn

    with patch("ai_orchestrator.routers.economics.acquire_for_tenant", _acq):
        app = FastAPI()
        app.include_router(economics.router)
        register_problem_handlers(app)
        with TestClient(app) as c:
            yield c


def _pg_row(month_start):
    """asyncpg row-like that responds to __getitem__."""
    data = {
        "enterprise_id":      T,
        "month_start":        month_start,
        "revenue_vnd":        Decimal("100_000_000"),
        "cost_vnd":           Decimal("80_000_000"),
        "nov_vnd":            Decimal("20_000_000"),
        "revenue_method":     "pre_post",
        "revenue_confidence": Decimal("0.7"),
        "people_cost_vnd":    Decimal("30_000_000"),
        "ai_cost_vnd":        Decimal("10_000_000"),
        "infra_cost_vnd":     Decimal("20_000_000"),
        "integration_cost_vnd": Decimal("20_000_000"),
        "revision":           1,
    }
    row = MagicMock()
    row.__getitem__ = lambda _s, k: data[k]
    return row


HEADERS = {"X-Enterprise-ID": str(T)}


class TestManagerDigestEndpoint:

    def test_happy_path_quarterly(self, client):
        r = client.get(
            "/economics/reports/manager-digest",
            params={"period": "quarterly", "quarter": "2026-Q1"},
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["quarter"] == "2026-Q1"
        assert body["month_count"] == 3
        assert body["revenue_total_vnd"] == "300000000"
        assert body["cost_total_vnd"] == "240000000"
        assert body["nov_total_vnd"] == "60000000"
        assert body["cost_breakdown"]["people_vnd"] == "90000000"
        assert isinstance(body["notes"], list)
        assert len(body["notes"]) >= 1

    def test_period_other_than_quarterly_rejected(self, client):
        r = client.get(
            "/economics/reports/manager-digest",
            params={"period": "monthly"},
            headers=HEADERS,
        )
        assert r.status_code == 400

    def test_invalid_quarter_label(self, client):
        r = client.get(
            "/economics/reports/manager-digest",
            params={"quarter": "not-a-quarter"},
            headers=HEADERS,
        )
        assert r.status_code == 400
