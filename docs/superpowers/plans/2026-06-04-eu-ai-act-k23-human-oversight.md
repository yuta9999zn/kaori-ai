# EU AI Act K-23 Human Oversight Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A workflow classified `risk_tier='high'` (Layer 2 `ai_use_risk_register`) must obtain human oversight before the runner executes any node whose `side_effect_class ∈ {write_non_idempotent, external}`; the human can **approve** (resume) or **stop** (cancel + saga compensation). EU AI Act Art 14, ADR-0041, invariant K-23.

**Architecture:** Reuse the runner's existing `awaiting_approval` pause/resume machinery. Insert an oversight check in `runner.run()` right before a node executes; when it fires, synthesize the same pause the runner already handles (write a `workflow_approvals` row tagged `gate_kind='eu_ai_act_oversight'`, set run status `awaiting_approval`, return). The existing `POST /workflow-runs/{id}/approve` resumes it unchanged (it's node-type-agnostic); on resume the granted row makes the oversight check pass and the node executes. A new `POST /workflow-runs/{id}/stop` cancels the run and fires `run_compensation_chain`. Pure trigger logic lives in a tiny testable module.

**Tech Stack:** Python FastAPI 0.111 (ai-orchestrator) · asyncpg + RLS (`acquire_for_tenant`) · pytest · the workflow runner (`workflow_runtime/runner.py`) + saga compensation (`workflow_runtime/compensation.py`).

**Branch:** `feat/eu-ai-act-k23-oversight` (stacked on `feat/eu-ai-act-compliance` — needs Layer 2's `ai_use_risk_register`). Re-target the PR to `main` after Layer 2 (PR #347) merges.

**Invariants:** K-1 RLS, K-6 audit, K-12 tenant-from-header, K-13 idempotent stop, K-14 RFC 7807, K-17 keyed on side_effect_class. No K-21 (column add only).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql` | Add `gate_kind` discriminator to `workflow_approvals` | Create |
| `scripts/test_migration_135_shape.py` | Shape test for mig 135 | Create |
| `services/ai-orchestrator/workflow_runtime/oversight.py` | Pure predicate `oversight_applies(...)` | Create |
| `services/ai-orchestrator/tests/test_oversight_predicate.py` | Unit tests for the predicate | Create |
| `services/ai-orchestrator/workflow_runtime/runner.py` | `_oversight_required` + `_pause_for_oversight` + insertion in `run()` | Modify |
| `services/ai-orchestrator/tests/test_oversight_runner.py` | Runner integration (pause/resume/non-trigger) | Create |
| `services/ai-orchestrator/routers/workflow_builder.py` | `POST /workflow-runs/{run_id}/stop` | Modify |
| `services/ai-orchestrator/tests/test_workflow_run_stop.py` | Stop endpoint tests | Create |
| OpenAPI spec + RouteConfigTest assertion | Drift artefacts | Modify |

---

## Task 1: Migration 135 — `gate_kind` on `workflow_approvals`

**Files:**
- Create: `infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql`
- Test: `scripts/test_migration_135_shape.py`

- [ ] **Step 1: Write the migration.** Create `infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql`:

```sql
-- =====================================================================
-- 135_workflow_approval_gate_kind.sql — EU AI Act Layer 3 (ADR-0041, K-23)
--
-- Discriminate an EU-AI-Act human-oversight pause from an author-placed
-- approval_gate. Additive: one nullable-safe column with a default; all
-- existing rows become 'approval_gate' (their actual meaning). No backfill.
-- =====================================================================

BEGIN;

ALTER TABLE workflow_approvals
    ADD COLUMN IF NOT EXISTS gate_kind VARCHAR(24) NOT NULL DEFAULT 'approval_gate';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_wfappr_gate_kind'
    ) THEN
        ALTER TABLE workflow_approvals
            ADD CONSTRAINT chk_wfappr_gate_kind
            CHECK (gate_kind IN ('approval_gate', 'eu_ai_act_oversight'));
    END IF;
END $$;

