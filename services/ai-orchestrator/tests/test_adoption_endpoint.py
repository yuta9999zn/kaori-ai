"""
P15-S10 D3+D4 — HTTP-surface tests for /adoption/interventions/trigger.

Pure TestClient — resolver + tracker are pure functions; the endpoint
only adds JWT header parsing + Pydantic envelope + I1 fail-closed
mapping to 422.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


@pytest.fixture
def client():
    import ai_orchestrator.routers.adoption as adoption_module
    test_app = FastAPI()
    test_app.include_router(adoption_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def _body(**overrides):
    base = {
        "intervention_id": "int-test-1",
        "workflow_id": "wf-test-1",
        "intervention_type": "csm_email",
        "pre_score": 72.5,
        "tenant_settings": {
            "locale": "vi",
            "zalo_oa_configured": False,
            "requires_manager_approval": False,
            "telegram_chat_id": None,
        },
    }
    base.update(overrides)
    return base


def test_trigger_auto_gate_email_fallback(client):
    """vi + no Zalo + no Telegram → channel=email, gate=auto."""
    resp = client.post(
        "/adoption/interventions/trigger",
        headers=HEADERS,
        json=_body(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"]["channel"] == "email"
    assert body["plan"]["gate"] == "auto"
    assert body["intervention_id"] == "int-test-1"
    assert body["baseline_captured_at"]   # ISO timestamp present
    assert body["checkpoint_due_at_14d"] != body["checkpoint_due_at_30d"]


def test_trigger_telegram_with_approval_gate(client):
    """vi + Telegram bound + requires approval → gate=manager_approval."""
    resp = client.post(
        "/adoption/interventions/trigger",
        headers=HEADERS,
        json=_body(tenant_settings={
            "locale": "vi", "zalo_oa_configured": False,
            "requires_manager_approval": True,
            "telegram_chat_id": "abc123",
        }),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["gate"] == "manager_approval"
    assert body["plan"]["channel"] == "telegram"


def test_misconfig_approval_no_telegram_422_fail_closed(client):
    """I1 fix: requires_manager_approval=True + no Telegram → 422
    with BIZ-ERR1 errcode. Tenant must reconcile before retry."""
    resp = client.post(
        "/adoption/interventions/trigger",
        headers=HEADERS,
        json=_body(tenant_settings={
            "locale": "vi", "zalo_oa_configured": True,
            "requires_manager_approval": True,
            "telegram_chat_id": None,
        }),
    )
    assert resp.status_code == 422
    detail = resp.json().get("detail", {})
    assert detail.get("errcode") == "BIZ-ERR1"
    assert "telegram_chat_id" in detail.get("detail", "")


def test_pre_score_out_of_range_422(client):
    """Pydantic ge=0/le=100 on pre_score."""
    resp = client.post(
        "/adoption/interventions/trigger",
        headers=HEADERS,
        json=_body(pre_score=150.0),
    )
    assert resp.status_code == 422


def test_bad_uuid_tenant_400(client):
    resp = client.post(
        "/adoption/interventions/trigger",
        headers={"X-Enterprise-Id": "bad"},
        json=_body(),
    )
    assert resp.status_code == 400
    assert resp.json().get("detail", {}).get("errcode") == "USR-ERR4"
