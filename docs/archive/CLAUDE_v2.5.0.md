# CLAUDE.md — Kaori AI Living Documentation

> **Version:** 2.5.0 | **Updated:** 2026-05-04
> **Source docs:** BRD v3.0 · PRD v5.0 · Feature Tree v3.0
> **Backlog:** `docs/BACKLOG.md` — phases, sprints, 92 functions, status

---

## 1. Product Overview

**Kaori AI** là SaaS B2B dùng AI biến dữ liệu kinh doanh thành quyết định — không cần data engineer. Tổ chức thành **6 portal**:

| Portal | Route | Users | Modules | Phase |
|--------|-------|-------|---------|-------|
| **P1** Platform Manager | `/p1` | Kaori staff (SUPER_ADMIN/ADMIN/SUPPORT) | 9 | 1 |
| **P2** Enterprise Portal | `/p2` | Khách hàng DN (MANAGER/OPERATOR/ANALYST/VIEWER) | 24 | 1–3 |
| **P3** Studio | `/p3` | Kaori Analyst + Enterprise Analyst được assign | 9 | 2 |
| **P4** Personal Portal | `/p4` | Freelancer / cá nhân | 10 | 2 |
| **Shared** System | `/shared`, `/mcp` | Backend services | 12 | 1–3 |
| **Billing** | `/billing` | Tất cả portal dùng chung | 3 | 1–3 |

**North Star Metric:** `SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)`

---

## 2. Tech Stack (PINNED)

### Phase 1 — Deployed Services
| Service | Technology | Port | Notes |
|---------|-----------|------|-------|
| API Gateway | Java Spring Cloud Gateway (Spring Boot 3.2.5) | 8080 | |
| Auth Service | Java Spring Boot + Spring Security 3.2.5 | 8091 | |
| Data Pipeline | Python FastAPI 0.111.0 | 8092 | |
| AI Orchestrator | Python FastAPI 0.111.0 | 8093 | |
| Notification Service | Python FastAPI | 8094 | F-NEW1 — SMTP sender; called via direct HTTP from auth-service (no Kafka topic yet) |
| LLM Gateway | Python FastAPI | 8095 | P-1 cutover — `ai-orchestrator/engine/llm_router.py` HTTP-POSTs every infer to `${LLM_GATEWAY_URL}/v1/infer`. Service runs in `docker-compose.yml`. Sprint 8 added `messages` + `tools` + `tool_choice` to `InferRequest` (chat tool-calling path; Ollama `/api/chat` for native Qwen 2.5 tool support). F-063 (External AI Gateway full feature set: provider keys store, per-provider quota/circuit-breaker, multi-model routing) remains a Phase 2 goal — but the K-3/K-4/K-5 enforcement boundary already sits at this hop |
| Conversational Layer | intra-process (Python, in `ai-orchestrator/chat/`) | — | Sprint 8 (F-NEW4) — `POST /api/v1/chat/{enterprise,platform}/stream` SSE. Curated tool registry (6 tools v0); AI never writes SQL (K-16). Standalone MCP server stays a Phase 2 goal |
| Frontend | Next.js 16 + TypeScript | 3000 | |
| PostgreSQL | 15 + pgvector | 5432 | |
| Redis | 7 | 6379 | |
| Kafka | Confluent 7.5.0 | 29092 | |
| Ollama / Qwen 2.5 | 14B default | 11434 | |

### Phase 2 — Additional Services (target)
| Service | Technology | Notes |
|---------|-----------|-------|
| Feature Store Online | Redis Cluster (sharded by tenant) | P99 <10ms |
| Feature Store Offline | ClickHouse | Columnar OLAP |
| Model Serving | Triton + vLLM | GPU autoscale |
| Workflow Engine | Temporal.io | 3-node cluster |
| Training Pipeline | Ray + PyTorch + sklearn | GPU on-demand |
| Model Registry | MLflow + PostgreSQL | |
| Knowledge Graph | Neo4j CE (pgvector fallback) | |
| MCP Server | Node.js | JSON-RPC 2.0 |

---

## 3. Project Structure

