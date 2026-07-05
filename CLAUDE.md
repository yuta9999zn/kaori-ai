# CLAUDE.md — Kaori AI Living Documentation

> **Version:** 4.0.4 | **Updated:** 2026-06-04 — **EU AI Act compliance landed** (ADR-0041, trust-first/conformity-ready): invariants **K-22..K-26** added to §4 (K-22 risk classification · K-23 human oversight · K-24 transparency disclosure · K-26 post-market monitoring + bias examination Art 10; **K-25 model card shipped 2026-06-06** — mig **137** `ai_model_card` + `/compliance/model-cards*` + `model_card_completeness`). Migs **134** `ai_use_risk_register` · **135** `workflow_approvals.gate_kind` · **136** `ai_incident` · **137** `ai_model_card`. Shipped via PRs #347–#352 (incl. #352 CI-fix: tenant-filter + stale test + openapi/FE drift — **regen specs with fastapi 0.136.3**, the version CI's combined install resolves to). Framework doc: `D:\Tài liệu dự án\6.1_EU_AI_Act_Compliance_Framework.md`.
> **Version:** 4.0.3 | **Updated:** 2026-06-01 (mig ledger refreshed 117→129: Tier-3 docs/contracts/approvals + node-catalog landed; schema-drift gate made deterministic across calendar months — partition children excluded, snapshot rebuilt). K-21 added 2026-05-23 — UUIDv7 internal + ULID external hybrid, ADR-0029, mig 104, shared/ids.py.
>
> **NNL-Harness + n8n landing (2026-05-27/28):** brought 3 NNL capabilities + n8n's workflow data-model into Kaori, all multi-tenant + additive (engine untouched). **ADR-0030** memory trust (decay/verify/reinforce) · **ADR-0032** memory palace (consolidate + associative recall + experience-by-age maturation) · **ADR-0033** foundational KB aging + version-history + CDFL **\|OR\|** coverage gate ("học 1 hiểu 10": enough foundational knowledge → generalise, else decline — no hallucination, K-3) · **ADR-0034** workflow item-envelope `[{json,binary,pairedItem}]` + declarative `config_schema`/`ui_schema`→builder UI + node `type_version` (K-20 for nodes) · **ADR-0035** workflow typed connection ports (`port_type` main/ai_tool/ai_memory/ai_model — runner topo-sorts only `main`; `NodeContext.connections` wires agent tools/memory/model) + trigger nodes (`is_trigger`). Also data-pipeline robustness (encoding-detect / ratio-sniff / locale-money). Code: `reasoning/{memory,knowledge}/`, `workflow_runtime/{items.py,runner.py}`. **No hardcode** — knowledge from DB, thresholds env-configurable (`KAORI_MEM_*` / `KAORI_KB_*`).
>
> **Migration ledger (2026-06-01):** max number **129** (126 .sql files; gaps 77/78/79 SSO renumber + 104 K-21 sorts before 105). Added since 105: 106 knowledge_documents · 107 knowledge_seed_retail_sme · 108 platform_ai_config · 109 wire_ai_config_knobs · **110 memory_trust_columns** · **111 knowledge_aging_versioning** · **112 node_type_ui_schema** · **113 node_type_version** · **114 workflow_typed_ports_triggers** · **115 workflow_bpmn_xml** (builder pivot → bpmn-js; `workflows.bpmn_xml TEXT` nullable) · **116 workflow_bpmn_node_metadata** (workflow_nodes pool_name/lane_name/bpmn_type/event_definition/attached_to_ref + workflow_edges flow_kind/is_default — BPMN→nodes sync) · **117 workflow_node_executor_key_alignment** (rename kaori_node_type→`node_type_catalog_key`, fix latent runner schema mismatch — runner aliases real config/condition cols). **Tier-3 docs/contracts/approvals + node-catalog epic (ADR-0037), added since 117:** **118 ai_config_kb_promote_knobs** · **119 workflow_doc_requirements** · **120 workflow_doc_instance_lifecycle** · **121 approval_chains** · **122 approval_chain_wiring_delegations** · **123 user_department_roles** · **124 contracts** (contracts/contract_parties/contract_signatures + e-sign) · **125 node_catalog_contract** · **126 abac_dept_restrictive** · **127 approval_gate_chain_binding** · **128 node_catalog_loop** · **129 node_type_loop_constraint**. Later: **130-133** (ADR-0039/0040 DMS + advisor + doc-analysis + embeddings) · **134-137** (EU AI Act, ADR-0041) · **138** document_doc_date (business date) · **139 document_type_templates** (ADR-0042 Confluence-style DMS: doc-type blueprints + folder-as-page `body_md`/`sample_file_id`/`page_version` + `document_folder_version` history + typed `metadata` JSONB + `labels` GIN + `document_collection_insight`; seeds 5 global templates). All 118-139 are K-21-compliant (`gen_uuid_v7()` PK / `gen_ulid()` external) + additive/nullable — low cutover cost. Gaps 77/78/79 (SSO renumber). ⚠️ K-21's `104` sorts before `105` in Flyway (independent — no ordering break). Running pilot DB is a deliberately lean subset: canonical through ~mig 084 + industry templates (101-104); migs **085-100 stubbed** (`skip phase2 DDL`); migs 106-129 are additive (new tables/columns + 1 rename, nullable defaults — low cutover cost). Full map + cutover impact → `docs/runbooks/pilot-db-state.md`. **CI `schema_snapshot.txt` now excludes date-rolling partition children (`*_YYYY_MM`) so the `migration-test` drift gate is deterministic across calendar months — regen with `python scripts/schema-drift.py --write` after any migration.**
>
> **Pointers (đọc on-demand khi cần):**
> - `docs/SPRINT_HISTORY.md` — toàn bộ §14 (Phase 1 → 2.8 Round 5 commit hash + test deltas + waves)
> - `docs/STRUCTURE.md` — cây thư mục đầy đủ
> - `docs/MODULE_MAP.md` — §14a/14b/14c module map (P15-S10 endpoints + P2-S15 follow-up + P2.5 MinerU)
> - `docs/HOWTO.md` — §12 Adding New Features
> - `docs/architecture/EVENT_BACKBONE.md` — §7 Kafka topics + Redis Streams chi tiết
>
> **Source-of-truth docs:** `docs/strategic/` (5 docs converted from Feature Tree v4.0 + Playbook + Pipeline + Reasoning + Workflow + SAD v2)
> **Backlog:** `docs/BACKLOG_V4.md` — 36 sprints, ~1147 features, status truth
> **Architecture:** `docs/strategic/SAD_SKELETON_V2.md` — kiến trúc tổng thể v4
> **FE specs:** `docs/specs/UI_SCREENS_INVENTORY.md` (77 screens) · `docs/specs/MESSAGE_DEFINITIONS.md` · `docs/specs/VALIDATION_RULES.md`
> **Migration path:** `docs/RESTRUCTURE_PROPOSAL.md`
> **Snapshot v2.5.0:** `docs/archive/CLAUDE_v2.5.0.md` (history only)

