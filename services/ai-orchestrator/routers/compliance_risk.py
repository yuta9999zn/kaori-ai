"""EU AI Act risk classification gate — Layer 2 (ADR-0041, K-22).

Classify an AI-use / workflow into a risk_tier; auto-derive controls_required;
record the classification in ai_decision_audit (K-6). prohibited => status
'blocked' (the workflow_builder guard refuses to publish/run it).

Namespace /compliance/... — routed at the edge via /api/v1/compliance/**.
K-1 RLS via acquire_for_tenant. K-12 tenant from X-Enterprise-ID only.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant
from ..shared.ai_governance import record_ai_call
from ..reasoning import compliance_controls as cc

log = structlog.get_logger()
router = APIRouter()


class ClassifyIn(BaseModel):
    use_name: str = Field(..., max_length=160)
    risk_tier: str
    workflow_id: Optional[UUID] = None
    annex_iii_category: Optional[str] = Field(None, max_length=80)
    rationale: Optional[str] = None


class RiskUseOut(BaseModel):
    ai_use_id: str
    public_ref: str
    workflow_id: Optional[str]
    use_name: str
    risk_tier: str
    annex_iii_category: Optional[str]
    rationale: Optional[str]
    controls_required: list[str]
    status: str
    classified_at: Optional[str]


def _row_to_out(row) -> RiskUseOut:
    controls = row["controls_required"]
    if isinstance(controls, str):
        try:
            controls = json.loads(controls)
        except (ValueError, TypeError):
            controls = []
    return RiskUseOut(
        ai_use_id=str(row["ai_use_id"]),
        public_ref=row["public_ref"],
        workflow_id=str(row["workflow_id"]) if row["workflow_id"] else None,
        use_name=row["use_name"],
        risk_tier=row["risk_tier"],
        annex_iii_category=row["annex_iii_category"],
        rationale=row["rationale"],
        controls_required=controls,
        status=row["status"],
        classified_at=row["classified_at"].isoformat() if row["classified_at"] else None,
    )


@router.post("/compliance/ai-uses", response_model=RiskUseOut, status_code=201)
async def classify_ai_use(
    body: ClassifyIn,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Classify an AI-use into a risk_tier; auto-derive controls; audit (K-6)."""
    try:
        tier = cc.validate_tier(body.risk_tier)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid risk_tier: {body.risk_tier}")

    controls = cc.controls_for_tier(tier)
    status = "blocked" if cc.is_prohibited(tier) else "active"

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO ai_use_risk_register
                   (enterprise_id, workflow_id, use_name, risk_tier,
                    annex_iii_category, rationale, controls_required,
                    status, classified_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
               RETURNING ai_use_id, public_ref, workflow_id, use_name,
                         risk_tier, annex_iii_category, rationale,
                         controls_required, status, classified_at""",
            x_enterprise_id, body.workflow_id, body.use_name, tier,
            body.annex_iii_category, body.rationale, json.dumps(controls),
            status, x_user_id,
        )

    # K-6 audit — reuse the AI audit ledger for the governance event.
    try:
        await record_ai_call(
            enterprise_id=x_enterprise_id,
            task_kind="risk_classification",
            model_version="rules-only",
            model_provider="kaori-compliance",
            prompt=f"{body.use_name}|tier={tier}|wf={body.workflow_id}",
            output=json.dumps({"tier": tier, "controls": controls, "status": status}),
            confidence=None,
        )
    except Exception as e:  # audit must not break the classification
        log.warning("compliance.audit_failed", error=str(e))

    log.info("compliance.classified", tier=tier, status=status,
             workflow_id=str(body.workflow_id) if body.workflow_id else None)
    return _row_to_out(row)


@router.get("/compliance/ai-uses/register", response_model=list[RiskUseOut])
async def list_risk_register(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    risk_tier: Optional[str] = Query(None),
    limit: int = Query(200, le=500),
):
    """The tenant's full AI-use risk register (newest first) — drives the
    /p2/compliance register table. RLS-scoped (K-1); not admin-gated (any
    enterprise user can see their own register). Optional risk_tier filter."""
    clauses, params = [], []
    if risk_tier:
        try:
            params.append(cc.validate_tier(risk_tier))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"invalid risk_tier: {risk_tier}")
        clauses.append(f"risk_tier = ${len(params)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT ai_use_id, public_ref, workflow_id, use_name, risk_tier,
                       annex_iii_category, rationale, controls_required,
                       status, classified_at
                FROM ai_use_risk_register{where}
                ORDER BY classified_at DESC LIMIT ${len(params)}""",
            *params,
        )
    return [_row_to_out(r) for r in rows]


@router.get("/compliance/ai-uses", response_model=Optional[RiskUseOut])
async def get_latest_for_workflow(
    workflow_id: UUID = Query(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Latest classification for a workflow, or null."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT ai_use_id, public_ref, workflow_id, use_name, risk_tier,
                      annex_iii_category, rationale, controls_required,
                      status, classified_at
               FROM ai_use_risk_register
               WHERE workflow_id = $1
               ORDER BY classified_at DESC
               LIMIT 1""",
            workflow_id,
        )
    return _row_to_out(row) if row else None