```
D:\Kaori System\
├── CLAUDE.md                          ← This file
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── README.md                      ← navigation index — read this first ★
│   ├── BACKLOG.md                     ← canonical 92-function catalog (status truth) ★
│   ├── PHASE1_CLOSEOUT_PLAN.md        ← active execution tracker (Phase 1 close-out) ★
│   ├── DEMO_RUNBOOK.md                ← pilot UAT script (anh-driven walkthrough)
│   ├── adr/                           ← Architecture Decision Records (append-only) ★ — read before changing top-level structure
│   ├── runbooks/                      ← operational playbooks (kafka lag, redis OOM, llm-gateway down, AI cost overrun)
│   ├── architecture/                  ← ARCHITECTURE_REVIEW · SCALE_PLAN · TARGET_ARCHITECTURE_1M
│   ├── specs/                         ← deep-dive contracts (read per-feature; e.g., CHAT_TOOL_REGISTRY, MEDALLION_CONTRACT)
│   ├── tasks/                         ← BACKEND_TASKS_PHASE · FRONTEND_TASKS_PHASE (per-group scope)
│   ├── archive/                       ← stale phase_*_execution trackers (history only — wrong F-IDs)
│   ├── product/                       ← BRD/PRD/Feature Tree source docs (.docx, .xlsx)
│   ├── uat/                           ← UAT scripts per feature (e.g., CHAT_PANEL.md)
│   └── api-specs/                     ← committed OpenAPI specs (refresh via scripts/dump_openapi.py)
├── services/                          ← each service has a service.yaml (owner, tier, SLO, deps)
│   ├── api-gateway/                   ← Java Spring Cloud Gateway (8080)
│   ├── auth-service/                  ← Java Spring Boot auth (8091)
│   ├── data-pipeline/                 ← Python FastAPI (8092)
│   ├── ai-orchestrator/               ← Python FastAPI LLM/analytics + Sprint 8 chat tool registry (8093)
│   ├── llm-gateway/                   ← Python FastAPI LLM gateway (P-1 cutover landed; F-063 features Phase 2)
│   └── notification-service/          ← Python FastAPI SMTP sender (8094, F-NEW1 — direct HTTP only, alert topic deferred)
├── frontend/                          ← Next.js TypeScript (3000)
│   ├── app/
│   │   ├── (auth)/                    ← login · forgot-password · reset-password
│   │   ├── (app)/                     ← /dashboard · /pipeline/new · /decisions · /settings
│   │   └── (platform)/                ← /platform · /workspaces · /admins
│   ├── components/
│   │   ├── pipeline/                  ← FileUploader · SchemaReview · CleaningReview · AnalysisConfig · ResultsDashboard
│   │   └── charts/                    ← chart-registry · FlexibleChart
│   ├── lib/api/client.ts              ← authApi · pipelineApi · analyticsApi · dashboardApi
│   └── mocks/                         ← MSW handlers (dev only)
├── infrastructure/
│   ├── postgres/migrations/           ← 001–007 SQL migrations
│   ├── kafka/topics.yml
│   └── ollama/Modelfile
├── config/
│   ├── language_dictionary.json       ← 28KB, 5-language column synonyms (VI/EN/JA/KO/ZH)
│   └── bank_rules.json
└── etl/ · utils/ · sql/               ← Legacy scripts (keep, reused by pipeline)
```

---

## 4. Critical Invariants (NEVER BREAK)

| # | Invariant | Why |
|---|-----------|-----|
| K-1 | Every SELECT filters `WHERE tenant_id = $1` (or `enterprise_id`) | Multi-tenant isolation |
| K-2 | Bronze tables append-only — no UPDATE/DELETE | Immutable source of truth |
| K-3 | All LLM calls via `llm_router.py` — never direct SDK | Cost governance + consent |
| K-4 | External AI only with `consent_external=True` flag | Privacy — Qwen is default |
| K-5 | PII redaction before any external API call | Email/phone/ID → `[redacted]` |
| K-6 | Decision audit log at every automated decision | `decision_audit_log` table |
| K-7 | JWT claims forwarded as X-* headers to all services | `enterprise_id`, `user_id`, `role` |
| K-8 | Idempotent pipeline runs — SHA-256 fingerprint | Same file = skip duplicate |
| K-9 | `NUMERIC(5,4)` for rates, `NUMERIC(14,4)` for money | Never FLOAT for precision |
| K-10 | 1 question = 1 analysis framework | Never parallel 5Why+SWOT |
| K-11 | Billing unit = `COUNT(DISTINCT customer_external_id)` per month | Chống split-batch gaming |
| K-12 | `tenant_id` never accepted via query string — JWT only | Chống IDOR |
| K-13 | Idempotency-Key header on all POST mutations (Redis TTL 24h) | Dedup safe retries |
| K-14 | Error format: RFC 7807 Problem Details (`application/problem+json`) | Consistent error handling |
| K-15 | MCP tool calls: authz check per tenant_id + audit log every call | Prevent cross-tenant data via MCP |
| K-16 | Chat tools (Sprint 8 conversational layer) NEVER accept tenant_id / user_id / workspace_id from arguments — JWT only via `ToolContext` | Same spirit as K-12, applied to LLM tool-calling. Registry refuses dispatch if forbidden keys present in `args` |

---

## 5. Data Flow

```
User uploads file
  ↓ POST /api/v1/upload → API Gateway (JWT auth, rate limit)
  ↓ data-pipeline:8092 → bronze/ingestor.py
      → SHA-256 check (K-8) → bronze_files + bronze_rows (K-2)
      → Kafka: kaori.ingest.bronze
  ↓ bronze/column_mapper.py (config/language_dictionary.json)
      → exact(1.0) → fuzzy(0.65–0.95) → LLM fallback(0.4–0.7)
      → decision_audit_log (K-6)
  ↓ User reviews schema → POST /schema/confirm
  ↓ silver/rule_catalog.py → cleaning rules → POST /clean/apply
      → silver_rows · Kafka: kaori.pipeline.events
  ↓ User selects templates → POST /analytics/runs
      → Kafka: kaori.pipeline.events (silver.complete)
  ↓ ai-orchestrator:8093
      → template_registry.py → runner.py (asyncio.gather)
      → llm_router.py (K-3, K-4, K-5) → Qwen OR external (after PII mask)
      → analysis_results (ChartBlock[] JSON)
      → Kafka: kaori.pipeline.events (analysis.complete)
  ↓ GET /analytics/runs/:id → Frontend ResultsDashboard
```

