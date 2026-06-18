# UAT — F-033 Multi-tier Analysis (PR A + PR B — all 3 tiers + approval)

> **Function:** F-033 — Multi-tier Analysis. PR A shipped basic + intermediate; PR B (this branch) wires advanced tier with external AI dispatch + per-run approval queue + real quota tracking. Multi-workspace memberships still deferred to PR D.
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role can list/read; create allowed for all roles in PR A (MANAGER role gate on advanced tier ships with PR B).
> **Service:** ai-orchestrator (`/api/v1/analysis/*`) + llm-gateway (Issue #3 path)
> **DB:** `analysis_runs` (migration 036 extends Phase-1 table — adds tier/scope/framework/source_ids/workspace_ids/consent_external/approval cols)
> **Owner:** anh (test) + em (standby fix)
> **Prepared:** 2026-05-04

---

## 0. What landed (PR A)

| Surface | Purpose |
|---|---|
| Migration 036 | Extend `analysis_runs` for tier × scope. Backfills wizard rows with `tier='basic', scope='single'`. DROP NOT NULL on `run_id` so intermediate/advanced rows don't need a pipeline anchor. CHECK constraints enforce K-4 (advanced ⇒ consent_external) + K-10 (intermediate ⇒ exactly 1 framework). |
| `GET /api/v1/analysis/sources?layer=silver,gold` | Picker catalogue — distinct silver runs + gold features for the calling tenant |
| `GET /api/v1/analysis/cross-workspaces` | PR A placeholder: returns just the calling workspace. PR B does the real ≥ANALYST lookup |
| `GET /api/v1/analysis/quota/external-ai` | PR A placeholder: returns 0/100 for current month. PR B wires the actual counter |
| `POST /api/v1/analysis/runs` | 202 + `run_id`; spawns `asyncio.create_task` background dispatcher. Body schema branches per `tier` |
| `GET /api/v1/analysis/runs?cursor=&limit=&tier=` | Cursor-paginated list across all tiers; `tier` filter optional |
| `GET /api/v1/analysis/runs/{id}` | Full detail with `overview` (parsed JSON output) + narrative |
| Kafka topic `kaori.analysis.tier.started` | Fired on queue (not on actual LLM start) — payload includes tier/scope/framework |
| Kafka topic `kaori.analysis.tier.completed` | Terminal-state event — payload `{analysis_run_id, enterprise_id, status: done\|error}` |

Background flow:

```
POST /analysis/runs (tier=intermediate, framework=swot, source_ids=[...])
  → INSERT analysis_runs (status=queued, …)            (sync, transactional)
  → emit kaori.analysis.tier.started                   (best-effort, never blocks)
  → 202 + run_id                                       (router returns)
  → asyncio.create_task(run_intermediate(...))         (background)
        → fetch_run + mark_running
        → llm_router.complete_structured(output_schema=swot.template, …)
              → llm-gateway /v1/infer with output_schema field
              → Issue #3 validate + one-shot repair on failure
        → mark_done(overview=parsed, narrative=...)     OR mark_error(...)
        → log_decision (K-6, decision_type='analysis.intermediate')
        → emit kaori.analysis.tier.completed (status=done|error)
```

---

## 1. Pre-flight checks

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8093/health` | `{"status":"ok"}` |
| A2 | `curl -fsS localhost:8095/health` | `{"status":"ok"}` |
| A3 | Migration 036 applied: `SELECT column_name FROM information_schema.columns WHERE table_name='analysis_runs' AND column_name='tier';` | row exists |
| A4 | Backfill default applied: `SELECT DISTINCT tier FROM analysis_runs;` | `'basic'` (only — wizard rows get the default) |
| A5 | Constraints present: `\d+ analysis_runs` in psql | shows `analysis_runs_tier_anchor_check`, `analysis_runs_advanced_consent_check`, `analysis_runs_intermediate_framework_check` |
| A6 | Kafka schemas reachable: `ls infrastructure/kafka/schemas/kaori.analysis.tier.*.json` | both files present |
| A7 | Pilot tenant has ≥ 1 completed pipeline_run with silver_rows (for tier=basic) | non-empty `pipeline_runs` with `status='analysis_complete'` |
| A8 | Pilot tenant has gold_features rows (so the picker shows at least 1 gold source) | `SELECT DISTINCT feature_name FROM gold_features;` ≥ 1 row |

---

## 2. Test scenarios

> All requests: `Authorization: Bearer <pilot JWT>` + `X-Enterprise-ID: <tenant>`. Full-stack mode B from `HAPPY_PATH_SWEEP.md` §0.

### SCN-1 — Sources picker (intermediate tier prep)

| Step | Action | Expected |
|------|--------|----------|
| 1 | `GET /api/v1/analysis/sources` (no layer query) | 200 + `items[]` with both silver + gold entries; `items[].layer ∈ {silver,gold}` |
| 2 | `GET /api/v1/analysis/sources?layer=silver` | Only `layer="silver"` entries |
| 3 | `GET /api/v1/analysis/sources?layer=bronze` | 400 RFC 7807 — `detail: "layer must be 'silver', 'gold', or both"` |
| 4 | Cross-tenant inspection: log in as enterprise B, hit endpoint | Empty list / only B's data — RLS enforces |

### SCN-2 — Basic tier (delegates to wizard runner)

| Step | Action | Expected |
|------|--------|----------|
| 1 | `POST /api/v1/analysis/runs` body `{tier: "basic", pipeline_run_id: "<existing>", templates: ["summary_stats", "rfm_churn"], question: "Khách rời nhiều nhất ở đâu?"}` | **202** + `{run_id, tier: "basic", status: "queued"}` |
| 2 | Inspect `analysis_runs`: `SELECT tier, scope, status, templates FROM analysis_runs WHERE id='<run_id>';` | `tier=basic, scope=single, status=queued|running|done, templates={summary_stats,rfm_churn}` |
| 3 | Wait 10–30s, `GET /api/v1/analysis/runs/{run_id}` | `status=done`; `overview` carries cross-template narrative; `templates` echoes back |
| 4 | Inspect Kafka: subscribe `kaori.analysis.tier.started` topic from Kafka UI | one message `{tier: "basic", scope: "single", framework: null}` for this run |
| 5 | Subscribe `kaori.analysis.tier.completed` after step 3 | one message `{status: "done"}` |
| 6 | `POST /analysis/runs` with empty `templates: []` | 400 RFC 7807 — `templates is required for tier='basic'` |
| 7 | `POST /analysis/runs` with `templates` length 11 | 400 — `at most 10 templates per basic run` |
| 8 | `POST /analysis/runs` body without `pipeline_run_id` | 400 — `pipeline_run_id is required for tier='basic'` |

### SCN-3 — Intermediate tier (multi-source + framework)

| Step | Action | Expected |
|------|--------|----------|
| 1 | `POST /api/v1/analysis/runs` body `{tier: "intermediate", framework: "swot", question: "Mảng bán lẻ Q3 mạnh ở đâu?", source_ids: [{layer: "silver", id: "<run_id>", label: "rfm_q3"}, {layer: "gold", id: "revenue_at_risk"}]}` | **202** + `{run_id, tier: "intermediate"}` |
| 2 | Wait 10–30s (Qwen 14B), `GET /api/v1/analysis/runs/{run_id}` | `status=done`; `overview` matches SWOT schema (4 quadrants + summary); `narrative` is the SWOT summary string; `framework=swot` |
| 3 | Inspect `decision_audit_log`: `SELECT decision_type, method, llm_provider FROM decision_audit_log ORDER BY created_at DESC LIMIT 1;` | `analysis.intermediate, llm, qwen-internal` (consent_external=false default) |
| 4 | Try `framework: "5why"` | 400 — `unknown framework '5why' (allowed: ['2h','6w','fishbone','swot'])` |
| 5 | Try 1 source only | 400 — `source_ids must contain at least 2 sources for tier='intermediate'` |
| 6 | Try 6 sources | 400 — `source_ids must contain 2 to 5 items` |
| 7 | Try `source_ids: [{layer: "bronze", id: "x"}]` | 400 — `layer must be 'silver' or 'gold'` |
| 8 | Try `question: "    "` (whitespace) | 400 — `question is required for tier='intermediate'` |
| 9 | Try other 3 frameworks (`6w`, `2h`, `fishbone`) | each completes with the framework's specific output schema |
| 10 | Inspect Kafka `kaori.analysis.tier.started`: payload | `tier: intermediate, scope: multi, framework: swot` |

### SCN-4 — Advanced tier (PR B end-to-end)

#### SCN-4a — Tenant has NOT opted in (approval required)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Confirm tenant flag: `SELECT consent_external_ai FROM tenant_settings WHERE enterprise_id=$1;` | `false` (default) |
| 2 | `POST /api/v1/analysis/runs` body `{tier:"advanced", framework:"swot", question:"...", source_ids:[2 items], consent_external:true}` | **202** with `{"run_id": "<uuid>", "tier": "advanced", "status": "awaiting_approval"}` |
| 3 | `GET /api/v1/analysis/runs/{id}` immediately | `status='queued'`, `requires_approval=true`, `approved_at=null` |
| 4 | Wait 30s | Status STILL `queued`, no `started_at` — dispatcher correctly short-circuited |
| 5 | Hit `POST /api/v1/analysis/runs/{id}/approve` with `X-Role: VIEWER` | **403** RFC 7807 — `Only MANAGER can approve advanced runs` |
| 6 | Hit `/approve` with `X-Role: MANAGER` + `X-User-Id: <uuid>` | **200** with full RunDetail; `approved_by` + `approved_at` populated |
| 7 | Wait 10-30s, re-`GET` | `status='done'`, `overview` populated, `narrative` set |
| 8 | Inspect `decision_audit_log` | row `decision_type='analysis.advanced.approved'` (audit row from approve flow) + row `decision_type='analysis.advanced'` `llm_provider='external'` (dispatch row) |

#### SCN-4b — Tenant HAS opted in (direct dispatch)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Set tenant flag: `UPDATE tenant_settings SET consent_external_ai=true WHERE enterprise_id=$1;` | row updated |
| 2 | POST advanced run with same body | 202 with `status='queued'` (NOT `awaiting_approval`) |
| 3 | `requires_approval` in detail | `false` |
| 4 | Wait 10-30s | Status moves `queued → running → done` without manual approve |
| 5 | Quota counter check: `GET /api/v1/analysis/quota/external-ai` | `external_calls_used` increments by ≥1 (counts the row we just dispatched) |

#### SCN-4c — Validation gates

| Step | Action | Expected |
|------|--------|----------|
| 1 | `POST /analysis/runs` advanced with `consent_external: false` | 400 — `tier='advanced' requires consent_external=true (K-4)` |
| 2 | Cross-workspaces endpoint with `X-Role: VIEWER` | 200 + 1 item but `can_include=false` (FE blocks the checkbox) |
| 3 | Cross-workspaces with `X-Role: MANAGER` or `ANALYST` | 200 + 1 item with `can_include=true` |

### SCN-5 — List + cursor pagination

| Step | Action | Expected |
|------|--------|----------|
| 1 | `GET /api/v1/analysis/runs?limit=2` after running SCN-2 + SCN-3 | items length ≤ 2; `next_cursor` non-null if more rows exist |
| 2 | Pass `next_cursor` back via `?cursor=<...>&limit=2` | next page; never re-includes a row from page 1 |
| 3 | `GET /api/v1/analysis/runs?tier=basic` | only basic-tier rows |
| 4 | `GET /api/v1/analysis/runs?tier=intermediate` | only intermediate rows |
| 5 | `?cursor=invalid` | 400 RFC 7807 — `invalid cursor (expected '<iso8601>|<uuid>')` |
| 6 | List endpoint payload | does NOT include `overview` / `config` / `templates` (small payload) |

### SCN-6 — RLS + K-12 isolation

| # | Action | Expected |
|---|---|---|
| 1 | Login enterprise A, create a run | succeeds |
| 2 | Login enterprise B, `GET /api/v1/analysis/runs/{A's run_id}` | **404** — RLS prunes the row, falls out of the SELECT |
| 3 | `?enterprise_id=<other tenant>` query param shenanigans | ignored; JWT enterprise_id wins (K-12) |

### SCN-7 — Quota placeholder (PR A behavior)

| # | Action | Expected |
|---|---|---|
| 1 | `GET /api/v1/analysis/quota/external-ai` | 200 with `{external_calls_used: 0, external_calls_limit: 100, period: "YYYY-MM"}` |
| 2 | Spam intermediate runs (consent_external=false) | quota counter doesn't move (PR A doesn't track) |
| 3 | After PR B ships | this counter will reflect actual external-AI calls |

### SCN-8 — Cross-workspaces placeholder (PR A behavior)

| # | Action | Expected |
|---|---|---|
| 1 | `GET /api/v1/analysis/cross-workspaces` | 200 with single-item list = current workspace; `member_role: "MANAGER"` |
| 2 | After PR B | actual lookup of `enterprise_users` for ≥ANALYST workspaces |

---

## 3. K-rule probes

| K | Probe | Expected |
|---|---|---|
| K-3 | Force consent_external=true (workaround direct curl) on intermediate | LLM call goes to llm-gateway with `consent_external=true` flag in body; consumer side picks Claude/GPT-4o |
| K-4 | DB invariant: try `INSERT INTO analysis_runs (tier, consent_external, …) VALUES ('advanced', false, …);` directly | constraint `analysis_runs_advanced_consent_check` rejects |
| K-6 | After successful intermediate run | `decision_audit_log` row with `decision_type='analysis.intermediate'`, `subject=run_id`, `chosen_value=framework`, `method='llm'`, `llm_provider IN ('qwen-internal','external')` |
| K-10 | Try INSERT with `tier='intermediate', framework=NULL` directly | constraint `analysis_runs_intermediate_framework_check` rejects |
| K-12 | Pass `?enterprise_id=…` to any of the 5 endpoints | ignored; JWT enterprise_id used |

---

## 4. Known gaps (deferred to PR B / PR C)

- ~~**Advanced tier engine**~~ → **Closed by PR B** — `queue_advanced` / `run_advanced` dispatch via llm_router with `consent_external=true` (PII mask K-5 happens at the gateway). `requires_approval` derived from `tenant_settings.consent_external_ai` flag (workspace-level opt-in). `POST /runs/{id}/approve` with MANAGER role gate.
- **Multi-workspace memberships** — Phase 1 `enterprise_users` schema is `UNIQUE(enterprise_id, email)` so 1 user belongs to exactly 1 enterprise. Cross-workspaces endpoint returns just the calling workspace until PR D ships a `user_workspace_memberships` join table.
- ~~**Real `quota/external-ai` accounting**~~ → **Closed by PR B** — counts `decision_audit_log` rows with `llm_provider != 'qwen-internal'` since the first of the calendar month. Limit hardcoded to 100 until F-067 wires per-plan quotas.
- ~~**FE wiring (templates 35/36/37/38)**~~ → **Closed by PR C** — hub renders recent runs from `/api/v1/analysis/runs`; basic + intermediate forms POST live; advanced form surfaces the 501 BE response as an RFC-7807 banner; new `/p2/analysis/runs/[id]` result page polls until terminal and renders SWOT/6W/2H/Fishbone shapes (basic tier falls back to JSON tree). MSW handlers added so dev mode works without llm-gateway.
- **Issue #3 `was_repaired` audit flag** — `analysis_runs.output_schema_repaired` column exists but stays NULL in PR A because `llm_router.complete_structured` doesn't surface the gateway's repair flag through its return signature. PR B can promote the flag if pilot needs the audit channel.

---

## 5. Rollback

If PR A regresses pilot:

1. Revert the `feat/multi-tier-analysis-f033` PR — services restart picks up clean code.
2. Migration 036 stays applied (rollback would lose any FE-issued runs). The wizard still works because it uses default values for the new columns.
3. To fully revert the schema (last-resort), drop the new columns:
   ```sql
   ALTER TABLE analysis_runs
       DROP COLUMN tier, DROP COLUMN scope, DROP COLUMN question,
       DROP COLUMN framework, DROP COLUMN source_ids, DROP COLUMN workspace_ids,
       DROP COLUMN consent_external, DROP COLUMN requires_approval,
       DROP COLUMN approved_by, DROP COLUMN approved_at,
       DROP COLUMN output_schema_repaired, DROP COLUMN narrative,
       DROP COLUMN created_by_user;
   ALTER TABLE analysis_runs ALTER COLUMN run_id SET NOT NULL;
   ```
   Do this only after confirming `analysis_runs.tier IN ('intermediate','advanced')` rows are not needed.

---

*Last updated: 2026-05-04 with PR A.*
