"""
Kaori Data Pipeline — FastAPI service
Wraps existing ETL scripts (etl/ingest.py, utils/excel_parser.py)
and exposes them as REST endpoints with Bronze/Silver/Gold layers.
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

# Add parent dir to path so we can import existing etl/ and utils/
sys.path.insert(0, "/app")

from .data_plane.gold.consumer import start_gold_consumer, stop_gold_consumer
from .routers import (
    upload, schema, clean, analyze, results, health,
    enterprise_pipelines, data_explorer, process_mining,
)
from .shared import db as db_module
from .shared import kafka_producer as kp
from .shared.db import init_db_pool, close_db_pool
from .shared.errors import register_problem_handlers
from .shared.kafka_producer import init_kafka, close_kafka
from .shared.outbox import OutboxPublisher
from .shared.log_context import LogContextMiddleware
from .shared.tracing import configure_structlog_with_trace, setup_tracing

# Phase 2 #2/#5 — structlog with trace_id/span_id enrichment. MUST run
# before the first ``structlog.get_logger()`` call.
configure_structlog_with_trace("kaori-data-pipeline")

log = structlog.get_logger()

_outbox_publisher: OutboxPublisher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _outbox_publisher
    log.info("kaori.pipeline.starting")
    await init_db_pool()
    await init_kafka()
    # G5: outbox relay — polls event_outbox and ships rows to Kafka.
    # Same lifecycle as the producer so it shares the connection pool
    # and the kafka producer instance.
    _outbox_publisher = OutboxPublisher(db_module.get_pool(), kp._producer)
    await _outbox_publisher.start()
    # F-032: Gold aggregator consumer — listens for silver.complete and
    # rebuilds the per-customer feature table. asyncio.create_task so the
    # consumer loop runs alongside FastAPI's request handling.
    consumer_task = asyncio.create_task(start_gold_consumer())
    yield
    log.info("kaori.pipeline.stopping")
    await stop_gold_consumer()
    consumer_task.cancel()
    if _outbox_publisher is not None:
        await _outbox_publisher.stop()
    await close_kafka()
    await close_db_pool()


app = FastAPI(
    title="Kaori Data Pipeline",
    description="File upload, column detection, data cleaning, and analysis pipeline",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Phase 2 #2/#5 — OpenTelemetry exporter to Tempo + auto-instrument
# FastAPI/asyncpg/aiokafka/httpx.
setup_tracing("kaori-data-pipeline", app)

# P1-S1 (OBS-012 / K-19) — bind gateway-trusted X-* headers into structlog
# scope so every log line carries tenant_id / user_id / role / session_id.
# Mount AFTER setup_tracing so trace_id is already populated.
app.add_middleware(LogContextMiddleware)

# CORS — disabled; the API gateway handles browser CORS. Adding `*` here
# made the gateway reflect both `*` and the configured origin in
# Access-Control-Allow-Origin, which browsers reject ("contains multiple
# values"). This service is reachable only via the gateway from outside
# the docker network, so no preflight ever lands here directly.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

Instrumentator().instrument(app).expose(app)

# K-14: RFC 7807 error envelope on every error path.
register_problem_handlers(app)

# Routers
app.include_router(health.router)
app.include_router(upload.router,  prefix="/upload",  tags=["Bronze — Upload"])
app.include_router(schema.router,  prefix="/schema",  tags=["Canonical — Schema"])
app.include_router(clean.router,   prefix="/clean",   tags=["Silver — Cleaning"])
app.include_router(analyze.router, prefix="/analyze", tags=["Gold — Analysis"])
app.include_router(results.router, prefix="/results", tags=["Results"])
# F-022 + F-NEW2 — pipeline run history + SSE status stream.
app.include_router(enterprise_pipelines.router, prefix="/pipelines", tags=["Pipelines"])
# F-NEW3 — Data Explorer hub overview (Phase 2).
app.include_router(data_explorer.router, prefix="/data", tags=["Data Explorer"])
# P15-S10 D1 + D2 — Process Mining metadata connectors (Gmail/Outlook +
# Calendar). Registration endpoints validate config + return session
# handle; long-running polling lives in Temporal worker.
app.include_router(process_mining.router, tags=["Process Mining"])