---

## 1. Product Overview

**Kaori AI** là SaaS B2B dùng AI biến dữ liệu kinh doanh thành quyết định — không cần data engineer. v4 mở rộng phạm vi qua **24 tháng × 36 sprint × 1147 features**, tổ chức 4 audience × 6 portal:

| Audience | Portal | Route | Users | Phase entry |
|---|---|---|---|---|
| **Platform** | P1 Platform Manager | `/platform` | Kaori staff (SUPER_ADMIN/ADMIN/SUPPORT/CSM) | P1 |
| **Enterprise** | P2 Enterprise Portal | `/p2` | Khách DN (MANAGER/OPERATOR/ANALYST/VIEWER) | P1-P3 |
| **Studio** | P3 Studio | `/p3` | Kaori Analyst + Enterprise Analyst assigned | P2 |
| **Personal** | P4 Personal Portal | `/p4` | Freelancer / cá nhân | P2 |
| **Shared** | P5 Shared Infrastructure | `/shared` | Backend services + cross-cutting admin | P1-P3 |
| **Billing** | P6 Billing | `/billing` | Financial ops + invoice generation | P1-P3 |

**North Star Metric:** `SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)` (định nghĩa giữ từ v3; F-060 đã ship FE/BE end-to-end Phase 2 Sprint 2.1).

**4 Phase roadmap (24 tháng):**

