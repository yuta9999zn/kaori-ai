"""
adoption-intel — Phase 2 extract skeleton.

Phase 1 + 1.5 code lives in ai-orchestrator/org_intel/adoption (signals.py,
health_score.py). This module exists so the Helm chart, service registry,
and CI smoke build target can already reference services/adoption-intel/.
The /health endpoint lets a build pipeline assert the image runs without
wiring the real adoption-intel surface today.

DO NOT add real route handlers here until the Phase 2 extract starts —
duplicating logic across two services would create drift.
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Kaori Adoption Intel (skeleton)",
    version="0.0.1-skeleton",
    docs_url="/docs",
    redoc_url=None,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "adoption-intel",
        "phase": "skeleton",
        "code_location_today": "ai-orchestrator/org_intel/adoption",
    }
