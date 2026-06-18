# EU AI Act Layer 3 — K-26 Post-market Monitoring (slice 3) — Design

> **Status:** design, pending approval → writing-plans
> **Date:** 2026-06-04
> **Part of:** EU AI Act Layer 3, ADR-0041. Slice 3 of 4 (K-22 #347, K-23 #348, K-24 #349 done).
> **Branch:** `feat/eu-ai-act-k26-monitoring`, off `main` (independent — uses only signals already on main: ai_decision_audit, workflow_runs).

## Goal

Provide the EU AI Act **post-market monitoring** surface (Art 72) and the **serious-incident register** (Art 73): a place to record incidents (with severity) and a single-pane summary that aggregates current health signals. Mirrors the existing `/admin/dlq` console pattern (admin-gated, tenant-scoped).

## Decisions (confirmed with anh, 2026-06-04)

1. **Scope:** register + monitoring summary, **record-only** (no auto-detection job this slice). A reusable `record_incident(...)` helper is the seam future auto-hooks/scanning call.
2. **Severity:** 4 levels `low | medium | high | serious`; `serious` = Art 73-reportable (substantial harm / cross-tenant leak / wrong actioned high-risk decision).
3. **Out of scope (YAGNI):** external regulator reporting transport (Art 73 submission — needs EU entity); auto-detection scanning job + thresholds; FE incident dashboard (contract only).

## Architecture

Admin router `routers/incidents.py` (no FastAPI prefix; reached under the same edge prefix as `/admin/dlq`), role-gated `SUPER_ADMIN`/`ADMIN` (reuse the `_require_admin` pattern from `dlq_console.py`), tenant-scoped via `acquire_for_tenant` (K-1/K-12).

### Data model — migration `ai_incident`
- PK `incident_id UUID DEFAULT gen_uuid_v7()` (K-21); `public_ref TEXT DEFAULT gen_ulid()` UNIQUE.
- `enterprise_id UUID NOT NULL`.
- `incident_type VARCHAR(48) NOT NULL` (free-ish category, e.g. `wrong_decision`, `data_leak`, `model_drift`, `pipeline_failure`, `other`).
- `severity VARCHAR(12) NOT NULL CHECK (low|medium|high|serious)`.
- `status VARCHAR(16) NOT NULL DEFAULT 'open' CHECK (open|investigating|resolved)`.
- `title VARCHAR(200) NOT NULL`; `description TEXT`.
- nullable refs: `decision_id UUID`, `run_id UUID`, `workflow_id UUID`.
- `detail JSONB NOT NULL DEFAULT '{}'`.
- `reported_by UUID`; `reported_at TIMESTAMPTZ DEFAULT NOW()`; `resolved_at TIMESTAMPTZ`.
- Indexes: `(enterprise_id, status, reported_at DESC)`, `(enterprise_id, severity)`.
- RLS K-1 (mirror mig 130/134); GRANT to kaori_app. Additive, K-21-compliant.

### Pure logic — `reasoning/incident_rules.py`
- `SEVERITIES = ("low","medium","high","serious")`, `INCIDENT_STATUSES = ("open","investigating","resolved")`.
- `validate_severity(s) -> str` / `validate_status(s) -> str` (trim+lower, raise ValueError on unknown). Unit-testable, no I/O.

### Endpoints (`routers/incidents.py`)
- `POST /admin/incidents` — body `{incident_type, severity, title, description?, decision_id?, run_id?, workflow_id?, detail?}` → validate severity → INSERT (status='open') → K-6 audit (`task_kind='incident_recorded'`) → return the row. Calls the shared `record_incident(...)` helper.
- `GET /admin/incidents?status=&severity=&limit=` — list, tenant-scoped, newest first.
- `PATCH /admin/incidents/{incident_id}` — body `{status, resolution_note?}` → validate status → update status (+ `resolved_at=NOW()` when status='resolved'). (Minimal lifecycle so an incident can be closed.)
- `GET /admin/incidents/summary` — the Art 72 monitoring pane:
  - `open_incidents_by_severity`: counts of non-resolved incidents grouped by severity.
  - `failed_runs_recent`: count of `workflow_runs` with status='failed' in the window.
  - `low_confidence_decisions_recent`: count of `ai_decision_audit` rows with `confidence < threshold` in the window.
  - `window_days` (default 7) + `low_confidence_threshold` (default 0.5) echoed back.
  (All tenant-scoped. No join to `ai_use_risk_register` — keeps K-26 independent of Layer 2.)

### `record_incident(...)` helper
A module-level async function (in `routers/incidents.py` or a small `shared/incidents.py`) that does the validated INSERT + K-6 audit and returns the new incident row. The POST endpoint calls it; future auto-hooks (other slices) call the same function — single write path.

## Error handling
- Invalid severity/status → 422 (`HTTPException`, str detail → RFC 7807 via global handler).
- Non-admin role → 403 (`_require_admin`).
- PATCH on missing incident → 404.
- K-6 audit wrapped (audit failure must not break recording).

## Testing
- **Unit (pure):** `validate_severity`/`validate_status` accept the valid sets, normalise case, raise on unknown; `SEVERITIES` exact tuple.
- **Router:** POST records (201, severity persisted, audit awaited); POST bad severity → 422; GET filters by status/severity; PATCH resolves (sets resolved_at); non-admin → 403; missing X-Enterprise-ID → 422; summary returns the 4 aggregate buckets with the right shape (fake conn returns canned counts).
- Regression: existing admin/dlq + router tests unaffected (new router, additive).

## Drift artefacts
- Migration → schema_snapshot regen (same DB caveat as #347/#348 — flag if no full-schema DB).
- New `/admin/incidents*` endpoints → OpenAPI regen (orchestrator). Gateway: confirm how `/admin/dlq` is routed at the edge (RouteConfigTest) — `/admin/incidents` should reuse the same `/api/v1/admin/**` (or equivalent) route; add a RouteConfigTest assertion if the admin prefix is asserted there. No new RouteConfig route if the prefix already covers it.
- No new error code → no FE i18n.

## Invariants
K-1 (RLS), K-6 (incident recording audited), K-12 (tenant + admin role from headers), K-14 (RFC 7807), K-21 (uuidv7/ulid). K-9 n/a (no money/rate). 

## File structure (anticipated — finalised in plan)
- `infrastructure/postgres/migrations/NNN_ai_incident.sql` (next free number) + shape test
- `services/ai-orchestrator/reasoning/incident_rules.py` (pure) + tests
- `services/ai-orchestrator/routers/incidents.py` (record_incident + 4 endpoints) + tests
- `services/ai-orchestrator/main.py` (mount router)
- drift: schema_snapshot (flag), OpenAPI, RouteConfigTest assertion

## Open risk
The gateway routing for `/admin/**` must already cover the new endpoints (so they're reachable like `/admin/dlq`). The plan confirms the edge route before assuming no RouteConfig change.
