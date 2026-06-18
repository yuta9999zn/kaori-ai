# Sprint P1-S5 — Acceptance Mapping

> **Sprint goal:** "Reasoning Layer + LLM integration"
> **Status:** ✅ 39 features traced (24 existing + 2 net new + 13 deferred)
> **Branch:** `feat/v4-p1-s5` (parent: `feat/v4-p1-s4`)
> **Date:** 2026-05-08

This sprint materialises K-20 (LLM version pinning, the workflow-as-code stability contract) and OBS-008 (per-call/per-token Prometheus metrics) on top of the llm-gateway. Plus Phase B-2 internal split: ai-orchestrator/analytics/ moved into reasoning/legacy_analytics/ + 7 reasoning-engine subfolder skeletons created (insight/recommendation/constraint/formula/criteria/rag/profiling). Most of the 39 P1-S5 features are existing Phase 1 v3 work (insight panel, RAG, explainability F-041, quota F-030, billing email F-031) — smoke-tested via the acceptance map.

---

## Net new work shipped this sprint

| Feature code | Description | Implementation |
|---|---|---|
| **Phase B-2** | ai-orchestrator/analytics/ → reasoning/legacy_analytics/ + 7 reasoning subfolder skeletons | `git mv analytics reasoning/legacy_analytics` + 5 internal import updates (`..analytics.X` → `.X`, `..engine.X` → `...engine.X`, `..shared.X` → `...shared.X`) + 4 external caller updates (consumers/pipeline_consumer.py, multi_tier/service.py, routers/analytics.py, tests/test_engines.py) + 7 NEW empty subpackages (insight_engine, recommendation_engine, constraint_engine, formula_library, criteria_registry, rag, profiling). 436 → 436 pass, 0 regression. |
| **P1-LLM-004 ⭐** | LLM Version Pinning (K-20) | `services/llm-gateway/models.py InferRequest` adds `pinned_model` + `pinned_version` fields. Router enforces both-or-neither at request time (422 on mismatch); when set, skips routing.resolve_model and forces method based on model prefix (claude-* / gpt-* / o1-*/o3-* → external; everything else → internal). Audit reasoning carries `pinned=<model>@<version>` so quality-regression investigators can grep the exact build. |
| **OBS-008 ⭐** | Custom metrics ai_calls_total + tokens_total | `kaori_ai_calls_total` Counter labels: provider × model × tenant_id × status (success/validation_failed/upstream_error). `kaori_ai_tokens_total` Counter labels: provider × model × tenant_id × direction (input/output). Phase 1 uses character count proxy; Phase 1.5 swap to provider-side billing API token counts. _provider_label() helper maps (method, model_used) → provider tag (ollama/anthropic/openai/external). |
| 10 unit tests | P1-LLM-004 + OBS-008 contract | `services/llm-gateway/tests/test_router_pinned_and_metrics.py`: pinned_model overrides routing, prefix-based method inference, both-or-neither validation (2 422 tests), audit reasoning carries pin, call counter increments on success, token counter splits input/output, _provider_label mapping, error path counter. |

---

## 24 existing features mapped

### Platform (3)

| Feature | Existing impl | Test |
|---|---|---|
| `P1-LLM-004 ⭐` | NEW this sprint — see above | `test_router_pinned_and_metrics.py` |
| `P1-M10-002` Quên mật khẩu → email reset | `auth-service AuthController.forgotPassword` (F-007) + notification-service template `reset-password` (F-NEW1) | `AuthServiceTest::forgotPassword_*` |
| `P1-M14-006` Tính overage cost tự động | F-031 `BillingAggregationService` overage calc + `enterprise_monthly_billing.overage_cost_vnd` | Existing billing tests |

### Enterprise (24, of which 18 existing)

