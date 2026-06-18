"""
Process Mining connector router — P15-S10 D1+D2 HTTP surface.

Two endpoints register a per-tenant metadata connector for Process
Mining session reconstruction:

  POST /process-mining/connectors/gmail-outlook   PM-EVT-004 (D1)
  POST /process-mining/connectors/calendar        PM-EVT-005 (D2)

Both endpoints validate the config + return a session-id handle.
Actual long-running polling is the Temporal worker's job
(workflow_runtime/workflows/process_mining_session.py — slated for
P15-S11 wire-up); these endpoints provide the registration surface so
FE can ship the "Connect Gmail / Calendar" wizard without waiting on
the worker.

Auth + tenant scoping via X-Enterprise-Id header (K-12 / K-16).
"""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..ingestion.connectors.gmail_outlook.connector import (
    GmailOutlookConnector,
)
from ..ingestion.connectors.calendar_metadata.connector import (
    CalendarMetadataConnector,
)
from ..ingestion.connectors.generic_webhook.connector import (
    GenericWebhookConnector,
)
from ..ingestion.connectors.microsoft_sharepoint.connector import (
    SharePointConnector,
)
from ..ingestion.connectors.slack_teams.connector import (
    SlackTeamsAuditConnector,
)

log = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class GmailOutlookRegisterRequest(BaseModel):
    """POST body. enterprise_id is NEVER from here — K-12 header only."""

    channel: str = Field(..., description="'gmail' or 'outlook'")
    tenant_mailbox: str = Field(
        ...,
        min_length=6,
        max_length=255,
        description="The mailbox to poll (also derives received vs sent direction)",
    )
    oauth_credential_path: Optional[str] = Field(
        default=None,
        description=(
            "Vault path 'secret/tenant/{id}/connectors/gmail_oauth' in prod; "
            "env override in dev. Real adapters land P15-S11."
        ),
    )
    poll_interval_seconds: int = Field(default=300, ge=60, le=3600)


class CalendarRegisterRequest(BaseModel):
    channel: str = Field(..., description="'google_calendar' or 'outlook_calendar'")
    tenant_calendar_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Calendar id ('primary' for default user calendar)",
    )
    tenant_mailbox: str = Field(
        ...,
        min_length=6,
        max_length=255,
        description="Calendar owner email (OAuth principal)",
    )
    oauth_credential_path: Optional[str] = None
    poll_interval_seconds: int = Field(default=300, ge=60, le=3600)


class ConnectorRegisterResponse(BaseModel):
    """Response shape for both endpoints. session_id is a stable handle
    that the Temporal Process Mining worker uses for cursor state."""

    session_id: str
    connector_source: str    # 'gmail_outlook' | 'calendar_metadata'
    channel: str
    status: str              # 'registered' (always; real poll is async)
    next_poll_at: Optional[str] = None  # ISO timestamp once worker enabled


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/process-mining/connectors/gmail-outlook",
    response_model=ConnectorRegisterResponse,
    tags=["Process Mining"],
)
async def register_gmail_outlook(
    body: GmailOutlookRegisterRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """Register a Gmail / Outlook metadata connector for this tenant.

    Validates channel + mailbox via the connector's own __init__ so any
    misconfig surfaces as 422 immediately. Returns a session_id that
    the worker uses as cursor key. Real polling fires when the
    `TEMPORAL_ENABLE_WORKER=true` flag is set (default false P15-S10).
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    config = {
        "channel": body.channel.lower(),
        "tenant_mailbox": body.tenant_mailbox,
        "oauth_credential_path": body.oauth_credential_path,
        "poll_interval_seconds": body.poll_interval_seconds,
    }
    try:
        connector = GmailOutlookConnector(tenant_id=enterprise_id, config=config)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://kaori.ai/errors/bad-connector-config",
                "title": "Gmail/Outlook connector config invalid",
                "detail": str(exc),
                "errcode": "USR-ERR4",
            },
        )

    session_id = str(uuid4())
    log.info(
        "process_mining.connector.registered",
        tenant_id=str(enterprise_id),
        source=connector.source,
        channel=connector.channel,
        session_id=session_id,
    )
    return ConnectorRegisterResponse(
        session_id=session_id,
        connector_source=connector.source,
        channel=connector.channel,
        status="registered",
    )


@router.post(
    "/process-mining/connectors/calendar",
    response_model=ConnectorRegisterResponse,
    tags=["Process Mining"],
)
async def register_calendar(
    body: CalendarRegisterRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """Register a Calendar metadata connector for this tenant."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    config = {
        "channel": body.channel.lower(),
        "tenant_calendar_id": body.tenant_calendar_id,
        "tenant_mailbox": body.tenant_mailbox,
        "oauth_credential_path": body.oauth_credential_path,
        "poll_interval_seconds": body.poll_interval_seconds,
    }
    try:
        connector = CalendarMetadataConnector(tenant_id=enterprise_id, config=config)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://kaori.ai/errors/bad-connector-config",
                "title": "Calendar connector config invalid",
                "detail": str(exc),
                "errcode": "USR-ERR4",
            },
        )

    session_id = str(uuid4())
    log.info(
        "process_mining.connector.registered",
        tenant_id=str(enterprise_id),
        source=connector.source,
        channel=connector.channel,
        session_id=session_id,
    )
    return ConnectorRegisterResponse(
        session_id=session_id,
        connector_source=connector.source,
        channel=connector.channel,
        status="registered",
    )


