"""Analyze router — POST /analyze"""
import json
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from datetime import datetime, timezone

from ..shared.db import acquire_for_tenant
from ..shared.event_bus import event_bus
from ..shared.kafka_producer import emit

router = APIRouter()


class AnalyzeRequest(BaseModel):
    run_id: UUID
    templates: list[str]
    config: dict = {}
    consent_external_ai: bool = False


@router.post("")
async def trigger_analysis(
    req: AnalyzeRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """
    Create an analysis_run (multi-template batch) and emit pipeline.silver.complete
    so the ai-orchestrator picks it up.

    Validation: UUID-typed inputs return 422 on malformed values.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        run = await conn.fetchrow(
            "SELECT status FROM pipeline_runs WHERE run_id=$1 AND enterprise_id=$2",
            req.run_id, x_enterprise_id,
        )
        if not run or run["status"] not in ("silver_complete", "analysis_complete"):
            raise HTTPException(400, "Run must be in silver_complete status")

        row = await conn.fetchrow(
            """INSERT INTO analysis_runs
               (enterprise_id, run_id, templates, config)
               VALUES ($1, $2, $3, $4::jsonb)
               RETURNING id""",
            x_enterprise_id,
            req.run_id,
            req.templates,
            json.dumps(req.config),
        )
        analysis_run_id = str(row["id"])

    # NB: pipeline_runs.status stays at 'silver_complete' while the
    # ai-orchestrator template_runner executes; orchestrator flips it to
    # 'analysis_complete' on success. Adding an 'analysis_running' state
    # would require a chk_pipeline_status migration — out of scope here.
    event_bus.publish(req.run_id, {
        "run_id":          str(req.run_id),
        "status":          "silver_complete",
        "analysis_run_id": analysis_run_id,
        "updated_at":      datetime.now(timezone.utc).isoformat(),
    })

    # Topic constant from kafka_topics (G2). UUID payload fields are
    # converted to str so the JSON serializer in send_event doesn't choke
    # on the UUID type — Batch 1 introduced the wrap; keep it after rebase.
    from ..shared import kafka_topics
    await emit(kafka_topics.PIPELINE_SILVER_COMPLETE, {
        "run_id": str(req.run_id),
        "enterprise_id": str(x_enterprise_id),
        "analysis_run_id": analysis_run_id,
        "consent_external_ai": req.consent_external_ai,
    })

    return {"run_id": str(req.run_id), "analysis_run_id": analysis_run_id}
