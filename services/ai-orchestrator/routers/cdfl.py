"""
CDFL planner router — P15-S11 Tuần 4 Build Week.

POST /cdfl/plan-next-action — given a learned process workflow (direct
follows from Process Mining) + current state, return the top-K next
actions ranked by CDFL information gain over H-step Monte Carlo rollouts.

The endpoint is the bridge between Process Mining (mine.py) and the
Workflow YAML emitter (post-Build-Week). FE flow:

    Process Mining canvas    →  POST /process-mining/mine
                                  ↓ MinedWorkflow JSON
    "Recommend next steps"    →  POST /cdfl/plan-next-action
                                  ↓ top-K ActionScore JSON
    Workflow Builder canvas   →  user picks 1 of the top-K
                                  ↓ (post-Build-Week)
    Temporal workflow YAML

Caller passes `direct_follows` (from /mine output) + `current_state`.
The orchestrator constructs a CDFLAgent on the fly, seeded from
direct_follows, and runs `score_actions(current_state)`.

Auth + tenant scoping via X-Enterprise-Id header (K-12 / K-16). No DB,
no LLM — pure function over inputs.
"""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..reasoning.cdfl import CDFLAgent
from ..reasoning.cdfl.agent import cdfl_agent_from_mined_workflow

log = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """Plan request. Format mirrors /process-mining/mine output exactly so
    FE can pipe one endpoint's response into the other.

    `direct_follows` keys are "from|to" delimited strings (same convention
    as MinedWorkflowOut). Counts must be positive ints.

    `current_state` is the event_type the agent is currently "standing at" —
    typically the most-recent event in a customer journey or the latest
    process step that completed.
    """

    direct_follows: dict[str, int] = Field(..., min_length=1)
    current_state: str = Field(..., min_length=1, max_length=128)

    # CDFL hyperparams — defaults match scaling_50.py from thesis.
    horizon: int = Field(default=5, ge=1, le=20)
    num_rollouts: int = Field(default=6, ge=1, le=50)
    uncertainty_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    information_gain_weight: float = Field(default=1.0, ge=0.0, le=10.0)
    temperature: float = Field(default=0.0, ge=0.0, le=10.0)  # 0 = greedy
    seed: Optional[int] = Field(default=42)

    top_k: int = Field(default=3, ge=1, le=20)


class ActionScoreOut(BaseModel):
    """One ranked action in the plan response."""

    action: str
    mean_score: float
    best_score: float
    visit_proxy: int


class PlanResponse(BaseModel):
    """Top-K actions ranked by CDFL information gain (descending).

    `current_state` echoed for FE convenience.
    `theory_position` line is the honest niche statement from luận văn —
    surfaced so the UI tooltip can show "this is CDFL's research position"
    without claiming SOTA.
    """

    current_state: str
    top_actions: list[ActionScoreOut]
    theory_position: str = (
        "CDFL (Convergent Dual-Field Learning) ranking — bounded compute "
        "exploration with scaling advantage in tabular environments. "
        "Niche per NNL-NTHT 8-phase benchmark; not SOTA RL replacement."
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/cdfl/plan-next-action",
    response_model=PlanResponse,
    tags=["CDFL Planner"],
)
async def plan_next_action(
    body: PlanRequest,
    x_enterprise_id: Annotated[str, Header()],
) -> PlanResponse:
    """Rank candidate next actions using CDFL information gain."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)

    # Parse "from|to" delimited keys back to tuple pairs.
    parsed_df: dict[tuple[str, str], int] = {}
    for key, count in body.direct_follows.items():
        if "|" not in key:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "https://kaori.ai/errors/bad-direct-follows-key",
                    "title": "direct_follows key missing '|' separator",
                    "detail": f"expected 'from|to', got {key!r}",
                    "errcode": "USR-ERR4",
                },
            )
        from_type, to_type = key.split("|", 1)
        if not from_type or not to_type:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "https://kaori.ai/errors/bad-direct-follows-key",
                    "title": "direct_follows key has empty side",
                    "detail": f"expected non-empty 'from|to', got {key!r}",
                    "errcode": "USR-ERR4",
                },
            )
        if count <= 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "https://kaori.ai/errors/bad-direct-follows-count",
                    "title": "direct_follows count must be positive",
                    "detail": f"{key} has count={count}",
                    "errcode": "USR-ERR4",
                },
            )
        parsed_df[(from_type, to_type)] = count

    agent: CDFLAgent = cdfl_agent_from_mined_workflow(
        parsed_df,
        horizon=body.horizon,
        num_rollouts=body.num_rollouts,
        uncertainty_weight=body.uncertainty_weight,
        information_gain_weight=body.information_gain_weight,
        temperature=body.temperature,
        seed=body.seed,
    )

    scored = agent.score_actions(body.current_state)
    # Rank: high mean_score first; tie-break by lower visit_proxy (less explored).
    scored.sort(key=lambda s: (-s.mean_score, s.visit_proxy))
    top_k = scored[: body.top_k]

    log.info(
        "cdfl.plan_next_action",
        tenant_id=str(enterprise_id),
        current_state=body.current_state,
        action_space_size=len(agent.action_space),
        horizon=body.horizon,
        num_rollouts=body.num_rollouts,
        top_k_returned=len(top_k),
    )

    return PlanResponse(
        current_state=body.current_state,
        top_actions=[
            ActionScoreOut(
                action=str(s.action),
                mean_score=float(s.mean_score),
                best_score=float(s.best_score),
                visit_proxy=int(s.visit_proxy),
            )
            for s in top_k
        ],
    )


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