**Medallion Architecture:**
| Layer | Engine | Purpose |
|-------|--------|---------|
| Bronze | MinIO/S3 (Parquet) | Raw ingest · append-only · SHA-256 · replay |
| Silver | ClickHouse (columnar) | Cleaned · typed · PII-masked · partitioned by tenant+month |
| Gold | PostgreSQL MV + Redis | Feature engineering · aggregates · dashboard-optimized |

---

## 6. API Design Conventions

```
Base (Phase 1): /api/v1/...               (flat routing, legacy)
Base (Phase 2): /api/v2/{portal}/...      (domain-segmented, target)

Auth:        JWT RS256 in Authorization: Bearer header
Tenant:      Extracted from JWT claims — NEVER from query string (K-12)
Envelope:    { data, meta: { request_id, trace_id, server_time }, errors, warnings }
Errors:      RFC 7807 Problem Details (K-14)
Pagination:  cursor-based ?cursor=&limit= (max 500)
Idempotency: Idempotency-Key header on all POST mutations (K-13)
```

**Phase 2+ portal prefixes:**
- `P1 /api/v2/platform/` · `P2 /api/v2/enterprise/` · `P3 /api/v2/studio/`
- `P4 /api/v2/personal/` · `Shared /api/v2/shared/` · `Billing /api/v2/billing/`
- MCP: `/mcp/jsonrpc` (JSON-RPC 2.0 — not REST)

---

## 7. Kafka Topics

| Topic | Key | Partitions | Retention | Consumers |
|-------|-----|-----------|-----------|-----------|
| `kaori.ingest.bronze` | tenant_id | 24 | 7d | medallion-engine |
| `kaori.pipeline.events` | pipeline_id | 12 | 7d | analysis-service, kg-builder, audit |
| `kaori.decisions.log` | tenant_id | 24 | 90d | audit, explainability, decision-index |
| `kaori.feedback.actions` | tenant_id | 12 | 30d | feature-store-updater, retrain-trigger |
| `kaori.billing.events` | tenant_id | 12 | 90d | billing-aggregator, invoice-generator |
| `kaori.alerts.fire` | tenant_id | 6 | 7d | notification-dispatcher, audit |
| `kaori.dlq.*` | origin key | varies | 30d | manual replay, alerting |
| `kaori.audit.internal` | tenant_id | 12 | 2y | audit-service, compliance-exporter |

**DLQ:** 5 retries (1s→2s→4s→8s→16s) → `kaori.dlq.{topic}`. PagerDuty if depth >100, escalate CTO if >1000.

---

## 8. LLM Routing Logic

```
Rule 1: privacy_mode='strict'    → ALWAYS Qwen internal (reject if fail, no external fallback)
Rule 2: prompt has PII detected  → Qwen internal
Rule 3: task='embedding'         → BGE-M3 internal
Rule 4: task=insight/summarize   → Qwen 14B first, fallback GPT-4o if quality < threshold
Rule 5: task=complex reasoning   → Claude Sonnet / GPT-4o (after PII masking)
Rule 6: task=coding/SQL          → Claude Sonnet / GPT-4o
Rule 7: task=chat.* (Sprint 8)   → Qwen local ALWAYS in v0; chat agent
                                    passes consent_external=False even
                                    when tenant has opted in. Phase 2
                                    decision unlocks external chat with
                                    a separate `consent_external_chat` flag.
```

External calls: PII masking (`<EMAIL_1>`, `<PHONE_1>`, `<NAME_1>`) → Guardrails validation on input+output → unmasking on response.

**Issue #3 — Output validation (optional, opt-in per call).** When `InferRequest.output_schema` is set (JSONSchema 2020-12), the gateway:
1. Extracts JSON from the model's free-text completion (handles ` ```json ` fences, bare JSON, JSON nested in prose).
2. Validates against the schema.
3. **One repair round** on failure: re-prompts with the schema + the validation error + the bad completion, asks for "ONLY JSON". If the second attempt also fails → 502 `LLM.OUTPUT_VALIDATION_FAILED`.
4. Returns `output_validation: { was_repaired, attempts, parsed_json }` so the caller never has to `json.loads` themselves and the audit row carries `schema_repaired=true|false` for ops metrics.
Callers without `output_schema` get the legacy raw-string path unchanged.

---

## 9. Authorization Model

**Phase 1:** RBAC only (roles in JWT claims).
**Phase 2+:** RBAC + ABAC → Hybrid PDP returns `{ allow, reason, policy_id, missing_perms[] }`.

| Portal | Roles |
|--------|-------|
| P1 | `SUPER_ADMIN` (MFA required), `ADMIN`, `SUPPORT` |
| P2 | `MANAGER` (≥1 required per enterprise), `OPERATOR`, `ANALYST`, `VIEWER` |
| P3 | `STUDIO_ADMIN`, `STUDIO_ANALYST` (scoped per enterprise) |
| P4 | `PERSONAL_USER` (self only) |

---

## 10. Pricing Model (ROI-Hybrid v3)

| Plan | VND/month | Unique KH/month | Overage |
|------|-----------|----------------|---------|
| PILOT | 1,000,000 | 500 max | No — upgrade required |
| ENT BASIC | 2,000,000 | 1,000 | +500K / 1,000 thêm |
| ENT MID | 5,000,000 | 4,000 | +400K / 1,000 thêm |
| ENT MAX | 8,000,000 | 10,000 | +250K / 1,000 thêm |
| ENT ROI | 8M + 1.5% revenue saved (cap 20M) | 10,000+ | Opt-in: ENT MAX ≥3 tháng |

