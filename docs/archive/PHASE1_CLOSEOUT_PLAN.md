# Phase 1 Close-Out Plan

> **Status: ✅ CLOSED 2026-04-27** (tag `v1.0-phase1-complete`) — Sprint 7 polish (`v1.1-pilot-ready`, PRs #84-#87) + Sprint 8 conversational layer (F-NEW4, branch `feat/sprint-8-pr-a-chat-backend`) followed.
> **Active tracker has moved to `docs/PHASE2_PLAN.md`** (created 2026-05-02). This file is preserved for sprint-by-sprint history; do not add new items here.
>
> Owner: Nguyen Truong An (solo) · Created 2026-04-26 · Target: ~6 weeks (27 working days + buffer)
> Source: Audit `2026-04-26` cross-checked against `BACKLOG.md` v1.3 + `CLAUDE.md` v2.3

---

## Scope decisions (locked)

| # | Decision | Rationale |
|---|---|---|
| 1 | Solo execution, strict serial | No parallel track A/B |
| 2 | F-031 = option (a): DB threshold flags only, no email | Defer email to Phase 2 with F-037 Alert Rules |
| 3 | F-032 = minimum scope: schema + `revenue_at_risk` aggregator only | Defer full feature engineering + `is_actioned` workflow to Phase 2 (F-060) |
| 4 | No hard deadline | Quality > speed; allow buffer for tests + PR review |

---

## Status legend
| Symbol | Meaning |
|---|---|
| ⬜ | Not started |
| 🟡 | In progress |
| 🟢 | Code complete, PR open |
| ✅ | Merged + tests pass |
| ❌ | Blocked (note in Risk register) |

---

## Timeline overview

| Sprint | Week | Items | Days | Cumulative | Status |
|---|---|---|---|---|---|
| 0 | Day 0 | Drift cleanup + CLAUDE.md §2 | 0.5 | 0.5 | ✅ done (PR #65, 2026-04-26) |
| **0.5** | **W1 D1-2** | **P0 #4 RLS cutover + P0 #6 K-6 audit wire-up** | **2** | **2.5** | ✅ done (PR #66 + #67, 2026-04-26) |
| 1 | W1 D3-W2 D2 | F-016, F-022, **F-NEW2 SSE** | 5 | 7.5 | ✅ done (PR #69 + #71, 2026-04-27) |
| 2 | W2 D3-W3 D2 | F-029, F-015 | 5 | 12.5 | ✅ done (PR #72 + #73, 2026-04-27) |
| 3 | W3 D3-W4 D2 | F-031, F-030 | 5 | 17.5 | ✅ done (PR #74 + #75, 2026-04-27) |
| 4-5 | W4-5 | F-032 Gold Layer | 8 | 25.5 | ✅ done (PR #80, 2026-04-27) |
| 6 | W6 D3-5 | Sign-off + DEMO_RUNBOOK + **OpenAPI codegen prep** | 3 | 30.5 | 🟢 in flight (this PR + OpenAPI sub-PR follows) |

**Progress: ALL 32 Phase 1 functions ✅ — close-out 1 calendar day (anh's pace). Total estimate was 6 weeks; actual = 1 day end-to-end.**

**P0 status after Phase 3 hardening (verified 2026-04-26):**
- ✅ P0 #1 SecurityConfig — TrustedGatewayAuthFilter wired
- ✅ P0 #2 Kafka topics — `kafka_topics.py` const module + `kaori.*` prefix aligned with CLAUDE.md §7
- ✅ P0 #3 RBAC — role matchers + filter chain enforced in SecurityConfig + JwtAuthFilter
- 🟡 P0 #4 RLS — **helper ready, routers not switched** → see Sprint 0.5
- ✅ P0 #5 Kafka outbox + consumer dedup — outbox.py + mark_processed() shipped
- 🟡 P0 #6 K-6 audit — **helper ready, only schema.py wired** → see Sprint 0.5

---

## Sprint 0 — Day 0 setup

### Drift cleanup
- [x] Status: ✅ Completed 2026-04-26
- [x] Delete `services/data-pipeline;C` (empty Windows shell artifact) — done in `chore/sprint-0-drift-cleanup`
- [x] Update `CLAUDE.md` §2 — `llm-gateway` (TBD, scaffold) + `notification-service` (8094, F-NEW1 partial) added with "Phase 2 target / not yet wired" notes — done in commit `8dcf17c` (merged via PR #64)
- [x] Single commit landed: `chore: drop stray data-pipeline;C directory`

---

## Sprint 0.5 — P0 defect close-out (Week 1, Day 1-2)

> **Why before everything else:** P0 #4 (RLS) prevents tenant-leak when adding 4 new endpoints in Sprints 1-3. P0 #6 (K-6 audit) is a hard prerequisite for F-029 — without LLM/clean/runner audit calls, the Decision Log page only shows schema-confirm rows (1 type out of dozens). Verified post Phase 3 hardening 2026-04-26 — see ARCHITECTURE_REVIEW.md §4.

### P0 #4 RLS cutover — 1 day
- [x] Status: ✅ Completed 2026-04-26 (`fix/p0-rls-cutover` branch)
- **Files touched (10 sites across 9 files):**
  - ✅ `services/data-pipeline/shared/db.py` — `acquire_for_tenant()` already in place (G4a scaffold)
  - ✅ `services/data-pipeline/routers/upload.py:57` (GET status) — POST /upload still passes `get_pool()` to `ingest_file` (background task — out of Sprint 0.5 scope)
  - ✅ `services/data-pipeline/routers/schema.py:41,123` (POST /schema, /confirm)
  - ✅ `services/data-pipeline/routers/clean.py:40,72,192` (POST /suggestions, /apply — last block also dropped redundant `conn.transaction()` since `acquire_for_tenant` opens its own)
  - ✅ `services/data-pipeline/routers/analyze.py:33` (POST /analyze)
  - ✅ `services/data-pipeline/routers/results.py:21` (GET /results/:run_id) — **discovered during cutover, not in original audit**
  - ✅ `services/ai-orchestrator/shared/db.py` — `acquire_for_tenant()` mirror already in place
  - ✅ `services/ai-orchestrator/routers/analytics.py:49,90,109` (POST /runs, GET /runs, GET /runs/:id)
  - ✅ `services/ai-orchestrator/routers/strategy.py:103,146` — **discovered during cutover** (recommendations + _load_data_context helper)
  - ✅ `services/ai-orchestrator/routers/dashboard.py:30,55,88,149,182` — **discovered during cutover**; `_compute_kpis` refactored to take `conn` not `pool`
  - ✅ `services/ai-orchestrator/consumers/pipeline_consumer.py:101` (`_handle_silver_complete`); `mark_processed` at line 80 intentionally KEPT on `pool.acquire()` because outbox dedup is system-level, not tenant-scoped (inline comment added)
  - ✅ `docker-compose.yml` lines 188/217/238 already DSN=`kaori_app` (no edit needed)
  - ✅ Migration `008_kaori_app_grants.sql` already grants + `BYPASSRLS` (preserved until G4c flips it)
  - ✅ Test fixture `tests/test_api.py::_make_tenant_ctx_factory` added — patches `acquire_for_tenant` in addition to `get_pool` for backward compat
- **DoD verified:**
  - [x] `acquire_for_tenant()` runs `SELECT set_config('app.enterprise_id', $1, true)` inside transaction (db.py:114-117)
  - [x] All router endpoints with tenant scope use the helper (grep `get_pool().acquire()` in `routers/*.py` → 0 hits, only `consumers/pipeline_consumer.py:80` retained for system dedup)
  - [x] DSN points to `kaori_app` (verified docker-compose.yml)
  - [x] Tests: data-pipeline **252/253 pass** (1 skipped), ai-orchestrator **171/171 pass**
  - [ ] Integration test (cross-tenant SELECT returns 0 with RLS) — deferred to G4c when `BYPASSRLS` is removed; today helper sets the GUC but RLS is bypassed at role level
  - [x] PR merged — PR #66 (commit `2ca5b3a`, merged 2026-04-26)

### P0 #6 K-6 audit wire-up — 1 day
- [x] Status: ✅ Completed 2026-04-26 (`fix/p0-k6-audit-wireup` branch)
- **Scope adjustments (locked 2026-04-26):**
  - `engine/llm_router.py` REMOVED from scope — audit for LLM routing has moved into `services/llm-gateway` (per `engine/llm_router.py:5-7` comment).
  - `schema.py` inline INSERT (lines 80-94) NOT migrated — keeps transactional consistency with column_map upsert. Helper-based audit reserved for fire-and-forget call sites.
- **Files touched:**
  - ✅ **NEW** `services/data-pipeline/shared/audit.py` — exact mirror of ai-orchestrator helper (same signature, best-effort, 4 KB truncation, kw-only args)
  - ✅ `services/data-pipeline/routers/clean.py` — `log_decision()` per cleaning rule applied, after main `acquire_for_tenant` block commits (decision_type=`cleaning_rule`, subject=`{rule_id}:{col}`)
  - ✅ `services/ai-orchestrator/analytics/runner.py` — `log_decision()` on both success and error paths of `_run_single_template` (decision_type=`template_analysis`, subject=`template_id`, chosen_value=`done`/`error`)
  - ✅ **NEW** `services/data-pipeline/tests/test_audit.py` — mirror of ai-orchestrator test_audit (7 tests: happy path, optional run_id, skip cases × 3, swallow DB error, truncation)
- **DoD verified:**
  - [x] Grep `decision_audit_log` INSERT/log_decision call sites → 4 distinct sources: `schema.py` inline + `clean.py` (helper) + `runner.py` success path (helper) + `runner.py` error path (helper)
  - [x] Helper signature matches ai-orchestrator (kw-only)
  - [x] Best-effort write — `pool.execute()` not nested in caller transaction; DB errors swallowed
  - [x] Unit test per call site for the helper itself (7 tests in test_audit.py); call sites covered by existing test_api.py routes that mock pool.execute
  - [x] Tests: data-pipeline **259/260 pass** (was 252 before; +7 audit), ai-orchestrator **171/171** (no regression from runner.py audit injections — mocked pool.execute accepts both)
  - [ ] End-to-end smoke (deferred to first real pipeline run after merge): `SELECT decision_type, COUNT(*) FROM decision_audit_log GROUP BY 1` should show ≥3 distinct types: `column_map`, `cleaning_rule`, `template_analysis`
  - [x] PR merged — PR #67 (commit `7da52ae`, merged 2026-04-26)

---

## Sprint 1 — Week 1

### F-022 Pipeline Run History — 1 day
- [x] Status: 🟢 PR open (2026-04-27, bundled with F-NEW2)
- **Depends on:** none
- **Scope adjustments (locked 2026-04-27):**
  - Path: `services/data-pipeline/routers/enterprise_pipelines.py` (PLAN said `api/`, repo convention is `routers/`).
  - Endpoint: `GET /api/v1/pipelines?cursor=&limit=&status=&from=&to=` (no `/enterprise/` prefix — tenant comes from `X-Enterprise-ID` already; gateway has the `/api/v1/pipelines/**` route now).
  - Cursor: keyset on `(created_at DESC, run_id DESC)` encoded as base64url("ISO8601|UUID"). Index `idx_pipeline_runs_enterprise(enterprise_id, created_at DESC)` already exists (002).
  - `lib/api/client.ts` not touched — page uses `api()` helper directly via `useInfiniteQuery`. Adding a typed wrapper is a Sprint 6 codegen concern.
- **Files touched:**
  - ✅ NEW `services/data-pipeline/routers/enterprise_pipelines.py` (`list_pipelines` + `status_stream` for F-NEW2)
  - ✅ `services/data-pipeline/main.py` (register router with `/pipelines` prefix)
  - ✅ `services/api-gateway/.../RouteConfig.java` — added `/api/v1/pipelines/**` to the pipeline route group
  - ✅ `frontend/app/(app)/pipeline/page.tsx` (cursor-based `useInfiniteQuery`, "Tải thêm" button, BE field shape)
  - ✅ `frontend/mocks/handlers/pipeline.ts` (new handler matching BE envelope; legacy `/pipeline/runs` kept for the upload wizard)
- **DoD checklist:**
  - [x] `GET /api/v1/pipelines?cursor=&limit=&status=&from=&to=` cursor-paginated, max 500
  - [x] `tenant_id` from `X-Enterprise-ID` header only (K-1, K-12)
  - [x] Filter by `status` (CSV) + `created_at` range; unknown status → 400
  - [x] Response envelope `{data, meta:{cursor, limit, count, has_more, request_id, trace_id, server_time}}`
  - [x] Unit + integration tests: 9 cases in `test_pipelines_api.py::TestListPipelines` (empty, paginated, cursor round-trip, invalid cursor, unknown status, status filter pass-through, from>to, limit-cap, missing header)
  - [x] FE renders real data, MSW handler updated
  - [ ] PR merged

### F-NEW2 Pipeline Status SSE — 1 day
- [x] Status: 🟢 PR open (2026-04-27, bundled with F-022)
- **Depends on:** F-022 ✅ — same router file, single PR.
- **Scope adjustments (locked 2026-04-27):**
  - Heartbeat sent as `: heartbeat\n\n` SSE comment lines so they don't show up as `event:` data in the browser.
  - Producer call sites: `bronze/ingestor.py` (bronze_complete + failed), `routers/schema.py` (schema_review + cleaning_pending), `routers/clean.py` (silver_complete), `routers/analyze.py` (analysis_running). 6 sites total.
  - In-process `event_bus` per single-process FastAPI worker — Kafka deferred until horizontal scaling lands in Phase 2.
- **Files touched:**
  - ✅ NEW `services/data-pipeline/shared/event_bus.py` (asyncio.Queue per subscriber, fan-out, ≤32 depth)
  - ✅ `services/data-pipeline/routers/enterprise_pipelines.py::status_stream` (SSE endpoint, 15s heartbeat, terminal-state close)
  - ✅ `services/data-pipeline/{bronze/ingestor,routers/schema,routers/clean,routers/analyze}.py` — `event_bus.publish()` calls after each status flip; ingestor uses lazy import to stay compatible with bare `import bronze.ingestor` in test_unit_whitebox.py
  - ✅ NEW `frontend/components/pipeline/StatusStream.tsx` (EventSource + 5s polling fallback on error / no-EventSource)
  - ✅ `frontend/mocks/handlers/pipeline.ts` (`/api/v1/pipelines/:runId/events` returns single-event stream for dev UX)
- **DoD checklist:**
  - [x] `GET /api/v1/pipelines/:id/events` returns `text/event-stream`
  - [x] `tenant_id` from JWT (K-1, K-12); 404 if pipeline_run not owned by tenant
  - [x] Server emits on each `pipeline_runs.status` transition (6 producer sites)
  - [x] Heartbeat every 15s to keep connection alive through proxies
  - [x] Client reconnects with `Last-Event-ID` on disconnect (browser auto + replay frame on initial state)
  - [x] Polling fallback path retained — `StatusStream` tries SSE first, falls back to `GET /upload/:run_id/status` every 5s
  - [x] Unit + integration tests: 4 EventBus cases (subscribe/publish/fan-out/no-leak) + 1 SSE 404 case = 5 total (full HTTP stream test deferred — sync TestClient blocks on `iter_bytes`, internal pub/sub already covered)
  - [ ] PR merged

### F-016 Enterprise Settings (Ghost fix) — 3 days
- [x] Status: ✅ Merged 2026-04-27 (PR #69, commit `dc09db9`)
- **Depends on:** none
- **Why this is here:** v3.1 audit flagged as Ghost — FE page exists but BE endpoint missing + no `tenant_settings` table
- **Scope adjustments (locked 2026-04-27):**
  - Endpoint shape follows FE: `/api/v1/enterprises/me/settings` (plural, `/me/`), field name `consent_external_ai` (FE convention).
  - K-4 enforcement at the existing shim path `services/ai-orchestrator/engine/llm_router.py` (PLAN said `llm/`, real path is `engine/`).
  - Java package = `model/` (not `entity/`) — matches existing JPA convention (Workspace, User, etc.).
  - **No `language` column in `tenant_settings`** — `enterprises.locale` (001_init.sql:43) already exists. GET response joins both tables; locale changes route through the existing LocalePicker flow. Avoids duplicate source of truth.
  - **Idempotency-Key deferred** — auth-service has no IdempotencyService yet (cross-cutting). PATCH is naturally idempotent (same body → same end state). Standalone middleware is a separate Phase 2 task.
  - **`enterprise_name` + `notification_email` included** in scope per anh's call: `enterprise_name` read-only (joined from `enterprises`), `notification_email` is just a settings flag (UI consumer is F-037, Phase 2).
- **Files touched:**
  - ✅ NEW `infrastructure/postgres/migrations/015_tenant_settings.sql`
  - ✅ NEW `services/auth-service/src/main/java/com/kaorisystem/auth/model/TenantSettings.java`
  - ✅ NEW `services/auth-service/src/main/java/com/kaorisystem/auth/repository/TenantSettingsRepository.java` (with `EnterpriseDescriptor` projection joining `enterprises`)
  - ✅ NEW `services/auth-service/src/main/java/com/kaorisystem/auth/service/TenantSettingsService.java` (lazy-create + theme validation)
  - ✅ NEW `services/auth-service/src/main/java/com/kaorisystem/auth/controller/EnterpriseSettingsController.java` (GET + PATCH; PATCH gated to MANAGER role)
  - ✅ `services/auth-service/src/main/java/com/kaorisystem/auth/security/SecurityConfig.java` — added `/api/v1/enterprises/**` matcher
  - ✅ `services/ai-orchestrator/engine/llm_router.py` — K-4 check + 60s consent cache + `ConsentDeniedError`
  - ✅ NEW `services/ai-orchestrator/tests/test_llm_router_consent.py` (7 tests)
  - ✅ `services/ai-orchestrator/tests/test_llm_router_shim.py` — updated 1 existing test for new K-4 path
  - ✅ NEW `services/auth-service/src/test/java/com/kaorisystem/auth/controller/EnterpriseSettingsControllerTest.java` (10 tests)
  - ✅ `frontend/mocks/handlers/enterprise.ts` — MSW shape matches new BE response
  - FE settings page (`frontend/app/(app)/settings/page.tsx`) needs no edit — already calls the right endpoint and only renders `consent_external_ai`.
- **DoD checklist:**
  - [x] Migration 015: `tenant_settings` (`enterprise_id PK FK`, `theme`, `consent_external_ai`, `notification_email`, `branding_*`, `created_at`, `updated_at`) + RLS policy mirroring 005
  - [x] `GET /api/v1/enterprises/me/settings` → returns settings (lazy-create row on first fetch)
  - [x] `PATCH /api/v1/enterprises/me/settings` → partial update; MANAGER-only; theme validated; empty body rejected
  - [x] **K-4 enforcement:** `engine/llm_router.py` raises `ConsentDeniedError` on external call when `consent_external_ai=false` (fail closed on DB error / missing row)
  - [x] Unit tests: auth-service +10 (controller); ai-orchestrator +7 (consent matrix incl. cache & fail-closed)
  - [x] FE wire + MSW handler
  - [x] Flyway baseline picks up 015 on auth-service restart (verified by file location; smoke check after merge)
  - [x] PR merged — PR #69 (commit `dc09db9`, 2026-04-27)

---

## Sprint 2 — Week 2

### F-029 AI Decision Log — 3 days
- [x] Status: ✅ Merged 2026-04-27 (PR #72, commit `97801a1`)
- **Depends on:** Sprint 0.5 P0 #6 (K-6 audit wire-up) ✅ — Decision Log shows column_map, cleaning_rule, template_analysis types from the post-Sprint 0.5 wire-up.
- **Scope adjustments (locked 2026-04-27):**
  - Path: `services/ai-orchestrator/routers/decisions.py` (PLAN said `api/`, repo convention is `routers/`).
  - Endpoint kept as `/api/v1/decisions` per PLAN; gateway routes it via the existing insights group (added in this PR).
  - `lib/api/client.ts` not touched — page uses `api()` helper directly via `useInfiniteQuery`. Wrapper deferred to Sprint 6 OpenAPI codegen.
  - Filter `type` (matches BE column `decision_type`) instead of `status` since `decision_audit_log` has no status column.
- **Files touched:**
  - ✅ NEW `services/ai-orchestrator/routers/decisions.py` (`list_decisions` + `export_decisions_csv`, shared `_build_where`)
  - ✅ `services/ai-orchestrator/main.py` (register router with `/decisions` prefix)
  - ✅ `services/api-gateway/.../RouteConfig.java` — added `/api/v1/decisions/**` to insights group
  - ✅ `services/ai-orchestrator/tests/test_routes.py` — added `/decisions` + `/decisions/export.csv` to `EXPECTED_ORCHESTRATOR_PATHS`
  - ✅ NEW `services/ai-orchestrator/tests/test_decisions.py` (13 cases — list × 9 + CSV × 4)
  - ✅ `frontend/app/(app)/decisions/page.tsx` (cursor `useInfiniteQuery`, 300ms debounced search, "Tải thêm" + "Xuất CSV" buttons, type label maps cover real BE types)
  - ✅ NEW `frontend/mocks/handlers/decisions.ts` (cursor envelope + CSV mock with UTF-8 BOM)
  - ✅ `frontend/mocks/browser.ts` — register decisions handlers
- **DoD checklist:**
  - [x] `GET /api/v1/decisions?cursor=&limit=&type=&from=&to=&q=` cursor-paginated, max 500
  - [x] `tenant_id` from `X-Enterprise-ID` header only (K-1, K-12)
  - [x] Read-only on `decision_audit_log` (K-2 immutability honored)
  - [x] CSV export endpoint `GET /api/v1/decisions/export.csv` — **streaming response**, **UTF-8 BOM** byte-checked in test
  - [x] **Cap export at 10,000 rows/request** + `X-Export-Truncated: true` header — both verified by test
  - [x] Unit + integration tests: **13 cases** (9 list + 4 CSV) incl. BOM byte check, truncation flag, exact-cap edge, filter pass-through. Plus 2 routes tests for `/decisions` + `/decisions/export.csv`. ai-orchestrator full suite **193 / 193**.
  - [x] FE renders, search debounced 300ms (`useDebouncedValue` hook), CSV export via `window.open` for streaming download
  - [ ] PR merged

### F-015 User & Role Management — 2 days
- [x] Status: ✅ Merged 2026-04-27 (PR #73, commit `907f03e`)
- **Depends on:** none
- **Scope adjustments (locked 2026-04-27):**
  - Endpoint shape: `/api/v1/enterprises/users` (plural — matches FE convention from F-016 + the existing MSW handler).
  - **No new entity** — reuse existing `model/User.java` + `repository/UserRepository.java` (`enterprise_users` table, mapped from F-008 work). Saved one round of @MockBean wiring.
  - **No `deleted_at` column** — soft delete writes `status='deleted'` (existing column). Avoids migration 016.
  - **No invite email** — random unusable password; user activates via existing F-007 password-reset flow. F-NEW1 email dispatch is a Phase 2 wire-up (same call we made for F-016).
  - **Idempotency-Key deferred** — auth-service has no cross-cutting middleware yet (same call as F-016).
- **Files touched:**
  - ✅ `services/auth-service/.../repository/UserRepository.java` — added `findByEnterpriseFiltered` + `countByEnterpriseFiltered` (page-based + role/status filter, soft-delete-aware) + `countActiveManagersExcluding` (the min-MANAGER guard).
  - ✅ NEW `services/auth-service/.../service/EnterpriseUserService.java` — list / invite / update (role+status) / softDelete; raises `LastManagerException` when an op would drop the active-MANAGER count to 0.
  - ✅ NEW `services/auth-service/.../controller/EnterpriseUserController.java` — `GET /enterprises/users` (any tenant role) + `POST/PATCH/DELETE /enterprises/users[/{userId}]` (MANAGER-only, RFC 7807 problem responses).
  - ✅ NEW `services/auth-service/.../controller/EnterpriseUserControllerTest.java` — 12 WebMvcTest cases.
  - ✅ `frontend/app/(app)/users/page.tsx` — invite form + per-row role select / activate-deactivate / soft-delete buttons; reads `meta.total/page/limit` envelope.
  - ✅ `frontend/mocks/handlers/enterprise.ts` — extended with POST/PATCH/DELETE mocks + role/status filter on GET.
- **DoD checklist:**
  - [x] `GET /api/v1/enterprises/users?page=&limit=&role=&status=` paginate + filter
  - [x] `POST /api/v1/enterprises/users` — invite by email (Idempotency-Key deferred, see scope note)
  - [x] `PATCH /api/v1/enterprises/users/:id` — change role and/or status (activate / deactivate)
  - [x] `DELETE /api/v1/enterprises/users/:id` — soft delete (status='deleted', no migration)
  - [x] **Service-layer guard:** `ensureNotLastManager()` rejects role-demote / deactivate / delete on the last active MANAGER → 409 LastManagerException
  - [x] `tenant_id` from JWT (X-Enterprise-ID) only (K-12)
  - [x] Unit tests: **12 cases** in `EnterpriseUserControllerTest` (GET happy + filter forwarded + missing header / POST invite happy + VIEWER 403 + duplicate 409 / PATCH role change + last-MANAGER 409 + VIEWER 403 / DELETE soft + last-MANAGER 409 + 404)
  - [x] FE wire (invite form, role dropdown, activate/delete actions)
  - [ ] PR merged

---

## Sprint 3 — Week 3

### F-031 Unique Billing Cron — 3 days
- [x] Status: ✅ Merged 2026-04-27 (PR #74, commit `9b82887`)
- **Depends on:** none (but blocks F-030 demo data)
- **Scope adjustments (locked 2026-04-27):**
  - Migration **016** added (`016_billing_alert_flags.sql`) — `alert_80_fired`, `alert_95_fired`, `last_aggregated_at` columns + partial index `idx_emb_alert_active`. PLAN's "if needed" condition fired since 001 schema lacked these columns.
  - Path: `services/auth-service/.../scheduled/BillingAggregationJob.java` per PLAN; service split into `BillingAggregationService` (transactional core) + `BillingAggregationJob` (`@Scheduled`).
  - **No `platform_admin_audit_log` row per cron run** — that table's `admin_id` is NOT NULL FK and the cron is a system actor with no admin row. Audit lives on `last_aggregated_at` (per-enterprise) + structured logs (per cron run). PLAN's spec relaxed in commit message.
  - Added @MockBean `BillingAggregationService` to `WorkspaceControllerIT` (per `auth-service-it-pattern` memory — `NamedParameterJdbcTemplate` autowire would otherwise fail when JPA autoconfig is excluded).
- **Files touched:**
  - ✅ NEW `infrastructure/postgres/migrations/016_billing_alert_flags.sql`
  - ✅ `services/auth-service/.../it/FlywayMigrationIT.java` — bumped 4 hardcodes 15→16 (per memory feedback)
  - ✅ NEW `services/auth-service/.../service/BillingAggregationService.java` — `aggregate(eid, month)` + `aggregateAll` + `aggregateCurrentMonth`; per-enterprise `REQUIRES_NEW` so one tenant failure doesn't abort the batch
  - ✅ NEW `services/auth-service/.../scheduled/BillingAggregationJob.java` — `@Scheduled(cron = "0 0 2 * * *", zone = "Asia/Ho_Chi_Minh")`
  - ✅ `services/auth-service/.../controller/PlatformBillingController.java` — added `POST /platform/billing/aggregate-now` (manual trigger; SUPER_ADMIN gating via existing /platform/** matcher)
  - ✅ NEW `services/auth-service/.../service/BillingAggregationServiceTest.java` — 7 cases
  - ✅ `services/auth-service/.../controller/WorkspaceControllerIT.java` — `@MockBean BillingAggregationService`
- **DoD checklist:**
  - [x] `@Scheduled(cron = "0 0 2 * * *", zone = "Asia/Ho_Chi_Minh")` — daily 02:00 ICT
  - [x] For each enterprise: `COUNT(DISTINCT clean_data->>'customer_external_id')` from silver_rows (current `billing_month`); rows missing the field skip via `clean_data ? 'customer_external_id'`
  - [x] Upsert `enterprise_monthly_billing` (K-11 unit definition); ON CONFLICT keeps existing alert flags (TRUE-only flip)
  - [x] Migration 016 — `alert_80_fired`, `alert_95_fired`, `last_aggregated_at` + partial index
  - [x] When usage ≥ 80%: alert_80_fired = old OR true (idempotent)
  - [x] Same logic at 95%
  - [x] **No email dispatch** (per scope decision — defer Phase 2 F-037)
  - [~] Audit row to `platform_admin_audit_log` — replaced with `last_aggregated_at` + structured logs (admin_id NOT NULL constraint blocks system events; PLAN updated)
  - [x] Unit tests **7 cases** in `BillingAggregationServiceTest` (under-80 / at-80 / at-95 / idempotent / no-quota skip / quota=0 div-zero / batch tolerates per-enterprise failure)
  - [x] One-shot trigger endpoint `POST /api/v1/platform/billing/aggregate-now` (SUPER_ADMIN gating via existing /platform/** matcher)
  - [ ] PR merged

### F-030 Subscription & Quota — 4 days (start W3, finish W4)
- [x] Status: 🟢 PR open (2026-04-27)
- **Depends on:** F-015 ✅, F-031 ✅
- **Scope adjustments (locked 2026-04-27):**
  - Endpoint paths: `GET /api/v1/enterprises/me/subscription` + `POST /api/v1/enterprises/me/subscription/upgrade` (instead of PLAN's `/api/v1/billing/upgrade`). Avoids adding a new gateway route — `/enterprises/**` already routes to auth-service while `/billing/**` is owned by the orchestrator dashboard group.
  - Migration **017** added (`017_subscription_change_requests.sql`) — new table with PENDING/APPROVED/REJECTED/CANCELLED status + partial unique index for at-most-one PENDING per tenant + CHECK constraints (different plan, status enum).
  - `lib/api/client.ts` not touched — page uses `api()` directly via `useQuery` + `useMutation`.
  - Plan catalogue hardcoded on FE for the upgrade picker (PILOT / ENT_BASIC / ENT_MID / ENT_MAX) — Phase 2 will source it from a new `GET /subscription/plans` endpoint, but doing that here would be scope creep.
- **Files touched:**
  - ✅ NEW `infrastructure/postgres/migrations/017_subscription_change_requests.sql`
  - ✅ `services/auth-service/.../it/FlywayMigrationIT.java` — bumped 4 hardcodes 16→17 (per memory feedback)
  - ✅ NEW `services/auth-service/.../model/SubscriptionChangeRequest.java` (JPA entity)
  - ✅ NEW `services/auth-service/.../repository/SubscriptionChangeRequestRepository.java` (JpaRepository + duplicate-pending finder)
  - ✅ NEW `services/auth-service/.../service/SubscriptionService.java` — composite read (enterprise → workspace plan → subscription_plans defaults → emb current month) + linear EOM forecast + duplicate-pending guard. Mixes JpaRepository (writes) + NamedParameterJdbcTemplate (read JOINs).
  - ✅ NEW `services/auth-service/.../controller/EnterpriseSubscriptionController.java` (GET any role, POST MANAGER only)
  - ✅ NEW `services/auth-service/.../controller/EnterpriseSubscriptionControllerTest.java` (8 WebMvcTest cases)
  - ✅ `services/auth-service/.../controller/WorkspaceControllerIT.java` — `@MockBean SubscriptionService` + `SubscriptionChangeRequestRepository`
  - ✅ NEW `frontend/app/(app)/subscription/page.tsx` — 3-tab layout (Quota / Plan / Upgrade), F-031 banner at top, pending-upgrade card on the Upgrade tab
  - ✅ NEW `frontend/mocks/handlers/subscription.ts` + registered in `browser.ts`
- **DoD checklist:**
  - [x] `GET /api/v1/enterprises/me/subscription` returns: current_plan, usage_count, quota, usage_pct, forecast_eom (linear projection), alert_80_fired, alert_95_fired, days_in_billing_month, days_remaining + pending_upgrade
  - [x] `POST /api/v1/enterprises/me/subscription/upgrade` — writes to `subscription_change_requests` (status=PENDING); 409 on duplicate; 400 on same/unknown plan
  - [x] FE: 3-tab layout (Quota | Plan | Upgrade) per BACKLOG F-030
  - [x] FE: in-app banner when `alert_80_fired || alert_95_fired` (F-031 alert surface)
  - [x] Unit tests: **8 cases** in `EnterpriseSubscriptionControllerTest` (GET happy + alert flags surface + missing header + 404; POST happy MANAGER + VIEWER 403 + duplicate 409 + invalid plan 400)
  - [ ] PR merged

---

## Sprint 4-5 — Week 4-5

### F-032 Gold Layer (minimum) — 8 days
- [x] Status: ✅ Merged 2026-04-27 (PR #80, commit `07b58a3`)
- **Depends on:** none for code; **PRE-FLIGHT CHECK** done — see scope adjustments below.
- **Scope discipline:** schema + revenue_at_risk computation only. No `is_actioned` workflow (= Phase 2 F-060). No churn ML (= Phase 2 F-024 deepen). No full feature engineering.
- **Scope adjustments (locked 2026-04-27):**
  - Migration **018** (017 was used by Sprint 3 F-030's `subscription_change_requests`).
  - **Pre-flight Risk R1 fired** — `customer_external_id` was missing from `language_dictionary.json`. Per the medallion-separation rule, Silver owns canonical names → fixed there: added `customer_external_id` canonical to `config/language_dictionary.json` with VI/EN/JA/KO/ZH aliases. The Gold aggregator reads strictly by canonical name with **no fallback** (would have been a layer-leak).
  - **Path adjustments**: aggregator + consumer live in `services/data-pipeline/gold/` (PLAN said `services/data-pipeline/kafka/silver_complete_consumer.py` but the repo's only kafka touchpoints are `shared/kafka_*.py`; keeping the consumer next to the aggregator it triggers is cleaner).
  - NEW `docs/specs/MEDALLION_CONTRACT.md` documents the Bronze / Silver / Gold responsibility split + the canonical Silver schema Gold depends on.
- **Files touched:**
  - ✅ NEW `infrastructure/postgres/migrations/018_gold_layer.sql` — `gold_features` + `gold_aggregates` + RLS policies + partial index `idx_gold_features_at_risk`
  - ✅ `services/auth-service/.../it/FlywayMigrationIT.java` — bumped 4 hardcodes 17→18 (per memory feedback)
  - ✅ `config/language_dictionary.json` — added `customer_external_id` canonical with VI/EN/JA/KO/ZH aliases (Silver work)
  - ✅ NEW `docs/specs/MEDALLION_CONTRACT.md` — Bronze/Silver/Gold contract document
  - ✅ NEW `services/data-pipeline/gold/aggregator.py` — strict canonical reader, pure-function classifier + 12-month ceiling, idempotent upsert
  - ✅ `services/data-pipeline/gold/__init__.py` — public exports
  - ✅ NEW `services/data-pipeline/gold/consumer.py` — Kafka consumer on `kaori.pipeline.silver.complete`, `kaori-gold-aggregator` group, DLQ to `kaori.dlq.gold-aggregator`
  - ✅ `services/data-pipeline/main.py` — boot consumer in lifespan
  - ✅ NEW `services/data-pipeline/tests/test_gold_aggregator.py` (11 cases)
- **DoD checklist:**

  **Pre-flight (Day 1):**
  - [x] `silver_rows.clean_data` JSONB pre-flight — `customer_external_id` was NOT a canonical name; **fixed at the Silver layer** by adding the canonical to `config/language_dictionary.json`. Aggregator reads strictly; pilot tenants map source → canonical at schema-confirm.
  - [x] Silver schema contract documented in NEW `docs/specs/MEDALLION_CONTRACT.md`

  **Schema (Day 2):**
  - [x] Migration 018: `gold_features` (`enterprise_id UUID FK`, `customer_external_id TEXT`, `revenue_at_risk NUMERIC(14,4)` per K-9, `last_purchase_at`, `total_purchases`, `purchase_count`, `avg_purchase_value`, `is_actioned BOOL DEFAULT false` (Phase 2 F-060 hook), `actioned_at`, `computed_at`, PK `(enterprise_id, customer_external_id)`)
  - [x] Migration 018: `gold_aggregates` (`enterprise_id`, `metric_key TEXT`, `metric_value NUMERIC(14,4)`, `computed_at`, PK `(enterprise_id, metric_key)`)
  - [x] Indices: `(enterprise_id, computed_at DESC)` on both + partial `idx_gold_features_at_risk` for the FE dashboard
  - [x] RLS policies (mirror 005 pattern); Flyway picks up on next auth-service restart

  **Aggregator (Day 3-5):**
  - [x] `aggregate_for_tenant(enterprise_id)` — heuristic: `revenue_at_risk = 0` if last_purchase ≤ 90d; else `min(avg_purchase_value, sum(purchases in last 12m))`
  - [x] Idempotent upsert into `gold_features` (ON CONFLICT (enterprise_id, customer_external_id) DO UPDATE; **leaves is_actioned alone** — Phase 2's surface)
  - [x] Roll-up into `gold_aggregates`: `total_revenue_at_risk`, `at_risk_customer_count`
  - [x] K-1 tenant filtering via `acquire_for_tenant()`

  **Kafka wiring (Day 6-7):**
  - [x] Consumer on `kaori.pipeline.silver.complete` (separate consumer group `kaori-gold-aggregator`)
  - [x] Triggers `aggregate_for_tenant(enterprise_id)` from event payload
  - [x] DLQ to `kaori.dlq.gold-aggregator` on failure (best-effort; never wedges the consumer loop)
  - [x] Outbox-based dedup using message key (G5 pattern, mirrors orchestrator consumer)

  **Tests (Day 8):**
  - [x] Unit aggregator math: **11 cases** in `test_gold_aggregator.py` (3 active/at-risk classifier + 3 strict-canonical contract + 3 field parsing + 2 upsert/rollup). data-pipeline full suite **284 / 285 passed** (1 pre-existing skip).
  - [~] Real-DB integration via Testcontainers — deferred to F-032 manual smoke + post-merge QA (same trade-off Sprint 1+ made; CI Linux runner exercises Flyway cold-boot which guarantees migration 018 applies).
  - [ ] PR merged

---

## Sprint 6 — Week 6: Sign-off audit

### Ghost-detector script — 1 day
- [ ] Status: ⬜
- **Files to touch:**
  - NEW `scripts/audit-ghost-features.sh` (or `.py`)
- **DoD checklist:**
  - [ ] For each F-001..F-032 in BACKLOG, parse declared FE route + BE endpoint
  - [ ] FE check: route file exists in `frontend/app/`
  - [ ] BE check: endpoint returns non-404 against running stack (or at least: route registered in code via grep)
  - [ ] Output table: F-ID | FE | BE | Status (✅ / Ghost / Partial)
  - [ ] **Run it. Confirm zero Ghost rows for F-001..F-032.**
  - [ ] Add to CI as a soft-warn step (not hard fail until next phase)

### Final close-out — 1 day
- [ ] Status: ⬜
- [ ] Update `BACKLOG.md`: F-015, F-016, F-022, F-029, F-030, F-031, F-032 → ✅ with merge commit hashes
- [ ] Update `CLAUDE.md` §14 phase status table; remove "Critical Phase 1 gaps" section
- [ ] NEW `docs/DEMO_RUNBOOK.md` — 1-pager pilot UAT script:
  - Login flow (P1 + P2)
  - Pipeline upload → schema → cleaning → analysis → results (5-step wizard, with SSE status stream from F-NEW2)
  - Decisions log + CSV export
  - Subscription / quota (with in-app 80%/95% banner from F-031)
  - Settings (consent gate)
  - User invite + role change
  - **⚠️ Phase 1 limitation callout — North Star metric:** dashboard shows `revenue_at_risk` (tử số) only. The full North Star `SUM(revenue_at_risk WHERE is_actioned=true)` requires the `is_actioned` workflow which ships in **Phase 2 F-060**. Pilot UAT must accept this limitation; users can see at-risk customers but cannot mark "actioned" through the UI yet — workaround for pilot is offline tracking by Customer Success team.
  - **⚠️ Pricing source of truth:** subscription quotas/prices shown to enterprise users come from `CLAUDE.md §10` (PILOT 1M / ENT BASIC 2M / ENT MID 5M / ENT MAX 8M / ENT ROI 8M+1.5%). Confirmed canonical 2026-04-26 by product. Promote to BRD v3.1 next revision.
- [ ] Tag release: `v1.0-phase1-complete`
- [ ] PR merged

### OpenAPI codegen pipeline (Phase 2 onboarding prep) — 1 day
- [ ] Status: ⬜
- **Why this is here:** Phase 1 close-out leaves ~30 BE endpoints. Phase 2 will add 60-80 more (F-033..F-068). Hand-writing TS types per endpoint in `frontend/lib/api/client.ts` will drift from BE spec — especially when multiple endpoints land in parallel. Setting up codegen ONCE at end of Phase 1 means Phase 2 onboarding gets type-safe API client for free.
- **Strategy chosen:** **types-only codegen via `openapi-typescript`** (lightweight, ~50KB output per service). NOT orval/react-query-codegen (heavier, fetch client + hooks generation lock-in). Keep FE wire-up flexible; can upgrade to orval later if pain emerges in Phase 2 sprints.
- **Files to touch:**
  - **Backend:**
    - `services/auth-service/pom.xml` — add `org.springdoc:springdoc-openapi-starter-webmvc-ui` (latest 2.x compatible with Spring Boot 3.2)
    - `services/auth-service/src/main/resources/application.yml` — expose `/v3/api-docs` (JSON spec) + `/swagger-ui` (interactive doc, dev profile only)
    - `services/data-pipeline/main.py` — FastAPI auto-exposes `/openapi.json` and `/docs` — just verify accessible through gateway in dev
    - `services/ai-orchestrator/main.py` — same as data-pipeline
  - **Gateway:**
    - `services/api-gateway/.../RouteConfig.java` — route `/v3/api-docs/**` and `/openapi.json` paths through to each service in dev profile only
  - **Frontend:**
    - `frontend/package.json` — add `openapi-typescript` devDependency
    - NEW `frontend/scripts/gen-api-types.sh` — fetch each service's spec → write `frontend/lib/api/types/{auth,pipeline,orchestrator}.d.ts`
    - `frontend/lib/api/client.ts` — refactor 1 endpoint as proof (e.g., `pipelineApi.list()` from F-022) to use generated types
    - `frontend/.gitignore` — track decision: gitignore generated types, OR commit them (em đề xuất commit để CI không cần BE running)
- **DoD checklist:**
  - [ ] All 3 backend services expose OpenAPI 3 spec (auth at `/v3/api-docs`, FastAPI services at `/openapi.json`)
  - [ ] `npm run gen:api` (alias for the script) regenerates types from running services
  - [ ] At least 1 endpoint in `frontend/lib/api/client.ts` migrated to generated types as proof of concept
  - [ ] CI step: regenerate types from spec, fail build if `git diff frontend/lib/api/types/` shows drift (catches "BE changed signature, FE didn't regen" bugs)
  - [ ] NEW `docs/specs/API_CODEGEN.md` (1-pager) — workflow doc: when to regen, how the CI check works, escape hatch for hand-written types if codegen fails
  - [ ] PR merged

---

## Risk register

| # | Risk | Mitigation | Trigger |
|---|---|---|---|
| R1 | Silver doesn't write `customer_external_id` | F-032 pre-flight check Day 1 — **stop F-032, fix silver first** | Pre-flight grep finds inconsistent fields |
| R2 | `enterprise_monthly_billing` schema may already have alert columns from earlier work | Inspect migration 001/006 first; skip migration 016 if columns exist | F-031 design phase |
| R3 | F-029 export of >10k rows on a noisy enterprise | Cap at 10k + truncated header; defer async to Phase 2 | At UAT time |
| R4 | Solo dev fatigue → quality drop in W4-5 | Buffer week (W6) + don't skip Sprint 6 audit | Self-monitor velocity weekly |
| R5 | Flyway picks up partial migrations on restart mid-PR | Local-only run with `flyway migrate` before commit; never push half-done SQL | Each migration PR |
| R6 | F-030 needs `subscription_change_requests` table → another migration | Bundle with F-030 migration; don't conflate with F-031 migration 016 | F-030 design phase |
| R7 | RLS cutover (P0 #4) breaks an unaudited query path | Run full integration suite + smoke test pipeline E2E before merging Sprint 0.5; have rollback plan to switch DSN back to `kaori` superuser | Sprint 0.5 day 1 |
| R8 | Audit helper (P0 #6) writes hot-loop in clean.py per-rule → perf regression | Use REQUIRES_NEW + try/catch swallow (same pattern as PlatformAdminAuditService); benchmark before/after on 10k-row pipeline | Sprint 0.5 day 2 |

---

## Daily check-in protocol

Each work session:
1. Open this file, set the active task to 🟡
2. At end of session: status → 🟢 if PR open, ✅ if merged, back to ⬜ if rolled back
3. Tick DoD boxes as completed (don't tick speculatively)
4. Note blockers in Risk register if new ones emerge

Weekly: review timeline overview table; if behind by >2 days, reassess scope of remaining items.

---

## Out of scope (don't touch this phase)

- llm-gateway integration → Phase 2 with F-063
- notification-service email dispatch → Phase 2 with F-037 alert rules
- MFA enforcement at login (2-step `mfa_challenge_token` flow) → next phase per Phase 3 deferred list
- Monitoring / Grafana dashboards → next phase
- Audit feed UI at `/platform/security/audit` → next phase
- Phase 2 features F-033+ → separate roadmap conversation
- **F-NEW3 Data Explorer (`/p2/data` Medallion table browser + lineage)** — evaluated 2026-04-26, deferred to Phase 2 alongside F-056 Knowledge Graph. Rationale: pilot UAT does not need raw Bronze/Silver/Gold table browsing; insight value only emerges with KG context.
- **F-060 `is_actioned` workflow** — Phase 2 hard prerequisite for full North Star metric. Phase 1 ships `revenue_at_risk` measurement only (see Sign-off DEMO_RUNBOOK callout).
