# Kaori AI — Product Backlog
> Version 1.4 | Updated: 2026-05-02 | Source: BRD v3.0 + PRD v5.0 + Feature Tree v3.0
>
> **2026-05-02 changelog:** Phase 2 kicked off. F-038 Reports backend shipped (PR #113); builder/templates/distribution surfaces remain pending. Phase 1 close-out plan archived — see `docs/PHASE2_PLAN.md` for the new tracker.

## Status Legend
| Symbol | Meaning |
|--------|---------|
| ✅ | Done — shipped & UAT-passed |
| 🔄 | In progress — code exists, not fully tested |
| ⬜ | Pending — not started |
| 🔵 | Phase 2 scope |
| 🟣 | Phase 3 scope |
| ❌ | Blocked |

## Phase Overview
| Phase | Theme | Target | MRR | Duration |
|-------|-------|--------|-----|----------|
| **Phase 1** | Core platform — retail vertical, 5 pilots | 5 paying customers | 10–40M VND | M1–M4 |
| **Phase 2** | Scale & intelligence — 25 customers, finance pilot | 25 paying customers | ≥100M VND | M5–M10 |
| **Phase 3** | Enterprise & expansion — 100 customers, SEA | 100 customers | ≥500M VND | M11–M18 |

---

## PHASE 1 — Core Platform (Month 1–4)

### Sprint 1.1 — Infrastructure Foundation (M1)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-001 | API Gateway + Auth Filter | Shared | — | `ALL /api/v1/*` — JWT RS256 extract, rate limit, tenant routing | `tenants`, `refresh_tokens`, `token_blacklist` | v1 | ✅ |
| F-002 | Auth Service — Login / Refresh / Logout | P2 2.0 | `/p2/auth/login` | `POST /auth/login` `POST /auth/refresh` `POST /auth/logout` | `users`, `refresh_tokens`, `token_blacklist` | v1 | ✅ |
| F-003 | Auth Service — Forgot / Reset Password | P2 2.0 | `/p2/auth/forgot-password` `/p2/auth/reset-password` | `POST /auth/forgot-password` `POST /auth/reset-password` | `password_reset_tokens` | v1 | ✅ |
| F-004 | Docker Compose + Infra Services | Shared | — | — | — | v1 | ✅ |
| F-005 | PostgreSQL Migrations (001–007) | Shared | — | — | All core tables | v1 | ✅ |
| F-006 | Kafka Topics Setup | Shared | — | — | — | v1 | ✅ |

---

### Sprint 1.2 — P1 Platform Manager (M1–M2)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-007 | P1 Auth — Login + MFA (SUPER_ADMIN/ADMIN) — TOTP MFA + sessions deepened in Batch 2 (Module 3, see below) | P1 1.0 | `/p1/auth/login` `/platform/security/mfa` `/platform/security/sessions` | `POST /auth/login` (role=platform) `POST /api/v1/platform/security/mfa/{enable,verify}` `GET/DELETE /api/v1/platform/security/sessions[/:id]` | `platform_admins.mfa_secret_enc`, `admin_sessions` | v1 | ✅ |
| F-008 | Workspace Management — CRUD + detail + members + billing + audit + keys | P1 1.1 | `/platform/workspaces` `/platform/workspaces/:id[/members\|billing\|audit\|keys\|edit]` `/platform/workspaces/new` | `GET POST /api/v1/platform/workspaces` `GET PATCH DELETE /api/v1/platform/workspaces/:id` `GET POST /api/v1/platform/workspaces/:id/members` `PATCH DELETE /api/v1/platform/workspaces/:id/members/:userId` `GET /api/v1/platform/workspaces/:id/billing` `GET /api/v1/platform/workspaces/:id/audit` | `workspaces`, `enterprises`, `enterprise_users`, `enterprise_monthly_billing`, `workspace_audit_log` | v1 | ✅ |
| F-009 | Private Key Management — generate, revoke, SHA-256 (additive: nested workspace-scoped routes added Batch 2; flat routes retained for AuthService.activateWorkspace) | P1 1.2 | `/platform/workspaces/:id/keys` | `GET POST /api/v1/platform/workspaces/:id/keys` `DELETE /api/v1/platform/workspaces/:id/keys/:keyId` (plus legacy flat `POST/GET/DELETE /api/v1/platform/keys`) | `workspace_keys` | v1 | ✅ |
| F-010 | Platform Admin Management — invite, deactivate, roles, password reset | P1 1.3 | `/platform/admins` `/platform/admins/invite` `/platform/admins/:id[/reset-password]` | `GET POST /api/v1/platform/admins` `GET PATCH /api/v1/platform/admins/:id` `POST /api/v1/platform/admins/:id/reset-password` | `platform_admins`, `platform_admin_password_resets` | v1 | ✅ |
| F-011 | Billing Monitor — platform-level aggregation, quota, overage, alert ≥80% | P1 1.4 | `/platform/billing/{overview\|quota\|enterprises/:id\|export}` | `GET /api/v1/platform/billing/{overview,quota,enterprises/:id,export}` | `enterprise_monthly_billing`, `subscription_plans`, `enterprises` | v1 | ✅ |
| F-012 | Platform Health Dashboard — KPI cards, 30d chart | P1 1.6 | `/platform` | `GET /api/v1/platform/health` `GET /api/v1/platform/metrics` | — | v1 | ✅ |

---

### Sprint 1.3 — P2 Enterprise Onboarding + User Mgmt (M2)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-013 | Enterprise Onboarding — key activation, company setup, invite | P2 2.2 | Phase 1: `/register` (legacy `/onboarding` redirects); Phase 2: `/p2/onboarding` | `POST /auth/workspace/activate` `POST /api/v1/enterprise/onboarding` | `tenants`, `users` | v1 | ✅ |
| F-014 | Enterprise RBAC — MANAGER/OPERATOR/ANALYST/VIEWER | P2 2.0a | — (middleware) | — (JWT + PDP) | `user_roles`, `permissions` | v1 | ✅ |
| F-015 | User & Role Management — CRUD member, min 1 MANAGER | P2 2.4 | `/p2/users` | `GET POST /api/v1/enterprises/users` `PATCH DELETE /api/v1/enterprises/users/:id` | `enterprise_users` | v1 | ✅ PR #73 (`907f03e`) |
| F-016 | Enterprise Settings — branding, language, AI consent | P2 2.1 | `/p2/settings` | `GET PATCH /api/v1/enterprises/me/settings` | `tenant_settings` (migration 015) | v1 | ✅ PR #69 (`dc09db9`) — Ghost fixed; K-4 enforced via `engine/llm_router.py` consent cache |

---

### Sprint 1.4 — Data Pipeline Wizard 5-step (M2–M3)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-017 | Step 1 — File Upload (Bronze ingest, SHA-256 dedup) | P2 2.5/2.6 | `/p2/pipelines/new` | `POST /api/v1/upload` `GET /api/v1/pipelines/:id/status` | `bronze_files`, `bronze_rows`, `pipeline_runs` | v1 | ✅ |
| F-018 | Step 2 — Schema Review (column mapping, confidence, overrides) | P2 2.6 | `/p2/pipelines/new` (step 2) | `GET /api/v1/schema/:runId` `POST /api/v1/schema/:runId/confirm` | `column_mappings`, `decision_audit_log` | v1 | ✅ |
| F-019 | Step 3 — Cleaning Review (rule suggestions, apply to Silver) | P2 2.5/2.6 | `/p2/pipelines/new` (step 3) | `GET /api/v1/clean/suggestions/:runId` `POST /api/v1/clean/apply` | `silver_rows`, `cleaning_rules_applied` | v1 | ✅ |
| F-020 | Step 4 — Analysis Config (template selection, external AI consent) | P2 2.6/2.8 | `/p2/pipelines/new` (step 4) | `POST /api/v1/analytics/runs` | `analysis_runs` | v1 | ✅ |
| F-021 | Step 5 — Results Dashboard (block-based: chart/stats/narrative) | P2 2.6/2.14 | `/p2/pipelines/new` (step 5) | `GET /api/v1/analytics/runs/:id` | `analysis_results` | v1 | ✅ |
| F-022 | Pipeline Run History — list, filter, re-open | P2 2.6 | `/p2/pipelines` | `GET /api/v1/pipelines` (cursor) `GET /api/v1/pipelines/:id/events` (SSE — F-NEW2) | `pipeline_runs` | v1 | ✅ PR #71 (`ece444d`) — bundled with F-NEW2 SSE |

---

### Sprint 1.5 — Analysis Engine + Insights (M3)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-023 | Statistical Analysis (summary_stats, distribution, correlation, time_series) | P2 2.8 | — (backend engine) | Called by `POST /api/v1/analytics/runs` | `analysis_results` | v1 | ✅ |
| F-024 | ML Analysis (clustering, regression, churn RFM, anomaly, bank_classify) | P2 2.8 | — (backend engine) | Called by `POST /api/v1/analytics/runs` | `analysis_results`, `gold_features` | v1 | ✅ |
| F-025 | Insights Engine — 3-tuyến (What/Why/What-to-do), narrative | P2 2.10 | `/p2/insights` | `GET /api/v1/insights/feed` `POST /api/v1/strategy/ask` | `insights`, `decision_audit_log` | v1 | ✅ |
| F-026 | LLM Router — Qwen internal default, external opt-in, PII redact | Shared 5.5 | — (backend) | `POST /shared/llm/internal/generate` | — | v1 | ✅ |
| F-027 | Chart & Visualization — 15 chart kinds, FlexibleChart picker | P2 2.14 | `/p2/analysis/:id` | `GET /api/v1/charts/render` | `analysis_results` | v1 | ✅ |

---

### Sprint 1.6 — Dashboard, Decisions, Billing Basics (M3–M4)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-028 | Enterprise Dashboard — 5-state machine, KPI cards, quota | P2 2.3 | `/p2/dashboard` | `GET /api/v1/dashboard/state` | `pipeline_runs`, `analysis_runs`, `enterprise_monthly_billing` | v1 | ✅ |
| F-029 | AI Decision Log — immutable list, filter, CSV export | P2 2.15 | `/p2/decisions` | `GET /api/v1/decisions` `GET /api/v1/decisions/export.csv` (UTF-8 BOM, 10k cap) | `decision_audit_log` | v1 | ✅ PR #72 (`97801a1`) |
| F-030 | Subscription & Quota — tab Quota/Plan/Upgrade, forecast, 80%/95% warn | P2 2.19 | `/p2/subscription` | `GET /api/v1/enterprises/me/subscription` `POST /api/v1/enterprises/me/subscription/upgrade` | `enterprise_monthly_billing`, `subscription_change_requests` (migration 017) | v1 | ✅ PR #75 (`ca948a3`) — endpoint paths adjusted to avoid `/billing/**` gateway collision |
| F-031 | Unique Billing Cron — daily aggregate COUNT DISTINCT, upsert, alert | Shared 5.1 | — (cron job) | `POST /api/v1/platform/billing/aggregate-now` (manual trigger) | `enterprise_monthly_billing` (migration 016 added `alert_*_fired` + `last_aggregated_at`) | v1 | ✅ PR #74 (`9b82887`) — daily 02:00 ICT. Email dispatch wired by F-037 (this branch — `BillingAlertService` enqueues `quota-alert` to `notification_outbox` on first 80%/95% crossing per month, cooldown 6h) |
| F-032 | Gold Layer — materialized views, feature engineering, aggregates | Shared 5.7 | — (backend) | Kafka consumer on `kaori.pipeline.silver.complete` → `aggregate_for_tenant()` | `gold_features`, `gold_aggregates` (migration 018) | v1 | ✅ PR #80 (`07b58a3`) — minimum scope: `revenue_at_risk` only; `is_actioned` workflow is Phase 2 F-060 |

---

## PHASE 2 — Scale & Intelligence (Month 5–10)

### Sprint 2.1 — Multi-tier Analysis + Frameworks (M5–M6)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-033 | Multi-tier Analysis — Intermediate/Advanced tiers, scope: multi/cross-pipeline | P2 2.8 | `/p2/analysis` `/p2/analysis/{basic,intermediate,advanced}` `/p2/analysis/runs/[id]` | `GET /api/v1/analysis/sources` · `GET /api/v1/analysis/cross-workspaces` · `GET /api/v1/analysis/quota/external-ai` · `POST GET /api/v1/analysis/runs[/{id}]` · `POST /api/v1/analysis/runs/{id}/approve` (MANAGER) | `analysis_runs` (migration 036 — tier/scope/framework/source_ids/workspace_ids/consent_external/approval cols) | v2 | ✅ BE PR A + B merged + FE PR C/D this branch — all 3 tiers ship end-to-end. Advanced gates on `tenant_settings.consent_external_ai`: ON → dispatch directly via llm-gateway external path (K-4 PII mask K-5); OFF → status='awaiting_approval' until MANAGER hits `/approve` endpoint. Real external-AI quota tracking from `decision_audit_log`. **Multi-workspace memberships** (1 user → N workspaces) deferred to PR D — Phase 1 enterprise_users model is one user per enterprise so cross-workspace currently degenerates to the calling workspace |
| F-034 | Analysis Frameworks — SWOT, 6W/2H, Fishbone (MoM/YoY deferred — calculation, not LLM) | P2 2.9 | `/p2/frameworks` `/p2/frameworks/{swot,6w,2h,fishbone-ishikawa}` | `POST /api/v1/frameworks/generate` (202 + background) · `GET /api/v1/frameworks` (cursor) · `GET /api/v1/frameworks/{run_id}` · `GET /api/v1/frameworks/templates` | `framework_runs` (migration 030); built-in templates in Python registry | v2 | ✅ BE PR #119 + FE this PR — 4 frameworks via Issue #3 `output_schema` validation + K-4 consent_external per call. FE: hub gallery + recent runs + 4 wired framework pages (generate-and-poll). MoM/YoY (calculation) + custom tenant frameworks deferred to v1 |
| F-035 | Cohort Retention — monthly retention table, customer cohort | P2 2.8 | `/p2/analysis/basic` (template picker) · `/p2/pipelines/{id}/step-4-analyze` (wizard) | Called by analysis runs engine via `cohort` template | `analysis_results`, `silver_rows` | v2 | ✅ Phase 1 ship — `StatisticalEngine._cohort` (statistical.py:307) + 8 unit tests + `RHeatmap` chart renderer + `cohort` template in registry. F-033 PR C surfaced via basic-tier picker (this PR — added MSW fixture + UAT script `docs/uat/F-035-cohort.md`). No dedicated FE page (basic-tier picker covers it; would dup code) |
| F-036 | Decision Detail & Override — explain + override + feedback retrain trigger | P2 2.16 | `/p2/decisions/[id]` | `GET /api/v1/decisions/{id}` · `POST /api/v1/decisions/{id}/override` · `POST /api/v1/decisions/{id}/override/{oid}/revoke` | `decision_audit_log` (existing) · `decision_overrides` (migration 031) · `kaori.feedback.actions` Kafka topic | v2 | ✅ BE PR #122 + FE this PR — wired detail page (header + reasoning + alternatives + audit + override section) with create modal + revoke flow + is_actioned toggle. SHAP explain layer (F-041) deferred to v1 |
| F-037 | Alert Rules — CRUD + billing-quota dispatcher (email v0; Slack/webhook deferred), cooldown via alert_events | P2 2.18 | `/p2/alerts` | `GET POST /api/v1/enterprises/alerts` `PATCH DELETE /api/v1/enterprises/alerts/:id` `GET /api/v1/enterprises/alerts/events` | `alert_rules`, `alert_events` (migration 028) | v0 | ✅ BE PR #116 + FE this PR — `/p2/alerts` page with 2 tabs (events history + rules CRUD), MSW handlers, MANAGER role gate on mutations. Slack/webhook + arbitrary-metric evaluator deferred to v1 follow-ups |

---

### Sprint 2.2 — Reports, Risk, Strategy (M6–M7)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-038 | Reports — auto LLM-generated + builder + template library + distribution | P2 2.13 | `/p2/reports` `/p2/reports/:id` `/p2/reports/distribution` | `GET /api/v1/reports` (cursor) · `POST /api/v1/reports/generate` (202 + background worker) · `GET /api/v1/reports/{id}` · `POST /api/v1/reports/{id}/distribute` · `GET /api/v1/reports/{id}/distributions` | `reports`, `report_templates`, `report_distributions` (migrations 027, 029); built-in seed `monthly_summary` | v2 | ✅ Auto path BE PR #113 + FE PR #115. Distribution BE PR #118 + FE this PR — wired `/p2/reports/distribution?report=<id>` (picker fallback + recipients form + history joined to outbox). Hub Send icon deep-links to it for ready reports. Builder / templates library / scheduler still pending v1 |
| F-039 | Risk Management — heat map, auto-detect from data, risk score, owner, alert | P2 2.11 | `/p2/risks` | `GET POST /api/v1/enterprises/risks` · `GET PATCH DELETE /api/v1/enterprises/risks/:id` · `GET /api/v1/enterprises/risks/severity-rollup` | `risk_items` (migration 033) | v2 | 🟡 backend this PR — manual CRUD with auto-computed score (likelihood × impact) + severity tier (low/medium/high/critical via DB trigger) + soft-delete + MANAGER role gate. Auto-detect from data + risk_snapshots history + alert integration deferred to v1 follow-ups. FE separate PR |
| F-040 | Strategy Builder — OKR/OGSM canvas, Gantt roadmap, link risk↔action | P2 2.12 | `/p2/strategy` | `GET POST /api/v2/enterprise/strategy` `PATCH /api/v2/enterprise/strategy/:id/okr` | `strategy_plans`, `okr_items`, `risk_items` | v2 | 🔵 |
| F-041 | Explainability Layer — top-3 factors + Vietnamese narrative, public API | Shared 5.3 | `/p2/decisions/[id]` "Vì sao Kaori quyết định thế?" section | `POST /api/v1/explainability/explain` | `decision_audit_log` (read + write 1 audit row per call) | v2 | ✅ this PR — `services/ai-orchestrator/explainability/` module + endpoint via Issue #3 `output_schema` (top_factors[] direction/weight/evidence + narrative + confidence_explanation) + K-6 audit + 7 unit tests + FE lazy section in 32b decision detail + MSW handler + UAT script. **"Lite" framing**: explanation is grounded in audit-row fields, not real SHAP — model-object persistence (real SHAP) deferred to F-073 once F-046 model registry ships. Same response shape so swap is FE-transparent |

---

### Sprint 2.3 — P3 Studio Portal (M7–M8)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-042 | Studio Auth — staff login, MFA required for STUDIO_ADMIN | P3 3.0 | `/p3/auth/login` | `POST /auth/login` (portal=studio) | `users`, `mfa_tokens` | v2 | 🔵 |
| F-043 | Studio Home + Project List — assigned projects, activity feed | P3 3.1/3.2 | `/p3` `/p3/projects` | `GET /api/v2/studio/projects` | `studio_projects` | v2 | 🔵 |
| F-044 | Project Detail — members, models, reports, datasets snapshot | P3 3.3 | `/p3/projects/:id` | `GET /api/v2/studio/projects/:id` | `studio_projects`, `model_versions` | v2 | 🔵 |
| F-045 | Model Registry & Versioning — checksum, metrics, state machine, promote, rollback | P3 3.4 | `/p3/models` | `GET POST /api/v2/studio/models` `POST /api/v2/studio/models/:id/promote` | `model_versions`, `model_training_logs` | v2 | 🔵 |
| F-046 | Training Log — loss/accuracy chart per epoch, compare, hyperparams | P3 3.5 | `/p3/training-log` | `GET /api/v2/studio/training-logs/:modelId` | `model_training_logs` | v2 | 🔵 |
| F-047 | Report Composer & Delivery — rich text, attach chart from Gold, fan-out | P3 3.6 | `/p3/reports/composer` | `POST /api/v2/studio/reports` `POST /api/v2/studio/reports/:id/deliver` | `reports`, `report_deliveries` | v2 | 🔵 |
| F-048 | Prompt Tuning — template by vertical/task, test, version, A/B test | P3 3.7 | `/p3/prompts` | `GET POST /api/v2/studio/prompts` `POST /api/v2/studio/prompts/:id/test` | `prompt_templates`, `prompt_test_results` | v2 | 🔵 |

---

### Sprint 2.4 — P4 Personal Portal (M8–M9)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-049 | Personal Auth — self-signup email/phone/OAuth, OTP, GDPR delete | P4 4.0 | `/p4/auth` | `POST /api/v2/personal/auth/signup` `POST /api/v2/personal/auth/oauth` | `personal_users` | v2 | 🔵 |
| F-050 | Personal Dashboard — KPI goals, streak, AI suggestions, 7d chart | P4 4.1 | `/p4/dashboard` | `GET /api/v2/personal/dashboard` | `personal_goals`, `goal_progress` | v2 | 🔵 |
| F-051 | Personal Data Pipeline — wizard 5-step, basic analysis only | P4 4.4 | `/p4/pipelines` | (reuse pipeline APIs, personal scope) | `pipeline_runs` (personal) | v2 | 🔵 |
| F-052 | Goals & Plans Hierarchy — Goal → Plan → Strategy tree, drag-drop, max 10 | P4 4.5/4.6 | `/p4/goals` `/p4/goals/:id` | `GET POST /api/v2/personal/goals` `PATCH /api/v2/personal/goals/:id` | `personal_goals`, `goal_plans` | v2 | 🔵 |
| F-053 | Performance Tracking — quick-log, line chart, calendar heatmap | P4 4.7 | `/p4/tracking` | `POST /api/v2/personal/tracking` `GET /api/v2/personal/tracking/chart` | `tracking_logs` | v2 | 🔵 |
| F-054 | AI Suggestions — relevance-sorted list, accept/dismiss/later | P4 4.8 | `/p4/suggestions` | `GET /api/v2/personal/suggestions` `POST /api/v2/personal/suggestions/:id/action` | `personal_suggestions` | v2 | 🔵 |
| F-055 | Personal Customization — avatar, theme light/dark, accent, language VN/EN | P4 4.9 | `/p4/customize` | `GET PATCH /api/v2/personal/settings` | `personal_users` | v2 | 🔵 |

---

### Sprint 2.5 — Knowledge Graph + Auto DB Design + Blast Radius (M8–M9)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-056 | Data Knowledge Graph — nodes/edges, visualize, lineage, semantic search | P2 2.21 | `/p2/knowledge-graph` | `GET /api/v2/enterprise/kg/graph` `GET /api/v2/enterprise/kg/search` | `kg_nodes`, `kg_edges` (Neo4j) | v2 | 🔵 |
| F-057 | Auto Database Design — AI pattern → schema 3NF/star, CREATE TABLE + ERD + form | P2 2.7 | `/p2/auto-db` | `POST /api/v2/enterprise/auto-db/suggest` `GET /api/v2/enterprise/auto-db/:id/erd` | `auto_db_designs` | v2 | 🔵 |
| F-058 | Blast Radius / Impact Analysis — pre-change impact, visualization, safe-change | P2 2.22 | `/p2/blast-radius` | `POST /api/v2/enterprise/blast-radius/analyze` | `blast_radius_reports`, `kg_edges` | v2 | 🔵 |

---

### Sprint 2.6 — ROI Hybrid Billing + Agent Framework (M9–M10)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-059 | ROI Hybrid Billing — cron monthly, 1.5% revenue saved, cap 20M VND | Shared 5.9 | `/p2/billing/roi` | `GET /api/v2/billing/roi-report` | `enterprise_monthly_billing`, `roi_billing_events` | v2 | 🔵 |
| F-060 | is_actioned Workflow — North Star Metric, mark actioned, audit trail | P2 2.10 | `/p2/customers/at-risk` (this FE) · `/p2/dashboard` (tile follow-up) | `POST /api/v1/customers/{external_id}/action` · `GET /api/v1/dashboard/north-star` · `GET /api/v1/customers/at-risk` | `gold_features` (migration 018 pre-baked is_actioned + actioned_at; migration 032 added actioned_by_user) · `kaori.feedback.actions` Kafka topic (extended enum) | v2 | ✅ BE PR #124 + FE this PR — canonical column on gold_features, `/p2/customers/at-risk` page combining North Star tile (4 KPIs + recent activity) + cursor-paginated customer table with per-row toggle (prompt for notes / confirm for revert) + nav entry "Khách hàng → Rủi ro & ROI". **Closes CLAUDE.md §14 North Star limitation end-to-end.** Dashboard-page tile embed (reuses exported `NorthStarTile`) deferred to /p2/dashboard FE refactor |
| F-061 | Agent Framework — Planner/Executor/Critic, insight-to-action workflow | Shared 5.6b | (FE follow-up) | `POST /api/v1/shared/agents/sessions` · `POST /api/v1/shared/agents/workflows/{id}/invoke` | `agent_sessions`, `agent_transcripts` (migration 038) | v2 | ✅ BE PR _pending_ — custom Python P/E/C (BRD T11 deferred — MS AF can swap later if pilot needs it). 1 workflow `insight-to-action` end-to-end + 2 action tools (`draft_followup_email`, `mark_customer_for_review`) gated by `dry_run` (default ON). 27 unit tests, ai-orchestrator suite at 408/408. **Defer:** 2 other workflows (data-quality-check, retention-campaign-draft), FE `/p2/workflows`, streaming SSE, human-in-loop queue (M11), P3 Studio surface (Phase 3), per-minute Redis rate limit. See `docs/specs/AGENT_FRAMEWORK.md` |
| F-062 | Guardrails Validation — PII, jailbreak, hallucination, custom validators | Shared 5.6a | — (middleware) | — (internal layer) | `guardrail_violations` | v2 | 🔵 |
| F-063 | External AI Gateway — OpenAI/Claude/Gemini/Azure, fallback, cost tracking | Shared 5.6 | `/p1/llm` (P1 config) | `POST /api/v2/shared/llm/external/generate` | `llm_request_logs` | v2 | 🔵 |

---

### Sprint 2.7 — Advanced AuthZ + Workflow Builder + Pilot Conversion (M10)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-064 | ABAC + Hybrid PDP — attribute-based policies, unified allow/deny + reason | P2 2.0a | — (middleware) | — (internal PDP) | `abac_policies`, `pdp_decisions` | v2 | 🔵 |
| F-065 | Workflow Builder — drag-drop canvas, versioning, trigger, test mode | P2 2.17 | `/p2/workflows` | `GET POST /api/v2/enterprise/workflows` `POST /api/v2/enterprise/workflows/:id/run` | `workflow_definitions`, `workflow_runs` | v2 | 🔵 |
| F-066 | Pilot Conversion Tracking — D25 reminder, D30 upgrade prompt, 1-click upgrade | P1 1.5 | `/platform/pilot-conversion` | `GET /api/v2/platform/pilot-tracking` `POST /api/v2/platform/pilot/:id/upgrade` | `tenants`, `enterprise_monthly_billing` | v2 | 🔵 |
| F-067 | Subscription Plans CRUD — create/soft-update/deactivate plan, keep history | P1 1.7 | `/platform/plans` | `GET POST /api/v2/platform/plans` `PATCH /api/v2/platform/plans/:id` | `subscription_plans` | v2 | 🔵 |
| F-068 | SSO Integration — SAML 2.0 + OIDC for enterprise | P2 2.0 | `/p2/settings/sso` | `POST /api/v2/enterprise/auth/sso/configure` | `sso_configs` | v2 | 🔵 |

---

## PHASE 3 — Enterprise & Expansion (Month 11–18)

### Sprint 3.1 — Finance Vertical + Compliance Display (M11–M12)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-069 | Finance Data Schema — credit, fraud, transaction Silver tables | Shared 5.7 | — (backend) | — (Medallion engine) | `silver.credit_applications`, `silver.fraud_events` | v3 | 🟣 |
| F-070 | Finance Analysis Templates — credit risk, fraud detection, cash flow | P2 2.8 | `/p2/analysis/finance` | `POST /api/v3/enterprise/analysis/run` (finance templates) | `analysis_results` | v3 | 🟣 |
| F-071 | Compliance Dashboard — SOC2, GDPR, EU AI Act status display | P2 (new) | `/p2/compliance` | `GET /api/v3/enterprise/compliance/status` | `compliance_checks` | v3 | 🟣 |
| F-072 | GDPR / PDPA Erasure Workflow — right-to-erasure, 30-day SLA | Shared | `/p2/settings/privacy` | `POST /api/v3/enterprise/privacy/erasure-request` | `erasure_requests` | v3 | 🟣 |

---

### Sprint 3.2 — LLM Infrastructure Management (M12–M13)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-073 | LLM Provider Management — Qwen config, external keys, token quota, privacy mode | P1 1.8 | `/platform/llm` | `GET PATCH /api/v3/platform/llm/config` `POST /api/v3/platform/llm/providers` | `llm_provider_configs` | v3 | 🟣 |
| F-074 | Qwen Fine-tuning — tenant-specific fine-tune on Silver data, Phase 3 | Shared 5.5 | `/platform/llm/finetune` | `POST /api/v3/platform/llm/finetune` | `finetune_jobs` | v3 | 🟣 |
| F-075 | Feature Store Online — Redis cluster, P99 <10ms inference | Shared 5.7 | — (backend) | `GET /api/v3/shared/feature-store/features` | `feature_definitions`, `feature_values` (Redis) | v3 | 🟣 |
| F-076 | Continuous Learning Loop — Kafka feedback → Feature Store → retrain | Shared 5.5 | — (backend pipeline) | — (Kafka consumer) | `model_versions`, `retraining_jobs` | v3 | 🟣 |

---

### Sprint 3.3 — Fairness, Audit & Compliance Export (M13–M14)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-077 | Fairness & Bias Detection — demographic parity, equalized odds, report | Shared 5.3 | `/p2/compliance/fairness` | `POST /api/v3/shared/fairness/audit` | `fairness_reports` | v3 | 🟣 |
| F-078 | Audit Log Query — search, filter, paginate, 2-year retention | Shared 5.4 | `/p2/audit` | `GET /api/v3/enterprise/audit-log` | `audit_log` | v3 | 🟣 |
| F-079 | Compliance Exporter — SOC2 evidence pack, EU AI Act Article 9/10/13/17 | Shared 5.4 | `/p2/compliance/export` | `POST /api/v3/enterprise/compliance/export` | `audit_log`, `decision_audit_log` | v3 | 🟣 |
| F-080 | MCP Server — JSON-RPC 2.0, Knowledge Graph exposure, tenant-scoped tools | Shared | `/mcp/` | `/mcp/jsonrpc` (JSON-RPC 2.0) | `mcp_sessions`, `kg_nodes` | v3 | 🟣 |

---

### Sprint 3.4 — Billing Portal + Vietnamese Payments (M14–M15)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-081 | Subscription Management — P2 view: tab Quota/Plan/Upgrade, ROI billing report | Billing | `/billing/subscription` | `GET /api/v3/billing/subscription` | `subscription_plans`, `enterprise_monthly_billing` | v3 | 🟣 |
| F-082 | Invoice Generation — auto monthly, Nghị định 123 e-invoice format | Billing | `/billing/invoices` | `GET /api/v3/billing/invoices` `GET /api/v3/billing/invoices/:id/pdf` | `invoices` | v3 | 🟣 |
| F-083 | Payment Gateway — VietQR, Momo, VNPay, ZaloPay, card | Billing | `/billing/payment` | `POST /api/v3/billing/payment/initiate` `POST /api/v3/billing/payment/webhook` | `payment_transactions` | v3 | 🟣 |

---

### Sprint 3.5 — Multi-region DR + Logistics Vertical (M15–M16)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-084 | Multi-region Deployment — active-passive, automatic failover RTO <4h | Shared | `/platform/health` (DR tab) | `GET /api/v3/platform/dr/status` | — (infra) | v3 | 🟣 |
| F-085 | Data Drift Monitor — PSI + KL divergence, alert on drift | Shared 5.7 | `/platform/health` | `GET /api/v3/platform/drift-monitor` | `drift_reports` | v3 | 🟣 |
| F-086 | Logistics Analysis Templates — demand forecast, route optimization | P2 2.8 | `/p2/analysis/logistics` | `POST /api/v3/enterprise/analysis/run` (logistics templates) | `analysis_results` | v3 | 🟣 |

---

### Sprint 3.6 — Scaling, i18n, SEA Expansion (M16–M18)

| ID | Function | Module | Screens | Key APIs | Entities | v | Status |
|----|----------|--------|---------|----------|----------|---|--------|
| F-087 | Organization Branding — logo, theme, subdomain, email+PDF branding | P2 2.1 | `/p2/settings/branding` | `GET PATCH /api/v3/enterprise/branding` | `tenant_settings` | v3 | 🟣 |
| F-088 | i18n — EN/JA/KO/ZH UI support (VI already done) | Frontend | (all screens) | — (i18n library) | — | v3 | 🟣 |
| F-089 | Notification Dispatch — multi-channel: in-app, email, Slack, webhook | Shared 5.10 | `/p2/alerts` | `POST /api/v3/shared/notifications/dispatch` | `notification_events` | v3 | 🟣 |
| F-090 | SOC 2 Type II Readiness — controls documentation, evidence automation | Shared | `/platform/compliance` | — (audit automation) | `compliance_checks` | v3 | 🟣 |
| F-091 | Dedicated Schema Option — DB-per-tenant for ENT MAX | Shared | — (infra) | — | — | v3 | 🟣 |
| F-092 | Kaori MCP Server Security — scope token per enterprise, rate limit, audit | Shared | `/platform/llm` (MCP tab) | — (MCP auth middleware) | `mcp_sessions` | v3 | 🟣 |

---

## Domain Entity Reference

### Phase 1 Core Tables (PostgreSQL)
| Entity | Key Columns | Notes |
|--------|-------------|-------|
| `tenants` | `id`, `name`, `plan`, `status`, `enterprise_id` | Workspace container |
| `users` | `id`, `tenant_id`, `email`, `role`, `portal` | All portals |
| `refresh_tokens` | `id`, `user_id`, `token_hash`, `expires_at` | Auth |
| `token_blacklist` | `jti`, `expires_at` | Logout invalidation |
| `workspace_keys` | `id`, `tenant_id`, `key_hash`, `revoked_at` | `KAORI-XXXX` onboarding |
| `pipeline_runs` | `id`, `tenant_id`, `status`, `sha256`, `source_filename` | Idempotency key = sha256 |
| `bronze_files` | `id`, `pipeline_run_id`, `tenant_id`, `s3_path` | Append-only |
| `bronze_rows` | `id`, `file_id`, `tenant_id`, `raw_payload` JSONB | Append-only |
| `column_mappings` | `id`, `pipeline_run_id`, `source_column`, `canonical_name`, `confidence` | Schema detection |
| `silver_rows` | `id`, `pipeline_run_id`, `tenant_id`, `row_data` JSONB | Post-cleaning |
| `analysis_runs` | `id`, `pipeline_run_id`, `tenant_id`, `templates` TEXT[], `status` | Multi-template |
| `analysis_results` | `id`, `analysis_run_id`, `template_id`, `results_payload` JSONB | ChartBlock[] |
| `decision_audit_log` | `id`, `tenant_id`, `decision_type`, `confidence`, `method`, `alternatives` JSONB | K-6 invariant |
| `enterprise_monthly_billing` | `enterprise_id`, `billing_month`, `unique_customers_billed` | Billing unit |
| `tenant_settings` | `tenant_id`, `language`, `ai_consent_external`, `theme` | Settings |

### Phase 2 Additional Tables
| Entity | Key Columns | Notes |
|--------|-------------|-------|
| `gold_features` | `tenant_id`, `customer_external_id`, `churn_probability`, `revenue_at_risk`, `is_actioned` | K-9: NUMERIC(5,4) for rates |
| `framework_sessions` | `id`, `tenant_id`, `framework_type`, `result_json` JSONB | SWOT/Fishbone etc. |
| `alert_rules` | `id`, `tenant_id`, `condition`, `channels` TEXT[], `last_fired_at` | Rate limit 1/5min |
| `reports` | `id`, `tenant_id`, `type` (auto/manual), `content_json` JSONB, `distributed_at` | |
| `risk_items` | `id`, `tenant_id`, `probability`, `impact`, `risk_score`, `owner_id`, `status` | |
| `strategy_plans` | `id`, `tenant_id`, `framework` (OKR/OGSM), `content_json` JSONB | |
| `workflow_definitions` | `id`, `tenant_id`, `canvas_json`, `version`, `status` | Temporal.io backed |
| `model_versions` | `id`, `project_id`, `checksum`, `metrics` JSONB, `state`, `promoted_at` | MLflow backed |
| `studio_projects` | `id`, `enterprise_id`, `name`, `assigned_analysts` UUID[] | |
| `prompt_templates` | `id`, `vertical`, `task`, `content`, `version`, `ab_test_id` | |
| `personal_goals` | `id`, `user_id`, `title`, `target`, `progress`, `deadline` | P4 only |
| `kg_nodes` | `id`, `tenant_id`, `type`, `label`, `properties` JSONB | Neo4j + pgvector |
| `kg_edges` | `id`, `from_node`, `to_node`, `edge_type`, `weight` | |
| `agent_sessions` | `id`, `tenant_id`, `workflow_type`, `state` JSONB, `transcript` JSONB | |
| `roi_billing_events` | `id`, `enterprise_id`, `decision_id`, `revenue_at_risk`, `is_actioned` | North Star metric |
| `guardrail_violations` | `id`, `tenant_id`, `guard_type`, `input_hash`, `action_taken` | Immutable |
| `llm_request_logs` | `id`, `tenant_id`, `provider`, `tokens_in`, `tokens_out`, `cost_usd` | Cost governance |

### Phase 3 Additional
| Entity | Key Columns | Notes |
|--------|-------------|-------|
| `compliance_checks` | `id`, `tenant_id`, `standard`, `control`, `status`, `evidence` JSONB | |
| `invoices` | `id`, `tenant_id`, `billing_month`, `amount_vnd`, `einvoice_id`, `pdf_url` | Nghị định 123 |
| `payment_transactions` | `id`, `tenant_id`, `gateway`, `amount_vnd`, `status`, `gateway_ref` | VietQR/Momo/VNPay |
| `mcp_sessions` | `id`, `tenant_id`, `client_id`, `tools_called` TEXT[], `created_at` | JSON-RPC 2.0 |
| `drift_reports` | `id`, `tenant_id`, `feature`, `psi_score`, `alert_fired` | |
| `erasure_requests` | `id`, `tenant_id`, `subject_id`, `requested_at`, `completed_at`, `status` | 30-day SLA |

---

## Progress Summary

| Phase | Total | ✅ Done | 🔄 In Progress | ⬜ / ❌ Pending |
|-------|-------|---------|----------------|-----------|
| Phase 1 (F-001–F-032) | 32 | **32** ✅ closed 2026-04-27 (tag `v1.0-phase1-complete`) + Sprint 7 polish (`v1.1-pilot-ready`) + Sprint 8 conversational layer (F-NEW4) | 0 | 0 |
| Phase 2 (F-033–F-068) | 36 | 11 (F-033/034/035/036/037/038/039/040/041/060/061) | 0 | 25 |
| Phase 3 (F-069–F-092) | 24 | 0 | 0 | 24 |
| **Total** | **92** | **32** | **1** | **59** |

**Phase 2 status (2026-05-02):** kickoff. F-038 Reports backend merged via PR #113 — first feature to use the three Phase-1 hardening rails (Issue #3 LLM output validation, Issue #4 Kafka schema registry, Issue #6 notification outbox). FE wiring of templates 47/48 follows on the next PR. See `docs/PHASE2_PLAN.md` for the running tracker.

### Phase 1 Pending (must complete before Phase 2)
- **F-015** User & Role Management — `/p2/users` page + API
- **F-016** Enterprise Settings — **flipped from ✅ to ❌ Ghost on 2026-04-26 audit**: FE page exists at `frontend/app/(app)/settings/page.tsx`, no `EnterpriseSettingsController`, no `tenant_settings` migration. K-4 enforcement at `llm_router.py` therefore unbacked.
- **F-022** Pipeline Run History — `/p2/pipelines` list page
- **F-NEW2** Pipeline Status SSE — `GET /api/v1/pipelines/:id/events` real-time stream (added 2026-04-26 from v3.1 reconciliation). Polling fallback retained.
- **F-029** AI Decision Log — `/p2/decisions` page (backend `/decisions` 404). **Hard prerequisite:** P0 #6 K-6 audit wire-up (helper exists in `ai-orchestrator/shared/audit.py` but only `schema.py` calls it — without `clean.py` + `runner.py` + `llm_router.py` calling, page renders ~1 decision type out of dozens). See `PHASE1_CLOSEOUT_PLAN.md` Sprint 0.5.
- **F-030** Subscription & Quota — `/p2/subscription` page
- **F-031** Unique Billing Cron — daily job not yet wired (frontend reads, no aggregator yet)
- **F-032** Gold Layer — `gold/` directory empty, no aggregation logic. **Pre-flight:** verify `silver_rows.row_data` JSONB writes `customer_external_id` consistently before starting aggregator; if missing, fix silver normalizer first.

### 2026-04-26 Audit reconciliation (what was found vs claimed)

Cross-checked `archive/phase_1_execution.md` (Apr 25, pre-Batch-2) against current code (post Phase 3 hardening Apr 26):

| F-ID | phase_1_execution claim | Actual (verified 2026-04-26) | Action |
|------|-------------------------|------------------------------|--------|
| F-010 | ❌ Ghost — "no controller exists" | ✅ Shipped Batch 1 — `PlatformAdminController.java` + 9 frontend routes + tests | False alarm; Apr-25 audit predated Batch 1 ship |
| F-014 | ❌ Ghost — "JwtAuthFilter never checks role" | ✅ Shipped — `TrustedGatewayAuthFilter` + `SecurityConfig` role matchers + `JwtAuthFilter.PLATFORM_ROLES` | False alarm; Phase 3 fixed the gap |
| F-016 | ❌ Ghost — "no controller exists" | ✅ Shipped Sprint 1 (PR #69) — migration 015 + EnterpriseSettingsController + TenantSettings entity/repo/service + K-4 enforcement in `engine/llm_router.py` | Resolved 2026-04-27 |
| F-027 | ❌ Ghost — "no /api/v1/charts/render handler" | ✅ Shipped — `frontend/components/charts/chart-registry.tsx` defines 15 kinds + FlexibleChart. Render is client-side, not server endpoint (spec interpretation differs) | False alarm; spec interpretation drift, not missing code |
| F-013 | 🔄 Partial — "endpoint name mismatch (`/auth/workspace/activate` ≠ `/enterprise/onboarding`)" | 🔄 Still partial — both endpoints intended; `/enterprise/onboarding` not impl | Re-evaluate scope: rename, drop one, or impl both |

**Why this happened:** `phase_1_execution.md` was written 2026-04-25, before Batch 1 (F-008 deepen + F-010), Batch 2 (F-009 + F-011 + Module 3), and Phase 3 hardening — all landed Apr 26. The file is now archived; this table preserves what it correctly identified vs what was already in flight.

**P0 defects from `architecture/ARCHITECTURE_REVIEW.md` §4 — status as of 2026-04-26:**
- ✅ #1 SecurityConfig (Phase 3 TrustedGatewayAuthFilter)
- ✅ #2 Kafka topics (`kafka_topics.py` const + `kaori.*` rename)
- ✅ #3 RBAC (role matchers in SecurityConfig + JwtAuthFilter)
- 🟡 #4 RLS — helper ready, routers not switched (Sprint 0.5)
- ✅ #5 Kafka outbox + consumer dedup (`outbox.py` + `mark_processed`)
- 🟡 #6 K-6 audit — helper ready, only `schema.py` wired (Sprint 0.5)

### Batch 2 — Closed 2026-04-26 (Phase 1 hardening)
- **F-009** Private Key Management — additive nested routes; reused `PlatformKeyService`. 25 new tests.
- **F-011** Billing Monitor — 4 endpoints + 4 frontend pages; new `BillingMath` shared with F-008. CSV with UTF-8 BOM. 50 new tests.
- **Module 3 — TOTP MFA + sessions** (deepens F-007) — RFC 6238 SHA-1 with AES-256-GCM at-rest encryption, ±30s skew. New migration 012 (`mfa_secret_enc`, `admin_sessions`). IDOR-safe session revoke. 40 new tests.
- **Test totals**: 207 → 322 backend tests (+115). Frontend routes: 14 → 25.

### Phase 3 — Closed 2026-04-26 (Hardening + Productization of Batch 2)
- **3.1.a** Platform admin login + session lifecycle — `POST /auth/platform/{login,refresh}`; session row on login; idle (30 min) + absolute (24 h) timeouts enforced in the auth filter. Migration 013 adds `revoke_reason`. **+37 tests**.
- **3.1.b** MFA rate limit + audit log — 5 fails / 15 min → 423; new `platform_admin_audit_log` table (migration 014); IP propagated through every event. **+7 tests**.
- **3.1.c** MFA key management — `KAORI_MFA_KEY` wired across `.env.example` + `docker-compose.yml`; production profile fail-fast; `scripts/generate-mfa-key.sh` + rotation procedure documented. **+6 tests**.
- **3.2.a** Flyway migration runner — `flyway-core` baselines at v14; SQL stays in `infrastructure/postgres/migrations/` and is copied into the JAR classpath at build time. Future migrations apply automatically on auth-service startup. **+3 tests** (1 Docker-gated).
- **3.2.b** API gateway routing — consolidated `/api/v1/platform/**` catch-all; `X-Session-Id` forwarded for platform tokens; `token_kind=platform` enforced; all 4xx short-circuits return RFC 7807. **+7 gateway tests**.
- **3.3** Polish + CI — `POST /security/sessions/revoke-others` bulk endpoint; QR rendering on MFA page (qrcode lib, canvas only); RFC 7807 error parsing in `lib/api.ts`. Existing `.github/workflows/ci.yml` already runs `mvn verify` + frontend typecheck + build. **+10 auth tests**.
- **Phase 3 totals**: **auth-service 385 / 385** (322 → 385, +63); **api-gateway 45 / 45** (39 → 45, +6); frontend tsc + next build clean.

### Phase 3 — Deferred (next phase, post-validation)
- MFA enforcement at login (2-step `mfa_challenge_token` flow) — `mfa_enabled` is informational only today
- Monitoring / metrics — WARN logs on rate-limit + token_kind mismatch; Grafana panels not yet built
- Audit feed UI at `/platform/security/audit` — repo + service ready, no FE consumer
- Session creation hook for enterprise users (platform admins only today)

---

## v3.1 Reconciliation (2026-04-25)

> Source: `docs/product/Feature_Tree_Kaori_AI_v3.1.xlsx` (108 endpoints in API Catalog · 216 screens across all portals).
> Cross-checked against BRD v3.0 phase plan (M1-M4 Phase 1, M5-M12 Phase 2, M13-M24 Phase 3) and v3.1 screen-sheet phase tags. Frontend mapping in `docs/FRONTEND_TASKS_PHASE.md`.

### API gaps — additions / amendments

| F-ID | Change | Detail |
|------|--------|--------|
| F-007 | **Amend APIs** | Add `POST /api/v1/platform/auth/mfa/verify` (TOTP + backup code) — referenced by P1 screen 1.0/2 MFA Challenge |
| F-011 | **Amend APIs** | Add `GET /api/v1/platform/billing/alerts` (workspaces >80%/>95% quota) — referenced by P1 screen 1.4/3 Quota & Alerts |
| F-NEW1 | **Phase 1 (shipped, partial)** | Notification Service (port 8094) — SMTP sender. Wired via direct HTTP from auth-service for password reset. Kafka `kaori.alerts.fire` topic deferred Phase 2 with F-037 |
| F-NEW2 | **Phase 1 (added 2026-04-26)** | Pipeline Status SSE — `GET /api/v1/pipelines/:id/events` real-time `text/event-stream` for upload/schema/cleaning progress. Polling fallback retained. Status: ⬜ Pending — see PHASE1_CLOSEOUT_PLAN.md Sprint 1 |
| F-NEW3 | ~~**NEW (Phase 1)**~~ → **Deferred to Phase 2 (decided 2026-04-26)** | **Data Explorer** — `/p2/data` (P2 module 2.5). APIs: `GET /api/v1/enterprise/data/{bronze\|silver\|gold}/tables`, `GET /api/v1/enterprise/data/lineage?table_id=`. Pilot UAT does not require raw Bronze/Silver/Gold browsing; pair with F-056 Knowledge Graph for insight value. Status: ⬜ Phase 2 |
| F-NEW4 | **Phase 1.5 — shipped 2026-04-29 (Sprint 8)** | **Conversational Layer (Chat tool registry)** — `POST /api/v1/chat/{enterprise,platform}/stream` SSE. Right-side ChatPanel drawer mounted on both portal shells. 6 curated tools v0 (3 P2 + 3 P1); AI never writes SQL (K-16 added). Inspired by `congdinh2008/chatbot-ai-mcp-demo`, adapted for multi-tenant Kaori. K-12 / K-15 / K-16 enforced in registry. Standalone MCP server stays a Phase 2 goal. Status: ✅ — see `docs/specs/CHAT_TOOL_REGISTRY.md`, UAT in `docs/uat/CHAT_PANEL.md` |
| F-025 | **Amend APIs** | Add `GET /api/v1/enterprise/insights/{id}` (insight detail with citations + confidence) |
| F-027 | **Amend APIs** | Add `GET /api/v1/enterprise/charts/catalog` (chart picker source for screen 2.14/1) |
| F-087 | **Move phase 3 → 2** | Branding (`/p2/branding`) — v3.1 screen 2.1 tagged Phase 2; should not wait for Phase 3 |
| F-082 | **Split phase** | Invoice list/detail backend → Phase 2; e-invoice per Nghị định 123 stays Phase 3 |
| F-083 | **Split phase** | Payment Gateway VietQR/Momo/VNPay/ZaloPay/card → Phase 2 (screens 6.1, 6.3); compliance hardening Phase 3 |
| F-078 | **Split phase** | Audit write API + storage → Phase 1 (v3.1 catalog tags Phase 1); Query UI at `/p2/audit` → Phase 2 |

### v3.1 Spec gaps escalated to source-of-truth fix (2026-04-26 audit)

These items exist in CLAUDE.md / Feature Tree but are **missing from the upstream BRD/PRD .docx files**. Source-of-truth chain is broken until these are absorbed back upstream:

| Topic | Where it lives now | Where it should also live | Action |
|-------|---------------------|---------------------------|--------|
| **Pricing tier SKUs** (PILOT 1M / ENT BASIC 2M / ENT MID 5M / ENT MAX 8M / ENT ROI 8M+1.5%) | CLAUDE.md §10 (canonical, confirmed 2026-04-26 by product) | `docs/product/Kaori_AI_BRD_v3.0.docx` § Pricing Model — currently only defines billing unit, not tier prices | **Promote to BRD v3.1 next revision.** Until then, F-030 Subscription page uses CLAUDE.md §10 as authority |
| **North Star metric `is_actioned` gate** | CLAUDE.md §1 ("North Star Metric") | TAI_LIEU + BRD only mention "churn risk detection" generically | Phase 1 ships `revenue_at_risk` measurement only; full metric requires Phase 2 F-060. Documented in DEMO_RUNBOOK |
| **F-NEW1/2/3/4 introduction** | BACKLOG v3.1 reconciliation only | Feature Tree v3.1 added F-NEW2 to "Phase 1 Reality Check" sheet; PRD/BRD don't mention F-NEW* | When BRD/PRD are next revised, add F-NEW1/F-NEW2/F-NEW4 (Conversational Layer) to scope; F-NEW3 added to Phase 2 scope |

### Phase tags reaffirmed (v3.1 API Catalog mis-tags overruled by screen-sheet authority)

The v3.1 API Catalog over-tags the following as Phase 1, but their consuming screens are Phase 2 — **keep as Phase 2 in BACKLOG**:

- F-034 Frameworks SWOT/6W/2H/Fishbone/MoM-YoY (screens 2.9/* Phase 2)
- F-036 Decision Override (screen 2.16/2 Override Form Phase 2)
- F-038 Reports auto/builder/distribute (screens 2.13/* Phase 2)
- F-057 Auto-DB Design (screens 2.7/* Phase 2)
- F-042..F-048 P3 Studio (entire portal Phase 2 per screen sheet)
- F-049..F-055 P4 Personal (entire portal Phase 2 per screen sheet)

### Screen-level honest impl status (from `Screen Status Summary` sheet)

| Portal | Total Screens | Impl | Partial | Ghost | Pending | % |
|--------|---------------|------|---------|-------|---------|---|
| P1 Platform | 34 | 3 | 9 | 4 | 18 | 9% |
| P2 Enterprise | 96 | 12 | 3 | 3 | 78 | 12% |
| P3 Studio | 20 | 0 | 0 | 0 | 20 | 0% |
| P4 Personal | 17 | 0 | 0 | 0 | 17 | 0% |
| Shared / Billing | 49 | 4 | 4 | 2 | 39 | 8% |
| **GRAND TOTAL** | **216** | **19** | **16** | **9** | **172** | **~9%** |

> Note: 9 screens are flagged as "Ghost" — feature claimed ✅ in trackers but no code. See `Phase 1 Reality Check` sheet for the F-ID-by-F-ID audit (F-010, F-014, F-016, F-027 are the main offenders). Frontend tasks for these are listed in `FRONTEND_TASKS_PHASE.md` §1.
