# Kaori AI — API Master Catalog v4.0

> **Source:** Feature Tree v4.0 — `🌐 API Master Catalog` sheet (169 endpoints) + `🔄 API Dependencies` (42 edges).
> **Format:** REST endpoints organised by Portal/Domain → Resource. Auth column shows JWT scope.
> **Updated:** 2026-05-21 (Phase 2.8 Round 5 — N2 OpenAPI regen + SLA/RateLimit/Errors policy + 10 PM sources). Live snapshots: `docs/api-specs/pipeline.openapi.json` (24 paths) + `docs/api-specs/orchestrator.openapi.json` (163 paths) + auth-service `/v3/api-docs` springdoc-openapi.
> **Cross-ref:** NFRS §2 Performance (SLA targets) · mig 099 tenant_quotas (rate limit) · `docs/specs/MESSAGE_DEFINITIONS.md` (RFC 7807 error codes) · CLAUDE.md §6 API conventions.

## Phase Distribution

| Phase | API count (Feature Tree v4.0 baseline) | Actual shipped (2026-05-21) |
|---|---|---|
| Phase 1 | 118 | 118 ✓ |
| Phase 1-2 | 5 | 5 ✓ |
| Phase 1.5 | 8 | 8 ✓ |
| Phase 2 | 35 | 35 ✓ |
| **Phase 2.5/2.6/2.7/2.8 NEW** (ship qua CR-0001..0012 + governance wiring) | — | **+~30** (PM extra connectors + AI nodes + lineage + DLQ + policy engine + CS vertical + claims framework) |

**Total baseline:** 166 endpoints
**Total actual:** ~187 paths (pipeline 24 + orchestrator 163 + auth ~10) — see live OpenAPI snapshots.

---

## P1 Platform

### Auth

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0001 | POST | `/api/v1/platform/auth/login` | Admin login with email+password, MFA gate | Phase 1 | JWT (admin) |
| API-0002 | POST | `/api/v1/platform/auth/mfa/verify` | Verify TOTP or backup code | Phase 1 | JWT (admin) |
| API-0003 | POST | `/api/v1/platform/auth/logout` | Invalidate session + blacklist refresh | Phase 1 | JWT (admin) |

### Workspace

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0004 | GET | `/api/v1/platform/workspaces` | List enterprise workspaces with filter (plan, status) | Phase 1 | JWT (admin) |
| API-0005 | POST | `/api/v1/platform/workspaces` | Create new workspace + generate KAORI-XXXX key | Phase 1 | JWT (admin) |
| API-0006 | GET | `/api/v1/platform/workspaces/{id}` | Workspace detail + usage + billing + members | Phase 1 | JWT (admin) |
| API-0007 | PATCH | `/api/v1/platform/workspaces/{id}` | Update lifecycle: activate/suspend/archive | Phase 1 | JWT (admin) |

### Keys

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0008 | POST | `/api/v1/platform/keys` | Issue private key (reveal once, SHA-256 store) | Phase 1 | JWT (admin) |
| API-0009 | DELETE | `/api/v1/platform/keys/{id}` | Revoke key | Phase 1 | JWT (admin) |

### Admins

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0010 | POST | `/api/v1/platform/admins/invite` | Invite platform admin with role | Phase 1 | JWT (admin) |
| API-0011 | PATCH | `/api/v1/platform/admins/{id}` | Deactivate/reset/change-role | Phase 1 | JWT (admin) |

### Billing

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0012 | GET | `/api/v1/platform/billing/monitor?month=` | Revenue, quota, overage per workspace | Phase 1 | JWT (admin) |
| API-0013 | GET | `/api/v1/platform/billing/alerts` | Alert >80% quota workspaces | Phase 1 | JWT (admin) |

### Pilot

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0014 | GET | `/api/v1/platform/pilot-conversion` | Pipeline view Pilot→ENT + D25/D30 triggers | Phase 1 | JWT (admin) |

### Health

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0015 | GET | `/api/v1/platform/health` | Realtime KPIs: services, inference latency, errors | Phase 1 | JWT (admin) |

### Plans

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0016 | GET | `/api/v1/platform/plans` | List subscription plans | Phase 1 | JWT (admin) |
| API-0017 | POST | `/api/v1/platform/plans` | Create new plan (soft update preserves history) | Phase 1 | JWT (admin) |

### LLM

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0018 | GET | `/api/v1/platform/llm/providers` | List configured LLM providers | Phase 2 | JWT (admin) |
| API-0019 | POST | `/api/v1/platform/llm/providers` | Add/configure provider (OpenAI/Claude/Gemini/Azure/Qwen) | Phase 2 | JWT (admin) |
| API-0020 | PATCH | `/api/v1/platform/llm/providers/{id}/privacy-mode` | Toggle data masking + external allow | Phase 2 | JWT (admin) |

---

## P2 Enterprise

### Auth

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0021 | POST | `/api/v1/enterprise/auth/login` | Login with invite or private key | Phase 1 | JWT (tenant-scoped) |
| API-0022 | POST | `/api/v1/enterprise/auth/activate/{token}` | First login activation | Phase 1 | JWT (tenant-scoped) |

### AuthZ

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0023 | POST | `/api/v1/enterprise/authz/evaluate` | Hybrid PDP: RBAC+ABAC evaluation | Phase 2 | JWT (tenant-scoped) |
| API-0024 | POST | `/api/v1/enterprise/authz/policies` | CRUD ABAC policy | Phase 2 | JWT (tenant-scoped) |
| API-0025 | POST | `/api/v1/enterprise/authz/simulate` | Simulate policy change impact | Phase 2 | JWT (tenant-scoped) |

### Branding

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0026 | POST | `/api/v1/enterprise/branding` | Update logo, colors, theme, subdomain | Phase 1 | JWT (tenant-scoped) |

### Onboarding

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0027 | POST | `/api/v1/enterprise/onboarding/activate-key` | Activate KAORI-XXXX private key | Phase 1 | JWT (tenant-scoped) |
| API-0028 | POST | `/api/v1/enterprise/onboarding/pilot/upgrade` | 1-click upgrade PILOT→ENT at D30 | Phase 1 | JWT (tenant-scoped) |

