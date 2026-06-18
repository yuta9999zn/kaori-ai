"""Health check — liveness and readiness."""
import os

import httpx
from fastapi import APIRouter

from ..shared.db import get_pool

router = APIRouter()

# After the P-1 cutover, ai-orchestrator no longer talks to Ollama
# directly — the gateway does. Probe the gateway here; gateway
# readiness implies provider readiness from our perspective.
LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")


@router.get("/health")
async def health():
    return {"status": "ok", "service": "kaori-ai-orchestrator"}


@router.get("/health/ready")
async def readiness():
    checks: dict[str, str] = {}

    # DB
    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"

    # LLM gateway (replaces the old direct-Ollama probe)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{LLM_GATEWAY_URL}/health")
            checks["llm_gateway"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
    except Exception as exc:
        checks["llm_gateway"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"ready": all_ok, "checks": checks}