COMMENT ON COLUMN workflow_approvals.gate_kind IS
    'ADR-0041 K-23 — approval_gate (author-placed) | eu_ai_act_oversight '
    '(auto high-risk oversight). Runner replay keys on node_type, so this is '
    'for audit + the oversight already-granted query.';

COMMIT;
```

- [ ] **Step 2: Write the shape test.** Create `scripts/test_migration_135_shape.py`:

```python
"""Shape test for migration 135 (workflow_approvals.gate_kind) — no DB."""
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql"


def test_migration_135_exists():
    assert MIG.exists(), f"missing {MIG}"


def test_adds_gate_kind_column_additively():
    sql = MIG.read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS gate_kind" in sql
    assert "DEFAULT 'approval_gate'" in sql


def test_check_constraint_both_kinds():
    sql = MIG.read_text(encoding="utf-8")
    assert "chk_wfappr_gate_kind" in sql
    assert "eu_ai_act_oversight" in sql
    assert "approval_gate" in sql
```

- [ ] **Step 3: Run the shape test.** Run: `python -m pytest scripts/test_migration_135_shape.py -v` — Expected: 3 passed.

- [ ] **Step 4: Commit.**
```bash
git add infrastructure/postgres/migrations/135_workflow_approval_gate_kind.sql scripts/test_migration_135_shape.py
git commit -m "feat(compliance): mig 135 workflow_approvals.gate_kind (K-23)"
```

---

## Task 2: Pure oversight predicate

**Files:**
- Create: `services/ai-orchestrator/workflow_runtime/oversight.py`
- Test: `services/ai-orchestrator/tests/test_oversight_predicate.py`

- [ ] **Step 1: Write the failing test.** Create `services/ai-orchestrator/tests/test_oversight_predicate.py`:

```python
from ai_orchestrator.workflow_runtime.oversight import oversight_applies, IMPACTFUL_CLASSES


def test_impactful_classes():
    assert IMPACTFUL_CLASSES == ("write_non_idempotent", "external")


def test_high_risk_external_not_granted_requires_oversight():
    assert oversight_applies("external", "high", already_granted=False) is True


def test_high_risk_write_non_idempotent_requires_oversight():
    assert oversight_applies("write_non_idempotent", "high", already_granted=False) is True


def test_granted_does_not_require_again():
    assert oversight_applies("external", "high", already_granted=True) is False


def test_reversible_classes_never_require():
    for sec in ("pure", "read_only", "write_idempotent"):
        assert oversight_applies(sec, "high", already_granted=False) is False


def test_non_high_risk_never_requires():
    for tier in ("limited", "minimal", "prohibited", None):
        assert oversight_applies("external", tier, already_granted=False) is False
```

- [ ] **Step 2: Run test to verify it fails.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_oversight_predicate.py -v` — Expected: FAIL (ModuleNotFoundError: oversight).

- [ ] **Step 3: Write the implementation.** Create `services/ai-orchestrator/workflow_runtime/oversight.py`:

```python
"""Pure EU AI Act K-23 human-oversight trigger predicate (ADR-0041 Layer 3).

No I/O. A high-risk workflow must get human sign-off before an impactful
(hard-to-reverse / external) side-effect. Reversible classes
(pure/read_only/write_idempotent) never trigger; non-high tiers never
trigger; an already-granted oversight does not re-trigger.
"""
from __future__ import annotations

from typing import Optional

# The side-effect classes that are hard to reverse / leave the system —
# mirrors side_effect.needs_idempotency_dedup (write_non_idempotent + external).
IMPACTFUL_CLASSES: tuple[str, ...] = ("write_non_idempotent", "external")


def oversight_applies(
    side_effect_class: str,
    risk_tier: Optional[str],
    *,
    already_granted: bool,
) -> bool:
    """True iff this node needs human oversight before executing."""
    return (
        side_effect_class in IMPACTFUL_CLASSES
        and risk_tier == "high"
        and not already_granted
    )
```

