# June 2026 Resume Checklist — P15-S9 + P15-S10 + Phase 1.5 path forward

> **Created:** 2026-05-12
> **Trigger to start:** GitHub Actions monthly budget reset (~1st June 2026; 3000 min/month exhausted on PR #179 2026-05-09)
> **Working branch state at freeze:** `feat/p15-s9-d1` HEAD `ce6217d` pushed origin 2026-05-12; contains P15-S9 (8/10 D-pieces) + P15-S10 (8/8 D-pieces) + I1 fix.
> **Local backup tag:** `backup/pre-push-p15-s10-2026-05-12` (snapshot before the bulk push)
> **PR #179:** OPEN, branch up-to-date with origin (CI will trigger when push lands after June reset; today's commits piled silently while budget exhausted).

This doc replaces ad-hoc memory: it is the single canonical resume artefact. When the budget resets, follow sections 1 → 4 in order. Do NOT re-push before doing section 1 (pre-flight drift) — burning re-runs on drift catches is the failure mode that already cost the May budget.

---

## 1. Pre-flight drift refresh BEFORE first re-push

Per memory `feedback_endpoint_addition_drift_checks.md`. P15-S9 added 1 endpoint (NOV monthly + ROI dashboard D7) + 1 webhook (Telegram D5). P15-S10 added 3 endpoints (Gmail/Outlook D1, Calendar D2, RAG D6). All 4 drift artefacts MUST refresh locally before push.

### Step 1.1 — Verify schema snapshot

```powershell
cd "D:\Kaori System"
# P15-S9 D7 added migration 043 (nov_monthly_*); P15-S10 D3 added 044.
# Migration 045 (pageindex_trees) is REFERENCED in P15-S10 docs/code comments
# but the .sql file has NOT been authored yet — PageIndex still stub-only,
# no DB persistence today (zero runtime impact; documentation aspiration).
# When upstream PageIndex wrap lands (S11), author 045 alongside.
type infrastructure\postgres\schema_snapshot.txt | findstr /R "043_ 044_"
# Expect: 043_nov_monthly_*, 044_intervention_outcomes
```

If 043 or 044 missing, regenerate via Flyway dump (path: `scripts/dump_postgres_schema.py` if it exists; else psql `\d+` per service).

### Step 1.2 — Regenerate OpenAPI specs

```powershell
cd "D:\Kaori System"
python scripts\dump_openapi.py ai-orchestrator
python scripts\dump_openapi.py data-pipeline
python scripts\dump_openapi.py notification-service
# Verify check mode (must pass):
python scripts\dump_openapi.py --check
```

### Step 1.3 — Regenerate FE types

```powershell
cd "D:\Kaori System\frontend"
npm run gen:api
# Verify check mode:
node scripts\gen-api-types.mjs --check
```

### Step 1.4 — RouteConfigTest (api-gateway)

Per memory `feedback_auth_service_it_pattern.md`: if any new endpoint, both
- `services/api-gateway/.../RouteConfigTest.java` route list
- `services/auth-service/.../FlywayMigrationIT.java` migration count (4 hardcodes)
- `services/auth-service/.../WorkspaceControllerIT.java` `@MockBean`

must be audited. Endpoints added this batch:
- `/process-mining/connectors/gmail-outlook` (P15-S10 D1)
- `/process-mining/connectors/calendar` (P15-S10 D2)
- `/rag/answer` (P15-S10 D6)
- `/economics/reports/manager-digest` (P15-S9 D7 ROI dashboard)
- `/notifications/telegram/webhook` (P15-S9 D5)

5 endpoints. Audit RouteConfigTest line-by-line. Note: local Win cannot reproduce auth-service IT failures; if Java IT fails in CI, follow memory's 4-hardcode pattern.

### Step 1.5 — Final local pytest sweep

```powershell
cd "D:\Kaori System\services\ai-orchestrator"     ; python -m pytest 2>&1 | Select-Object -Last 3
cd "D:\Kaori System\services\notification-service"; python -m pytest 2>&1 | Select-Object -Last 3
cd "D:\Kaori System\services\data-pipeline"       ; python -m pytest 2>&1 | Select-Object -Last 3
```

Expected counts (frozen 2026-05-12):
- ai-orchestrator: **623** (was 571 at S9 close, +52 from S10 + I1 fix)
- notification-service: **58**
- data-pipeline: **416**

Any drift = local issue, fix before push.

---

## 2. Push procedure (after section 1 passes)

PR #179 already exists pointing at `feat/p15-s9-d1` HEAD `ce6217d`. The branch is already pushed (origin == local at the May 12 freeze). When budget resets, push is a no-op UNLESS pre-flight in §1 changed something — in that case:

```powershell
cd "D:\Kaori System"
git status                                       # confirm any drift fixes are committed
git push origin feat/p15-s9-d1                   # triggers full CI matrix
```

Open the PR in browser to watch CI fire. Expected red count from May freeze: **~10 of 19** (down from 19 thanks to pre-emptive fixes in commits `339e3d8`+`db5eaf3`).

Resume per the failure-class table in `P15-S9_CI_BACKLOG.md` line 96+ for the remaining 10. Likely classes (verify when logs accessible):

| Class | Affected checks | Likely root cause |
|---|---|---|
| docker-smoke build | #14-19 | docker-compose.yml may need updates for ClickHouse + Temporal services (Helm-only paths) |
| schema drift | #5 | confirm §1.1 truly clean |
| arch-guards | #1 | grep for tenant_id span attr in new services (K-19) |
| gitleaks | #4 | check that vault import script doesn't ship credentials in fixtures |
| Java tests | #6 #7 | Java VaultClient deferred → may need @ConditionalOnProperty guard on Vault beans |

---

## 3. Outstanding code-level findings to address PRE-MERGE

Reviewer (anh) will likely ask about these. Either fix before merge, or call out in PR body as "follow-up to land in cleanup commit":

### From P15-S10_REVIEW.md
- ✅ **R1 router whitelist** — fixed `abc9097`
- ✅ **I1 intervention fail-open** — fixed 2026-05-12
- MEDIUM R2 — dead code line in `_apply_whitelist`
- MEDIUM T1 — CHECK constraint on `intervention_outcomes` score columns (migration 044)
- MEDIUM T2 — `intervention_id` empty-string validation
- MEDIUM A1 — population extrapolation guardrail (A/B revenue estimator)
- MEDIUM P2 — schema_version sync comment on `StubPageIndexTreeBuilder`
- 13× LOW — defer to next cleanup pass

### From P15-S9_REVIEW.md
- ✅ **W4 + W7** CRITICAL — fixed `db5eaf3`
- 5× MEDIUM + 12× LOW — defer

**Recommendation:** ship MEDIUM fixes as a single cleanup commit after CI green; do NOT block merge on them.

---

## 4. Deferred deliverables — track for P15-S11 or beyond

| Deferred item | Original sprint | Block reason | Target |
|---|---|---|---|
| **D4a — Postgres CDC connector real impl** (PM-EVT-001) | S9 | scope dropped | P15-S11 |
| **D4c — Zalo metadata connector real impl** (PM-EVT-003) | S9 + S10 | customer Zalo OA account not provisioned | unblocked when Olist gives OA creds |
| **D8 — Silver-tier ClickHouse dual-write cutover** | S9 | needs FPT Cloud cluster live | P15-S11 |
| **D2 — Java `VaultClient.java`** | S9 | Python services use `kaori_vault.py`; Java still on env-var fallback | P15-S11 |
| **PageIndex PyPI wrap (real)** | S10 D7 | currently `StubPageIndexTreeBuilder`; upstream PyPI version uncertain | P15-S11 (or vendor MIT fork) |
| **DocSage** (RAG-DOCSAGE-001/002/003) | always slated for S11 | research-heavy | P15-S11 (RAG addendum batch) |
| **K8s FPT Cloud cluster provisioning** | S9 D1 | account waiting | unblocked by FPT support |
| **Temporal cluster live (TEMPORAL_ENABLE_WORKER=true)** | S9 D3 | scaffold ready, gate flag default false | P15-S11 once K8s ready |

---

## 4a. Auth / RBAC roadmap — user onboarding → role assignment (added 2026-05-16)

**Context:** UAT #14 (workflow activate feedback) ship 2026-05-16 also raised a
follow-up product question — when an HR onboarding workflow approves a new
employee, how does the system assign them the right permissions per
`department × position × subsidiary × branch`? Anh chốt 2026-05-16:
**Hướng A ship trước (RBAC tĩnh), Hướng B note lại deferred (RBAC + ABAC PDP).**

### Hướng A — RBAC tĩnh (ship-fast, Phase 1.5 P15-S11 target)

**Scope** — 1.5-2 ngày dev. Đủ cho pilot demo, không vỡ kiến trúc Phase 2.

```sql
-- migration 060_department_role_templates.sql (TBD; do NOT create yet —
-- waiting for anh's go-ahead on column shape + default seeds).
CREATE TABLE department_role_templates (
    template_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dept_type          dept_type_enum NOT NULL,            -- marketing/sales/cs/warehouse/hr/finance/custom
    seniority_level    TEXT NOT NULL                       -- entry / junior / mid / senior / executive
                       CHECK (seniority_level IN
                              ('entry','junior','mid','senior','executive')),
    default_role       TEXT NOT NULL                       -- maps to enterprise_users.role
                       CHECK (default_role IN
                              ('VIEWER','ANALYST','OPERATOR','MANAGER')),
    description_vi     TEXT,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dept_type, seniority_level)
);

-- Seed defaults (illustrative; refine before ship):
--   marketing × entry|junior  → VIEWER
--   marketing × mid|senior    → ANALYST
--   marketing × executive     → MANAGER
--   sales × entry|junior      → OPERATOR
--   sales × mid|senior        → ANALYST
--   sales × executive         → MANAGER
--   finance × *               → ANALYST (manager required for write paths)
--   hr × *                    → MANAGER  (HR always has admin scope on people)
--   warehouse × entry|junior  → OPERATOR
--   warehouse × mid|senior    → OPERATOR
--   warehouse × executive     → MANAGER
--   customer_service × *      → OPERATOR
--   custom × *                → VIEWER  (forces explicit manager re-grant)
```

**Endpoints to add:**
- `GET  /api/v1/departments/{dept_id}/role-template?seniority=<lvl>` →
  `{ default_role: 'MANAGER', overridable: true }`
- `PATCH /api/v1/enterprise-users/{user_id}/role` (manager scope) — explicit
  override when the template doesn't fit. Audit row mandatory.
- Onboarding approval hook (workflow_step_documents writer): when an approval
  step transitions to APPROVED, derive `default_role` from template +
  `users-onboarding-approval.csv:position_level` column, write to
  `enterprise_users.role`. Side_effect_class = `write_idempotent`.

**Out of scope for A (pushed to B):**
- Per-permission granularity (just "MANAGER vs OPERATOR" — no fine-grained
  `approve_invoices` / `view_payroll` toggles).
- Cross-branch scoping ("user can approve only own branch" — Phase 2).
- Time-bound roles ("temporary acting MANAGER during vacation cover" —
  Phase 2 needs effective-from/effective-to).
- Delegation ("MANAGER can delegate approval to ANALYST for 1 week").

**Migration risk:** Touches `enterprise_users.role` writer paths. Must update
auth-service Java code (`AuthService.login` reads role for JWT). Phase B-2
cutover safe — additive table, role column already exists.

### Hướng B — RBAC + ABAC + PDP (Phase 2 v4 SAD alignment, deferred)

**Scope** — 1-2 sprint. Per `docs/strategic/SAD_SKELETON_V2.md` Phần 6.
Đúng kiến trúc target nhưng không cần cho pilot.

- Policy DSL inline trong YAML (workflow author writes policies):
  ```yaml
  policy: approve_invoice_low_risk
    when: user.dept = 'Finance' AND user.position_level >= 'senior'
          AND target.amount_vnd <= 100_000_000
          AND target.branch = user.branch
    allow: ['approve', 'reject']
  ```
- PDP service (probably extracted from auth-service) returns
  `{ allow: bool, reason: str, policy_id: str, missing_perms: [] }`.
- Policy evaluation on every protected endpoint via FastAPI/Spring middleware.
- ABAC attributes pulled from JWT + request context (target_branch_id,
  amount, ...).
- Audit row per allow/deny decision.

**Why deferred:** lớn, không cần cho 10-15 pilot khách hàng Phase 1.5.
Tracking: BACKLOG_V4 Phase 2 Sprint P2-S13+ (security pillar).

---

## 5. Phase 1.5 remaining plan to draft

Phase 1.5 = 4 sprints (S9-S12). S9 + S10 shipped local; need to plan S11 + S12 next.

### P15-S11 — Week 21-22 (BACKLOG_V4 line 760)
- 2 Enterprise: `NOV-REV-006` variance analysis, `NOV-CST-012` setup cost amortization
- 2 Cross-cutting: `OBS-005` sampling policy, `OBS-020` SLI/SLO dashboards
- 3 RAG addendum: `RAG-DOCSAGE-001/002/003` (full 3-module pipeline)
- Plus the 4 deferred items from §4 above

Estimated 8-9 days dev. Plan doc not yet written.

### P15-S12 — Week 23-24 (BACKLOG_V4 line 787)
- 1 Enterprise: `NOV-RPT-020` CFO summary quarterly report
- 1 Cross-cutting: `OBS-017` SLO-based alerting (error budget burn)

Light sprint; mostly bug fix + acceptance signoff before Phase 2 kickoff.

### Closing Phase 1.5
Once S12 ships + green CI: tag `v4.5-phase1.5-complete`. THEN frontend restructure can start (per anh's preference + CLAUDE.md §2 line 26 paused state).

---

## 6. Storage status snapshot (frozen 2026-05-12)

- **Origin:** `feat/p15-s9-d1` HEAD `ce6217d` (pushed today)
- **Local backup tag:** `backup/pre-push-p15-s10-2026-05-12` → same commit `ce6217d`
- **Tags on disk:** `v1.0-phase1-complete`, `v4.0-phase1-complete`, `backup/pre-push-p15-s10-2026-05-12`
- **Working tree:** clean
- **No stashes**
- **PR #179:** open at https://github.com/yuta9999zn/kaori-system/pull/179

All work is now off-laptop. Even if disk dies, origin holds the full S9 + S10 + I1-fix state.

---

## 7. Quick-resume command sequence (June)

```powershell
# 1. Sync local with any drift the reviewer may have committed
cd "D:\Kaori System"
git fetch --all --tags
git checkout feat/p15-s9-d1
git pull --ff-only origin feat/p15-s9-d1

# 2. Run §1 pre-flight drift refresh

# 3. If drift fixes needed, commit + push
git add -A
git commit -m "fix(p15-s10): pre-flight drift refresh for June CI re-run"
git push origin feat/p15-s9-d1

# 4. Watch CI in browser, debug per §2 failure-class table
gh pr checks 179
```

---

*Source docs cross-ref:*
- `docs/sprint/P15-S9_CI_BACKLOG.md` — original 19 check failure catalog
- `docs/sprint/P15-S9_REVIEW.md` — S9 self-review (2 CRIT fixed, 5 MED + 12 LOW pending)
- `docs/sprint/P15-S10_PLAN.md` — S10 deliverables breakdown
- `docs/sprint/P15-S10_REVIEW.md` — S10 self-review (2 CRIT now FIXED, 5 MED + 13 LOW pending)
- `docs/GAPS_V4.md` — Phase 1.5 progress + deferred items registry