### Dashboard

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0029 | GET | `/api/v1/enterprise/dashboard/kpis` | Main dashboard KPIs | Phase 1 | JWT (tenant-scoped) |

### Users

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0030 | POST | `/api/v1/enterprise/users/invite` | Invite member with role | Phase 1 | JWT (tenant-scoped) |

### Data

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0031 | GET | `/api/v1/enterprise/data/{bronze\|silver\|gold}/tables` | List tables per medallion layer | Phase 1 | JWT (tenant-scoped) |
| API-0032 | GET | `/api/v1/enterprise/data/lineage?table_id=` | Table lineage (Bronze→Silver→Gold) | Phase 1 | JWT (tenant-scoped) |

### Pipeline

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0033 | POST | `/api/v1/enterprise/data/bronze/upload` | Multipart CSV/Excel upload to Bronze | Phase 1 | JWT (tenant-scoped) |
| API-0034 | POST | `/api/v1/enterprise/pipelines` | Create pipeline (5-step wizard) | Phase 1 | JWT (tenant-scoped) |
| API-0035 | POST | `/api/v1/enterprise/pipelines/{id}/steps/{1-5}/run` | Execute wizard step | Phase 1 | JWT (tenant-scoped) |
| API-0036 | GET | `/api/v1/enterprise/pipelines/{id}/results` | Pipeline outputs + predictions | Phase 1 | JWT (tenant-scoped) |

### AutoDB

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0037 | POST | `/api/v1/enterprise/auto-db/analyze` | AI schema analysis → 3NF/Star suggestions | Phase 1 | JWT (tenant-scoped) |
| API-0038 | POST | `/api/v1/enterprise/auto-db/suggestions/{id}/apply` | Apply suggestion → CREATE TABLE + ERD + form | Phase 1 | JWT (tenant-scoped) |

### Analysis

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0039 | POST | `/api/v1/enterprise/analysis/basic` | Descriptive stats, top-N, segment | Phase 1 | JWT (tenant-scoped) |
| API-0040 | POST | `/api/v1/enterprise/analysis/intermediate` | Correlation, trend, time-series | Phase 2 | JWT (tenant-scoped) |
| API-0041 | POST | `/api/v1/enterprise/analysis/advanced` | Predictive, causal, what-if | Phase 2 | JWT (tenant-scoped) |

### Frameworks

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0042 | POST | `/api/v1/enterprise/frameworks/swot/generate` | AI-fill SWOT from pipeline data | Phase 1 | JWT (tenant-scoped) |
| API-0043 | POST | `/api/v1/enterprise/frameworks/{6w\|2h\|fishbone\|mom-yoy}/generate` | AI-fill framework matrices | Phase 1-2 | JWT (tenant-scoped) |
| API-0044 | POST | `/api/v1/enterprise/frameworks/custom` | Custom framework builder | Phase 2 | JWT (tenant-scoped) |

### Insights

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0045 | POST | `/api/v1/enterprise/insights/generate` | 3-tuyến: Chuyện gì · Tại sao · Nên làm gì | Phase 1 | JWT (tenant-scoped) |
| API-0046 | GET | `/api/v1/enterprise/insights/{id}` | Insight detail with citations + confidence | Phase 1 | JWT (tenant-scoped) |

### Risks

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0047 | POST | `/api/v1/enterprise/risks/auto-detect` | AI scan data → risks with prob×impact | Phase 2 | JWT (tenant-scoped) |
| API-0048 | POST | `/api/v1/enterprise/risks/{id}/escalate` | Escalate risk to owner/manager | Phase 2 | JWT (tenant-scoped) |

### Strategy

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0049 | POST | `/api/v1/enterprise/strategy/okr` | Create OKR/OGSM canvas | Phase 2 | JWT (tenant-scoped) |
| API-0050 | GET | `/api/v1/enterprise/strategy/{id}/timeline` | Gantt roadmap + progress | Phase 2 | JWT (tenant-scoped) |

### Reports

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0051 | POST | `/api/v1/enterprise/reports/auto` | LLM-generated auto report | Phase 1 | JWT (tenant-scoped) |
| API-0052 | POST | `/api/v1/enterprise/reports/builder` | User-created report builder | Phase 2 | JWT (tenant-scoped) |
| API-0053 | POST | `/api/v1/enterprise/reports/{id}/distribute` | Multi-channel: email/slack/webhook | Phase 1-2 | JWT (tenant-scoped) |

### Charts

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0054 | GET | `/api/v1/enterprise/charts/catalog` | 100+ chart types catalog | Phase 1-2 | JWT (tenant-scoped) |
| API-0055 | POST | `/api/v1/enterprise/charts/recommend` | Recommend top-3 chart from data shape | Phase 2 | JWT (tenant-scoped) |

### Decisions

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0056 | GET | `/api/v1/enterprise/decisions` | AI decision log (immutable) | Phase 1 | JWT (tenant-scoped) |
| API-0057 | POST | `/api/v1/enterprise/decisions/{id}/override` | Human override → sent to retrain queue | Phase 1 | JWT (tenant-scoped) |

### Workflow

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0058 | POST | `/api/v1/enterprise/workflows` | Create drag-drop workflow | Phase 2 | JWT (tenant-scoped) |
| API-0059 | POST | `/api/v1/enterprise/workflows/{id}/test` | Test mode on historical data | Phase 2 | JWT (tenant-scoped) |

### Alerts

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0060 | POST | `/api/v1/enterprise/alerts` | Create alert rule (threshold + channel) | Phase 2 | JWT (tenant-scoped) |

### Subscription

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0061 | GET | `/api/v1/enterprise/subscription/quota` | Quota gauge + forecast overage | Phase 1 | JWT (tenant-scoped) |
| API-0062 | POST | `/api/v1/enterprise/subscription/upgrade` | 1-click upgrade plan | Phase 1 | JWT (tenant-scoped) |

