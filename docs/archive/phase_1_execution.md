# Phase 1 Execution Tracker — Core Platform (Month 1–4)
> Kaori AI | Updated: 2026-04-25 | Source: BACKLOG.md v1.0 + executed work + `ARCHITECTURE_REVIEW.md`
>
> **2026-04-25 reconciliation**: Phantom completions identified via code audit (F-010, F-014, F-016, F-027) reclassified from ✅ to ❌/🔄. Honest screen-level Phase-1 impl is **~9%** (19/216 screens across all portals — see `Feature_Tree_Kaori_AI_v3.1.xlsx › Screen Status Summary`), while feature-level impl is **56%** (19/34) after ghosts removed. See `ARCHITECTURE_REVIEW.md` for P0 blockers (SecurityConfig, Kafka topic mismatch, RLS bypass, K-6 gap).

---

## 🔴 CURRENT EXECUTION STATE

| Field                  | Value                                                                                  |
|------------------------|----------------------------------------------------------------------------------------|
| **Phase**              | 1 — Core Platform                                                                      |
| **Sprint**             | 1.4 — Pipeline Wizard                                                                  |
| **Active Function**    | F-NEW2 Pipeline Status Polling / SSE (P0) — F-008 fully closed                         |
| **Active Task**        | T-FNW2-01 Add `GET /pipelines/:id/status` endpoint                                     |
| **File Being Edited**  | `services/data-pipeline/routers/upload.py`                                             |
| **Last Completed**     | T-F008-05/06 — gateway route was already in place (commit 40b462b); frontend page realigned to real backend contract (cursor pagination, snake_case fields, status enum) |
| **Next Task**          | T-FNW2-02 — Add SSE `/pipelines/:id/events` endpoint                                   |

---

## Phase 1 Progress

| Metric                  | Value (claimed → honest)                                                                                  |
|-------------------------|-----------------------------------------------------------------------------------------------------------|
| **Total Functions**     | 34 (F-001–F-032 + F-NEW1 + F-NEW2)                                                                        |
| **Done** ✅             | ~~24~~ → **20** (F-008 closed 2026-04-25)                                                                  |
| **Partial** 🔄          | ~~1~~ → **4** (F-007 MFA, F-009 unreachable, F-013 endpoint mismatch, F-026 partial routing) — F-008 closed |
| **Ghost** ❌            | **4** (F-010 Platform Admin, F-014 RBAC, F-016 Enterprise Settings, F-027 Chart render)                    |
| **Pending** ⬜          | **10** (F-NEW2, F-011, F-015, F-022, F-029, F-030, F-031 P0, F-032 P0)                                    |
| **Feature Progress**    | ~~71%~~ → **59% honest** (20 real ÷ 34)                                                                    |
| **Screen Progress**     | **9%** (19 impl / 216 total screens across P1+P2+P3+P4+Shared)                                             |
| **P0 defects**          | **6** — see `ARCHITECTURE_REVIEW.md §4` (SecurityConfig, Kafka topic mismatch, RBAC unenforced, RLS bypass, K-6 missing, silent event loss) |

### Sprint Progress

| Sprint                        | Total | Done | 🔄 | ⬜ | Progress   |
|-------------------------------|-------|------|----|----|------------|
| 1.1 Infrastructure Foundation | 7     | 7    | 0  | 0  | ✅ **100%** |
| 1.2 P1 Platform Manager       | 6     | 5    | 0  | 1  | 🔄 **83%**  |
| 1.3 P2 Onboarding + Users     | 4     | 3    | 0  | 1  | 🔄 **75%**  |
| 1.4 Pipeline Wizard           | 7     | 5    | 0  | 2  | 🔄 **71%**  |
| 1.5 Analysis Engine           | 5     | 5    | 0  | 0  | ✅ **100%** |
| 1.6 Dashboard + Billing       | 5     | 1    | 0  | 4  | ⬜ **20%**  |

---

## Done Functions Summary

