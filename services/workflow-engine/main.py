"""
workflow-engine — Phase 2 extract skeleton.

Phase 1 + 1.5 code lives in ai-orchestrator/workflow_runtime/ (temporal_client,
worker, activities, workflows, side_effect, idempotency). This module exists
so the Helm chart, service registry, and CI smoke build target can already
reference services/workflow-engine/. The /health endpoint lets a build
pipeline assert the image runs without wiring the real engine surface today.

Phase 2 extract per ADR-0010 — workflow-engine becomes the single Temporal
worker host + admin endpoints (DLQ, retry, force-cancel) for ops UI.

DO NOT add real route handlers here until the Phase 2 extract starts —
duplicating logic across two services would create drift.
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Kaori Workflow Engine (skeleton)",
    version="0.0.1-skeleton",
    docs_url="/docs",
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "workflow-engine",
        "phase": "skeleton",
        "code_location_today": "ai-orchestrator/workflow_runtime",
    }
