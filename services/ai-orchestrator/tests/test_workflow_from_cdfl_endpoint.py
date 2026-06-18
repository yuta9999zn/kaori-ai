"""Tests for /workflow/from-cdfl-plan endpoint — P15-S11 Tuần 5."""
from __future__ import annotations

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.workflow_runtime.yaml_schema import validate_workflow_yaml


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


@pytest.fixture
def client() -> TestClient:
    import ai_orchestrator.routers.workflow_from_cdfl as wfc

    test_app = FastAPI()
    test_app.include_router(wfc.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def _basic_body(**overrides) -> dict:
    body = {
        "current_state": "browse",
        "top_actions": [
            {
                "action": "checkout",
                "mean_score": 1.42,
                "best_score": 1.91,
                "visit_proxy": 40,
            },
            {
                "action": "view_more",
                "mean_score": 1.28,
                "best_score": 1.67,
                "visit_proxy": 60,
            },
        ],
        "intervention_channel": "log_only",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_emit_default_log_only_produces_3_nodes(client: TestClient):
    r = client.post("/workflow/from-cdfl-plan", json=_basic_body(), headers=HEADERS)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["k17_check"] == "passed"
    doc = payload["yaml_parsed"]
    # log_only → no notify_customer node.
    node_ids = {n["node_id"] for n in doc["nodes"]}
    assert node_ids == {
        "wait_for_state",
        "compute_cdfl_recommendation",
        "log_recommendation",
    }
    assert len(doc["edges"]) == 2


def test_emit_email_channel_adds_external_node_with_compensation(client: TestClient):
    body = _basic_body(intervention_channel="email")
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    doc = r.json()["yaml_parsed"]
    notify = next(n for n in doc["nodes"] if n["node_id"] == "notify_customer")
    assert notify["side_effect_class"] == "external"
    # REL-012 — external MUST declare compensation.
    assert "compensation" in notify
    assert "retraction" in notify["compensation"]["reason_template"].lower()


def test_emit_telegram_channel_carries_compensation(client: TestClient):
    body = _basic_body(intervention_channel="telegram")
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    doc = r.json()["yaml_parsed"]
    notify = next(n for n in doc["nodes"] if n["node_id"] == "notify_customer")
    assert notify["side_effect_class"] == "external"
    assert "telegram" in notify["compensation"]["reason_template"].lower()


def test_emit_zalo_channel_carries_compensation(client: TestClient):
    body = _basic_body(intervention_channel="zalo")
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    doc = r.json()["yaml_parsed"]
    notify = next(n for n in doc["nodes"] if n["node_id"] == "notify_customer")
    assert notify["side_effect_class"] == "external"
    assert "zalo" in notify["compensation"]["reason_template"].lower()


def test_emit_yaml_text_round_trips(client: TestClient):
    r = client.post("/workflow/from-cdfl-plan", json=_basic_body(), headers=HEADERS)
    assert r.status_code == 200
    payload = r.json()
    parsed = yaml.safe_load(payload["yaml"])
    assert parsed == payload["yaml_parsed"]


def test_emit_yaml_passes_k17_validator(client: TestClient):
    """The emitter MUST produce YAML that the workflow_runtime validator
    accepts — same one operators upload through. Catches future drift
    if yaml_schema.py adds new required fields."""
    r = client.post(
        "/workflow/from-cdfl-plan",
        json=_basic_body(intervention_channel="email"),
        headers=HEADERS,
    )
    assert r.status_code == 200
    validate_workflow_yaml(r.json()["yaml_parsed"])


def test_emit_uses_top_action_in_workflow_id(client: TestClient):
    body = _basic_body()  # top action = checkout
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 200
    wf_id = r.json()["workflow_id"]
    assert "browse" in wf_id
    assert "checkout" in wf_id
    # Schema enforces <=100 chars.
    assert len(wf_id) <= 100


def test_emit_with_suffix_appends_to_workflow_id(client: TestClient):
    body = _basic_body(workflow_name_suffix="phuc_long_cart_recovery")
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 200
    wf_id = r.json()["workflow_id"]
    assert "phuc_long_cart_recovery" in wf_id


def test_emit_determinism_same_input_same_workflow_id(client: TestClient):
    body = _basic_body()
    r1 = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    r2 = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r1.json()["workflow_id"] == r2.json()["workflow_id"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_emit_rejects_empty_top_actions(client: TestClient):
    body = _basic_body()
    body["top_actions"] = []
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 422


def test_emit_rejects_unknown_channel(client: TestClient):
    body = _basic_body()
    body["intervention_channel"] = "carrier_pigeon"
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 422


def test_emit_rejects_bad_enterprise_id(client: TestClient):
    body = _basic_body()
    r = client.post(
        "/workflow/from-cdfl-plan",
        json=body,
        headers={"X-Enterprise-Id": "not-a-uuid"},
    )
    assert r.status_code == 400


def test_emit_handles_unicode_action_names(client: TestClient):
    body = _basic_body()
    body["current_state"] = "đang xem menu"
    body["top_actions"][0]["action"] = "thêm vào giỏ"
    r = client.post("/workflow/from-cdfl-plan", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    payload = r.json()
    # Unicode survives YAML round-trip.
    assert "thêm vào giỏ" in payload["yaml"]
    assert "đang xem menu" in payload["yaml"]