| Feature | Existing impl | Test |
|---|---|---|
| `P2-M20-002` Kích hoạt qua email invite | F-007 + F-NEW1 invite template | `EnterpriseUserService` invite path |
| `P2-M20-003` Quên mật khẩu → email reset | Same as P1-M10-002 (shared flow) | Same |
| `P2-M21-006` Custom subdomain (mycompany.kaori.ai) | Phase 2 explicit per BACKLOG_V4 — DEFERRED |
| `P2-M21-007` Custom email template branding | F-016 partial (logo column exists in tenant_settings); template engine uses it for invite + reset emails (notification-service Jinja2) | Existing — verify via `notification-service tests/test_outbox_poller` |
| `P2-M22-007` Chọn industry (RETAIL/FINANCE/...) | F-006 industry selection on signup | Existing tests |
| `P2-M23-004` Widget AI decisions today | F-012 + F-029 dashboard widget | Existing dashboard tests |
| `P2-M23-010` Customize widget layout (drag-drop) | FE feature — paused per anh |
| `P2-M24-002` Mời member qua email | F-015 + F-NEW1 invite | `EnterpriseUserService.invite` |
| `P2-M25-024` Aggregated Objects (daily/weekly/monthly summary) | F-032 `gold_aggregator` rebuilds gold features from silver each silver.complete event; weekly/monthly rollups via `gold_features.week_*` / `month_*` columns | `tests/test_gold_aggregator.py` |
| `P2-M26-005` Drag-drop file | FE feature — paused |
| `P2-M26-008` Template catalog (Retail/Finance/Logistics/HR/Marketing) | F-NEW3 rule_catalog has BY_PURPOSE rules for each industry | `test_unit_whitebox.py::TestRuleCatalogRegistry` |
| `P2-M26-016` Drag-drop mapping | FE feature — paused (BE has POST `/schema/confirm`) |
| `P2-M26-031` Rule: Validate email/phone format | F-NEW3 `data_plane/silver/rule_catalog.py` `VALIDATE_EMAIL`, `VALIDATE_PHONE_VN` | `test_unit_whitebox.py::TestApplyRulesToDf` |
| `P2-M26-044` Chọn external AI provider (optional) | FE feature — paused. BE supports per-call `consent_external` + `pinned_model` (just added P1-LLM-004) |
| `P2-M26-051` Insight panel "Chuyện gì · Tại sao · Nên làm gì" | F-029 + F-041 explainability panel | `tests/test_explainability.py` |
| `P2-M210-005` Confidence score per insight | F-041 + `decision_audit_log.confidence` NUMERIC(5,4) | `tests/test_explainability.py` |
| `P2-M210-008` Chọn LLM nội bộ vs external AI | `consent_external` flag in `tenant_settings` (F-016) + InferRequest field (existing) | `tests/test_routing.py` |
| `P2-M210-009` Export insight as PDF report | F-038 reports + PDF generator | `tests/test_reports.py` |
| `P2-M210-010` Save insight + track acted/not-acted | F-029 `decision_audit_log.is_actioned` (boolean) | `tests/test_decisions.py` |
| `P2-M210-011` Feedback loop — user rate insight → improve prompt | F-036 decision overrides emit `kaori.feedback.actions` Kafka topic | Existing decision tests |
| `P2-M210-014` RAG cho insights | F-NEW4 chat already has retrieval pattern; insight-panel RAG uses pgvector via `services/ai-orchestrator/explainability/service.py` | `tests/test_explainability.py` |
| `P2-M216-002` Panel "Tại sao AI quyết định" (top 3 factors) | F-041 explainability "lite" — top_factors JSONB column | `tests/test_explainability.py` |
| `P2-M219-001` Tab Quota — gauge X/Y khách / token LLM | F-030 quota tab + `enterprise_monthly_billing.unique_customers` | Existing tests |
| `P2-M219-002` Dự báo overage | F-031 overage projection | Existing billing tests |

### Studio (2 — DEFERRED)

| Feature | Reason |
|---|---|
| `P3-M34-002` Click → version detail | Studio portal Phase 2 |
| `P3-M34-005` Tab Training Log | Studio portal Phase 2 (model registry F-046) |

### Personal (5 — DEFERRED)

| Feature | Reason |
|---|---|
| `P4-M40-002` Đăng ký tài khoản cá nhân | Personal portal Phase 2 |
| `P4-M40-004` Xác thực email/SMS OTP | Personal portal Phase 2 |
| `P4-M41-004` AI suggestions unread panel | Personal portal Phase 2 |
| `P4-M44-003` Insights cá nhân hóa | Personal portal Phase 2 |
| `P4-M45-005` Drag-drop reorder (persist ngay) | Personal portal Phase 2 |

### Cross-cutting (5)

| Feature | Existing impl | Notes |
|---|---|---|
| `SH-M51-001` Cron daily aggregate | F-031 `BillingAggregationCron` runs daily 02:00 ICT | Existing `BillingAggregationServiceTest` |
| `SH-M53-005` API explainability public | F-041 `POST /api/v1/explainability/explain` | `tests/test_explainability.py` |
| `SH-M57-001` Bronze layer storage (object storage / S3-compatible) | Phase 1 stays Postgres `bronze_files` + filesystem; MinIO P1-S3/P15-S9 per ADR-0016 |  |
| `SH-M62-002` Gửi invoice qua email | F-031 + notification-service Jinja2 invoice template | Existing |
| `OBS-008 ⭐` | NEW this sprint — see above | `test_router_pinned_and_metrics.py` |

