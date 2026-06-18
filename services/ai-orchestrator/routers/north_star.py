"""
F-060 — North Star tile + per-customer action toggle.

Closes the CLAUDE.md §14 limitation: the canonical North Star formula

    SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)

now reads ``gold_features.is_actioned`` directly. v0 uses
``revenue_at_risk > 0`` as the HIGH-risk proxy because the aggregator
(services/data-pipeline/.../gold/aggregator.py) only writes non-zero
``revenue_at_risk`` for model-flagged customers. F-051 explicit
classifier later narrows this to a label column.

Endpoints::

    POST /api/v1/customers/{customer_external_id}/action
                                                   toggle is_actioned + actioned_at + actioned_by_user
                                                   emit kaori.feedback.actions (customer.actioned/unactioned)
    GET  /api/v1/dashboard/north-star               total_at_risk, resolved, resolution_rate, top_actioned
    GET  /api/v1/customers/at-risk                  cursor list of revenue_at_risk > 0 customers
                                                   filterable by ?actioned=true|false

Sprint 7 PR D's ``decision_actions`` side table keeps working for the
per-decision toggle on ``/decisions`` — that's a *different* product
surface. The dashboard tile + ROI rollup now key off this canonical
column instead.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..shared import kafka_topics
from ..shared.db import acquire_for_tenant
from ..shared.kafka_producer import emit

log = structlog.get_logger()

router = APIRouter()

DEFAULT_LIMIT = 50
MAX_LIMIT     = 500


# =========================================================================
# Wire shapes
# =========================================================================

class CustomerActionRequest(BaseModel):
    is_actioned: bool = Field(
        ...,
        description="True flips the row to 'resolved' (counts toward North Star). "
                    "False reverts (rare — usually only for typos).",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional context — what action was taken or why "
                    "the toggle was reverted.",
    )


class CustomerActionResponse(BaseModel):
    customer_external_id: str
    is_actioned:          bool
    actioned_at:          Optional[datetime] = None
    actioned_by_user:     Optional[UUID] = None
    revenue_at_risk:      float


class NorthStarTileResponse(BaseModel):
    """Dashboard tile payload — three numbers + a teaser of recently
    resolved customers so the FE can render a sparkline / activity feed
    without a second round-trip."""
    total_at_risk_vnd:    float = Field(
        description="Sum of revenue_at_risk across all flagged customers, "
                    "actioned or not.",
    )
    resolved_vnd:         float = Field(
        description="Canonical North Star number — sum where "
                    "is_actioned=true. Renders as the headline.",
    )
    resolution_rate_pct:  float = Field(
        description="resolved / total_at_risk × 100. 0 when total_at_risk=0.",
    )
    actioned_count:       int
    at_risk_count:        int
    recent_actions:       list["RecentActionItem"] = Field(default_factory=list)


class RecentActionItem(BaseModel):
    customer_external_id: str
    revenue_at_risk:      float
    actioned_at:          datetime
    actioned_by_user:     Optional[UUID] = None


class AtRiskCustomerItem(BaseModel):
    customer_external_id: str
    revenue_at_risk:      float
    last_purchase_at:     Optional[datetime] = None
    purchase_count:       int
    is_actioned:          bool
    actioned_at:          Optional[datetime] = None
    actioned_by_user:     Optional[UUID] = None
    computed_at:          datetime


class AtRiskListResponse(BaseModel):
    items:       list[AtRiskCustomerItem]
    next_cursor: Optional[str] = None


# Forward-ref resolution for the nested model.
NorthStarTileResponse.model_rebuild()


# =========================================================================
# POST /api/v1/customers/{customer_external_id}/action
# =========================================================================

@router.post(
    "/customers/{customer_external_id}/action",
    response_model=CustomerActionResponse,
)
async def upsert_customer_action(
    customer_external_id: str,
    body: CustomerActionRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Mark / unmark a customer's ``is_actioned`` flag on gold_features.

    Idempotent: same (customer, is_actioned) hit twice writes the same
    row state but bumps actioned_at — the FE shows the latest toggle
    time even if the value didn't change. Kafka emit fires every time
    (including no-op flips) so consumers see the user touched the row.
    Best-effort emit; a Kafka outage doesn't roll back the DB write."""

    sql = """
        UPDATE gold_features
           SET is_actioned      = $3,
               actioned_at      = CASE WHEN $3 THEN NOW() ELSE NULL END,
               actioned_by_user = CASE WHEN $3 THEN $4    ELSE NULL END
         WHERE enterprise_id        = $1
           AND customer_external_id = $2
        RETURNING customer_external_id, is_actioned, actioned_at,
                  actioned_by_user, revenue_at_risk
    """

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            sql, x_enterprise_id, customer_external_id,
            body.is_actioned, x_user_id,
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Customer {customer_external_id} not in gold_features — "
                       f"run the gold aggregator first.",
            )

    occurred_at = (
        row["actioned_at"].astimezone(timezone.utc).isoformat()
        if row["actioned_at"]
        else datetime.now(timezone.utc).isoformat()
    )

    try:
        await emit(kafka_topics.FEEDBACK_ACTIONS, {
            # The schema requires override_id + decision_id — this isn't
            # an override event, so we use synthetic identifiers that
            # consumers can route off ``action`` instead. additionalProperties
            # is true on the schema so this works without a schema bump.
            "override_id":    f"customer:{x_enterprise_id}:{customer_external_id}",
            "decision_id":    f"customer:{customer_external_id}",
            "enterprise_id":  str(x_enterprise_id),
            "action":         "customer.actioned" if body.is_actioned else "customer.unactioned",
            "decision_type":  "customer_action",
            "original_value": "",
            "override_value": "true" if body.is_actioned else "false",
            "reason":         body.notes or "",
            "user_id":        str(x_user_id) if x_user_id else "",
            "occurred_at":    occurred_at,
        })
    except Exception as exc:
        log.error(
            "customer.action.kafka_emit_failed",
            customer_external_id=customer_external_id,
            enterprise_id=str(x_enterprise_id),
            error=str(exc),
        )

    log.info(
        "customer.action.upsert",
        enterprise_id=str(x_enterprise_id),
        customer_external_id=customer_external_id,
        is_actioned=body.is_actioned,
        actioned_by=str(x_user_id) if x_user_id else None,
    )

    return CustomerActionResponse(
        customer_external_id=row["customer_external_id"],
        is_actioned=row["is_actioned"],
        actioned_at=row["actioned_at"],
        actioned_by_user=row["actioned_by_user"],
        revenue_at_risk=float(row["revenue_at_risk"] or 0),
    )