| Phase | Months | Sprint | Theme | Acceptance |
|---|---|---|---|---|
| **Phase 1 — Foundation** | M1-M4 | 8 (P1-S1..S8) | Modular monolith MVP, 10-15 khách đầu | ≥10 khách, workflow ≥99.5%, 0 cross-tenant leak, NOV positive ≥3 |
| **Phase 1.5 — Stabilization** | M5-M6 | 4 (P15-S9..S12) | Critical gaps + 90-day testing infra | 10-15 active, NPS >30, full 9 adoption signals |
| **Phase 2 — Differentiation** | M7-M12 | 12 (P2-S13..S24) | Moat (Process Mining full + Adoption + NOV A/B), microservices extraction | 100 khách, SOC 2 Type 1, 99.9% uptime |
| **Phase 3 — Platform** | Year 2 | 12 (P3-S25..S36) | Multi-region, marketplace, self-hosted LLM, ecosystem | 1000 khách, SOC 2 Type 2 + ISO 27001 |

Chi tiết feature từng sprint: `docs/BACKLOG_V4.md`.

---

## 2. Tech Stack (PINNED)

### Phase 1 v4 (đang chạy + skeleton mới)

| Service | Technology | Port | State |
|---|---|---|---|
| API Gateway | Java Spring Cloud Gateway (Spring Boot 3.2.5, Java 21 pom / Java 25 base image) | 8080 | ✅ chạy (ADR-0010); SB 4.x + Java 25 pom Phase 3 (ADR-0027) |
| Auth Service | Java Spring Boot + Spring Security 3.2.5 (Java 21) | 8091 | ✅ chạy (MFA + sessions Phase 3 hardening); SB 4.x + Java 25 Phase 3 (ADR-0027) |
| Data Pipeline | Python FastAPI 0.111.0 | 8092 | ✅ chạy — Phase B internal split `ingestion/` · `data_plane/` · `quality/` |
| AI Orchestrator | Python FastAPI 0.111.0 | 8093 | ✅ chạy — Phase B internal split `reasoning/` · `workflow_runtime/` · `org_intel/` |
| LLM Gateway | Python FastAPI | 8095 | ✅ chạy (output_schema validation, tool calling); ADR-0015 Qwen-first |
| Notification Service | Python FastAPI | 8094 | ✅ chạy (SMTP outbox); Phase 2 thêm Zalo Bot |
| Process Mining / Adoption / Economics / Workflow Engine | (Phase 3 extract — decision 2026-05-18 update ADR-0010) | TBD | 🔵 module sống trong `ai-orchestrator/` Phase 1-2 |
| Frontend | Next.js 16 + TypeScript | 3000 | ⏸ **TẠM DỪNG** — anh restructure FE template trước |

### Infrastructure (Phase 1 đã có / Phase 1.5 mới)

| Component | State | Notes |
|---|---|---|
| PostgreSQL 15 + pgvector | ✅ chạy | RLS multi-tenancy cutover (ADR-0013); 136 mig files (max 139) tại 2026-07-05 (134-137 EU AI Act; 138 doc_date; 139 ADR-0042 doc templates) |
| Redis 7 | ✅ chạy | cache + idempotency 24h + rate limit; Redis Streams (ADR-0017) |
| Kafka Confluent 7.5 | ✅ chạy | topic v3 legacy; Phase 2 mở rộng |
| Ollama / Qwen 2.5 14B | ✅ chạy | **default LLM cho mọi tenant** + BGE-M3 embedding + Qwen2-VL OCR (ADR-0015) |
| MinIO distributed | 🔵 P1-S3 | Bronze object storage |
| ClickHouse 3-node | 🔵 P15-S10 (infra-gated) | Silver tier columnar + OTel trace + NOV time-series (ADR-0012) |
| HashiCorp Vault HA | ✅ wired Phase 1.5+ | secrets per-tenant path (K-18) |
| Temporal cluster | 🔵 worker code ready, gated `TEMPORAL_ENABLE_WORKER=true` | workflow orchestrator (ADR-0011) |
| OpenTelemetry + Jaeger + Prometheus + Loki + Sentry | 🔵 P1-S2 | OTel SDK mọi service, tenant_id mandatory span (K-19); Python pin 1.28.2 + instrumentation 0.49b2 Phase 1-2, forward-sync 1.40 + 0.51b2 Phase 3 (ADR-0028) |
| Kubernetes 1.28 (FPT Cloud HCM) | 🔵 P15-S9 (infra-gated) | DEFER tới Phase 1.5 (ADR-0016) |
| Pinecone managed (vector RAG) | 🔵 P15+ | Qdrant fallback cho data residency strict |

Trạng thái: ✅ chạy · 🔵 skeleton hoặc planned · ⏸ paused · ❌ deprecated.

---

## 3. Project Structure

Cây thư mục đầy đủ → `docs/STRUCTURE.md`. Tóm tắt top-level:

