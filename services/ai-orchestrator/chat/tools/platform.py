"""
P1 Platform tools — cross-tenant, role-gated to SUPER_ADMIN/ADMIN.

These tools intentionally do NOT use ``acquire_for_tenant`` because
they need to aggregate across tenants. The role gate sits in the
registry (see registry.dispatch) so a non-admin caller can never
land in this code path.

Every invocation lands in decision_audit_log with
``decision_type='chat.platform_tool'`` so platform admins reading
through cross-tenant data leave a trail (CLAUDE.md K-15 spirit).
"""
from __future__ import annotations

from ...shared.db import acquire_cross_tenant
from .base import BaseTool, ToolContext


# =========================================================================
# get_platform_summary
# =========================================================================

class GetPlatformSummaryTool(BaseTool):
    name = "get_platform_summary"
    description = (
        "Đếm tổng số workspace, enterprise, user, và pipeline runs đang "
        "có trên platform. Dùng khi admin hỏi 'Hiện có bao nhiêu khách "
        "hàng?' / 'Quy mô hệ thống?' / kiểm tra sức khỏe nhanh."
    )
    scope = "platform"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict:
        # Migration 024 prep — pipeline_runs is RLS-protected. acquire_cross_tenant
        # flips row_security=off for this transaction so the platform-admin
        # COUNT(*) keeps working once kaori_app loses BYPASSRLS.
        async with acquire_cross_tenant() as conn:
            # One-shot multi-count to avoid five round-trips.
            row = await conn.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM workspaces                          WHERE status = 'active') AS workspaces_active,
                  (SELECT COUNT(*) FROM enterprises                          WHERE status = 'active') AS enterprises_active,
                  (SELECT COUNT(*) FROM enterprise_users                     WHERE status = 'active') AS users_active,
                  (SELECT COUNT(*) FROM pipeline_runs)                                                AS pipeline_runs_total,
                  (SELECT COUNT(*) FROM pipeline_runs WHERE created_at >= NOW() - INTERVAL '7 days')  AS pipeline_runs_last_7d
                """
            )
        return {
            "workspaces_active":      int(row["workspaces_active"]),
            "enterprises_active":     int(row["enterprises_active"]),
            "users_active":           int(row["users_active"]),
            "pipeline_runs_total":    int(row["pipeline_runs_total"]),
            "pipeline_runs_last_7d":  int(row["pipeline_runs_last_7d"]),
        }


# =========================================================================
# count_recent_signups
# =========================================================================

class CountRecentSignupsTool(BaseTool):
    name = "count_recent_signups"
    description = (
        "Đếm số enterprise mới đăng ký trong N ngày qua. Hữu ích cho "
        "câu hỏi 'Tuần này có bao nhiêu khách mới?' / kiểm tra funnel."
    )
    scope = "platform"
    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Số ngày gần nhất, mặc định 30, tối đa 365.",
                "minimum": 1,
                "maximum": 365,
                "default": 30,
            },
        },
        "required": [],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict:
        days = int(args.get("days", 30))
        if days < 1 or days > 365:
            raise ValueError("days must be between 1 and 365")

        # enterprises has no RLS today, so acquire_cross_tenant is harmless.
        # Kept for consistency — every platform-tool path uses the same wrapper.
        async with acquire_cross_tenant() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  COUNT(*) FILTER (WHERE created_at >= NOW() - ($1 || ' days')::INTERVAL) AS new_count,
                  COUNT(*)                                                                AS total_count
                  FROM enterprises
                 WHERE status = 'active'
                """,
                str(days),
            )
        return {
            "window_days":   days,
            "new_signups":   int(row["new_count"]),
            "total_active":  int(row["total_count"]),
        }


# =========================================================================
# find_workspaces_in_alert
# =========================================================================

class FindWorkspacesInAlertTool(BaseTool):
    name = "find_workspaces_in_alert"
    description = (
        "Liệt kê các enterprise đã chạm ngưỡng cảnh báo billing (80% "
        "hoặc 95% quota) trong tháng hiện tại — đọc từ "
        "enterprise_monthly_billing. Trả về tối đa 50 dòng."
    )
    scope = "platform"
    parameters = {
        "type": "object",
        "properties": {
            "threshold": {
                "type": "string",
                "description": "Ngưỡng cảnh báo cần tìm: '80' (sắp hết), "
                               "'95' (gần kịch), hoặc 'any' (cả hai).",
                "enum": ["80", "95", "any"],
                "default": "any",
            },
        },
        "required": [],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict:
        threshold = args.get("threshold", "any")
        if threshold not in {"80", "95", "any"}:
            raise ValueError("threshold must be one of: 80, 95, any")

        if threshold == "80":
            where = "b.alert_80_fired = TRUE"
        elif threshold == "95":
            where = "b.alert_95_fired = TRUE"
        else:
            where = "(b.alert_80_fired = TRUE OR b.alert_95_fired = TRUE)"

        # enterprise_monthly_billing IS RLS-protected — acquire_cross_tenant
        # turns it off for this read so the platform-admin alert list works.
        async with acquire_cross_tenant() as conn:
            rows = await conn.fetch(
                f"""
                SELECT b.enterprise_id, e.name AS enterprise_name,
                       b.billing_month, b.unique_customers, b.quota,
                       b.alert_80_fired, b.alert_95_fired
                  FROM enterprise_monthly_billing b
                  JOIN enterprises e ON e.enterprise_id = b.enterprise_id
                 WHERE b.billing_month = DATE_TRUNC('month', NOW())::DATE
                   AND {where}
                 ORDER BY b.unique_customers::FLOAT / NULLIF(b.quota, 0) DESC
                 LIMIT 50
                """
            )

        return {
            "threshold": threshold,
            "count": len(rows),
            "workspaces": [
                {
                    "enterprise_id":    str(r["enterprise_id"]),
                    "enterprise_name":  r["enterprise_name"],
                    "billing_month":    r["billing_month"].isoformat(),
                    "unique_customers": int(r["unique_customers"]),
                    "quota":            int(r["quota"]),
                    "usage_pct": round(
                        100.0 * r["unique_customers"] / r["quota"], 2
                    ) if r["quota"] else 0.0,
                    "alert_80_fired":   bool(r["alert_80_fired"]),
                    "alert_95_fired":   bool(r["alert_95_fired"]),
                }
                for r in rows
            ],
        }
