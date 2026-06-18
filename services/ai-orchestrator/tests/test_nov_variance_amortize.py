"""Tests for NOV-REV-006 variance + NOV-CST-012 cost amortization.

Pure-function tests on the calculators + HTTP-surface tests on the
two endpoints (POST /economics/revenue/estimate method=variance and
POST /economics/cost/compute).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.economics.cost import (
    AmortizedCost,
    amortize_setup_cost,
    monthly_run_rate,
)
from ai_orchestrator.org_intel.economics.revenue import (
    VarianceAnalysis,
    estimate_revenue_variance,
)


ENT = str(uuid4())
HEADERS = {"X-Enterprise-ID": ENT}


# ─── NOV-REV-006 — estimate_revenue_variance ────────────────────────


class TestVarianceCalculator:

    def test_on_target_under_10pct(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("100_000_000"),
            actual_vnd=Decimal("105_000_000"),
        )
        assert v.verdict == "on_target"
        assert v.variance_vnd == Decimal("5_000_000")
        assert v.relative_variance == Decimal("0.0500")

    def test_on_target_at_exactly_10pct(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("100"), actual_vnd=Decimal("110"),
        )
        assert v.verdict == "on_target"

    def test_modest_drift_between_10_and_30(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("100"), actual_vnd=Decimal("125"),
        )
        assert v.verdict == "modest_drift"

    def test_significant_drift_between_30_and_50(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("100"), actual_vnd=Decimal("145"),
        )
        assert v.verdict == "significant_drift"

    def test_unreliable_over_50pct(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("100"), actual_vnd=Decimal("250"),
        )
        assert v.verdict == "estimate_unreliable"

    def test_negative_variance_flags_overestimate(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("100"), actual_vnd=Decimal("80"),
        )
        # 20% drop → modest_drift on |relative|
        assert v.verdict == "modest_drift"
        assert v.variance_vnd == Decimal("-20")

    def test_predicted_zero_actual_zero(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("0"), actual_vnd=Decimal("0"),
        )
        assert v.verdict == "on_target"

    def test_predicted_zero_actual_positive(self):
        v = estimate_revenue_variance(
            predicted_vnd=Decimal("0"), actual_vnd=Decimal("100"),
        )
        assert v.verdict == "estimate_unreliable"


# ─── NOV-CST-012 — amortize_setup_cost ──────────────────────────────


class TestAmortizeSetupCost:

    def test_straight_line_12_months(self):
        a = amortize_setup_cost(
            total_setup_vnd=Decimal("12_000_000"),
            term_months=12, months_elapsed=1,
        )
        assert a.monthly_amortized_vnd == Decimal("1_000_000.0000")
        assert a.months_remaining == 11
        assert a.cumulative_amortized_vnd == Decimal("1_000_000.0000")
        assert a.remaining_to_amortize_vnd == Decimal("11_000_000.0000")
        assert a.fully_amortized is False

    def test_fully_amortized_at_term_end(self):
        a = amortize_setup_cost(
            total_setup_vnd=Decimal("12_000_000"),
            term_months=12, months_elapsed=12,
        )
        assert a.fully_amortized is True
        assert a.months_remaining == 0
        assert a.cumulative_amortized_vnd == Decimal("12_000_000.0000")
        assert a.remaining_to_amortize_vnd == Decimal("0")

    def test_caps_cumulative_at_total(self):
        """months_elapsed past term — cumulative should NOT exceed total."""
        a = amortize_setup_cost(
            total_setup_vnd=Decimal("12_000_000"),
            term_months=12, months_elapsed=24,
        )
        assert a.fully_amortized is True
        assert a.cumulative_amortized_vnd == Decimal("12_000_000.0000")
        assert a.remaining_to_amortize_vnd == Decimal("0")
        assert a.months_remaining == 0   # max(0, 12-24) = 0

    def test_24_month_term(self):
        a = amortize_setup_cost(
            total_setup_vnd=Decimal("24_000_000"),
            term_months=24, months_elapsed=6,
        )
        assert a.monthly_amortized_vnd == Decimal("1_000_000.0000")
        assert a.cumulative_amortized_vnd == Decimal("6_000_000.0000")

    def test_negative_setup_rejected(self):
        with pytest.raises(ValueError):
            amortize_setup_cost(
                total_setup_vnd=Decimal("-100"),
                term_months=12, months_elapsed=1,
            )

    def test_zero_term_rejected(self):
        with pytest.raises(ValueError):
            amortize_setup_cost(
                total_setup_vnd=Decimal("100"),
                term_months=0, months_elapsed=0,
            )

    def test_negative_elapsed_rejected(self):
        with pytest.raises(ValueError):
            amortize_setup_cost(
                total_setup_vnd=Decimal("100"),
                term_months=12, months_elapsed=-1,
            )


class TestMonthlyRunRate:

    def test_average_of_three_months(self):
        out = monthly_run_rate(monthly_total_costs=[
            Decimal("100"), Decimal("200"), Decimal("300"),
        ])
        assert out == Decimal("200.0000")

    def test_empty_list_zero(self):
        assert monthly_run_rate(monthly_total_costs=[]) == Decimal("0")


# ─── HTTP surface — POST /economics/revenue/estimate variance ───────


@pytest.fixture
def client():
    from ai_orchestrator.routers import economics
    from ai_orchestrator.shared.errors import register_problem_handlers
    app = FastAPI()
    app.include_router(economics.router)
    register_problem_handlers(app)
    return TestClient(app)


class TestVarianceEndpoint:

    def test_variance_method_happy_path(self, client):
        r = client.post(
            "/economics/revenue/estimate",
            json={
                "method": "variance",
                "variance": {
                    "predicted_vnd": "100000000",
                    "actual_vnd":    "105000000",
                    "predicted_confidence": "0.7",
                },
            },
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["method"] == "variance"
        assert body["revenue_vnd"] == "105000000"
        assert body["variance"]["verdict"] == "on_target"
        assert body["variance"]["predicted_vnd"] == "100000000"
        assert body["variance"]["variance_vnd"] == "5000000"

    def test_variance_method_missing_inputs(self, client):
        r = client.post(
            "/economics/revenue/estimate",
            json={"method": "variance"},   # no variance object
            headers=HEADERS,
        )
        # Global RFC 7807 handler strips dict-detail per memory
        # feedback_rfc7807_dict_detail_stripped; just assert status.
        assert r.status_code == 400

    def test_unknown_method_returns_400(self, client):
        r = client.post(
            "/economics/revenue/estimate",
            json={"method": "random_walk"},
            headers=HEADERS,
        )
        assert r.status_code == 400


# ─── HTTP surface — POST /economics/cost/compute ────────────────────


class TestCostComputeEndpoint:

    def test_happy_path_12_month(self, client):
        r = client.post(
            "/economics/cost/compute",
            json={
                "total_setup_vnd": "12000000",
                "term_months": 12,
                "months_elapsed": 1,
            },
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # _dec_str preserves quantize(0.0001) trailing zeros
        assert body["monthly_amortized_vnd"] == "1000000.0000"
        assert body["months_remaining"] == 11
        assert body["fully_amortized"] is False

    def test_term_months_out_of_range_rejected(self, client):
        r = client.post(
            "/economics/cost/compute",
            json={
                "total_setup_vnd": "1000000",
                "term_months": 0,           # min=1 enforced by Pydantic
                "months_elapsed": 0,
            },
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_negative_setup_returns_400(self, client):
        r = client.post(
            "/economics/cost/compute",
            json={
                "total_setup_vnd": "-1000",
                "term_months": 12,
                "months_elapsed": 1,
            },
            headers=HEADERS,
        )
        assert r.status_code == 400