```
D:\Kaori System\
├── services/{api-gateway,auth-service,data-pipeline,ai-orchestrator,llm-gateway,notification-service}/
├── frontend/                ← Next.js 16 (PAUSED)
├── infrastructure/{postgres,kafka,redis,ollama,temporal,clickhouse,minio,vault,otel,prometheus,loki,grafana,k8s}/
├── docs/{strategic,adr,specs,ba,runbooks,api-specs,sprint,uat,archive}/
├── scripts/                 ← OpenAPI regen + governance checks
└── config/ · etl/ · utils/ · sql/  ← legacy scripts kept
```

---

## 4. Critical Invariants (NEVER BREAK)

| # | Invariant | Why |
|---|---|---|
| K-1 | Every SELECT filters `WHERE tenant_id = $1` (or `enterprise_id`); RLS enforced via `acquire_for_tenant` GUC | Multi-tenant isolation (ADR-0013) |
| K-2 | Bronze tables append-only — no UPDATE/DELETE | Immutable source of truth |
| K-3 | All LLM calls via `llm-gateway` — never direct SDK | Cost governance + consent + drift |
| K-4 | External AI only with `consent_external=True` flag — **Qwen is default** (ADR-0015). Per-call `prefer_external=True` opt-in còn cần thêm. `data_residency_strict=true` tenant override consent — luôn Qwen. **OCR + embedding endpoints REFUSE consent_external entirely** (no field in OcrRequest / EmbedRequest, schema-level pin via tests) — image bytes + raw text carry PII byte-level redaction can't strip; vendor vision / vendor embed = Phase 3 + separate ADR. | Privacy + cost — vendor adapter pluggable nhưng không tự ý dùng |
| K-5 | PII redaction before any external API call | Email/phone/ID/name → `[redacted]` (Vietnamese-aware Phase 1.5) |
| K-6 | Decision audit log at every automated decision | `decision_audit_log` table |
| K-7 | JWT claims forwarded as X-* headers to all services | `enterprise_id`, `user_id`, `role`, `tenant_id` |
| K-8 | Idempotent pipeline runs — SHA-256 fingerprint | Same file = skip duplicate |
| K-9 | `NUMERIC(5,4)` for rates, `NUMERIC(14,4)` for money | Never FLOAT for precision |
| K-10 | 1 question = 1 primary analysis framework, optional secondary | Đổi từ "1 framework only" v3 — v4 cho phép multi-framework qua `P2-M26-043` |
| K-11 | Billing unit = `COUNT(DISTINCT customer_external_id)` per month | Chống split-batch gaming |
| K-12 | `tenant_id` never accepted via query string / body / header — JWT only | Chống IDOR |
| K-13 | Idempotency-Key header on all POST mutations (Redis TTL 24h API-layer) + per-node `idempotency_records` Postgres table (TTL 7d) cho workflow node | Dedup safe retries (ADR-0014) |
| K-14 | Error format: RFC 7807 Problem Details (`application/problem+json`) | Consistent error handling |
| K-15 | MCP tool calls: authz check per tenant_id + audit log every call | Prevent cross-tenant data via MCP |
| K-16 | Chat tools NEVER accept tenant_id / user_id / workspace_id from arguments — JWT-only via `ToolContext` | Same spirit as K-12, applied to LLM tool-calling |
| **K-17** | Workflow YAML — every node MUST declare `side_effect_class` ∈ `{pure, read_only, write_idempotent, write_non_idempotent, external}` | Ép retry policy + saga compensation đúng (ADR-0014) |
| **K-18** | Phase 1.5+ — Vault is the only secret store; no env-var secrets in production profile | Centralised rotation + audit per access |
| **K-19** | OpenTelemetry mandatory; every span MUST carry attribute `tenant_id` | Cross-tenant trace search + leak detection (ADR-0013) |
| **K-20** | LLM version pinning per workflow (`model: claude-sonnet-4-6`, `version: "2026-01-01"`); no silent vendor upgrade | Drift control + reproducibility (ADR-0015) |
| **K-21** | New tables Phase 2.9+ → `DEFAULT gen_uuid_v7()` (not `gen_random_uuid()`). External-facing public IDs → `TEXT(26) DEFAULT gen_ulid()`. Existing UUIDv4 columns untouched (no data migration). Mirror in app layer: `services/ai-orchestrator/shared/ids.py`. | B-tree locality + URL-friendly externals (ADR-0029) |
| **K-22** | EU AI Act risk classification — every registered AI-use/workflow carries a `risk_tier ∈ {prohibited, high, limited, minimal}` (`ai_use_risk_register`, mig 134). `prohibited` is blocked at publish + run (RFC 7807 `COMPLIANCE.PROHIBITED_USE`); `high` auto-enables the controls below. Classify via `POST /compliance/ai-uses`. | EU AI Act Art 5/9 (ADR-0041) |
| **K-23** | EU AI Act human oversight — a `risk_tier=high` workflow MUST get human sign-off before the runner executes any node with `side_effect_class ∈ {write_non_idempotent, external}`: pause `eu_ai_act_oversight` (`workflow_approvals.gate_kind`, mig 135) → **approve** (resume) or **stop** (`POST /workflow-runs/{id}/stop` = cancel + saga compensation). | EU AI Act Art 14 (ADR-0041) |
| **K-24** | EU AI Act transparency — every generative AI output carries a machine-readable disclosure at the K-3 chokepoint (`InferResponse.disclosure` = `{generated_by_ai, model, method, notice}`); the chatbot self-identifies via an SSE `disclosure` event. | EU AI Act Art 50 (ADR-0041) |
| **K-25** | EU AI Act technical documentation — an **Annex IV-lite model card** per `model + version` of the K-20 registry (`ai_model_card`, mig 137): intended purpose · capabilities · limitations · training-data summary · evaluation summary · risk mitigations. Authored/read via `/compliance/model-cards*`; a card's `completeness` (`reasoning/compliance_controls.py` `model_card_completeness`) tells whether the K-25 control a `risk_tier=high` use requires is satisfied. Trust-first (an incomplete card is recorded + flagged, not hard-blocked). | EU AI Act Art 11 (ADR-0041) |
| **K-26** | EU AI Act post-market monitoring — incident register (`ai_incident`, mig 136; `severity=serious` = Art 73-reportable) + monitoring summary at `/admin/incidents*`; **bias examination (Art 10)** runs in the Stage-4 quality gate (`bias` report on the scorecard — representativeness imbalance on sensitive/proxy attributes, env-configurable `KAORI_BIAS_*`). | EU AI Act Art 72/73 + Art 10 (ADR-0041) |