### KG

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0063 | GET | `/api/v1/enterprise/knowledge-graph/search` | Semantic search across data assets | Phase 2 | JWT (tenant-scoped) |
| API-0064 | GET | `/api/v1/enterprise/knowledge-graph/lineage` | Upstream/downstream lineage trace | Phase 2 | JWT (tenant-scoped) |

### BlastRadius

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0065 | POST | `/api/v1/enterprise/blast-radius/simulate` | Pre-change impact analysis | Phase 2 | JWT (tenant-scoped) |
| API-0066 | POST | `/api/v1/enterprise/blast-radius/governance/{id}/approve` | Governance queue approval | Phase 2 | JWT (tenant-scoped) |

---

## P3 Studio

### Auth

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0067 | POST | `/api/v1/studio/auth/login` | Kaori staff or Enterprise Analyst login | Phase 1 | JWT (admin) |

### Projects

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0068 | GET | `/api/v1/studio/projects` | List projects filtered by enterprise/status | Phase 1 | JWT (admin) |
| API-0069 | POST | `/api/v1/studio/projects` | Create project, auto-assign lead | Phase 1 | JWT (admin) |

### Models

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0070 | GET | `/api/v1/studio/models` | Model registry with versions, checksums, metrics | Phase 1 | JWT (admin) |
| API-0071 | POST | `/api/v1/studio/models/{id}/promote` | Promote to DEPLOYED (green-blue) | Phase 1 | JWT (admin) |
| API-0072 | POST | `/api/v1/studio/models/{id}/rollback` | Rollback to previous version | Phase 1 | JWT (admin) |

### Training

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0073 | GET | `/api/v1/studio/training-log/{run_id}` | Loss/accuracy per epoch, compare runs | Phase 1 | JWT (admin) |

### Reports

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0074 | POST | `/api/v1/studio/reports/compose` | Rich-text report with chart from Gold | Phase 1 | JWT (admin) |
| API-0075 | POST | `/api/v1/studio/reports/{id}/fan-out` | Deliver to multiple enterprise recipients | Phase 1 | JWT (admin) |

### Prompts

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0076 | POST | `/api/v1/studio/prompts` | Custom prompt template with A/B test | Phase 2 | JWT (admin) |

---

## P4 Personal

### Auth

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0077 | POST | `/api/v1/personal/auth/signup` | Self-signup email/phone/OAuth | Phase 1 | JWT (admin) |
| API-0078 | POST | `/api/v1/personal/auth/verify-otp` | Email/SMS OTP verification | Phase 1 | JWT (admin) |

### Upload

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0079 | POST | `/api/v1/personal/uploads` | Upload HEALTH/FINANCE/PRODUCTIVITY/GENERIC data | Phase 1 | JWT (admin) |

### Pipeline

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0080 | POST | `/api/v1/personal/pipelines` | Personal 5-step wizard (basic only) | Phase 1 | JWT (admin) |

### Goals

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0081 | POST | `/api/v1/personal/goals` | Create goal (max 10 active) | Phase 1 | JWT (admin) |
| API-0082 | GET | `/api/v1/personal/goals/{id}/tracking` | Target vs actual chart + calendar heatmap | Phase 1 | JWT (admin) |

### Suggestions

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0083 | GET | `/api/v1/personal/suggestions` | AI suggestions sorted by relevance | Phase 1 | JWT (admin) |
| API-0084 | POST | `/api/v1/personal/suggestions/{id}/action` | Accept/dismiss/later | Phase 1 | JWT (admin) |

---

## Shared

### Billing

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0085 | POST | `/api/v1/shared/billing/aggregate` | Cron daily unique_customers_billed aggregate | Phase 1 | JWT (admin) |

### Isolation

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0086 | MIDDLEWARE | `(tenant_id inject)` | Extract tenant_id from JWT, inject WHERE enterprise_id= | Phase 1 | JWT (admin) |

### Explainability

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0087 | GET | `/api/v1/shared/explainability/decisions/{id}` | SHAP values + top-3 factors tiếng Việt | Phase 1 | JWT (admin) |

### Audit

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0088 | POST | `/api/v1/shared/audit/events` | Async write immutable audit event | Phase 1 | JWT (admin) |
| API-0089 | GET | `/api/v1/shared/audit/events` | Query with tenant/action/time filters | Phase 1 | JWT (admin) |

### LLM Internal

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0090 | POST | `/api/v1/shared/llm/internal/generate` | Qwen 2.5 generate via vLLM | Phase 1 | JWT (admin) |
| API-0091 | POST | `/api/v1/shared/llm/internal/embeddings` | BGE-M3 Vietnamese embeddings | Phase 1-2 | JWT (admin) |

### LLM External

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0092 | POST | `/api/v1/shared/llm/external/generate` | OpenAI/Claude/Gemini/Azure proxy with masking | Phase 1-2 | JWT (admin) |

### Guardrails

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0093 | POST | `/api/v1/shared/guardrails/validate-input` | PII/jailbreak/profanity/custom input validation | Phase 2 | JWT (admin) |
| API-0094 | POST | `/api/v1/shared/guardrails/validate-output` | Output validation + on-fail action | Phase 2 | JWT (admin) |

### Agents

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0095 | POST | `/api/v1/shared/agents/sessions` | Start MS Agent Framework session | Phase 2 | JWT (admin) |
| API-0096 | POST | `/api/v1/shared/agents/workflows/{id}/invoke` | Invoke pre-built agent workflow | Phase 2 | JWT (admin) |

### Medallion

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0097 | POST | `/api/v1/shared/medallion/silver/refresh` | CDC refresh Silver from Bronze | Phase 1 | JWT (admin) |
| API-0098 | POST | `/api/v1/shared/medallion/gold/materialize` | Rebuild Gold MV | Phase 1 | JWT (admin) |

### Charts

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0099 | POST | `/api/v1/shared/charts/render` | Server-side render to PNG/SVG/PDF | Phase 1 | JWT (admin) |

