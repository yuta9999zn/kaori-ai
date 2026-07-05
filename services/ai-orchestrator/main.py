"""
Kaori AI Orchestrator — FastAPI service
Handles analysis execution, strategy frameworks, dashboard aggregation,
and AI-powered insights. Consumes pipeline events from Kafka.

K-3: All LLM calls route through engine/llm_router.py
K-10: Framework selection is deterministic — 1 question = 1 framework
"""
import asyncio
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .shared import db as db_module
from .shared import kafka_producer as kp
from .shared.db import init_db_pool, close_db_pool
from .shared.errors import register_problem_handlers
from .shared.kafka_producer import init_kafka, close_kafka
from .shared.outbox import OutboxPublisher
from .shared.log_context import LogContextMiddleware
from .shared.tracing import configure_structlog_with_trace, setup_tracing
from .consumers.pipeline_consumer import start_pipeline_consumer, stop_pipeline_consumer
from .routers import analytics, strategy, dashboard, health, decisions, reports, frameworks, north_star, multi_tier, explainability, economics, rag, adoption, process_mining, cdfl, workflow_from_cdfl, workflow_builder, workflow_documents, workflow_advisor, document_repository, document_templates, approval_rbac, contracts, corporate_tree, role_templates, enterprise_users, customers_vendors, temporal_health, admin_reconcile, industry_bootstrap, industry_compare, compliance_risk, compliance_model_card, incidents
from .chat import router as chat_router
from .agents import router as agents_router
from .workflow_runtime.worker import run_worker as run_temporal_worker
from .reasoning.trace_distiller.runner import run_distiller_loop

# Phase 2 #2/#5 — structlog with trace_id/span_id enrichment. MUST run
# before the first ``structlog.get_logger()`` call so the configured
# pipeline takes effect on every logger in this process.
configure_structlog_with_trace("kaori-ai-orchestrator")

log = structlog.get_logger()

_outbox_publisher: OutboxPublisher | None = None
_temporal_stop_event: asyncio.Event | None = None
_distiller_stop_event: asyncio.Event | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _outbox_publisher, _temporal_stop_event, _distiller_stop_event
    log.info("kaori.orchestrator.starting")
    await init_db_pool()
    await init_kafka()
    _outbox_publisher = OutboxPublisher(db_module.get_pool(), kp._producer)
    await _outbox_publisher.start()
    consumer_task = asyncio.create_task(start_pipeline_consumer())
    # P15-S9 D3 — Temporal worker. No-op when TEMPORAL_ENABLE_WORKER not
    # truthy (default Phase 1.5 — opt-in until cluster verified stable).
    _temporal_stop_event = asyncio.Event()
    temporal_task = asyncio.create_task(run_temporal_worker(_temporal_stop_event))
    # P2-S21 D4 — TraceDistillerWorker poll loop. No-op when
    # TRACE_DISTILLER_ENABLED not truthy. Reads decision_audit_log →
    # T-Cube distill → Memory L4 PROCEDURAL on a schedule (default 5min).
    _distiller_stop_event = asyncio.Event()
    distiller_task = asyncio.create_task(run_distiller_loop(_distiller_stop_event))
    yield
    log.info("kaori.orchestrator.stopping")
    if _distiller_stop_event is not None:
        _distiller_stop_event.set()
    try:
        await asyncio.wait_for(distiller_task, timeout=10.0)
    except asyncio.TimeoutError:
        log.warning("trace_distiller.shutdown_timeout")
        distiller_task.cancel()
    except Exception:
        log.exception("trace_distiller.shutdown_error")
    if _temporal_stop_event is not None:
        _temporal_stop_event.set()
    try:
        await asyncio.wait_for(temporal_task, timeout=10.0)
    except asyncio.TimeoutError:
        log.warning("temporal.worker.shutdown_timeout")
        temporal_task.cancel()
    except Exception:
        log.exception("temporal.worker.shutdown_error")
    await stop_pipeline_consumer()
    consumer_task.cancel()
    if _outbox_publisher is not None:
        await _outbox_publisher.stop()
    await close_kafka()
    await close_db_pool()