---

## 5. Data Flow (v4 — Pipeline Unified 12 stages)

Xem `docs/strategic/PIPELINE_UNIFIED.md` cho diagram đầy đủ. Tóm tắt:

```
Stage 1 Upload + Bronze         → MinIO immutable, SHA-256, K-2/K-8
Stage 2 Schema Detection        → multi-stage (exact → fuzzy → LLM fallback)
Stage 3 Cleaning → Silver       → 3-layer rules (Universal + Domain + AI), Parquet
Stage 4 Quality Scorecard (Gate)→ 7 dimensions, NUMERIC(5,4), per-tenant target
Stage 5 Semantic Enrichment     → 7-Primitives Ontology (Neo4j), master records, lifecycle
Stage 6 Knowledge Extraction    → unstructured (PDF/Word/audio), 10-stage parallel
Stage 7 Memory System           → 4-tier hierarchy, RAG read flow
Stage 8 Gold Layer              → views (not tables), per-dept customization
Stage 9 AI Decision Generation  → confidence-based action policy, decision_audit_log (K-6)
Stage 10 Reports                → Studio compose, fan-out delivery
Stage 11 Adoption + NOV         → 9 signals, revenue + cost + ROI manager-language
Stage 12 Loop                   → 60-day baseline + 90-day testing → replace/migrate
```

**Medallion Architecture (ADR-0012):**

| Layer | Engine | Purpose |
|---|---|---|
| Bronze | MinIO (Parquet) | Raw ingest, append-only, SHA-256, replay |
| Silver | ClickHouse (Phase 1.5+) | Cleaned, typed, PII-masked, partitioned by tenant+month. 8-step pipeline canonical: schema_validation → type_cast → null_handling → dedup → PII_masking_VN → normalize → outlier_flag → lineage_tag. 7-Dim quality gate ≥80% weighted avg trước promote Gold. |
| Gold | Postgres MV + Redis cache | Feature engineering, aggregates, dashboard-optimized |

---

## 6. API Design Conventions

