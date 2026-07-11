"""Analytics router — template listing, run management, results retrieval."""
import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..reasoning.legacy_analytics.template_registry import (
    get_eligible_templates,
    profile_from_df,
)
from ..reasoning.legacy_analytics.runner import _load_silver, run_analysis_for_run
from ..shared.db import acquire_for_tenant

router = APIRouter()


class AnalyzeRequest(BaseModel):
    run_id: str
    templates: list[str]
    config: dict = {}


# ── GET /api/v1/analytics/templates ──────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    detected_types: str = "",          # comma-separated: "date,currency,text"
    detected_purpose: str | None = None,
    row_count: int = 0,
    run_id: str | None = None,        # profile the run's Silver server-side
    x_enterprise_id: Annotated[str | None, Header()] = None,
):
    """Return all templates with eligibility flag for the given data profile.

    Two modes:
      * explicit — caller passes detected_types/detected_purpose/row_count;
      * run-aware — caller passes run_id (+ X-Enterprise-ID) and the profile
        is derived from the run's Silver rows. Explicit params, when
        non-empty, override the derived values.
    """
    types_set = set(t.strip() for t in detected_types.split(",") if t.strip())

    if run_id and x_enterprise_id:
        try:
            df = await _load_silver(run_id, x_enterprise_id, None)
        except Exception:  # noqa: BLE001 — profiling is best-effort
            df = None
        if df is not None:
            d_types, d_purpose, d_rows = profile_from_df(df)
            types_set = types_set or d_types
            detected_purpose = detected_purpose or d_purpose
            row_count = row_count or d_rows

    return get_eligible_templates(types_set, detected_purpose, row_count)


# ── POST /api/v1/analytics/runs ───────────────────────────────────────────────

@router.post("/runs", status_code=202)
async def create_analysis_run(
    body: AnalyzeRequest,
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[str, Header()],
):
    """
    Create an analysis_run record and queue execution.
    Returns immediately (202 Accepted); poll /runs/{id} for status.
    """
    if not body.templates:
        raise HTTPException(400, "templates list cannot be empty")

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Verify pipeline run belongs to this enterprise
        # pipeline_runs PK is run_id (UUID) — there is no `id` column. The
        # old `SELECT id ... WHERE id=$1` 500'd the analyze step (same bug
        # dashboard.py already fixed).
        row = await conn.fetchrow("""
            SELECT run_id FROM pipeline_runs
            WHERE run_id = $1 AND enterprise_id = $2
        """, body.run_id, x_enterprise_id)
        if not row:
            raise HTTPException(404, "Pipeline run not found")

        # Insert analysis_run in 'queued' state
        analysis_run_id = await conn.fetchval("""
            INSERT INTO analysis_runs
                (enterprise_id, run_id, templates, config, status)
            VALUES ($1, $2, $3, $4::jsonb, 'queued')
            RETURNING id
        """, x_enterprise_id, body.run_id,
            body.templates, json.dumps(body.config))

    # Run immediately (not waiting for Kafka when calling directly)
    import asyncio
    asyncio.create_task(run_analysis_for_run(
        analysis_run_id=str(analysis_run_id),
        run_id=body.run_id,
        enterprise_id=x_enterprise_id,
        templates=body.templates,
        config=body.config,
    ))

    return {"analysis_run_id": str(analysis_run_id), "status": "queued"}


# ── GET /api/v1/analytics/runs ────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(
    x_enterprise_id: Annotated[str, Header()],
    limit: int = 20,
    offset: int = 0,
):
    """List recent analysis runs for this enterprise (K-1: enterprise filter)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch("""
            SELECT id, run_id, templates, status, created_at, completed_at
            FROM analysis_runs
            WHERE enterprise_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, x_enterprise_id, limit, offset)
    return [dict(r) for r in rows]


# ── GET /api/v1/analytics/runs/{id} ──────────────────────────────────────────

@router.get("/runs/{analysis_run_id}")
async def get_run(
    analysis_run_id: str,
    x_enterprise_id: Annotated[str, Header()],
):
    """Get analysis run status + per-template results."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        run = await conn.fetchrow("""
            SELECT id, run_id, templates, status, overview, config, created_at, completed_at
            FROM analysis_runs
            WHERE id = $1 AND enterprise_id = $2
        """, analysis_run_id, x_enterprise_id)
        if not run:
            raise HTTPException(404, "Analysis run not found")

        results = await conn.fetch("""
            SELECT template_id, status, results_payload, error_message, created_at
            FROM analysis_results
            WHERE analysis_run_id = $1 AND enterprise_id = $2
            ORDER BY created_at ASC
        """, analysis_run_id, x_enterprise_id)

    payload = dict(run)
    # FE Bước 5 hiển thị nguồn AI theo consent của CHÍNH run này (K-24 —
    # minh bạch model nào viết nhận xét). config là JSONB (str khi asyncpg
    # không decode) — chỉ cần cờ consent_external, không lộ nguyên config.
    cfg = payload.pop("config", None)
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except ValueError:
            cfg = None
    payload["consent_external"] = bool((cfg or {}).get("consent_external"))
    return {
        **payload,
        "template_results": [dict(r) for r in results],
    }
