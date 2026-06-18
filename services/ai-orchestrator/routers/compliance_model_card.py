"""EU AI Act model card (Annex IV-lite) — Layer 2 (ADR-0041, K-25).

Author / read the technical-documentation card per (model, version) of the
K-20 LLM-pinning registry. Satisfies the ``K-25_MODEL_CARD`` control that a
``risk_tier = high`` use auto-requires (reasoning/compliance_controls.py).

Trust-first / conformity-ready (same posture as K-22/K-26): the card is
recorded + its Annex IV-lite completeness computed, but publishing an
incomplete card is NOT hard-blocked here — the gap is surfaced via
``completeness`` so a deployer can close it. record_ai_call audits the event
(K-6).

Namespace /compliance/... — routed at the edge via /api/v1/compliance/**.
K-1 RLS via acquire_for_tenant. K-12 tenant from X-Enterprise-ID only.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..shared.db import acquire_for_tenant
from ..shared.ai_governance import record_ai_call
from ..reasoning import compliance_controls as cc

log = structlog.get_logger()
router = APIRouter()


# `model` is a plain field name (not the protected `model_` prefix), but we
# disable pydantic's protected-namespace guard explicitly so the field name is
# unambiguous across pydantic versions.
class ModelCardIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model: str = Field(..., max_length=120)
    version: str = Field(..., max_length=40)
    intended_purpose: str = Field(..., max_length=4000)
    provider: Optional[str] = Field(None, max_length=40)
    capabilities: Optional[str] = None
    limitations: Optional[str] = None
    training_data_summary: Optional[str] = None
    evaluation_summary: Optional[str] = None
    risk_mitigations: Optional[str] = None
    foreseeable_misuse: Optional[str] = None
    annex_iv: dict = Field(default_factory=dict)


class ModelCardOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_card_id: str
    public_ref: str
    model: str
    version: str
    provider: Optional[str]
    intended_purpose: str
    capabilities: Optional[str]
    limitations: Optional[str]
    training_data_summary: Optional[str]
    evaluation_summary: Optional[str]
    risk_mitigations: Optional[str]
    foreseeable_misuse: Optional[str]
    annex_iv: dict
    completeness: dict
    status: str
    authored_at: Optional[str]


_SELECT_COLS = (
    "model_card_id, public_ref, model, version, provider, intended_purpose, "
    "capabilities, limitations, training_data_summary, evaluation_summary, "
    "risk_mitigations, foreseeable_misuse, annex_iv, completeness, status, authored_at"
)


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _row_to_out(row) -> ModelCardOut:
    return ModelCardOut(
        model_card_id=str(row["model_card_id"]),
        public_ref=row["public_ref"],
        model=row["model"],
        version=row["version"],
        provider=row["provider"],
        intended_purpose=row["intended_purpose"],
        capabilities=row["capabilities"],
        limitations=row["limitations"],
        training_data_summary=row["training_data_summary"],
        evaluation_summary=row["evaluation_summary"],
        risk_mitigations=row["risk_mitigations"],
        foreseeable_misuse=row["foreseeable_misuse"],
        annex_iv=_as_dict(row["annex_iv"]),
        completeness=_as_dict(row["completeness"]),
        status=row["status"],
        authored_at=row["authored_at"].isoformat() if row["authored_at"] else None,
    )


@router.post("/compliance/model-cards", response_model=ModelCardOut, status_code=201)
async def author_model_card(
    body: ModelCardIn,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Author an Annex IV-lite model card for a (model, version). Computes
    completeness (which required sections are missing) and audits (K-6).
    Append-only — re-authoring writes a new row; readers take the latest."""
    card = body.model_dump()
    completeness = cc.model_card_completeness(card)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            f"""INSERT INTO ai_model_card
                    (enterprise_id, model, version, provider, intended_purpose,
                     capabilities, limitations, training_data_summary,
                     evaluation_summary, risk_mitigations, foreseeable_misuse,
                     annex_iv, completeness, authored_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        $12::jsonb, $13::jsonb, $14)
                RETURNING {_SELECT_COLS}""",
            x_enterprise_id, body.model, body.version, body.provider,
            body.intended_purpose, body.capabilities, body.limitations,
            body.training_data_summary, body.evaluation_summary,
            body.risk_mitigations, body.foreseeable_misuse,
            json.dumps(body.annex_iv), json.dumps(completeness), x_user_id,
        )

    # K-6 audit — reuse the AI audit ledger for the governance event.
    try:
        await record_ai_call(
            enterprise_id=x_enterprise_id,
            task_kind="model_card",
            model_version=f"{body.model}@{body.version}",
            model_provider=body.provider or "unknown",
            prompt=f"model_card|{body.model}@{body.version}",
            output=json.dumps(completeness),
            confidence=None,
        )
    except Exception as e:  # audit must not break the authoring
        log.warning("compliance.model_card.audit_failed", error=str(e))

    log.info("compliance.model_card.authored", model=body.model,
             version=body.version, complete=completeness["complete"])
    return _row_to_out(row)


@router.get("/compliance/model-cards/register", response_model=list[ModelCardOut])
async def list_model_cards(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    model: Optional[str] = Query(None, max_length=120),
    limit: int = Query(200, le=500),
):
    """The tenant's model cards (newest first) — drives the /p2/compliance
    model-card tab. RLS-scoped (K-1). Optional `model` filter."""
    clauses, params = [], []
    if model:
        params.append(model)
        clauses.append(f"model = ${len(params)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT {_SELECT_COLS}
                FROM ai_model_card{where}
                ORDER BY authored_at DESC LIMIT ${len(params)}""",
            *params,
        )
    return [_row_to_out(r) for r in rows]


@router.get("/compliance/model-cards/lookup", response_model=Optional[ModelCardOut])
async def latest_for_model_version(
    model: str = Query(..., max_length=120),
    version: str = Query(..., max_length=40),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Latest model card for an exact (model, version), or null. This is the
    K-25 satisfaction check: a `risk_tier = high` workflow pinned to this
    (model, version) has its K-25 control met when a card exists AND
    ``completeness.complete`` is true."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            f"""SELECT {_SELECT_COLS}
                FROM ai_model_card
                WHERE model = $1 AND version = $2
                ORDER BY authored_at DESC
                LIMIT 1""",
            model, version,
        )
    return _row_to_out(row) if row else None