### ROI Billing

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0100 | GET | `/api/v1/shared/roi-billing/{id}/report` | 1.5% revenue_at_risk actioned, cap 20M | Phase 2 | JWT (admin) |

### MCP

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0101 | POST | `/mcp/jsonrpc` | JSON-RPC 2.0 endpoint (tools/list, tools/call, ...) | Phase 2 | JWT (admin) |
| API-0102 | GET | `/mcp/sse` | Server-Sent Events stream | Phase 2 | JWT (admin) |
| API-0103 | POST | `/mcp/auth/oauth/authorize` | OAuth2 authorization for AI clients | Phase 2 | JWT (admin) |

---

## Billing

### Methods

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0104 | POST | `/api/v1/billing/payment-methods` | Add card/VietQR/Momo/VNPay/ZaloPay | Phase 1 | JWT (admin) |

### Invoices

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0105 | GET | `/api/v1/billing/invoices` | Monthly invoice history | Phase 1 | JWT (admin) |
| API-0106 | POST | `/api/v1/billing/invoices/{id}/e-invoice` | Issue Nghị định 123 e-invoice | Phase 1 | JWT (admin) |

### Subscription

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0107 | POST | `/api/v1/billing/subscription/renew` | Auto-renewal trigger | Phase 1 | JWT (admin) |
| API-0108 | POST | `/api/v1/billing/subscription/cancel` | Cancel with refund calc | Phase 1 | JWT (admin) |

---

## Process Mining

### Sessions

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0109 | POST | `/api/v1/enterprise/process-mining/sessions` | Start new mining session with scope config | Phase 1 | JWT (tenant-scoped) |
| API-0110 | GET | `/api/v1/enterprise/process-mining/sessions/{id}` | Get session status + findings | Phase 1 | JWT (tenant-scoped) |
| API-0111 | POST | `/api/v1/enterprise/process-mining/sessions/{id}/extract-events` | Extract events from configured sources | Phase 1 | JWT (tenant-scoped) |
| API-0112 | POST | `/api/v1/enterprise/process-mining/sessions/{id}/run-algorithm` | Run discovery algorithm (heuristic/inductive/fuzzy) | Phase 1 | JWT (tenant-scoped) |
| API-0113 | GET | `/api/v1/enterprise/process-mining/sessions/{id}/anomalies` | Get detected bottlenecks + shadow processes | Phase 1 | JWT (tenant-scoped) |
| API-0114 | POST | `/api/v1/enterprise/process-mining/sessions/{id}/translate-to-builder` | Generate workflow YAML from mining | Phase 1 | JWT (tenant-scoped) |
| API-0115 | GET | `/api/v1/enterprise/process-mining/sessions/{id}/findings-report` | Download human-readable findings PDF | Phase 1 | JWT (tenant-scoped) |

### Connectors

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0116 | GET | `/api/v1/enterprise/process-mining/connectors` | List available source connectors | Phase 1 | JWT (tenant-scoped) |
| API-0117 | POST | `/api/v1/enterprise/process-mining/connectors/{type}/test` | Test connector before mining | Phase 1 | JWT (tenant-scoped) |

> **⭐ 10 PM connector sources shipped (post-CR-0008 IMPLEMENTING, 2026-05-21):**
> | Source | Phase ship | Endpoint pattern |
> |---|---|---|
> | Postgres CDC | Phase 1 | `POST /process-mining/connectors/postgres-cdc` |
> | Excel upload | Phase 1 | `POST /process-mining/connectors/excel-upload` |
> | Zalo OA | Phase 1.5 | `POST /process-mining/connectors/zalo` |
> | Gmail | P15-S10 D1 | `POST /process-mining/connectors/gmail-outlook` |
> | Outlook | P15-S10 D1 | `POST /process-mining/connectors/gmail-outlook` (shared adapter) |
> | Calendar | P15-S10 D2 | `POST /process-mining/connectors/calendar` |
> | Slack | P2-S13 | `POST /process-mining/connectors/slack-teams` |
> | Microsoft Teams | P2-S13 | `POST /process-mining/connectors/slack-teams` (shared) |
> | SharePoint | P2-S13 | `POST /process-mining/connectors/sharepoint` |
> | Webhook generic | P2-S13 | `POST /process-mining/connectors/webhook` |
> Catalog baseline ("Phase 1 = 4 nguồn") obsolete sau CR-0008. URD US-C1 cập nhật v2.1 reflect 10 sources.

---

## Adoption Intel

### Signals

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0118 | GET | `/api/v1/enterprise/adoption/signals` | List all detected adoption signals | Phase 1 | JWT (tenant-scoped) |
| API-0119 | POST | `/api/v1/enterprise/adoption/signals/configure` | Configure signal thresholds per workflow | Phase 1 | JWT (tenant-scoped) |

### Health

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0120 | GET | `/api/v1/enterprise/adoption/health/{workflow_id}` | Get adoption health score for workflow | Phase 1 | JWT (tenant-scoped) |
| API-0121 | GET | `/api/v1/enterprise/adoption/health/department/{id}` | Department-level adoption rollup | Phase 1 | JWT (tenant-scoped) |
| API-0122 | GET | `/api/v1/enterprise/adoption/health/tenant` | Tenant overall adoption score | Phase 1 | JWT (tenant-scoped) |

### Interventions

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0123 | GET | `/api/v1/enterprise/adoption/interventions` | List active + completed interventions | Phase 1.5 | JWT (tenant-scoped) |
| API-0124 | POST | `/api/v1/enterprise/adoption/interventions/trigger` | Manually trigger intervention | Phase 1.5 | JWT (tenant-scoped) |
| API-0125 | GET | `/api/v1/enterprise/adoption/interventions/effectiveness` | Effectiveness metrics per intervention type | Phase 1.5 | JWT (tenant-scoped) |

### Renewal

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0126 | GET | `/api/v1/platform/adoption/renewal-risk/{tenant_id}` | Renewal risk score (CSM tool) | Phase 1.5 | JWT (admin) |

---

## Economics

