# Phase 2 Plan — Scale & Intelligence

> Owner: Nguyen Truong An (solo) · Created 2026-05-02 · Target: M5–M10 (rolling, no hard deadline)
> Source: `docs/BACKLOG.md` Phase 2 (F-033..F-068, 36 functions) · `CLAUDE.md` §14
>
> **Companion docs:**
> - `docs/PHASE1_CLOSEOUT_PLAN.md` — closed 2026-04-27, history only
> - `docs/BACKLOG.md` — feature catalog (status truth)
> - `docs/tasks/BACKEND_TASKS_PHASE.md` + `FRONTEND_TASKS_PHASE.md` — endpoint + screen task IDs

---

## 1. Scope decisions (locked)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Solo execution — feature-by-feature, one feature = one branch | Phase 1 cadence proved out |
| 2 | Default API prefix stays `/api/v1/...` until end of Phase 2 | F-038 backend already shipped under `/api/v1/reports`. Mass-rename to `/api/v2/{portal}/...` is a Phase 2.7 cross-cutting PR after most endpoints exist; doing it now would slow every feature PR |
| 3 | Each Phase 2 feature picks 1+ Phase-1 hardening rail to use end-to-end | Issue #3 (output validation) · Issue #4 (Kafka schema registry) · Issue #6 (notification outbox). F-038 used all three; future features can reach for whichever fit |
| 4 | Defer "build a new microservice" features (F-042..F-048 P3 Studio, F-049..F-055 P4 Personal) until Sprints 2.3/2.4 | Pilot is P2-only today; new portals need their own auth + RBAC + UI shell |

---

## 2. Hardening rails available (shipped late Phase 1, this batch)

| Rail | PR | Use case for Phase 2 features |
|------|----|------|
| **Issue #3 — LLM output validation** | #112 | Any feature that needs structured LLM output (Reports, Frameworks SWOT/Fishbone JSON, Risk Auto-Detect, Alert Rules condition compilation). Pass `output_schema`; gateway validates + repairs once on failure |
| **Issue #4 — Kafka schema registry** | #111 | Any new event topic needs `infrastructure/kafka/schemas/<topic>.json` + producer-side validation. CI guard `G10` enforces additive-only |
| **Issue #6 — Notification outbox** | #110 | Any feature that emits user-visible email (alert rules F-037, report-ready F-038, distribution F-038, decision-override F-036). INSERT into `notification_outbox` after the source-of-truth row commits — dispatcher retries with backoff |
| **Curated chat tool registry (F-NEW4)** | merged Sprint 8 | Surface a tool to the chat panel by adding it to `services/ai-orchestrator/chat/tools/`. K-12 + K-15 + K-16 invariants enforced by registry — never accept tenant_id from args |
| **RLS cutover (`kaori_app NOBYPASSRLS`)** | #107 | Tenant filtering is automatic via `acquire_for_tenant()`. Cross-tenant rows are invisible at the SQL layer; 404 just falls out of the SELECT |
| **OpenAPI types codegen** | already wired in `frontend/lib/api/types/orchestrator.d.ts` | Run `npm run gen:api` after backend ships; FE imports `components["schemas"]["..."]` |

---

## 3. Status legend

| Symbol | Meaning |
|---|---|
| ⬜ | Not started |
| 🟡 | In progress (branch open, no PR) |
| 🟢 | PR open |
| ✅ | Merged + tests pass |
| 🔄 | Backend or frontend done but other half pending |
| ❌ | Blocked (note in Risk register) |

---

## 4. Sprint plan

### Sprint 2.2 — Reports + Risk + Strategy (M6–M7) — **active**

| F-ID | Title | Backend | Frontend | UAT | Notes |
|---|---|---|---|---|---|
| **F-038** | Reports — auto LLM-generated | ✅ PR #113 (`994ceef`) — `POST /api/v1/reports/generate` (202 + bg worker), `GET /api/v1/reports`, `GET /api/v1/reports/{id}`, migration 027, built-in `monthly_summary` template, `kaori.reports.generated` event, `report-ready` outbox email | 🟡 — wiring of templates 47-reports-hub + 48-report-auto on next PR | 🟡 — `docs/uat/F-038-reports.md` | Builder (49) / Templates library (50) / Distribution (51) screens deferred to follow-up PRs once auto-path is proven in pilot |
| F-039 | Risk Management | 🟡 BE this branch | ⬜ | ⬜ | Migration 033 + CRUD endpoints + auto-computed score/severity via DB trigger + 16 unit tests. Auto-detect from data + risk_snapshots history + alert wiring deferred to v1 |
| F-040 | Strategy Builder | ⬜ | ⬜ | ⬜ | OKR/OGSM canvas; complex FE — split into 2-3 sub-PRs |
| F-041 | Explainability Layer | ✅ this branch — `services/ai-orchestrator/explainability/` (templates + service + router) + gateway route + 7 BE tests | ✅ this branch — lazy section in `/p2/decisions/[id]` with top-3 factor rows + weight bars + narrative + confidence_explanation + MSW handler | ✅ `docs/uat/F-041-explainability.md` (6 SCN) | "Lite" — LLM-derived top factors from audit row, not real SHAP (model registry F-073). Response shape compatible with future SHAP swap |