```
Base (Phase 1 legacy):  /api/v1/...
Base (Phase 1 v4 new):  /api/v1/{platform,p2,p3,p4,shared,billing}/...
Phase 2+:               /api/v2/{portal}/... (target)

Auth:        JWT RS256 in Authorization: Bearer header
Tenant:      Extracted from JWT — NEVER from query/body/header (K-12)
Envelope:    { data, meta: { request_id, trace_id, server_time }, errors, warnings }
Errors:      RFC 7807 Problem Details (K-14)
Pagination:  cursor-based ?cursor=&limit= (max 500)
Idempotency: Idempotency-Key header on all POST mutations (K-13)
Tracing:     OpenTelemetry mandatory; tenant_id span attribute (K-19)
```

API catalog đầy đủ: `docs/API_CATALOG_V4.md` (~187 actual endpoints post-Round 5).

---

## 7. Event Backbone (ADR-0017)

Phase 1 hybrid: Kafka cho topic v3 legacy, Redis Streams cho event v4 mới. Topic table + DLQ recovery + naming convention → `docs/architecture/EVENT_BACKBONE.md`.

Phase 2.7 added `GET /admin/dlq` console (5-source unified — Kafka DLQ + Redis stream DLQ + workflow_run failed + workflow_idempotency_records expired + workflow_compensation logs).

---

## 8. LLM Routing Logic (ADR-0015 — Qwen-first, vendor pluggable opt-in)

```
DEFAULT (no consent / no opt-in):
  task=insight/summarize/reasoning/coding/SQL/chat.*  → Qwen 2.5 14B local
  task=embedding                                     → BGE-M3 local

OVERRIDES:
Rule 1: tenant.data_residency_strict=true            → ALWAYS Qwen (override consent)
Rule 2: prompt has PII detected (Vietnamese-aware)   → Qwen local (no external even if consent)
Rule 3: tenant.consent_external=true AND request.prefer_external=true
        → router thử vendor primary (Anthropic Claude / OpenAI GPT-4o / khác qua adapter), 
          fallback Qwen on vendor error
        → PII masking trước call vendor (K-5); unmask response
Rule 4: chat.* (Sprint 8 conversational layer)      → Qwen ALWAYS in v0
        → Phase 2 unlock với flag `consent_external_chat` riêng
Rule 5: vendor circuit breaker open                  → fallback Qwen, alert ops
```

**Pluggable adapter (`llm-gateway`):** OllamaAdapter (Qwen + BGE-M3, default) · AnthropicAdapter · OpenAIAdapter · (Phase 2 thêm Cohere/VertexAI/...). Mỗi adapter circuit breaker per provider + per-tenant token budget.

External calls: PII masking (`<EMAIL_1>`, `<PHONE_1>`, `<NAME_1>`) → Guardrails validation input+output → unmasking on response.

**Output validation (opt-in per call):** `InferRequest.output_schema` (JSONSchema 2020-12) → extract JSON from completion → validate → 1 repair round on fail → 502 `LLM.OUTPUT_VALIDATION_FAILED` if 2nd fail. Audit row carries `schema_repaired=true|false`.

**Phase 2.7 wiring:** `/v1/infer` charges `tenant_quota` (llm_tokens_external / llm_tokens_local) BEFORE provider invoke; 429 RFC 7807 on QuotaExceeded. `record_ai_call` writes `ai_decision_audit` row after every call (model_version + prompt_hash + output_hash + confidence + consent_external + pii_redacted + latency + cost).

---

## 9. Authorization Model

**Phase 1:** RBAC (roles trong JWT claims).
**Phase 2+:** RBAC + ABAC → Hybrid PDP returns `{ allow, reason, policy_id, missing_perms[] }`.
**Phase 2.9 (planned, CR-0012):** Permission Claims framework — 10 claim catalog với auto-grant logic (role-based + dept-based + temporary grants); 6 new NFR-SEC-15..20.

| Portal | Roles |
|---|---|
| P1 | `SUPER_ADMIN` (MFA required), `ADMIN`, `SUPPORT`, `CSM` |
| P2 | `MANAGER` (≥1 required), `OPERATOR`, `ANALYST`, `VIEWER` |
| P3 | `STUDIO_ADMIN`, `STUDIO_ANALYST` (alias STU-01) — per-enterprise scope |
| P4 | `PERSONAL_USER` (self only) |

---

## 10. Pricing Model (giữ ROI-Hybrid v3, expanded Phase 2)