### Revenue

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0127 | POST | `/api/v1/enterprise/economics/revenue/estimate` | Estimate revenue impact of workflow | Phase 1 | JWT (tenant-scoped) |

### Cost

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0128 | POST | `/api/v1/enterprise/economics/cost/compute` | Compute total workflow cost | Phase 1 | JWT (tenant-scoped) |

### NOV

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0129 | GET | `/api/v1/enterprise/economics/nov/{workflow_id}/monthly` | Monthly NOV per workflow | Phase 1 | JWT (tenant-scoped) |
| API-0130 | GET | `/api/v1/enterprise/economics/nov/tenant/total` | Tenant total NOV across workflows | Phase 1 | JWT (tenant-scoped) |
| API-0131 | GET | `/api/v1/enterprise/economics/nov/{workflow_id}/payback` | Time-to-payback projection | Phase 1 | JWT (tenant-scoped) |

### Reports

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0132 | GET | `/api/v1/enterprise/economics/reports/manager-digest` | Monthly manager email digest data | Phase 1 | JWT (tenant-scoped) |

### Dashboards

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0133 | GET | `/api/v1/enterprise/economics/dashboards/roi` | ROI dashboard data | Phase 1 | JWT (tenant-scoped) |

### Simulation

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0134 | POST | `/api/v1/enterprise/economics/simulate` | What-if simulation of NOV | Phase 2 | JWT (tenant-scoped) |

---

## Workflow

### Engine

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0135 | POST | `/api/v1/enterprise/workflows` | Create workflow (DRAFT state) | Phase 1 | JWT (tenant-scoped) |
| API-0136 | PUT | `/api/v1/enterprise/workflows/{id}` | Update workflow (creates version) | Phase 1 | JWT (tenant-scoped) |
| API-0137 | POST | `/api/v1/enterprise/workflows/{id}/promote-to-testing` | State transition: DRAFT → TESTING | Phase 1.5 | JWT (tenant-scoped) |
| API-0138 | POST | `/api/v1/enterprise/workflows/{id}/promote-to-active` | State transition: TESTING → ACTIVE_BASELINE | Phase 1.5 | JWT (tenant-scoped) |
| API-0139 | POST | `/api/v1/enterprise/workflows/{id}/rollback` | Rollback to previous version | Phase 1 | JWT (tenant-scoped) |
| API-0140 | POST | `/api/v1/enterprise/workflows/{id}/execute` | Trigger workflow execution | Phase 1 | JWT (tenant-scoped) |
| API-0141 | GET | `/api/v1/enterprise/workflows/{id}/runs` | List workflow runs | Phase 1 | JWT (tenant-scoped) |
| API-0142 | GET | `/api/v1/enterprise/workflows/{id}/runs/{run_id}/trace` | Get distributed trace for run | Phase 1 | JWT (tenant-scoped) |
| API-0143 | POST | `/api/v1/enterprise/workflows/validate` | Validate workflow before save | Phase 1 | JWT (tenant-scoped) |

### Templates

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0144 | GET | `/api/v1/enterprise/templates` | List workflow templates | Phase 1 | JWT (tenant-scoped) |
| API-0145 | POST | `/api/v1/enterprise/templates/{id}/instantiate` | Create workflow from template | Phase 1 | JWT (tenant-scoped) |

### YAML

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0146 | POST | `/api/v1/enterprise/workflows/import-yaml` | Import workflow as YAML (Workflow as Code) | Phase 2 | JWT (tenant-scoped) |
| API-0147 | GET | `/api/v1/enterprise/workflows/{id}/export-yaml` | Export workflow to YAML | Phase 2 | JWT (tenant-scoped) |

---

## Reasoning

### Insights

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0148 | POST | `/api/v1/enterprise/reasoning/insights/generate` | Generate insight (with LLM version pinning) | Phase 1 | JWT (tenant-scoped) |

### Recommendations

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0149 | POST | `/api/v1/enterprise/reasoning/recommendations/generate` | Generate action recommendations | Phase 1 | JWT (tenant-scoped) |

### Constraints

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0150 | POST | `/api/v1/enterprise/reasoning/constraints/validate` | Validate proposed action against constraints | Phase 1 | JWT (tenant-scoped) |

### Formulas

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0151 | GET | `/api/v1/enterprise/reasoning/formulas` | List available formulas (LTV, CAC, etc.) | Phase 1 | JWT (tenant-scoped) |

### Criteria

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0152 | GET | `/api/v1/enterprise/reasoning/criteria` | List active criteria | Phase 1 | JWT (tenant-scoped) |

### RAG

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0153 | POST | `/api/v1/enterprise/reasoning/rag/query` | RAG query with citation tracking | Phase 1 | JWT (tenant-scoped) |

---

## Platform LLM

### Versions

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0154 | POST | `/api/v1/platform/llm/versions/pin` | Pin LLM version to workflow | Phase 1 | JWT (admin) |
| API-0155 | GET | `/api/v1/platform/llm/versions/drift-report` | Drift detection across LLM versions | Phase 1.5 | JWT (admin) |
| API-0156 | POST | `/api/v1/platform/llm/versions/upgrade-test` | Initiate 90-day controlled LLM upgrade | Phase 2 | JWT (admin) |

---

## Platform DLQ

### DLQ

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0157 | GET | `/api/v1/platform/dlq` | List dead letter queue messages | Phase 1 | JWT (admin) |
| API-0158 | POST | `/api/v1/platform/dlq/{id}/reprocess` | Reprocess DLQ message | Phase 1 | JWT (admin) |
| API-0159 | POST | `/api/v1/platform/dlq/{id}/discard` | Discard DLQ message after review | Phase 1 | JWT (admin) |

---

## Platform Health

### Metrics

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0160 | GET | `/api/v1/platform/health/metrics` | Custom Prometheus metrics endpoint | Phase 1 | JWT (admin) |

### Traces

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0161 | GET | `/api/v1/platform/health/traces/{run_id}` | Get trace by run_id | Phase 1 | JWT (admin) |

---