- [ ] **Step 4: Run test to verify it passes.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_oversight_predicate.py -v` — Expected: 6 passed.

- [ ] **Step 5: Commit.**
```bash
git add services/ai-orchestrator/workflow_runtime/oversight.py services/ai-orchestrator/tests/test_oversight_predicate.py
git commit -m "feat(compliance): pure K-23 oversight trigger predicate"
```

---

## Task 3: Runner integration — gate + pause

**Files:**
- Modify: `services/ai-orchestrator/workflow_runtime/runner.py`
- Test: `services/ai-orchestrator/tests/test_oversight_runner.py`

**Context for the implementer:** Read `runner.py` lines 690–1000 first. Key facts:
- The per-node loop is `for node in ordered:` (line ~695). After branch-gating/loop handling, it resolves `executor = self._registry.get_versioned(...)` (~860), builds `ctx`/`config` (~862–876), emits `NODE_STARTED` (~878), then `result = await executor.execute(ctx, config)` (~887).
- The `awaiting_approval` pause is handled at lines ~985–1000 (emit NODE_PAUSED, set run status `awaiting_approval`, emit WORKFLOW_PAUSED, `return {"status":"awaiting_approval","paused_at_node":...}`).
- The approval replay block (~765) is keyed on `node["node_type_catalog_key"] == "approval_gate"` — it will NOT touch impactful nodes, so an oversight-paused node executes normally on resume.
- `prior_completed` skips only nodes recorded `completed`. We record the paused node `awaiting_approval`, so it re-runs on resume; by then the approved oversight row makes `_oversight_required` return False.
- Helper methods available on the runner: `self._record_node(run_id=, node=, enterprise_id=, side_effect_class=, status=, input_data=, output_data=, error_message=)`, `self._update_run_status(run_id, enterprise_id, status=, ...)`, `self._emit(run_id, enterprise_id, EventType.X, node_id=, payload=)`. `EventType.NODE_PAUSED` and `EventType.WORKFLOW_PAUSED` exist (used at 985–998).
- The `workflow_approvals` INSERT shape is in `executors/approval.py` (columns: run_id, node_id, enterprise_id, approver_roles, approver_user_id, sla_minutes, reason_prompt, status, chain_id, level_no) with `ON CONFLICT (run_id, node_id) DO UPDATE`.

- [ ] **Step 1: Write the failing integration test.** Create `services/ai-orchestrator/tests/test_oversight_runner.py`. FIRST read an existing runner test that exercises the approval_gate pause/resume (search `tests/` for `awaiting_approval` or `approval_gate` runner tests, e.g. `grep -rl awaiting_approval services/ai-orchestrator/tests`) and MIRROR its harness (how it builds a `WorkflowRunner`, fakes `acquire_for_tenant`, seeds nodes/edges snapshot, and asserts run status). Encode these behaviours:

```
1. test_high_risk_external_node_pauses_for_oversight:
   A snapshot with one `external` node, workflow risk_tier='high' (ai_use_risk_register
   row returns 'high'), no granted oversight row → runner.run(...) returns
   {"status": "awaiting_approval", ...}; a workflow_approvals row was inserted with
   gate_kind='eu_ai_act_oversight' and status='pending'; the executor's execute() was
   NOT called (the node did not run).

2. test_high_risk_read_only_node_does_not_pause:
   Same workflow but the node is `read_only` → no pause for oversight (runs normally /
   completes); no eu_ai_act_oversight row written.

3. test_non_high_risk_external_node_does_not_pause:
   external node but risk_tier='limited' (or no ai_use_risk_register row) → no oversight
   pause.

4. test_resume_after_oversight_executes_node:
   external node, high-risk, with an APPROVED eu_ai_act_oversight row already present for
   (run_id, node_id) → _oversight_required returns False → the node's executor IS invoked
   (the run proceeds). (If a full resume harness is too heavy, assert at minimum that
   _oversight_required(...) is False when the approved row exists — call the runner method
   directly with a faked conn.)
