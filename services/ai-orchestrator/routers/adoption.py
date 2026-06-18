"""
Adoption intervention router — P15-S10 D3 + D4 HTTP surface.

Wraps the intervention engine + tracker so CSM workflows can trigger
an intervention via REST. The actual long-running effectiveness check
(14-day + 30-day score-reads) is owned by the Temporal workflow
`workflow_runtime/workflows/intervention_followup.py`; this endpoint
captures the baseline + resolves the per-tenant channel/gate plan +
hands off to the workflow.

Endpoint::

    POST /api/v1/adoption/interventions/trigger

Auth + tenant scoping via ``X-Enterprise-Id`` header (K-12 / K-16).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..org_intel.adoption import (
    ApprovalGate,
    InterventionChannel,
    InterventionMisconfigError,
    TenantInterventionSettings,
    capture_baseline,
    resolve_intervention_plan,
)

log = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class TenantSettingsIn(BaseModel):
    """Subset of tenant settings the resolver needs. Caller (CSM tooling)
    loads from tenant config + posts; we don't read DB here so the
    endpoint stays pure-function testable."""

    locale: str = Field(default="vi", description="'vi' or 'en'")
    zalo_oa_configured: bool = False
    requires_manager_approval: bool = False
    telegram_chat_id: Optional[str] = None


class InterventionTriggerRequest(BaseModel):
    """POST body. enterprise_id is NEVER trusted from here — read from
    X-Enterprise-Id header (K-12)."""

    intervention_id: str = Field(min_length=1, max_length=255)
    workflow_id: str = Field(min_length=1, max_length=255)
    intervention_type: str = Field(
        ...,
        description=(
            "Domain-specific type — 'csm_email', 'in_product_nudge', "
            "'manager_callout', etc. Used for analytics + audit."
        ),
    )
    pre_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Composite adoption health score at trigger time.",
    )
    tenant_settings: TenantSettingsIn


class InterventionPlanOut(BaseModel):
    """Resolved plan — channel + gate + rationale. FE/CSM tooling shows
    rationale on the audit timeline."""

    channel: str             # 'zalo' / 'telegram' / 'email'
    gate: str                # 'auto' / 'manager_approval'
    locale: str
    rationale: str


class InterventionTriggerResponse(BaseModel):
    intervention_id: str
    workflow_id: str
    plan: InterventionPlanOut
    baseline_captured_at: str   # ISO timestamp
    checkpoint_due_at_14d: str
    checkpoint_due_at_30d: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/adoption/interventions/trigger",
    response_model=InterventionTriggerResponse,
    tags=["Adoption"],
)
async def trigger_intervention(
    body: InterventionTriggerRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """Resolve the per-tenant plan + capture the baseline.

    Fails-CLOSED on misconfig (I1 self-review fix): if the tenant set
    `requires_manager_approval=true` without binding Telegram, the
    resolver raises and we return 422 — CSM tooling must reconcile
    before retrying. Auto-firing the intervention would silently bypass
    the audit gate the tenant explicitly opted into (K-6 spirit).
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)

    settings = TenantInterventionSettings(
        locale=body.tenant_settings.locale,
        zalo_oa_configured=body.tenant_settings.zalo_oa_configured,
        requires_manager_approval=body.tenant_settings.requires_manager_approval,
        telegram_chat_id=body.tenant_settings.telegram_chat_id,
    )

    try:
        plan = resolve_intervention_plan(settings)
    except InterventionMisconfigError as exc:
        log.warning(
            "adoption.intervention.misconfig",
            tenant_id=str(enterprise_id),
            intervention_id=body.intervention_id,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://kaori.ai/errors/intervention-misconfig",
                "title": "Tenant intervention settings inconsistent",
                "detail": str(exc),
                "errcode": "BIZ-ERR1",
            },
        )

    now = datetime.now(timezone.utc)
    baseline = capture_baseline(
        intervention_id=body.intervention_id,
        workflow_id=body.workflow_id,
        enterprise_id=enterprise_id,
        intervention_type=body.intervention_type,
        triggered_at=now,
        pre_score=body.pre_score,
    )

    log.info(
        "adoption.intervention.triggered",
        tenant_id=str(enterprise_id),
        intervention_id=body.intervention_id,
        channel=plan.channel.value,
        gate=plan.gate.value,
    )

    from datetime import timedelta
    due_14 = (baseline.triggered_at + timedelta(days=14)).isoformat()
    due_30 = (baseline.triggered_at + timedelta(days=30)).isoformat()

    return InterventionTriggerResponse(
        intervention_id=body.intervention_id,
        workflow_id=body.workflow_id,
        plan=InterventionPlanOut(
            channel=plan.channel.value,
            gate=plan.gate.value,
            locale=plan.locale,
            rationale=plan.rationale,
        ),
        baseline_captured_at=baseline.triggered_at.isoformat(),
        checkpoint_due_at_14d=due_14,
        checkpoint_due_at_30d=due_30,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_enterprise_id(header_value: str) -> UUID:
    """K-14 RFC 7807 envelope on bad UUID rather than 422."""
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