## Platform Security

### Audit

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0162 | GET | `/api/v1/platform/security/cross-tenant-attempts` | Cross-tenant access attempts (must be 0) | Phase 1 | JWT (admin) |
| API-0163 | POST | `/api/v1/platform/security/run-leak-tests` | Run RLS leak tests (CI integration) | Phase 1 | JWT (admin) |

---

## Platform CSM

### Health

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0164 | GET | `/api/v1/platform/customer-success/{tenant_id}/health` | Customer health overview for CSM | Phase 1 | JWT (admin) |

### Portfolio

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0165 | GET | `/api/v1/platform/customer-success/portfolio` | CSM portfolio view | Phase 1 | JWT (admin) |

### Triggers

| ID | Method | Endpoint | Purpose | Phase | Auth |
|---|---|---|---|---|---|
| API-0166 | GET | `/api/v1/platform/customer-success/engagement-triggers` | 7 proactive engagement triggers | Phase 1.5 | JWT (admin) |

---

## API Dependency Graph

| Edge | Source (caller) | Target (callee) | Type | Trigger |
|---|---|---|---|---|
| EDGE-001 | `POST /platform/auth/login` | `POST /platform/auth/mfa/verify` | sync | mfa_required=true |
| EDGE-002 | `POST /platform/auth/login` | `GET /platform/admins/profile` | sync | always after login |
| EDGE-003 | `POST /platform/workspaces` | `POST /platform/keys` | sync | always on workspace create |
| EDGE-004 | `POST /platform/workspaces` | `POST /enterprise/notification/email` | async | always |
| EDGE-005 | `POST /enterprise/pipelines/upload` | `POST /enterprise/data/bronze/ingest` | sync | on success upload |
| EDGE-006 | `POST /enterprise/data/bronze/ingest` | `POST /enterprise/data/silver/promote` | async | event: pipeline.bronze.complete |
| EDGE-007 | `POST /enterprise/data/silver/promote` | `POST /enterprise/data/gold/aggregate` | async | event: pipeline.silver.complete |
| EDGE-008 | `POST /enterprise/pipelines/analyze` | `POST /enterprise/reasoning/insights/generate` | sync | user clicks Analyze |
| EDGE-009 | `POST /enterprise/reasoning/insights/generate` | `POST /enterprise/reasoning/rag/query` | sync | always |
| EDGE-010 | `POST /enterprise/reasoning/insights/generate` | `POST /platform/llm/versions/check` | sync | always before LLM call |
| EDGE-011 | `POST /enterprise/reasoning/recommendations/generat` | `POST /enterprise/reasoning/constraints/validate` | sync | always |
| EDGE-012 | `POST /enterprise/workflows/{id}/execute` | `POST /enterprise/reasoning/insights/generate` | sync | when AI node in workflow |
| EDGE-013 | `POST /enterprise/workflows/{id}/execute` | `POST /enterprise/integrations/{provider}/send` | sync/async | when external node in workflow |
| EDGE-014 | `POST /enterprise/workflows/{id}/execute` | `POST /enterprise/notification/dispatch` | async | when notification node |
| EDGE-015 | `POST /enterprise/process-mining/sessions` | `POST /enterprise/process-mining/connectors/{type}/` | async | always on session start |
| EDGE-016 | `POST /enterprise/process-mining/sessions/{id}/run-` | `POST /enterprise/process-mining/sessions/{id}/extr` | sync | always before algo runs |
| EDGE-017 | `POST /enterprise/process-mining/sessions/{id}/tran` | `POST /enterprise/workflows` | sync | on user approval of findings |
| EDGE-018 | `POST /enterprise/workflows/{id}/execute` | `POST /enterprise/adoption/signals/extract` | async | every workflow run |
| EDGE-019 | `GET /enterprise/adoption/signals` | `GET /enterprise/adoption/health/{workflow_id}` | sync | on health request |
| EDGE-020 | `GET /enterprise/adoption/health/{workflow_id}` | `POST /enterprise/adoption/interventions/trigger` | sync | health <40 |
| EDGE-021 | `POST /enterprise/economics/nov/compute` | `POST /enterprise/economics/revenue/estimate` | sync | monthly cron |
| EDGE-022 | `POST /enterprise/economics/nov/compute` | `POST /enterprise/economics/cost/compute` | sync | monthly cron |
| EDGE-023 | `GET /enterprise/economics/dashboards/roi` | `GET /enterprise/economics/nov/tenant/total` | sync | on dashboard load |
| EDGE-024 | `POST /enterprise/workflows/{id}/promote-to-testing` | `POST /enterprise/workflows/{id}/setup-90day-test` | sync | always on transition |
| EDGE-025 | `POST /enterprise/workflows/{id}/promote-to-active` | `POST /enterprise/adoption/baseline/capture` | sync | always on activation |
| EDGE-026 | `POST /platform/llm/versions/upgrade-test` | `POST /enterprise/workflows/{id}/promote-to-testing` | sync | on new LLM version available |
| EDGE-027 | `All /enterprise/** APIs` | `GET /platform/security/check-tenant-context` | sync | every authenticated request |
| EDGE-028 | `All write APIs` | `POST /platform/audit/log` | async | every write operation |
| EDGE-029 | `GET /platform/customer-success/{tenant_id}/health` | `GET /enterprise/adoption/health/tenant` | sync | on CSM dashboard load |
| EDGE-030 | `GET /platform/customer-success/{tenant_id}/health` | `GET /enterprise/economics/nov/tenant/total` | sync | on CSM dashboard load |
| EDGE-031 | `GET /platform/customer-success/engagement-triggers` | `GET /platform/customer-success/portfolio` | sync | cron daily |
| EDGE-032 | `All workflow execution APIs` | `POST /platform/dlq/enqueue` | async | after max retries |
| EDGE-033 | `POST /platform/dlq/{id}/reprocess` | `POST /enterprise/workflows/{id}/execute` | sync | on admin reprocess |
| EDGE-034 | `All APIs` | `POST /platform/health/metrics/emit` | async | every API call |
| EDGE-035 | `All APIs` | `POST /platform/health/traces/emit` | async | every API call |
| EDGE-036 | `GET /platform/adoption/renewal-risk/{tenant_id}` | `GET /enterprise/adoption/health/tenant` | sync | on CSM check |
| EDGE-037 | `GET /platform/adoption/renewal-risk/{tenant_id}` | `GET /enterprise/economics/nov/tenant/total` | sync | on CSM check |
| EDGE-038 | `All /enterprise/** APIs` | `GET /platform/billing/tier-check` | sync | every API call |
| EDGE-039 | `All authenticated APIs` | `POST /platform/authz/pdp/decide` | sync | every authenticated request |

