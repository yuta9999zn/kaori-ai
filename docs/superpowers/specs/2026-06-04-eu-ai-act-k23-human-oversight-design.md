# EU AI Act Layer 3 — K-23 Human Oversight Gate (slice 1) — Design

> **Status:** design, pending approval → writing-plans
> **Date:** 2026-06-04
> **Part of:** EU AI Act Layer 3 (runtime enforcement), ADR-0041. Follows Layer 2 (K-22 classification gate, PR #347).
> **Scope:** slice 1 of 4 in Layer 3 (K-23 → K-24 → K-26 → bias). This doc covers **K-23 only**.

## Goal

For a workflow classified `risk_tier='high'` (EU AI Act Annex III high-risk, recorded in `ai_use_risk_register` by Layer 2), enforce **mandatory human oversight** (Art 14) before the runner executes any node with an **impactful** side-effect — `side_effect_class ∈ {write_non_idempotent, external}` — even when the workflow author did not place an explicit `approval_gate`. The human can **approve** (proceed), or **stop** (cancel the run + run saga compensation). This makes "a human can intervene and stop the system" a runtime guarantee, not an authoring choice.

## Decisions (confirmed with anh, 2026-06-04)

1. **Trigger:** gate fires iff `workflow.risk_tier == 'high'` **AND** the node's `side_effect_class ∈ {write_non_idempotent, external}` **AND** no oversight grant exists yet for that (run, node). `pure` / `read_only` / `write_idempotent` nodes proceed freely (reversible / no external effect).
2. **Stop semantics:** `stop` = cancel run **+ run compensation** (saga) for already-executed side-effecting nodes (`compensation.py`).
3. **Mechanism:** REUSE the existing pause/resume machinery (`awaiting_approval` status + `workflow_approvals` row + `POST /workflow-runs/{run_id}/approve`). Distinguish an EU-oversight pause from an authored `approval_gate` via a new `gate_kind` column.
4. **Out of slice 1 (YAGNI):** oversight for the standalone `decisions` table (already has `needs_user_confirm` + `decision_actions`); confidence-based trigger (different signal — slice 1b); full "override-with-different-action" (folded into approve-with-note for now).

## Architecture

### Insertion point (the chokepoint)
`workflow_runtime/runner.py`, inside `run()`'s per-node loop, **immediately before** `result = await executor.execute(ctx, config)` (currently ~line 887), where `executor.side_effect_class` is already resolved (~line 882). Insert:

```
if await _oversight_required(conn, workflow_id, run_id, node, executor.side_effect_class):
    <synthesize an awaiting_approval pause for this node>
    return {"status": "awaiting_approval", ...}   # mirror lines 985-999
```

The synthesized pause writes a `workflow_approvals` row with `gate_kind='eu_ai_act_oversight'` and sets `workflow_runs.status = awaiting_approval` — identical to how `ApprovalGateExecutor` pauses. The runner's existing awaiting_approval handling (lines 985-999) and `resume_run` (line 1152) need no change: on resume, `_oversight_required` returns False because a **granted** oversight row now exists, so the node executes.

### `_oversight_required(conn, workflow_id, run_id, node, side_effect_class) -> bool`
Returns True iff ALL hold:
- `side_effect_class in {"write_non_idempotent", "external"}`
- the workflow's latest `ai_use_risk_register` row has `risk_tier='high'` (reuse the same SELECT as Layer 2's `_check_prohibited_use`, reading `risk_tier`)
- there is **no** `workflow_approvals` row for `(run_id, node_id)` with `gate_kind='eu_ai_act_oversight'` and `status='approved'`
Tolerant of `ai_use_risk_register` missing (lean deployments) → returns False (fail-open, same posture as `_check_prohibited_use`). K-1 RLS via the tenant `conn` already open in the loop.

### Stop action — `POST /workflow-runs/{run_id}/stop`
New endpoint: validates the run is in `awaiting_approval` (or running) for this tenant; marks `workflow_runs.status='cancelled'`; invokes the existing compensation path (`compensation.py`) for nodes already executed with a side-effect; audits the stop. Idempotent (K-13): stopping an already-cancelled run returns the cancelled state.

### Reuse of approve
The existing `POST /workflow-runs/{run_id}/approve` already resumes any pending `workflow_approvals` row → it resumes an `eu_ai_act_oversight` row unchanged. No change needed beyond ensuring it stamps `status='approved'` on the row (it already does for the gate). Approve-with-note covers the "override" case for slice 1.

## Data model

**Migration 135** (additive, low-risk): add to `workflow_approvals`:
- `gate_kind VARCHAR(24) NOT NULL DEFAULT 'approval_gate'` — values `'approval_gate'` | `'eu_ai_act_oversight'`. Existing rows default to `'approval_gate'` (no backfill needed). No new table; K-21 not applicable (column add to an existing table).

(If `workflow_approvals` already carries a discriminator that fits, reuse it instead — the plan will confirm by reading the table's migration first.)

## Audit (K-6)
- When the gate opens (pause): `record_ai_call`-style audit row, `task_kind='human_oversight_gate'`, carrying workflow_id/run_id/node_id + side_effect_class + risk_tier.
- On approve / stop: audit the human action (reuse existing approval audit if present; else add a minimal audit write).

## Error handling
- Gate pause is not an error — it's a normal `awaiting_approval` return (200/202 from the run endpoint).
- `stop` on a run not in a stoppable state → RFC 7807 `409` (reuse existing run-state error pattern).
- `_oversight_required` swallows DB errors → False (fail-open) so an infra hiccup never deadlocks a run; logged as a warning.

## Testing
- **Unit (pure):** `_oversight_required` truth table — impactful×high → True; impactful×(non-high/none) → False; reversible×high → False; granted-row present → False; table-missing → False.
- **Runner integration:** a high-risk workflow with an `external` node pauses at that node (status awaiting_approval, gate_kind='eu_ai_act_oversight'); after approve → resumes and completes; a `read_only` high-risk node does NOT pause.
- **Stop endpoint:** stop on a paused high-risk run → cancelled + compensation invoked for executed side-effect nodes; idempotent re-stop; 409 on non-stoppable state.
- Regression: existing approval_gate tests still pass (gate_kind defaults preserve behaviour); broad `-k workflow` suite green.

## Drift artefacts (per repo rule)
New `/workflow-runs/{id}/stop` endpoint → refresh: RouteConfigTest (the `/api/v1/workflow-runs/**` route likely already exists — confirm; if covered, no new gateway route, only a resolution assertion), OpenAPI regen, FE i18n for any new error code. Migration 135 → schema_snapshot regen (same DB caveat as Layer 2 — flag if no full DB).

## Invariants
K-1 (RLS via tenant conn), K-6 (audit gate + actions), K-12 (tenant from JWT/header), K-13 (stop idempotent), K-14 (RFC 7807), K-17 (gate keyed off side_effect_class). No K-21 (column add only).

## File structure (anticipated — finalised in plan)
- `infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql` + shape test
- `workflow_runtime/oversight.py` (pure `oversight_required` predicate; thin, testable) + tests
- `workflow_runtime/runner.py` (insert the gate check + synthesize pause)
- `routers/workflow_builder.py` or `workflow_collab.py` (the `/workflow-runs/{id}/stop` endpoint — place beside the existing `/approve`) + tests
- drift artefacts (gateway test assertion, openapi, FE i18n)

## Open risk
The runner pause synthesis must exactly match the existing `awaiting_approval` return shape (lines 985-999) so resume works unchanged. The plan will read that block + `resume_run` verbatim before writing the insert.
