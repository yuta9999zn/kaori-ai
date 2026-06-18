"""
F-041 Explainability — HTTP surface.

Single endpoint::

    POST /api/v1/explainability/explain   { decision_id }

Body shape returns the parsed top_factors + narrative + confidence
explanation. Synchronous — the LLM call is short (≤ 5s on Qwen 14B,
~2s on a 7B model). No queue / polling.

K-12: tenant comes from the gateway-trusted X-Enterprise-ID header.
"""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..explainability import service
from ..explainability.service import (
    DecisionNotFoundError,
    ExplanationFailedError,
)

log = structlog.get_logger()

router = APIRouter()


class ExplainRequest(BaseModel):
    decision_id: UUID = Field(..., description="decision_audit_log.decision_id to explain.")
    consent_external: bool = Field(
        default=False,
        description="K-4 — opt in to external LLM (Claude / GPT-4o) for this call. Default Qwen local.",
    )


class TopFactor(BaseModel):
    factor_name: str
    direction:   str = Field(..., pattern="^(positive|negative|neutral)$")
    weight:      float
    evidence:    str


class ExplainResponse(BaseModel):
    decision_id:  UUID
    top_factors:  list[TopFactor]
    narrative:    str
    confidence_explanation: str


@router.post("/explainability/explain", response_model=ExplainResponse)
async def explain_endpoint(
    req: ExplainRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    try:
        parsed = await service.explain(
            decision_id=req.decision_id,
            enterprise_id=x_enterprise_id,
            consent_external=req.consent_external,
        )
    except DecisionNotFoundError:
        # Don't leak existence — RLS would 404 cross-tenant requests
        # too.
        raise HTTPException(status_code=404, detail="Decision not found")
    except ExplanationFailedError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM gave up explaining this decision: {exc}",
        ) from exc

    return ExplainResponse(
        decision_id=req.decision_id,
        top_factors=[TopFactor(**f) for f in parsed.get("top_factors", [])],
        narrative=parsed.get("narrative", ""),
        confidence_explanation=parsed.get("confidence_explanation", ""),
    )