Billing unit: `COUNT(DISTINCT customer_external_id)` per enterprise per billing_month → `enterprise_monthly_billing`. See K-11.
Alert: ≥80% quota → email + in-app. ≥95% → extra alert + suggest upgrade.

---

## 11. Development Setup

```bash
# 1. Copy env
cp .env.example .env   # set POSTGRES_PASSWORD, JWT keys, SMTP_*

# 2. Start infrastructure
docker compose up postgres redis kafka zookeeper ollama -d

# 3. Pull Ollama model
docker exec kaori-ollama-1 ollama pull qwen2.5:14b

# 4. Start all services
docker compose up -d

# 5. Frontend dev (faster iteration)
cd frontend && npm install && npm run dev

# Dev MSW mock credentials
# Admin:  test@demo.com      / password123
# Locked: locked@test.com   (423 response)
# Error:  error@test.com    (401 response)
```

**Service URLs:**
- `localhost:3000` Frontend · `localhost:8080` API Gateway · `localhost:8082` Swagger
- `localhost:8085` Kafka UI · `localhost:3001` Grafana · `localhost:11434` Ollama

---

## 12. Adding New Features

**New analysis template:**
1. Add to `services/ai-orchestrator/analytics/template_registry.py`
2. Add frontend card in `frontend/components/pipeline/AnalysisConfig.tsx` (TEMPLATES array)
3. Add engine function in `services/ai-orchestrator/analytics/engines/`
4. Add result rendering in `ResultsDashboard.tsx`
5. Add MSW mock shape in `frontend/mocks/handlers/analytics.ts`
6. Add F-XXX entry to `docs/BACKLOG.md`

**New cleaning rule:**
1. Add function in `services/data-pipeline/silver/rule_catalog.py`
2. Register in `RULE_CATALOG` under appropriate category (UNIVERSAL/BY_TYPE/BY_PURPOSE/AI_DETECTED)
3. Frontend auto-discovers via `GET /clean/suggestions`

---

## 13. Engineering Tenets

1. **Dumb baseline first** — statistical before ML, rule-based before LLM
2. **Measure before optimize** — profile before adding indices
3. **Fail loud** — no silent exception swallowing; log + propagate
4. **Explicit over implicit** — always pass `tenant_id` explicitly (K-12)
5. **Privacy by default** — Qwen local unless user opts in (K-4)
6. **Decision traceability** — every automated decision logged with confidence + alternatives (K-6)
7. **Vietnamese business language** — avoid "ETL", "dtype", "inference" in UI copy
8. **Additive-only Kafka contracts** — add fields only, never remove or rename
9. **Immutable billing records** — `enterprise_monthly_billing` never deleted, only upserted

---

## 14. Phase Status

See **`docs/BACKLOG.md`** for full sprint-by-sprint breakdown.

