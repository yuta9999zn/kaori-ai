# Kaori AI — Backend Tasks (per Target Group + Phase) + API Status Board

> **Version:** 1.0 · **Generated:** 2026-04-25 · **Mirrors `FRONTEND_TASKS_PHASE.md` structure**
> **Sources:**
> - `docs/product/Feature_Tree_Kaori_AI_v3.1.xlsx` — API Catalog (108 endpoints), Phase 1 Reality Check, Screen Status Summary
> - `docs/BACKLOG.md` (incl. v3.1 Reconciliation section)
> - `docs/phase_1_execution.md` — Real status from code audit
> - `docs/ARCHITECTURE_REVIEW.md` — P0 defects
>
> **Convention:** Backend task IDs follow `BE-{GROUP}-{NNN}` where group ∈ {PT, EU, ST, PE, SH, BL}. Phase per task = phase tag from authoritative screen sheet (see reconciliation §0.1).
>
> **Companion docs:**
> - `docs/FRONTEND_TASKS_PHASE.md` — frontend tasks per group (FE-XXX-### IDs)
> - `docs/BACKLOG.md` — feature catalog (F-001..F-092 + F-NEW1..F-NEW3)

---

## Table of Contents

- [0. Reconciliation & Status Legend](#0-reconciliation--status-legend)
- [1. Platform Tenant (PT) — Backend](#1-platform-tenant-pt--backend)
- [2. Enterprise User (EU) — Backend](#2-enterprise-user-eu--backend)
- [3. Studio (ST) — Backend](#3-studio-st--backend)
- [4. Personal (PE) — Backend](#4-personal-pe--backend)
- [5. Cross-cutting Shared & Billing — Backend](#5-cross-cutting-shared--billing--backend)
- [6. ⭐ API Status Board (108 endpoints)](#6--api-status-board-108-endpoints)
- [7. Backend phase progress summary by group](#7-backend-phase-progress-summary-by-group)
- [8. P0 defects gating Phase 1 close](#8-p0-defects-gating-phase-1-close)

---

## 0. Reconciliation & Status Legend

### 0.1 Status legend (used throughout this doc + API Status Board)

| Symbol | Meaning |
|--------|---------|
| ✅ | **Done** — endpoint live, code in repo, integration tested, contract matches FE expectation |
| 🔄 | **Partial** — endpoint exists OR logic exists but NOT both / not reachable / contract drift / unaudited path |
| ❌ | **Ghost** — claimed ✅ in trackers but no code OR endpoint registered but returns 404/403 unconditionally |
| ⬜ | **Pending** — not started, no code |
| 🔒 | **Blocked** — pending dependency on another F or P0 defect |
| ⚠️ | **Drift** — endpoint exists but contract diverges from CLAUDE.md or v3.1 spec |

### 0.2 Phase plan recap (mirror)

| Phase | Months | Theme | MRR target |
|-------|--------|-------|------------|
| Phase 1 | M1-M4 | MVP Retail · core platform | 10-40M VND |
| Phase 2 | M5-M12 | Scale + Intelligence | ≥100M VND |
| Phase 3 | M13-M24 | Enterprise + Compliance + SEA | ≥500M VND |

### 0.3 Target groups overview (mirror)

| Group | Code | Backend services | Phase activation | Endpoints owned |
|-------|------|------------------|------------------|-----------------|
| **Platform Tenant** | PT | auth-service (P1 routes), api-gateway, billing-service | Phase 1 (foundational) | 17 (Phase 1) + 3 (Phase 2) + 4 (Phase 3) |
| **Enterprise User** | EU | auth-service (P2 routes), data-pipeline, ai-orchestrator | Phase 1+2+3 | 32 (Phase 1) + 21 (Phase 2) + 7 (Phase 3) |
| **Studio** | ST | studio-service (NEW Phase 2), model-registry, training-pipeline | Phase 2 only | 10 (Phase 2) |
| **Personal** | PE | personal-service (NEW Phase 2), reuses pipeline + analysis | Phase 2 only | 8 (Phase 2) |
| Shared/Billing | SH/BL | llm-gateway, medallion-engine, charts, billing-service, mcp-server, audit-service | Phase 1-3 | 16 (Phase 1) + 8 (Phase 2) + 2 (Phase 3) |
| **Total** | | | | **108 endpoints** |

### 0.4 v3.1 reconciliation summary

Cross-checked v3.1 API Catalog vs. BACKLOG.md (built from v3.0). Findings already applied to `BACKLOG.md` § "v3.1 Reconciliation":
- **NEW: F-NEW3** Data Explorer (Phase 1) — `GET /enterprise/data/{layer}/tables` + `/lineage`
- **Amend** F-007 (add `mfa/verify`), F-011 (add `billing/alerts`), F-025 (add `insights/{id}`), F-027 (add `charts/catalog`)
- **Move phase** F-087 Branding 3→2; F-082/F-083 Billing/Payment 3→2 (e-invoice stays 3); F-078 Audit (writer 1, query UI 2)
- **Phase tags reaffirmed** (v3.1 catalog mis-tagged): Frameworks, Decision Override, Reports, Auto-DB, all P3 Studio, all P4 Personal — all Phase 2 in BACKLOG, NOT Phase 1

---

## 1. Platform Tenant (PT) — Backend

> **Owning services:** `auth-service` (port 8091, Java Spring Boot) for P1 admin routes · `api-gateway` (port 8080) for routing + JWT extraction · `billing-service` (Phase 2, currently inside data-pipeline cron stub) · `notification-service` (port 8094) for admin alerts.
>
> **Phase 1 active:** 17 endpoints across 6 modules. **Real status: 9 ⬜/❌ pending vs ~6 ✅ done — see API Status Board §6.1.**

### 1.1 Module 1.0 — Authentication backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/auth/login` | POST | 1 | ✅ | F-002, F-007 | _shipped_ |
| `/api/v1/platform/auth/mfa/verify` | POST | 1 | 🔄 | F-007 | **BE-PT-001** Build TOTP verify (speakeasy/pyotp) + backup-code consumption + audit `MFA_VERIFY_*` events |
| `/api/v1/platform/auth/logout` | POST | 1 | ✅ | F-002 | _shipped_ (token blacklist working) |
| `/api/v1/platform/auth/sessions` | GET / DELETE | 2 | ⬜ | new (F-NEW) | **BE-PT-101** Sessions endpoint listing active refresh tokens; DELETE invalidates single session |

**Tables:** `users`, `mfa_tokens`, `admin_mfa_backup_codes` (NEW for backup codes), `refresh_tokens`, `token_blacklist`, `password_reset_tokens`.

**Edge cases backend must enforce:** TOTP replay protection (jti per token), backup code single-use, lockout 15min after 5 fails, IP whitelist check if configured.

### 1.2 Module 1.1 — Workspace Management backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/workspaces` | GET | 1 | ✅ | F-008 | _shipped_ (cursor pagination, filter by plan/status) |
| `/api/v1/platform/workspaces` | POST | 1 | 🔄 | F-008 | **BE-PT-002** Complete workspace creation transaction (tenant + first MANAGER + key issuance + audit) |
| `/api/v1/platform/workspaces/{id}` | GET | 1 | 🔄 | F-008 | **BE-PT-003** Aggregate detail endpoint (workspace + usage + billing + members) — currently returns shell |
| `/api/v1/platform/workspaces/{id}` | PATCH | 1 | 🔄 | F-008 | **BE-PT-004** Lifecycle action handler (activate/suspend/archive) with cascading effects (kick sessions, pause pipelines) + audit |
| `/api/v1/platform/workspaces/{id}` | DELETE | 1 | 🔄 | F-008 | **BE-PT-005** Soft delete + scheduled hard delete after 30d grace |

**Tables:** `tenants`, `workspace_plans`, `workspace_keys` (junction), `users`.

### 1.3 Module 1.2 — Private Key Management backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/keys` | POST | 1 | 🔄🔒 | F-009 | **BE-PT-006** Generate key (32-byte CSPRNG, format `KAORI-XXXX-XXXX-XXXX-XXXX`), SHA-256 store, return raw ONCE. **🔒 Blocked on SecurityConfig fix** (currently deny-all) |
| `/api/v1/platform/keys/{id}` | DELETE | 1 | 🔄🔒 | F-009 | **BE-PT-007** Revoke key + invalidate all derived refresh tokens + audit `KEY_REVOKED` |
| `/api/v1/platform/keys/{id}` | GET | 1 | ⬜ | F-009 (NEW endpoint) | **BE-PT-008** Detail with usage history (joins audit log) |
| `/api/v1/platform/workspaces/{id}/keys` | GET | 1 | ⬜ | F-009 (NEW endpoint) | **BE-PT-009** List keys for a workspace |

**Tables:** `workspace_keys` (key_hash, status, revoked_at, last_used_at, last_used_ip).

### 1.4 Module 1.3 — Platform Admin Management backend (auth-service)

> **❌ ALL GHOST.** F-010 claimed ✅ in tracker but `grep PlatformAdmin → 0 hits`. Frontend FE-PT-019..022 blocked.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/admins` | GET | 1 | ❌ | F-010 | **BE-PT-010** Build PlatformAdminController with list endpoint (filter by role/status/MFA) |
| `/api/v1/platform/admins/invite` | POST | 1 | ❌ | F-010 | **BE-PT-011** Invite endpoint sending email with TTL 72h token |
| `/api/v1/platform/admins/{id}` | PATCH | 1 | ❌ | F-010 | **BE-PT-012** Deactivate / role change / reset MFA — enforce ≥1 SUPER_ADMIN invariant |
| `/api/v1/platform/admins/{id}/reset-password` | POST | 1 | ❌ | F-010 | **BE-PT-013** Trigger reset email; SUPER_ADMIN reset requires another SUPER_ADMIN action |

**Tables:** `users` (with `portal=PLATFORM`), `platform_roles`, `audit_log`.

### 1.5 Module 1.4 — Billing Monitor backend (data-pipeline cron + auth-service query)

> **🔒 ALL BLOCKED on F-031 cron.** `kaori.billing.events` topic doesn't exist; `enterprise_monthly_billing` table empty.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/billing/monitor?month=` | GET | 1 | ⬜🔒 | F-011 | **BE-PT-014** Aggregate query across `enterprise_monthly_billing` + filter month + workspace; needs F-031 first |
| `/api/v1/platform/billing/alerts` | GET | 1 | ⬜🔒 | F-011 (NEW, v3.1) | **BE-PT-015** Workspaces >80% / >95% quota with derived urgency |
| `/api/v1/shared/billing/aggregate` | POST (cron) | 1 | ⬜ | F-031 | **BE-SH-001 (P0)** Daily cron 00:05 UTC: COUNT DISTINCT customer_external_id per (enterprise, month); upsert `enterprise_monthly_billing`; emit Kafka `kaori.billing.events`; alert on >80% / >95% |

**Tables:** `enterprise_monthly_billing` (immutable upsert per K-9), `pipeline_runs`, `analysis_runs`.

### 1.6 Module 1.5 — Pilot Conversion Tracking backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/pilot-conversion` | GET | 2 | ⬜ | F-066 | **BE-PT-102** Query view of tenants in pilot stage with D25/D30 trigger flags |
| `/api/v1/enterprise/onboarding/pilot/upgrade` | POST | 2 | ⬜ | F-066 | **BE-PT-103** Upgrade action: change tenant.plan + prorate + emit `kaori.billing.events` |

### 1.7 Module 1.6 — Platform Health Dashboard backend (api-gateway)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/health` | GET | 1 | ✅ | F-012 | _shipped_ (gateway actuator + custom KPIs) |
| `/api/v1/platform/metrics` | GET | 1 | ✅ | F-012 | _shipped_ (Prometheus-compatible) |
| `/api/v1/platform/health/layout` | PATCH | 2 | ⬜ | new | **BE-PT-104** Per-admin layout persistence |

### 1.8 Module 1.7 — Subscription Plans backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/plans` | GET | 2 | ⬜ | F-067 | **BE-PT-105** List plans (active + retired with `keep_history=true`) |
| `/api/v1/platform/plans` | POST | 2 | ⬜ | F-067 | **BE-PT-106** Create plan + soft-update preserves history (existing customers untouched) |
| `/api/v1/platform/plans/{id}` | PATCH | 2 | ⬜ | F-067 | **BE-PT-107** Edit creates new version; deactivate flag for retired |

**Tables:** `subscription_plans` (with `version`, `parent_plan_id`, `is_active`).

### 1.9 Module 1.8 — LLM & AI Provider Management backend (api-gateway → llm-gateway)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/platform/llm/providers` | GET | 2 | ⬜ | F-073 | **BE-PT-108** List configured providers + masked keys + status |
| `/api/v1/platform/llm/providers` | POST | 2 | ⬜ | F-073 | **BE-PT-109** Add provider config (Qwen/OpenAI/Claude/Gemini/Azure) with key vault integration |
| `/api/v1/platform/llm/providers/{id}/privacy-mode` | PATCH | 2 | ⬜ | F-073 | **BE-PT-110** Toggle data masking + external allow per tenant |
| `/api/v1/platform/llm/finetune` | POST | 3 | ⬜ | F-074 | **BE-PT-301** Submit fine-tune job to training-pipeline + run history |

**Tables:** `llm_provider_configs`, `llm_request_logs` (for cost tracking).

---

## 2. Enterprise User (EU) — Backend

> **Owning services:** `auth-service` (P2 auth + users + branding), `data-pipeline` (port 8092, FastAPI — pipelines + bronze/silver + auto-db + data explorer), `ai-orchestrator` (port 8093, FastAPI — analysis engines + insights + decisions + frameworks + reports + KG + workflows + agents).
>
> **Phase 1 active:** 32 endpoints across 14 modules. **Real status: ~7 done, ~12 partial/ghost, ~13 pending — see §6.2.**

### 2.1 Module 2.0 — Authentication backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/auth/login` | POST | 1 | ✅ | F-002 | _shipped_ |
| `/api/v1/enterprise/auth/activate/{token}` | POST | 1 | 🔄⚠️ | F-013 | **BE-EU-001** Resolve route mismatch (current `/auth/workspace/activate` vs spec `/enterprise/auth/activate/{token}`); reconcile contract |
| `/api/v1/enterprise/auth/sessions` | GET / DELETE | 2 | ⬜ | new | **BE-EU-101** Mirror PT sessions endpoint, scoped to enterprise users |

### 2.2 Module 2.0a — Authorization (RBAC + ABAC + Hybrid) backend (auth-service + middleware)

> **❌ F-014 GHOST.** JwtAuthFilter extracts role but never enforces it (no `@PreAuthorize`, no role predicate in gateway).

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| (RBAC middleware) | — | 1 | ❌ | F-014 | **BE-EU-002 (P0)** Wire `@PreAuthorize` annotations across enterprise controllers + gateway role predicate; add Cypress E2E coverage |
| `/api/v1/enterprise/authz/evaluate` | POST | 2 | ⬜ | F-064 | **BE-EU-201** Hybrid PDP service: RBAC + ABAC evaluation, return `{allow, reason, policy_id, missing_perms[]}` |
| `/api/v1/enterprise/authz/policies` | POST/GET/PATCH/DELETE | 2 | ⬜ | F-064 | **BE-EU-202** ABAC policy CRUD with versioning |
| `/api/v1/enterprise/authz/simulate` | POST | 2 | ⬜ | F-064 | **BE-EU-203** Simulate policy on sample requests (dry-run mode) |

### 2.3 Module 2.1 — Branding backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/branding` | GET / POST | 2 | ⬜ | F-087 (moved Phase 3→2) | **BE-EU-204** Logo storage (S3) + colors + theme + subdomain availability check + propagation to email/PDF templates |

**Tables:** `tenant_settings` (`branding_json`).

### 2.4 Module 2.2 — Onboarding backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/onboarding/activate-key` | POST | 1 | 🔄⚠️ | F-013 | **BE-EU-003** Standardize endpoint; ensure first MANAGER created with min-1 invariant |
| `/api/v1/enterprise/users/invite` | POST | 1 | 🔄 | F-013, F-015 | **BE-EU-004** Invite endpoint with email + token + role assignment |
| `/api/v1/enterprise/onboarding/pilot/upgrade` | POST | 2 | ⬜ | F-066 | (covered in BE-PT-103) |

### 2.5 Module 2.3 — Dashboard backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/dashboard/kpis` | GET | 1 | ✅ | F-028 | _shipped_ (5-state machine, KPI cards, quota) |
| `/api/v1/enterprise/dashboard/layout` | PATCH | 2 | ⬜ | new | **BE-EU-205** Per-user layout persistence |

### 2.6 Module 2.4 — User & Role Management backend (auth-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/users` | GET | 1 | ⬜ | F-015 | **BE-EU-005** List users with filter (role/status/last_login) + pagination |
| `/api/v1/enterprise/users/invite` | POST | 1 | ⬜ | F-015 | **BE-EU-006** Bulk invite endpoint (CSV-ready) |
| `/api/v1/enterprise/users/{id}` | PATCH / DELETE | 1 | ⬜ | F-015 | **BE-EU-007** Edit role / deactivate / delete; **enforce min 1 MANAGER invariant in DB transaction** |

### 2.7 Module 2.5 — Data Architecture backend (data-pipeline) — NEW (F-NEW3)

> **NEW for Phase 1.** No existing endpoints. Required by P2 screen 2.5 Data Explorer.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/data/{bronze\|silver\|gold}/tables` | GET | 1 | ⬜ | **F-NEW3** | **BE-EU-008 (NEW)** List tables per medallion layer with row count + last update + tenant filter (K-1) |
| `/api/v1/enterprise/data/lineage?table_id=` | GET | 1 | ⬜ | **F-NEW3** | **BE-EU-009 (NEW)** Build lineage trace Bronze→Silver→Gold from `column_mappings` + `silver_rows.source_run_id`; tenant-scoped |

**Tables read:** `bronze_files`, `silver_rows` (count grouped), `gold_features`, `column_mappings`. **Note:** Gold layer empty until F-032 lands.

### 2.8 Module 2.6 — Data Pipeline Wizard backend (data-pipeline)

> **✅ ALL DONE (F-017..F-021).** Phase 1 wizard fully shipped.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/data/bronze/upload` | POST | 1 | ✅ | F-017 | _shipped_ — note: row-by-row INSERT could be optimized post-Phase 1 |
| `/api/v1/enterprise/pipelines` | POST | 1 | ✅ | F-017 | _shipped_ |
| `/api/v1/enterprise/pipelines/{id}/steps/{1-5}/run` | POST | 1 | ✅ | F-018..F-021 | _shipped_ |
| `/api/v1/enterprise/pipelines/{id}/results` | GET | 1 | ✅ | F-021 | _shipped_ |
| `/api/v1/enterprise/pipelines/{id}/status` | GET | 1 | 🔄 | F-NEW2 | **BE-EU-010 (P0)** Status polling endpoint (currently stub); add SSE `/events` for real-time updates |
| `/api/v1/enterprise/pipelines` | GET | 1 | ⬜ | F-022 | **BE-EU-011** Pipeline run history list (filter by status/date, paginate) |

### 2.9 Module 2.7 — Auto Database Design backend (data-pipeline + ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/auto-db/analyze` | POST | 2 | ⬜ | F-057 | **BE-EU-206** AI schema analysis → 3NF/Star suggestions; uses LLM router |
| `/api/v1/enterprise/auto-db/suggestions/{id}/apply` | POST | 2 | ⬜ | F-057 | **BE-EU-207** Apply suggestion → CREATE TABLE migration + ERD JSON + form spec |

### 2.10 Module 2.8 — Multi-tier Data Analysis backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/analysis/basic` | POST | 1 | ✅ | F-023 | _shipped_ (statistical engine: summary_stats, distribution, correlation, time_series) |
| `/api/v1/enterprise/analysis/intermediate` | POST | 2 | 🔄 | F-024, F-033 | **BE-EU-208** Intermediate tier — extend statistical + add cohort + retention; multi-pipeline scope |
| `/api/v1/enterprise/analysis/advanced` | POST | 2 | 🔄 | F-024, F-033 | **BE-EU-209** Advanced tier — predictive (regression/classification) + causal + what-if; uses Gold features |

### 2.11 Module 2.9 — Analysis Frameworks backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/frameworks/generate` | POST | 2 | 🟡 | F-034 | **BE-EU-210** _shipped this branch_ — single endpoint with `framework_code` discriminator (swot/6w/2h/fishbone). Validates code against the Python registry (templates.py); 400 on unknown. Issue #3 `output_schema` validation per framework. K-4 `consent_external` per call. 202 + run_id; LLM call runs as `asyncio.create_task` — poll GET endpoint. Path is flat `/api/v1/frameworks/...` (not `/enterprise/frameworks/...`) to match the F-038 reports convention while /v2 routing stabilises |
| `/api/v1/frameworks/{run_id}` | GET | 2 | 🟡 | F-034 | **BE-EU-211** _shipped this branch_ — single run with `content_json`. Cross-tenant returns 404 (RLS) |
| `/api/v1/frameworks` | GET | 2 | 🟡 | F-034 | **BE-EU-211b** _shipped this branch_ — cursor-paginated list (`<created_at>\|<run_id>` cursor; same shape as reports) |
| `/api/v1/frameworks/templates` | GET | 2 | 🟡 | F-034 | **BE-EU-211c** _shipped this branch_ — static catalogue of built-ins for the FE hub gallery |
| `/api/v1/frameworks/custom` | POST | 2 | ⬜ | F-034 | **BE-EU-212** Custom framework runner (JSON-spec driven) — deferred to v1 follow-up |

### 2.12 Module 2.10 — Insights Engine backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/insights/generate` | POST | 1 | ✅ | F-025 | _shipped_ (3-tuyến: Chuyện gì · Tại sao · Nên làm gì) |
| `/api/v1/enterprise/insights/feed` | GET | 1 | ✅ | F-025 | _shipped_ |
| `/api/v1/enterprise/insights/{id}` | GET | 1 | 🔄 | F-025 (amendment) | **BE-EU-012** Add detail endpoint with citations + confidence + actionable links — currently missing per v3.1 reconciliation |
| `/api/v1/enterprise/insights/knowledge-base` | GET | 2 | ⬜ | new | **BE-EU-213** KB articles + tags + auto-citation linking |

**K-6 gap:** F-025 LLM calls currently NOT audit-logged. **BE-EU-013 (P0)** Wire decision_audit_log writes for every insight generation.

### 2.13 Module 2.11 — Risk Management backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/risks/auto-detect` | POST | 2 | ⬜ | F-039 | **BE-EU-214** Scan data → produce `risk_items` with prob × impact score |
| `/api/v1/enterprise/risks/{id}/escalate` | POST | 2 | ⬜ | F-039 | **BE-EU-215** Escalate to owner/manager + notification + audit |
| `/api/v1/enterprise/risks` | GET | 2 | ⬜ | F-039 | **BE-EU-216** List + filter + paginate |

### 2.14 Module 2.12 — Strategy Builder backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/strategy/okr` | POST | 2 | ⬜ | F-040 | **BE-EU-217** Create OKR/OGSM canvas; KR auto-link to gold features |
| `/api/v1/enterprise/strategy/{id}/timeline` | GET | 2 | ⬜ | F-040 | **BE-EU-218** Gantt timeline data + progress per KR |
| `/api/v1/enterprise/strategy/{id}/review-meetings` | GET / POST | 2 | ⬜ | F-040 | **BE-EU-219** Meeting CRUD + auto-populated KR delta notes |

### 2.15 Module 2.13 — Reports Management backend (ai-orchestrator)

> **Auto path shipped 2026-05-02 (PR #113).** Endpoints landed under `/api/v1/reports*` (not the spec's `/enterprise/reports/*`) to keep the FE migration window small — templates 47/48 already point at `/api/v1/reports`. Builder + distribution still ⬜.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/reports/generate` | POST | 2 | ✅ | F-038 | **BE-EU-220** _shipped PR #113_ — 202 + bg worker; uses Issue #3 `output_schema` validation, emits `kaori.reports.generated` (Issue #4), enqueues `notification_outbox` `report-ready` (Issue #6). Single-recipient (`owner_email`) v0; fan-out distribution = follow-up |
| `/api/v1/reports` | GET | 2 | ✅ | F-038 | **BE-EU-220a** _shipped PR #113_ — cursor-paginated list (`<iso>|<uuid>`), RLS-isolated, content_json omitted |
| `/api/v1/reports/{id}` | GET | 2 | ✅ | F-038 | **BE-EU-220b** _shipped PR #113_ — full detail incl. validated content_json; cross-tenant returns 404 (RLS) |
| `/api/v1/reports/builder` | POST | 2 | ⬜ | F-038 | **BE-EU-221** Manual builder save + render — separate PR |
| `/api/v1/reports/{id}/distribute` | POST | 2 | 🟡 | F-038 | **BE-EU-222** _shipped this branch (email channel only)_ — manual multi-recipient send via `report_distributions` (migration 029) + per-recipient `notification_outbox` row. Validates `status='ready'` (409 otherwise); de-dupes recipients case-insensitively; cap 50 per call; `custom_message` (max 500 chars) renders above narrative in template. Slack/webhook channels deferred to v1 follow-up |
| `/api/v1/reports/{id}/distributions` | GET | 2 | 🟡 | F-038 | **BE-EU-222b** _shipped this branch_ — list distributions joined with live `notification_outbox` state (status, attempts, sent_at) for the FE audit drawer |
| `/api/v1/data/gold/datasets` | GET | 2 | ⬜ | (separate) | **BE-EU-220c** Dataset picker for the auto-report form — currently returns 404, FE falls back to MOCK_DATASETS. Belongs to a "data exploration" feature surface, not strictly F-038 |

### 2.16 Module 2.14 — Charts backend (ai-orchestrator + chart-engine)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/charts/catalog` | GET | 1 | ⬜ | F-027 (amendment) | **BE-EU-014** Static-ish catalog of 100+ chart kinds with min data shape — currently missing |
| `/api/v1/enterprise/charts/recommend` | POST | 2 | ⬜ | F-027 | **BE-EU-223** Recommendation engine: data shape → top-3 chart suggestions |
| `/api/v1/shared/charts/render` | POST | 1 | ❌ | F-027 | **BE-SH-002 (P0)** Server-side rendering (Node+Canvas or Python+Matplotlib) — currently NO HANDLER. Frontend FE-EU-014 blocked. |

### 2.17 Module 2.15 — AI Decision Log backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/decisions` | GET | 1 | ❌ | F-029 | **BE-EU-015 (P0)** Register decisions router; query `decision_audit_log` with filter (type/date/confidence/actioned); **currently returns 404** |
| `/api/v1/enterprise/decisions/{id}` | GET | 1 | ⬜ | F-029 | **BE-EU-016** Detail endpoint with full feature payload + alternatives + audit trail |

### 2.18 Module 2.16 — Decision Override backend (ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/decisions/{id}` | GET | 2 | 🟡 | F-036 | **BE-EU-223a** _shipped this branch_ — decision detail with overrides history (latest non-revoked is the effective one). Joins `decision_actions` for the is_actioned flag. RLS scoping → cross-tenant 404. Path is `/api/v1/decisions/...` (matches existing F-029 list endpoint, NOT `/enterprise/decisions/...`) |
| `/api/v1/decisions/{id}/override` | POST | 2 | 🟡 | F-036 | **BE-EU-224** _shipped this branch_ — append-only override write to `decision_overrides` (migration 031) + emit `kaori.feedback.actions` action='override.created' for F-074 fine-tuning + F-060 ROI rollup. 404 on missing decision; multiple overrides per decision allowed (latest non-revoked wins) |
| `/api/v1/decisions/{id}/override/{oid}/revoke` | POST | 2 | 🟡 | F-036 | **BE-EU-224b** _shipped this branch_ — soft revoke (sets `revoked_at`/`revoked_by_user`/`revoke_reason`); 409 on already-revoked to preserve first-revoke metadata; emits `kaori.feedback.actions` action='override.revoked' |

### 2.19 Module 2.17 — Workflow Builder backend (Temporal.io + ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/workflows` | POST / GET | 2 | ⬜ | F-065 | **BE-EU-225** Workflow definition CRUD; persist `canvas_json` + `version` |
| `/api/v1/enterprise/workflows/{id}/test` | POST | 2 | ⬜ | F-065 | **BE-EU-226** Dry-run on historical data via Temporal.io |
| `/api/v1/enterprise/workflows/{id}/run` | POST | 2 | ⬜ | F-065 | **BE-EU-227** Trigger production execution |

### 2.20 Module 2.18 — Alert Rules backend (notification-service + ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprises/alerts` | POST / GET | 2 | 🟡 | F-037 | **BE-EU-228** _shipped this branch_ — alert rule CRUD against `alert_rules` (migration 028); MANAGER-only mutations. Evaluator wired only for `metric_type='billing_quota_pct'` via `BillingAlertService`; `kaori.alerts.fire` Kafka consumer + arbitrary-metric evaluator deferred to v1 follow-up. Path uses `enterprises` (plural) to match existing routes |
| `/api/v1/enterprises/alerts/{id}` | PATCH / DELETE | 2 | 🟡 | F-037 | **BE-EU-229** _shipped this branch_ — partial update via COALESCE; soft-delete sets `deleted_at` + `is_active=false` |
| `/api/v1/enterprises/alerts/events` | GET | 2 | 🟡 | F-037 | **BE-EU-230** _shipped this branch_ — recent fire history (default 50, max 500) including `suppressed=true` rows for forensics |

### 2.21 Module 2.19 — Subscription & Quota backend (auth-service + billing-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/subscription/quota` | GET | 1 | ⬜🔒 | F-030 | **BE-EU-017** Quota gauge endpoint (uses `enterprise_monthly_billing`); **🔒 needs F-031 cron** |
| `/api/v1/enterprise/subscription/upgrade` | POST | 1 | ⬜ | F-030 | **BE-EU-018** Upgrade plan + prorate + emit billing event |
| `/api/v1/enterprise/subscription` | GET | 1 | ⬜ | F-030 | **BE-EU-019** Current plan details |

### 2.22 Module 2.20 — ROI Billing Report backend (billing-service)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/shared/roi-billing/{id}/report` | GET | 2 | ⬜ | F-059 | **BE-SH-201** Monthly ROI calculator: 1.5% revenue_at_risk actioned, cap 20M VND, ENT MAX opt-in only |
| `/api/v1/enterprise/decisions/{id}/action` | POST | 2 | ⬜ | F-060 | **BE-SH-202** Mark `is_actioned=true` (drives North Star metric) + emit `roi_billing_events` |

### 2.23 Module 2.21 — Knowledge Graph backend (kg-service NEW Phase 2 — Neo4j CE + pgvector)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/knowledge-graph/search` | GET | 2 | ⬜ | F-056 | **BE-EU-230** BGE-M3 embedding search across `kg_nodes` |
| `/api/v1/enterprise/knowledge-graph/lineage` | GET | 2 | ⬜ | F-056 | **BE-EU-231** Cypher query upstream/downstream |
| `/api/v1/enterprise/kg/graph` | GET | 2 | ⬜ | F-056 | **BE-EU-232** Subgraph fetch around node id |

### 2.24 Module 2.22 — Blast Radius backend (kg-service + ai-orchestrator)

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/enterprise/blast-radius/simulate` | POST | 2 | ⬜ | F-058 | **BE-EU-233** Simulate change impact via KG traversal + risk score |
| `/api/v1/enterprise/blast-radius/governance/{id}/approve` | POST | 2 | ⬜ | F-058 | **BE-EU-234** Approve change in governance queue + audit |

### 2.25 Phase 3 additions for Enterprise User backend

| Endpoint | Method | Phase | F-ID | Backend tasks |
|----------|--------|-------|------|---------------|
| `/api/v3/enterprise/compliance/status` | GET | 3 | F-071 | **BE-EU-301** SOC2/GDPR/EU AI Act status aggregator |
| `/api/v3/enterprise/compliance/export` | POST | 3 | F-079 | **BE-EU-302** Generate SOC2 evidence pack from audit log + decision_audit_log |
| `/api/v3/enterprise/privacy/erasure-request` | POST | 3 | F-072 | **BE-EU-303** GDPR erasure request workflow (30-day SLA) |
| `/api/v3/enterprise/audit-log` | GET | 3 | F-078 | **BE-EU-304** Audit log query (Phase 2 in v3.1 reconciliation, but extended UI Phase 3) |
| `/api/v3/shared/fairness/audit` | POST | 3 | F-077 | **BE-SH-301** Bias detection (demographic parity, equalized odds) |
| `/api/v3/enterprise/analysis/run` (finance) | POST | 3 | F-070 | **BE-EU-305** Finance vertical templates (credit risk, fraud, cash flow) |
| `/api/v3/enterprise/analysis/run` (logistics) | POST | 3 | F-086 | **BE-EU-306** Logistics templates (demand forecast, route optimization) |

---

## 3. Studio (ST) — Backend

> **Owning service:** NEW `studio-service` (Phase 2 stand-up) + `model-registry` (MLflow + PostgreSQL) + `training-pipeline` (Ray + PyTorch).
>
> **Phase activation: ENTIRE PORTAL Phase 2.** All endpoints ⬜ Pending. v3.1 API Catalog mis-tagged Phase 1 — corrected.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/studio/auth/login` | POST | 2 | ⬜ | F-042 | **BE-ST-001** Login supporting Kaori staff + Enterprise Analyst (scoped) + MFA enforcement |
| `/api/v1/studio/auth/activate/{token}` | POST | 2 | ⬜ | F-042 | **BE-ST-002** Activation flow with scope assignment |
| `/api/v1/studio/projects` | GET | 2 | ⬜ | F-043 | **BE-ST-003** List projects scoped by analyst assignment |
| `/api/v1/studio/projects` | POST | 2 | ⬜ | F-043 | **BE-ST-004** Create project + auto-assign creator as lead |
| `/api/v1/studio/projects/{id}` | GET | 2 | ⬜ | F-044 | **BE-ST-005** Project detail (5 tabs: overview/members/models/reports/datasets) |
| `/api/v1/studio/models` | GET | 2 | ⬜ | F-045 | **BE-ST-006** Model registry list (MLflow proxy) |
| `/api/v1/studio/models` | POST | 2 | ⬜ | F-045 | **BE-ST-007** Register new model with checksum |
| `/api/v1/studio/models/{id}/promote` | POST | 2 | ⬜ | F-045 | **BE-ST-008** Green-blue promote with traffic split |
| `/api/v1/studio/models/{id}/rollback` | POST | 2 | ⬜ | F-045 | **BE-ST-009** Rollback to previous version + audit |
| `/api/v1/studio/training-log/{run_id}` | GET | 2 | ⬜ | F-046 | **BE-ST-010** Training metrics per epoch from MLflow |
| `/api/v1/studio/reports/compose` | POST | 2 | ⬜ | F-047 | **BE-ST-011** Rich report save (HTML + chart refs from Gold) |
| `/api/v1/studio/reports/{id}/fan-out` | POST | 2 | ⬜ | F-047 | **BE-ST-012** Multi-recipient delivery with branding per enterprise |
| `/api/v1/studio/prompts` | POST | 2 | ⬜ | F-048 | **BE-ST-013** Prompt template CRUD with versioning |
| `/api/v1/studio/prompts/{id}/test` | POST | 2 | ⬜ | F-048 | **BE-ST-014** Test prompt against sample input |
| `/api/v1/studio/prompts/{id}/ab` | POST | 2 | ⬜ | F-048 | **BE-ST-015** A/B experiment setup with traffic split |
| `/api/v3/studio/agents/build` | POST | 3 | ⬜ | F-061 (P3 surface) | **BE-ST-301** Build AutoGen-style multi-agent definition (Shared 5.6b/5) — surfaces under P3 |
| `/api/v3/studio/agents/run` | POST | 3 | ⬜ | F-061 | **BE-ST-302** Run agent design with sample input |
| `/api/v3/studio/agents/inspect` | GET | 3 | ⬜ | F-061 | **BE-ST-303** Inspect agent run transcript + intermediate states |

**Tables:** `studio_projects`, `model_versions`, `model_training_logs`, `prompt_templates`, `prompt_test_results`, `report_deliveries`, `agent_designs` (Phase 3).

**Cross-service deps:** Reads `gold_features` (data-pipeline), writes to `model_serving` triton-vllm (Phase 2 infra).

---

## 4. Personal (PE) — Backend

> **Owning service:** NEW `personal-service` (Phase 2 stand-up) — reuses pipeline + analysis engines but with personal scope (single-user data isolation).
>
> **Phase activation: ENTIRE PORTAL Phase 2.** All endpoints ⬜ Pending.

| Endpoint | Method | Phase | Status | F-ID | Backend tasks |
|----------|--------|-------|--------|------|---------------|
| `/api/v1/personal/auth/signup` | POST | 2 | ⬜ | F-049 | **BE-PE-001** Self-signup email/phone/OAuth + GDPR opt-in |
| `/api/v1/personal/auth/oauth` | POST | 2 | ⬜ | F-049 | **BE-PE-002** OAuth callback (Google/Apple) |
| `/api/v1/personal/auth/verify-otp` | POST | 2 | ⬜ | F-049 | **BE-PE-003** Email/SMS OTP verify |
| `/api/v1/personal/auth/delete-account` | DELETE | 2 | ⬜ | F-049 | **BE-PE-004** GDPR right-to-erasure with 30-day grace |
| `/api/v1/personal/uploads` | POST | 2 | ⬜ | F-051 | **BE-PE-005** Upload by type (HEALTH/FINANCE/PRODUCTIVITY/GENERIC) + virus scan |
| `/api/v1/personal/pipelines` | POST | 2 | ⬜ | F-051 | **BE-PE-006** Personal pipeline (5-step wizard, BASIC tier only) |
| `/api/v1/personal/dashboard` | GET | 2 | ⬜ | F-050 | **BE-PE-007** KPI goals + streak + AI suggestions + 7d activity |
| `/api/v1/personal/goals` | GET / POST | 2 | ⬜ | F-052 | **BE-PE-008** Goal CRUD with max-10-active enforcement |
| `/api/v1/personal/goals/{id}/tracking` | GET | 2 | ⬜ | F-053 | **BE-PE-009** Target vs actual chart + calendar heatmap data |
| `/api/v1/personal/tracking` | POST | 2 | ⬜ | F-053 | **BE-PE-010** Quick-log endpoint |
| `/api/v1/personal/tracking/chart` | GET | 2 | ⬜ | F-053 | **BE-PE-011** Aggregate tracking chart data |
| `/api/v1/personal/suggestions` | GET | 2 | ⬜ | F-054 | **BE-PE-012** AI suggestions sorted by relevance |
| `/api/v1/personal/suggestions/{id}/action` | POST | 2 | ⬜ | F-054 | **BE-PE-013** Accept / dismiss / later action |
| `/api/v1/personal/settings` | GET / PATCH | 2 | ⬜ | F-055 | **BE-PE-014** Profile + theme + accent + language |

**Tables:** `personal_users`, `personal_goals`, `goal_plans`, `tracking_logs`, `personal_suggestions`. **Reuses:** `pipeline_runs`, `analysis_runs` (with `scope=personal`).

---

## 5. Cross-cutting Shared & Billing — Backend

> Services that serve **multiple target groups**. Each endpoint annotated with consuming groups (PT/EU/ST/PE) so common-API status can be tracked from one place.

### 5.1 Module 5.1 — Unique Billing Engine (data-pipeline cron)

| Endpoint / Job | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/billing/aggregate` (cron 00:05 UTC) | 1 | ⬜🔒 | F-031 | PT (monitor), EU (quota) | **BE-SH-001 (P0)** Daily COUNT DISTINCT customer_external_id per (enterprise, month); upsert immutable; emit `kaori.billing.events` |
| Quota Alert Emitter | 1 | ⬜ | F-031 | PT, EU | **BE-SH-003** Emit alerts on >80% / >95% quota crossing |
| Gaming Detector | 2 | ⬜ | new | PT | **BE-SH-203** Detect split-batch gaming patterns |

### 5.2 Module 5.2 — Multi-tenant Isolation (api-gateway middleware + db query guard)

| Component | Phase | Status | F-ID | Consuming groups | Backend tasks |
|-----------|-------|--------|------|------------------|---------------|
| JWT Tenant Extractor (gateway filter) | 1 | ✅ | (cross-cutting) | ALL | _shipped_ — `gateway/filter/JwtAuthFilter.java` |
| Query Guard (WHERE injector) | 1 | ❌ | (cross-cutting) | ALL | **BE-SH-004 (P0)** No DB-layer query guard exists; tenant filter relies on each route remembering — RLS bypass risk per ARCHITECTURE_REVIEW. Implement Row-Level Security policies in PostgreSQL OR query-rewriter middleware |
| Cross-tenant Audit | 1 | ⬜ | (cross-cutting) | ALL | **BE-SH-005** Audit any 403 cross-tenant attempt |

### 5.3 Module 5.3 — Explainability Layer (explainability-service NEW Phase 2)

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/explainability/decisions/{id}` | GET | 2 | ⬜ | F-041 | EU (Decision Detail), ST (Model audit) | **BE-SH-204** SHAP top-3 factors with Vietnamese translation; cache per decision id |
| `/api/v2/shared/explainability/explain` | POST | 2 | ⬜ | F-041 (split) | EU (inline widget · Decisions, Insights, Reports), ST | **BE-SH-204b** Inline widget endpoint — accepts `{target_id, target_type, lang}` for ad-hoc explanation; lighter response than `/decisions/{id}` (cache-friendly, used in 5+ surfaces). Per Shared module 5.3/2 |

### 5.4 Module 5.4 — Audit Log (audit-service NEW)

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/audit/events` | POST | 1 | 🔄 | F-NEW | ALL (writers) | **BE-SH-006** Audit Writer (Kafka consumer): only `schema.py` writes today; need full coverage. **Closes K-6 gap** |
| `/api/v1/shared/audit/events` | GET | 1 | ⬜ | F-078 (split: writer P1, query P1, UI P2) | PT, EU | **BE-SH-007** Query API with tenant/action/time filters + pagination |
| Retention Rotator (cron weekly) | 2 | ⬜ | F-078 | (system) | **BE-SH-205** Partition rotation, 2-year retention enforcement |

### 5.5 Module 5.5 — Internal LLM (llm-gateway: Qwen + vLLM)

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/llm/internal/generate` | POST | 1 | 🔄 | F-026 | ALL (LLM consumers) | **BE-SH-008** Implement K-3 rules 1/3/4/5/6 from CLAUDE.md §8 (currently incomplete routing) |
| `/api/v1/shared/llm/internal/embeddings` | POST | 1-2 | ⬜ | F-026 | EU (insights, KG search), ST (RAG) | **BE-SH-009** BGE-M3 Vietnamese embeddings endpoint |
| Inference Logging | (audit) | 1 | 🔄 | F-026 | ALL | **BE-SH-010** Wire decision_audit_log writes for every LLM call (closes K-6) |
| Fine-tuning | (offline) | 3 | ⬜ | F-074 | ST | **BE-PT-301** (cross-ref) — fine-tune job runner |

### 5.6 Module 5.6 — External AI Gateway

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/llm/external/generate` | POST | 1-2 | 🔄 | F-026, F-063 | ALL (with consent) | **BE-SH-011** Provider integrations (OpenAI/Claude only today; need Gemini/Azure); fallback policy; PII masking (3 regex today, need MS Presidio); cost tracking |
| Cost Tracking | (table) | 2 | ⬜ | F-063 | PT (monitor) | **BE-SH-206** `llm_request_logs` table + per-tenant cost rollups |

### 5.7 Module 5.6a — Guardrails Validation (Phase 2)

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/guardrails/validate-input` | POST | 2 | ⬜ | F-062 | ALL (LLM input) | **BE-SH-207** Input guards: PII/jailbreak/profanity; on-fail action policy |
| `/api/v1/shared/guardrails/validate-output` | POST | 2 | ⬜ | F-062 | ALL (LLM output) | **BE-SH-208** Output guards: hallucination check, custom validators |
| Violation Logging | (table) | 2 | ⬜ | F-062 | PT (dashboard) | **BE-SH-209** `guardrail_violations` immutable log + UI feed |

### 5.8 Module 5.6b — Agent Framework (Phase 2)

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/agents/sessions` | POST | 2 | ⬜ | F-061 | EU, ST | **BE-SH-210** Start MS Agent Framework session (Planner/Executor/Critic) |
| `/api/v1/shared/agents/workflows/{id}/invoke` | POST | 2 | ⬜ | F-061 | EU | **BE-SH-211** Invoke pre-built agent workflow |

### 5.9 Module 5.7 — Medallion Data Warehouse Engine

| Endpoint / Job | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------------|-------|--------|------|------------------|---------------|
| Storage Layers (Bronze/Silver/Gold) | 1 | ✅ | F-005, F-017..F-019 | EU (Pipeline), PT (Health) | _shipped — schemas + ingestion working_ |
| `/api/v1/shared/medallion/silver/refresh` | POST | 1 | ⬜ | F-032 | (system / EU pipelines) | **BE-SH-012** CDC refresh Silver from Bronze (idempotent) |
| `/api/v1/shared/medallion/gold/materialize` | POST | 1 | ⬜🔒 | F-032 | EU (analytics) | **BE-SH-013 (P0)** Gold MV builder; **`gold/` directory currently empty (only `__init__.py`)**; NUMERIC(5,4) for rates, NUMERIC(14,4) for money per K-9 |
| Lineage Graph | 2 | ⬜ | F-056 | EU (KG, Data Explorer) | **BE-SH-212** Build lineage graph for KG |
| Incremental & Time-travel | 2 | ⬜ | new | EU | **BE-SH-213** Incremental refresh + time-travel queries |

### 5.10 Module 5.8 — Chart Rendering Engine

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/shared/charts/render` | POST | 1 | ❌ | F-027 | EU (Charts), ST (Reports) | **BE-SH-002 (P0)** Server-side render to PNG/SVG/PDF — NO HANDLER. FE-EU-014 + FE-ST-013 blocked |
| Spec Schema + Theme Engine | 2 | ⬜ | F-027 | EU, ST | **BE-SH-214** Standardized JSON spec + theme variables (matches branding API) |

### 5.11 Module 5.9 — ROI Hybrid Billing Engine (Phase 2)

| Endpoint / Job | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------------|-------|--------|------|------------------|---------------|
| Monthly ROI Calculator (cron) | 2 | ⬜ | F-059 | EU (ROI Report), PT (billing oversight) | **BE-SH-201** (above) |
| `/api/v1/shared/roi-billing/{id}/report` | GET | 2 | ⬜ | F-059 | EU | (covered above) |

### 5.12 Module 5.10 — Kaori MCP Server (Phase 2 — Node.js NEW service)

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/mcp/jsonrpc` | POST | 2 | ⬜ | F-080 | External AI clients (Claude/Cursor/ChatGPT) + PT visibility | **BE-SH-215** JSON-RPC 2.0 server (tools/list, tools/call, resources/list) |
| `/mcp/sse` | GET | 2 | ⬜ | F-080 | (MCP clients) | **BE-SH-216** SSE stream for tool execution updates |
| `/mcp/auth/oauth/authorize` | POST | 2 | ⬜ | F-092 | (MCP clients) | **BE-SH-217** OAuth2 authorization flow |
| MCP Security & Audit | 2 | ⬜ | F-092 | PT | **BE-SH-218** Per-tenant scope token + rate limit + audit every call (K-15) |

### 5.13 Module 6.1-6.3 — Billing & Payment

| Endpoint | Method | Phase | Status | F-ID | Consuming groups | Backend tasks |
|----------|--------|-------|--------|------|------------------|---------------|
| `/api/v1/billing/payment-methods` | POST / GET / DELETE | 2 | ⬜ | F-083 (split per v3.1) | EU, PE | **BE-BL-001** Add card/VietQR/Momo/VNPay/ZaloPay; tokenize via gateway |
| `/api/v1/billing/invoices` | GET | 2 | ⬜ | F-082 (split) | EU | **BE-BL-002** List invoices with filter |
| `/api/v1/billing/invoices/{id}` | GET | 2 | ⬜ | F-082 | EU | **BE-BL-003** Detail with line items |
| `/api/v1/billing/invoices/{id}/pdf` | GET | 2 | ⬜ | F-082 | EU | **BE-BL-004** PDF generator (with branding) |
| `/api/v1/billing/invoices/{id}/e-invoice` | POST | 3 | ⬜ | F-082 | EU | **BE-BL-301** Issue Nghị định 123 e-invoice + tax authority integration |
| `/api/v1/billing/subscription/renew` | POST (cron) | 2 | ⬜ | F-067 | (system) | **BE-BL-005** Auto-renewal cron |
| `/api/v1/billing/subscription/cancel` | POST | 2 | ⬜ | F-067 | EU | **BE-BL-006** Cancel + refund calc |
| `/api/v1/billing/payment/initiate` | POST | 2 | ⬜ | F-083 | EU, PE | **BE-BL-007** Initiate payment session |
| `/api/v1/billing/payment/webhook` | POST | 2 | ⬜ | F-083 | (gateway callback) | **BE-BL-008** Webhook handler (signature verify per gateway) |

---

## 6. ⭐ API Status Board (108 endpoints)

> **The control board.** Every endpoint listed with: phase, status, owning F-ID, consuming groups, backend service. Use this section to triage daily — sort by status to find blockers, by group to scope work, by phase to plan sprints.
>
> **Status legend:** ✅ Done · 🔄 Partial · ❌ Ghost · ⬜ Pending · 🔒 Blocked · ⚠️ Drift

### 6.1 Platform Tenant endpoints (20)

| # | Endpoint | Method | Phase | Status | F-ID | Backend service | Consumed by | Backend task |
|---|----------|--------|-------|--------|------|-----------------|-------------|--------------|
| 1 | `/platform/auth/login` | POST | 1 | ✅ | F-002, F-007 | auth-service | PT | _done_ |
| 2 | `/platform/auth/mfa/verify` | POST | 1 | 🔄 | F-007 | auth-service | PT | BE-PT-001 |
| 3 | `/platform/auth/logout` | POST | 1 | ✅ | F-002 | auth-service | PT | _done_ |
| 4 | `/platform/workspaces` | GET | 1 | ✅ | F-008 | auth-service | PT | _done_ |
| 5 | `/platform/workspaces` | POST | 1 | 🔄 | F-008 | auth-service | PT | BE-PT-002 |
| 6 | `/platform/workspaces/{id}` | GET | 1 | 🔄 | F-008 | auth-service | PT | BE-PT-003 |
| 7 | `/platform/workspaces/{id}` | PATCH | 1 | 🔄 | F-008 | auth-service | PT | BE-PT-004 |
| 8 | `/platform/keys` | POST | 1 | 🔄🔒 | F-009 | auth-service | PT | BE-PT-006 |
| 9 | `/platform/keys/{id}` | DELETE | 1 | 🔄🔒 | F-009 | auth-service | PT | BE-PT-007 |
| 10 | `/platform/admins/invite` | POST | 1 | ❌ | F-010 | auth-service | PT | BE-PT-011 |
| 11 | `/platform/admins/{id}` | PATCH | 1 | ❌ | F-010 | auth-service | PT | BE-PT-012 |
| 12 | `/platform/billing/monitor?month=` | GET | 1 | ⬜🔒 | F-011 | auth-service | PT | BE-PT-014 |
| 13 | `/platform/billing/alerts` | GET | 1 | ⬜🔒 | F-011 (NEW) | auth-service | PT | BE-PT-015 |
| 14 | `/platform/pilot-conversion` | GET | 2 | ⬜ | F-066 | auth-service | PT | BE-PT-102 |
| 15 | `/platform/health` | GET | 1 | ✅ | F-012 | api-gateway | PT | _done_ |
| 16 | `/platform/plans` | GET | 2 | ⬜ | F-067 | auth-service | PT | BE-PT-105 |
| 17 | `/platform/plans` | POST | 2 | ⬜ | F-067 | auth-service | PT | BE-PT-106 |
| 18 | `/platform/llm/providers` | GET | 2 | ⬜ | F-073 | llm-gateway | PT | BE-PT-108 |
| 19 | `/platform/llm/providers` | POST | 2 | ⬜ | F-073 | llm-gateway | PT | BE-PT-109 |
| 20 | `/platform/llm/providers/{id}/privacy-mode` | PATCH | 2 | ⬜ | F-073 | llm-gateway | PT | BE-PT-110 |

**PT subtotal:** ✅ 4 · 🔄 6 · ❌ 2 · ⬜ 8 · 🔒 4 (subset)

### 6.2 Enterprise User endpoints (53)

| # | Endpoint | Method | Phase | Status | F-ID | Backend service | Consumed by | Backend task |
|---|----------|--------|-------|--------|------|-----------------|-------------|--------------|
| 21 | `/enterprise/auth/login` | POST | 1 | ✅ | F-002 | auth-service | EU | _done_ |
| 22 | `/enterprise/auth/activate/{token}` | POST | 1 | 🔄⚠️ | F-013 | auth-service | EU | BE-EU-001 |
| 23 | `/enterprise/authz/evaluate` | POST | 2 | ⬜ | F-064 | auth-service | EU | BE-EU-201 |
| 24 | `/enterprise/authz/policies` | * | 2 | ⬜ | F-064 | auth-service | EU | BE-EU-202 |
| 25 | `/enterprise/authz/simulate` | POST | 2 | ⬜ | F-064 | auth-service | EU | BE-EU-203 |
| 26 | `/enterprise/branding` | POST | 2 | ⬜ | F-087 (3→2) | auth-service | EU | BE-EU-204 |
| 27 | `/enterprise/onboarding/activate-key` | POST | 1 | 🔄⚠️ | F-013 | auth-service | EU | BE-EU-003 |
| 28 | `/enterprise/onboarding/pilot/upgrade` | POST | 2 | ⬜ | F-066 | auth-service | EU | BE-PT-103 |
| 29 | `/enterprise/dashboard/kpis` | GET | 1 | ✅ | F-028 | ai-orchestrator | EU | _done_ |
| 30 | `/enterprise/users` | GET | 1 | ⬜ | F-015 | auth-service | EU | BE-EU-005 |
| 31 | `/enterprise/users/invite` | POST | 1 | ⬜ | F-015 | auth-service | EU | BE-EU-006 |
| 32 | `/enterprise/users/{id}` | PATCH/DELETE | 1 | ⬜ | F-015 | auth-service | EU | BE-EU-007 |
| 33 | `/enterprise/data/{layer}/tables` | GET | 1 | ⬜ | **F-NEW3** | data-pipeline | EU | BE-EU-008 (NEW) |
| 34 | `/enterprise/data/lineage` | GET | 1 | ⬜ | **F-NEW3** | data-pipeline | EU | BE-EU-009 (NEW) |
| 35 | `/enterprise/data/bronze/upload` | POST | 1 | ✅ | F-017 | data-pipeline | EU | _done_ |
| 36 | `/enterprise/pipelines` | POST | 1 | ✅ | F-017 | data-pipeline | EU | _done_ |
| 37 | `/enterprise/pipelines` | GET | 1 | ⬜ | F-022 | data-pipeline | EU | BE-EU-011 |
| 38 | `/enterprise/pipelines/{id}/steps/{1-5}/run` | POST | 1 | ✅ | F-018..F-021 | data-pipeline | EU | _done_ |
| 39 | `/enterprise/pipelines/{id}/results` | GET | 1 | ✅ | F-021 | ai-orchestrator | EU | _done_ |
| 40 | `/enterprise/pipelines/{id}/status` | GET | 1 | 🔄 | F-NEW2 | data-pipeline | EU | BE-EU-010 |
| 41 | `/enterprise/auto-db/analyze` | POST | 2 | ⬜ | F-057 | ai-orchestrator | EU | BE-EU-206 |
| 42 | `/enterprise/auto-db/suggestions/{id}/apply` | POST | 2 | ⬜ | F-057 | ai-orchestrator | EU | BE-EU-207 |
| 43 | `/enterprise/analysis/basic` | POST | 1 | ✅ | F-023 | ai-orchestrator | EU | _done_ |
| 44 | `/enterprise/analysis/intermediate` | POST | 2 | ⬜ | F-024, F-033 | ai-orchestrator | EU | BE-EU-208 |
| 45 | `/enterprise/analysis/advanced` | POST | 2 | ⬜ | F-024, F-033 | ai-orchestrator | EU | BE-EU-209 |
| 46 | `/enterprise/frameworks/swot/generate` | POST | 2 | ⬜ | F-034 | ai-orchestrator | EU | BE-EU-210 |
| 47 | `/enterprise/frameworks/{6w\|2h\|fishbone\|mom-yoy}/generate` | POST | 2 | ⬜ | F-034 | ai-orchestrator | EU | BE-EU-211 |
| 48 | `/enterprise/frameworks/custom` | POST | 2 | ⬜ | F-034 | ai-orchestrator | EU | BE-EU-212 |
| 49 | `/enterprise/insights/generate` | POST | 1 | ✅ | F-025 | ai-orchestrator | EU | _done_ |
| 50 | `/enterprise/insights/feed` | GET | 1 | ✅ | F-025 | ai-orchestrator | EU | _done_ |
| 51 | `/enterprise/insights/{id}` | GET | 1 | 🔄 | F-025 (NEW) | ai-orchestrator | EU | BE-EU-012 |
| 52 | `/enterprise/risks/auto-detect` | POST | 2 | ⬜ | F-039 | ai-orchestrator | EU | BE-EU-214 |
| 53 | `/enterprise/risks/{id}/escalate` | POST | 2 | ⬜ | F-039 | ai-orchestrator | EU | BE-EU-215 |
| 54 | `/enterprise/strategy/okr` | POST | 2 | ⬜ | F-040 | ai-orchestrator | EU | BE-EU-217 |
| 55 | `/enterprise/strategy/{id}/timeline` | GET | 2 | ⬜ | F-040 | ai-orchestrator | EU | BE-EU-218 |
| 56 | `/reports/generate` (was spec'd as `/enterprise/reports/auto`) | POST | 2 | ✅ | F-038 | ai-orchestrator | EU | BE-EU-220 — _shipped PR #113_ |
| 56a | `/reports` | GET | 2 | ✅ | F-038 | ai-orchestrator | EU | BE-EU-220a — _shipped PR #113_ |
| 56b | `/reports/{id}` | GET | 2 | ✅ | F-038 | ai-orchestrator | EU | BE-EU-220b — _shipped PR #113_ |
| 57 | `/reports/builder` | POST | 2 | ⬜ | F-038 | ai-orchestrator | EU | BE-EU-221 |
| 58 | `/reports/{id}/distribute` | POST | 2 | ⬜ | F-038 | ai-orchestrator | EU | BE-EU-222 |
| 59 | `/enterprise/charts/catalog` | GET | 1 | ⬜ | F-027 (NEW) | ai-orchestrator | EU | BE-EU-014 |
| 60 | `/enterprise/charts/recommend` | POST | 2 | ⬜ | F-027 | ai-orchestrator | EU | BE-EU-223 |
| 61 | `/enterprise/decisions` | GET | 1 | ❌ | F-029 | ai-orchestrator | EU | BE-EU-015 (P0) |
| 62 | `/enterprise/decisions/{id}` | GET | 1 | ⬜ | F-029 | ai-orchestrator | EU | BE-EU-016 |
| 63 | `/enterprise/decisions/{id}/override` | POST | 2 | ⬜ | F-036 | ai-orchestrator | EU | BE-EU-224 |
| 64 | `/enterprise/decisions/{id}/action` | POST | 2 | ⬜ | F-060 | ai-orchestrator | EU | BE-SH-202 |
| 65 | `/enterprise/workflows` | POST/GET | 2 | ⬜ | F-065 | workflow-engine | EU | BE-EU-225 |
| 66 | `/enterprise/workflows/{id}/test` | POST | 2 | ⬜ | F-065 | workflow-engine | EU | BE-EU-226 |
| 67 | `/enterprise/alerts` | POST/GET | 2 | ⬜ | F-037 | notification-service | EU | BE-EU-228 |
| 68 | `/enterprise/subscription/quota` | GET | 1 | ⬜🔒 | F-030 | auth-service | EU | BE-EU-017 |
| 69 | `/enterprise/subscription/upgrade` | POST | 1 | ⬜ | F-030 | auth-service | EU | BE-EU-018 |
| 70 | `/enterprise/subscription` | GET | 1 | ⬜ | F-030 | auth-service | EU | BE-EU-019 |
| 71 | `/enterprise/knowledge-graph/search` | GET | 2 | ⬜ | F-056 | kg-service | EU | BE-EU-230 |
| 72 | `/enterprise/knowledge-graph/lineage` | GET | 2 | ⬜ | F-056 | kg-service | EU | BE-EU-231 |
| 73 | `/enterprise/blast-radius/simulate` | POST | 2 | ⬜ | F-058 | kg-service | EU | BE-EU-233 |

**EU subtotal Phase 1:** ✅ 9 · 🔄 5 · ❌ 1 · ⬜ 13 (28 total) — **EU subtotal Phase 2:** 25 ⬜

### 6.3 Studio endpoints (10) — All Phase 2 ⬜

| # | Endpoint | Method | Phase | Status | F-ID | Backend service | Consumed by | Backend task |
|---|----------|--------|-------|--------|------|-----------------|-------------|--------------|
| 74 | `/studio/auth/login` | POST | 2 | ⬜ | F-042 | studio-service | ST | BE-ST-001 |
| 75 | `/studio/projects` | GET | 2 | ⬜ | F-043 | studio-service | ST | BE-ST-003 |
| 76 | `/studio/projects` | POST | 2 | ⬜ | F-043 | studio-service | ST | BE-ST-004 |
| 77 | `/studio/models` | GET | 2 | ⬜ | F-045 | model-registry | ST | BE-ST-006 |
| 78 | `/studio/models/{id}/promote` | POST | 2 | ⬜ | F-045 | model-registry | ST | BE-ST-008 |
| 79 | `/studio/models/{id}/rollback` | POST | 2 | ⬜ | F-045 | model-registry | ST | BE-ST-009 |
| 80 | `/studio/training-log/{run_id}` | GET | 2 | ⬜ | F-046 | model-registry | ST | BE-ST-010 |
| 81 | `/studio/reports/compose` | POST | 2 | ⬜ | F-047 | studio-service | ST | BE-ST-011 |
| 82 | `/studio/reports/{id}/fan-out` | POST | 2 | ⬜ | F-047 | studio-service | ST | BE-ST-012 |
| 83 | `/studio/prompts` | POST | 2 | ⬜ | F-048 | studio-service | ST | BE-ST-013 |
| 83b | `/api/v3/studio/agents/build` | POST | 3 | ⬜ | F-061 | studio-service | ST | BE-ST-301 |
| 83c | `/api/v3/studio/agents/run` | POST | 3 | ⬜ | F-061 | studio-service | ST | BE-ST-302 |
| 83d | `/api/v3/studio/agents/inspect` | GET | 3 | ⬜ | F-061 | studio-service | ST | BE-ST-303 |

### 6.4 Personal endpoints (8) — All Phase 2 ⬜

| # | Endpoint | Method | Phase | Status | F-ID | Backend service | Consumed by | Backend task |
|---|----------|--------|-------|--------|------|-----------------|-------------|--------------|
| 84 | `/personal/auth/signup` | POST | 2 | ⬜ | F-049 | personal-service | PE | BE-PE-001 |
| 85 | `/personal/auth/verify-otp` | POST | 2 | ⬜ | F-049 | personal-service | PE | BE-PE-003 |
| 86 | `/personal/uploads` | POST | 2 | ⬜ | F-051 | personal-service | PE | BE-PE-005 |
| 87 | `/personal/pipelines` | POST | 2 | ⬜ | F-051 | personal-service | PE | BE-PE-006 |
| 88 | `/personal/goals` | POST | 2 | ⬜ | F-052 | personal-service | PE | BE-PE-008 |
| 89 | `/personal/goals/{id}/tracking` | GET | 2 | ⬜ | F-053 | personal-service | PE | BE-PE-009 |
| 90 | `/personal/suggestions` | GET | 2 | ⬜ | F-054 | personal-service | PE | BE-PE-012 |
| 91 | `/personal/suggestions/{id}/action` | POST | 2 | ⬜ | F-054 | personal-service | PE | BE-PE-013 |

### 6.5 Shared / Common APIs — multi-group consumers (12)

> **🎯 THESE ARE THE COMMON APIS WITH STATUS CHECKS** — single source of truth for shared endpoints.

| # | Endpoint | Method | Phase | Status | F-ID | Backend service | **Consumed by** | Backend task |
|---|----------|--------|-------|--------|------|-----------------|-----------------|--------------|
| 92 | `/shared/billing/aggregate` (cron) | POST | 1 | ⬜🔒 | F-031 | data-pipeline | **PT, EU** | **BE-SH-001 (P0)** |
| 93 | (middleware) tenant_id inject | — | 1 | ✅ | (cross) | api-gateway | **PT, EU, ST, PE** | _done_ |
| 94 | (middleware) DB query guard | — | 1 | ❌ | (cross) | (NEW) | **PT, EU, ST, PE** | **BE-SH-004 (P0)** |
| 95 | `/shared/explainability/decisions/{id}` | GET | 2 | ⬜ | F-041 | explainability-service | **EU, ST** | BE-SH-204 |
| 95b | `/api/v2/shared/explainability/explain` | POST | 2 | ⬜ | F-041 | explainability-service | **EU, ST** (inline widget) | BE-SH-204b |
| 96 | `/shared/audit/events` | POST | 1 | 🔄 | F-NEW | audit-service | **ALL (writers)** | BE-SH-006 |
| 97 | `/shared/audit/events` | GET | 1 | ⬜ | F-078 (split) | audit-service | **PT, EU** | BE-SH-007 |
| 98 | `/shared/llm/internal/generate` | POST | 1 | 🔄 | F-026 | llm-gateway | **ALL** | BE-SH-008 |
| 99 | `/shared/llm/internal/embeddings` | POST | 1-2 | ⬜ | F-026 | llm-gateway | **EU, ST** | BE-SH-009 |
| 100 | `/shared/llm/external/generate` | POST | 1-2 | 🔄 | F-026, F-063 | llm-gateway | **ALL (with consent)** | BE-SH-011 |
| 101 | `/shared/guardrails/validate-input` | POST | 2 | ⬜ | F-062 | guardrails-service | **ALL (LLM input)** | BE-SH-207 |
| 102 | `/shared/guardrails/validate-output` | POST | 2 | ⬜ | F-062 | guardrails-service | **ALL (LLM output)** | BE-SH-208 |
| 103 | `/shared/agents/sessions` | POST | 2 | ⬜ | F-061 | ai-orchestrator | **EU, ST** | BE-SH-210 |
| 104 | `/shared/agents/workflows/{id}/invoke` | POST | 2 | ⬜ | F-061 | ai-orchestrator | **EU** | BE-SH-211 |
| 105 | `/shared/medallion/silver/refresh` | POST | 1 | ⬜ | F-032 | medallion-engine | **(system)** | BE-SH-012 |
| 106 | `/shared/medallion/gold/materialize` | POST | 1 | ⬜🔒 | F-032 | medallion-engine | **EU (analytics)** | **BE-SH-013 (P0)** |
| 107 | `/shared/charts/render` | POST | 1 | ❌ | F-027 | chart-engine | **EU, ST** | **BE-SH-002 (P0)** |
| 108 | `/shared/roi-billing/{id}/report` | GET | 2 | ⬜ | F-059 | billing-service | **EU, PT** | BE-SH-201 |
| 109 | `/mcp/jsonrpc` | POST | 2 | ⬜ | F-080 | mcp-server | **External AI clients** | BE-SH-215 |
| 110 | `/mcp/sse` | GET | 2 | ⬜ | F-080 | mcp-server | **External** | BE-SH-216 |
| 111 | `/mcp/auth/oauth/authorize` | POST | 2 | ⬜ | F-092 | mcp-server | **External** | BE-SH-217 |

### 6.6 Billing endpoints (5)

| # | Endpoint | Method | Phase | Status | F-ID | Backend service | Consumed by | Backend task |
|---|----------|--------|-------|--------|------|-----------------|-------------|--------------|
| 112 | `/billing/payment-methods` | POST | 2 | ⬜ | F-083 (3→2) | billing-service | **EU, PE** | BE-BL-001 |
| 113 | `/billing/invoices` | GET | 2 | ⬜ | F-082 (3→2) | billing-service | **EU** | BE-BL-002 |
| 114 | `/billing/invoices/{id}/e-invoice` | POST | 3 | ⬜ | F-082 (kept Phase 3) | billing-service | **EU** | BE-BL-301 |
| 115 | `/billing/subscription/renew` | POST | 2 | ⬜ | F-067 | billing-service | **(cron)** | BE-BL-005 |
| 116 | `/billing/subscription/cancel` | POST | 2 | ⬜ | F-067 | billing-service | **EU** | BE-BL-006 |

### 6.7 Status board summary

| Status | Phase 1 | Phase 1-2 | Phase 2 | Phase 3 | Total |
|--------|---------|-----------|---------|---------|-------|
| ✅ Done | 13 | 0 | 0 | 0 | **13 (12%)** |
| 🔄 Partial | 11 | 1 | 0 | 0 | **12 (11%)** |
| ❌ Ghost | 4 | 0 | 0 | 0 | **4 (3%)** |
| ⬜ Pending | 14 | 4 | 52 | 14 | **84 (74%)** |
| **Total** | **42** | **5** | **52** | **14** | **113** |

> Note: 113 vs API Catalog's 108 — discrepancy comes from (a) F-NEW3 2 endpoints, (b) subscription accounting split into 3, (c) v3.1 audit gap-fill: BE-SH-204b inline explain + 3 BE-ST-301..303 AutoGen Studio agents that v3.1 listed only as "screens" not in the API Catalog. Use this board as source of truth.

---

## 7. Backend phase progress summary by group

| Group | Phase 1 endpoints | Phase 1 ✅ | Phase 1 🔄 | Phase 1 ❌ | Phase 1 ⬜ | Phase 2 ⬜ | Phase 3 ⬜ | Total |
|-------|-------------------|-----------|-----------|-----------|-----------|-----------|-----------|-------|
| **Platform Tenant** | 13 | 4 | 6 | 2 | 1 | 7 | 4 | 24 |
| **Enterprise User** | 28 | 9 | 5 | 1 | 13 | 25 | 7 | 60 |
| **Studio** | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 10 |
| **Personal** | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 8 |
| **Shared/Billing** | 6 | 0 | 1 | 1 | 4 | 18 | 1 | 26 |
| **Total** | **47** | **13** | **12** | **4** | **18** | **68** | **12** | **128** |

---

## 8. P0 defects gating Phase 1 close

> Sourced from `docs/ARCHITECTURE_REVIEW.md §4` + Phase 1 Reality Check sheet. **These MUST close before Phase 1 GA.**

| # | P0 | Backend task | Group impact | Frontend tasks blocked |
|---|----|--------------|--------------|------------------------|
| 1 | SecurityConfig blanket-deny on `/platform/keys` | BE-PT-006, BE-PT-007 (F-009 unblock) | PT | FE-PT-014..018 |
| 2 | Kafka topic naming mismatch (`pipeline.*` in code vs `kaori.*` in docs) | BE-SH-019 (rename or alias) | ALL | (system) |
| 3 | RBAC unenforced — F-014 ghost | BE-EU-002 | EU, PT | (security regressions everywhere) |
| 4 | DB query guard missing — RLS bypass | BE-SH-004 | ALL | (cross-tenant leak risk) |
| 5 | K-6 audit log gap (LLM calls + insights not logged) | BE-EU-013, BE-SH-010 | EU, ST | (decision log incomplete) |
| 6 | Silent event loss on async parse (data-pipeline) | BE-EU-020 (durable retry queue) | EU | (pipeline reliability) |
| 7 | F-031 cron not started | BE-SH-001 | PT, EU | FE-PT-023..027, FE-EU-017..019 |
| 8 | F-032 Gold layer empty | BE-SH-013 | EU | FE-EU-008..009, analysis Gold paths |
| 9 | F-027 chart render no handler | BE-SH-002 | EU, ST | FE-EU-014, FE-ST-013 |
| 10 | F-029 decisions router 404 | BE-EU-015 | EU | FE-EU-015..016 |
| 11 | F-010 PlatformAdminController doesn't exist | BE-PT-010..013 | PT | FE-PT-019..022 |

**Critical path order to unblock Phase 1:**
1. SecurityConfig + RBAC (week 1) → unblocks workspace key flow + access guards
2. F-031 cron + F-032 Gold (week 2) → unblocks billing + analytics
3. F-029 decisions + F-027 chart render (week 3) → unblocks decision UI + chart picker
4. F-010 admin controller + F-NEW3 data explorer (week 4) → fills remaining FE gaps

---

## 9. Cross-references

- Frontend tasks per group: `docs/FRONTEND_TASKS_PHASE.md`
- Feature catalog: `docs/BACKLOG.md` (incl. v3.1 Reconciliation)
- Phase 1 audit: `docs/phase_1_execution.md`
- Architecture P0s: `docs/ARCHITECTURE_REVIEW.md`
- v3.1 source: `docs/product/Feature_Tree_Kaori_AI_v3.1.xlsx` sheets `API Catalog`, `Phase 1 Reality Check`, `Screen Status Summary`
- Product BRD/PRD: `docs/product/Kaori_AI_BRD_v3.0.docx`, `Kaori_AI_PRD_v5.0.docx`, `TAI_LIEU_YEU_CAU_SAN_PHAM_v5.0.docx`
