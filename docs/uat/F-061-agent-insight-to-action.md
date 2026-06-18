# F-061 — Agent Framework UAT — `insight-to-action` workflow

> **Feature:** F-061 (Sprint 2.6, Phase 2)
> **Spec:** `docs/specs/AGENT_FRAMEWORK.md`
> **Pre-req:** BE stack up (`docker compose up -d`), Olist seed loaded
> **Test surface:** BE only (PR1 is BE-only; FE follow-up later). Pilot tests via `curl`.

---

## SCN-1 — Dry-run a workflow against the Olist seed

**Setup:** the Olist seed loaded ≥1 `decision_audit_log` row at
`scripts/seed-pilot-olist.py`. Pick one as the insight target:

```powershell
docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -c `
  "SELECT decision_id FROM decision_audit_log WHERE enterprise_id = '00000000-0000-0000-0001-000000011577' LIMIT 1;"
```

Note the UUID returned. (Or paste any UUID — the planner just needs
the shape; v0 doesn't pre-fetch the insight.)

**Get a fresh JWT for `cs@olist.local`:**

```powershell
$token = (Invoke-RestMethod -Method POST -Uri http://localhost:8080/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"cs@olist.local","password":"Pilot@2026"}').accessToken
```

**Hit the agent endpoint:**

```powershell
$body = @{
  workflow_id = "insight-to-action"
  input       = @{ insight_id = "<paste-uuid-from-step-above>" }
  dry_run     = $true
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8080/api/v1/shared/agents/sessions" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 10
```

**Expected (✅ pass):**
- HTTP 200
- `status: "completed"` OR `status: "escalated"` (depending on what
  the local Qwen produces — both are valid v0 outcomes; failures =
  bug)
- `dry_run: true`
- `plan.steps[]` non-empty, every `tool_name` in the workflow's
  allowlist (4 tools max — see spec §3)
- `transcripts[]` has at least 3 rows: 1 planner + ≥1 executor + 1 critic
- Every executor row with `tool_name ∈ {draft_followup_email, mark_customer_for_review}` has `tool_result.side_effect_fired = false`
- `decision_audit_log` query AFTER the run shows NO new rows tagged `agent.*` (because dry_run=true skipped writes)

```powershell
docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -c `
  "SELECT decision_type, subject FROM decision_audit_log WHERE decision_type LIKE 'agent.%' ORDER BY created_at DESC LIMIT 5;"
```

---

## SCN-2 — Real run (dry_run=false) writes audit rows

Same as SCN-1 but with `dry_run=$false`. Expected delta:

- `plan.steps[]` includes ≥1 step calling `draft_followup_email` or `mark_customer_for_review`
- That step's `tool_result.side_effect_fired = true` and contains an `audit_decision_id` UUID
- AFTER the run, `decision_audit_log` shows new rows tagged `agent.draft_email` or `agent.flag_for_review`
- `/p2/decisions` (FE) lists the new entries (manual click-through verification)

---

## SCN-3 — Unknown workflow_id returns 404 RFC 7807

```powershell
$body = @{ workflow_id = "does-not-exist"; input = @{} } | ConvertTo-Json
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8080/api/v1/shared/agents/sessions" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body
```

**Expected:** HTTP 404; response body is `application/problem+json`
with `detail` mentioning the unknown id AND listing available workflow
ids ("Có sẵn: insight-to-action").

---

## SCN-4 — Bad input shape returns 400 RFC 7807

Send `input` with an extra disallowed key (workflow's `additionalProperties: false`):

```powershell
$body = @{
  workflow_id = "insight-to-action"
  input = @{ insight_id = "11111111-1111-1111-1111-111111111111"; enterprise_id = "deadbeef" }
} | ConvertTo-Json
```

**Expected:** HTTP 400; `detail` mentions `enterprise_id` (forbidden).

Send `input` with non-UUID `insight_id`:

```powershell
$body = @{ workflow_id = "insight-to-action"; input = @{ insight_id = "not-a-uuid" } } | ConvertTo-Json
```

**Expected:** HTTP 400; `detail` mentions UUID format.

---

## SCN-5 — Path-based workflow_id wins over body

```powershell
$body = @{
  workflow_id = "this-id-is-ignored"
  input       = @{ insight_id = "11111111-1111-1111-1111-111111111111" }
  dry_run     = $true
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8080/api/v1/shared/agents/workflows/insight-to-action/invoke" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType "application/json" `
  -Body $body
```

**Expected:** runs the `insight-to-action` workflow (path wins);
response `workflow_id` = `"insight-to-action"`.

---

## SCN-6 — Tenant isolation (K-12)

Two distinct tenants must never see each other's sessions/transcripts.
Trigger SCN-1 as `cs@olist.local` (tenant A), then check from a tenant
B JWT — the session shouldn't be visible (RLS enforces).

This is implicit in the migration's RLS policy; no follow-up endpoint
in PR1 to read sessions, so v0 verification is via direct DB query
with the wrong tenant GUC:

```powershell
docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -c `
  "SET LOCAL app.enterprise_id = '00000000-0000-0000-0000-000000000000'; SELECT COUNT(*) FROM agent_sessions;"
```

**Expected:** `count = 0` (RLS hides the Olist tenant's rows).

---

## SCN-7 — Token budget cap forces failure (engineering check)

Hard to reproduce manually with Qwen local (each call is ~500 tokens).
Verified by unit test
`tests/test_agent_orchestrator.py::test_orchestrator_max_replan_forces_escalation`
covering the same cap-and-bail logic.

---

## Acceptance criteria

| # | Criterion | Pass iff |
|---|-----------|----------|
| 1 | Endpoint reachable through gateway | SCN-1 returns 200 |
| 2 | Dry-run = no DB writes | SCN-1 audit query empty for `agent.*` types |
| 3 | Real run = DB writes happen | SCN-2 audit query shows new rows |
| 4 | Workflow lookup error → 404 RFC 7807 | SCN-3 returns 404 with `application/problem+json` |
| 5 | Input validation error → 400 RFC 7807 | SCN-4 returns 400 with format-specific detail |
| 6 | Path-based variant works | SCN-5 returns 200 with workflow_id=path value |
| 7 | RLS isolates per-tenant | SCN-6 cross-tenant count=0 |
| 8 | All 27 unit tests green | `pytest tests/test_agent_*.py` all pass |
