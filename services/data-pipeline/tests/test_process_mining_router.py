"""
P15-S10 D1+D2 — HTTP-surface tests for /process-mining/connectors/*.

Registration validates config via the connector __init__ + returns a
session handle. Real polling is the Temporal worker's job; these tests
don't exercise that path (worker disabled by default).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


@pytest.fixture
def client():
    import data_pipeline.routers.process_mining as pm_module
    test_app = FastAPI()
    test_app.include_router(pm_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


# ---- Gmail/Outlook ----


def test_register_gmail_connector_returns_session_handle(client):
    resp = client.post(
        "/process-mining/connectors/gmail-outlook",
        headers=HEADERS,
        json={
            "channel": "gmail",
            "tenant_mailbox": "olist-cs@kaori.local",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["connector_source"] == "gmail_outlook"
    assert body["channel"] == "gmail"
    assert body["status"] == "registered"
    assert body["session_id"]


def test_register_outlook_connector_accepts_outlook_channel(client):
    resp = client.post(
        "/process-mining/connectors/gmail-outlook",
        headers=HEADERS,
        json={"channel": "outlook", "tenant_mailbox": "ops@kaori.local"},
    )
    assert resp.status_code == 200
    assert resp.json()["channel"] == "outlook"


def test_register_gmail_bad_channel_422(client):
    """Connector __init__ raises ValueError → endpoint maps to 422."""
    resp = client.post(
        "/process-mining/connectors/gmail-outlook",
        headers=HEADERS,
        json={"channel": "yahoo", "tenant_mailbox": "a@b.com"},
    )
    assert resp.status_code == 422
    detail = resp.json().get("detail", {})
    assert detail.get("errcode") == "USR-ERR4"


def test_register_gmail_missing_mailbox_422(client):
    """Pydantic min_length=6 on tenant_mailbox."""
    resp = client.post(
        "/process-mining/connectors/gmail-outlook",
        headers=HEADERS,
        json={"channel": "gmail", "tenant_mailbox": ""},
    )
    assert resp.status_code == 422


# ---- Calendar ----


def test_register_google_calendar(client):
    resp = client.post(
        "/process-mining/connectors/calendar",
        headers=HEADERS,
        json={
            "channel": "google_calendar",
            "tenant_calendar_id": "primary",
            "tenant_mailbox": "owner@kaori.local",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["connector_source"] == "calendar_metadata"
    assert body["channel"] == "google_calendar"


def test_register_calendar_bad_channel_422(client):
    resp = client.post(
        "/process-mining/connectors/calendar",
        headers=HEADERS,
        json={
            "channel": "ical",
            "tenant_calendar_id": "primary",
        },
    )
    assert resp.status_code == 422


# ---- Shared ----


def test_bad_uuid_tenant_400(client):
    resp = client.post(
        "/process-mining/connectors/gmail-outlook",
        headers={"X-Enterprise-Id": "bad"},
        json={"channel": "gmail", "tenant_mailbox": "a@b.com"},
    )
    assert resp.status_code == 400
    assert resp.json().get("detail", {}).get("errcode") == "USR-ERR4"


def test_missing_tenant_header_422(client):
    resp = client.post(
        "/process-mining/connectors/gmail-outlook",
        json={"channel": "gmail", "tenant_mailbox": "a@b.com"},
    )
    assert resp.status_code == 422