# ---------------------------------------------------------------------------
# P2-S13 — 3 more connectors
# ---------------------------------------------------------------------------


class SlackTeamsRegisterRequest(BaseModel):
    channel: str = Field(..., description="'slack' or 'teams'")
    workspace_id: str = Field(..., min_length=1, max_length=128)
    oauth_credential_path: Optional[str] = None
    poll_interval_seconds: int = Field(default=300, ge=60, le=3600)


@router.post(
    "/process-mining/connectors/slack-teams",
    response_model=ConnectorRegisterResponse,
    tags=["Process Mining"],
)
async def register_slack_teams(
    body: SlackTeamsRegisterRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """PM-EVT-006 — Slack Enterprise Grid / Teams audit-API connector.

    Validates channel + workspace via the connector's __init__. Real
    polling fires when TEMPORAL_ENABLE_WORKER=true AND the per-tenant
    OAuth onboarding completes (the Slack admin / Teams Tenant Admin
    consent ships outside this endpoint).
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    config = {
        "channel": body.channel.lower(),
        "workspace_id": body.workspace_id,
        "oauth_credential_path": body.oauth_credential_path,
        "poll_interval_seconds": body.poll_interval_seconds,
    }
    try:
        connector = SlackTeamsAuditConnector(tenant_id=enterprise_id, config=config)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type":  "https://kaori.ai/errors/bad-connector-config",
                "title": "Slack/Teams connector config invalid",
                "detail": str(exc),
                "errcode": "USR-ERR4",
            },
        )
    session_id = str(uuid4())
    log.info("process_mining.connector.registered",
             tenant_id=str(enterprise_id), source=connector.source,
             channel=connector.channel, session_id=session_id)
    return ConnectorRegisterResponse(
        session_id=session_id, connector_source=connector.source,
        channel=connector.channel, status="registered",
    )


class SharePointRegisterRequest(BaseModel):
    site_id: str = Field(..., min_length=1, max_length=128)
    drive_id: str = Field(..., min_length=1, max_length=128)
    oauth_credential_path: Optional[str] = None
    poll_interval_seconds: int = Field(default=300, ge=60, le=3600)


@router.post(
    "/process-mining/connectors/microsoft",
    response_model=ConnectorRegisterResponse,
    tags=["Process Mining"],
)
async def register_microsoft_sharepoint(
    body: SharePointRegisterRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """PM-EVT-007 — MS SharePoint file change connector via MS Graph
    delta query."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    config = {
        "site_id": body.site_id,
        "drive_id": body.drive_id,
        "oauth_credential_path": body.oauth_credential_path,
        "poll_interval_seconds": body.poll_interval_seconds,
    }
    try:
        connector = SharePointConnector(tenant_id=enterprise_id, config=config)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type":  "https://kaori.ai/errors/bad-connector-config",
                "title": "SharePoint connector config invalid",
                "detail": str(exc),
                "errcode": "USR-ERR4",
            },
        )
    session_id = str(uuid4())
    log.info("process_mining.connector.registered",
             tenant_id=str(enterprise_id), source=connector.source,
             channel="microsoft_sharepoint", session_id=session_id)
    return ConnectorRegisterResponse(
        session_id=session_id, connector_source=connector.source,
        channel="microsoft_sharepoint", status="registered",
    )


class GenericWebhookMapping(BaseModel):
    actor_path:       str
    event_type_path:  str
    occurred_at_path: str
    case_id_path:     Optional[str]      = None
    event_id_path:    Optional[str]      = None
    payload_keys:     list[str] = Field(default_factory=list)
    pii_redact_paths: list[str] = Field(default_factory=list)


class GenericWebhookRegisterRequest(BaseModel):
    webhook_label: str = Field(..., min_length=1, max_length=64,
                                  description="Tenant-friendly label, e.g. "
                                              "'crm-events' or 'stripe-prod'")
    mapping: GenericWebhookMapping


@router.post(
    "/process-mining/connectors/generic",
    response_model=ConnectorRegisterResponse,
    tags=["Process Mining"],
)
async def register_generic_webhook(
    body: GenericWebhookRegisterRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """PM-EVT-008 — generic webhook event-log connector. Tenants register
    the mapping config; the actual webhook receiver endpoint (POST
    /process-mining/webhook/{label}) routes payloads here for mapping."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    config = {
        "webhook_label": body.webhook_label,
        "mapping": body.mapping.model_dump(),
    }
    try:
        connector = GenericWebhookConnector(tenant_id=enterprise_id, config=config)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type":  "https://kaori.ai/errors/bad-connector-config",
                "title": "Generic webhook connector config invalid",
                "detail": str(exc),
                "errcode": "USR-ERR4",
            },
        )
    session_id = str(uuid4())
    log.info("process_mining.connector.registered",
             tenant_id=str(enterprise_id), source=connector.source,
             webhook_label=connector.webhook_label, session_id=session_id)
    return ConnectorRegisterResponse(
        session_id=session_id, connector_source=connector.source,
        channel=body.webhook_label, status="registered",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_enterprise_id(header_value: str) -> UUID:
    try:
        return UUID(header_value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://kaori.ai/errors/bad-enterprise-id",
                "title": "X-Enterprise-Id must be a UUID",
                "detail": f"got {header_value!r}",
                "errcode": "USR-ERR4",
            },
        )
