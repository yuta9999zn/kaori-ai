"""
Kaori LLM Gateway — FastAPI service (Phase 1 P-1 scaffold).

The eventual home for ALL LLM dispatch — internal Qwen/Ollama,
external Claude/OpenAI, semantic cache, PII redaction, per-tenant
token budgets, decision audit. Today it's the contract surface +
stub provider so Phase 2 work can call POST /v1/infer while the real
plumbing lands incrementally.

Concrete migration plan (out of scope for this scaffold PR):
  1. Move PII redaction + provider clients out of
     ai-orchestrator/engine/llm_router.py into providers.py here.
  2. Wire a Redis-backed semantic cache before the provider call.
  3. Replace ai-orchestrator's llm_router with an HTTP shim that
     calls POST /v1/infer.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .db import init_db_pool, close_db_pool
from .errors import register_problem_handlers
from .log_context import LogContextMiddleware
from .router import router as v1_router
from .router_guardrails import router as guardrails_router
from .tracing import configure_structlog_with_trace, setup_tracing

# Phase 2 #2/#5 — structlog with trace_id/span_id enrichment.
configure_structlog_with_trace("kaori-llm-gateway")

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("kaori.llm_gateway.starting")
    await init_db_pool()
    yield
    log.info("kaori.llm_gateway.stopping")
    await close_db_pool()


app = FastAPI(
    title="Kaori LLM Gateway",
    description="Centralized LLM dispatch (P-1 scaffold).",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Phase 2 #2/#5 — OpenTelemetry to Tempo. llm-gateway has no Kafka in
# the dependency tree, so we skip the aiokafka instrumentor.
setup_tracing("kaori-llm-gateway", app, instrument_kafka=False)

# P1-S1 (OBS-012 / K-19) — bind gateway-trusted X-* headers into structlog
# scope so every log line carries tenant_id / user_id / role / session_id.
app.add_middleware(LogContextMiddleware)

Instrumentator().instrument(app).expose(app)

register_problem_handlers(app)

app.include_router(v1_router, tags=["Inference"])
app.include_router(guardrails_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kaori-llm-gateway"}