# =========================================================================
# GET /api/v1/dashboard/north-star
# =========================================================================

@router.get("/dashboard/north-star", response_model=NorthStarTileResponse)
async def north_star_tile(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Three-number tile for the home dashboard.

    Formula matches CLAUDE.md §14:
        SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)

    v0 uses ``revenue_at_risk > 0`` as the HIGH proxy (the aggregator
    only writes non-zero for model-flagged customers; idle customers
    stay at 0). F-051 explicit classifier later narrows to a label
    column."""

    sql_summary = """
        SELECT
            COALESCE(SUM(revenue_at_risk), 0)                                     AS total_at_risk,
            COALESCE(SUM(revenue_at_risk) FILTER (WHERE is_actioned), 0)           AS resolved,
            COUNT(*) FILTER (WHERE revenue_at_risk > 0)                           AS at_risk_count,
            COUNT(*) FILTER (WHERE revenue_at_risk > 0 AND is_actioned)           AS actioned_count
          FROM gold_features
         WHERE enterprise_id   = $1
           AND revenue_at_risk > 0
    """

    sql_recent = """
        SELECT customer_external_id, revenue_at_risk, actioned_at, actioned_by_user
          FROM gold_features
         WHERE enterprise_id    = $1
           AND is_actioned      = TRUE
           AND revenue_at_risk  > 0
           AND actioned_at IS NOT NULL
         ORDER BY actioned_at DESC
         LIMIT 5
    """

    async with acquire_for_tenant(x_enterprise_id) as conn:
        summary = await conn.fetchrow(sql_summary, x_enterprise_id)
        recent  = await conn.fetch(sql_recent, x_enterprise_id)

    total = float(summary["total_at_risk"] or 0)
    resolved = float(summary["resolved"] or 0)
    resolution_rate = (resolved / total * 100.0) if total > 0 else 0.0

    return NorthStarTileResponse(
        total_at_risk_vnd=total,
        resolved_vnd=resolved,
        resolution_rate_pct=round(resolution_rate, 2),
        actioned_count=int(summary["actioned_count"] or 0),
        at_risk_count=int(summary["at_risk_count"] or 0),
        recent_actions=[
            RecentActionItem(
                customer_external_id=r["customer_external_id"],
                revenue_at_risk=float(r["revenue_at_risk"] or 0),
                actioned_at=r["actioned_at"],
                actioned_by_user=r["actioned_by_user"],
            )
            for r in recent
        ],
    )


# =========================================================================
# GET /api/v1/customers/at-risk
# =========================================================================

def _encode_cursor(revenue_at_risk: float, customer_external_id: str) -> str:
    raw = f"{revenue_at_risk}|{customer_external_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[float, str]:
    pad = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + pad).encode("ascii")).decode("utf-8")
        rev_str, ext_id = decoded.split("|", 1)
        return float(rev_str), ext_id
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}")


@router.get("/customers/at-risk", response_model=AtRiskListResponse)
async def list_at_risk_customers(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor:   Optional[str]  = Query(None),
    limit:    int            = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    actioned: Optional[bool] = Query(None, description="Filter — true / false / omitted (all)"),
):
    """Cursor-paginated list of at-risk customers (revenue_at_risk > 0)
    for the FE to render the action UI. Sorted by revenue_at_risk DESC
    so the highest-impact customers surface first.

    Cursor format: base64url(``<revenue_at_risk>|<customer_external_id>``).
    """

    where_parts = ["enterprise_id = $1", "revenue_at_risk > 0"]
    params: list = [x_enterprise_id]

    if actioned is not None:
        where_parts.append(f"is_actioned = ${len(params) + 1}")
        params.append(actioned)

    if cursor:
        cursor_rev, cursor_id = _decode_cursor(cursor)
        where_parts.append(
            f"(revenue_at_risk, customer_external_id) "
            f"< (${len(params) + 1}, ${len(params) + 2})"
        )
        params.extend([cursor_rev, cursor_id])

    sql = f"""
        SELECT customer_external_id, revenue_at_risk, last_purchase_at,
               purchase_count, is_actioned, actioned_at, actioned_by_user,
               computed_at
          FROM gold_features
         WHERE {" AND ".join(where_parts)}
         ORDER BY revenue_at_risk DESC, customer_external_id DESC
         LIMIT ${len(params) + 1}
    """
    params.append(limit + 1)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor: Optional[str] = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(
            float(last["revenue_at_risk"]),
            last["customer_external_id"],
        )

    return AtRiskListResponse(
        items=[
            AtRiskCustomerItem(
                customer_external_id=r["customer_external_id"],
                revenue_at_risk=float(r["revenue_at_risk"] or 0),
                last_purchase_at=r["last_purchase_at"],
                purchase_count=int(r["purchase_count"] or 0),
                is_actioned=bool(r["is_actioned"]),
                actioned_at=r["actioned_at"],
                actioned_by_user=r["actioned_by_user"],
                computed_at=r["computed_at"],
            )
            for r in items
        ],
        next_cursor=next_cursor,
    )