| Phase | Functions | Done | Pending |
|-------|-----------|------|---------|
| Phase 1 (F-001–F-032) | 32 | **32 ✅** | 0 — **CLOSE-OUT COMPLETE 2026-04-27** + Sprint 7 polish (PRs #84–#87) |
| Phase 2 (F-033–F-068) | 36 | **11 ✅** (F-033 · F-034 · F-035 · F-036 · F-037 · F-038 · F-039 · F-040 · F-041 · F-060 · F-061) | 25 🔵 — Sprint 2.3 P3 Studio · Sprint 2.4 P4 Personal · Sprint 2.5 KG/AutoDB · Sprint 2.6 ROI/Guardrails/ExtAI (F-061 ✅) · Sprint 2.7 ABAC/Workflow/SSO |
| Phase 3 (F-069–F-092) | 24 | 0 | 24 🟣 |

**Sprint 7 — Pilot Polish (landed 2026-04-27, PRs #84 → #87, tagged `v1.1-pilot-ready`):**
- **PR A** (#84) — F-012 Platform Health endpoint (was Ghost, now real `/api/v1/platform/stats`); `/decisions` CSV export uses fetch+Blob (no JWT in URL — K-7 spirit); CLAUDE.md §2 corrected on `llm-gateway` (P-1 cutover landed, port 8095, K-3/K-4/K-5 boundary now sits at this hop).
- **PR B** (#85) — `notification-service` wired into `AuthService` (password reset) + `EnterpriseUserService.invite` (F-015 invite). Inline `JavaMailSender` HTML retired. Settings page Notifications card flipped from "Sắp ra mắt" placeholder to real `notification_email` toggle (column existed since migration 015 / F-016).
- **PR C** (#86) — Enterprise `(app)/` shell redesigned to match the platform shell (cream sidebar `#F5F1EA`, KaoriLockup, gold accent bar, hex-hardcoded → CSS vars). `/pipeline` row click → wizard detail (was no-op). Pipeline status terminology canonicalized to BE DB CHECK (`schema_review`/`analyzing`/`analysis_complete` — FE-only `_pending`/`_running`/`_done` aliases retired). `/platform/billing/overview` got an F-031 cron health card (3-tier OK/warn/critical, surfaces `last_aggregated_at` + `stale_enterprise_count`). Login mailto link → `/onboarding`.
- **PR D** (#87) — North Star manual `is_actioned` toggle on `/decisions` (migration 019 `decision_actions` side table, RLS, FK CASCADE; one row per decision; `POST /api/v1/decisions/{id}/action` UPSERT; checkbox column on FE). F-013 `/register` 2-step page (paste workspace key → admin credentials → land on /dashboard) — closes the manual-provisioning Phase 1 limitation. Originally shipped as `/onboarding`; renamed post-pilot when customers searched for "Đăng ký" rather than "Kích hoạt" (legacy URL redirects). Gateway `/auth/workspace/activate` added to PUBLIC_PATHS.

**Phase 1 close-out — landed 2026-04-27 (PRs #65 → #80):**
- **Sprint 0** — drift cleanup (PR #65)
- **Sprint 0.5** — P0 #4 RLS cutover (PR #66) + P0 #6 K-6 audit wire-up (PR #67) + status tick (PR #68). Both architecture-review P0s now closed.
- **Sprint 1** — F-016 Enterprise Settings (PR #69, Ghost fixed, K-4 enforced) + gitleaks workflow side-fix (PR #70) + F-022 Pipeline Run History bundled with F-NEW2 SSE status stream (PR #71)
- **Sprint 2** — F-029 AI Decision Log (PR #72, cursor + CSV BOM + 10k cap) + F-015 User & Role Management (PR #73, min-MANAGER guard)
- **Sprint 3** — F-031 Unique Billing Cron (PR #74, daily 02:00 ICT, 80%/95% alert flags, no email — Phase 2 F-037) + F-030 Subscription & Quota (PR #75, 3-tab page + alert banner + manual upgrade workflow)
- **Sprint 4-5** — F-032 Gold Layer (PR #80, migration 018, strict-canonical aggregator, 90d cutoff + 12m ceiling, idempotent upsert, Kafka consumer with DLQ; `is_actioned` workflow reserved for Phase 2 F-060)
- **Sprint 6** — sign-off: `scripts/audit-ghost-features.py` (0 unallowlisted Ghost), `docs/DEMO_RUNBOOK.md` (pilot UAT script), this status update; release tagged `v1.0-phase1-complete`

**Phase 2 Sprint 2.1 close-out — landed 2026-05-04 (5 features):**

Phase 2 Sprint 2.1 ("Multi-tier Analysis + Frameworks") + Sprint 2.2 ("Reports + Risk + Strategy") closed end-to-end. 10 of the 36 Phase-2 functions ship. Migrations 028 → 036 added; 14 new Kafka topic schemas; ai-orchestrator pytest suite at 381/381 (was 207 before Phase 2).

| F-ID | Feature | Status | Highlights |
|---|---|---|---|
| F-033 | Multi-tier Analysis | ✅ PR A + B + C + D | Migration 036 extends `analysis_runs` (tier/scope/framework/source_ids/workspace_ids/consent_external/approval cols). 5 endpoints `/api/v1/analysis/*` + `POST .../runs/{id}/approve` (MANAGER role gate). Basic delegates to wizard runner; intermediate uses F-034 framework templates with multi-source label context; advanced dispatches to llm-gateway external path with `requires_approval` gated on `tenant_settings.consent_external_ai`. Real external-AI quota counter from `decision_audit_log`. Multi-workspace memberships deferred to PR D when `enterprise_users.UNIQUE(enterprise_id, email)` can be relaxed. |
| F-034 | Analysis Frameworks (SWOT / 6W / 2H / Fishbone) | ✅ | Migration 030 + Python registry + `/api/v1/frameworks/{generate,list,detail,templates}` + Issue #3 output_schema validation + 4 wired FE pages. |
| F-035 | Cohort Retention | ✅ | Engine + RHeatmap chart + 8 unit tests already shipped Phase 1; Phase 2 surfaced via F-033 basic-tier picker + MSW heatmap fixture + UAT script. No dedicated FE page (basic-tier picker covers it). |
| F-036 | Decision Override | ✅ | Migration 031 + `/decisions/{id}/override[/{oid}/revoke]` + Kafka emit `kaori.feedback.actions` + wired `/p2/decisions/[id]` detail page. |
| F-037 | Alert Rules | ✅ | Migration 028 + `BillingAlertService` quota dispatcher + `notification_outbox` integration + `/p2/alerts` page (events + rules tabs, MANAGER role gate). |
| F-038 | Reports (auto-generate) | ✅ + Distribution | Migration 027 + 029 + `POST /reports/generate` (202 + bg worker via Issue #3) + `kaori.reports.generated` Kafka + `report-ready` outbox email + distribution recipients form. Builder + template library still pending. |
| F-039 | Risk Management | ✅ | Migration 033 + 034 (category enum) + auto-computed score (likelihood × impact) + severity tier via DB trigger + 5×5 heat map FE. Auto-detect from data deferred. |
| F-040 | Strategy Builder OKR | ✅ | Migration 035 + `/p2/strategy/okr` editor (Objective + Key Results tree). Gantt timeline view + review-meeting templates pending. |
| F-041 | Explainability Layer | ✅ | `services/ai-orchestrator/explainability/` + `POST /api/v1/explainability/explain` via Issue #3 output_schema (top_factors[] direction/weight/evidence + narrative + confidence_explanation) + lazy section in `/p2/decisions/[id]` page. **"Lite" framing**: explanation grounded in audit-row fields, NOT real SHAP. Model-object persistence (real SHAP) deferred to F-073 once F-046 model registry ships; response shape is forward-compatible. |
| F-060 | is_actioned Workflow / Customer At-Risk | ✅ | Migration 032 + `/p2/customers/at-risk` page bundles North Star tile + filterable table + per-row toggle. Closes CLAUDE.md §14 North Star limitation end-to-end. |

**Hardening rails fully amortised** (originated late Phase 1, used by every Phase-2 feature above):
- **Issue #3 output_schema validation** — F-034, F-038, F-041 all use `llm_router.complete_structured(output_schema=…)` with one-shot repair on the gateway side.
- **Issue #4 Kafka schema registry** — `kaori.feedback.actions` (F-036), `kaori.reports.generated` (F-038), `kaori.analysis.tier.{started,completed}` (F-033) all validate before producing.
- **Issue #6 notification_outbox** — `report-ready` (F-038), `quota-alert` (F-037) all enqueue + dispatch through the same outbox dispatcher.
- **RLS NOBYPASSRLS cutover** — every new repository module relies on `acquire_for_tenant` GUC; `# tenant-filter-lint: allow` annotations document the RLS path.

**Sprint 2.1 limitations (intentionally deferred, tracked):**
- **F-033 multi-workspace memberships (PR D follow-up)** — Phase 1 `enterprise_users` is `UNIQUE(enterprise_id, email)`. Adding `user_workspace_memberships` join table lets one user span multiple workspaces; cross-workspace cohort engine then reads it. Deferred until pilot tenant explicitly requests cross-workspace analytics.
- **F-041 real SHAP** — needs persisted fitted model objects + the feature row that was scored. Phase 3 work alongside F-046 model registry / F-073 finetune. Endpoint shape is compatible with the swap.
- **F-038 builder + template library + scheduler** — auto-generate path proven; pilot can request bespoke shapes per report. Schedule in Sprint 2.6 if customer feedback warrants.
- **F-039 auto-detect risks from data** — manual CRUD wired; auto-detection from anomaly engine deferred to Sprint 2.5 alongside knowledge graph.

**Sprint 8 — Conversational Layer v0 (landed 2026-04-29, branch `feat/sprint-8-pr-a-chat-backend`):**
Inspired by `congdinh2008/chatbot-ai-mcp-demo` (MCP tool-calling pattern), adapted to multi-tenant Kaori (RLS-aware, JWT-bound tenant_id, K-15 audit). Three sub-PRs landed back-to-back on one branch:
- **PR A — Backend tool registry.** New module `services/ai-orchestrator/chat/` (registry · agent · 6 curated tools = 3 P2 + 3 P1). Endpoints `POST /chat/{enterprise,platform}/stream` (SSE). Extended `llm-gateway` `InferRequest`/`InferResponse` with `messages`/`tools`/`tool_calls`/`finish_reason`. Ollama `/api/chat` provider for native Qwen 2.5 tool calling; Anthropic + OpenAI tool format conversion. K-12 + K-16 enforced (registry refuses tenant identifiers in args). K-15 audit row per enterprise tool dispatch. +57 tests, full ai-orchestrator suite at 264/264.
- **PR B — Frontend ChatPanel.** Right-side drawer (cream + gold), one mount per portal shell (`AppShell` for P2, `platform/layout.tsx` for P1 with role gate `SUPER_ADMIN/ADMIN/SUPPORT`). `useChatStream` hook uses `fetch` + ReadableStream because EventSource is GET-only. ToolCallCard shows ✔/✖ + collapsible args/preview so users can audit what the assistant looked at. MSW handler for both scopes (deterministic 4-event fixtures, no Ollama needed in dev). `tsc --noEmit` + `next build` clean.
- **PR C — Docs + UAT + backlog.** This entry · §4 K-16 · §8 Rule 7 · `docs/specs/CHAT_TOOL_REGISTRY.md` · `docs/uat/CHAT_PANEL.md` · `docs/BACKLOG.md` F-NEW4 row · `docs/DEMO_RUNBOOK.md` chat demo step.

**Phase 1 limitations after Sprint 7 (still deferred to Phase 2):**
- ~~**North Star half-closed**~~ → **Closed end-to-end by F-060 (BE PR #124 + FE this PR)** — `gold_features.is_actioned` (pre-baked in migration 018) is now the canonical column. Migration 032 adds `actioned_by_user` for audit. Endpoints: `POST /api/v1/customers/{external_id}/action` (toggle + Kafka emit `customer.actioned`/`unactioned`), `GET /api/v1/dashboard/north-star` (canonical formula tile: `SUM(revenue_at_risk WHERE is_actioned=true AND revenue_at_risk > 0)` — `revenue_at_risk > 0` is the v0 proxy for `churn_risk_label='HIGH'` until F-051 explicit classifier ships), `GET /api/v1/customers/at-risk` (cursor list). FE: new `/p2/customers/at-risk` page bundles the tile + filterable customer table + per-row toggle. Sprint 7 PR D's `decision_actions` side table stays for the per-decision `/decisions` toggle (different surface). F-036 override Kafka feedback continues to fire on disagreements.
- ~~**Quota alert email copy**~~ → **Closed by F-037 (`feat/alerts-f037-backend`)** — `BillingAggregationService` now calls `BillingAlertService.dispatchOnAggregate(...)` after each upsert. On first 80%/95% crossing per month (cooldown 6h via `alert_events`), a `quota-alert` row is enqueued in `notification_outbox` with per-tier upsell context. `templates/quota_alert.html` ships per-plan copy (PILOT → ENT_BASIC upsell, ENT_BASIC → MID, MID → MAX, MAX → ROI). Implicit defaults use stable sentinel rule_ids (`...0080`, `...0095`); custom rules go through `/api/v1/enterprises/alerts` CRUD (MANAGER-only). FE `/p2/alerts` page is the next follow-up (FE-EU-237).
- **F-027 chart picker** — render is intentionally client-side (`frontend/components/charts/chart-registry.tsx`); no `/api/v1/charts/render` endpoint by design.

**Closed in Sprint 7 (no longer limitations):**
- ~~F-013 Onboarding wizard FE not implemented~~ → `/register` 2-step page live (PR D / #87; renamed from `/onboarding` post-pilot, legacy URL redirects).
- ~~Email dispatch deferred for password-reset + F-015 invite~~ → `notification-service` wired (PR B / #85). Quota alerts still on the deferred list.
- ~~F-012 Platform Health Dashboard is Ghost~~ → real `/api/v1/platform/stats` endpoint (PR A / #84).
- ~~CSV export leaks JWT in URL~~ → fetch + Blob pattern (PR A / #84).

**Recently completed (2026-04-26 — Batch 1):**
- **F-008** Workspace deep CRUD — added GET-by-id, members CRUD, billing summary, audit log subroutes (auth-service migration 011 adds `workspace_audit_log`).
- **F-010** Platform admin management — full CRUD + invite + reset-password (auth-service migration 011 adds `platform_admins`, `platform_admin_password_resets`).
- Frontend: 9 screens added under `/platform/workspaces/[id]/*` and `/platform/admins/*`. Folder renamed `app/(platform)/` → `app/platform/` so URLs match the documented `/platform/*` pattern (route group dropped the prefix).

**Recently completed (2026-04-26 — Batch 2):**
- **F-009** Private Key Management — nested `/platform/workspaces/{id}/keys` endpoints (additive; flat `/platform/keys` retained for `AuthService.activateWorkspace`). New `WorkspaceKeyService` reuses `PlatformKeyService` for hashing/rate-limit. Frontend page at `/platform/workspaces/[id]/keys`.
- **F-011** Billing Monitor — platform-level aggregation: `/platform/billing/{overview,quota,enterprises/{id},export}`. New `BillingMath` shared by F-008 + F-011. CSV export with **UTF-8 BOM** for Vietnamese Excel compat. 4 frontend pages.
- **Module 3 — TOTP MFA + active sessions (deepens F-007)** — `POST /security/mfa/{enable,verify}` (RFC 6238 SHA-1, 30s, 6-digit, ±1 step skew; AES-256-GCM encrypted at rest), `GET/DELETE /security/sessions[/{id}]`. Migration 012 adds `mfa_secret_enc` column + `admin_sessions` table. Frontend pages at `/platform/security/{mfa,sessions}`.
- Tests: **322 backend tests** (was 207 before Batch 2 — +115 new), 0 failures. 25 frontend routes registered. `tsc --noEmit` + `next build` clean.

**Recently completed (2026-04-26 — Phase 3, Hardening + Productization of Batch 2):**

| Slice | What landed | Tests added |
|---|---|---|
| **3.1.a** Platform admin login + session lifecycle | `POST /auth/platform/{login,refresh}` against `platform_admins`; admin_sessions row created on login; `session_id` in JWT (`token_kind=platform`); `last_active_at` touched per-request via Redis-throttled validator (60s); idle (30 min) + absolute (24 h) timeouts auto-revoke from the auth filter and short-circuit with RFC 7807 401. Migration 013 adds `revoke_reason`. | +37 |
| **3.1.b** MFA rate limit + audit log | 5 failed `/security/mfa/verify` per 15 min per admin → 423 RFC 7807 with `lockout_remaining_seconds`. New `platform_admin_audit_log` table (migration 014) + nullable `actor_id` on `workspace_audit_log`. All MFA + session events emit audit rows with IP (`admin.mfa.{initiated,enabled,verified,verify_failed}` + `admin.session.revoked` with reason: manual/logout/idle_timeout/absolute_timeout/manual_bulk). Audit writes are best-effort (REQUIRES_NEW + try/catch swallow). | +7 |
| **3.1.c** MFA key management | `KAORI_MFA_KEY` wired into `.env.example` + `docker-compose.yml`. Auth-service refuses to start in production profile when key is missing. `scripts/generate-mfa-key.sh` for one-line generation. See §15 below for rotation procedure. | +6 |
| **3.2.a** Flyway migration runner | `flyway-core` added to auth-service. Single source of truth: SQL files stay in `infrastructure/postgres/migrations/`, copied into JAR classpath at build time via Maven `<resource>`. Baselines existing schema at v14; future migrations 015+ apply automatically on app startup. Separate Flyway DB user (`kaori`) so the runtime `kaori_app` keeps SELECT/INSERT/UPDATE-only. | +3 (1 cold-boot Docker-gated) |
| **3.2.b** API gateway routing | Consolidated `/api/v1/platform/**` catch-all (covers admins/billing/security/workspaces/keys). Filter forwards `X-Session-Id` from JWT for platform tokens only; enforces `token_kind=platform` on platform paths in addition to role gate. All 401/403 short-circuits return RFC 7807 `application/problem+json`. WARN log on token_kind mismatch for forensics. | +7 (gateway) |
| **3.3** Polish + CI | `POST /security/sessions/revoke-others` bulk endpoint (keeps caller's current session). Frontend MFA page replaces placeholder with real QR (`qrcode` lib, canvas render — secret never enters URL bar). Sessions page gets "Revoke all other sessions" button + confirm modal. `lib/api.ts` reads RFC 7807 fields. Existing `.github/workflows/ci.yml` already covers `mvn verify` + `npm run typecheck` + `next build`. | +10 |

**Phase 3 totals:** **auth-service 385 / 385** (was 207 before Batch 2 — +178 net), **api-gateway 45 / 45** (was 39 — +6), frontend `tsc` + `next build` clean. Migrations 011-014 baselined by Flyway; future schema changes flow through the JVM-side runner.

**Deferred (intentionally out of scope, tracked):**
- **MFA enforcement at login (2-step `mfa_challenge_token` flow)** — `mfa_enabled` flag is informational only today. The product team flagged this for the next phase pending validation feedback.
- **Monitoring / metrics** — WARN logs on rate-limit hits + token_kind mismatches give grep-able starting points; Grafana panels haven't been built. Flagged as a next-phase item.
- **Audit feed UI at `/platform/security/audit`** — repo + service support cursor pagination; no FE consumer yet.
- **Session creation hook for enterprise users** — only platform admins get session tracking today. Enterprise auth flow is unchanged.

---

## 15. MFA Key Management

**Purpose.** `KAORI_MFA_KEY` is the AES-256 master key that encrypts platform admin TOTP secrets at rest. The encrypted ciphertext lives in `platform_admins.mfa_secret_enc` (Base64 of `IV(12B) || GCM-ciphertext`). Without this key, the auth-service cannot decrypt stored secrets to validate 6-digit codes — every admin would fail MFA verification.

**Format.** Base64 encoding of exactly **32 random bytes** (AES-256). Anything else is rejected at startup:

| Input | Behaviour |
|---|---|
| Unset, profile NOT production | WARN log + deterministic dev key (acceptable for local + tests only) |
| Unset, profile = `prod` / `production` | Fail-fast `IllegalStateException` at startup — service refuses to boot |
| Set, length ≠ 32 bytes | Fail-fast `IllegalStateException` regardless of profile |
| Set, length = 32 bytes | OK, used for AES-256-GCM encrypt/decrypt |

**Generation.**
```bash
# One-shot — writes to .env in place:
./scripts/generate-mfa-key.sh

# Or manually:
openssl rand -base64 32
```

**Storage.** Inject as the `KAORI_MFA_KEY` env var. In `docker-compose.yml` it flows into auth-service's environment block. In production, source it from a secret manager (HashiCorp Vault, AWS Secrets Manager, k8s secret). Never commit to git, never log, never echo in CI output.

**Rotation procedure (v1 — disruptive).**

The current implementation supports a single key — rotating it invalidates every previously stored TOTP secret. Recovery requires every admin to re-enrol. Run this only when:

1. Suspected key compromise (former staff with secret-manager access, leaked log, etc.)
2. Annual hygiene rotation per your org's policy

Steps:
```
1. Email all platform admins ≥48h ahead: "MFA reset on YYYY-MM-DD HH:MM UTC. You'll be asked to re-scan your QR code at next login."
2. T-0:
   a. Generate new key:           ./scripts/generate-mfa-key.sh --force
   b. Force re-enrol on all rows: UPDATE platform_admins SET mfa_secret_enc=NULL, mfa_enabled=false;
   c. Restart auth-service so it picks up the new key.
3. Each admin's next sign-in shows the "MFA disabled, please re-enable" UI prompt → /platform/security/mfa.
4. Confirm re-enrolment count in platform_admin_audit_log:
   SELECT COUNT(*) FROM platform_admin_audit_log
    WHERE event_type = 'admin.mfa.enabled' AND created_at > '<rotation_time>';
```

**Rotation procedure (v2 — zero-disruption, NOT yet implemented).**

The roadmap path is dual-key support: `KAORI_MFA_KEY_ACTIVE` (encrypts new) + `KAORI_MFA_KEY_PREVIOUS` (decrypts old). On every successful verify, re-encrypt the secret with the active key. After the 24h absolute-session window, retire the previous key. Worth implementing only when a quarterly rotation cadence is required — for v1 the disruptive flow is acceptable given platform admin count is small (single-digit at launch).

**Operational checklist before flipping `SPRING_PROFILES_ACTIVE=production`.**

- [ ] `KAORI_MFA_KEY` set in env (32-byte Base64)
- [ ] Backup of current `platform_admins.mfa_secret_enc` taken (in case of key loss)
- [ ] Secret-manager access logged + restricted to ops on-call rotation
- [ ] Runbook entry pointing to this section + the rotation script

---

*Architecture deep-dives → `docs/` folder*
*Full feature catalog (986 leaves) → Feature Tree v3.0 at `D:\Kaori Document\`*
