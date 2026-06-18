"""Tests for /cdfl/plan-next-action endpoint — P15-S11 Tuần 4."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


@pytest.fixture
def client() -> TestClient:
    import ai_orchestrator.routers.cdfl as cdfl_module

    test_app = FastAPI()
    test_app.include_router(cdfl_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def test_plan_returns_top_k_ranked(client: TestClient):
    """Basic plan request → top-K actions returned in ranked order."""
    body = {
        "direct_follows": {
            "login|browse": 100,
            "browse|checkout": 40,
            "browse|abandon": 30,
            "browse|view_more": 60,
        },
        "current_state": "browse",
        "top_k": 3,
        "seed": 42,
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["current_state"] == "browse"
    assert len(payload["top_actions"]) <= 3
    # Mean scores should be ranked descending (planner sort applied).
    scores = [a["mean_score"] for a in payload["top_actions"]]
    assert scores == sorted(scores, reverse=True)


def test_plan_with_temperature_0_is_deterministic(client: TestClient):
    """Same input + temperature=0 + seed=42 → same top-K twice."""
    body = {
        "direct_follows": {
            "S|a": 10,
            "S|b": 5,
            "S|c": 1,
        },
        "current_state": "S",
        "temperature": 0.0,
        "seed": 42,
        "top_k": 3,
    }
    r1 = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    r2 = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["top_actions"] == r2.json()["top_actions"]


def test_plan_prefers_high_uncertainty_action(client: TestClient):
    """Action with low visit count gets uncertainty boost → ranked higher."""
    body = {
        "direct_follows": {
            "S|common": 1000,    # heavily visited
            "S|rare": 1,         # high uncertainty
        },
        "current_state": "S",
        "temperature": 0.0,
        "horizon": 1,            # focus on immediate uncertainty signal
        "seed": 42,
        "top_k": 2,
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    payload = r.json()
    top = payload["top_actions"][0]
    assert top["action"] == "rare"
    assert top["visit_proxy"] == 1


def test_plan_returns_theory_position_string(client: TestClient):
    """Response includes honest niche statement from luận văn — UI uses
    this for tooltip so it doesn't accidentally overclaim CDFL as SOTA."""
    body = {
        "direct_follows": {"S|a": 1},
        "current_state": "S",
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 200
    text = r.json()["theory_position"]
    assert "CDFL" in text
    assert "not SOTA" in text or "NNL-NTHT" in text


def test_plan_rejects_bad_direct_follows_key_format(client: TestClient):
    body = {
        "direct_follows": {"missing_separator": 5},
        "current_state": "S",
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 422


def test_plan_rejects_empty_side_in_key(client: TestClient):
    body = {
        "direct_follows": {"|to_only": 5},
        "current_state": "from_only",
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 422


def test_plan_rejects_zero_count(client: TestClient):
    body = {
        "direct_follows": {"a|b": 0},
        "current_state": "a",
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 422


def test_plan_rejects_empty_direct_follows(client: TestClient):
    body = {
        "direct_follows": {},
        "current_state": "S",
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 422


def test_plan_rejects_bad_enterprise_id(client: TestClient):
    body = {"direct_follows": {"a|b": 1}, "current_state": "a"}
    r = client.post(
        "/cdfl/plan-next-action",
        json=body,
        headers={"X-Enterprise-Id": "not-a-uuid"},
    )
    assert r.status_code == 400


def test_plan_handles_unknown_current_state_gracefully(client: TestClient):
    """`current_state` not in observed transitions → agent still returns
    candidates (scored from learned action space + novelty)."""
    body = {
        "direct_follows": {"a|b": 5, "b|c": 5},
        "current_state": "totally_unknown_state",
        "seed": 42,
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert len(payload["top_actions"]) > 0


def test_plan_top_k_caps_response_size(client: TestClient):
    """top_k=1 → response has at most 1 action even if more candidates exist."""
    body = {
        "direct_follows": {"S|a": 1, "S|b": 1, "S|c": 1, "S|d": 1},
        "current_state": "S",
        "top_k": 1,
        "seed": 42,
    }
    r = client.post("/cdfl/plan-next-action", json=body, headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()["top_actions"]) == 1
