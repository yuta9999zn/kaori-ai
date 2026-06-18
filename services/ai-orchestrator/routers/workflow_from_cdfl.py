"""
Workflow emitter router — P15-S11 Tuần 5 Build Week.

POST /workflow/from-cdfl-plan — turn a CDFL `top_actions` ranking into
a valid Temporal workflow YAML that monitors customer state and surfaces
the recommended next action. Pure function: no DB write, no LLM call,
no Temporal call. Caller (FE Workflow Builder) saves the YAML separately.

Why this endpoint instead of FE templating: K-17 invariant says every
node MUST declare a side_effect_class, and REL-012 says external nodes
MUST declare compensation. The validation lives in workflow_runtime/
yaml_schema.py; emitting the YAML server-side guarantees validity on
the way out so the operator never has to remember the K-17 rules
manually.

Emitted workflow shape (deterministic, linear chain):

    wait_for_state (read_only)
        ↓
    compute_cdfl_recommendation (pure)
        ↓
    log_recommendation (write_idempotent)
        ↓
    (optional) notify_customer (external + compensation)

The `notify_customer` node is appended only when intervention_channel
is not 'log_only'. When external it carries the REL-012 compensation
template so the saga orchestrator (REL-013, Phase 1.5+) can roll back
if a downstream step fails.
"""
from __future__ import annotations

import hashlib
import re
from typing import Annotated, Literal, Optional
from uuid import UUID

import structlog
import yaml
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..workflow_runtime.yaml_schema import (
    WorkflowSchemaError,
    validate_workflow_yaml,
)

log = structlog.get_logger()

router = APIRouter()


# Channel → side-effect class for the notify_customer node.
# log_only is the default (no external traffic).
_CHANNEL_TO_NODE_PROPS: dict[str, dict] = {
    "log_only": {
        # No external — skip notify node entirely (caller handles).
    },
    "email": {
        "side_effect_class": "external",
        "compensation_template": "Send retraction email for {action} recommendation",
    },
    "telegram": {
        "side_effect_class": "external",
        "compensation_template": "Send correction telegram for {action} recommendation",
    },
    "zalo": {
        "side_effect_class": "external",
        "compensation_template": "Send correction zalo message for {action} recommendation",
    },
}

_VALID_CHANNELS = tuple(_CHANNEL_TO_NODE_PROPS.keys())


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class ActionScoreIn(BaseModel):
    """One ranked action from a CDFL plan response — input to the emitter."""

    action: str = Field(..., min_length=1, max_length=128)
    mean_score: float
    best_score: float = 0.0
    visit_proxy: int = 0


class EmitRequest(BaseModel):
    """Request body. Mirrors /cdfl/plan-next-action response so FE can
    pipe one endpoint's output into the other."""

    current_state: str = Field(..., min_length=1, max_length=128)
    top_actions: list[ActionScoreIn] = Field(..., min_length=1)

    workflow_name_suffix: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Optional human-readable suffix for the workflow id. Allowed "
            "chars: [a-z0-9_-]. Auto-derived from current_state + top "
            "action when omitted."
        ),
    )
    intervention_channel: Literal["log_only", "email", "telegram", "zalo"] = (
        Field(
            default="log_only",
            description=(
                "log_only = no external notification node; email/telegram/"
                "zalo emit external node with REL-012 compensation."
            ),
        )
    )


