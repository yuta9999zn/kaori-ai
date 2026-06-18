# UAT — F-008 Workspace Management CRUD

> **Function:** F-008 — Workspace Management CRUD
> **Portal:** P1 Platform Manager (`/p1/workspaces`)
> **Roles allowed:** `SUPER_ADMIN`, `ADMIN`
> **Service:** auth-service (`/api/v1/platform/workspaces`)
> **DB tables:** `workspaces`, `enterprises`, `subscription_plans`
> **Owner:** Platform Operations team
> **Prepared:** 2026-04-25

---

## 1. Business Context

The Platform Manager portal lets Kaori staff create, list, update and
deactivate **workspaces** — the top-level tenant container that every
Enterprise and its users live under.

A workspace binds to:

- a **name** (shown everywhere in the P1/P2 UI),
- a **subscription plan** (`PILOT`, `ENT_BASIC`, `ENT_MID`, `ENT_MAX`, `ENT_ROI`),
- optional **industry** (used to seed the first enterprise record), and
- a **status** (`active` / `suspended` / `inactive`).

Deactivation is always **soft** — no row is ever deleted, so billing,
audit and decision-log histories stay intact (K-2, K-9, K-11).

---

## 2. Pre-conditions

| # | Pre-condition |
|---|---------------|
| P1 | Tester is logged in as `SUPER_ADMIN` with MFA verified. |
| P2 | At least one `subscription_plans` row exists (see `007_seed.sql` — seeded on infra bootstrap). |
| P3 | auth-service (8091) and api-gateway (8080) are healthy (`/actuator/health` = UP). |
| P4 | Browser dev tools Network tab open to inspect response codes and payloads. |

---

## 3. Test Scenarios

### SCN-1 — Create a new workspace (happy path)

**Goal:** Onboard a new enterprise customer ("Acme Ltd") on the MID plan.

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Navigate to `/p1/workspaces`. | List page renders with existing workspaces. |
| 2 | Click **New workspace**. | Modal opens with `name`, `plan_code`, `industry` fields. |
| 3 | Enter `name = "Acme Ltd"`, `plan_code = "ENT_MID"`, `industry = "Retail"`. | Submit button enables. |
| 4 | Click **Create**. | Toast "Workspace created"; new row appears on top of the list with `status=active`. |
| 5 | Network tab: inspect `POST /api/v1/platform/workspaces`. | Status **201 Created**; body: `{ data: { workspace_id, name, plan_code: "ENT_MID", status: "active", created_at } }`. |

**Edge cases:**

- **E1 — missing plan_code** → button disabled; if bypassed via API, backend returns **400** with body `{ title: "...", status: 400 }`.
- **E2 — plan_code = "FREE_TIER_123"** (not in `subscription_plans`) → **400** from service with `title: "Invalid plan_code"`. UI shows "Plan does not exist" under the field.
- **E3 — `name` has leading/trailing whitespace** → backend trims before persisting; the listed workspace shows the trimmed name.
- **E4 — duplicate workspace name on same day** → permitted; workspace uniqueness is by `workspace_id`, not name.
- **E5 — `industry` omitted** → **201**; workspace is created without seeding an enterprise row. Industry can be set later via F-016 Enterprise Settings.

---

### SCN-2 — Update plan (upgrade / downgrade)

**Goal:** Promote "Acme Ltd" from `ENT_MID` to `ENT_MAX` after a successful pilot.

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | On `/p1/workspaces`, click the ⋯ menu on the Acme row → **Change plan**. | Dialog shows current plan and a dropdown of eligible plans. |
| 2 | Select `ENT_MAX`. Confirm. | Toast "Plan updated". Row reflects the new plan. Quota displayed becomes 10,000. |
| 3 | Network tab: `PATCH /api/v1/platform/workspaces/{id}` body `{ "plan_code": "ENT_MAX" }`. | **200 OK**; `data.plan_code = "ENT_MAX"`; `updated_at` changed. |
| 4 | Refresh page. | Plan persists — reading from DB, not cache. |

**Edge cases:**

- **E1 — empty PATCH body `{}`** → backend returns **400** `title: "Empty update"`. UI prevents submission.
- **E2 — downgrade from MAX → PILOT while current month's unique-customer count > 500** → service allows the plan change but flags **quota overage** (visible in F-011 Billing Monitor). Test: after downgrade, `GET /api/v1/platform/billing/workspaces` shows `overage_count > 0` for this workspace.
- **E3 — invalid UUID in path** → **400** `title: "Invalid workspace ID"`.
- **E4 — workspace does not exist (random UUID)** → **404** `title: "Workspace not found"`.

---

### SCN-3 — Deactivate a workspace (soft delete)