---

## Appendix A — Session-shipped endpoints not in original Feature Tree v4.0 catalog

> Added 2026-05-17. The 169-endpoint master catalog above came from `Kaori_AI_Feature_Tree_v4_0.xlsx`. During Phase 2 sprint marathon 2026-05-17 (P2-S15/S16/S18/S21/S25), em ship 30+ endpoints that don't have a row in the original spec. Listed here so the catalog stays a single point of truth.

### P2-S15 workflow node catalog + agent palette (mig 068, ship `d0e959f`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/workflow-node-types` | GET | List 45-row mig 068 catalog with category filter |
| `/shared/agents/studio/builder/palette` | GET | SH-M56b-026: curated 28-node agent palette grouped by bucket |
| `/workflow-templates?industry=` | GET | Extension — industry_vertical filter (P2-S15) |

### P2-S16 Workflow as Code + Multi-user collab (mig 072, ship `e438482`/`ff8fd22`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/workflows/import` | POST | YAML import → validates mig 068 catalog → creates workflow |
| `/workflows/{workflow_id}/export.yaml` | GET | YAML export (round-trip) |
| `/workflows/{workflow_id}/editors` | POST/GET | Multi-user assign + list |
| `/workflows/{workflow_id}/editors/{user_id}` | PATCH/DELETE | Role update + remove |
| `/workflows/{workflow_id}/comments` | POST/GET | Threaded comments (workflow or node anchored) |
| `/workflows/{workflow_id}/comments/{comment_id}` | PATCH | Edit body / resolve |
| `/workflows/{workflow_id}/lock` | POST/GET/DELETE | Optimistic edit lock (K-13 anti-IDOR token) |

### P2-S18 Observability deep-dive (mig 073, ship `1886ca8`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/platform/observability/metric-anomalies` | GET | OBS-018 z-score + EWMA on api/etl metrics |
| `/platform/observability/capacity` | GET | OBS-021 linear regression capacity forecast |
| `/platform/observability/sessions/consent` | POST/GET | OBS-023 per-user opt-in consent |
| `/platform/observability/sessions/{session_id}/record` | POST | Submit recording (K-5 PII re-redacted) |
| `/platform/observability/sessions/{session_id}/replay` | GET | Fetch redacted event stream |

### P2-S21 OKR + NOV recommendations + simulation (mig 071, ship `24cf91e`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/p2/strategy/okr` | POST/GET | P2-M212-001: create + list OKRs |
| `/p2/strategy/okr/{okr_id}` | GET/PATCH/DELETE | OKR detail with KRs + workflows; update meta |
| `/p2/strategy/okr/{okr_id}/key-results` | POST | Add KR (triggers progress recalc) |
| `/p2/strategy/okr/{okr_id}/key-results/{kr_id}` | PATCH/DELETE | Update / remove KR |
| `/p2/strategy/okr/{okr_id}/link-workflow` | POST | Link workflow with contribution_weight |
| `/p2/strategy/okr/{okr_id}/link-workflow/{workflow_id}` | DELETE | Unlink |
| `/economics/reports/manager-digest/recommendations` | GET | NOV-RPT-023 top-K underperforming workflows + replacement templates |
| `/economics/reports/manager-digest/simulate` | POST | NOV-RPT-024 what-if scenario simulation |

### P2-S25 MFA + field encryption (mig 074, ship `b46bdca`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/p2/auth/mfa/enroll` | POST | P2-AUTH-002: TOTP secret + 10 backup codes (one-time view) |
| `/p2/auth/mfa/verify` | POST | Verify 6-digit TOTP or 10-char backup code (±30s drift) |
| `/p2/auth/mfa/status` | GET | Enrollment + last verified + backup count |
| `/p2/auth/mfa` | DELETE | Disable MFA |
| `/p2/auth/field-key/status` | GET | P2-ENC-001: current key version + ref_kind |
| `/p2/auth/field-key/rotate` | POST | Bump key version (Vault prod / inline dev) |

**OpenAPI total at session close:** 115 paths (was 89 at session start). Drift artefacts regenerated each commit; `docs/api-specs/orchestrator.openapi.json` is the authoritative wire spec.

**Live total 2026-05-21 (Round 5 N2 regen):** pipeline 24 paths · orchestrator **163 paths** · auth-service ~10 paths ≈ **~187 total**.

---

## Cross-cutting policies (Round 5 N2 additions)

### SLA per-endpoint (NFRS §2 Performance)

Targets baseline (Phase 1 → Phase 3):

| NFR | Endpoint class | Phase 1 P99 | Phase 3 P99 |
|---|---|---|---|
| NFR-P-01 | API read (GET) | <200ms | <100ms |
| NFR-P-02 | API write (POST/PATCH/DELETE) | <500ms | <250ms |
| NFR-P-03 | Feature Store online | <20ms | <10ms |
| NFR-P-04 | Insight 3-tuyến gen (LLM) | <15s | <10s |
| NFR-P-05 | Qwen 14B 512 tok | <5s | <3s |
| NFR-P-06 | Pipeline 5-step (10k rows) | <5 phút | <2 phút |
| NFR-P-09 | Process Mining (50k events) | <10 phút | <3 phút |
| NFR-P-10 | NOV monthly compute / tenant | <2 phút | <30s |
| NFR-P-11 | Org Hierarchy tree load (≤5 cấp, ≤500 nodes) | <1s | <500ms |
| NFR-P-12 | Document OCR tiếng Việt (1 trang A4) | <8s | <4s |

