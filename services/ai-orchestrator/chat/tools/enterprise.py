"""
P2 Enterprise tools — bind ``enterprise_id`` from JWT, RLS-aware.

All three tools wrap their DB query in ``acquire_for_tenant`` so
the row-level security policies declared in ``005_rls.sql`` filter
by the calling tenant. Even if a future change drops the BYPASSRLS
flag on ``kaori_app``, these tools keep working unchanged.

Tool catalog (v0):
    summarize_recent_decisions   — decision_audit_log group-by
    get_top_at_risk_customers    — gold_features (F-032 PR #80)
    get_billing_quota_status     — v_billing_summary view
"""
from __future__ import annotations

from ...shared.db import acquire_for_tenant
from .base import BaseTool, ToolContext


# =========================================================================
# summarize_recent_decisions
# =========================================================================

class SummarizeRecentDecisionsTool(BaseTool):
    name = "summarize_recent_decisions"
    description = (
        "Tóm tắt các quyết định AI gần đây của doanh nghiệp (từ "
        "decision_audit_log) — đếm theo loại quyết định trong N ngày qua. "
        "Dùng khi user hỏi 'AI đã quyết những gì tuần này' hoặc tương tự."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Số ngày gần nhất, mặc định 7, tối đa 90.",
                "minimum": 1,
                "maximum": 90,
                "default": 7,
            },
        },
        "required": [],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict:
        days = int(args.get("days", 7))
        if days < 1 or days > 90:
            raise ValueError("days must be between 1 and 90")
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            rows = await conn.fetch(
                """
                SELECT decision_type, COUNT(*) AS n
                  FROM decision_audit_log
                 WHERE enterprise_id = $1
                   AND created_at >= NOW() - ($2 || ' days')::INTERVAL
                 GROUP BY decision_type
                 ORDER BY n DESC
                """,
                ctx.enterprise_id,
                str(days),
            )

        total = sum(r["n"] for r in rows)
        return {
            "window_days": days,
            "total_decisions": total,
            "by_type": [
                {"decision_type": r["decision_type"], "count": int(r["n"])}
                for r in rows
            ],
        }


# =========================================================================
# get_top_at_risk_customers
# =========================================================================

class GetTopAtRiskCustomersTool(BaseTool):
    name = "get_top_at_risk_customers"
    description = (
        "Liệt kê top khách hàng có doanh thu rủi ro cao nhất (từ bảng "
        "gold_features). Trả về customer_external_id + revenue_at_risk. "
        "Dùng khi user hỏi 'Ai đang sắp churn?' / 'Top khách rủi ro?'."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Số lượng khách hàng trả về (1–20).",
                "minimum": 1,
                "maximum": 20,
                "default": 5,
            },
        },
        "required": [],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict:
        limit = int(args.get("limit", 5))
        if limit < 1 or limit > 20:
            raise ValueError("limit must be between 1 and 20")
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            rows = await conn.fetch(
                """
                SELECT customer_external_id, revenue_at_risk,
                       last_purchase_at, purchase_count
                  FROM gold_features
                 WHERE enterprise_id = $1
                   AND revenue_at_risk > 0
                 ORDER BY revenue_at_risk DESC
                 LIMIT $2
                """,
                ctx.enterprise_id,
                limit,
            )

        return {
            "count": len(rows),
            "customers": [
                {
                    "customer_external_id": r["customer_external_id"],
                    "revenue_at_risk": float(r["revenue_at_risk"]),
                    "last_purchase_at": r["last_purchase_at"].isoformat()
                    if r["last_purchase_at"] else None,
                    "purchase_count": int(r["purchase_count"]),
                }
                for r in rows
            ],
        }


# =========================================================================
# get_billing_quota_status
# =========================================================================

class GetBillingQuotaStatusTool(BaseTool):
    name = "get_billing_quota_status"
    description = (
        "Cho biết hạn mức (quota) và số khách hàng duy nhất đã dùng "
        "trong tháng hiện tại — đọc từ view v_billing_summary. Trả về "
        "usage_pct, plan_code, alert_80, alert_95."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict:
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT v.plan_code, v.quota, v.current_month_usage, v.usage_pct,
                       COALESCE(b.alert_80_fired, FALSE) AS alert_80,
                       COALESCE(b.alert_95_fired, FALSE) AS alert_95
                  FROM v_billing_summary v
                  LEFT JOIN enterprise_monthly_billing b
                    ON b.enterprise_id = v.enterprise_id
                   AND b.billing_month = DATE_TRUNC('month', NOW())::DATE
                 WHERE v.enterprise_id = $1
                """,
                ctx.enterprise_id,
            )

        if row is None:
            return {"found": False}

        return {
            "found": True,
            "plan_code": row["plan_code"],
            "quota": int(row["quota"]),
            "current_month_usage": int(row["current_month_usage"]),
            "usage_pct": float(row["usage_pct"]) if row["usage_pct"] is not None else 0.0,
            "alert_80_fired": bool(row["alert_80"]),
            "alert_95_fired": bool(row["alert_95"]),
        }