app = FastAPI(
    title="Kaori AI Orchestrator",
    description="Analysis execution, strategy frameworks, dashboard, insights",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Phase 2 #2/#5 — wire OpenTelemetry: OTLP exporter to Tempo + auto-
# instrumentation on FastAPI/asyncpg/aiokafka/httpx. Must run AFTER the
# FastAPI app is constructed (instrumentor needs the app handle) and
# BEFORE the first request comes in.
setup_tracing("kaori-ai-orchestrator", app)

# P1-S1 (OBS-012 / K-19) — bind gateway-trusted X-* headers into structlog
# scope so every log line carries tenant_id / user_id / role / session_id.
# Mount AFTER setup_tracing so trace_id is already populated when middleware
# runs (FastAPIInstrumentor wraps the app first).
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

app.include_router(health.router)
app.include_router(temporal_health.router, tags=["Health"])
app.include_router(admin_reconcile.router, tags=["Admin"])
# Mount routers WITHOUT /api/v1 prefix so the service can be tested directly
# (no gateway needed) and so the gateway's rewrite filter
#   /api/v1/(.*) → /$1
# lands at the right path. Previously these were mounted at /api/v1/analytics
# and /api/v1, which double-prefixed the path after the gateway rewrite
# (gateway sent /analytics/runs/X but the orchestrator listened at
# /api/v1/analytics/runs/X) → every orchestrator endpoint returned 404 to
# the frontend.
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(strategy.router,                       tags=["Strategy & AI"])
app.include_router(dashboard.router,                      tags=["Dashboard & Insights"])
app.include_router(industry_compare.router,               tags=["Industry Compare (RAG)"])
# F-029 — AI Decision Log (read-only over decision_audit_log).
app.include_router(decisions.router, prefix="/decisions", tags=["Decisions"])
# Sprint 8 — Conversational Layer (P2 + P1 chat tool registry).
# Two endpoints under /chat: /chat/enterprise/stream and /chat/platform/stream.
app.include_router(chat_router.router, prefix="/chat", tags=["Chat"])
# F-038 — Reports (auto LLM-generated, structured output via Issue #3).
# Three endpoints under /reports: POST /generate, GET /, GET /{id}.
app.include_router(reports.router, tags=["Reports"])
# F-034 — Analysis Frameworks (SWOT / 6W / 2H / Fishbone). Uses the
# same Issue #3 output_schema layer as reports; built-in templates
# live in services/ai-orchestrator/frameworks/templates.py.
app.include_router(frameworks.router, tags=["Frameworks"])
# F-060 — North Star tile + per-customer is_actioned toggle. Reads
# the canonical column on gold_features (migration 018 pre-baked it
# + migration 032 added the audit user). Closes CLAUDE.md §14.
app.include_router(north_star.router, tags=["North Star"])
# P15-S9 D7 — ROI Dashboard (Operational Economics / NOV). Mounted under
# /economics/*; gateway rewrite /api/v1/economics/... → /economics/....
# Reads nov_monthly_digests (migration 043); writes are the
# nov_monthly_digest Temporal workflow's job.
app.include_router(economics.router, tags=["Operational Economics"])
# F-033 — Multi-tier Analysis (PR A: basic + intermediate). Mounted
# under /analysis/* — gateway rewrite /api/v1/analysis/... → /analysis/...
# Coexists with /analytics/* (the wizard runner endpoint) — different
# prefix, different table-write strategy, same underlying analysis_runs
# table (post-migration 036).
app.include_router(multi_tier.router, tags=["Multi-tier Analysis"])
# F-061 — Agent Framework (Planner/Executor/Critic loop). Mounted under
# /shared/agents/* — gateway rewrite /api/v1/shared/agents/... →
# /shared/agents/.... v0 ships ONE workflow (insight-to-action) end-to-end;
# follow-up PRs add the other two pre-built workflows + FE wiring.
app.include_router(agents_router.router, tags=["Agents"])
# F-041 — Explainability (top-3 factors + Vietnamese narrative for any
# decision_audit_log row). LLM-derived from the audit fields — no
# real SHAP today (model-object persistence is Phase 3 work).
app.include_router(explainability.router, tags=["Explainability"])
# P15-S10 D6 — RAG Router. Mounted under /rag/* (gateway rewrite
# /api/v1/rag/... → /rag/...). Wraps reasoning/rag/router.py 3-engine
# dispatch (pgvector / pageindex / docsage). DocSage stub today;
# PageIndex stub today; pgvector is the real path.
app.include_router(rag.router, tags=["RAG"])
# P15-S10 D3 + D4 — Adoption interventions. Mounted under /adoption/*.
# Captures the baseline + resolves channel/gate plan; long-running
# 14-day + 30-day evaluation is the Temporal workflow's job (not yet
# triggered from this endpoint — workflow stub lands when worker is
# enabled in prod).
app.include_router(adoption.router, tags=["Adoption"])
# P15-S11 Tuần 4 — Process Mining /mine endpoint. Runs HeuristicMiner over
# inline events. Build Week demo entry point: FE uploads event log, BE
# renders direct_follows graph on Process Mining canvas. Session-id-backed
# mode (load events from Bronze via data-pipeline) lands post-Build-Week.
app.include_router(process_mining.router, tags=["Process Mining"])
# P15-S11 Tuần 4 — CDFL Planner. Ranks next-action candidates by
# information gain over H-step Monte Carlo rollouts. Pure function:
# direct_follows + current_state → ranked top-K. Honest niche statement
# from luận văn surfaced in response so FE can position correctly.
app.include_router(cdfl.router, tags=["CDFL Planner"])
# P15-S11 Tuần 5 — Workflow YAML emitter. Pipes /cdfl/plan-next-action
# output → valid Temporal workflow YAML with K-17 side_effect_class +
# REL-012 compensation declared. Pure function; caller saves YAML.
app.include_router(workflow_from_cdfl.router, tags=["Workflow"])
# P15-S11 Tuần 8 — Workflow Builder CRUD (drag-drop FE backing store).
# Card model per anh's directive 2026-05-15: each node has title +
# note + hashtags + required_document_types + expected_mapping_template.
app.include_router(workflow_builder.router, tags=["Workflow Builder"])
app.include_router(workflow_documents.router, tags=["Workflow Documents (Tier-3)"])
app.include_router(workflow_advisor.router, tags=["Workflow Advisor (ADR-0040)"])
app.include_router(document_repository.router, tags=["Document Repository / DMS (ADR-0039)"])
app.include_router(document_templates.router, tags=["Document Templates & Pages (ADR-0042)"])
app.include_router(approval_rbac.router, tags=["Approval Chains & RBAC (Tier-3)"])
app.include_router(contracts.router, tags=["Contracts (Tier-3)"])
# P15-S11 Tuần 8 — Corporate hierarchy CRUD (mig 055/056). Endpoints for
# tập đoàn → mảng → công ty con → phòng ban tree. Anh's Vingroup-class
# question 2026-05-15 — workspace can model a full corporate group with
# 8 divisions × ~16 subsidiaries, each with branches + departments.
app.include_router(corporate_tree.router, tags=["Corporate Tree"])
# P15-S11 Hướng A — RBAC tĩnh (mig 061). Onboarding approval handler hits
# /departments/{id}/role-template?seniority_level= to derive the default
# role for the new employee. B (RBAC+ABAC+PDP) deferred to Phase 2.
app.include_router(role_templates.router, tags=["Role Templates"])
# Phase 2.8 D4 — Industry template + bootstrap (anh's 2026-05-20 spec:
# "chọn ngành → sinh phòng ban mẫu → sinh workflow mẫu → user chỉnh").
# 3 industries seeded (Retail / Finance / Generic SME); 5 còn lại
# (F&B / Logistics / Healthcare / Manufacturing / Education) seed khi
# customer đầu tiên thuộc industry đó ký.
app.include_router(industry_bootstrap.router, tags=["Industry Template"])
app.include_router(compliance_risk.router, tags=["Compliance (EU AI Act, ADR-0041)"])
app.include_router(compliance_model_card.router, tags=["Compliance (EU AI Act, ADR-0041)"])
# P15-S11 Hướng A — PATCH /enterprise-users/{id}/role for manager
# assignment + override + audit row. Same router will gain the
# onboarding approval hook once workflow runtime lands.
app.include_router(enterprise_users.router, tags=["Enterprise Users"])
# P15-S11 — customers + vendors + contracts (mig 062/063). Read-only
# today; CRUD lands when FE flows ask for it. Anh's request 2026-05-16
# split customer & vendor into separate datasets each with their own
# contract type vocab.
app.include_router(customers_vendors.router, tags=["Customers & Vendors"])
# P2-S15 SH-M56b-026 — Visual agent workflow builder palette.
# Curated subset of mig 068 node_type_catalog (28 of 45) grouped by
# use-case bucket (intake/reasoning/decision/action/output) for agent
# builder FE. Mounted at /shared/agents/studio/builder/palette.
from .routers import agents_studio_builder  # noqa: E402
app.include_router(agents_studio_builder.router, tags=["Agent Studio Builder"])
# P2-S16 — Workflow as Code. YAML import/export of workflows.
# /workflows/{id}/export.yaml + POST /workflows/import. Validates
# against mig 068 node_type_catalog at the boundary.
from .routers import workflow_yaml  # noqa: E402
app.include_router(workflow_yaml.router, tags=["Workflow YAML"])
# P2-S21 D5 P2-M212-001 — OKR framework (Objectives + Key Results).
# Mig 071 tables: okrs + key_results + workflow_okr_links.
# Mounted at /p2/strategy/okr.
from .routers import okr  # noqa: E402
app.include_router(okr.router, tags=["OKR"])
# P2-S16 — Multi-user workflow collaboration. Mig 072 tables:
# workflow_editors + workflow_comments + workflow_locks.
# 10 endpoints mounted under /workflows/{workflow_id}/* (editors,
# comments, lock — optimistic K-13 anti-IDOR pattern).
from .routers import workflow_collab  # noqa: E402
app.include_router(workflow_collab.router, tags=["Workflow Collaboration"])
# P2-S18 cross-cutting observability — OBS-018 anomaly detection +
# OBS-021 capacity planning + OBS-023 session replay (opt-in, mig 073).
# Mounted at /platform/observability/*.
from .routers import observability  # noqa: E402
app.include_router(observability.router, tags=["Observability"])
# P2-S25 — enterprise auth security: MFA TOTP + field-level encryption.
# Mig 074 tables: mfa_secrets + mfa_backup_codes + tenant_field_keys.
# Mounted at /p2/auth/{mfa,field-key}.
from .routers import auth_security  # noqa: E402
app.include_router(auth_security.router, tags=["Auth Security"])
# P2-S22 — LLM ops (MAX tier): catalog + tenant API keys + token
# monitoring + 90-day shadow upgrade tests. Mig 075. Dogfoods
# shared/crypto.py for API key encryption.
from .routers import llm_ops  # noqa: E402
app.include_router(llm_ops.router, tags=["LLM Operations"])

# SH-M59 ROI-Hybrid billing — +1.5% revenue saved add-on for ENT ROI
# opt-in tier, capped 20M/month, requires ≥3 months of data. Mig 077.
from .routers import roi_billing  # noqa: E402
app.include_router(roi_billing.router, tags=["ROI Billing"])

# P2-AUTH-001 SSO — Google + Microsoft OAuth 2.0. Mig 079.
# Pre-auth endpoints under /p2/auth/sso/* — no JWT required for
# /start + /callback. Internal /exchange-info gated by
# X-Internal-Service-Token (shared with auth-service Java).
from .routers import sso  # noqa: E402
app.include_router(sso.router, tags=["SSO"])

# Phase 2.7 P1 — lineage tracking endpoints. mig 097.
# GET /lineage/{kind}/{id}/upstream + /downstream
from .routers import lineage  # noqa: E402
app.include_router(lineage.router, tags=["Lineage"])

# Phase 2.7 P1 — DLQ recovery console for ops.
# /admin/dlq overview + per-source listings + retry/replay/requeue actions
from .routers import dlq_console  # noqa: E402
app.include_router(dlq_console.router, tags=["DLQ Console"])
app.include_router(incidents.router, tags=["Incidents (EU AI Act, ADR-0041)"])

# CR-0017 — Domain knowledge base ("kho tri thức ngành"). mig 106.
# Ingest tier-4 tenant knowledge + semantic search over global (tier 1-3) + own.
from .routers import knowledge_base  # noqa: E402
app.include_router(knowledge_base.router, tags=["Knowledge Base"])
