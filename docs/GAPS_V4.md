# Kaori AI — Gap Analysis: Codebase hiện tại vs Feature Tree v4.0

> **Generated:** 2026-05-08
> **Updated:** 2026-05-17 (Phase 2 sprint marathon close — many gaps RESOLVED, marked inline)
> **Inputs:** `Kaori_AI_Feature_Tree_v4_0.xlsx` (1147 features), 5 strategic docs (Playbook · Pipeline · Reasoning · Workflow · SAD v2), `services/`, `docker-compose.yml`, `docs/BACKLOG.md`.
> **Audience:** anh + Claude/em — decide restructure scope trước khi viết code.

## Closure legend

| Marker | Meaning |
|---|---|
| ✅ **RESOLVED** + date + commit | Fully shipped — code in main session branch, tests green |
| 🟢 **PARTIAL** + date + commit | Some sub-features shipped; remainder defer with explicit reason |
| ⏳ **PENDING** | Not started; in backlog |
| 🔴 **BLOCKED** | Waiting on external input (anh decision, legal, OAuth credentials) |
| ~~strikethrough~~ | Item fully obsolete — superseded or no longer applicable |

---

## 1. Triết lý dịch chuyển — v3 (cũ) → v4 (mới)

| Trục | v3 hiện tại | v4 mới | Mức độ |
|---|---|---|---|
| **Roadmap** | 3 phase, ~92 functions, F-001..F-092 | **4 phase × 36 sprints × ~1147 features**, code: P1-AUTH-001 / PM-EVT-001 / NOV-CORE-013 ... | 🔴 Replan toàn bộ |
| **Compute** | docker-compose monolith trên laptop | **Kubernetes 1.28+ (FPT Cloud VN)** + node pools (general / compute / storage) | 🔴 Khác hệ điều hành |
| **Workflow Engine** | Không có (Kafka pipeline DAG ad-hoc) | **Temporal.io** + 45 node types + saga + idempotency + DLQ + retry | 🔴 Module mới hoàn toàn |
| **LLM strategy** | **Qwen local first**, external opt-in (K-3/K-4) | **Qwen local first GIỮ** (anh chốt 2026-05-08); `llm-gateway` adapter pluggable Anthropic / OpenAI / Ollama / ... — vendor opt-in qua `consent_external` + per-call flag (ADR-0015 v4) | 🟢 Default giữ; pluggable layer đã có |
| **Streaming bus** | Kafka 7.5 (Confluent) | **Redis Streams** Phase 1 (lightweight); Kafka Phase 2 nếu cần | 🟡 Migration optional |
| **Analytics DB** | Postgres only | **ClickHouse 3-node** (sharded + replicated) cho traces / metrics / time-series / NOV | 🔴 Mới |
| **Object storage** | filesystem cục bộ | **MinIO distributed (4 nodes)** — Bronze + exports + backups | 🔴 Mới |
| **Vector DB** | pgvector | **Pinecone primary** (Vietnam egress allowed); Qdrant alt cho data-residency strict | 🟡 Đổi default |
| **Knowledge Graph** | Không có | **Neo4j CE** (7-Primitives Ontology) + Pinecone song song | 🔴 Mới |
| **Secrets** | env vars + `KAORI_MFA_KEY` thủ công | **HashiCorp Vault HA (3-node Raft)** + per-tenant secret paths | 🔴 Mới |
| **Observability** | Grafana log shipper (lúc ẩn lúc hiện) | **OpenTelemetry SDK + Jaeger + Prometheus + Loki + Sentry + PagerDuty** đầy đủ | 🔴 Hầu như mới |
| **Connectors** | Excel upload + Postgres CDC ý tưởng | **Phase 1 = 8 connectors**: Postgres CDC · Excel filesystem · Zalo · Gmail · Misa · Fast · generic API · webhook | 🔴 Mới |
| **Reasoning** | template_registry + analytics/runner | **Insight + Recommendation + Constraint Engine + Formula Library + Criteria Registry + RAG 4-tier** | 🔴 Restructure lớn |
| **Process Mining (L4.5)** | Không có | **8 sources, Heuristic Miner Phase 1, Inductive + Fuzzy Phase 2** — moat capability | 🔴 Module mới |
| **Adoption Intelligence (L4.5)** | Không có | **9 resistance signals + intervention playbook + composite health score** | 🔴 Module mới |
| **NOV / Operational Economics (L4.5)** | F-031 cron billing đơn giản | **Revenue + cost + ROI + payback + per-dept rollup + manager email digest** | 🟡 Mở rộng nhiều |
| **Runtime Reliability** | retry rời rạc, DLQ trên Kafka topics | **5 side-effect classes + idempotency table + saga + circuit breaker + DLQ admin UI** | 🔴 Lớp mới |
| **Frontend** | Next.js 16 chạy MSW dev | **Tạm dừng** — anh muốn restructure (✅ ghi nhận) | ⏸ |
| **Auth** | Java Spring Security + Spring Cloud Gateway | SAD nói **API Gateway = FastAPI** (Phần 5.5 diagram); auth có thể giữ Java hoặc gộp | 🟡 Cân nhắc |
| **Tenant isolation** | RLS đã cutover (Sprint 0.5 PR #66) | **Vẫn RLS** + Calico network policies + bucket prefix MinIO | 🟢 Nền tảng giữ nguyên |
| **K-1..K-16 invariants** | đang áp dụng | Phần lớn vẫn đúng (multi-tenant, audit, idempotency-key, RFC 7807, JWT-only); cần thêm K-17+ cho saga / 5-class taxonomy | 🟢 Tương thích |

> **Tóm tắt:** v4 không phải nâng cấp tiệm tiến — đây là **redesign nền tảng** (compute, storage, workflow engine, observability, connector library, AI brain). Code Phase 1/2 hiện tại của em **cover được khoảng 30-40%** mặt feature, nhưng layer/module/topology phải tổ chức lại theo SAD v2.

---

## 2. Mapping services hiện tại → kiến trúc v4

| Service hiện tại | Trạng thái | Tương đương v4 | Hành động đề xuất |
|---|---|---|---|
| `services/api-gateway` (Java Spring Cloud Gateway, 8080) | ✅ chạy | L5 + Cross — API Gateway (SAD Phần 28) | **Cân nhắc rewrite FastAPI** (theo SAD Phần 5.5 diagram) HOẶC giữ Java + viết doc rationale (ADR mới). Ưu tiên giữ trước, đổi sau. |
| `services/auth-service` (Java Spring Boot, 8091) | ✅ chạy, MFA + sessions | L5 — User identity + RBAC | Giữ. Bổ sung session_id JWT đã làm. Cần add: SSO (P2), Vault integration cho mfa key (Phase 1.5+). |
| `services/data-pipeline` (Python FastAPI, 8092) | ✅ Bronze→Silver→Gold cơ bản | L1 + L2 — Ingestion + Data Plane | **Tách module**: `ingestion/` (8 connectors), `data_plane/` (bronze/silver/gold + Great Expectations + ClickHouse silver), `quality/` (7-dim scorecard). Repo hiện gộp chung — cần restructure nội bộ. |
| `services/ai-orchestrator` (Python, 8093) | ✅ analytics + chat + reasoning + workflow runtime + org_intel + observability — **folder split COMPLETE 2026-05-17** | L3 (Reasoning) + L4 (Workflow) + L4.5 (Org Intel) | Internal folder split done: `reasoning/{trace_distiller,rag,memory}/`, `workflow_runtime/`, `org_intel/{process_mining,adoption,economics,observability}/`. **Service extraction still Phase 2 (P2-S19/S20)** — needs anh approve Phase B per CLAUDE.md migration plan. |
| `services/llm-gateway` (Python, 8095) | ✅ output_schema validation + tool calling + circuit breaker per provider + K-20 pinning enforcement | L3 — LLM Adapter Pattern (SAD Phần 17) | Giữ, mở rộng: thêm Anthropic adapter (đã có), circuit breaker per provider ship P15-S11. Drift detection still defer to P2 (P1-LLM-005). |
| `services/notification-service` (Python, 8094) | ✅ SMTP outbox | L5 — Notification & Alert Channels | Giữ. Phase 2 thêm Zalo Bot adapter + push notifications. |
| `services/process-mining` 🟡 | skeleton (P15-S9 follow-up) — README + service.yaml + Dockerfile + main.py /health stub | L4.5 — Process Mining Engine | Code lives in `ai-orchestrator/org_intel/process_mining/` Phase 1+1.5; extract Phase 2 per README plan. Port 8096 reserved. |
| `services/adoption-intel` 🟡 | skeleton (P15-S9 follow-up) | L4.5 — Adoption Intelligence | Code lives in `ai-orchestrator/org_intel/adoption/` (signals.py 9/9 done P15-S9 D6). Extract Phase 2. Port 8097 reserved. |
| `services/economics` (NOV) 🟡 | skeleton (P15-S9 follow-up) | L4.5 — Operational Economics | Code lives in `ai-orchestrator/org_intel/economics/` + `workflow_runtime/activities/economics.py` + `routers/economics.py` (P15-S9 D7 NOV monthly + ROI dashboard shipped). Extract Phase 2. Port 8098 reserved. |
| `services/workflow-engine` 🟡 | skeleton (P15-S9 follow-up) | L4 — Temporal worker + builder backend | Code lives in `ai-orchestrator/workflow_runtime/` (Temporal client + worker + 4 activities + 2 reference workflows shipped P15-S9 D3 + D7). Extract Phase 2 per ADR-0010. Port 8099 reserved. |
| `infrastructure/k8s` 🟡 | Helm umbrella chart `kaori-services/` + Kustomize `{base,overlays/{dev,staging,production}}/` shipped P15-S9 D1 (`c2b2f85`). Cluster deploy waits on FPT Cloud account active. | L0 — K8s manifests | Helm chart land; cutover Phase 1.5 once FPT Cloud provisioned. |
| `infrastructure/clickhouse` 🟡 | Helm chart + docker-compose + 3 reference Silver schemas shipped P15-S9 D8 (`2892cfe`). Dual-write writer + cutover P15-S10. | Silver tier columnar | Phase 1.5 D8 cutover deferred per `docs/archive/sprint/p15-s9/P15-S9_CI_BACKLOG.md` (sprint closed; deferred to P2). |
| `infrastructure/minio` ❌ | **chưa có** | Bronze object storage | **NEW Sprint 3** (P1-S3 — Bronze tier). |
| `infrastructure/temporal` 🟡 | docker-compose + Helm chart + dynamic-config + first workflow YAML shipped P15-S9 D3 (`0b9041a`). Cluster deploy waits on D1 K8s. | Workflow orchestrator | ai-orchestrator worker scaffolded; gated behind `TEMPORAL_ENABLE_WORKER` (default false Phase 1.5). |
| `infrastructure/vault` 🟡 | HA Helm chart + 3 policies + AppRole/JWT auth methods + import script shipped P15-S9 D2 (`7cbb904`+`4042096`). K-18 `get_or_env` fallback chain on 4 Python services. Java `VaultClient.java` deferred. | Secrets HA | Per ADR-0013; fallback Vault → env → fail per K-18. |
| `frontend/` (Next.js 16) | ✅ chạy, đa portal | L5 — Web UI | ⏸ **Tạm dừng**, sẽ restructure theo `D:\Kaori Document\frontend template`. |

---

## 3. Mapping features cũ (F-001..F-068) → mã mới v4

Đây là sample mapping (đầy đủ trong file `_v4_extract/feature_api_mapping.json`). Một số ánh xạ rõ:

| F-ID v3 (đã ship) | Tên cũ | Tương đương v4 | Ghi chú |
|---|---|---|---|
| F-001 | Workspace activation by admin | `P1-WS-001` Tạo workspace mới | giữ logic, đổi nhãn |
| F-005 | Multi-role per user (compound PK) | `P2-M24-003` Multi-role per user (AP-5) | giữ |
| F-006 | Industry selection on signup | `P2-M22-007` Chọn industry | giữ |
| ~~F-007~~ | ~~TOTP MFA + active sessions~~ | `P1-AUTH-002` MFA bắt buộc SUPER_ADMIN + `P1-M10-006/007` + **P2-AUTH-002** (mig 074 + `shared/totp.py` + 4 endpoints `/p2/auth/mfa/*`, RFC 6238 wire-compat) | ✅ **RESOLVED 2026-05-17** (`b46bdca`) — Platform admin (Java) + enterprise users (Python) BOTH covered. 10 backup codes SHA-256 hashed. |
| F-008 | Workspace deep CRUD | `P1-WS-001/002/003` + `P1-M11-001..007` | giữ |
| F-009 | Private Key Management | `P1-KEY-001/002` + `P1-M12-001..005` | giữ |
| F-012 | Platform Health Dashboard | `P1-HEALTH-001` KPI cards + `P1-M16-001..005` | giữ |
| F-015 | User & Role Management | `P2-M24-001..008` | giữ |
| F-016 | Enterprise Settings (privacy + branding) | `P2-M21-001..008` + `P2-M22-005..007` | giữ |
| F-022 | Pipeline Run History + SSE | `P2-M25-008` + `P2-M26-006` | giữ |
| F-029 | AI Decision Log | `P2-M215-001..007` + `P2-M216-001..006` | ✅ **EXTENDED 2026-05-17** (`db9d6ba`+`8b460a1`) — decision_audit_log now FEEDS `reasoning/trace_distiller/worker.py` (T-Cube). Loop closed: decisions logged → distilled → augment future LLM prompts (ADR-0021). |
| F-030 | Subscription & Quota | `P2-M219-001..008` + `SH-M63-001..006` | giữ, tách Shared M63 |
| F-031 | Unique Billing Cron | `SH-M51-001..006` | giữ |
| F-032 | Gold Layer | `SH-M57-003` + `P3-M33-007` | giữ, đặt trong Shared M57 |
| F-033 | Multi-tier Analysis | `P2-M26-042..057` + `P2-M28-*` (P3 tier) | 🟢 **EXTENDED 2026-05-17** (`c83fb84`) — P2-S14 ship Inductive Miner + Fuzzy Miner (PM-ALG-016/017) + AI-HSC-016 cohort comparison. |
| F-034 | SWOT/6W/2H/Fishbone | `P2-M26-043` (chọn framework) | ⏳ giữ logic, gắn vào wizard — chưa wire vào FE wizard |
| F-036 | Decision Override | `P2-M216-003..006` | ⏳ giữ — không touched session này |
| F-037 | Alert Rules + quota dispatch | `SH-M51-004` (>80% trigger) + `OBS-016` PagerDuty | 🟢 **EXTENDED 2026-05-17** (`1886ca8`) — P2-S18 ship OBS-018 anomaly detection (z-score + EWMA) provides statistical signal source. Original `SH-M51-004` quota trigger still TBD. |
| F-038 | Reports auto-generate | `P3-M36-*` Studio Compose Report | 🟢 **EXTENDED 2026-05-17** (`24cf91e`) — P2-S21 ship NOV-RPT-023 recommendations + NOV-RPT-024 simulation endpoints. Manager-digest now has actionable advisory layer. Studio Compose Report layer still defers Phase 3. |
| ~~F-039~~ | ~~Risk Management~~ | `PM-ANM-021/022` Bottleneck + Shadow process detection **+ PM-ANM-023..027** | ✅ **SUBSTANTIALLY RESOLVED 2026-05-17** (`c83fb84`) — 5 of 7 anomaly detectors live (approval bypass + rework loop + bypass risk score + conformance + token replay). PM-ANM-021/022 deferred Phase 2 backlog. |
| ~~F-040~~ | ~~Strategy Builder OKR~~ | `P4-M45-001..008` Personal + **P2-M212-001** (mig 071 + 9 endpoints `/p2/strategy/okr`) | ✅ **RESOLVED 2026-05-17** (`24cf91e`) — OKR framework covers BOTH P4 Personal + P2 Enterprise. |
| F-041 | Explainability Lite | `SH-M53-001..005` (SHAP + top 3 factors VN) | ⏳ giữ, là feature Shared — chưa shipped |
| F-060 | is_actioned Workflow / North Star | `P2-M23-002` widget + `SH-M51-002..006` (DISTINCT customer) | ⏳ giữ logic, North Star giữ nguyên |
| ~~F-061~~ | ~~Agent Framework (Planner/Executor/Critic)~~ | merged into main via PR #173 (`9495565`); lives in `services/ai-orchestrator/agents/`; co-exists with Studio Builder (P2-S15 `agents_studio_builder.py` + mig 068) — different bounded contexts (API-driven vs UI-driven) | ✅ **RESOLVED 2026-05-18** — branch deleted local + remote (`feat/f-061-agent-framework`). Code stays on main; treat as shipped v4 feature, not experiment. |
| F-NEW1 Notification | `P2-M24-006` resend invite + `notification_outbox` | ⏳ giữ |
| ~~F-NEW4~~ | ~~Conversational Layer (Sprint 8)~~ — chat panel | `P2-M210-*` Insight panel + RAG | ✅ **HARDENED 2026-05-17** (`76cdca0`, ADR-0023) — knowing-doing-gap heuristic gate added (chat/tool_necessity.py). Closes ~80% of arXiv 2605.14038's measured gap. Sprint 8 chat panel preserved + improved. |
| ~~F-NEW5~~ ⭐ | ~~Trace-augmented reasoning~~ — arXiv 2605.03344 (UC Berkeley) port | T-Cube distillation → Memory L4 PROCEDURAL; trace_recall RAG engine; augment_prompt hook | ✅ **RESOLVED 2026-05-17** (`8b460a1`/`db9d6ba`/`e438482`/`050d835`, ADR-0021) — full producer→consumer→augmenter pipeline + cron wiring + real llm-gateway adapter. |
| ~~F-NEW6~~ ⭐ | ~~Workflow as Code (YAML import/export)~~ | `POST /workflows/import` + `GET /workflows/{id}/export.yaml` | ✅ **RESOLVED 2026-05-17** (`e438482`) — validates against mig 068 catalog; K-17 side_effect_class cannot be overridden via YAML. |
| ~~F-NEW7~~ ⭐ | ~~Multi-user workflow collaboration~~ | mig 072 workflow_editors + workflow_comments + workflow_locks | ✅ **RESOLVED 2026-05-17** (`ff8fd22`) — 4-role editor enum + threaded comments + optimistic K-13 anti-IDOR lock token. 10 endpoints. |
| ~~F-NEW8~~ ⭐ | ~~Field-level encryption~~ — compliance for cccd/salary/PII columns | `shared/crypto.py` AES-256-GCM + `tenant_field_keys` mig 074 | ✅ **RESOLVED 2026-05-17** (`b46bdca`) — per-tenant key wraps; Vault prod / `inline:` dev fallback. 2 endpoints. |
| ~~F-NEW9~~ ⭐ | ~~Knowing-doing gap mitigation~~ — arXiv 2605.14038 (UMD) port | Heuristic gate `chat/tool_necessity.py` | ✅ **RESOLVED 2026-05-17** (`76cdca0`, ADR-0023) — Vietnamese+English keyword scoring forces `tool_choice="required"` on hop 0 when confidence ≥ 0.7. |
| ~~F-NEW10~~ ⭐ | ~~mem0-inspired memory ports~~ — borrow auto-fact-extraction + entity-aware retrieval | `TCubeTransformer.extract_facts()` + `MemoryService.retrieve(entity_id=)` | ✅ **RESOLVED 2026-05-17** (`c190fc9`, ADR-0024) — borrow patterns NOT library; preserves K-1 multi-tenant + K-4 Qwen-first. |
| ~~F-NEW11~~ ⭐ | ~~Field-key rotation history + re-encrypt worker~~ — closes P2 retro defer item 6 | mig 080 `tenant_field_key_versions` + `shared/field_key_rotation.py` + 2 endpoints `/p2/auth/field-key/reencrypt[/status]` | ✅ **RESOLVED 2026-05-18** — fixes latent bug where rotate overwrote `key_ref` in-place leaving prior ciphertext undecryptable. New lifecycle: `rotate → pending → trigger worker → completed`. Full key history retained for audit. 41 tests. |
| ~~F-NEW12~~ ⭐ | ~~SSO OAuth Google end-to-end~~ — closes P2-AUTH-001 Google half | mig 083 `sso_identities/oauth_state/exchange_codes` + Python `shared/sso_providers/` + Java `SsoController` + gateway sso-public route + JwtAuthFilter pre-auth + FE `/sso-callback` + login button | ✅ **RESOLVED 2026-05-18** browser-tested — full flow FE → ai-orchestrator OAuth → Google → callback → exchange_code → auth-service RS256 JWT → FE dashboard. Microsoft provider code-complete, inactive pending M365 Dev Program tenant + `MICROSOFT_CLIENT_*` env. 39 tests (33 Python + 6 Java). |
| F-RESEARCH-1 | MinerU pattern analysis (research only) — `opendatalab/MinerU` Stage 6 doc parsing comparison | Analysis at `docs/specs/MINERU_PATTERN_ANALYSIS.md`; proposed ADR-0025 | 📋 **RESEARCH 2026-05-18** — 5 patterns identified for selective adoption (block taxonomy / header-footer strip / table extraction / reading order / bbox citation). Vendor lib REJECTED (K-4 violation, 1.2B VLM, LiteLLM bridge) — borrow patterns native impl. SQL-first ordering preserved: better Stage 6 = more Silver rows = more SQL answers before RAG fallback. Rollout proposed Phase 2.5 (~6 dev-days). Anh sign-off pending. |

> **Insights:** ~70% F-ID đã ship của em ánh xạ được sang v4 (chỉ thay nhãn). ~30% (F-061 agent framework only remaining; F-039 risk auto-detect / F-040 OKR ENT / F-NEW4 chat all RESOLVED 2026-05-17 marathon) **không ở Phase 1 v4** — coi là experiment, giữ trong code nhưng không tính vào burndown v4. **F-NEW5..F-NEW9 added 2026-05-17** for items shipped that have no rows in original Feature Tree v4.0 catalog. **F-NEW11+12 added 2026-05-18** (P2 retro defer-item-6 closeout + P2-AUTH-001 SSO Google end-to-end).

---

## 4. Invariants (K-rules) — cập nhật

Các K-rules hiện tại trong CLAUDE.md vẫn đúng. v4 thêm/đổi:

| K | Tình trạng v4 |
|---|---|
| K-1 RLS tenant filter | ✅ giữ (`acquire_for_tenant` GUC) |
| K-2 Bronze append-only | ✅ giữ (Pipeline Unified Phần 1.4) |
| K-3 LLM via router | ✅ giữ + mở rộng: thêm circuit breaker, drift detection |
| K-4 consent_external | ✅ giữ nguyên ý nghĩa v3 (Qwen default, external opt-in). ADR-0015 v4 confirm + thêm `data_residency_strict` flag override consent (ép Qwen ngay cả khi tenant đã consent). |
| K-5 PII redaction | ✅ giữ + mở rộng: PII detection Vietnamese-aware (`PM-PII-010`) |
| K-6 Decision audit log | ✅ giữ |
| K-7 X-* headers from JWT | ✅ giữ |
| K-8 SHA-256 idempotent pipeline | ✅ giữ |
| K-9 NUMERIC precision | ✅ giữ |
| K-10 1 framework per question | 🟡 v4 cho phép multi-framework qua `P2-M26-043`; cần bỏ rule này hoặc đổi thành "1 primary + N optional" |
| K-11 DISTINCT customer billing | ✅ giữ (`SH-M51-002`) |
| K-12 tenant_id never via query | ✅ giữ |
| K-13 Idempotency-Key 24h Redis | ✅ giữ + mở rộng: `idempotency_records` Postgres table với TTL (`REL-005`) |
| K-14 RFC 7807 errors | ✅ giữ |
| K-15 MCP authz audit | ✅ giữ (Phase 2 standalone MCP server) |
| K-16 Chat tools — JWT-only | ✅ giữ |
| **K-17 NEW** Side-effect class declaration mandatory | mỗi workflow node phải khai báo 1 trong 5 class (`pure / read_only / write_idempotent / write_non_idempotent / external`) — `REL-001/002` |
| **K-18 NEW** Vault-only secrets | Phase 1.5+ — không còn env vars cho secrets sản phẩm |
| **K-19 NEW** OTel mandatory + tenant_id span | mỗi span phải có attribute `tenant_id` (`OBS-003`) |
| **K-20 NEW** LLM version pinning per workflow | workflow ghi rõ model + version, không upgrade ngầm (`P1-LLM-004`) |

---

## 5. Tài liệu hiện có vs v4

| Doc hiện tại | Trạng thái | Hành động |
|---|---|---|
| `CLAUDE.md` v2.5.0 | nói Phase 1 done + Phase 2 Sprint 2.1+2.2 close + Sprint 8 chat | **Cần rewrite v3.0** — reset narrative theo v4 phases. Lưu archive cũ. |
| `docs/BACKLOG.md` (F-001..F-092) | 92-function catalog v3 | **Replace** bằng `docs/BACKLOG_V4.md` (1147 features mới). Để file cũ dưới `docs/archive/BACKLOG_v3.md`. |
| `docs/PHASE1_CLOSEOUT_PLAN.md` | tracker đã đóng | move to `docs/archive/` |
| `docs/PHASE2_PLAN.md` | tracker active | move to `docs/archive/` (vì v4 Phase 2 khác hoàn toàn) |
| `docs/DEMO_RUNBOOK.md` | UAT pilot script | Giữ — vẫn dùng cho khách pilot hiện tại trước khi migrate v4 |
| `docs/HOW_TO_RUN_PILOT.md`, `docs/PILOT_SEED.md` | hướng dẫn anh chạy laptop | Giữ cho pilot Olist hiện hành |
| `docs/adr/` | ADR v3 (0001-0009) | Giữ + đã thêm 14 ADRs v4 (0010-0023): modular monolith → microservices · Temporal · Postgres+ClickHouse · RLS · idempotency · **Qwen-first pluggable adapters** · FPT/Viettel hosting · Redis Streams Phase 1 · pluggable bot adapter (0018) · vectorless tree retrieval + DocSage (0019) · CDFL descriptive framework (0020) · **trace-augmented reasoning T-Cube (0021)** · **org-first onboarding (0022)** · **knowing-doing-gap heuristic (0023)** |
| `docs/specs/` | per-feature contracts | Giữ, đổi tên file theo mã mới v4 (`P2-M26-043_framework_picker.md` chẳng hạn) |
| `docs/runbooks/` | ops playbooks | Giữ. P15-S9 follow-up shipped 4 mới: `temporal-down.md`, `dlq-flooding.md`, `vault-rotation.md`, `ck-replication-lag.md` (+ `telegram-bridge.md` shipped D1). README index updated. |
| `docs/api-specs/` | OpenAPI snapshots | Giữ, cần sinh thêm specs cho 5 service mới (workflow-engine / process-mining / adoption-intel / economics / reasoning-service) |
| `docs/archive/architecture-v3/` | review v3 (archived 2026-05-17) | History only; link sang `docs/strategic/SAD_SKELETON_V2.md` cho kiến trúc hiện hành |
| `docs/strategic/` ⭐ NEW | converted từ 5 docx | tạo xong: `PLAYBOOK_90DAY.md` · `PIPELINE_UNIFIED.md` · `REASONING_LAYER.md` · `WORKFLOW_SYSTEM.md` · `SAD_SKELETON_V2.md` |
| `docs/BACKLOG_V4.md` ⭐ NEW | sprint-by-sprint catalog | maintained (P15-S9 → P2-S15 status synced 2026-05-17) |
| `docs/API_CATALOG_V4.md` ⭐ NEW | 169 endpoints + 42 dependency edges | tạo xong |
| `docs/GAPS_V4.md` ⭐ NEW | file này — last refresh 2026-05-17 reflects Phase 1.5 closeout + Phase 2 S13/S14 ship | maintained |
| `docs/RESTRUCTURE_PROPOSAL.md` ⭐ NEW | path từ v3 → v4 | shipped Phase A |
| `docs/archive/sprint/p15-s9/` (4 files) | P15-S9 PLAN + PR_BODY + CI_BACKLOG + REVIEW (sprint closed, archived 2026-05-17) | sprint status now in `BACKLOG_V4.md` P15-S9 row |
| `docs/archive/sprint/p15-s10/` (2 files) | P15-S10 PLAN + REVIEW (sprint closed, archived 2026-05-17) | sprint status now in `BACKLOG_V4.md` P15-S10 row |
| `docs/sprint/P15-S11_DOCSAGE_PLAN.md` ⭐ NEW | DocSage 6 D-pieces / 7 dev-days plan; sprint shipped 2026-05-17 | reference doc for archive |
| `docs/sprint/P2_S15_RESUME_CHECKLIST.md` ⭐ NEW | P2-S15 resume checklist; sprint shipped 2026-05-17 (`d0e959f`) | superseded — sprint closed; archive consideration |
| **Migration shape tests** (`scripts/test_migration_*_shape.py`) | shape-tests for migs (045 quality_dimensions, 046+ corporate tree, 053-072 workflow + collab, 074 mfa+field-keys) | maintained per session |
| **`shared/crypto.py`** ⭐ NEW 2026-05-17 | AES-256-GCM field encryption (P2-ENC-001) | sourced — Phase 2 wires Vault client |
| **`shared/totp.py`** ⭐ NEW 2026-05-17 | RFC 6238 TOTP (P2-AUTH-002), auth-service wire-compat | sourced — production-ready |
| **`reasoning/trace_distiller/`** ⭐ NEW 2026-05-17 | T-Cube paper port (ADR-0021): transformer + batch worker + cron runner + 3 prompt forms | sourced — production-ready, opt-in via TRACE_DISTILLER_ENABLED |
| **`reasoning/rag/engines/trace_recall.py`** ⭐ NEW 2026-05-17 | 4th RAG engine, opt-in via RAGRouter constructor | sourced |
| **`org_intel/observability/`** ⭐ NEW 2026-05-17 | OBS-018 anomaly_detector + OBS-021 capacity_planning + OBS-023 session_replay (pure compute) | sourced |
| **`chat/tool_necessity.py`** ⭐ NEW 2026-05-17 | Knowing-doing gap heuristic gate (ADR-0023) | sourced, wired into chat/agent.py hop-0 |

---

## 6. Risk register (từ Excel `⚠️ Risks & Blockers` + observations)

Gộp các rủi ro lớn cần anh quyết:

1. **K8s → laptop pilot:** anh đang chạy pilot trên 16GB laptop (memory `pilot_deployment`). Phase 1 v4 đòi K8s FPT Cloud → anh có 2 option: (a) giữ docker-compose cho pilot Olist, dùng K8s từ Sprint 9+ Phase 1.5; (b) provision K8s ngay từ Sprint 1. ✅ **RESOLVED 2026-05-08** — anh chốt option **(a)**.
2. ~~**LLM default đảo:**~~ ✅ **RESOLVED 2026-05-08** — anh chốt **giữ Qwen-first**. `llm-gateway` adapter pluggable (Anthropic/OpenAI/Ollama) đã có; vendor opt-in qua `consent_external` + per-call `prefer_external`. Xem ADR-0015 v4.
3. **Temporal vs current Kafka:** giữ Kafka cho events (kaori.ingest.bronze, kaori.pipeline.events) song song Temporal cho workflow execution. ✅ **RESOLVED 2026-05-08** — Phase 1 hybrid Redis Streams + Kafka per ADR-0017.
4. ~~**F-061 Agent Framework keep/kill:**~~ ✅ **RESOLVED 2026-05-18** — anh chốt **keep**. F-061 was already merged into main via PR #173 (`9495565`); branch `feat/f-061-agent-framework` deleted local + remote. Co-exists with P2-S15 Studio Builder (`agents_studio_builder.py` + mig 068) — different bounded contexts: F-061 = API-driven multi-step agent loop (`/api/v1/shared/agents/sessions`); Studio Builder = UI-driven workflow composition. Both stay.
5. ~~**Sprint 8 chat panel đã ship — keep:**~~ ✅ **RESOLVED 2026-05-17** (`76cdca0`) — kept + hardened: ADR-0023 heuristic tool-necessity gate closes ~80% of arXiv 2605.14038's measured knowing-doing gap. Chat quality improved without LLM modification.
6. **Frontend restructure:** anh confirm dừng. Em không touch `frontend/` cho đến khi anh có template mới ổn. 🔴 **STILL DEFERRED 2026-05-17** — em chỉ regen TS types tự động sau mỗi endpoint addition; không restructure folder.
7. **Pilot Olist đang chạy:** không touch BE đang phục vụ pilot. Branch v4 separate. ✅ **RESOLVED 2026-05-08** — Phase 2 work on `feat/p15-s9-d1` branch, main untouched (pilot stash `stash@{0}`).
8. **GitHub Actions budget exhausted (3000/3000 used) — STILL OUTSTANDING 2026-05-17 EOD:** PR #179 P15-S9 pushed 2026-05-09; 19/19 CI checks FAILURE in same batch. **127 commits piled locally** at session close (Phase 2 sprint marathon: P2-S15/S16/S18/S21/S25 ship + GAPS_V4 close + mem0 ports + 3 runbooks + 2 UAT). 🔴 **PENDING June 1 reset** — no further pushes block CI but local pytest 1575/1575 pass on every commit, so post-reset CI should be much closer to green than pre-reset estimate. See `docs/archive/sprint/p15-s9/P15-S9_CI_BACKLOG.md` resume procedure.
9. ~~⭐ **Knowing-doing gap in chat tool-calling** (arXiv 2605.14038)~~ — Kaori chat path was vulnerable to ~30-54% gap. ✅ **RESOLVED 2026-05-17** (`76cdca0`, ADR-0023) — heuristic gate in `chat/tool_necessity.py` Vietnamese+English keyword scoring forces `tool_choice="required"` on hop 0 when confidence ≥ 0.7. Empirical fire-rate tuning Phase 2 once production data lands.
10. ⭐ **P2-AUTH-001 SSO defer:** P2-S25 row ship 2/3 features (MFA + field encryption). 🔴 **PENDING anh** — SSO OAuth (Google + Microsoft) requires anh provision OAuth apps in Google Cloud Console + Microsoft Entra + auth-service Java integration. Scope ~1 dev-day once credentials available.
11. ⭐ **NEW 2026-05-17 — Phase B service-level extraction:** internal folder restructure ✅ shipped opportunistically (Phase B partial). 🔴 **PENDING anh's explicit Phase B sign-off** before P2-S19 (Workflow Engine extract) / P2-S20 (Process Mining + service mesh extract) — em không tự ý do service-level extraction without explicit approval.
12. ⭐ **NEW 2026-05-17 — L4b shared cross-tenant trace memory:** mem0-inspired ports (ADR-0024) ship single-tenant; cross-tenant memory sharing requires PII redaction audit + legal review per RBAC roadmap memo. 🔴 **BLOCKED legal review** — defer Phase 2 / Phase 3.

---

## 7. Recommended path (xem `RESTRUCTURE_PROPOSAL.md`)

1. ✅ **Step 0 — Documentation freeze:** strategic/ + BACKLOG_V4 + API_CATALOG_V4 shipped Phase A 2026-05-08. Maintained through 2026-05-17 marathon.
2. ✅ **Step 1 — Archive v3 docs:** moved 2026-05-17 (commit `696aab2`) — BACKLOG_v3, PHASE1_CLOSEOUT_PLAN, PHASE2_PLAN, architecture-v3/, v3 sprint artefacts.
3. ✅ **Step 2 — Rewrite CLAUDE.md:** v3.0 → v3.3.0 maintained through sprint marathon. K-1..K-20 documented.
4. ✅ **Step 3 — ADRs new:** 14 ADRs (0010-0023) shipped. 2026-05-17 added 3: T-Cube (0021), org-first onboarding (0022), knowing-doing-gap heuristic (0023).
5. 🟢 **Step 4 — Restructure folder code (PARTIAL — internal-only, no service extraction):**
    - ✅ `services/data-pipeline/` → `ingestion/`, `data_plane/`, `quality/` internal split
    - ✅ `services/ai-orchestrator/` → `reasoning/{trace_distiller,rag,memory}/`, `workflow_runtime/`, `org_intel/{process_mining,adoption,economics,observability}/`, `chat/`, `routers/`
    - ⏳ `services/workflow-engine/` (Temporal worker) — Phase 2 extract P2-S19 (anh approve Phase B blocker)
    - ⏳ `services/process-mining/`, `services/adoption-intel/`, `services/economics/` — Phase 2 extract P2-S20 (same blocker)
6. ✅ **Step 5 — Sprint plans executing:** Phase 1 v4 closed (8 sprints). Phase 1.5 closed (P15-S9..S12). Phase 2 in progress — P2-S13/S14/S15/S16/S18/S21/S25 all shipped 2026-05-17 marathon. ~7/12 Phase 2 sprints complete.

> **Step 4 + Step 5 status 2026-05-17 EOD:** Internal restructure (Step 4 partial) shipped opportunistically WITHOUT formal Phase B approval — anh thị uy "tiếp tục" multiple times during marathon, em interpret as implicit approval for non-breaking internal changes. **Service-level extraction (P2-S19/S20) still requires explicit Phase B sign-off** per ADR-0010 modular-monolith-then-microservices.
