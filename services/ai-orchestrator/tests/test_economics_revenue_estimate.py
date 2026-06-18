"""
P15-S10 D5 — HTTP-surface tests for /economics/revenue/estimate dispatcher.

Pure function inputs — no DB access. Just confirms the 3 method
discriminators dispatch correctly + bad-method/missing-input branches
return RFC 7807 envelopes per CLAUDE.md K-14.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


@pytest.fixture
def client():
    import ai_orchestrator.routers.economics as econ_module
    test_app = FastAPI()
    test_app.include_router(econ_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def test_pre_post_method_returns_decimal_strings(client):
    resp = client.post(
        "/economics/revenue/estimate",
        headers=HEADERS,
        json={
            "method": "pre_post",
            "pre_post": {
                "revenue_30d_before_vnd": "100000000",
                "revenue_30d_after_vnd":  "115000000",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "pre_post"
    assert body["revenue_vnd"] == "15000000"
    assert float(body["confidence"]) > 0


def test_a_b_method_with_decent_sample_size(client):
    resp = client.post(
        "/economics/revenue/estimate",
        headers=HEADERS,
        json={
            "method": "a_b",
            "a_b": {
                "control_revenue_vnd":   "50000000",
                "treatment_revenue_vnd": "60000000",
                "control_group_size":   500,
                "treatment_group_size": 500,
                "total_population":     2000,
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "a_b"
    # delta per user = (60M/500 - 50M/500) = 20K → x 2000 = 40M
    assert body["revenue_vnd"].startswith("40000000")
    assert float(body["confidence"]) >= 0.8   # sample size ≥ 100 → 0.8 floor


def test_industry_benchmark_method(client):
    resp = client.post(
        "/economics/revenue/estimate",
        headers=HEADERS,
        json={
            "method": "industry_benchmark",
            "industry_benchmark": {
                "industry": "RETAIL",
                "annual_revenue_vnd": "12000000000",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["method"] == "industry_benchmark"
    # RETAIL = 5% annual / 12 → 50M/month
    assert float(body["revenue_vnd"]) == 50000000.0


def test_unknown_method_400(client):
    resp = client.post(
        "/economics/revenue/estimate",
        headers=HEADERS,
        json={"method": "magic"},
    )
    assert resp.status_code == 400
    assert resp.json().get("detail", {}).get("errcode") == "USR-ERR4"


def test_missing_method_inputs_400(client):
    resp = client.post(
        "/economics/revenue/estimate",
        headers=HEADERS,
        json={"method": "pre_post"},
    )
    assert resp.status_code == 400
    assert resp.json().get("detail", {}).get("errcode") == "USR-ERR3"