### Sprint 2.1 — Multi-tier Analysis + Frameworks (M5–M6) — **next after F-038 FE wiring**

| F-ID | Title | Status |
|---|---|---|
| F-033 | Multi-tier Analysis (Intermediate/Advanced tiers, multi-pipeline scope) | ✅ BE PR A + PR B merged + FE PR C/D — all three tiers wired end-to-end. PR B added `queue_advanced` / `run_advanced` (gates on `tenant_settings.consent_external_ai`) + `POST /api/v1/analysis/runs/{id}/approve` MANAGER role gate + real external-AI quota counter from `decision_audit_log`. FE 38 advanced template wires sources picker + framework toggle + dispatch + approval banner on result page. 374 BE tests, frontend tsc clean. **Multi-workspace memberships** (1 user → N workspaces) deferred to PR D when `enterprise_users` schema unique-constraint can be relaxed |
| F-034 | Analysis Frameworks (SWOT, 6W/2H, Fishbone, MoM/YoY) — uses Issue #3 output_schema | ✅ BE PR #119 + FE this branch — migration 030 + 4 built-in templates Python registry + `/api/v1/frameworks/{generate,list,detail,templates}` + 16 tests + `/p2/frameworks` hub + 4 wired framework pages + MSW. MoM/YoY (calculation) + custom deferred to v1 |
| F-035 | Cohort Retention | ✅ Phase 1 engine + chart already shipped (`StatisticalEngine._cohort` + `RHeatmap`); F-033 basic-tier picker surfaces it. This branch added MSW fixture + UAT script `docs/uat/F-035-cohort.md`. No dedicated FE page (basic-tier picker covers it) |
| F-036 | Decision Detail & Override — write to `decision_overrides`, emit `kaori.feedback.actions` | ✅ BE PR #122 + FE this branch — migration 031 + endpoints + Kafka emit + 11 BE tests + wired `/p2/decisions/[id]` page with override modal + revoke flow + is_actioned toggle + MSW handlers. SHAP explain (F-041) deferred to v1 |
| F-037 | Alert Rules — first user of `notification_outbox` for billing alerts (closes the F-031 quota email TODO from CLAUDE.md §14) | ✅ BE PR #116 + FE PR #117 — migration 028 + `BillingAlertService` dispatcher + per-tier email + `/api/v1/enterprises/alerts` CRUD + `/p2/alerts` page (events + rules tabs) + MSW handlers. Slack/webhook channels + arbitrary-metric evaluator deferred to v1 follow-ups |

### Sprint 2.3 — P3 Studio Portal (M7–M8)

F-042..F-048 — entire portal. New auth flow, new RBAC roles (`STUDIO_ADMIN`, `STUDIO_ANALYST`), new shell. Plan as standalone milestone after at least F-033 + F-038 finished surface-to-DB.

### Sprint 2.4 — P4 Personal Portal (M8–M9)

F-049..F-055 — same shape as Sprint 2.3 but for individual users. Self-signup + OAuth + GDPR delete.

### Sprint 2.5 — Knowledge Graph + Auto DB Design + Blast Radius (M8–M9)

F-056..F-058 — Neo4j (or pgvector fallback), AI-driven schema generation, impact analysis.

### Sprint 2.6 — ROI Hybrid Billing + Agent Framework (M9–M10)

| F-ID | Title | Status |
|---|---|---|
| F-059 | ROI Hybrid Billing — cron monthly, 1.5% revenue saved, cap 20M VND | 🔵 |
| F-060 | is_actioned Workflow / North Star tile | ✅ shipped Sprint 2.1 close-out |
| F-061 | Agent Framework — Planner/Executor/Critic loop | ✅ BE PR _pending_ (this branch). Custom Python P/E/C (BRD T11 punted — MS AF swap-in path preserved). 1 workflow `insight-to-action` + 2 action tools gated by `dry_run` (default ON). 27 unit tests added (ai-orchestrator 381 → 408). **Defer:** 2 other workflows, FE `/p2/workflows`, streaming SSE, human-in-loop queue, P3 Studio surface |
| F-062 | Guardrails Validation — PII, jailbreak, hallucination | 🔵 |
| F-063 | External AI Gateway — full feature set | 🔵 |