class EmitResponse(BaseModel):
    """Response shape. `yaml_parsed` lets the FE preview without YAML lib."""

    workflow_id: str
    yaml: str
    yaml_parsed: dict
    k17_check: str = "passed"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/workflow/from-cdfl-plan",
    response_model=EmitResponse,
    tags=["Workflow"],
)
async def workflow_from_cdfl_plan(
    body: EmitRequest,
    x_enterprise_id: Annotated[str, Header()],
) -> EmitResponse:
    """Emit a valid Temporal workflow YAML from a CDFL plan response."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)

    top_action = body.top_actions[0]
    workflow_id = _build_workflow_id(
        current_state=body.current_state,
        top_action=top_action.action,
        suffix=body.workflow_name_suffix,
    )

    doc = _build_workflow_doc(
        workflow_id=workflow_id,
        current_state=body.current_state,
        top_action=top_action,
        intervention_channel=body.intervention_channel,
    )

    # K-17 validation — must pass before we return YAML to the operator.
    try:
        validate_workflow_yaml(doc)
    except WorkflowSchemaError as exc:
        log.error(
            "workflow.from_cdfl_plan.k17_validation_failed",
            tenant_id=str(enterprise_id),
            workflow_id=workflow_id,
            node_id=exc.node_id,
            error=str(exc),
        )
        # 500 not 422 — emitter is OUR code, a failure here means we
        # generated invalid YAML, not that the caller mis-paramed.
        raise HTTPException(
            status_code=500,
            detail={
                "type": "https://kaori.ai/errors/workflow-emit-bug",
                "title": "emitter produced invalid YAML",
                "detail": str(exc),
                "errcode": "SYS-ERR1",
            },
        )

    yaml_text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)

    log.info(
        "workflow.from_cdfl_plan.emitted",
        tenant_id=str(enterprise_id),
        workflow_id=workflow_id,
        node_count=len(doc["nodes"]),
        edge_count=len(doc.get("edges", [])),
        intervention_channel=body.intervention_channel,
    )

    return EmitResponse(
        workflow_id=workflow_id,
        yaml=yaml_text,
        yaml_parsed=doc,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_workflow_id(
    *,
    current_state: str,
    top_action: str,
    suffix: Optional[str],
) -> str:
    """Generate deterministic, schema-safe workflow_id.

    Format: cdfl_{state}_to_{action}_{hash6}[_{suffix}]
    - state + action sanitised to [a-z0-9_]
    - hash6 disambiguates trivial collisions across tenants
    """
    state_slug = _slugify(current_state)
    action_slug = _slugify(top_action)
    seed = f"{state_slug}|{action_slug}|{suffix or ''}".encode("utf-8")
    hash6 = hashlib.sha256(seed).hexdigest()[:6]
    parts = [f"cdfl_{state_slug}_to_{action_slug}_{hash6}"]
    if suffix:
        parts.append(_slugify(suffix))
    workflow_id = "_".join(parts)
    return workflow_id[:100]  # respect yaml_schema.json maxLength


_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


def _slugify(value: str) -> str:
    if not value:
        return "x"
    slug = _SLUG_RE.sub("_", value.lower())
    slug = slug.strip("_-") or "x"
    return slug[:32]


def _build_workflow_doc(
    *,
    workflow_id: str,
    current_state: str,
    top_action,  # ActionScoreIn — not annotated to avoid circular import
    intervention_channel: str,
) -> dict:
    """Construct the Kaori workflow YAML dict for this CDFL plan."""
    nodes: list[dict] = [
        {
            "node_id": "wait_for_state",
            "type": "activity",
            "side_effect_class": "read_only",
            "timeout_ms": 60_000,
            "retry": {
                "max_attempts": 5,
                "initial_backoff_ms": 1000,
                "max_backoff_ms": 30_000,
                "multiplier": 2.0,
            },
            "input": {
                "watched_state": current_state,
                "poll_interval_seconds": 60,
            },
        },
        {
            "node_id": "compute_cdfl_recommendation",
            "type": "activity",
            "side_effect_class": "pure",
            "timeout_ms": 30_000,
            "retry": {"max_attempts": 3},
            "input": {
                "current_state": current_state,
                "expected_top_action": top_action.action,
                "expected_mean_score": float(top_action.mean_score),
            },
        },
        {
            "node_id": "log_recommendation",
            "type": "activity",
            "side_effect_class": "write_idempotent",
            "timeout_ms": 10_000,
            "retry": {"max_attempts": 5},
            "input": {
                "recommendation_action": top_action.action,
                "current_state": current_state,
            },
        },
    ]

    edges: list[dict] = [
        {"from": "wait_for_state", "to": "compute_cdfl_recommendation"},
        {"from": "compute_cdfl_recommendation", "to": "log_recommendation"},
    ]

    # Optional external notification node.
    if intervention_channel != "log_only":
        props = _CHANNEL_TO_NODE_PROPS[intervention_channel]
        nodes.append(
            {
                "node_id": "notify_customer",
                "type": "activity",
                "side_effect_class": props["side_effect_class"],
                "timeout_ms": 30_000,
                "retry": {"max_attempts": 3},
                "compensation": {
                    "node_id": "send_correction",
                    "reason_template": props["compensation_template"].format(
                        action=top_action.action
                    ),
                },
                "input": {
                    "channel": intervention_channel,
                    "message_template": (
                        f"Recommend next action: {top_action.action} "
                        f"(from state {current_state})"
                    ),
                },
            }
        )
        edges.append({"from": "log_recommendation", "to": "notify_customer"})

    return {
        "workflow_id": workflow_id,
        "name": (
            f"CDFL recommendation: {current_state} → {top_action.action}"
        ),
        "description": (
            "Auto-generated from /cdfl/plan-next-action output. "
            "Monitors customer state, computes CDFL recommendation, "
            "logs it, and optionally notifies via "
            f"{intervention_channel}."
        ),
        "version": "1.0",
        "nodes": nodes,
        "edges": edges,
    }


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
