# Kaori AI — Pilot UAT Runbook

> Version: 1.4 · Phase 2 Sprint 2.1 close-out · 2026-05-04
> Audience: pilot tenant operator + Customer Success driver

This is the 1-pager script the pilot UAT walkthrough follows. Each step references the F-ID it exercises so a failure can be triaged against `BACKLOG.md`. Everything below works against the merged `main` branch (Phase 1 + Sprint 7 + Sprint 8 + Phase 2 Sprint 2.1+2.2).

## What changed in v1.4 (Phase 2 Sprint 2.1 + 2.2 close-out)

10 of the 36 Phase-2 functions ship in this batch. The pilot now has multi-tier analysis, frameworks, decision override + explainability, alert rules, auto-reports, risk management, OKR strategy, and the customer at-risk dashboard — all wired end-to-end.

- **Multi-tier Analysis (F-033)** — `/p2/analysis` hub with 3 tiers: Basic (1 pipeline + N templates, Qwen), Intermediate (2-5 silver/gold sources + 1 framework, Qwen), Advanced (cohort + Claude/GPT-4o after PII mask, MANAGER approval gate when tenant hasn't opted in). Each run lives at `/p2/analysis/runs/[id]` with framework-aware result rendering.
- **Frameworks (F-034)** — `/p2/frameworks` hub + 4 wired pages (SWOT / 6W / 2H / Fishbone-Ishikawa). Each generates structured output via Issue #3 schema validation; history accessible.
- **Cohort Retention (F-035)** — pick "Cohort Retention" template inside `/p2/analysis/basic` for retention heatmap (cohort × M0/M1/M2/...). Engine shipped Phase 1; Sprint 2.1 surfaced it through the multi-tier picker.
- **Decision Override + Explainability (F-036 + F-041)** — `/p2/decisions/[id]` page has both: an Override section to register expert disagreement (Kafka emit to `kaori.feedback.actions` for retrain) and an Explainability section ("Vì sao Kaori quyết định thế?") that lazily generates top-3 factors + Vietnamese narrative + confidence explanation from the audit row. Honest framing — labelled as explanation-from-audit, not real SHAP (model-object persistence is Phase 3).
- **Alert Rules (F-037)** — `/p2/alerts` two tabs (Events + Rules). Quota crossings (≥80% / ≥95%) auto-fire emails through `notification_outbox` with per-tier upsell copy. MANAGER-only mutations.
- **Auto Reports (F-038)** — `/p2/reports/hub` lists generated reports; `/p2/reports/auto` form fires `POST /api/v1/reports/generate` with the built-in monthly-summary template. Distribution form at `/p2/reports/distribution` fans out via outbox. Builder + template library still pending.
- **Risk Management (F-039)** — `/p2/risks` hub: 5×5 heat map + auto-computed severity. Add/edit risks at `/p2/risks/[riskId]`. CSV export with UTF-8 BOM at `/p2/risks/export`.
- **Strategy OKR (F-040)** — `/p2/strategy` hub + `/p2/strategy/okr` Objective/Key Results editor.
- **Customer At-Risk (F-060)** — `/p2/customers/at-risk` bundles North Star tile + filterable customer table + per-row "Đã xử lý" toggle. Closes the half-shut Phase 1 North Star metric.

For the pilot demo: open `/p2/analysis`, run an Intermediate SWOT against 2 silver datasets, then go to `/p2/decisions/[id]` and hit "Tạo giải thích" — the Vietnamese narrative is the headline moment for non-technical viewers.

## What changed in v1.3 (Sprint 8 — Conversational Layer)

Sprint 8 added the right-side **Kaori chat panel** to both portals (P2 Enterprise on every `(app)/*` page; P1 Platform for SUPER_ADMIN/ADMIN/SUPPORT). The panel is curated — six tools v0, AI never writes SQL (new invariant K-16). For the demo: open the floating "Hỏi Kaori" button on `/dashboard`, ask "Top 3 khách hàng đang rủi ro" — assistant invokes `get_top_at_risk_customers`, shows the ToolCallCard, then summarises in Vietnamese. Full UAT script in `docs/uat/CHAT_PANEL.md`.

Pilot caveat: Qwen 2.5 7B (default for the 16 GB laptop posture) sometimes skips tool calling on ambiguous prompts. If a turn returns plain text without a card, re-ask with a more explicit phrasing or escalate to the 14B model on a 32 GB box.

## What changed in v1.2 (Sprint 7 — Pilot Polish)

Sprint 7 closed four PRs (#84 → #87) that took the runbook end-to-end inside the product. No more spreadsheets, no more manual SQL, no more silent emails.

- **F-013 Onboarding** — `/register` 2-step page (renamed from `/onboarding` post-pilot feedback; the old URL still redirects) replaces "CS provisions tenant via API + emails the key + creates the user." Now: paste key → set credentials → land on `/dashboard`.
- **North Star is_actioned toggle** — `/decisions` page has an "Đã xử lý" checkbox on every row, persisted to migration 019's `decision_actions` side table. CS team marks customers in-product (the offline spreadsheet retires).
- **Email actually sends** — F-007 password-reset and F-015 user-invite now route through `notification-service` (was `JavaMailSender` direct + nothing, respectively).
- **F-031 cron health card** — `/platform/billing/overview` surfaces `last_aggregated_at` + `stale_enterprise_count` so SUPER_ADMIN can verify the daily 02:00 ICT cron at a glance.
- **F-012 platform stats endpoint is real** — was MSW-only, now backed by `auth-service` `PlatformController.stats()` aggregating workspaces / users / pipeline runs / Ollama probe.
- **CSV export no longer leaks JWT** — `/decisions` "Xuất CSV" uses `fetch` + Blob + anchor-click pattern (was `?access_token=<JWT>` in URL, K-7 spirit).
- **Visual closeness** — `(app)/` enterprise sidebar now matches the platform redesign (cream `#F5F1EA`, KaoriLockup, gold accent bar). Login → Dashboard is one continuous brand surface.

## UI design notes (v1.1)

The Platform (P1) + auth pages match anh's reference templates in `D:\Kaori Document\frontend template\platform tenant\`:

- **Light cream canvas** (`#FAF7F2`) + sidebar (`#F5F1EA`) — NOT dark.
- **Muted gold accent** `#D4B88A`, hover `#BFA88C`. Buttons use **dark text on gold** (boutique intent).
- **Fonts:** Inter (body) + Playfair Display italic (headings).
- **Login / forgot / reset** share a split-screen brand panel + form with decorative blur orbs and dot pattern.
- **Platform sidebar** is collapsible (240px ↔ 72px), grouped (Chính / Quản lý / Hệ thống), with KaoriLogo lockup, user-menu dropdown, and an active accent bar.
- **Cards / badges / buttons** restyled to soft-shadow + 12px radius per template.

P2 (Enterprise users) UI is unchanged for now — anh's templates for those pages are pending. When they land, run a similar `chore/enterprise-ui-redesign` pass.

---

## ⚠️ Phase 1 limitations to call out before the demo

Read these to the room **before** starting so expectations match what's actually shipped:

1. **North Star metric — half-closed.** Sprint 7 PR D added an in-product `is_actioned` toggle on `/decisions` (migration 019 `decision_actions` side table), so CS team can mark which decisions they actioned without leaving the product. The full per-customer formula
   `SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)`
   still requires Phase 2 F-060 to wire `gold_features.is_actioned` into the dashboard tile and replace the side table with the canonical column. The pilot can compute the metric manually by joining `decision_actions` to the relevant Gold rows.
2. **Pricing source of truth.** Plan quotas + prices shown in the Subscription page come from `CLAUDE.md §10` (PILOT 1M ₫ / ENT BASIC 2M / ENT MID 5M / ENT MAX 8M / ENT ROI 8M+1.5%). These were confirmed canonical 2026-04-27 by product. BRD v3.1 absorbs them on the next revision.
3. **Quota alert email — copy not finalised.** Sprint 7 PR B wired `notification-service` for password-reset and user-invite, both of which use template HTML in `services/notification-service/templates/`. The 80% / 95% billing alerts (F-031) write the alert flags to `enterprise_monthly_billing` and the in-app banner renders, but the **email body** for the quota alert template still uses the F-NEW1 generic copy — Phase 2 F-037 finalises tone + per-tier upsell text. (Password-reset and invite emails are pilot-ready.)
4. **Pilot tenant onboarding step:** during the schema-confirm step (below), map your customer-ID column to the canonical name `customer_external_id`. Without this mapping, the F-032 aggregator will skip the tenant (logged as `gold.aggregate.skip.no_customer_id`). See `docs/specs/MEDALLION_CONTRACT.md` for the canonical Silver schema Gold consumes.

---

## Login

| Portal | URL | Test credentials (MSW dev mode) |
|---|---|---|
| **P1 Platform** (Kaori staff) | `/platform` | A platform-admin row created in `platform_admins` via PR #69+; MFA required for SUPER_ADMIN per F-007 |
| **P2 Enterprise** (tenant) | `/login` | `test@demo.com` / `password123` |
| **New tenant registration** (pilot CS hand-off, Sprint 7 PR D / renamed) | `/register` (legacy `/onboarding` redirects here) | Workspace activation key (any `KAORI-XXXX-XXXX` shape in MSW; real key from `/platform/workspaces/[id]/keys` in prod) |

After login, redirect lands on `/dashboard` (P2) or `/platform` (P1). After successful onboarding, the new MANAGER lands on `/dashboard` directly — no separate login round-trip.

**What to verify:** JWT in `localStorage.kaori.access_token`; gateway forwards `X-Enterprise-ID` + `X-User-Role` to the right service per `RouteConfig.java`.

---

## Pipeline — 5-step wizard (F-017 → F-021 + F-NEW2 SSE)

1. Click **"Pipeline mới"** → `/pipeline/new`.
2. **Step 1 — Upload (F-017).** Drag a CSV from `D:\Kaori Document\datasets\<industry>\` (5 industries pre-downloaded). Verify SHA-256 dedup: re-upload the same file → status reports the existing run, no duplicate row in `pipeline_runs`.
3. **Step 2 — Schema review (F-018).** Map source columns to canonical names. **Critical**: map your customer-ID column to `customer_external_id` (per the limitations callout). Confidence badges + uncertainty flags should render.
4. **Step 3 — Cleaning (F-019).** Select rules (trim whitespace, standardise dates, drop empty rows). Apply → silver_rows populated.
5. **Step 4 — Analysis config (F-020).** Pick at least one template. **Toggle the consent_external_ai checkbox OFF** to confirm K-4 (Qwen-only). Toggle ON to verify external opt-in.
6. **Step 5 — Results (F-021).** Block-based dashboard renders chart + stats + AI narrative.

**Live status (F-NEW2 SSE):** the wizard's status panel updates in real time via `GET /api/v1/pipelines/:id/events` (text/event-stream). To verify the polling fallback, open DevTools → Network → block the events request → status should keep advancing via the 5s polling on `/upload/:run_id/status`.

**Pipeline list (F-022):** `/pipeline` shows all runs with cursor-paginated history, "Tải thêm" button at the bottom for next page.

---

## AI Decision Log (F-029) + manual is_actioned toggle (Sprint 7 PR D)

1. Navigate to `/decisions`.
2. Verify rows for the run you just completed: `column_map` (Step 2), `cleaning_rule` (Step 3), `template_analysis` (Step 5).
3. Type in the search box — debounced 300 ms, then re-queries.
4. Click **"Xuất CSV"** → file downloads via fetch + Blob (no JWT in URL — DevTools Network confirms `Authorization: Bearer` header). Open the CSV in Excel and verify Vietnamese diacritics render correctly (the BOM is the test).
5. **`is_actioned` toggle (Sprint 7 PR D).** Tick the **"Đã xử lý"** checkbox on any row → POST lands in `decision_actions` (migration 019). Refresh → checkbox state persists. Untick → flag flips back. Notes column reserved for the per-row detail panel landing in Phase 2.

---

## Subscription & Quota (F-030 + F-031 alerts)

1. Navigate to `/subscription`.
2. **Tab Quota** — usage / quota / progress bar / EOM forecast (linear projection). Days remaining counter.
3. **Tab Plan** — current plan code + display name + monthly price (₫).
4. **Tab Upgrade** — pick a higher plan + click "Gửi yêu cầu nâng cấp" → row lands in `subscription_change_requests` (status=PENDING). Click again → 409 (only 1 pending allowed).
5. **F-031 alert banner** — to test, run the manual cron trigger:
   ```
   POST /api/v1/platform/billing/aggregate-now    (SUPER_ADMIN)
   ```
   then refresh `/subscription`. If usage ≥ 80% → amber banner. ≥ 95% → red banner.

---

## Settings — consent gate (F-016)

1. Navigate to `/settings`.
2. Toggle **"AI ngoài (Claude / GPT-4o)"** OFF (default) → click "Lưu thay đổi".
3. Run an analysis with `task=insight` requesting external — `engine/llm_router.py` raises `ConsentDeniedError` (K-4 enforced). Visible in service logs as `llm_router.consent_lookup_failed` or `ConsentDeniedError`.
4. Toggle ON, save → re-run analysis → external call now permitted (gateway forwards `consent_external=true` to `llm-gateway`).

---

## User & Role Management (F-015)

1. Navigate to `/users`.
2. Click **"Mời thành viên"** → form opens inline.
3. Email + full name + role → submit. New user appears in the table with `is_active=true`. **Sprint 7 PR B:** invite email is now actually sent via `notification-service` (template `invite.html`) — the new user receives a reset link with 1-hour TTL to set their initial password.
4. Per-row: change role via dropdown → instant PATCH. Toggle status (Power icon) → activate/deactivate. Trash icon → confirm → soft delete (status='deleted').
5. **Min-MANAGER guard:** demote / deactivate / delete the **only** active MANAGER → 409 banner ("Cannot leave enterprise with zero active MANAGERs").

---

## Cross-cutting checks (smoke after each release)

- **Health:** `GET /health` on every service returns 200.
- **Auth filter:** call any `/api/v1/enterprises/me/*` without a JWT → 401 RFC 7807. With expired JWT → 401. With wrong role for a MANAGER-only endpoint → 403.
- **Tenant isolation:** Tenant A's JWT trying to read Tenant B's `pipeline_runs` row → 404 (filter by `enterprise_id` from header, K-12).
- **Audit immutability:** `UPDATE decision_audit_log SET ...` → 0 rows affected (rule blocks). `DELETE` → same.
- **CI:** GitHub Actions on `main` is green (Java + Python + frontend + arch-guards + gitleaks).

---

## Known issues (sign-off acknowledges these)

| F-ID | Issue | Workaround |
|---|---|---|
| F-013 | ~~Onboarding wizard FE not implemented~~ | **Closed in Sprint 7 PR D** — `/register` 2-step page (renamed from `/onboarding` post-pilot) is live; old URL redirects |
| F-027 | No `/api/v1/charts/render` server endpoint | By design — chart rendering is client-side via `frontend/components/charts/chart-registry.tsx` (15 chart kinds + FlexibleChart picker) |
| North Star half-closed | Per-customer `is_actioned` on `gold_features` not yet wired into the dashboard tile | Sprint 7 PR D added the per-decision toggle on `/decisions` (`decision_actions` table); Phase 2 F-060 lands the per-customer canonical column |
| F-031 quota alert email copy | Generic F-NEW1 template, not yet brand-finalised | Phase 2 F-037 finalises tone + per-tier upsell text. Password-reset and invite emails are pilot-ready. |

---

## Useful URLs (dev environment)

| What | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Gateway | http://localhost:8080 |
| Swagger | http://localhost:8082 |
| Kafka UI | http://localhost:8085 |
| Grafana | http://localhost:3001 |
| Ollama | http://localhost:11434 |

Run `scripts/audit-ghost-features.py` after every Phase 1 sign-off pass to confirm 0 unallowlisted Ghost rows.