---

## Quick-run smoke command

```bash
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q       # 436 pass
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q          # 367 pass + 1 skip
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q            # 96 pass (+10 new)
cd "D:\Kaori System\services\notification-service" && python -m pytest -q   # 17 pass
```

**Total: 916 Python pass** (was 906 after P1-S4, +10 from P1-S5 router tests).

---

## Files touched this sprint (P1-S5)

```
services/ai-orchestrator/
  analytics/                            MOVED → reasoning/legacy_analytics/   (git mv)
  reasoning/__init__.py                 NEW (empty package marker)
  reasoning/{insight_engine,            NEW (7 empty subpackages with __init__.py
              recommendation_engine,           — Sprint P1-S5+ adds modules)
              constraint_engine,
              formula_library,
              criteria_registry,
              rag,
              profiling}/
  reasoning/legacy_analytics/runner.py  MODIFIED (5 internal imports)
  consumers/pipeline_consumer.py        MODIFIED (..analytics.runner → ..reasoning.legacy_analytics.runner)
  multi_tier/service.py                 MODIFIED (same)
  routers/analytics.py                  MODIFIED (2 imports)
  tests/test_engines.py                 MODIFIED (2 imports)

services/llm-gateway/
  models.py                             MODIFIED (InferRequest +pinned_model +pinned_version fields)
  router.py                             MODIFIED (P1-LLM-004 pin override + OBS-008 emit)
  tests/test_router_pinned_and_metrics.py NEW (10 tests)

docs/sprint/P1-S5_ACCEPTANCE.md         NEW (this file)
```

---

## What this sprint did NOT do (deferred / not in scope)

- **Real reasoning engines** (insight_engine, recommendation_engine, constraint_engine, formula_library, criteria_registry, rag, profiling) — skeleton subfolders only. Sprint P1-S6+ wires actual logic per `docs/strategic/REASONING_LAYER.md`.
- **Studio portal features** — Phase 2 (P3-M34-*).
- **Personal portal features** — Phase 2 (P4-M40-*, P4-M41-*, P4-M44-*, P4-M45-*).
- **Custom subdomain** (P2-M21-006) — Phase 2 explicit.
- **FE drag-drop / mapping / file upload** — paused per anh.
- **Per-tenant LLM token budget enforcement** — uses OBS-008 metrics; budget logic Phase 1.5+.
- **Real token counts** — Phase 1 uses char-count proxy; provider-side billing API integration P1-S6 follow-up.
- **drift Olist 12 file** — still stashed `stash@{0}` from P1-S3.

---

## Phase B-2 progress after Sprint P1-S5

```
services/data-pipeline/
├── data_plane/{bronze,silver,gold}/    ← P1-S3 + P1-S4 ✅
├── ingestion/connectors/{...}/         ← P1-S3 ✅
└── (other modules unchanged)

services/ai-orchestrator/
├── reasoning/                           ← NEW this sprint
│   ├── legacy_analytics/                ← moved from analytics/ ✅
│   ├── insight_engine/                  ← skeleton (P1-S6+)
│   ├── recommendation_engine/           ← skeleton
│   ├── constraint_engine/               ← skeleton
│   ├── formula_library/                 ← skeleton
│   ├── criteria_registry/               ← skeleton
│   ├── rag/                             ← skeleton (consider moving from explainability)
│   └── profiling/                       ← skeleton
├── chat/                                ← stays per CHAT_TOOL_REGISTRY_V4 (refactor defer)
├── workflow_runtime/                    ← Sprint P1-S6 will create (Temporal worker)
├── org_intel/                           ← Sprint P1-S7 will create (process_mining/, adoption/, economics/)
└── (frameworks/, explainability/, multi_tier/, reports/, agents/ — stay; gradual move per future sprints)
```

---

## Sprint dependency map

P1-S5 unblocks:
- P1-S6 Temporal Workflow Engine — uses pinned_model/pinned_version contract per workflow node (K-20)
- P1-S7 Process Mining v1 — Adoption Intel signals consume llm_calls_total metric for "AI override rate" calculation

P1-S5 depends on:
- P1-S4 commit `76a5b27` — silver+gold under data_plane/ ready

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S5 (39 features)
- `docs/RESTRUCTURE_PROPOSAL.md` §3 Step 4 (lazy file move strategy)
- `docs/strategic/REASONING_LAYER.md` PART I + IV (Reasoning + RAG)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 13-17 (Reasoning Layer Architecture)
- `docs/adr/0015-qwen-first-with-pluggable-vendor-adapters.md` (LLM strategy + K-20)
- `docs/_v4_extract/sprint_phase1.json` — raw 39-feature list
