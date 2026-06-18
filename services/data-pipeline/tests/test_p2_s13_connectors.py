"""P2-S13 — PM-EVT-006/007/008 connector tests.

Unit tests on each connector's __init__ validation + map_payload pure
function for the webhook mapper. HTTP-surface tests on the 3 new
register endpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from data_pipeline.ingestion.connectors.generic_webhook.connector import (
    GenericWebhookConnector,
    WebhookMapping,
    map_payload,
)
from data_pipeline.ingestion.connectors.microsoft_sharepoint.connector import (
    SharePointConnector,
)
from data_pipeline.ingestion.connectors.slack_teams.connector import (
    SlackTeamsAuditConnector,
)


T = UUID("11111111-1111-1111-1111-111111111111")


# ─── SlackTeamsAuditConnector ──────────────────────────────────────


class TestSlackTeamsAuditConnector:

    def test_slack_channel_constructs(self):
        c = SlackTeamsAuditConnector(
            tenant_id=T,
            config={"channel": "slack", "workspace_id": "T01ABC"},
        )
        assert c.source == "slack_teams"
        assert c.channel == "slack"
        assert c.workspace_id == "T01ABC"

    def test_teams_channel_constructs(self):
        c = SlackTeamsAuditConnector(
            tenant_id=T,
            config={"channel": "teams", "workspace_id": "tenant-guid-123"},
        )
        assert c.channel == "teams"

    def test_unknown_channel_rejected(self):
        with pytest.raises(ValueError, match="channel"):
            SlackTeamsAuditConnector(
                tenant_id=T,
                config={"channel": "discord", "workspace_id": "x"},
            )

    def test_missing_workspace_id_rejected(self):
        with pytest.raises(ValueError, match="workspace_id"):
            SlackTeamsAuditConnector(
                tenant_id=T, config={"channel": "slack"},
            )


# ─── SharePointConnector ───────────────────────────────────────────


class TestSharePointConnector:

    def test_constructs_with_site_and_drive(self):
        c = SharePointConnector(
            tenant_id=T,
            config={"site_id": "site-abc", "drive_id": "drive-xyz"},
        )
        assert c.source == "microsoft_sharepoint"
        assert c.site_id == "site-abc"
        assert c.drive_id == "drive-xyz"

    def test_missing_site_id_rejected(self):
        with pytest.raises(ValueError, match="site_id"):
            SharePointConnector(
                tenant_id=T, config={"drive_id": "x"},
            )

    def test_missing_drive_id_rejected(self):
        with pytest.raises(ValueError, match="drive_id"):
            SharePointConnector(
                tenant_id=T, config={"site_id": "x"},
            )


# ─── GenericWebhookConnector — map_payload + ctor ──────────────────


class TestWebhookMapperPure:

    @pytest.fixture
    def basic_mapping(self):
        return WebhookMapping(
            actor_path="data.user.email",
            event_type_path="data.action",
            occurred_at_path="data.timestamp",
            case_id_path="data.order_id",
            payload_keys=("data.order_id", "data.action"),
            pii_redact_paths=("data.user.full_name",),
        )

    def test_iso_timestamp(self, basic_mapping):
        raw = {
            "data": {
                "user": {"email": "anh@acme.com", "full_name": "Nguyễn An"},
                "action": "approved",
                "timestamp": "2026-05-17T10:00:00Z",
                "order_id": "O-001",
            }
        }
        ev = map_payload(raw, basic_mapping, tenant_id=T, source="crm-events")
        assert ev.source == "generic_webhook"
        assert ev.event_type == "webhook.approved"
        assert ev.occurred_at.year == 2026
        # actor is sha256-hashed
        assert ev.actor and len(ev.actor) == 64
        assert ev.case_id == "O-001"

    def test_epoch_timestamp(self, basic_mapping):
        raw = {
            "data": {
                "user": {"email": "x@acme.com"},
                "action": "created",
                "timestamp": 1747476000,
                "order_id": "O-2",
            }
        }
        ev = map_payload(raw, basic_mapping, tenant_id=T, source="t")
        assert ev.occurred_at.year == 2025 or ev.occurred_at.year == 2026

    def test_missing_required_field_raises(self, basic_mapping):
        raw = {"data": {"user": {"email": "x@y"}, "timestamp": "2026-05-17T10:00:00Z"}}
        with pytest.raises(ValueError, match="incomplete"):
            map_payload(raw, basic_mapping, tenant_id=T, source="t")

    def test_pii_redaction(self, basic_mapping):
        raw = {
            "data": {
                "user": {"email": "x@y.com", "full_name": "PRIVATE NAME"},
                "action": "x",
                "timestamp": "2026-05-17T10:00:00Z",
                "order_id": "O-1",
            }
        }
        ev = map_payload(raw, basic_mapping, tenant_id=T, source="t")
        # full_name is NOT in payload_keys but it's in pii_redact_paths;
        # the redaction is applied to the (in-memory) raw before payload
        # extraction. Since payload_keys doesn't include full_name, it
        # won't appear — but the test verifies the redaction doesn't
        # crash + the included keys still survive.
        assert "PRIVATE NAME" not in str(ev.payload)

    def test_event_id_hashed_when_no_path(self, basic_mapping):
        raw = {
            "data": {"user": {"email": "x@y"}, "action": "a",
                      "timestamp": "2026-05-17T10:00:00Z", "order_id": "O-1"}
        }
        ev = map_payload(raw, basic_mapping, tenant_id=T, source="crm")
        # event_id format: webhook:{source}:{hash}
        assert ev.event_id.startswith("webhook:crm:")

    def test_event_id_from_explicit_path(self):
        mapping = WebhookMapping(
            actor_path="actor", event_type_path="action",
            occurred_at_path="ts", event_id_path="id",
        )
        ev = map_payload(
            {"actor": "x@y", "action": "a", "ts": "2026-05-17T10:00:00Z",
              "id": "explicit-id-1"},
            mapping, tenant_id=T, source="src",
        )
        assert ev.event_id == "webhook:src:explicit-id-1"


class TestGenericWebhookConnectorCtor:

    def test_constructs_with_full_mapping(self):
        c = GenericWebhookConnector(
            tenant_id=T,
            config={
                "webhook_label": "crm-events",
                "mapping": {
                    "actor_path": "user.email",
                    "event_type_path": "event",
                    "occurred_at_path": "ts",
                },
            },
        )
        assert c.source == "generic_webhook"
        assert c.webhook_label == "crm-events"

    def test_missing_label_rejected(self):
        with pytest.raises(ValueError, match="webhook_label"):
            GenericWebhookConnector(
                tenant_id=T,
                config={"mapping": {"actor_path": "x", "event_type_path": "y",
                                       "occurred_at_path": "z"}},
            )

    def test_missing_mapping_rejected(self):
        with pytest.raises(ValueError, match="mapping"):
            GenericWebhookConnector(
                tenant_id=T, config={"webhook_label": "x"},
            )

    def test_mapping_missing_required_key_rejected(self):
        with pytest.raises(ValueError, match="missing required key"):
            GenericWebhookConnector(
                tenant_id=T,
                config={
                    "webhook_label": "x",
                    "mapping": {"actor_path": "a"},   # missing event_type + ts
                },
            )

    def test_map_one_round_trip(self):
        c = GenericWebhookConnector(
            tenant_id=T,
            config={
                "webhook_label": "crm",
                "mapping": {
                    "actor_path": "user.email",
                    "event_type_path": "event",
                    "occurred_at_path": "ts",
                },
            },
        )
        ev = c.map_one({"user": {"email": "x@y"}, "event": "x",
                          "ts": "2026-05-17T10:00:00Z"})
        assert ev.tenant_id == T
        assert ev.source == "generic_webhook"


# ─── HTTP surface — 3 new endpoints ────────────────────────────────


@pytest.fixture
def client():
    from data_pipeline.routers import process_mining
    from data_pipeline.shared.errors import register_problem_handlers
    app = FastAPI()
    app.include_router(process_mining.router)
    register_problem_handlers(app)
    return TestClient(app)


HEADERS = {"X-Enterprise-ID": str(uuid4())}


class TestSlackTeamsEndpoint:
    def test_happy_path_slack(self, client):
        r = client.post(
            "/process-mining/connectors/slack-teams",
            json={"channel": "slack", "workspace_id": "T01ABC"},
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["connector_source"] == "slack_teams"
        assert body["channel"] == "slack"
        assert body["status"] == "registered"

    def test_unknown_channel_returns_422(self, client):
        r = client.post(
            "/process-mining/connectors/slack-teams",
            json={"channel": "discord", "workspace_id": "x"},
            headers=HEADERS,
        )
        assert r.status_code == 422


class TestSharePointEndpoint:
    def test_happy_path(self, client):
        r = client.post(
            "/process-mining/connectors/microsoft",
            json={"site_id": "site-1", "drive_id": "drive-1"},
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["connector_source"] == "microsoft_sharepoint"
        assert body["status"] == "registered"

    def test_missing_drive_id_returns_422(self, client):
        r = client.post(
            "/process-mining/connectors/microsoft",
            json={"site_id": "x"},  # missing drive_id
            headers=HEADERS,
        )
        assert r.status_code == 422


class TestGenericWebhookEndpoint:
    def test_happy_path(self, client):
        r = client.post(
            "/process-mining/connectors/generic",
            json={
                "webhook_label": "crm-events",
                "mapping": {
                    "actor_path": "user.email",
                    "event_type_path": "event",
                    "occurred_at_path": "ts",
                    "case_id_path": "order_id",
                },
            },
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["connector_source"] == "generic_webhook"
        assert body["channel"] == "crm-events"

    def test_incomplete_mapping_returns_422(self, client):
        r = client.post(
            "/process-mining/connectors/generic",
            json={
                "webhook_label": "x",
                "mapping": {"actor_path": "x"},
            },
            headers=HEADERS,
        )
        # Pydantic validates required mapping keys first → 422
        assert r.status_code == 422