**Goal:** Deactivate a workspace that has churned. Data must be preserved.

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | On `/p1/workspaces`, locate the workspace. | Visible with `status=active`. |
| 2 | ⋯ menu → **Deactivate**. Confirm dialog ("The workspace will be deactivated but data preserved."). | Row status flips to `inactive` and is greyed. |
| 3 | Network tab: `DELETE /api/v1/platform/workspaces/{id}`. | **200 OK**; body: `{ data: { workspace_id, status: "inactive" } }`. |
| 4 | Open PostgreSQL and `SELECT status FROM workspaces WHERE workspace_id = '…'`. | Row still exists; `status='inactive'`. No `DELETE` was issued. |
| 5 | Try to log in as any user under that workspace (`/p2/login`). | Login rejected with **423 Locked** / 403 — users of an inactive workspace cannot authenticate. |
| 6 | `GET /api/v1/platform/workspaces` (default filter). | Deactivated workspace may still appear (filter by status is client-side); UI shows a greyed row tagged "Inactive". |

**Edge cases:**

- **E1 — deactivating an already inactive workspace** → **200** with same body; idempotent from the user's perspective.
- **E2 — deactivating a workspace that never existed** → **404**.
- **E3 — invalid UUID** → **400**.
- **E4 — audit trail** → the action is logged in `decision_audit_log` per K-6 and surfaced in the P1 Audit view.

---

### SCN-4 — Pagination and large lists

**Goal:** Verify the list page behaves under realistic data volumes (>50 workspaces).

| Step | Action | Expected result |
|------|--------|-----------------|
| 1 | Seed 120 workspaces in test DB (use `scripts/seed_workspaces.sql` or UI repeat). | 120 rows exist. |
| 2 | Open `/p1/workspaces`. | First page shows 50 rows newest-first. "Load more" button visible. |
| 3 | Network tab: initial `GET /api/v1/platform/workspaces`. | **200**; `data.length = 50`; `meta.cursor` is a non-null opaque string; `meta.total` = 120. |
| 4 | Click **Load more**. | Next 50 rows append. Request: `GET /api/v1/platform/workspaces?cursor={prev_cursor}&limit=50`. |
| 5 | Keep clicking until exhausted. | Third request returns the final 20 rows; `meta.cursor = null`. Button hides. |
| 6 | Set URL param `?limit=200`. | **200**; returns up to 200 rows. |
| 7 | Set `?limit=1000` via API directly. | **400**; `title: "Invalid limit"`; `detail` mentions the 500 max. |
| 8 | Set `?limit=0` via API directly. | **400**. |

**Edge cases:**

- **E1 — empty list** (fresh DB) → **200** with `data: []`, `meta.total: 0`, `meta.cursor: null`. UI shows the "No workspaces yet — create your first" empty-state card.
- **E2 — cursor tampered with** (user hand-edits query string) → service must reject with **400** (details on tracker invariant). This UAT flags it for backend hardening in T-F008-02.
- **E3 — `limit` not a number** (`?limit=abc`) → **400** from Spring param binding.

---

## 4. Cross-cutting Expectations

All endpoints must satisfy:

| # | Check |
|---|-------|
| X1 | **Response envelope** is `{ data, meta }` on success and RFC 7807 Problem Details on error (K-14). |
| X2 | **Content-Type** is `application/json` (or `application/problem+json` on errors). |
| X3 | `tenant_id` / `workspace_id` **never accepted from query string** for write endpoints (K-12). |
| X4 | **Idempotency-Key** header on `POST` should de-duplicate retries within 24h (K-13) — if absent, the POST is processed normally. |
| X5 | **Authorization**: `SUPER_ADMIN` or `ADMIN` only. A `MANAGER` or unauthenticated caller receives **403** from the gateway before reaching auth-service. |
| X6 | Every mutating call produces an audit entry visible in `decision_audit_log` (K-6). |
| X7 | **Logging**: each create/update/deactivate emits a structured log line with `workspace_id` for ops traceability. |
| X8 | Response times under light load (<10 rps) should return within **300 ms p95**. |

---

## 5. Exit Criteria

- All scenarios **SCN-1 … SCN-4** pass including their edge cases.
- All cross-cutting expectations **X1 … X8** verified at least once.
- Regression: the existing P1 Private Key flow (F-009) and Platform Admin CRUD (F-010) still work.
- Sign-off recorded in the sprint demo notes with the tester's name and date.

---

## 6. Sign-off

| Role | Name | Date | Result (PASS / FAIL) |
|------|------|------|----------------------|
| Tester (QA) |  |  |  |
| Platform PM |  |  |  |
| Backend Lead |  |  |  |