| Plan | VND/month | Unique KH/month | Overage |
|---|---|---|---|
| PILOT | 1.000.000₫ | 500 max | No — upgrade required |
| ENT BASIC | 2.000.000₫ | 1.000 | +500K / 1.000 thêm |
| ENT MID | 5.000.000₫ | 4.000 | +400K / 1.000 thêm |
| ENT MAX | 8.000.000₫ | 10.000 | +250K / 1.000 thêm |
| ENT ROI | 8M + 1.5% revenue saved (cap 20M) | 10.000+ | Opt-in: ENT MAX ≥3 tháng |

Billing unit: `COUNT(DISTINCT customer_external_id)` per enterprise per billing_month → `enterprise_monthly_billing` (K-11). Quota matrix đầy đủ trong `docs/strategic/PLAYBOOK_90DAY.md` Phần 9.

---

## 11. Development Setup

```bash
# 1. Copy env
cp .env.example .env

# 2. Start infrastructure
docker compose up postgres redis kafka zookeeper ollama -d

# 3. Pull Ollama model (data_residency_strict + chat fallback)
docker exec kaori-ollama-1 ollama pull qwen2.5:14b
docker exec kaori-ollama-1 ollama pull bge-m3   # embedding

# 4. Start all services
docker compose up -d

# 5. Frontend dev (currently PAUSED for restructure)
# cd frontend && npm install && npm run dev
```

**Service URLs (Phase 1 đang chạy):**
- `localhost:3000` Frontend (paused) · `localhost:8080` API Gateway · `localhost:8082` Swagger
- `localhost:8085` Kafka UI · `localhost:3001` Grafana · `localhost:11434` Ollama

---

## 12. Adding New Features (v4-aware)

Quy trình chi tiết per feature kind (template / rule / node / connector / metric) + drift artefacts checklist → `docs/HOWTO.md`.

---

## 13. Engineering Tenets

1. **Dumb baseline first** — statistical → ML → LLM
2. **Measure before optimize** — profile + dashboard trước khi index
3. **Fail loud** — không silent except swallow; log + propagate
4. **Explicit over implicit** — `tenant_id` truyền tường minh (K-12)
5. **Privacy by default** — Qwen local default; vendor opt-in qua `consent_external=True` + per-call flag (K-4, ADR-0015)
6. **Decision traceability** — mỗi decision tự động log + confidence + alternatives (K-6)
7. **Vietnamese business language** — UI tránh "ETL", "dtype", "inference"
8. **Additive-only event contracts** — thêm field, không xóa/rename
9. **Immutable billing** — `enterprise_monthly_billing` upsert-only, không delete
10. **Side-effect class declaration** — mỗi workflow node tuyên bố class (K-17)
11. **Tenant_id is span attribute, not log line** — K-19; trace search by tenant
12. **Vault-only secrets Phase 1.5+** — K-18
13. **Per-item failure ≠ abort run** — degraded envelope + warning, not 5xx (Phase 2.5 pattern)

---

## 14. Phase Status (snapshot)

> Lịch sử commit hash, wave closeout, round polish, test deltas → **`docs/SPRINT_HISTORY.md`**.

| Phase | Status |
|---|---|
| **Phase 1** (M1-M4, 8 sprints) | ✅ COMPLETE 2026-05-08; tag `v4.0-phase1-complete` |
| **Phase 1.5** (M5-M6, 4 sprints) | ✅ COMPLETE 2026-05-17; ai-orch 514→1261 |
| **Phase 2** (M7-M12, 12 sprints) | 🟡 BE COMPLETE — S13/S14/S15/S16/S18/S21/**S22**/**S24**(retro)/S25 ship; S17 skip; S19/S20 defer Phase 3. Only open item: **S23 (English UI/i18n, 324 feat FE-heavy) gated on FE restructure** (§2) — Phase 2 closes when FE delivers i18n. |
| **Phase 2.5** ⭐ NEW (MinerU + AI catalog) | ✅ COMPLETE 2026-05-19 (10/10 BE; FE bbox highlight defer) |
| **Workflow Execution Closeout** | ✅ COMPLETE 2026-05-19 — registry 45/45 (100% catalog coverage); 25/25 templates LIVE |
| **Phase 2.6** (Orchestration Hardening) | ✅ 9/12 ship; 3 defer infra-gated (CDC / ClickHouse / Streaming) |
| **Phase 2.7** (Production-Readiness Governance) | ✅ 5/5 items + 4/4 producer-side wiring complete 2026-05-20 |
| **Phase 2.8** (Industry Template 3-tier + UX redesign) | ✅ Round 5 closeout 2026-05-21 EOD — 4-layer alignment (code ↔ UX spec ↔ FE Impl Spec v1.1 ↔ BA v2.1) |
| **Phase 3** (Year 2, 12 sprints) | ⏳ NOT STARTED |

