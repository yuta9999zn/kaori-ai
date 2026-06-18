"""
Dashboard & Insights & Billing router.
GET /api/v1/dashboard/state   — 5-state dashboard machine
GET /api/v1/insights/feed     — AI-generated insight cards
GET /api/v1/billing/summary   — quota usage summary
"""
import asyncio
import json
import os
from typing import Annotated

import structlog
from fastapi import APIRouter, Header

from ..engine.llm_router import llm_router
from ..reasoning.grounding import collect_facts, disclaimer_for, ground_claims
from ..shared import ai_config
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()
router = APIRouter()


# ── GET /api/v1/dashboard/state ───────────────────────────────────────────────

@router.get("/dashboard/state")
async def dashboard_state(
    x_enterprise_id: Annotated[str, Header()],
):
    """
    Returns one of 5 states so the frontend can render the correct view:
      no_data → first_upload → pending_review → analysis_ready → results_ready
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Check latest pipeline run. PK is run_id (uuid); the older code
        # selected "id" which doesn't exist on this table → 500.
        run = await conn.fetchrow("""
            SELECT run_id, status, created_at
            FROM pipeline_runs
            WHERE enterprise_id = $1
            ORDER BY created_at DESC
            LIMIT 1
        """, x_enterprise_id)

        if not run:
            return {"state": "no_data", "run_id": None}

        run_status = run["status"]
        run_id = str(run["run_id"])

        # Status enum canonical names per migration 002 + Sprint 7 PR C:
        # uploading | bronze_complete | schema_review | silver_complete
        # | analyzing | analysis_complete | failed | cancelled.
        if run_status in ("uploading", "bronze_complete"):
            return {"state": "first_upload", "run_id": run_id, "pipeline_status": run_status}

        if run_status == "schema_review":
            return {"state": "pending_review", "run_id": run_id, "pipeline_status": run_status}

        if run_status == "silver_complete":
            return {"state": "analysis_ready", "run_id": run_id}

        if run_status in ("analyzing", "analysis_complete"):
            # Get analysis results summary
            analysis = await conn.fetchrow("""
                SELECT id, templates, status, overview, completed_at
                FROM analysis_runs
                WHERE run_id = $1 AND enterprise_id = $2
                ORDER BY created_at DESC LIMIT 1
            """, run_id, x_enterprise_id)

            kpis = await _compute_kpis(run_id, x_enterprise_id, conn)

            return {
                "state": "results_ready",
                "run_id": run_id,
                "analysis_run_id": str(analysis["id"]) if analysis else None,
                "templates_run": analysis["templates"] if analysis else [],
                "kpis": kpis,
            }

        return {"state": "no_data", "run_id": run_id}


# ── GET /api/v1/insights/feed ─────────────────────────────────────────────────

@router.get("/insights/feed")
async def insights_feed(
    x_enterprise_id: Annotated[str, Header()],
    limit: int = 10,
):
    """
    Return AI-generated insight cards from latest analysis results.
    Each card: {id, title, body, category, run_id}
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        analysis = await conn.fetchrow("""
            SELECT ar.id, ar.templates, ar.overview,
                   array_agg(res.results_payload) AS results
            FROM analysis_runs ar
            LEFT JOIN analysis_results res ON res.analysis_run_id = ar.id
                AND res.status = 'done'
            WHERE ar.enterprise_id = $1 AND ar.status = 'done'
            GROUP BY ar.id
            ORDER BY ar.completed_at DESC
            LIMIT 1
        """, x_enterprise_id)

    if not analysis:
        return {"insights": [], "note": "Chạy phân tích để xem insights."}

    # asyncpg returns JSONB as a str unless a codec is registered — guard both
    # columns (same pattern the results loop below already uses) so .get()/iter
    # don't blow up with AttributeError. Latent 500 on /insights/feed once an
    # analysis row existed.
    overview = analysis["overview"] or {}
    if isinstance(overview, str):
        try:
            overview = json.loads(overview)
        except (ValueError, TypeError):
            overview = {}
    narrative = overview.get("narrative", "") if isinstance(overview, dict) else ""
    templates = analysis["templates"] or []
    if isinstance(templates, str):
        try:
            templates = json.loads(templates)
        except (ValueError, TypeError):
            templates = []

    # CR-0018 — the measured facts behind this analysis. Used twice: injected
    # into the prompt to GROUND generation (the LLM sees the real numbers), and
    # kept to VERIFY the output (flag any number it still invents).
    results = [r for r in (analysis["results"] or []) if r is not None]
    facts: list[float] = []
    for payload in results:
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                continue
        facts.extend(collect_facts(payload))
    facts.extend(collect_facts(overview))

    facts_block = json.dumps(results, ensure_ascii=False, default=str)[:2000] if results else ""

    prompt = (
        f"Từ kết quả phân tích ({', '.join(templates)}):\n{narrative}\n\n"
        + (f"DỮ LIỆU ĐO ĐƯỢC (CHỈ dùng số có trong đây, TUYỆT ĐỐI không bịa số mới):\n"
           f"{facts_block}\n\n" if facts_block else "")
        + f"Hãy tạo {min(limit, 5)} insight ngắn gọn, mỗi insight gồm:\n"
        "- title: 5-8 từ\n"
        "- body: 1-2 câu cụ thể\n"
        "- category: trend|anomaly|opportunity|risk\n"
        "Format: title|||body|||category (một dòng mỗi insight)\n"
        "Bằng tiếng Việt."
    )

    # K — LLM in the request path MUST be bounded. The dashboard insight tile
    # calls this synchronously behind a 30s gateway timeout; on the pilot's
    # local Qwen 7B a cold generation can exceed it, and the gateway then
    # returns a raw "Response took longer than timeout: PT30S" to the user.
    # Cap the LLM well under the gateway deadline and degrade to a friendly
    # empty state instead (env-configurable, no hardcode).
    llm_deadline_s = float(os.getenv("KAORI_INSIGHTS_LLM_DEADLINE_S", "22"))
    try:
        answer = await asyncio.wait_for(
            llm_router.complete(
                prompt=prompt,
                task="insights_feed",
                enterprise_id=x_enterprise_id,
            ),
            timeout=llm_deadline_s,
        )
    except (asyncio.TimeoutError, TimeoutError):
        log.warning(
            "insights_feed.llm_timeout",
            enterprise_id=x_enterprise_id,
            deadline_s=llm_deadline_s,
        )
        return {
            "insights": [],
            "note": "Insight đang được tạo (mô hình đang bận) — tải lại sau ít phút.",
        }

    # CR-0019 — grounding strictness is a platform-admin knob (falls back to
    # the CR-0018 default when unset / DB unavailable).
    tol = await ai_config.get_float("grounding_tolerance", 0.02)

    insights = []
    for i, line in enumerate(answer.strip().split("\n")):
        parts = [p.strip() for p in line.split("|||")]
        if len(parts) == 3:
            # CR-0018 — grounding self-verify on the body (|OR| number-overlap).
            g = ground_claims(parts[1], facts, tol=tol)
            insights.append({
                "id": f"insight_{i}",
                "title": parts[0],
                "body": parts[1],
                "category": parts[2] if parts[2] in ("trend", "anomaly", "opportunity", "risk") else "trend",
                "analysis_run_id": str(analysis["id"]),
                "grounding_score": g.score,
                "flagged_claims": g.flagged,
                "disclaimer": disclaimer_for(g),
            })
        if len(insights) >= limit:
            break

    flagged_total = sum(len(it["flagged_claims"]) for it in insights)
    if flagged_total:
        log.warning("insights_feed.grounding_flagged",
                    run_id=str(analysis["id"]), flagged=flagged_total,
                    insights=len(insights))

    return {"insights": insights}


