"""
Tests for run-aware template eligibility (GET /analytics/templates?run_id=).

Incident 2026-07-10 (demo AABW): the FE step-4 picker called
/analytics/templates with NO profile params, so detected_types=∅ and
row_count=0 → every template rendered "Dữ liệu hiện tại có thể chưa đủ
điều kiện" even for a clean 108-row sales dataset. The endpoint now
accepts run_id (+ X-Enterprise-ID) and profiles the Silver dataset
server-side; explicit query params still win when provided.
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.reasoning.legacy_analytics.template_registry import (
    profile_from_df,
)
from ai_orchestrator.routers import analytics as analytics_router


ENTERPRISE = str(uuid4())


def _sales_df() -> pd.DataFrame:
    n = 120  # above churn's min_rows=100
    return pd.DataFrame({
        "date":     pd.to_datetime(["2026-01-04"] * n),
        "name":     ["Co.opmart"] * n,
        "product":  ["Cà chua"] * n,
        "quantity": pd.Series([90] * n, dtype="int64"),
        "revenue":  pd.Series([1980000.0] * n, dtype="float64"),
    })


# ── profile_from_df ──────────────────────────────────────────────────────────

def test_profile_detects_canonical_types_and_rows():
    types, purpose, rows = profile_from_df(_sales_df())
    assert "date" in types
    assert "integer" in types
    assert "decimal" in types
    assert "text" in types
    assert rows == 120


def test_profile_infers_transaction_purpose_for_date_plus_numeric():
    _, purpose, _ = profile_from_df(_sales_df())
    assert purpose == "transaction_list"


def test_profile_no_purpose_without_date_axis():
    df = pd.DataFrame({"region": ["R0", "R1"], "amount": [1.0, 2.0]})
    _, purpose, _ = profile_from_df(df)
    assert purpose is None


# ── endpoint with run_id ─────────────────────────────────────────────────────

@pytest.fixture
def client():
    app = FastAPI()
    # Same mount shape as main.py:140
    app.include_router(analytics_router.router, prefix="/analytics")
    return TestClient(app)


def _eligibility(res_json: list, template_id: str) -> bool:
    return next(t["eligible"] for t in res_json if t["template_id"] == template_id)


def test_run_id_mode_marks_time_series_and_churn_eligible(client):
    with patch.object(analytics_router, "_load_silver",
                      AsyncMock(return_value=_sales_df())):
        r = client.get(
            "/analytics/templates",
            params={"run_id": str(uuid4())},
            headers={"X-Enterprise-ID": ENTERPRISE},
        )
    assert r.status_code == 200
    body = r.json()
    assert _eligibility(body, "summary_stats") is True
    assert _eligibility(body, "time_series") is True
    assert _eligibility(body, "churn") is True


def test_run_id_mode_with_empty_silver_falls_back_to_ineligible(client):
    with patch.object(analytics_router, "_load_silver",
                      AsyncMock(return_value=None)):
        r = client.get(
            "/analytics/templates",
            params={"run_id": str(uuid4())},
            headers={"X-Enterprise-ID": ENTERPRISE},
        )
    assert r.status_code == 200
    assert _eligibility(r.json(), "time_series") is False


def test_without_run_id_behaves_as_before(client):
    r = client.get("/analytics/templates",
                   params={"detected_types": "date,currency", "row_count": 50})
    assert r.status_code == 200
    assert _eligibility(r.json(), "time_series") is True
    # churn needs 100 rows → stays ineligible at 50
    assert _eligibility(r.json(), "churn") is False