**Branch state 2026-05-24:** `chore/uuid-v7-ulid-hybrid` ahead `main` 1 commit (bdcc50b, K-21). PR #179 (feat/p15-s9-d1, ~250 commits) MERGED 2026-05-22 — `main` is canonical. ai-orchestrator 2350+ tests, llm-gateway 210, data-pipeline 695 (counts from 2026-05-21 snapshot, not re-verified). Migrations: 134 .sql files (max 137 as of 2026-06-06; 104 = K-21 UUIDv7, 105 = admin-bypass RLS from pilot UAT, 118-129 = Tier-3 docs/contracts/approvals epic, 134-137 = EU AI Act K-22/K-23/K-26/K-25 — 137 = ai_model_card).

**Phase 2.8 = anh's "rõ vật thể" redesign — BE foundation + UX spec.** FE Workflow Library page (per-industry empty state + "Tạo workflow đầu tiên cho phòng Sales") đợi FE restructure resume per §2.

**2-file UX vs internal split:**
- `docs/sprint/feature-workflows.html` — INTERNAL CATALOG cho dev / AI agent audit. Đừng show cho khách.
- `docs/sprint/workflow-builder-ux.html` — SME UX MOCKUP cho FE team.
- `docs/sprint/feature-screens.html` — SCREEN INVENTORY (77 màn × 6 portals P1-P6).

**Module map** (P15-S10 endpoints + P2-S15 follow-up + P2.5 MinerU 9 modules) → **`docs/MODULE_MAP.md`**.

---

## 15. MFA + field encryption key management

### `KAORI_MFA_KEY` — platform-wide TOTP secret-encryption master

AES-256 master key encrypt platform admin TOTP secrets + (P2-S25 2026-05-17 add) enterprise user TOTP secrets via `services/ai-orchestrator/shared/totp.py`. Wire shape `base64(IV(12B) || GCM_ciphertext(secret(20B)))` compatible với auth-service Java `TotpService`.

Rotation procedure + operational checklist xem `docs/archive/CLAUDE_v2.5.0.md` §15.

**Vault wiring (K-18, ship 2026-05-18):** `_platform_mfa_master_key()` reads from Vault path `platform/encryption/mfa_master_key` (expects `{"key": "<base64>"}`) before falling back to `KAORI_MFA_KEY` env var. Production profile (`KAORI_PROFILE=production`) refuses env fallback — Vault must resolve or the endpoint 500s. Dev/staging keep transparent fallback with a warning log.

### Tenant field-encryption keys (P2-S25, ship 2026-05-17)

`tenant_field_keys` table (mig 074) — one row per tenant carrying `key_ref`. **2026-05-18 K-18 wiring:** three formats handled by `resolve_tenant_key`:
- `vault:<path>` (production — reads via `KaoriVault.read_sync` expecting `{"key":"<b64>"}`)
- `inline:<b64>` (dev only — refused under `KAORI_PROFILE=production`)
- `""` (env fallback to `KAORI_FIELD_KEY` — dev only)

Rotate endpoint writes to `tenant/<id>/encryption/field_key_<timestamp>` in Vault under prod profile, returns `vault:<path>` for storage.

`services/ai-orchestrator/shared/crypto.py` provides:
- `encrypt_field(plaintext, WrappedKey)` / `decrypt_field(ciphertext_b64, WrappedKey)` — AES-256-GCM per-column
- `resolve_tenant_key(tenant_id, key_ref, vault_client=)` — Vault prod / inline / env var fallback
- `generate_key_b64()` — fresh 32-byte key for onboarding
- `POST /p2/auth/field-key/rotate` — bump version
- `POST /p2/auth/field-key/reencrypt[/status]` — F-NEW11 follow-up (mig 080, history table)

K-18 enforcement: production keys MUST live in Vault. Dev profile uses env var `KAORI_FIELD_KEY` or `inline:` prefix; module logs warning on dev fallback.

---

*Architecture deep-dive → `docs/strategic/SAD_SKELETON_V2.md`*
*Sprint backlog → `docs/BACKLOG_V4.md`*
*Sprint history → `docs/SPRINT_HISTORY.md`*
*Source-of-truth docx → `D:\Kaori Document\` (gitignored)*