```

Use the same fake-`acquire_for_tenant` dispatch-by-SQL approach as `tests/test_workflow_prohibited_block.py`: SQL containing `ai_use_risk_register` returns the risk_tier row; SQL containing `workflow_approvals` + `EXISTS` returns the granted boolean; INSERT into `workflow_approvals` is captured. If mirroring the full runner harness is impractical for cases 1–4, it is acceptable to test `_oversight_required` (the DB-backed method) and `_pause_for_oversight` directly with a faked conn + assert the synthesized return shape, PLUS the pure predicate (Task 2) — note which approach you used.

- [ ] **Step 2: Run test to verify it fails.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_oversight_runner.py -v` — Expected: FAIL (methods `_oversight_required` / `_pause_for_oversight` don't exist).

- [ ] **Step 3: Add the two runner methods.** In `runner.py`, add these as methods on the `WorkflowRunner` class (place them near `_compensate_safe` / the other private helpers):

```python
    async def _oversight_required(
        self, *, run_id, enterprise_id, workflow_id, node_id, side_effect_class: str,
    ) -> bool:
        """K-23 — does this node need human oversight before executing?

        High-risk workflow (Layer 2 ai_use_risk_register) + impactful side-effect
        + not already granted. Cheap short-circuit for reversible classes (no DB).
        Fail-open on any DB error / missing table (lean deployments) so a hiccup
        never deadlocks a run.
        """
        from .oversight import oversight_applies, IMPACTFUL_CLASSES
        if side_effect_class not in IMPACTFUL_CLASSES:
            return False
        from ai_orchestrator.shared.db import acquire_for_tenant
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                risk_row = await conn.fetchrow(
                    """SELECT risk_tier FROM ai_use_risk_register
                       WHERE workflow_id = $1
                       ORDER BY classified_at DESC LIMIT 1""",
                    workflow_id,
                )
                granted = await conn.fetchval(
                    """SELECT EXISTS(
                           SELECT 1 FROM workflow_approvals
                           WHERE run_id = $1 AND node_id = $2
                             AND gate_kind = 'eu_ai_act_oversight'
                             AND status = 'approved')""",
                    run_id, node_id,
                )
        except Exception as e:  # noqa: BLE001 — fail-open
            log.warning("oversight.check_failed", error=str(e), run_id=str(run_id))
            return False
        risk_tier = risk_row["risk_tier"] if risk_row else None
        return oversight_applies(side_effect_class, risk_tier, already_granted=bool(granted))

    async def _pause_for_oversight(
        self, *, run_id, enterprise_id, node, side_effect_class: str,
    ) -> dict:
        """Synthesize an awaiting_approval pause for a K-23 oversight gate —
        mirrors the executor pause path (lines ~985-1000) but for a node we
        have NOT executed yet."""
        from ai_orchestrator.shared.db import acquire_for_tenant
        node_id = node["node_id"]
        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """INSERT INTO workflow_approvals
                       (run_id, node_id, enterprise_id, approver_roles,
                        sla_minutes, reason_prompt, status, gate_kind)
                   VALUES ($1, $2, $3, $4, $5, $6, 'pending', 'eu_ai_act_oversight')
                   ON CONFLICT (run_id, node_id) DO UPDATE
                       SET status = 'pending',
                           gate_kind = 'eu_ai_act_oversight',
                           approver_roles = EXCLUDED.approver_roles,
                           reason_prompt = EXCLUDED.reason_prompt""",
                run_id, node_id, enterprise_id, ["MANAGER"], 240,
                "Quy trình rủi ro cao (EU AI Act) — cần người phê duyệt trước bước có tác động.",
            )
        await self._record_node(
            run_id=run_id, node=node, enterprise_id=enterprise_id,
            side_effect_class=side_effect_class, status="awaiting_approval",
            input_data={"oversight": "eu_ai_act_high_risk"},
        )
        await self._emit(
            run_id, enterprise_id, EventType.NODE_PAUSED, node_id=node_id,
            payload={"oversight": True, "side_effect_class": side_effect_class},
        )
        await self._update_run_status(run_id, enterprise_id, status="awaiting_approval")
        await self._emit(
            run_id, enterprise_id, EventType.WORKFLOW_PAUSED,
            payload={"paused_at_node": str(node_id), "oversight": True},
        )
        try:
            from ..shared.ai_governance import record_ai_call
            await record_ai_call(
                enterprise_id=enterprise_id, task_kind="human_oversight_gate",
                model_version="rules-only", model_provider="kaori-compliance",
                prompt=f"oversight|node={node_id}|sec={side_effect_class}",
                output="paused_for_human_oversight", confidence=None,
                run_id=run_id, node_id=node_id,
            )
        except Exception as e:  # noqa: BLE001 — audit must not break the pause
            log.warning("oversight.audit_failed", error=str(e))
        return {"status": "awaiting_approval",
                "paused_at_node": str(node_id), "oversight": True}
```

- [ ] **Step 4: Insert the gate into the run loop.** In `runner.run()`, immediately AFTER the `config` parse block (the `config = node.get("config_json") or {}` / `if isinstance(config, str): config = json.loads(...)` lines, ~876) and BEFORE the `await self._emit(... EventType.NODE_STARTED ...)` call (~878), insert:

```python
            # K-23 EU AI Act human oversight (ADR-0041 Layer 3): a high-risk
            # workflow must get human sign-off before an impactful side-effect.
            # Synthesize the same awaiting_approval pause handled below; on resume
            # the granted oversight row makes this check pass and the node runs.
            if await self._oversight_required(
                run_id=run_id, enterprise_id=enterprise_id,
                workflow_id=snapshot.workflow_id, node_id=node["node_id"],
                side_effect_class=executor.side_effect_class.value,
            ):
                return await self._pause_for_oversight(
                    run_id=run_id, enterprise_id=enterprise_id, node=node,
                    side_effect_class=executor.side_effect_class.value,
                )
```

- [ ] **Step 5: Run the test to verify it passes.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_oversight_runner.py -v` — Expected: all pass.

- [ ] **Step 6: Run the broader runner suite for regressions.** Run: `cd services/ai-orchestrator && python -m pytest tests/ -k "runner or workflow_run or approval" -q` — Expected: no new failures vs baseline (the gate is inert for non-high-risk / reversible nodes, which is the existing-test majority). Report any failure + whether it relates to this change.

- [ ] **Step 7: Commit.**
```bash
git add services/ai-orchestrator/workflow_runtime/runner.py services/ai-orchestrator/tests/test_oversight_runner.py
git commit -m "feat(compliance): K-23 oversight gate in workflow runner"
```

---

## Task 4: Stop endpoint — `POST /workflow-runs/{run_id}/stop`

**Files:**
- Modify: `services/ai-orchestrator/routers/workflow_builder.py` (add beside the approve endpoint, ~line 2645)
- Test: `services/ai-orchestrator/tests/test_workflow_run_stop.py`

**Context:** The approve endpoint (`approve_workflow_run`, ~2645) shows the tenant/run pattern: `acquire_for_tenant(x_enterprise_id)`, header `X-Enterprise-ID` / `X-User-ID`, response_model `WorkflowRunOut`, helper `_fetch_run(x_enterprise_id, run_id)`. `run_compensation_chain(enterprise_id=, run_id=, failed_node_id=)` is in `workflow_runtime/compensation.py` (walks completed external/write_non_idempotent nodes in reverse; `failed_node_id` is used only for the event payload). Confirm the `workflow_runs` cancel column/values by reading how `_update_run_status(..., ended=True)` writes status/ended_at in runner.py, and match it.

- [ ] **Step 1: Write the failing test.** Create `services/ai-orchestrator/tests/test_workflow_run_stop.py`. Mirror the fake-conn + TestClient pattern from `tests/test_workflow_prohibited_block.py`. Patch `routers.workflow_builder.run_compensation_chain`... — actually `run_compensation_chain` is imported INSIDE the handler, so patch `ai_orchestrator.workflow_runtime.compensation.run_compensation_chain` with an `AsyncMock`. Behaviours:

```
1. test_stop_awaiting_approval_run_cancels_and_compensates:
   run status='awaiting_approval' → POST /workflow-runs/{id}/stop → 200; response status
   reflects 'cancelled'; workflow_runs UPDATE to 'cancelled' was issued; pending
   workflow_approvals UPDATE to 'cancelled' was issued; run_compensation_chain awaited once.

2. test_stop_already_cancelled_is_idempotent:
   run status='cancelled' → stop → 200, returns cancelled state, run_compensation_chain
   NOT awaited again (idempotent).

3. test_stop_completed_run_409:
   run status='completed' → stop → 409 (not stoppable).

4. test_stop_missing_run_404.

5. test_stop_missing_enterprise_header_422.
```

- [ ] **Step 2: Run test to verify it fails.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_workflow_run_stop.py -v` — Expected: FAIL (404/endpoint missing).

- [ ] **Step 3: Add the endpoint.** In `workflow_builder.py`, after the approve endpoint block, add:

```python
class WorkflowStopAction(BaseModel):
    """Body for POST /workflow-runs/{run_id}/stop (K-23 — human can stop a run)."""
    reason: Optional[str] = Field(default=None, max_length=2000)


_STOPPABLE_STATES = ("awaiting_approval", "running", "queued")


@router.post("/workflow-runs/{run_id}/stop", response_model=WorkflowRunOut)
async def stop_workflow_run(
    body:             WorkflowStopAction,
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:        Optional[UUID] = Header(default=None, alias="X-User-ID"),
):
    """Stop a run under human oversight (EU AI Act Art 14 / K-23): cancel the
    run + fire saga compensation for already-executed impactful nodes.
    Idempotent (K-13): stopping an already-cancelled run returns its state."""
    from ..workflow_runtime.compensation import run_compensation_chain

    async with acquire_for_tenant(x_enterprise_id) as conn:
        run = await conn.fetchrow(
            "SELECT status FROM workflow_runs WHERE run_id = $1", run_id,
        )
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        if run["status"] == "cancelled":
            return await _fetch_run(x_enterprise_id, run_id)   # idempotent
        if run["status"] not in _STOPPABLE_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"run status={run['status']!r} is not stoppable",
            )
        # Anchor node for the compensation event payload (best-effort).
        anchor = await conn.fetchrow(
            "SELECT node_id FROM workflow_run_nodes WHERE run_id = $1 "
            "ORDER BY ended_at DESC NULLS LAST LIMIT 1",
            run_id,
        )
        await conn.execute(
            "UPDATE workflow_approvals SET status = 'cancelled', resolved_at = NOW() "
            "WHERE run_id = $1 AND status = 'pending'",
            run_id,
        )
        await conn.execute(
            "UPDATE workflow_runs SET status = 'cancelled', ended_at = NOW() "
            "WHERE run_id = $1",
            run_id,
        )

    if anchor is not None:
        await run_compensation_chain(
            enterprise_id=x_enterprise_id, run_id=run_id,
            failed_node_id=anchor["node_id"],
        )

    try:
        from ..shared.ai_governance import record_ai_call
        await record_ai_call(
            enterprise_id=x_enterprise_id, task_kind="human_oversight_stop",
            model_version="rules-only", model_provider="kaori-compliance",
            prompt=f"stop|run={run_id}|reason={body.reason or ''}",
            output="run_cancelled", confidence=None, run_id=run_id,
        )
    except Exception:  # noqa: BLE001 — audit must not break the stop
        pass

    return await _fetch_run(x_enterprise_id, run_id)
```

(If `workflow_runs` has no `ended_at` column, drop that part of the UPDATE to match the real schema — verify against how `_update_run_status(ended=True)` writes it. If `BaseModel`/`Field`/`Optional`/`UUID`/`Header`/`Path`/`HTTPException`/`acquire_for_tenant`/`_fetch_run`/`WorkflowRunOut` aren't already imported at module top, they are — this router already uses all of them for the approve endpoint.)

- [ ] **Step 4: Run the test to verify it passes.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_workflow_run_stop.py -v` — Expected: all pass.

- [ ] **Step 5: Commit.**
```bash
git add services/ai-orchestrator/routers/workflow_builder.py services/ai-orchestrator/tests/test_workflow_run_stop.py
git commit -m "feat(compliance): POST /workflow-runs/{id}/stop — cancel + compensation (K-23)"
```

---

## Task 5: Drift artefacts

**Files:**
- Modify: `services/api-gateway/.../config/RouteConfigTest.java` (assertion only) · OpenAPI spec · (schema snapshot — flagged)

- [ ] **Step 1: OpenAPI regen.** Run: `cd D:\Kaori System && python scripts/dump_openapi.py orchestrator`. Confirm `docs/api-specs/orchestrator.openapi.json` now contains `/workflow-runs/{run_id}/stop`. If the script fails on import, report BLOCKED for this step (do not hand-edit the JSON).

- [ ] **Step 2: RouteConfigTest assertion.** The gateway already routes `/api/v1/workflow-runs/**` to ai-orchestrator (RouteConfigTest already asserts `/api/v1/workflow-runs/{id}/approve` → ORCH_URL). Add one assertion next to it: `assertResolvesTo("/api/v1/workflow-runs/" + "<uuid>/stop", ORCH_URL);`. No `RouteConfig.java` change (same prefix). Run `cd services/api-gateway && mvn -q -Dtest=RouteConfigTest test` (or the wrapper). If Maven can't run offline, report source-edited-not-run.

- [ ] **Step 3: Schema snapshot — flag.** Migration 135 alters `workflow_approvals`. `infrastructure/postgres/schema_snapshot.txt` must be regenerated (`python scripts/schema-drift.py --write --url <pg-url>` against a DB with mig 135 applied) before merge or CI `migration-test` flags drift. If no full-schema DB is available, DO NOT edit the snapshot — report it as the required pre-merge follow-up (same as Layer 2).

- [ ] **Step 4: Commit what changed.**
```bash
git add docs/api-specs/orchestrator.openapi.json services/api-gateway
git commit -m "chore(compliance): drift artefacts for /workflow-runs/{id}/stop (K-23)"
```

---

## Self-Review

**Spec coverage (vs the K-23 design doc):**
- ✅ Trigger = high-risk + impactful → Task 2 (pure) + Task 3 (`_oversight_required`).
- ✅ Reuse awaiting_approval pause + workflow_approvals + gate_kind discriminator → Task 1 + Task 3 (`_pause_for_oversight`).
- ✅ approve resumes unchanged (node-type-agnostic; replay keyed on approval_gate) → no code, verified in design; covered by Task 3 case 4.
- ✅ stop = cancel + compensation → Task 4.
- ✅ Audit K-6 (gate + stop) → Task 3 + Task 4 `record_ai_call`.
- ✅ Drift artefacts → Task 5.

**Placeholder scan:** No TBD/TODO. Two deliberate "verify against real schema" notes (workflow_runs.ended_at in Task 4; the existing runner test harness to mirror in Task 3) — these are "match existing code," not unspecified logic; exact code is given for everything else.

**Type consistency:** `oversight_applies(side_effect_class, risk_tier, already_granted)` + `IMPACTFUL_CLASSES` consistent across Task 2 (def) and Task 3 (call). `gate_kind='eu_ai_act_oversight'` consistent across Task 1 (constraint), Task 3 (insert + query). `_oversight_required` / `_pause_for_oversight` signatures match their call sites in the Task 3 insertion. Status strings (`awaiting_approval`, `cancelled`, `approved`, `pending`) consistent with the existing runner/approve code.

**Scope:** One subsystem (K-23 slice 1), one service + a gateway test assertion. Decisions table oversight / confidence trigger / full override explicitly deferred. Focused enough for one plan.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-06-04-eu-ai-act-k23-human-oversight.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, spec + quality review between tasks.
2. **Inline Execution** — executing-plans, batch with checkpoints.

Which approach?