| ID      | Function                            | Service                      | Key APIs                                              | Status |
|---------|-------------------------------------|------------------------------|-------------------------------------------------------|--------|
| F-001   | API Gateway + Auth Filter           | api-gateway                  | ALL /api/v1/* (JWT, rate limit, routing)              | ✅     |
| F-002   | Auth Login / Refresh / Logout       | auth-service                 | POST /auth/login, /refresh, /logout                   | ✅     |
| F-003   | Forgot / Reset Password             | auth-service                 | POST /auth/forgot-password, /reset-password           | ✅     |
| F-004   | Docker Compose + Infra Services     | infrastructure               | —                                                     | ✅     |
| F-005   | PostgreSQL Migrations 001–007       | infrastructure/postgres      | —                                                     | ✅     |
| F-006   | Kafka Topics Setup                  | infrastructure/kafka         | —                                                     | ✅     |
| F-NEW1  | SMTP Notification Service           | notification-service (8094)  | POST /internal/notifications/send                     | ✅     |
| F-007   | P1 Login + MFA (SUPER_ADMIN)        | auth-service                 | POST /auth/login (role=platform)                      | ✅     |
| F-008   | Workspace Management CRUD           | auth-service + frontend      | GET/POST/PATCH/DELETE /api/v1/platform/workspaces     | ✅     |
| F-009   | Private Key Management              | auth-service                 | POST/GET/DELETE /api/v1/platform/keys                 | ✅     |
| F-010   | Platform Admin CRUD                 | auth-service                 | GET/POST/PATCH /api/v1/platform/admins                | ❌ Ghost — no controller exists |
| F-012   | Platform Health Dashboard           | api-gateway                  | GET /api/v1/platform/health, /metrics                 | ✅     |
| F-013   | Enterprise Onboarding               | auth-service                 | POST /auth/workspace/activate  (note: /enterprise/onboarding ≠ impl) | 🔄 endpoint name mismatch |
| F-014   | Enterprise RBAC middleware          | auth-service                 | JWT PDP (internal)                                    | ❌ Ghost — JwtAuthFilter extracts role but never checks it |
| F-016   | Enterprise Settings                 | auth-service                 | GET/PATCH /api/v1/enterprise/settings                 | ❌ Ghost — no controller exists |
| F-017   | File Upload + Bronze Ingest         | data-pipeline                | POST /api/v1/upload, GET /pipelines/:id/status        | ✅     |
| F-018   | Schema Review + Column Mapping      | data-pipeline                | GET/POST /api/v1/schema/:runId/confirm                | ✅     |
| F-019   | Cleaning Review (Silver)            | data-pipeline                | GET /clean/suggestions/:runId, POST /clean/apply      | ✅     |
| F-020   | Analysis Config (Step 4)            | data-pipeline                | POST /api/v1/analytics/runs                           | ✅     |
| F-021   | Results Dashboard (Step 5)          | ai-orchestrator              | GET /api/v1/analytics/runs/:id                        | ✅     |
| F-023   | Statistical Analysis Engine         | ai-orchestrator              | (called by analytics/runs)                            | ✅     |
| F-024   | ML Analysis Engine                  | ai-orchestrator              | (called by analytics/runs)                            | ✅     |
| F-025   | Insights Engine 3-tuyến             | ai-orchestrator              | GET /insights/feed, POST /strategy/ask                | ✅     |
| F-026   | LLM Router (Qwen + External)        | ai-orchestrator              | POST /shared/llm/internal/generate                    | ✅     |
| F-027   | Chart & Visualization (15 kinds)    | frontend + ai-orchestrator   | GET /api/v1/charts/render                             | ❌ Ghost — no /api/v1/charts/render handler in ai-orchestrator |
| F-028   | Enterprise Dashboard (5-state)      | ai-orchestrator + frontend   | GET /api/v1/dashboard/state                           | ✅     |

---

## Pending / In-Progress Functions — Full Task Breakdown

---

### F-008 — Workspace Management CRUD ✅
**Sprint:** 1.2 | **Priority:** P1 | **Service:** auth-service + frontend

| Field          | Value                                                                               |
|----------------|-------------------------------------------------------------------------------------|
| **APIs**       | `GET /api/v1/platform/workspaces` `POST /api/v1/platform/workspaces` `PATCH /api/v1/platform/workspaces/:id` `DELETE /api/v1/platform/workspaces/:id` |
| **DB Tables**  | `workspaces`, `enterprises`, `subscription_plans`                                   |
| **Screens**    | `/p1/workspaces` → `frontend/app/(platform)/workspaces/page.tsx`                   |
| **Depends On** | F-007 (platform auth), F-009 (key gen button per workspace)                         |
| **Blocks**     | F-011 (billing monitor lists workspaces)                                             |

#### Tasks

| Task ID     | Task Name                           | File Path                                                                                   | Action  | Status      | Depends On  |
|-------------|-------------------------------------|---------------------------------------------------------------------------------------------|---------|-------------|-------------|
| T-F008-01   | Create WorkspaceController.java     | `services/auth-service/src/main/java/com/kaorisystem/auth/controller/WorkspaceController.java` | create  | ✅ done     | —           |
| T-F008-02   | Create WorkspaceService.java        | `services/auth-service/src/main/java/com/kaorisystem/auth/service/WorkspaceService.java`   | create  | ✅ done     | T-F008-01   |
| T-F008-03   | Create WorkspaceRepository.java     | `services/auth-service/src/main/java/com/kaorisystem/auth/repository/WorkspaceRepository.java` | create | ✅ done     | —           |
| T-F008-04   | Create Workspace.java entity        | `services/auth-service/src/main/java/com/kaorisystem/auth/model/Workspace.java`            | create  | ✅ done     | —           |
| T-F008-05   | Add gateway routes for /workspaces  | `services/api-gateway/src/main/java/com/kaorisystem/gateway/config/RouteConfig.java`       | update  | ✅ done (40b462b) | T-F008-01   |
| T-F008-06   | Create frontend workspaces page     | `frontend/app/(platform)/workspaces/page.tsx`                                               | create  | ✅ done     | T-F008-01   |

#### API Contract
```
GET  /api/v1/platform/workspaces?cursor=&limit=
     → { data: Workspace[], meta: { cursor, total } }

POST /api/v1/platform/workspaces
     ← { name: string, plan_code: string, industry?: string }
     → 201 { data: { workspace_id, name, plan_code, status, created_at } }

PATCH /api/v1/platform/workspaces/:id
     ← { name?, plan_code?, status? }
     → 200 { data: Workspace }

DELETE /api/v1/platform/workspaces/:id   (soft-delete → status='inactive')
     → 200 { data: { workspace_id, status: 'inactive' } }
```

---

### F-NEW2 — Pipeline Status Polling / SSE ⬜
**Sprint:** 1.4 | **Priority:** P0 | **Service:** data-pipeline + frontend

| Field          | Value                                                                                      |
|----------------|--------------------------------------------------------------------------------------------|
| **APIs**       | `GET /api/v1/pipelines/:id/status` (polling) · `GET /api/v1/pipelines/:id/events` (SSE)   |
| **DB Tables**  | `pipeline_runs` (status field)                                                             |
| **Screens**    | `/p2/pipelines/new` wizard — steps 1–5                                                     |
| **Kafka**      | Reads `kaori.pipeline.events` to update status                                             |
| **Depends On** | F-017 (creates pipeline_run on upload)                                                     |
| **Blocks**     | Wizard step transitions (currently blind after upload)                                     |

#### Tasks

| Task ID     | Task Name                               | File Path                                                  | Action  | Status      | Depends On |
|-------------|----------------------------------------|------------------------------------------------------------|---------|-------------|------------|
| T-FNW2-01   | Add GET /pipelines/:id/status endpoint  | `services/data-pipeline/routers/upload.py`                | update  | not_started | —          |
| T-FNW2-02   | Add SSE /pipelines/:id/events endpoint  | `services/data-pipeline/routers/upload.py`                | update  | not_started | T-FNW2-01  |
| T-FNW2-03   | Update wizard to consume SSE            | `frontend/components/pipeline/FileUploader.tsx`           | update  | not_started | T-FNW2-02  |
| T-FNW2-04   | Add SSE reconnect + polling fallback    | `frontend/components/pipeline/FileUploader.tsx`           | update  | not_started | T-FNW2-03  |

#### API Contract
```
GET /pipelines/:id/status
→ 200 { status: "QUEUED|INGESTING|SCHEMA_REVIEW|CLEANING|ANALYSIS|DONE|FAILED",
        pct_complete: 0–100, current_step: 1–5, error?: string }
→ 404 if pipeline_run not found for this tenant

GET /pipelines/:id/events   (SSE — text/event-stream)
→ event: status_update
  data: { status, pct_complete, current_step, error? }
```

---

### F-015 — User & Role Management ⬜
**Sprint:** 1.3 | **Priority:** P1 | **Service:** auth-service + frontend

| Field          | Value                                                                                             |
|----------------|---------------------------------------------------------------------------------------------------|
| **APIs**       | `GET/POST /api/v1/enterprise/users` · `PATCH/DELETE /api/v1/enterprise/users/:id` · `POST /api/v1/enterprise/users/invite` |
| **DB Tables**  | `enterprise_users`, (roles stored in `role` column)                                               |
| **Screens**    | `/p2/users` → `frontend/app/(app)/users/page.tsx`                                                 |
| **Depends On** | F-014 (RBAC middleware), F-NEW1 (invite email)                                                    |
| **Constraint** | Server must reject DELETE if target is the last MANAGER (→ 409)                                   |

#### Tasks

| Task ID     | Task Name                                  | File Path                                                                                         | Action  | Status      | Depends On           |
|-------------|--------------------------------------------|----------------------------------------------------------------------------------------------------|---------|-------------|----------------------|
| T-F015-01   | Create UserManagementController.java       | `services/auth-service/src/main/java/com/kaorisystem/auth/controller/UserManagementController.java` | create  | not_started | —                    |
| T-F015-02   | Create UserManagementService.java          | `services/auth-service/src/main/java/com/kaorisystem/auth/service/UserManagementService.java`     | create  | not_started | T-F015-01            |
| T-F015-03   | Add min-1-MANAGER guard in service         | `services/auth-service/src/main/java/com/kaorisystem/auth/service/UserManagementService.java`     | update  | not_started | T-F015-02            |
| T-F015-04   | Add POST /invite endpoint → F-NEW1 call    | `services/auth-service/src/main/java/com/kaorisystem/auth/controller/UserManagementController.java` | update  | not_started | T-F015-02, F-NEW1 ✅ |
| T-F015-05   | Add gateway route for /enterprise/users    | `services/api-gateway/src/main/java/com/kaorisystem/gateway/config/RouteConfig.java`              | update  | not_started | T-F015-01            |
| T-F015-06   | Create frontend /p2/users page             | `frontend/app/(app)/users/page.tsx`                                                                | create  | not_started | T-F015-01            |

#### API Contract
```
GET  /api/v1/enterprise/users          → { data: User[], meta: { total } }
POST /api/v1/enterprise/users          ← { email, role, full_name }
                                       → 201 User
POST /api/v1/enterprise/users/invite   ← { email, role }
                                       → 202 (email queued via notification-service)
PATCH /api/v1/enterprise/users/:id     ← { role?, status? }
                                       → 200 User
DELETE /api/v1/enterprise/users/:id    → 200 | 409 (last MANAGER)
```

---

### F-022 — Pipeline Run History ⬜
**Sprint:** 1.4 | **Priority:** P1 | **Service:** data-pipeline + frontend

| Field          | Value                                                                     |
|----------------|---------------------------------------------------------------------------|
| **APIs**       | `GET /api/v1/enterprise/pipelines` · `GET /api/v1/enterprise/pipelines/:id` |
| **DB Tables**  | `pipeline_runs`, `bronze_files`, `analysis_runs`                          |
| **Screens**    | `/p2/pipelines` → `frontend/app/(app)/pipelines/page.tsx`                |
| **Depends On** | F-017 (pipeline_runs exist in DB)                                         |
| **Pagination** | Cursor-based, max 50/page, sort by created_at DESC                       |

#### Tasks

| Task ID     | Task Name                                   | File Path                                          | Action  | Status      | Depends On  |
|-------------|---------------------------------------------|----------------------------------------------------|---------|-------------|-------------|
| T-F022-01   | Create pipeline history router              | `services/data-pipeline/routers/pipeline.py`      | create  | not_started | —           |
| T-F022-02   | Implement cursor-paginated list endpoint    | `services/data-pipeline/routers/pipeline.py`      | update  | not_started | T-F022-01   |
| T-F022-03   | Implement GET /pipelines/:id detail         | `services/data-pipeline/routers/pipeline.py`      | update  | not_started | T-F022-01   |
| T-F022-04   | Register pipeline router in main.py         | `services/data-pipeline/main.py`                  | update  | not_started | T-F022-01   |
| T-F022-05   | Create frontend /p2/pipelines list page     | `frontend/app/(app)/pipelines/page.tsx`           | create  | not_started | T-F022-01   |

#### API Contract
```
GET /api/v1/enterprise/pipelines?cursor=&limit=50&status=
→ { data: [{ run_id, filename, status, sha256, row_count_bronze,
              analysis_count, created_at }], meta: { cursor, total } }

GET /api/v1/enterprise/pipelines/:id
→ { data: { run_id, filename, status, bronze_files[], analysis_runs[],
             quality_score, created_at, updated_at } }
```

---

### F-031 — Unique Billing Cron ⬜ **P0**
**Sprint:** 1.6 | **Priority:** P0 | **Service:** data-pipeline (APScheduler)

| Field          | Value                                                                                           |
|----------------|-------------------------------------------------------------------------------------------------|
| **APIs**       | `POST /internal/billing/cron-run` (manual trigger for testing)                                 |
| **Kafka**      | Publishes to `kaori.billing.events` on quota threshold breach                                  |
| **DB Tables**  | `enterprise_monthly_billing` (UPSERT), `enterprise_users` (source customer_external_id)        |
| **Schedule**   | Daily 00:05 UTC via APScheduler                                                                 |
| **Depends On** | F-019 (silver data), F-NEW1 (quota alert emails)                                               |
| **Blocks**     | F-011 (billing monitor reads this data), F-030 (subscription quota display)                    |

#### Tasks

| Task ID     | Task Name                                      | File Path                                               | Action  | Status      | Depends On           |
|-------------|------------------------------------------------|---------------------------------------------------------|---------|-------------|----------------------|
| T-F031-01   | Create billing package                         | `services/data-pipeline/billing/__init__.py`           | create  | not_started | —                    |
| T-F031-02   | Create cron.py with APScheduler               | `services/data-pipeline/billing/cron.py`               | create  | not_started | T-F031-01            |
| T-F031-03   | Implement COUNT DISTINCT customer_external_id  | `services/data-pipeline/billing/cron.py`               | update  | not_started | T-F031-02            |
| T-F031-04   | Implement UPSERT enterprise_monthly_billing    | `services/data-pipeline/billing/cron.py`               | update  | not_started | T-F031-03            |
| T-F031-05   | Add 80%/95% quota alert → F-NEW1              | `services/data-pipeline/billing/cron.py`               | update  | not_started | T-F031-04, F-NEW1 ✅ |
| T-F031-06   | Create POST /internal/billing/cron-run         | `services/data-pipeline/routers/internal.py`           | create  | not_started | T-F031-02            |
| T-F031-07   | Register scheduler + router in main.py         | `services/data-pipeline/main.py`                       | update  | not_started | T-F031-02, T-F031-06 |

#### Cron Logic
```
Daily 00:05 UTC:
  FOR each active enterprise:
    unique_count = SELECT COUNT(DISTINCT customer_external_id)
                   FROM silver_rows WHERE enterprise_id = $1
                   AND created_at >= date_trunc('month', NOW())

    UPSERT enterprise_monthly_billing
      SET unique_customers = unique_count, updated_at = NOW()
      WHERE enterprise_id = $1 AND billing_month = date_trunc('month', NOW())

    quota = SELECT monthly_quota FROM subscription_plans sp
            JOIN workspaces w ON w.plan_code = sp.plan_code
            JOIN enterprises e ON e.workspace_id = w.workspace_id
            WHERE e.enterprise_id = $1

    pct = unique_count / quota * 100
    IF pct >= 95 → POST /internal/notifications/send (quota-alert, usage_pct=pct)
    ELIF pct >= 80 → POST /internal/notifications/send (quota-alert, usage_pct=pct)
```
**Kafka:** `kaori.billing.events` key=`enterprise_id` on threshold breach.

---

### F-032 — Gold Layer Aggregation ⬜ **P0**
**Sprint:** 1.6 | **Priority:** P0 | **Service:** data-pipeline (gold/)

| Field          | Value                                                                                  |
|----------------|----------------------------------------------------------------------------------------|
| **APIs**       | `POST /internal/gold/refresh` · `GET /api/v1/gold/features/:customerId`               |
| **Kafka**      | Consumes `kaori.pipeline.events` (silver.complete → triggers gold refresh)             |
| **DB Tables**  | `gold_features` (churn_probability `NUMERIC(5,4)`, revenue_at_risk `NUMERIC(14,4)`)   |
| **Depends On** | F-019 (silver_rows populated), F-024 (ML models output to feed)                       |
| **Blocks**     | F-024 reads gold for retraining, F-028 dashboard KPIs, F-029 decision log enrichment  |

#### Tasks

| Task ID     | Task Name                                        | File Path                                                       | Action  | Status      | Depends On  |
|-------------|--------------------------------------------------|-----------------------------------------------------------------|---------|-------------|-------------|
| T-F032-01   | Verify gold_features table in migration 003      | `infrastructure/postgres/migrations/003_silver_gold.sql`       | verify  | not_started | —           |
| T-F032-02   | Create gold aggregator entrypoint                | `services/data-pipeline/gold/aggregator.py`                    | create  | not_started | T-F032-01   |
| T-F032-03   | Implement RFM scoring module                     | `services/data-pipeline/gold/rfm.py`                           | create  | not_started | T-F032-02   |
| T-F032-04   | Implement churn_probability (NUMERIC 5,4)        | `services/data-pipeline/gold/aggregator.py`                    | update  | not_started | T-F032-03   |
| T-F032-05   | Implement revenue_at_risk (NUMERIC 14,4)         | `services/data-pipeline/gold/aggregator.py`                    | update  | not_started | T-F032-04   |
| T-F032-06   | Add POST /internal/gold/refresh endpoint         | `services/data-pipeline/routers/internal.py`                   | update  | not_started | T-F032-02   |
| T-F032-07   | Add GET /gold/features/:id endpoint              | `services/data-pipeline/routers/internal.py`                   | update  | not_started | T-F032-02   |
| T-F032-08   | Wire Kafka consumer: silver.complete → gold      | `services/data-pipeline/consumers/pipeline_consumer.py`        | update  | not_started | T-F032-02   |

#### Invariants
- `churn_probability` → `NUMERIC(5,4)` — never FLOAT (K-9)
- `revenue_at_risk` → `NUMERIC(14,4)` — never FLOAT (K-9)
- Gold refresh is idempotent: re-running replaces, never appends

---

### F-029 — AI Decision Log ⬜
**Sprint:** 1.6 | **Priority:** P1 | **Service:** ai-orchestrator + frontend

| Field          | Value                                                                                                   |
|----------------|---------------------------------------------------------------------------------------------------------|
| **APIs**       | `GET /api/v1/decisions` · `GET /api/v1/decisions/:id` · `GET /api/v1/decisions/export?format=csv`     |
| **DB Tables**  | `decision_audit_log` (append-only — K-6 invariant)                                                     |
| **Screens**    | `/p2/decisions` → `frontend/app/(app)/decisions/page.tsx`                                              |
| **Depends On** | F-025 (insights write entries), F-026 (LLM router writes entries)                                      |
| **Note**       | Backend currently returns 404 — router not registered                                                   |

#### Tasks

| Task ID     | Task Name                                  | File Path                                                | Action  | Status      | Depends On  |
|-------------|--------------------------------------------|---------------------------------------------------------|---------|-------------|-------------|
| T-F029-01   | Create decisions router                    | `services/ai-orchestrator/routers/decisions.py`        | create  | not_started | —           |
| T-F029-02   | Implement GET /decisions (filter + cursor) | `services/ai-orchestrator/routers/decisions.py`        | update  | not_started | T-F029-01   |
| T-F029-03   | Implement GET /decisions/:id               | `services/ai-orchestrator/routers/decisions.py`        | update  | not_started | T-F029-01   |
| T-F029-04   | Implement CSV export endpoint              | `services/ai-orchestrator/routers/decisions.py`        | update  | not_started | T-F029-01   |
| T-F029-05   | Register router + add gateway route        | `services/ai-orchestrator/main.py`                     | update  | not_started | T-F029-01   |
| T-F029-06   | Create frontend /p2/decisions page         | `frontend/app/(app)/decisions/page.tsx`                | create  | not_started | T-F029-01   |

#### API Contract
```
GET /api/v1/decisions?cursor=&limit=50&type=&date_from=&date_to=&confidence_min=
→ { data: [{ decision_id, decision_type, subject, chosen_value, confidence,
              method, llm_provider, created_at }], meta: { cursor, total } }

GET /api/v1/decisions/:id
→ { data: { ...all fields, alternatives[], reasoning, uncertainty_flags[] } }

GET /api/v1/decisions/export?format=csv
→ 200 text/csv  Content-Disposition: attachment; filename="decisions_export.csv"
```

---

### F-030 — Subscription & Quota ⬜
**Sprint:** 1.6 | **Priority:** P1 | **Service:** auth-service + frontend

| Field          | Value                                                                                  |
|----------------|----------------------------------------------------------------------------------------|
| **APIs**       | `GET /api/v1/enterprise/subscription` · `POST /api/v1/billing/upgrade`               |
| **DB Tables**  | `enterprise_monthly_billing`, `subscription_plans`, `tenant_settings`                 |
| **Screens**    | `/p2/subscription` → `frontend/app/(app)/subscription/page.tsx` (tabs: Quota/Plan/Upgrade) |
| **Depends On** | F-031 (billing cron populates data)                                                    |

#### Tasks

| Task ID     | Task Name                                  | File Path                                                                                         | Action  | Status      | Depends On       |
|-------------|--------------------------------------------|----------------------------------------------------------------------------------------------------|---------|-------------|------------------|
| T-F030-01   | Create SubscriptionController.java         | `services/auth-service/src/main/java/com/kaorisystem/auth/controller/SubscriptionController.java` | create  | not_started | F-031            |
| T-F030-02   | Create SubscriptionService.java            | `services/auth-service/src/main/java/com/kaorisystem/auth/service/SubscriptionService.java`       | create  | not_started | T-F030-01        |
| T-F030-03   | Add POST /billing/upgrade endpoint         | `services/auth-service/src/main/java/com/kaorisystem/auth/controller/SubscriptionController.java` | update  | not_started | T-F030-02        |
| T-F030-04   | Add gateway routes for subscription/billing| `services/api-gateway/src/main/java/com/kaorisystem/gateway/config/RouteConfig.java`              | update  | not_started | T-F030-01        |
| T-F030-05   | Create frontend /p2/subscription page      | `frontend/app/(app)/subscription/page.tsx`                                                         | create  | not_started | T-F030-01        |

#### API Contract
```
GET /api/v1/enterprise/subscription
→ { data: { plan: string, unique_customers_billed: int, quota_limit: int,
             pct_used: float, days_in_month_remaining: int,
             overage_count: int, overage_cost_vnd: NUMERIC(14,4) } }

POST /api/v1/billing/upgrade
← { target_plan: string }
→ 202 { data: { request_id, status: "pending", target_plan } }
```

---

### F-011 — Billing Monitor ⬜
**Sprint:** 1.2 | **Priority:** P1 | **Service:** auth-service + frontend

| Field          | Value                                                                     |
|----------------|---------------------------------------------------------------------------|
| **APIs**       | `GET /api/v1/platform/billing/summary` · `GET /api/v1/platform/billing/workspaces` |
| **DB Tables**  | `enterprise_monthly_billing`, `v_billing_summary` (view in migration 001) |
| **Screens**    | `/p1/billing` → `frontend/app/(platform)/billing/page.tsx`               |
| **Depends On** | F-031 (cron populates data)                                               |

#### Tasks

| Task ID     | Task Name                                   | File Path                                                                                           | Action  | Status      | Depends On |
|-------------|---------------------------------------------|------------------------------------------------------------------------------------------------------|---------|-------------|------------|
| T-F011-01   | Create PlatformBillingController.java       | `services/auth-service/src/main/java/com/kaorisystem/auth/controller/PlatformBillingController.java` | create  | not_started | F-031      |
| T-F011-02   | Create PlatformBillingService.java          | `services/auth-service/src/main/java/com/kaorisystem/auth/service/PlatformBillingService.java`       | create  | not_started | T-F011-01  |
| T-F011-03   | Add gateway route for /platform/billing     | `services/api-gateway/src/main/java/com/kaorisystem/gateway/config/RouteConfig.java`                | update  | not_started | T-F011-01  |
| T-F011-04   | Create frontend /p1/billing page            | `frontend/app/(platform)/billing/page.tsx`                                                           | create  | not_started | T-F011-01  |

---

## Master Task Table (All Pending Functions)

| Task ID     | Function   | File (abbreviated)                        | Action  | Status      | Depends On           |
|-------------|------------|-------------------------------------------|---------|-------------|----------------------|
| T-F008-01   | F-008      | `auth-service/.../WorkspaceController.java`  | create  | ✅ done     | —                    |
| T-F008-02   | F-008      | `auth-service/.../WorkspaceService.java`     | create  | ✅ done     | T-F008-01            |
| T-F008-03   | F-008      | `auth-service/.../WorkspaceRepository.java`  | create  | ✅ done     | —                    |
| T-F008-04   | F-008      | `auth-service/.../Workspace.java`            | create  | ✅ done     | —                    |
| T-F008-05   | F-008      | `api-gateway/.../RouteConfig.java`           | update  | ✅ done (40b462b) | T-F008-01     |
| T-F008-06   | F-008      | `frontend/(platform)/workspaces/page.tsx`    | create  | ✅ done     | T-F008-01            |
| T-FNW2-01   | F-NEW2     | `data-pipeline/routers/upload.py`            | update  | not_started | —                    |
| T-FNW2-02   | F-NEW2     | `data-pipeline/routers/upload.py`            | update  | not_started | T-FNW2-01            |
| T-FNW2-03   | F-NEW2     | `frontend/components/pipeline/FileUploader.tsx` | update | not_started | T-FNW2-02          |
| T-FNW2-04   | F-NEW2     | `frontend/components/pipeline/FileUploader.tsx` | update | not_started | T-FNW2-03          |
| T-F015-01   | F-015      | `auth-service/.../UserManagementController.java` | create | not_started | —                  |
| T-F015-02   | F-015      | `auth-service/.../UserManagementService.java`   | create | not_started | T-F015-01            |
| T-F015-03   | F-015      | `auth-service/.../UserManagementService.java`   | update | not_started | T-F015-02            |
| T-F015-04   | F-015      | `auth-service/.../UserManagementController.java` | update | not_started | T-F015-02, F-NEW1 ✅ |
| T-F015-05   | F-015      | `api-gateway/.../RouteConfig.java`              | update | not_started | T-F015-01            |
| T-F015-06   | F-015      | `frontend/(app)/users/page.tsx`                 | create | not_started | T-F015-01            |
| T-F022-01   | F-022      | `data-pipeline/routers/pipeline.py`             | create | not_started | —                    |
| T-F022-02   | F-022      | `data-pipeline/routers/pipeline.py`             | update | not_started | T-F022-01            |
| T-F022-03   | F-022      | `data-pipeline/routers/pipeline.py`             | update | not_started | T-F022-01            |
| T-F022-04   | F-022      | `data-pipeline/main.py`                         | update | not_started | T-F022-01            |
| T-F022-05   | F-022      | `frontend/(app)/pipelines/page.tsx`             | create | not_started | T-F022-01            |
| T-F031-01   | F-031 🔴P0 | `data-pipeline/billing/__init__.py`             | create | not_started | —                    |
| T-F031-02   | F-031 🔴P0 | `data-pipeline/billing/cron.py`                 | create | not_started | T-F031-01            |
| T-F031-03   | F-031 🔴P0 | `data-pipeline/billing/cron.py`                 | update | not_started | T-F031-02            |
| T-F031-04   | F-031 🔴P0 | `data-pipeline/billing/cron.py`                 | update | not_started | T-F031-03            |
| T-F031-05   | F-031 🔴P0 | `data-pipeline/billing/cron.py`                 | update | not_started | T-F031-04, F-NEW1 ✅ |
| T-F031-06   | F-031 🔴P0 | `data-pipeline/routers/internal.py`             | create | not_started | T-F031-02            |
| T-F031-07   | F-031 🔴P0 | `data-pipeline/main.py`                         | update | not_started | T-F031-02            |
| T-F032-01   | F-032 🔴P0 | `migrations/003_silver_gold.sql`                | verify | not_started | —                    |
| T-F032-02   | F-032 🔴P0 | `data-pipeline/gold/aggregator.py`              | create | not_started | T-F032-01            |
| T-F032-03   | F-032 🔴P0 | `data-pipeline/gold/rfm.py`                     | create | not_started | T-F032-02            |
| T-F032-04   | F-032 🔴P0 | `data-pipeline/gold/aggregator.py`              | update | not_started | T-F032-03            |
| T-F032-05   | F-032 🔴P0 | `data-pipeline/gold/aggregator.py`              | update | not_started | T-F032-04            |
| T-F032-06   | F-032 🔴P0 | `data-pipeline/routers/internal.py`             | update | not_started | T-F032-02            |
| T-F032-07   | F-032 🔴P0 | `data-pipeline/routers/internal.py`             | update | not_started | T-F032-02            |
| T-F032-08   | F-032 🔴P0 | `data-pipeline/consumers/pipeline_consumer.py`  | update | not_started | T-F032-02            |
| T-F029-01   | F-029      | `ai-orchestrator/routers/decisions.py`          | create | not_started | —                    |
| T-F029-02   | F-029      | `ai-orchestrator/routers/decisions.py`          | update | not_started | T-F029-01            |
| T-F029-03   | F-029      | `ai-orchestrator/routers/decisions.py`          | update | not_started | T-F029-01            |
| T-F029-04   | F-029      | `ai-orchestrator/routers/decisions.py`          | update | not_started | T-F029-01            |
| T-F029-05   | F-029      | `ai-orchestrator/main.py`                       | update | not_started | T-F029-01            |
| T-F029-06   | F-029      | `frontend/(app)/decisions/page.tsx`             | create | not_started | T-F029-01            |
| T-F030-01   | F-030      | `auth-service/.../SubscriptionController.java`  | create | not_started | F-031                |
| T-F030-02   | F-030      | `auth-service/.../SubscriptionService.java`     | create | not_started | T-F030-01            |
| T-F030-03   | F-030      | `auth-service/.../SubscriptionController.java`  | update | not_started | T-F030-02            |
| T-F030-04   | F-030      | `api-gateway/.../RouteConfig.java`              | update | not_started | T-F030-01            |
| T-F030-05   | F-030      | `frontend/(app)/subscription/page.tsx`          | create | not_started | T-F030-01            |
| T-F011-01   | F-011      | `auth-service/.../PlatformBillingController.java` | create | not_started | F-031              |
| T-F011-02   | F-011      | `auth-service/.../PlatformBillingService.java`  | create | not_started | T-F011-01            |
| T-F011-03   | F-011      | `api-gateway/.../RouteConfig.java`              | update | not_started | T-F011-01            |
| T-F011-04   | F-011      | `frontend/(platform)/billing/page.tsx`          | create | not_started | T-F011-01            |

---

## Flow View — Critical Path to Phase 2 Unlock

```
F-008 (Workspace CRUD) ──────────────── workspace_id established
  │
  └─► F-009 (Key Gen ✅) ──────────────► KAORI-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
                                           │
                                           ▼
                        F-013 (Onboarding ✅) ─── enterprise + first MANAGER created
                                           │       JWT: enterprise_id, role=MANAGER
                                           ▼
F-NEW1 (Email ✅) ──────► F-015 (User Mgmt) ─── team invited, roles assigned
                                           │
                                           ▼
                F-017→F-018→F-019 (Pipeline Wizard ✅)
                                           │
                          ┌────────────────┤
                          │                ▼
                     F-NEW2 (SSE)     silver_rows populated
                     real-time              │
                     feedback              ▼
                                    F-032 (Gold Layer 🔴P0)
                                     churn_probability
                                     revenue_at_risk (NUMERIC 14,4)
                                           │
                          ┌────────────────┤
                          ▼                ▼
                    F-024 (ML ✅)    F-031 (Billing Cron 🔴P0)
                    reads gold        COUNT DISTINCT → UPSERT
                                           │
                                    ┌──────┴──────┐
                                    ▼             ▼
                             F-028 (Dashboard ✅) F-NEW1 quota-alert ✅
                                    │
                          ┌─────────┴───────────┐
                          ▼                     ▼
                    F-029 (Decision Log)  F-030 (Subscription)
                                                │
                                          F-011 (Billing Monitor)
                                                │
                                                ▼
                                        ✅ Phase 1 COMPLETE
                                        → Phase 2 unlocks
```

### Function → API → Service → Kafka → DB → Next Function

| Function    | API Endpoint                            | Service           | Kafka Topic              | DB Write                     | Triggers Next     |
|-------------|----------------------------------------|-------------------|--------------------------|------------------------------|-------------------|
| F-017       | POST /upload                            | data-pipeline     | kaori.ingest.bronze      | bronze_files, bronze_rows    | F-018             |
| F-019       | POST /clean/apply                       | data-pipeline     | kaori.pipeline.events    | silver_rows                  | F-031, F-032      |
| F-031       | (cron 00:05 UTC)                        | data-pipeline     | kaori.billing.events     | enterprise_monthly_billing   | F-011, F-030      |
| F-032       | POST /internal/gold/refresh             | data-pipeline     | (consumes silver.complete)| gold_features               | F-024, F-028      |
| F-025       | POST /strategy/ask                      | ai-orchestrator   | kaori.decisions.log      | decision_audit_log           | F-029             |

---

*Updated: 2026-04-25 | To update active task: edit "CURRENT EXECUTION STATE" table at top*

---

## Cross-references

- **`docs/ARCHITECTURE_REVIEW.md`** — strict review with 6 P0 defects (SecurityConfig blocking own endpoints, Kafka topic mismatch between docs and code, RBAC never enforced, RLS decorative, silent event loss, K-6 audit only in one file) + improvement plan A–L.
- **`D:\Kaori Document\Feature_Tree_Kaori_AI_v3.1.xlsx`** — Feature Tree updated 2026-04-25:
  - New **Phase 1 Reality Check** sheet — maps every F-### to Feature Tree module, tracker status, code evidence, block/note.
  - New **Cross-Screen Journeys** sheet — 7 end-to-end user paths (A: workspace onboarding, B: pipeline wizard, C: decision override, D: quota breach, E: pilot conversion, F: MCP session, G: audit export).
  - New **Screen Status Summary** sheet — per-module + per-portal rollup (P1 9% impl / P2 12% / P3-P4 0% / Shared 8% / grand total 9% screen-level).
  - **Screen Dependencies** expanded from 44 to 80 flows (+36 new: P1 admin chain, LLM mgmt chain, P2 Users, Data Explorer drill-down, Reports Templates→Builder, Subscription→Payment, P3 Studio chain, P4 signup flow, MCP deeper flows, Guardrails→Audit).
  - **Shared Screens** orphan rows for `5.6b Agent Framework` now fully labeled (Module ID + routes).
  - Every per-portal Screens sheet gains **Phase / Impl Status / Evidence** columns with colour coding (green=impl, amber=partial, red=ghost).
  - **Design Coverage** now shows the _Missing Leaves_ delta — gaps: `2.0a Authz` (10 leaves missing design), `2.21 Knowledge Graph` (21), `5.6b Agent Framework` (8), `2.20 ROI Billing` (1).
