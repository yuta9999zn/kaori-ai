"""
P2-S15 SH-M56b-026 — Visual agent workflow builder palette endpoint.

This is the agent-flavoured cousin of `/workflows/node-types` (which lists
all 45 mig 068 catalog rows). The palette here is a CURATED subset
optimized for chat-agent runtime use cases:

  - Drops `data_input` connectors that don't fit conversational flows
    (read_form_submission, read_calendar — agents don't poll).
  - Keeps all AI nodes (the moat of agent flows).
  - Keeps decision + action + output nodes.
  - Adds palette grouping by use-case category (intake / reasoning /
    action / output) instead of the storage-layer's 6 categories.

K-1 / K-12: tenant scope from JWT header — never accept from body.
K-3: AI nodes here just enumerate; actual `llm-gateway` dispatch happens
     in the agent_runtime when the workflow runs.

URL prefix
----------
This router is mounted at `/shared/agents/studio/builder` per
docs/BACKLOG_V4.md P2-S15 row (SH-M56b-026 column "API"). Builder UI lives
under `/p2/workflows` today; agent-studio variant gets its own palette
endpoint without forking the underlying node_type_catalog table.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter(prefix="/shared/agents/studio/builder")


# Curated palette: 45 catalog rows → 28 agent-friendly nodes grouped into
# 4 use-case buckets. Listed by node_type_key. Builder FE renders these.
AGENT_PALETTE_BUCKETS: dict[str, list[str]] = {
    "intake": [
        "read_chat",                # primary agent intake
        "read_webhook",
        "read_api",
        "read_email",
    ],
    "reasoning": [
        # All 8 AI nodes — agent's whole point
        "call_insight_engine",
        "call_recommendation_engine",
        "call_risk_detection",
        "call_forecasting",
        "generate_narrative",
        "classify_text",
        "extract_entities",
        "rag_query",
        # Light processing useful between reasoning steps
        "filter",
        "transform",
        "enrich",
    ],
    "decision": [
        "if_else",
        "switch",
        "approval_gate",
        "wait_for_condition",
    ],
    "action": [
        "send_chat_message",        # primary agent action
        "send_email",
        "create_task",
        "call_api",
        "trigger_workflow",
    ],
    "output": [
        "publish_insight",
        "publish_alert",
        "display_dashboard",
        "log",
    ],
}


class PaletteNode(BaseModel):
    """Single palette entry — catalog row + agent-specific bucket label."""
    node_type_key:          str
    bucket:                 str   # intake / reasoning / decision / action / output
    category:               str   # original mig 068 category (for cross-ref)
    side_effect_class:      str
    is_irreversible:        bool
    requires_saga:          bool
    cost_band:              str
    pricing_tier_required:  Optional[str]
    description_vi:         str
    sort_order:             int


class PaletteResponse(BaseModel):
    """Full palette grouped by bucket. FE renders bucket sections."""
    buckets:        dict[str, list[PaletteNode]]
    total_nodes:    int
    catalog_total:  int   # 45 — for "X of 45 nodes shown" UI affordance


@router.get("/palette", response_model=PaletteResponse)
async def get_agent_builder_palette(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    bucket: Optional[str] = Query(
        None,
        pattern=r"^(intake|reasoning|decision|action|output)$",
        description="Filter to one bucket. Omit to get full palette.",
    ),
):
    """Return curated palette for the agent workflow builder.

    Reads mig 068 node_type_catalog and joins with the AGENT_PALETTE_BUCKETS
    curation. Tenant-isolated via JWT header (K-12) though the catalog
    itself is global (no tenant_id column) — `acquire_for_tenant` still
    enforces the GUC for downstream RLS calls in same session.
    """
    target_keys: list[str] = []
    bucket_map: dict[str, str] = {}
    for b, keys in AGENT_PALETTE_BUCKETS.items():
        if bucket is not None and b != bucket:
            continue
        for k in keys:
            target_keys.append(k)
            bucket_map[k] = b

    if not target_keys:
        return PaletteResponse(buckets={}, total_nodes=0, catalog_total=0)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT node_type_key, category, side_effect_class,
                      is_irreversible, requires_saga, cost_band,
                      pricing_tier_required, description_vi, sort_order
               FROM node_type_catalog
               WHERE node_type_key = ANY($1::text[])
               ORDER BY sort_order""",
            target_keys,
        )
        catalog_total = await conn.fetchval("SELECT COUNT(*) FROM node_type_catalog")

    buckets: dict[str, list[PaletteNode]] = {}
    for r in rows:
        b = bucket_map[r["node_type_key"]]
        buckets.setdefault(b, []).append(PaletteNode(
            node_type_key=r["node_type_key"],
            bucket=b,
            category=r["category"],
            side_effect_class=r["side_effect_class"],
            is_irreversible=r["is_irreversible"],
            requires_saga=r["requires_saga"],
            cost_band=r["cost_band"],
            pricing_tier_required=r["pricing_tier_required"],
            description_vi=r["description_vi"],
            sort_order=r["sort_order"],
        ))

    total = sum(len(v) for v in buckets.values())
    return PaletteResponse(buckets=buckets, total_nodes=total, catalog_total=catalog_total)