> **Per-endpoint SLA column:** add tới từng row của catalog là follow-up dài (chuyển effort vào schema_history extension or `docs/specs/SLA_MATRIX.md`). Hiện tại class-level SLA áp dụng theo HTTP method/resource type. Endpoint specific SLA chỉ deviate khi feature override (e.g. NFR-P-04 cho LLM, NFR-P-09 cho PM mining).

### Rate Limit per-endpoint (mig 099 tenant_quotas)

Per-tenant per-resource quota system shipped Phase 2.7. 5 default quota types seeded per enterprise:

| Quota type | Period | Default cap | Applies to endpoints |
|---|---|---|---|
| `llm_tokens_external` | per_day | 1,000,000 tokens | All `POST /v1/infer` external |
| `llm_tokens_local` | per_day | 10,000,000 tokens | All `POST /v1/infer` Qwen + `/v1/embed` |
| `workflow_concurrent` | rolling | 20 concurrent runs | `POST /workflows/{id}/run` |
| `api_calls` | per_minute | 1000 req/min | Catch-all on all `/api/v1/*` |
| `export_files` | per_day | 100 exports | `POST /reports/{id}/export` |

429 response with `Retry-After` header per NFR-SEC-09. Override per plan in PRD §11 (BASIC/MID/MAX/ROI multipliers).

### Error Codes (RFC 7807 Problem Details)

All 4xx/5xx responses follow RFC 7807. Full catalog: `docs/specs/MESSAGE_DEFINITIONS.md` (SYS-ERR-* + USR-ERR-*).

Common error class mappings:

| HTTP | Code prefix | Trigger | Recovery |
|---|---|---|---|
| 400 | USR-ERR-400-* | Validation fail (Pydantic / zod) | Inline field error VN |
| 401 | USR-ERR-401-* | JWT expired/invalid | Redirect `/login?return=` |
| 403 | USR-ERR-403-ROLE | Role insufficient | "Permission denied — liên hệ admin" |
| 403 | USR-ERR-403-CLAIM | Claim missing (NFRS §5.bis) | "Tính năng X cần quyền Y" |
| 409 | USR-ERR-409-* | Resource conflict (dup, already-bootstrapped) | Modal "Conflict — recover" |
| 422 | USR-ERR-422-* | Semantic validation (issues[]) | Per-field inline |
| 429 | SYS-ERR-429-QUOTA | Tenant quota exceeded | Show plan + upgrade CTA |
| 500 | SYS-ERR-500-* | Unhandled exception | Sentry capture + OTel span error |
| 502 | SYS-ERR-502-LLM | LLM gateway fail/repair fail | Fallback Qwen / Retry |
| 503 | SYS-ERR-503-* | Dependency down | `Retry-After` + degrade |

### API Versioning Policy

Current:
- `/api/v1/*` — legacy Phase 1 endpoints (still primary in 2026-05)
- `/api/v1/{portal}/*` — Phase 1 v4 new pattern (P1/P2/P3/P4/shared/billing)
- `/api/v2/{portal}/*` — target Phase 2+ (microservices extraction defer Phase 3 per ADR-0010)

Deprecation policy:
- **Major version change**: 6-month deprecation window. v1 endpoints kept alive với `Deprecation: true` header + `Sunset: <date>` header pointing to retirement.
- **Breaking change in same major**: KHÔNG cho phép. Use feature flag hoặc new endpoint.
- **Additive change** (new field, new enum value): allowed any time.
- **Field rename**: KHÔNG. Add new field + deprecate old (6 months).
- **Endpoint move**: redirect 301 từ old → new during deprecation.

Test invariant: drift between API_CATALOG_V4.md ↔ live OpenAPI snapshot CI-checked qua `scripts/dump_openapi.py --check`.

### Outbound Webhooks Contract (Phase 2 EPIC notification)

For tenant integrations consuming Kaori events (alerts, NOV digest, workflow run completion):

**Request shape:**
```json
{
  "event_id": "uuid",
  "event_type": "workflow_run.completed" | "alert.fired" | "nov.monthly_digest",
  "tenant_id": "...",
  "timestamp": "2026-05-21T07:53:47Z",
  "payload": { ... event-specific ... },
  "signature": "hmac-sha256:..."
}
```

**Headers:**
- `X-Kaori-Event-Type: workflow_run.completed`
- `X-Kaori-Signature: sha256=<hmac>` (HMAC-SHA256 with tenant webhook_secret)
- `X-Kaori-Delivery-Id: <uuid>` (for idempotency on consumer side)
- `Content-Type: application/json`
- `User-Agent: Kaori-Webhook/1.0`

**Retry policy:** 5 retries exponential backoff (1s, 2s, 4s, 8s, 16s) on 5xx or timeout. After 5 fails → DLQ + alert tenant integration owner. 4xx → no retry (consumer must fix).

**Signature verification (consumer side):**
```python
import hmac, hashlib
expected = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, header_signature.split("=")[1]):
    raise UnauthorizedSignature
```

**Event catalog (Phase 2+):**

| Event type | Trigger | Phase |
|---|---|---|
| `workflow_run.started` | Run begins | Phase 2 |
| `workflow_run.completed` | Run reaches terminal state | Phase 2 |
| `workflow_run.failed` | Run fails (links DLQ entry) | Phase 2 |
| `alert.fired` | publish_alert executor side effect | Phase 2 |
| `insight.created` | publish_insight executor side effect | Phase 2 |
| `nov.monthly_digest` | NOV cron monthly | Phase 2 |
| `adoption.health_drop` | Health < 40 threshold | Phase 1.5 |
| `quota.exceeded` | Tenant 429 hit (consumer alerting) | Phase 2.7 |

Per-tenant webhook config endpoint TBD (defer to Phase 3 with self-service UI). Phase 1-2: webhook URL + secret configured per tenant manually qua Platform Admin P1.