# ── GET /api/v1/billing/summary ───────────────────────────────────────────────

@router.get("/billing/summary")
async def billing_summary(
    x_enterprise_id: Annotated[str, Header()],
):
    """Return quota usage for current billing period."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Schema reality: enterprises has no plan_code column — the plan lives
        # on workspaces. emb.month is actually emb.billing_month. Joining via
        # enterprise -> workspace -> subscription_plans, falling back to
        # 'PILOT' when nothing's been provisioned yet so the FE shell doesn't
        # break on an empty tenant.
        row = await conn.fetchrow("""
            SELECT
                emb.billing_month AS month,
                emb.unique_customers,
                sp.monthly_quota,
                sp.plan_code,
                CASE
                    WHEN sp.monthly_quota IS NULL THEN 0
                    ELSE ROUND(emb.unique_customers::numeric / sp.monthly_quota * 100, 1)
                END AS usage_pct
            FROM enterprise_monthly_billing emb
            JOIN enterprises e        ON e.enterprise_id = emb.enterprise_id
            JOIN workspaces   w        ON w.workspace_id  = e.workspace_id
            JOIN subscription_plans sp ON sp.plan_code    = w.plan_code
            WHERE emb.enterprise_id = $1
              AND emb.billing_month = DATE_TRUNC('month', NOW())::DATE
            LIMIT 1
        """, x_enterprise_id)

    if not row:
        return {
            "month": None,
            "unique_customers": 0,
            "monthly_quota": None,
            "plan_code": "PILOT",
            "usage_pct": 0,
        }
    return dict(row)


# ── Helper ────────────────────────────────────────────────────────────────────

async def _compute_kpis(run_id: str, enterprise_id: str, conn) -> list[dict]:
    """Extract top-level KPI values from analysis_results for dashboard cards.

    Caller passes an already-acquired tenant-scoped connection so we don't
    open a second one (keeps the whole dashboard_state in one transaction).
    """
    rows = await conn.fetch("""
        SELECT template_id, results_payload
        FROM analysis_results
        WHERE analysis_run_id IN (
            SELECT id FROM analysis_runs
            WHERE run_id = $1 AND enterprise_id = $2
            ORDER BY created_at DESC LIMIT 1
        ) AND status = 'done'
    """, run_id, enterprise_id)

    kpis = []
    for row in rows:
        payload = row["results_payload"] or {}
        blocks = payload.get("blocks", [])
        for block in blocks:
            if block.get("type") == "stats_card":
                kpis.append({
                    "template": row["template_id"],
                    "title": block.get("title", ""),
                    "data": block.get("data", {}),
                })
    return kpis