### Sprint 2.7 — Advanced AuthZ + Workflow Builder + Pilot Conversion (M10)

F-064..F-068 — ABAC + Hybrid PDP, Workflow Builder (Temporal.io), Pilot Conversion Tracking, Plans CRUD, SSO.

---

## 5. Cross-cutting Phase 2 work

These don't have F-IDs but block multiple features. Schedule as gaps appear.

| Item | Trigger to schedule | Notes |
|---|---|---|
| `/api/v2/{portal}/...` URL migration | When ≥ 60% of Phase 2 endpoints ship | One PR + gateway redirect for old `/api/v1/...` paths. Do NOT do it per-feature |
| Quota alert email copy (F-031 limitation) | F-037 ships | F-NEW1 generic copy → per-tier upsell text. CLAUDE.md §14 limitation closes |
| ~~North Star tile (F-031 / F-060 limitation)~~ | ✅ Closed by F-060 BE this branch — `GET /api/v1/dashboard/north-star` reads canonical `gold_features.is_actioned` directly. Sprint 7 PR D's side table stays for the per-decision toggle on `/decisions` (different surface) | — |
| Phase 2 dependencies (Triton, vLLM, Temporal.io, Neo4j) | When first feature needs them | Follow `docker-compose.yml` extension pattern; ADR per new service |
| Audit feed UI at `/platform/security/audit` | Phase 1 deferred | Repo + service ready since Batch 2; FE consumer left to do |

---

## 6. Dependency map (phase 2 internal)

```
F-033 (analysis tiers) ── F-034 (frameworks)
                       └─ ✅ F-036 (decision override BE+FE) ── ✅ F-060 BE+FE (is_actioned canonical + at-risk page + tile)

F-037 (alerts) ── outbox ── F-038 (reports) ──┬─ ✅ distribution BE+FE ─ scheduler / builder v1 follow-ups
                                              └─ F-047 (P3 studio reports) — Phase 2.3

F-056 (KG) ── F-058 (blast radius)

F-061 (agent framework) ── F-062 (guardrails) ── F-063 (external AI gateway)
```

---

## 7. Risk register

| # | Risk | Mitigation | Trigger |
|---|---|---|---|
| R1 | Phase 2 features land but FE wiring lags → "demi-feature" repeat (F-038 backend without UI) | Each backend PR ends with explicit FE-wiring follow-up issue + estimate | After every backend PR merges |
| R2 | New microservices (Triton, Temporal.io, Neo4j) blow up the dev `docker-compose up` time → pilot laptop can't run stack | Profile per-service in `docker-compose.yml` (`profiles: [phase2-ml]`); pilot stays on Phase-1 profile by default | When R2 service is added |
| R3 | LLM cost overrun once Frameworks (F-034) + Auto-DB (F-057) + Reports (F-038) all generate structured output | Track tokens via existing K-3 audit; alert if monthly external-LLM cost > 2× Phase 1 baseline | Monthly cost review |
| R4 | OpenAPI types drift between backend ship + FE wiring | Make `npm run gen:api` step part of every backend-PR checklist; CI guard already exists | Every backend PR |
| R5 | Solo-dev fatigue across a 6-month phase | Soft-cap to 1 feature/week unless hardening rail amortises ≥ 3 features | Weekly self-check |

---

## 8. Daily check-in protocol

Same as Phase 1:
1. Open this file, set the active task to 🟡
2. End of session: status → 🟢 if PR open, ✅ if merged, back to ⬜ if rolled back
3. After every backend PR: open a follow-up issue for FE wiring + UAT script
4. Weekly: glance at the dependency map; reorder if a downstream item is gating

---

## 9. Out of scope (don't touch this phase)

- **Phase 3 features (F-069..F-092)** — Finance vertical, fairness/bias, MCP server, multi-region, e-invoice payment gateway compliance hardening
- **Hard infra rewrites** — Triton/vLLM only added when first feature actually needs GPU inference; until then llm-gateway + Ollama covers it
- **MFA enforcement at login (2-step `mfa_challenge_token`)** — Phase 3 deferred per CLAUDE.md §14
- **Monitoring / Grafana dashboards** — Phase 3 deferred; WARN logs exist for grep
