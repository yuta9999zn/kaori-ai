# Kaori AI — Frontend Tasks (per Target Group + Phase)

> **Version:** 2.0 · **Generated:** 2026-04-25 · **Restructured by 4 target groups**
> **Sources:**
> - `docs/product/Feature_Tree_Kaori_AI_v3.1.xlsx` — Screen sheets, Leaves Detail (rich per-feature spec), API Catalog (108 endpoints), Phase 1 Reality Check, Cross-Screen Journeys
> - `docs/product/Kaori_AI_BRD_v3.0.docx` — Phase plan (M1-M4 / M5-M12 / M13-M24)
> - `docs/product/Kaori_AI_PRD_v5.0.docx` — Service topology
> - `docs/product/TAI_LIEU_YEU_CAU_SAN_PHAM_v5.0.docx` — Module-level phase tags
> - `docs/BACKLOG.md` — Backend feature backlog (F-001..F-092 + v3.1 reconciliation)
>
> **Convention:** Frontend task IDs follow `FE-{GROUP}-{NNN}` where group ∈ {PT, EU, ST, PE, SH, BL}. Phase per task = phase of the consuming screen.

---

## Table of Contents

- [0. Reconciliation & Foundation](#0-reconciliation--foundation)
  - [0.1 API gaps to address in BACKLOG](#01-api-gaps-to-address-in-backlog)
  - [0.2 Phase plan recap](#02-phase-plan-recap)
  - [0.3 Target groups overview](#03-target-groups-overview)
- [1. Platform Tenant (P1) — Kaori internal staff](#1-platform-tenant-p1--kaori-internal-staff)
- [2. Enterprise User (P2) — Customer organization](#2-enterprise-user-p2--customer-organization)
- [3. Studio (P3) — Kaori Analyst + Enterprise Analyst](#3-studio-p3--kaori-analyst--enterprise-analyst)
- [4. Personal (P4) — Freelancer / individual](#4-personal-p4--freelancer--individual)
- [5. Cross-cutting Shared & Billing](#5-cross-cutting-shared--billing)
- [6. Cross-screen journeys (E2E flows)](#6-cross-screen-journeys-e2e-flows)
- [7. Phase progress summary by group](#7-phase-progress-summary-by-group)

---

## 0. Reconciliation & Foundation

### 0.1 API gaps to address in BACKLOG

The v3.1 `API Catalog` (108 endpoints) was cross-checked with `BACKLOG.md`. Concrete diffs already applied to `BACKLOG.md` § "v3.1 Reconciliation":

| F-ID | Change | Reason |
|------|--------|--------|
| **F-NEW3** Data Explorer | NEW (Phase 1) | P2 screen 2.5 needs `GET /enterprise/data/{layer}/tables` + `/lineage` — not in any existing F |
| F-007 | Add `POST /platform/auth/mfa/verify` | MFA Challenge screen needs explicit verify endpoint |
| F-011 | Add `GET /platform/billing/alerts` | Quota & Alerts screen needs alert list endpoint |
| F-025 | Add `GET /enterprise/insights/{id}` | Insight Detail screen requires id-level fetch |
| F-027 | Add `GET /enterprise/charts/catalog` | Chart Picker screen needs catalog source |
| F-087 Branding | Phase 3 → Phase 2 | Screen 2.1 tagged Phase 2 in v3.1 |
| F-082 Invoice / F-083 Payment | Split: payment list/methods → Phase 2; e-invoice Nghị định 123 stays Phase 3 | Screens 6.1/6.3 are Phase 2 |
| F-078 Audit | Backend write/read API → Phase 1; Query UI → Phase 2 | Audit writer is foundational |

**Phase tags reaffirmed (v3.1 API Catalog mis-tags overruled by screen-sheet authority):**
F-034 (Frameworks), F-036 (Decision Override), F-038 (Reports), F-057 (Auto-DB), F-042..F-048 (P3), F-049..F-055 (P4) — **all stay Phase 2** despite v3.1 API Catalog tagging some as Phase 1.

### 0.2 Phase plan recap

| Phase | Months | Theme | MRR target | Customer count |
|-------|--------|-------|------------|----------------|
| **Phase 1** | M1-M4 (T1-T4) | MVP Retail · core platform | 10-40M VND | 5 paying pilots |
| **Phase 2** | M5-M12 (T5-T12) | Scale + Intelligence | ≥100M VND | 25 customers |
| **Phase 3** | M13-M24 (T13-T24) | Enterprise + Compliance + SEA | ≥500M VND | 100 customers |

### 0.3 Target groups overview

| Group | Code | Portal | Personas / roles | Phase activation | Total screens | Phase 1 screens | Honest impl % |
|-------|------|--------|------------------|------------------|---------------|-----------------|---------------|
| **Platform Tenant** | PT | P1 (`/p1`, `/platform`) | Kaori SUPER_ADMIN (MFA mandatory), ADMIN, SUPPORT | Phase 1 (foundational) | 34 | 21 | 9% (3 ✅, 9 🔄, 4 ❌, 18 ⬜) |
| **Enterprise User** | EU | P2 (`/p2`) | MANAGER (≥1 required/enterprise), OPERATOR, ANALYST, VIEWER | Phase 1 (core), 2 (intelligence), 3 (compliance) | 96 | 25 | 12% (12 ✅, 3 🔄, 3 ❌, 78 ⬜) |
| **Studio** | ST | P3 (`/p3`) | STUDIO_ADMIN (Kaori staff, MFA), STUDIO_ANALYST (scoped per enterprise) | Phase 2 only | 20 | 0 | 0% (0/20) |
| **Personal** | PE | P4 (`/p4`) | PERSONAL_USER (self only) | Phase 2 only | 17 | 0 | 0% (0/17) |
| Shared/Billing | SH/BL | `/shared`, `/billing`, `/mcp` | All groups (cross-cutting) | Phase 1-3 | 49 | 12 | 8% (4 ✅, 4 🔄, 2 ❌, 39 ⬜) |
| **Total** | | | | | **216** | **58** | **9%** |

> "Honest impl %" comes from `Screen Status Summary` sheet; "Ghost" = feature claimed ✅ in tracker but no code.

---

## 1. Platform Tenant (P1) — Kaori internal staff

> **Audience:** Kaori platform operators (SUPER_ADMIN/ADMIN/SUPPORT). Manages tenants, billing, infra health, LLM providers, plans. **All screens require P1 portal auth + RBAC; SUPER_ADMIN actions need MFA.**
>
> **Module count:** 9 · **Screens:** 34 · **Leaves:** 82 · **Phase 1 active modules:** 1.0, 1.1, 1.2, 1.3, 1.4, 1.6, partial 1.8

### 1.1 Module 1.0 — Authentication (`/p1/auth`)

> 4 screens. Login, MFA, Password Recovery, Sessions. Phase 1 except Sessions (Phase 2).

#### Screen 1.0/1 — Login `/p1/auth/login` · **Phase 1 · ✅ Impl**

- **Goal:** Authenticate Kaori admin via email + password, issue short-lived access + refresh cookie.
- **UI components:** `TextField` × 2, `Checkbox` "Trusted device", `Button` primary, `Toast` error, `EnvironmentBanner`.
- **Validation:** Client = email RFC 5322 + non-empty password; server = bcrypt match + status=ACTIVE + IP whitelist (if set).
- **APIs:** `POST /api/v1/platform/auth/login` → `{access_token, refresh_token, mfa_required, mfa_challenge_id?, profile}`.
- **States:** Loading (spinner) · Error generic (no field disclosure) · Error locked (modal + countdown) · Error IP-denied · Success (redirect MFA or `/platform`).
- **Edge cases:** 3 wrong → invisible reCAPTCHA v3; 5 wrong → 15-min lock + email SUPER_ADMIN; concurrent session → confirm "kick old device".
- **Tasks:** _shipped — no FE work_.

#### Screen 1.0/2 — MFA Challenge `/p1/auth/mfa` · **Phase 1 · 🔄 Partial**

- **Goal:** Second-factor verification for high-risk SUPER_ADMIN actions; step-up for destructive actions (force logout, reset MFA, change plan price).
- **UI components:** `OTPInput` (6 boxes auto-advance), `Toggle` "Use backup code", `Button`, `CountdownRing` 30s TOTP period.
- **Validation:** TOTP within ±1 period skew; backup code unused (12-char from `admin_mfa_backup_codes`).
- **APIs:** `POST /api/v1/platform/auth/mfa/verify` `{challenge_id, code}` → `{access_token, refresh_token}`.
- **States:** Loading · Error wrong code (shake animation, "còn N lần thử") · Error expired (modal + redirect login 3s) · Success (checkmark animate → intended URL).
- **Edge cases:** TOTP replay → reject + audit `MFA_REPLAY_ATTEMPTED`; backup code consumption → mark used + warn if remaining < 3.
- **Tasks:**
  - **FE-PT-001** Build OTPInput component (6 cells, auto-advance, paste support) + MFA verification flow with countdown ring.
  - **FE-PT-002** Backup-code toggle + textarea entry; show "remaining codes" warning when ≤ 3.
  - **FE-PT-003** Wire to backend `POST /platform/auth/mfa/verify` (currently missing — block until F-007 amendment lands).

#### Screen 1.0/3 — Password Recovery `/p1/auth/forgot-password` · **Phase 1 · ✅ Impl**

- Tasks: _shipped (forgot + reset + change-password sub-features all done in F-003)_.

#### Screen 1.0/4 — Session & Security Settings `/p1/auth/sessions` · **Phase 2 · ⬜ Pending**

- **Goal:** Show list of active sessions, allow revoke per session.
- **UI components:** `DataTable` (Device · Browser · IP · Region · Login time · Status · Action) · "Current session" badge non-revokable · Bulk "End all other sessions" requires re-auth password.
- **APIs:** `GET /api/v1/platform/auth/sessions` · `DELETE /api/v1/platform/auth/sessions/:id`.
- **Tasks:**
  - **FE-PT-004** Sessions table with device fingerprint icons + region geo-lookup labels.
  - **FE-PT-005** Bulk "end other sessions" modal with re-auth password gate.

### 1.2 Module 1.1 — Workspace Management (`/platform/workspaces`)

> 4 screens. CRUD enterprise workspaces · plan/status filter · CSV export. **All Phase 1 · F-008 ✅ closed 2026-04-25 (workspace list page).**

#### Screen 1.1/1 — Workspace List `/platform/workspaces` · **Phase 1 · ✅ Impl**

- _Shipped — F-008. Cursor pagination, snake_case fields, status enum aligned to backend._

#### Screen 1.1/2 — Workspace Detail (Overview) `/platform/workspaces/:id` · **Phase 1 · 🔄 Partial**

- **Goal:** Single workspace overview: company info, current plan, usage gauge, member roster, billing snapshot.
- **UI components:** `Header` (name + plan badge + status pill) · 4 KPI cards (active users, pipelines, decisions, MRR) · `Tabs` (Overview · Members · Billing · Audit) · `Timeline` recent actions.
- **APIs:** `GET /api/v1/platform/workspaces/{id}` → workspace + usage + billing + members.
- **States:** Loading skeleton · Empty (just-created workspace, no data) · Suspended banner red · Archived banner gray with "Restore" CTA.
- **Edge cases:** Workspace created < 24h → show "Setting up..." state until first ingestion; plan downgrade pending → show banner "Hạ gói có hiệu lực từ {date}".
- **Tasks:**
  - **FE-PT-006** Detail header + KPI cards layout.
  - **FE-PT-007** Tabs container with lazy-loaded Members/Billing/Audit panes.
  - **FE-PT-008** Timeline component fed from audit API (filter by tenant_id).

#### Screen 1.1/3 — Create Wizard `/platform/workspaces/new` · **Phase 1 · 🔄 Partial**

- **Goal:** 3-step wizard creating tenant + first MANAGER user + private key.
- **UI components:** `Stepper` (1. Company → 2. Plan → 3. Key issued) · forms with inline validation · final step shows generated `KAORI-XXXX` key with copy-once + acknowledge gate.
- **Validation:** Company name unique within Kaori system; tax ID format VN (10/13 digits); plan choice from active plans only.
- **APIs:** `POST /api/v1/platform/workspaces` → returns `{workspace_id, key_raw}` (raw key shown ONCE, store SHA-256).
- **Edge cases:** Network failure on step 3 → key may have been issued — call `GET /platform/keys?workspace_id` to recover; cancel after step 3 → workspace exists but no key issued, prompt to issue key.
- **Tasks:**
  - **FE-PT-009** Stepper component with state persistence (localStorage scoped to admin session).
  - **FE-PT-010** Reveal-once key modal with `navigator.clipboard.writeText` + acknowledge-checkbox gate.
  - **FE-PT-011** Recovery flow when network fails after key issue.

#### Screen 1.1/4 — Edit & Lifecycle Actions `/platform/workspaces/:id/edit` · **Phase 1 · 🔄 Partial**

- **Goal:** Edit workspace metadata + lifecycle (activate/suspend/archive).
- **UI components:** Form (name, contact, billing email) · Action buttons with destructive variants · Confirm modal showing data impact ("X active users, Y pipelines will be paused").
- **APIs:** `PATCH /api/v1/platform/workspaces/{id}` with action enum.
- **Edge cases:** Suspend with pending billing > 0 → require force flag + audit reason; archive with active analyses → wait for completion or kill.
- **Tasks:**
  - **FE-PT-012** Edit form with optimistic updates + rollback on error.
  - **FE-PT-013** Lifecycle action buttons + confirmation modals with impact preview.

### 1.3 Module 1.2 — Private Key Management (`/platform/keys`)

> 3 screens. Generate + revoke onboarding `KAORI-XXXX` keys. **All Phase 1 · backend exists but F-009 unreachable due to SecurityConfig blanket-deny.**

#### Screen 1.2/1 — Keys List `/platform/keys` · **Phase 1 · 🔄 Unreachable**

- **Goal:** List active + revoked keys per workspace · search by prefix · revoke action.
- **UI components:** `DataTable` (key prefix · workspace · created_at · last_used_at · status · actions) · `Filter` by status/workspace · `Search` by `KAORI-` prefix.
- **APIs:** `GET /api/v1/platform/workspaces/{id}/keys` · `DELETE /api/v1/platform/keys/{id}` (revoke).
- **Edge cases:** Revoke a key currently in active session → invalidate refresh_tokens immediately, audit `KEY_REVOKED_FORCED`.
- **Tasks:**
  - **FE-PT-014** Keys table + filters; depends on F-009 SecurityConfig fix landing first.
  - **FE-PT-015** Revoke confirm modal showing "N active sessions will be terminated".

#### Screen 1.2/2 — Issue Key (Reveal-Once) `/platform/keys/new` · **Phase 1 · 🔄 Partial**

- **Goal:** Generate new private key for workspace, display raw value once.
- **UI components:** Workspace picker · Purpose textarea (audit) · `RevealOnce` panel with copy-to-clipboard + "I've saved this" gate.
- **APIs:** `POST /api/v1/platform/keys` `{workspace_id, purpose}` → `{id, raw_key, hash}`.
- **Edge cases:** User refreshes page after issue → key lost forever; show big warning before close.
- **Tasks:**
  - **FE-PT-016** Reveal-once panel reused from Workspace Create wizard (extract shared component).
  - **FE-PT-017** Beforeunload guard preventing accidental navigation.

#### Screen 1.2/3 — Key Detail & Usage History `/platform/keys/:id` · **Phase 1 · 🔄 Partial**

- **Goal:** Show metadata + usage timeline (login attempts, last IP, user agent).
- **APIs:** `GET /api/v1/platform/keys/{id}` (needs new endpoint) + audit query for `KEY_USED` events.
- **Tasks:**
  - **FE-PT-018** Usage timeline view (paginated, filter by event type).

### 1.4 Module 1.3 — Platform Admin Management (`/platform/admins`)

> 4 screens. Invite + manage SUPER_ADMIN/ADMIN/SUPPORT. **All Phase 1 · ❌ Ghost — F-010 claimed ✅ but no PlatformAdminController exists. Frontend blocked on backend rebuild.**

#### Screen 1.3/1 — Admin Directory `/platform/admins` · **Phase 1 · ❌ Ghost**

- **Goal:** List Kaori internal admins · filter by role · search by email/name.
- **UI components:** `DataTable` (avatar · name · email · role badge · MFA status · last login · status · actions) · `Filter` chips (role, status, MFA).
- **APIs:** `GET /api/v1/platform/admins` (NOT IMPLEMENTED).
- **Edge cases:** Cannot reduce SUPER_ADMIN count below 1 (system invariant); deactivate self → confirm + force logout + redirect login.
- **Tasks:**
  - **FE-PT-019** Admin table + role filter (block on F-010 backend rebuild).

#### Screen 1.3/2 — Invite Admin `/platform/admins/invite` · **Phase 1 · ❌ Ghost**

- **UI components:** Modal with email + role picker + welcome message; sends invite link with TTL 72h.
- **APIs:** `POST /api/v1/platform/admins/invite`.
- **Tasks:**
  - **FE-PT-020** Invite modal · email validation · role picker (SUPER_ADMIN requires MFA enrollment in onboarding).

#### Screen 1.3/3 — Admin Detail `/platform/admins/:id` · **Phase 1 · ❌ Ghost**

- **APIs:** `PATCH /api/v1/platform/admins/{id}` (deactivate/role change/reset MFA).
- **Tasks:**
  - **FE-PT-021** Detail panel with audit log of role changes; destructive actions step-up MFA.

#### Screen 1.3/4 — Identity Recovery `/platform/admins/:id/reset-password` · **Phase 1 · ❌ Ghost**

- **Tasks:**
  - **FE-PT-022** Reset trigger sending email + audit; SUPER_ADMIN reset requires another SUPER_ADMIN action.

### 1.5 Module 1.4 — Billing Monitor (`/platform/billing`)

> 4 screens. Quota / overage / alerts / export per workspace. **All Phase 1 · ⬜ Pending — blocked on F-031 cron.**

#### Screen 1.4/1 — Billing Overview `/platform/billing/overview` · **Phase 1 · ⬜ Pending**

- **Goal:** Aggregate revenue and quota across all workspaces, MoM trend.
- **UI components:** 4 KPI cards (MRR · Active enterprises · Avg quota usage · Overage events this month) · 12-month MRR `LineChart` · Top-10 enterprises by revenue table.
- **APIs:** `GET /api/v1/platform/billing/monitor?month=YYYY-MM`.
- **States:** Loading skeleton · Empty (no billing data) · Cron not run banner (if no data for current month).
- **Tasks:**
  - **FE-PT-023** KPI cards + MRR LineChart (Recharts/ECharts).
  - **FE-PT-024** Top-10 ranking with sortable columns.

#### Screen 1.4/2 — Workspace Billing Drill-down `/platform/billing/enterprises/:id` · **Phase 1 · ⬜ Pending**

- **APIs:** `GET /api/v1/platform/billing/monitor?month&workspace=`.
- **Tasks:**
  - **FE-PT-025** Per-workspace revenue card · quota gauge · overage events list · invoice history table.

#### Screen 1.4/3 — Quota & Alerts `/platform/billing/quota` · **Phase 1 · ⬜ Pending**

- **APIs:** `GET /api/v1/platform/billing/alerts` (NEW per v3.1 reconciliation).
- **Tasks:**
  - **FE-PT-026** Alert list grouped by severity (>95% critical · >80% warning) with quick-link to workspace.

#### Screen 1.4/4 — Export Center `/platform/billing/export` · **Phase 1 · ⬜ Pending**

- **APIs:** `GET /api/v1/platform/billing/monitor?format=csv`.
- **Tasks:**
  - **FE-PT-027** Date range picker + format toggle (CSV/XLSX) + async download with progress.

### 1.6 Module 1.5 — Pilot Conversion Tracking (`/platform/pilot-conversion`)

> 3 screens. **All Phase 2 · ⬜ Pending.**

| Screen | Route | Phase | Tasks |
|--------|-------|-------|-------|
| Conversion Analytics | `/platform/pilot-conversion/overview` | 2 | **FE-PT-101** Funnel + cohort retention chart by signup-month |
| Pipeline Kanban | `/platform/pilot-conversion/pipeline` | 2 | **FE-PT-102** Kanban board (Pilot · Activated · Upgraded · Churned) with drag-drop stage change + audit |
| Upgrade Wizard | `/platform/pilot-conversion/:id/convert` | 2 | **FE-PT-103** Plan picker with current usage forecast → payment confirmation → 1-click upgrade calling `POST /enterprise/onboarding/pilot/upgrade` |

### 1.7 Module 1.6 — Platform Health Dashboard (`/platform`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Health Dashboard | `/platform` | 1 | ✅ Impl | _shipped — F-012 (gateway actuator + /metrics + KPI cards)_ |
| Customize Layout | `/platform/health/customize` | 2 | ⬜ | **FE-PT-104** Drag-drop card layout editor with per-admin save (`PATCH /platform/health/layout`) |

### 1.8 Module 1.7 — Subscription Plans Config (`/platform/plans`)

> 3 screens. **All Phase 2 · ⬜ Pending.** Soft-update preserves history (existing customers keep old plan version).

| Screen | Route | Phase | Tasks |
|--------|-------|-------|-------|
| Plans Catalog | `/platform/plans` | 2 | **FE-PT-105** Plans table (PILOT / ENT BASIC / MID / MAX / ROI) + active version badge |
| Plan Detail & Versions | `/platform/plans/:id` | 2 | **FE-PT-106** Detail with version history timeline + customers count per version |
| Plan Editor | `/platform/plans/new` | 2 | **FE-PT-107** Editor: price · quotas · features matrix · "soft update" flag preserves existing customer pricing |

### 1.9 Module 1.8 — LLM & AI Provider Management (`/platform/llm`)

> 7 screens (1 Phase 1 read-only, 6 Phase 2 full editor).

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Provider & Model Catalog | `/platform/llm/catalog` | 1 | 🔄 Partial | **FE-PT-028** Read-only catalog showing Qwen variants + external providers (OpenAI/Claude/Gemini/Azure); links to per-provider drawer |
| Model Deploy & Checksum | `/platform/llm/catalog/deploy` | 2 | ⬜ | **FE-PT-108** Deploy form for new Qwen variants + SHA-256 checksum verify gate |
| External API Keys Vault | `/platform/llm/api-keys` | 2 | ⬜ | **FE-PT-109** Vault UI: list (masked), add (reveal-once), rotate, revoke; audit on every action |
| Token Quota & Cost Monitor | `/platform/llm/tokens` | 2 | ⬜ | **FE-PT-110** Usage chart + cost breakdown by provider/tenant; alert >80% monthly budget |
| Privacy Mode Policy | `/platform/llm/privacy` | 2 | ⬜ | **FE-PT-111** Per-tenant toggle for `privacy_mode=strict` (block external) + masking policy editor |
| Prompt Template Catalog | `/platform/llm/prompts` | 2 | ⬜ | **FE-PT-112** Template list (read from Studio prompts) + tag filter (vertical/task) |
| Prompt A/B Experiments | `/platform/llm/prompts/ab` | 2 | ⬜ | **FE-PT-113** A/B test dashboard: traffic split, win-rate, statistical significance |

### 1.10 Phase 3 additions for Platform Tenant

| Screen | Route | APIs | Frontend task |
|--------|-------|------|---------------|
| Compliance Dashboard | `/platform/compliance` | `GET /api/v3/enterprise/compliance/status` | **FE-PT-301** SOC2 + GDPR + EU AI Act status grid |
| LLM Fine-tuning | `/platform/llm/finetune` | `POST /api/v3/platform/llm/finetune` | **FE-PT-302** Fine-tune job submission form + run history table |
| DR Status Tab | `/platform/health` (sub-tab) | `GET /api/v3/platform/dr/status` | **FE-PT-303** Region health map + RTO/RPO indicators |
| Drift Monitor | `/platform/health` (drift card) | `GET /api/v3/platform/drift-monitor` | **FE-PT-304** PSI/KL chart per feature with alert state |

### 1.11 Platform Tenant — Phase 1 acceptance gate

- [ ] All P1 Phase 1 screens shipped or actively in sprint
- [ ] F-010 PlatformAdmin backend rebuilt; FE-PT-019..022 unblocked
- [ ] F-031 billing cron live → FE-PT-023..027 unblocked
- [ ] F-009 SecurityConfig fixed → FE-PT-014..018 unblocked
- [ ] MFA flow E2E green for SUPER_ADMIN destructive actions

---

## 2. Enterprise User (P2) — Customer organization

> **Audience:** Customer's own users — MANAGER (≥1 mandatory per enterprise), OPERATOR, ANALYST, VIEWER. The product's primary revenue-generating surface.
>
> **Module count:** 24 · **Screens:** 96 · **Leaves:** 579 · **Phase 1 active:** 2.0, 2.2, 2.3, 2.4, 2.5, 2.6 (full), 2.10, 2.14 (picker only), 2.15, 2.16/1, 2.19 (3 of 4)

### 2.1 Module 2.0 — Authentication (`/p2/auth`)

> 4 screens. Phase 1 except Sessions.

#### Screen 2.0/1 — Login `/p2/auth/login` · **Phase 1 · ✅ Impl**

- _Shipped — F-002._

#### Screen 2.0/2 — First Login & Activation `/p2/auth/activate/:token` · **Phase 1 · 🔄 Partial**

- **Goal:** First-time enterprise user activates account via invite token, sets password, optionally enables MFA.
- **UI components:** `TokenVerifier` (loading) · 3-step wizard (verify → set password → MFA optional) · `PasswordStrengthMeter`.
- **Validation:** Token < 72h old, not used, matches `users.invitation_token_hash`; new password policy (12+ chars, mixed case + digit + symbol).
- **APIs:** `POST /api/v1/enterprise/auth/activate/{token}` `{password, mfa_enable}`.
- **States:** Loading · Token expired (CTA "Request new invite") · Success (redirect dashboard with onboarding tour flag).
- **Edge cases:** Backend contract mismatch with current `/auth/workspace/activate` route — coordinate with F-013 cleanup; user already activated → 410 Gone with login link.
- **Tasks:**
  - **FE-EU-001** 3-step activation wizard with token verifier + password setup + MFA opt-in.
  - **FE-EU-002** Reconcile route naming with backend (F-013 contract fix).

#### Screen 2.0/3 — Password Recovery `/p2/auth/forgot-password` · **Phase 1 · ✅ Impl**

- _Shipped — F-003._

#### Screen 2.0/4 — Session Management `/p2/auth/sessions` · **Phase 2 · ⬜ Pending**

- **Tasks:** **FE-EU-101** Sessions table identical structure to FE-PT-004 (extract shared component).

### 2.2 Module 2.0a — Authorization (RBAC + ABAC + Hybrid) (`/p2/authz`)

> 8 screens. **All Phase 2 · ⬜ Pending.** Cross-portal authorization editor.

| Screen | Route | Phase | Tasks |
|--------|-------|-------|-------|
| Roles & Permissions | `/p2/authz/rbac` | 1 (currently ❌ Ghost) | **FE-EU-002b** Read-only role matrix viewer for Phase 1 (full editor → Phase 2) |
| Custom Roles Editor | `/p2/authz/rbac/custom-roles` | 2 | **FE-EU-201** Custom role builder: pick permissions from catalog · clone existing role · save with audit |
| ABAC Policy Builder | `/p2/authz/abac/builder` | 2 | **FE-EU-202** Visual policy builder (Subject/Resource/Action/Condition) · DSL preview pane |
| Policy Simulation & Impact | `/p2/authz/abac/simulate` | 2 | **FE-EU-203** Simulate policy on sample requests · diff allow/deny vs current · "what-if" mode |
| Delegation | `/p2/authz/delegation` | 3 | **FE-EU-301** Temporary role delegation form with TTL + audit (Phase 3 — see §2.24) |
| Decision Audit | `/p2/authz/audit/decisions` | 2 | **FE-EU-204** Audit table: every PDP decision with reason chain |
| Why Denied (User-facing) | `/p2/authz/audit/why-denied` | 2 | **FE-EU-205** End-user view: "Action X denied because policy Y" with appeal CTA |
| Compliance Reports | `/p2/authz/compliance/*` | 2 | **FE-EU-206** Reports per compliance standard (SOC2/GDPR access reviews) |

### 2.3 Module 2.1 — Organization Branding (`/p2/branding`)

> 2 screens. **Phase 2** (re-tagged from Phase 3 per v3.1 reconciliation).

| Screen | Route | Phase | Tasks |
|--------|-------|-------|-------|
| Branding Editor | `/p2/branding` | 2 | **FE-EU-207** Editor: logo upload (PNG/SVG, max 2MB) · color pickers (primary/accent/neutral) · theme toggle (light/dark/auto) · subdomain field with availability check |
| Email & PDF Template | `/p2/branding/email` | 2 | **FE-EU-208** Template editor with variable substitution preview · PDF mock generator using current branding |

### 2.4 Module 2.2 — Onboarding + Pilot Flow (`/p2/onboarding`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Onboarding Wizard | `/p2/onboarding` | 1 | ❌ Ghost | **FE-EU-003** 4-step wizard: enter `KAORI-XXXX` key → company info (name, tax ID, vertical, size) → invite first MANAGER → success with first-login email sent |
| Pilot Countdown Banner | (cross-portal overlay) | 2 | ⬜ | **FE-EU-209** Persistent banner D1-D30 of pilot · D25 "5 days left" · D30 "Upgrade now" with CTA |
| Upgrade Flow | `/p2/onboarding/pilot/upgrade` | 2 | ⬜ | **FE-EU-210** Plan picker with usage-based recommendation · payment method · confirm |

#### Detail for Onboarding Wizard

- **Goal:** Convert key-bearing prospect into first usable enterprise account in < 5 min.
- **UI components:** Stepper · KeyInput (auto-format `KAORI-XXXX-XXXX-XXXX-XXXX`) · CompanyForm (autocomplete tax ID via VN biz registry if integrated) · InviteForm.
- **Validation:** Key format match · key not yet activated · tax ID 10/13 digits · MANAGER email RFC 5322 + not already used.
- **APIs:** `POST /api/v1/enterprise/onboarding/activate-key` · `POST /api/v1/enterprise/users/invite`.
- **Edge cases:** Key already activated → show "This key was activated on {date}, contact Kaori support" with audit trail link; user closes mid-wizard → resumable via email reminder D+1.

### 2.5 Module 2.3 — Enterprise Dashboard (`/p2/dashboard`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Main Dashboard | `/p2/dashboard` | 1 | ✅ Impl | _shipped — F-028 (5-state machine, KPI cards, quota)_ |
| Customize Layout | `/p2/dashboard/customize` | 2 | ⬜ | **FE-EU-211** Drag-drop layout editor (`react-grid-layout`) · per-user save · template library |

### 2.6 Module 2.4 — User & Role Management (`/p2/users`)

> 3 screens. **All Phase 1 · ⬜ Pending.** Min 1 MANAGER invariant.

| Screen | Route | Status | APIs | Tasks |
|--------|-------|--------|------|-------|
| Users List | `/p2/users` | ⬜ | `GET /enterprise/users` | **FE-EU-004** Table (avatar · name · email · role badge · status · last login · actions) · Filter by role/status · Search · "Invite member" CTA top-right |
| Invite Modal | `/p2/users/invite` | ⬜ | `POST /enterprise/users/invite` | **FE-EU-005** Modal: email + role + welcome message + send · multiple invites in one go · CSV bulk upload |
| User Detail & Role Editor | `/p2/users/:id` | ⬜ | `PATCH /enterprise/users/:id`, `DELETE` | **FE-EU-006** Detail panel: profile · role editor with permissions preview · activity timeline · destructive actions (deactivate, force logout, delete) |

**Min-MANAGER invariant:** Frontend MUST block role downgrade or deactivation if it would reduce active MANAGER count below 1. Show modal "Cần ≥1 MANAGER. Promote another user first."

### 2.7 Module 2.5 — Data Architecture (`/p2/data`)

> 4 screens. Screen 1 Phase 1 (Data Explorer); 3 layer screens Phase 2.

#### Screen 2.5/1 — Data Explorer `/p2/data` · **Phase 1 · ❌ Ghost** (NEW backend F-NEW3)

- **Goal:** Browse Bronze/Silver/Gold tables across the medallion layers; click table for lineage trace.
- **UI components:** 3 layer tabs · per-layer table list with row count + last update · `LineageDrawer` showing Bronze→Silver→Gold flow for selected table · search + filter.
- **APIs (NEW):** `GET /api/v1/enterprise/data/{bronze|silver|gold}/tables` · `GET /api/v1/enterprise/data/lineage?table_id=`.
- **States:** Loading per tab · Empty (Gold layer empty until F-032 lands) · Error (table not in tenant scope → 403).
- **Edge cases:** Lineage cross-tenant leak prevention — backend MUST filter; FE displays only nodes in current tenant.
- **Tasks:**
  - **FE-EU-007** Tab + table list per layer.
  - **FE-EU-008** LineageDrawer with `react-flow` or `cytoscape` for the graph.
  - **FE-EU-009** Tenant-aware error states + 403 redirect.

| Screen | Route | Phase | Tasks |
|--------|-------|-------|-------|
| Bronze Layer | `/p2/data/bronze` | 2 | **FE-EU-212** Bronze table inspector (raw payload viewer · ingestion timeline · file source link) |
| Silver Layer | `/p2/data/silver` | 2 | **FE-EU-213** Silver table inspector (cleaned data preview · cleaning rules applied · type schema) |
| Gold Layer | `/p2/data/gold` | 2 | **FE-EU-214** Gold table inspector (MV definition · refresh history · feature lineage) — depends on F-032 |

### 2.8 Module 2.6 — Data Pipeline Wizard (`/p2/pipelines`)

> **6 screens · ALL ✅ Impl (F-017..F-021).** Phase 1 wizard fully shipped.

| Screen | Route | Status | Notes |
|--------|-------|--------|-------|
| Wizard Shell & Stepper | `/p2/pipelines/new` | ✅ | F-017..F-021 wired |
| Step 1 · Upload | `/p2/pipelines/new/step-1-upload` | ✅ | SHA-256 dedup; 0-row guard |
| Step 2 · Columns | `/p2/pipelines/new/step-2-columns` | ✅ | Confidence-based color coding; manual override row |
| Step 3 · Clean | `/p2/pipelines/new/step-3-clean` | ✅ | Rule preview; rollback per rule |
| Step 4 · Analyze | `/p2/pipelines/new/step-4-analyze` | ✅ | Template multi-select; external AI consent gate |
| Step 5 · Results | `/p2/pipelines/new/step-5-results` | ✅ | ChartBlock[] renderer |

**Pipeline Run History (companion screen):**

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Pipeline Run History | `/p2/pipelines` | 1 | ⬜ Pending | **FE-EU-010** Table list (file name · created_at · status · row count · duration · actions) · Filter (status, date range) · Re-open action navigates to wizard at appropriate step |

**Polish backlog:**
- **FE-EU-215** Wizard analytics (drop-off per step) for product team.
- **FE-EU-216** Retry surfaces on transient errors; SSE status stream when F-NEW2 lands.

### 2.9 Module 2.7 — Auto Database Design (`/p2/auto-db`)

> 4 screens. **All Phase 2 · ⬜ Pending** (despite v3.1 catalog mis-tag).

| Screen | Route | Tasks |
|--------|-------|-------|
| Suggestions Dashboard | `/p2/auto-db` | **FE-EU-217** Dashboard listing AI-suggested schemas (3NF · star · denormalized) · accept/reject per suggestion |
| Schema Suggestion Wizard | `/p2/auto-db/schema-suggestion` | **FE-EU-218** AI-driven wizard: pick source table → pattern detection → proposed CREATE TABLE + ERD preview |
| Form Generator | `/p2/auto-db/forms/generate` | **FE-EU-219** Generated CRUD form scaffolding for the new schema · field validators auto-derived |
| Quality Trend & Migrations | `/p2/auto-db/quality-trend` | **FE-EU-220** Quality score over time · migration history with rollback |

### 2.10 Module 2.8 — Multi-tier Data Analysis (`/p2/analysis`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Analysis Dashboard | `/p2/analysis` | 1 | 🔄 Partial | **FE-EU-011** Hub: list of completed analyses · "New analysis" CTA · Tier badge per row (Basic/Intermediate/Advanced) · Filter by template/scope/date |
| Basic Analysis | `/p2/analysis/basic` | 2 | ⬜ | **FE-EU-221** Form: pick pipeline + descriptive stats + top-N + segments → run → results page |
| Intermediate Analysis | `/p2/analysis/intermediate` | 2 | ⬜ | **FE-EU-222** Form: correlation · trend · time-series · MoM/YoY auto-fill |
| Advanced Analysis | `/p2/analysis/advanced` | 2 | ⬜ | **FE-EU-223** Form: predictive (regression/classification) · causal · what-if simulator |
| Scope Picker | `/p2/analysis/scope` | 2 | ⬜ | **FE-EU-224** Multi-pipeline picker · time window · compare mode (A vs B) |

### 2.11 Module 2.9 — Analysis Frameworks (`/p2/frameworks`)

> **F-034 v0 — ✅ shipped (4 frameworks).** MoM/YoY + Custom remain ⬜ pending v1 BE.

| Screen | Route | Tasks |
|--------|-------|-------|
| Frameworks Gallery | `/p2/frameworks` | **FE-EU-225** _shipped this PR_ — wired hub: live catalogue from `/templates`, gallery cards for 4 active frameworks + 2 placeholder cards (MoM/YoY + Custom), recent runs table joining all framework codes |
| SWOT Canvas | `/p2/frameworks/swot` | **FE-EU-226** _shipped this PR_ — generate-and-poll form (question + source_ref + K-4 consent toggle) → 4-quadrant grid (S/W/O/T) with confidence per item + summary callout. Manual edit / "export to report" deferred to v1 |
| 6W Framework | `/p2/frameworks/6w` | **FE-EU-227** _shipped this PR_ — same form shell, renders 6 fields list (Who/What/When/Where/Why/How) + summary |
| 2H Framework | `/p2/frameworks/2h` | **FE-EU-228** _shipped this PR_ — How section (approach + 3-7 steps) + How much section (estimate + unit + confidence + assumptions) |
| Fishbone Diagram | `/p2/frameworks/fishbone-ishikawa` | **FE-EU-229** _shipped this PR_ — categorised list grid with depth badges (triệu chứng / trực tiếp / gốc rễ) + root cause hypothesis callout. Diagram editor (`react-flow`) deferred to v1 — current renderer is sufficient for read-only |
| MoM/YoY Analysis | `/p2/frameworks/mom-yoy-analysis` | **FE-EU-230** ⬜ — placeholder card on hub; legacy mock template still wired. v1 (calculation feature, not LLM) |
| Custom Framework Builder | `/p2/frameworks/custom-analyst` | **FE-EU-231** ⬜ — placeholder card on hub; legacy mock template still wired. v1 stretch |

### 2.12 Module 2.10 — Insights Engine (`/p2/insights`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Insights List | `/p2/insights` | 1 | ✅ Impl | _shipped — F-025_ |
| Insight Detail (3-panel) | `/p2/insights/:id` | 1 | ✅ Impl | _Verify backend includes `GET /enterprise/insights/{id}`_ — see F-025 amendment |
| Generate Insight | `/p2/insights/generate` | 1 | ✅ Impl | _shipped — F-025_ |
| Knowledge Base | `/p2/insights/knowledge-base` | 2 | ⬜ | **FE-EU-232** Curated KB articles + tags + search; auto-attached to insights as citations |

**Insight Detail spec recap:**
- 3 panels: "Chuyện gì" (what) · "Tại sao" (why) · "Nên làm gì" (what to do)
- Each panel includes confidence + citation chips linking to source data/rules
- Export to PDF or share via email
- Action button "Mark as actioned" feeds North Star Metric (`is_actioned=true` → ROI bonus calc)

### 2.13 Module 2.11 — Risk Management (`/p2/risks`)

> 3 screens. **All Phase 2 · ⬜ Pending.**

| Screen | Route | Tasks |
|--------|-------|-------|
| Risk Radar Dashboard | `/p2/risks` | **FE-EU-233** Heat map (probability × impact) · auto-detected risks listed · filter by status (open/mitigated/closed) |
| Risk Detail Drawer | `/p2/risks/:id` | **FE-EU-234** Detail: description · score · owner · mitigation plan · escalate button calling `POST /risks/:id/escalate` · audit timeline |
| Risk Register Export | `/p2/risks/export` | **FE-EU-235** CSV/PDF export with date range + filters |

### 2.14 Module 2.12 — Strategy Builder (`/p2/strategy`)

> 4 screens. **All Phase 2 · ⬜ Pending.**

| Screen | Route | Tasks |
|--------|-------|-------|
| Strategy Dashboard | `/p2/strategy` | **FE-EU-236** Active strategies grid · KPI per strategy · health indicator |
| OKR/OGSM Canvas | `/p2/strategy/okr` | **FE-EU-237** Editable canvas (Objective + Key Results) · KR auto-link to gold features for live progress |
| Timeline & Progress | `/p2/strategy/:id/timeline` | **FE-EU-238** Gantt roadmap (`react-gantt-task` or custom) · drag to reschedule · risk-action linkage badges |
| Review Meeting | `/p2/strategy/:id/review-meetings` | **FE-EU-239** Meeting scheduler · attendance · note template auto-populated with KR delta since last review |

### 2.15 Module 2.13 — Reports Management (`/p2/reports`)

> 5 screens, all in `frontend/components/p2/templates/` (47..51) since the P2-templates batch shipped 2026-05-01. **Backend `/api/v1/reports*` shipped PR #113 (2026-05-02).** Auto path FE wiring is the next PR; builder/templates/distribution stay ⬜.

| Screen | Route | Template file | Tasks |
|--------|-------|---------------|-------|
| Reports Hub | `/p2/reports/hub` | 47-reports-hub.tsx | **FE-EU-240** 🔄 — wire `GET /api/v1/reports` (cursor + adapter from BE `ReportListItem` to template `ReportRow` shape: `report_id→id`, `created_at→updated_at`, derive `type` from `template_id == built-in monthly_summary`, status map `queued→scheduled / running→draft / ready→published / failed→failed`). Patch F-053→F-038 banner. Remove `@ts-nocheck` |
| Auto Reports Config | `/p2/reports/auto` | 48-report-auto.tsx | **FE-EU-241** 🔄 — wire `POST /api/v1/reports/generate` with `{template_id: built-in monthly_summary uuid, title: name, owner_email: recipients[0], params: {goal, cadence, dataset_id, schedule_cron, consent_external}}`. Single recipient v0; fan-out is BE follow-up. Patch F-053→F-038 banner |
| Report Builder | `/p2/reports/builder` | 49-report-builder.tsx | **FE-EU-242** ⬜ — block-based builder. Patch F-053→F-038 typo only this round; full wiring waits for `POST /api/v1/reports/builder` (BE-EU-221) |
| Templates Library | `/p2/reports/template` | 50-report-template.tsx | **FE-EU-243** ⬜ — template grid + clone/edit. Patch F-053→F-038 typo only |
| Distribution & Export | `/p2/reports/distribution` | 51b-report-distribution-wired.tsx | **FE-EU-244** _shipped this PR_ — wired one-shot manual distribute against BE PR #118: `?report=<id>` querystring picker fallback + recipients textarea (FE dedup mirror, ≤50 cap mirror) + custom_message ≤500 chars + Send Now + history table joined to `notification_outbox` (live SMTP status / attempts / sent_at). Hub Send icon deep-links here for `published` reports only. Slack/webhook + cron + role-groups deferred to v1 (legacy 51-report-distribution.tsx kept in components/ as placeholder) |

### 2.16 Module 2.14 — Chart & Visualization Library (`/p2/charts`)

> 7 screens. Screen 1 Phase 1 (Picker), rest Phase 2.

#### Screen 2.14/1 — Chart Picker & Recommendation `/p2/charts/picker` · **Phase 1 · 🔄 Partial**

- **Goal:** Let user pick from 100+ chart kinds with AI recommendation based on data shape.
- **UI components:** Search · category filter (comparison · distribution · relationship · composition · trend) · grid of chart cards with thumbnail + min data shape · "Recommend top 3" button.
- **APIs:** `GET /api/v1/enterprise/charts/catalog` (NEW per v3.1 reconciliation) · `POST /api/v1/shared/charts/render` (currently ❌ Ghost — F-027 backend missing).
- **Tasks:**
  - **FE-EU-012** Chart picker grid with search + filter.
  - **FE-EU-013** Recommendation panel calling backend `POST /charts/recommend`.
  - **FE-EU-014** Render preview pane — blocked on F-027 backend handler.

| Screen | Route | Phase | Tasks |
|--------|-------|-------|-------|
| Chart Type Catalogs | `/p2/charts/:category` | 2 | **FE-EU-245** Per-category browser with examples |
| Chart Customization | `/p2/charts/customization` | 2 | **FE-EU-246** Spec editor (axes · colors · legend · tooltip · data label) with live preview |
| Chart Interactivity Settings | `/p2/charts/interactivity` | 2 | **FE-EU-247** Toggle drill-down · cross-filter · zoom · pan |
| Chart Export & Share | `/p2/charts/export` | 2 | **FE-EU-248** Export PNG/SVG/PDF · share via link with permissions |
| Chart Templates | `/p2/charts/templates` | 2 | **FE-EU-249** Template library + save current chart as template |
| Chart Container (embedded) | (cross-screen) | 2 | **FE-EU-250** Reusable `<KaoriChart />` component used in dashboards/reports/insights |

### 2.17 Module 2.15 — AI Decision Log (`/p2/decisions`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Decision Log Table | `/p2/decisions` | 1 | ⬜ Pending | **FE-EU-015** Immutable log table: type · model · confidence · features summary · actioned badge · timestamp · drill-link · CSV export · filter (type, date, confidence range, actioned status) |

- **APIs:** `GET /api/v1/enterprise/decisions` (currently 404 — F-029 router unregistered).
- **Edge cases:** Confidence visualization (color band: green ≥0.8, yellow 0.6-0.8, red <0.6); actioned events highlighted (drives North Star).

### 2.18 Module 2.16 — Decision Detail & Override (`/p2/decisions/:id`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Decision Detail Page | `/p2/decisions/[id]` | 1+2 | 🟡 | **FE-EU-016** _shipped this PR (basic surface)_ — wired against BE PR #122: header card (subject + chosen_value + confidence + uncertainty_flags + is_actioned toggle from Sprint 7 PR D), reasoning section, alternatives list (gracefully accepts any-shape jsonb), audit panel (decision_id / run_id / method / created_at). SHAP explainability + Vietnamese translation are deferred to F-041 |
| Override (inline modal) | `/p2/decisions/[id]` (modal) | 2 | 🟡 | **FE-EU-251** _shipped this PR_ — header "Override mới" button opens a modal (override_value ≤ 500 + reason 1-2000) → POST `/api/v1/decisions/{id}/override` → emits `kaori.feedback.actions`. History list per decision shows active + revoked overrides; "Thu hồi" button on active rows triggers `prompt()` reason → POST `/.../revoke`. Header card displays struck-through original chosen_value when an active override exists |

### 2.19 Module 2.17 — Workflow Builder (`/p2/workflows`)

> 3 screens. **All Phase 2 · ⬜ Pending.** Backed by Temporal.io.

| Screen | Route | Tasks |
|--------|-------|-------|
| Workflows List | `/p2/workflows` | **FE-EU-252** Workflows table · status (draft/active/paused) · last run · trigger source |
| Canvas Builder | `/p2/workflows/:id/builder` | **FE-EU-253** Drag-drop canvas (`react-flow`) · node types (trigger/action/condition/agent) · variable mapping · save as version |
| Test & Versions | `/p2/workflows/:id/test` | **FE-EU-254** Test mode: run on historical data · diff vs production version · promote test → active |

### 2.20 Module 2.18 — Alert Rules (`/p2/alerts`)

> 2 screens. **F-037 v0 — ✅ shipped.** Email channel only this round; Slack/webhook + DSL editor deferred to v1.

| Screen | Route | Tasks |
|--------|-------|-------|
| Rules + History | `/p2/alerts` | **FE-EU-255** _shipped this PR_ — single page with 2 tabs (events history + rules CRUD), KPIs (fires 7d, suppressed 7d, total, latest), MANAGER role-gated mutations, modal editor (no full /new route). MSW handlers in `mocks/handlers/alerts.ts`. F-058 fired-alerts inbox (62-alert.tsx) stays as Phase 2 placeholder for the eventual ack/resolve workflow at a future route |
| Rule Editor | _modal in `/p2/alerts`_ | **FE-EU-256** _shipped this PR_ — inline modal (Plus button → modal, Pencil icon → edit-modal). Fields: name / description / operator / threshold / target_email / cooldown_seconds / is_active. Slack/webhook + DSL autocomplete + test-send deferred (BE only supports `metric_type=billing_quota_pct` + `channel=email` in v0) |

### 2.21 Module 2.19 — Subscription & Quota (`/p2/subscription`)

> 4 screens. 3 Phase 1, 1 Phase 2.

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| Quota Dashboard | `/p2/subscription/quota` | 1 | ⬜ | **FE-EU-017** Gauge: unique customers used vs quota · 80% warning banner · 95% critical banner · forecast end-of-month overage |
| Current Plan | `/p2/subscription/plan` | 1 | ⬜ | **FE-EU-018** Plan card with features matrix · billing contact · next renewal date · payment method preview |
| Upgrade Compare | `/p2/subscription/upgrade` | 1 | ⬜ | **FE-EU-019** Plan comparison table · "Upgrade" CTA per plan · confirmation modal showing prorated charge |
| Contact Sales | `/p2/subscription/contact-sales` | 2 | ⬜ | **FE-EU-257** Form: company size · use case · preferred contact · sends to Sales team via webhook |

**Quota gauge edge cases:** When `unique_customers_billed = quota` exactly → show "AT QUOTA" amber banner; when overage active → show overage cost projection.

### 2.22 Module 2.20 — ROI Billing Report (`/p2/billing/roi`)

| Screen | Route | Phase | Status | Tasks |
|--------|-------|-------|--------|-------|
| ROI Report Dashboard | `/p2/billing/roi` | 2 | ⬜ | **FE-EU-258** Per billing month: base + overage + ROI bonus breakdown · revenue_at_risk vs actioned chart · download PDF/Excel |

### 2.23 Module 2.21 — Data Knowledge Graph (`/p2/knowledge-graph`)

> 7 screens. **All Phase 2 · ⬜ Pending.** Backed by Neo4j CE + pgvector.

| Screen | Route | Tasks |
|--------|-------|-------|
| Graph Canvas | `/p2/knowledge-graph` | **FE-EU-259** Interactive graph (`cytoscape.js`) · zoom/pan/select · cluster by node type · search highlight |
| Node Inspector | `/p2/knowledge-graph/nodes/:id` | **FE-EU-260** Node detail drawer: properties JSON · incoming/outgoing edges · related entities · audit |
| Lineage Tracing | `/p2/knowledge-graph/lineage` | **FE-EU-261** Upstream/downstream graph for selected node (data lineage) |
| Semantic Search | `/p2/knowledge-graph/search` | **FE-EU-262** Search bar with BGE-M3 embedding lookup · result list with relevance score |
| Graph Maintenance | `/p2/knowledge-graph/maintenance` | **FE-EU-263** Admin tools: rebuild index · validate constraints · purge orphans |
| Graph API Console | `/p2/knowledge-graph/api-console` | **FE-EU-264** Cypher query playground (read-only) · sample queries library |
| Annotation Editor | (inline overlay) | **FE-EU-265** Inline annotation tool on canvas · save with author + timestamp |

### 2.24 Module 2.22 — Blast Radius / Impact Analysis (`/p2/blast-radius`)

> 5 screens. **All Phase 2 · ⬜ Pending.**

| Screen | Route | Tasks |
|--------|-------|-------|
| Pre-change Impact Modal | `/p2/blast-radius/pre-change` | **FE-EU-266** Modal triggered before destructive change · shows affected nodes/users · proceed/cancel/governance route |
| Change Types Catalog | `/p2/blast-radius/change-types` | **FE-EU-267** Catalog of supported change types with risk profile per type |
| Impact Visualization | `/p2/blast-radius/visualization` | **FE-EU-268** Visual blast radius graph centered on change · color by risk score |
| Change Governance Queue | `/p2/blast-radius/governance` | **FE-EU-269** Queue of high-risk changes pending approval · approve/reject with comment |
| Safe-change Assistant | `/p2/blast-radius/assistant` | **FE-EU-270** AI-assistant suggesting safer alternative for risky change |

### 2.25 Phase 3 additions for Enterprise User

| Screen | Route | APIs | Frontend task |
|--------|-------|------|---------------|
| Compliance Status | `/p2/compliance` | `GET /api/v3/enterprise/compliance/status` | **FE-EU-302** Tenant-level compliance grid |
| Compliance Fairness | `/p2/compliance/fairness` | `POST /api/v3/shared/fairness/audit` | **FE-EU-303** Bias detection report (demographic parity, equalized odds) |
| Compliance Export | `/p2/compliance/export` | `POST /api/v3/enterprise/compliance/export` | **FE-EU-304** SOC2 / EU AI Act evidence pack download |
| GDPR Erasure | `/p2/settings/privacy` | `POST /api/v3/enterprise/privacy/erasure-request` | **FE-EU-305** Erasure request form + 30-day SLA tracker |
| Audit Log Query UI | `/p2/audit` | `GET /api/v1/shared/audit/events` | **FE-EU-306** Search + filter + paginate; 2-year retention |
| Finance Analysis | `/p2/analysis/finance` | `POST /api/v3/enterprise/analysis/run` (finance) | **FE-EU-307** Templates: credit risk · fraud detection · cash flow |
| Logistics Analysis | `/p2/analysis/logistics` | `POST /api/v3/enterprise/analysis/run` (logistics) | **FE-EU-308** Templates: demand forecast · route optimization |

### 2.26 Enterprise User — Phase 1 acceptance gate

- [ ] All P2 Phase 1 screens shipped or actively in sprint (FE-EU-001..019 closed)
- [ ] Decision Log loads ≥1 real audit row (validates K-6 invariant)
- [ ] Pipeline wizard E2E green for 3 retail vertical sample CSVs
- [ ] Subscription quota shows real `enterprise_monthly_billing` data (validates F-031)
- [ ] User & Role enforces min-1-MANAGER guard on FE side

---

## 3. Studio (P3) — Kaori Analyst + Enterprise Analyst

> **Audience:** Kaori internal Data Scientists / ML Engineers (STUDIO_ADMIN, MFA mandatory) and assigned Enterprise Analysts (STUDIO_ANALYST, scoped per enterprise).
>
> **Purpose:** Build models, fine-tune prompts, deliver custom reports per enterprise. Isolation enforced at project level — analyst sees only assigned enterprises.
>
> **Module count:** 9 · **Screens:** 20 · **Leaves:** 62 · **Phase activation:** **Entire portal Phase 2** (per v3.1 screen sheet).

### 3.1 Module 3.0 — Authentication (`/p3/auth`)

> 4 screens · all Phase 2.

| Screen | Route | Tasks |
|--------|-------|-------|
| Login | `/p3/auth/login` | **FE-ST-001** Login form supporting Kaori staff (LDAP-style email) and Enterprise Analyst (invite-based) · MFA enforcement for STUDIO_ADMIN |
| Activation | `/p3/auth/activate/:token` | **FE-ST-002** First-login activation for invited analyst · scope assignment confirm |
| Password Recovery | `/p3/auth/forgot-password` | **FE-ST-003** Standard recovery flow |
| Sessions Management | `/p3/auth/sessions` | **FE-ST-004** Active sessions table + revoke (reuse component from FE-PT-004) |

### 3.2 Module 3.1 — Studio Home (`/p3/home`)

| Screen | Tasks |
|--------|-------|
| Home Dashboard | **FE-ST-005** Home: assigned projects card list · activity feed (model trained, report sent, prompt updated) · shortcut to recent project · role badge (STAFF/ANALYST) |

### 3.3 Module 3.2 — Project List (`/p3/projects`)

| Screen | Tasks |
|--------|-------|
| Projects Table | **FE-ST-006** Table: project name · enterprise · status · members · last activity · actions; filter by enterprise/status; bulk archive |
| New Project Wizard | **FE-ST-007** Wizard: enterprise picker (scoped) → project info → auto-assign creator as lead |

### 3.4 Module 3.3 — Project Detail (`/p3/projects/:id`)

| Screen | Tasks |
|--------|-------|
| Project Detail (5 tabs) | **FE-ST-008** Tabs: Overview · Members · Models · Reports · Datasets snapshot. Edit only for project lead. Audit trail per tab. |

### 3.5 Module 3.4 — Model Registry & Version (`/p3/models`)

> 3 screens. Backed by MLflow + PostgreSQL.

| Screen | Tasks |
|--------|-------|
| Models List | **FE-ST-009** Table: model name · current version · framework · checksum · metrics summary · state (DRAFT/STAGING/DEPLOYED/RETIRED) |
| Model Version Detail | **FE-ST-010** Detail: training log link · metrics (precision/recall/F1/AUC) · feature importance · checksum verification · download artifact |
| Promote / Rollback Modal | **FE-ST-011** Modal: green-blue promote with traffic split slider · rollback to previous version · confirm with audit reason |

### 3.6 Module 3.5 — Training Log (`/p3/training-log/:runId`)

| Screen | Tasks |
|--------|-------|
| Training Log Detail | **FE-ST-012** Charts: loss curve · accuracy curve per epoch · hyperparam table · dataset info · compare-runs mode (overlay 2-3 runs) |

### 3.7 Module 3.6 — Report Composer & Delivery (`/p3/reports/composer`)

> 3 screens.

| Screen | Tasks |
|--------|-------|
| Composer Editor | **FE-ST-013** Rich text editor (TipTap/Lexical) · attach chart from Gold tables (chart picker drawer) · attach analysis result · enterprise picker (scoped, multi-select) · draft autosave every 30s |
| Preview | **FE-ST-014** Per-recipient preview (branding applied per enterprise) |
| Send & Delivery | **FE-ST-015** Fan-out delivery: email + in-app notification · delivery status table (queued/sent/opened/failed) |

### 3.8 Module 3.7 — Custom LLM Prompt Tuning (`/p3/prompts`)

> 3 screens.

| Screen | Tasks |
|--------|-------|
| Prompts List & Editor | **FE-ST-016** Split view: left = prompt list filterable by vertical/task · right = editor with variable placeholders · test panel with sample input · save with versioning |
| Share Modal | **FE-ST-017** Share to specific enterprise(s) · scope: read-only / use-as-template / full-edit |
| A/B Experiments Dashboard | **FE-ST-018** Experiment setup (variant A vs B · traffic split) · running stats · stop / promote winner |

### 3.9 Module 3.8 — Studio Settings (`/p3/settings/members`)

> 2 screens.

| Screen | Tasks |
|--------|-------|
| Members List | **FE-ST-019** List Studio members · type badge (STAFF/ANALYST) · scope (enterprises) · status · invariant: ≥1 STUDIO_ADMIN |
| Invite & Edit Member | **FE-ST-020** Modal: email + type + scope (enterprise picker, only for ANALYST) + send invite |

### 3.10 Studio — Phase 3 additions

| Screen | Route | APIs | Frontend task |
|--------|-------|------|---------------|
| AutoGen Studio Alternative UI | `/p3/agents/studio` | `POST /api/v3/studio/agents/build`, `/run`, `/inspect` | **FE-ST-301** AutoGen-style multi-agent design canvas: agent palette · message-flow visualizer · run inspector · transcript export. Replaces external AutoGen Studio for tenants needing in-Kaori agent design (Shared module 5.6b/5 surfaces here under P3 portal) |

### 3.11 Studio — Phase 2 acceptance gate

- [ ] All 20 P3 screens shipped
- [ ] At least 3 Kaori analysts use Studio for model lifecycle
- [ ] At least 1 enterprise analyst onboarded with scoped access
- [ ] Report fan-out delivered to ≥1 enterprise customer with branding applied

---

## 4. Personal (P4) — Freelancer / individual

> **Audience:** Solo users — freelancers, knowledge workers, individuals tracking goals/health/finance/productivity. Single role: PERSONAL_USER (self-only data scope).
>
> **Purpose:** Personal data analysis at consumer-grade UX. Reuse pipeline + analysis engine but with simpler templates and personal-level branding.
>
> **Module count:** 10 · **Screens:** 17 · **Leaves:** 58 · **Phase activation:** **Entire portal Phase 2** (per v3.1 screen sheet).

### 4.1 Module 4.0 — Authentication (`/p4/auth`)

> 5 screens · all Phase 2.

| Screen | Tasks |
|--------|-------|
| Signup | **FE-PE-001** Signup form: email/phone/OAuth (Google/Apple) · password setup · terms+GDPR opt-in · email/SMS OTP |
| Login | **FE-PE-002** Login with email/phone/OAuth · MFA optional |
| OTP Verify | **FE-PE-003** OTP input (6 digits) · resend timer · alternate channel (email→SMS) |
| Password Recovery | **FE-PE-004** Standard recovery |
| Account Management | **FE-PE-005** Profile · password change · MFA toggle · delete account (GDPR right-to-erasure: 30-day grace period, then hard delete) |

### 4.2 Module 4.1 — Personal Dashboard (`/p4/dashboard`)

| Screen | Tasks |
|--------|-------|
| Dashboard | **FE-PE-006** Layout: top KPI strip (active goals · streak days · weekly progress %) · 7-day activity sparkline · AI suggestions card · quick "log activity" CTA |

### 4.3 Module 4.2 — Data Upload (`/p4/uploads`)

| Screen | Tasks |
|--------|-------|
| Upload Wizard | **FE-PE-007** Type picker (HEALTH/FINANCE/PRODUCTIVITY/GENERIC) · drag-drop file zone · progress bar · checksum + virus scan status · post-upload status lifecycle |

### 4.4 Module 4.3 — Data Library (`/p4/library`)

> 2 screens.

| Screen | Tasks |
|--------|-------|
| Library Grid | **FE-PE-008** File grid · filter by type/status · preview (first 100 rows) · soft-delete (30-day trash) |
| Trash Bin | **FE-PE-009** Trashed items · restore action · permanent delete (irreversible confirm) |

### 4.5 Module 4.4 — Personal Data Pipeline (`/p4/pipelines/new`)

| Screen | Tasks |
|--------|-------|
| Personal Pipeline Wizard | **FE-PE-010** 5-step wizard reusing P2 pipeline shell · restricted to BASIC analysis tier · personalized insight phrasing |

### 4.6 Module 4.5 — Goals & Plans Hierarchy (`/p4/goals`)

> 2 screens. Tree: Goal → Plan → Strategy. Max 10 active goals.

| Screen | Tasks |
|--------|-------|
| Goals Tree | **FE-PE-011** Tree view (drag-drop reorder) · per-goal progress circle · max 10 active enforcement · archive vs delete |
| New Goal Wizard | **FE-PE-012** Wizard: title · target · deadline · category · plan template picker |

### 4.7 Module 4.6 — Goal Detail & Tracking (`/p4/goals/:id`)

| Screen | Tasks |
|--------|-------|
| Goal Detail | **FE-PE-013** Chart target vs actual · plans accordion · checklist (strategies) · inline edit · archive button |

### 4.8 Module 4.7 — Performance Tracking (`/p4/tracking`)

> 2 screens.

| Screen | Tasks |
|--------|-------|
| Quick Log | **FE-PE-014** Modal/sticky-bottom quick-log: pick metric · enter value · timestamp default now · submit |
| Tracking Dashboard | **FE-PE-015** Line chart target vs actual · calendar heatmap (year view) · streak counter |

### 4.9 Module 4.8 — AI Suggestions (`/p4/suggestions`)

| Screen | Tasks |
|--------|-------|
| Suggestions List | **FE-PE-016** Sort by relevance score · action chips (Accept · Dismiss · Later) · filter by type · unread badge in nav |

### 4.10 Module 4.9 — Personal Customization (`/p4/customize`)

| Screen | Tasks |
|--------|-------|
| Customization Settings | **FE-PE-017** Avatar uploader · theme toggle (light/dark/auto) · accent color picker · language toggle (VN/EN) |

### 4.11 Personal — Phase 2 acceptance gate

- [ ] All 17 P4 screens shipped
- [ ] ≥10 active personal users (freelancer pilot)
- [ ] ≥3 verticals covered (health/finance/productivity)
- [ ] GDPR delete tested end-to-end (30-day grace + hard delete)

---

## 5. Cross-cutting Shared & Billing

> Components consumed by multiple groups. Frontend tasks here are utility surfaces — the heavy lifting happens at the backend service layer.

### 5.1 Shared (`/shared`, `/mcp`)

| Surface | Route | Phase | Group consumer | Frontend task |
|---------|-------|-------|----------------|---------------|
| Audit Query UI | `/p2/audit` (or `/platform/audit`) | 2 | Platform Tenant + Enterprise User | **FE-SH-101** Search + filter + paginate UI calling `GET /shared/audit/events`; 2-year retention awareness |
| Inline Explainability Widget | (embedded in Decision Detail · Insight Detail · Reports) | 2 | Enterprise User + Studio | **FE-SH-100** Reusable `<ExplainBlock />` component calling `POST /api/v2/shared/explainability/explain` `{decision_id\|insight_id, lang}` → returns SHAP top-3 in Vietnamese; renders factor bars + plain-language sentence; embedded everywhere the user sees an AI decision/output (Shared module 5.3/2) |
| Guardrails Violation Dashboard | `/platform/guardrails` | 2 | Platform Tenant | **FE-SH-102** Violation log table · type chips (PII/jailbreak/profanity) · trend chart · top offending tenants/prompts |
| Agent Configs | `/platform/agents/configs` | 2 | Platform Tenant | **FE-SH-103** Agent role config (Planner/Executor/Critic) · model + prompt + tool catalog |
| Agent Workflows | `/p2/agents/workflows` | 2 | Enterprise User | **FE-SH-104** Pre-built workflow gallery + invoke button calling `POST /shared/agents/workflows/:id/invoke` |
| Agent Sessions | `/p2/agents/sessions` | 2 | Enterprise User | **FE-SH-105** Session list + transcript drawer · cost per session · trace link |
| Agent Tools | `/p2/agents/tools` | 2 | Enterprise User | **FE-SH-106** Tool catalog + per-tool consent toggle |
| MCP Server Console | `/mcp/jsonrpc`, `/mcp/tools`, `/mcp/resources`, `/mcp/prompts`, `/mcp/security`, `/mcp/clients`, `/mcp/analytics` (7 screens) | 2 | Platform Tenant | **FE-SH-107..113** Read-only console: tools list · resources list · prompts library · security policy · client distribution kits · analytics dashboard |
| Compliance Fairness Worker UI | `/platform/compliance/fairness` | 3 | Platform Tenant | **FE-SH-301** Bias audit run trigger + report list |

### 5.2 Billing (`/billing`)

| Surface | Route | Phase | Group consumer | Frontend task |
|---------|-------|-------|----------------|---------------|
| Payment Methods | `/p2/subscription/payment` | 2 | Enterprise User + Personal | **FE-BL-101** Add/remove/default payment method (card · VietQR · Momo · VNPay · ZaloPay) · masked display |
| Invoice List + Detail | `/p2/subscription/invoices` | 2 | Enterprise User | **FE-BL-102** Monthly invoice list · detail drawer with line items · download PDF |
| Auto-Renewal Toggle | (in Subscription page) | 2 | Enterprise User | **FE-BL-103** Toggle + confirmation showing next charge date |
| Cancel & Refund | `/p2/subscription/cancel` | 2 | Enterprise User | **FE-BL-104** Cancel flow with reason survey · refund calculation preview · final confirm |
| E-Invoice Generator | (in Invoice detail) | 3 | Enterprise User | **FE-BL-301** "Issue e-invoice" button per Nghị định 123 · status (issued/cancelled/replaced) · tax authority response |

### 5.3 Cross-cutting i18n (Phase 3)

- **FE-INT-301** Wire `i18next` for EN/JA/KO/ZH (VI already done) — applies to ALL screens
- **FE-INT-302** Branding propagation (logo, colors, accent) across P2 + P4 surfaces; PDF export + email template templating

---

## 6. Cross-screen journeys (E2E flows)

From `Cross-Screen Journeys` sheet (7 named end-to-end flows). Frontend tasks should ensure these journeys remain green via Cypress E2E tests.

| # | Journey | Group | Phase | Screens involved | E2E task |
|---|---------|-------|-------|------------------|----------|
| 1 | Onboarding → First insight | Enterprise User | 1 | 2.0/2 Activation → 2.2 Onboarding → 2.6 Pipeline Wizard (5 steps) → 2.10 Insight Detail | **FE-JR-001** Cypress journey covering activation → first chart in <15 min |
| 2 | Pilot → Upgrade | Platform + Enterprise | 2 | 1.5 Pilot Conversion Pipeline Kanban → 2.19 Upgrade Compare → 2.2 Pilot Upgrade Flow → BL Payment Methods → invoice issued | **FE-JR-002** Pilot D30 conversion E2E |
| 3 | Decision → Action → ROI | Enterprise User | 1+2 | 2.15 Decision Log → 2.16 Decision Detail (Phase 1) → 2.16/2 Override Form (Phase 2) → North Star metric updates | **FE-JR-003** Override drives `is_actioned=true` flow |
| 4 | Workspace lifecycle | Platform Tenant | 1 | 1.1 Workspace Create Wizard → 1.2 Issue Key → Enterprise activates → 1.1 Detail tabs populated | **FE-JR-004** New workspace → first user E2E |
| 5 | Risk → Strategy → Workflow | Enterprise User | 2 | 2.11 Risk Detail → escalate → 2.12 Strategy OKR linked → 2.17 Workflow trigger | **FE-JR-005** Risk-to-action chain |
| 6 | Studio model → Enterprise consumption | Studio + Enterprise | 2 | 3.4 Promote model → 2.16 Decision uses new model → 3.6 Report fan-out summarizes impact | **FE-JR-006** Model deployment to value |
| 7 | Personal goal → Insight → Action | Personal | 2 | 4.5 New Goal → 4.4 Pipeline → 4.8 AI Suggestion → 4.7 Quick Log of action | **FE-JR-007** Personal value loop |

---

## 7. Phase progress summary by group

| Group | Total screens | Phase 1 screens | Phase 2 screens | Phase 3 screens | Phase 1 ✅ | Phase 1 🔄 | Phase 1 ❌ Ghost | Phase 1 ⬜ | FE tasks total |
|-------|---------------|-----------------|-----------------|-----------------|-----------|-----------|-------------------|------------|----------------|
| Platform Tenant (PT) | 34 | 21 | 13 | +4 | 3 | 9 | 4 | 5 | ~30 P1 + ~20 P2 + 4 P3 |
| Enterprise User (EU) | 96 | 25 | 71 | +7 | 12 | 3 | 3 | 7 | ~20 P1 + ~75 P2 + 7 P3 |
| Studio (ST) | 20 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 P1 + 20 P2 |
| Personal (PE) | 17 | 0 | 17 | 0 | 0 | 0 | 0 | 0 | 0 P1 + 17 P2 |
| Shared/Billing (SH/BL) | 49 | 12 | 32 | +5 | 4 | 4 | 2 | 2 | ~5 P1 + ~25 P2 + 5 P3 |
| **TOTAL** | **216** | **58** | **153** | **+16** | **19** | **16** | **9** | **14** | **~250 frontend tasks** |

### 7.1 Critical path to Phase 1 close (frontend perspective)

1. **Unblock Platform Tenant ghosts:** F-010 (PlatformAdmin) backend rebuild → unblocks FE-PT-019..022
2. **Unblock Workspace key flow:** F-009 SecurityConfig fix → unblocks FE-PT-014..018
3. **Unblock Billing:** F-031 cron + F-011 backend → unblocks FE-PT-023..027 + FE-EU-017..019
4. **Unblock Decisions:** F-029 router register → unblocks FE-EU-015..016
5. **Unblock Charts picker:** F-027 render endpoint + F-NEW3 backend → unblocks FE-EU-012..014, FE-EU-007..009
6. **Close P2 user mgmt:** F-015 backend + FE-EU-004..006 → final P1 piece for Enterprise admin UX

### 7.2 Phase 2 launch criteria (frontend)

- All Phase 1 acceptance gates passed
- Studio (P3) screens shipped end-to-end (FE-ST-001..020)
- Personal (P4) screens shipped (FE-PE-001..017)
- KG + Blast Radius + Workflow Builder + Alert Rules functional for ≥3 enterprise customers
- ROI Hybrid billing report displayed for opt-in customers
- MCP Server console (read-only) visible to Platform Tenant

### 7.3 Phase 3 launch criteria (frontend)

- i18n EN/JA/KO/ZH complete for top 20 screens
- Compliance dashboards (SOC2/GDPR/EU AI Act) shipped
- Finance + Logistics analysis screens shipped
- DR + Drift Monitor visible to Platform Tenant

---

## 8. Cross-references

- Backend tracking: `docs/BACKLOG.md` (v3.1 Reconciliation section), `docs/phase_1_execution.md`, `docs/phase_2_execution.md`, `docs/phase_3_execution.md`
- Architecture audit: `docs/ARCHITECTURE_REVIEW.md`
- Detailed feature/leaf data (20 columns per leaf): `docs/product/Feature_Tree_Kaori_AI_v3.1.xlsx` sheets `P1/P2/P3/P4/Shared Leaves Detail`
- Source product docs: `docs/product/Kaori_AI_BRD_v3.0.docx`, `Kaori_AI_PRD_v5.0.docx`, `TAI_LIEU_YEU_CAU_SAN_PHAM_v5.0.docx`
- Frontend code: `frontend/app/(auth|app|platform)`, `frontend/components/{pipeline,charts}`, `frontend/lib/api/client.ts`, `frontend/mocks/`
