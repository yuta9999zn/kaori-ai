"""Qwen Workflow Advisor endpoints (ADR-0040).

Sits beside workflow_builder.router (same /workflows/... namespace, no prefix;
already routed at the edge via /api/v1/workflows/**). K-1 RLS via
acquire_for_tenant. The advisor run (rules + optional Qwen narrative) executes
in a BackgroundTask so the LLM stays off the request path
(feedback: llm-in-request-path-bound); the FE polls GET for the result.
"""
from __future__ import annotations

import json
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path

from ..shared.db import acquire_for_tenant
from ..reasoning import workflow_advisor as advisor

log = structlog.get_logger()
router = APIRouter()


async def _run_and_store(workflow_id: UUID, enterprise_id: UUID) -> None:
    """Background: evaluate the workflow and append a workflow_review row.

    Two-phase so the (slow, unreliable on pilot 7B) Qwen narrative never holds
    the deterministic findings hostage:
      1. Run rules-only + store the row IMMEDIATELY → the FE's GET poll shows
         findings within a cycle (previously the narrate() call ran ~90s before
         the INSERT, so the FE saw 'never_run' for ~25s and gave up).
      2. Best-effort Qwen narrative → UPDATE the row in place if it lands.
    """
    try:
        # Phase 1 — fast rules-only result, stored right away.
        async with acquire_for_tenant(enterprise_id) as conn:
            review = await advisor.evaluate(
                conn, workflow_id, enterprise_id, with_narrative=False,
            )
            if review is None:
                return
            review_id = await conn.fetchval(
                """INSERT INTO workflow_review
                       (enterprise_id, workflow_id, run_mode, model,
                        overall_health, findings, narrative)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, NULL)
                   RETURNING review_id""",
                enterprise_id, workflow_id, review["run_mode"], review["model"],
                review["overall_health"], json.dumps(review["findings"]),
            )
        log.info("advisor.run_stored", workflow_id=str(workflow_id),
                 mode=review["run_mode"], health=review["overall_health"],
                 findings=len(review["findings"]))
    except Exception as e:  # pragma: no cover - background safety net
        log.exception("advisor.run_failed", workflow_id=str(workflow_id), error=str(e))
        return

    # Phase 2 — best-effort Qwen narrative (no DB connection held during the
    # LLM call). On pilot 7B this usually times out → row stays rules-only.
    try:
        narrative = await advisor.narrate(workflow_id, enterprise_id, review["findings"])
        if narrative:
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """UPDATE workflow_review
                          SET narrative = $1, model = 'qwen2.5-local'
                        WHERE review_id = $2""",
                    narrative, review_id,
                )
            log.info("advisor.narrative_added", workflow_id=str(workflow_id))
    except Exception as e:  # pragma: no cover - narrative is best-effort
        log.warning("advisor.narrative_enrich_failed",
                    workflow_id=str(workflow_id), error=str(e))


@router.post("/workflows/{workflow_id}/advisor/run", status_code=202)
async def run_advisor(
    background_tasks: BackgroundTasks,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Kick a workflow self-evaluation (async). Poll GET …/advisor for the result."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            "SELECT 1 FROM workflows WHERE workflow_id = $1", workflow_id,
        )
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    background_tasks.add_task(_run_and_store, workflow_id, x_enterprise_id)
    return {"status": "running"}


@router.get("/workflows/{workflow_id}/advisor")
async def get_advisor(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Latest advisor review for a workflow, or {status:'never_run'}."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT review_id, run_mode, model, overall_health,
                      findings, narrative, created_at
               FROM workflow_review
               WHERE workflow_id = $1
               ORDER BY created_at DESC
               LIMIT 1""",
            workflow_id,
        )
    if row is None:
        return {"status": "never_run"}

    findings = row["findings"]
    if isinstance(findings, str):
        try:
            findings = json.loads(findings)
        except (ValueError, TypeError):
            findings = []
    return {
        "status": "done",
        "review_id": str(row["review_id"]),
        "run_mode": row["run_mode"],
        "model": row["model"],
        "overall_health": float(row["overall_health"]) if row["overall_health"] is not None else None,
        "findings": findings,
        "narrative": row["narrative"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
