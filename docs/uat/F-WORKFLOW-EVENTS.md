# UAT — F-WORKFLOW-EVENTS (Event Sourcing + Replay)

> **Function:** Phase 2.6 P0.1 — workflow_events append-only event store + replay harness
> **Portal:** P2 Enterprise (transparent backend; surfaced trong SH-04 DLQ Console + replay admin)
> **Service:** ai-orchestrator (`workflow_runtime/event_store.py` + `replay.py`)
> **DB:** mig 094 `workflow_events` (append-only + immutability triggers + 15 event types + per-run sequence_no)
> **Owner:** QA Lead + Platform Eng
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.6 P0.1 ship `c4eb59d` + `8d54230`)

| Surface | Purpose |
|---|---|
| Mig 094 `workflow_events` | Append-only + immutability triggers (UPDATE/DELETE blocked) + 15 EventType enum + per-run monotonic sequence_no |
| `event_store.py` | EventType/WorkflowEvent/RunProjection dataclasses + async append_event + load_event_stream + pure project_state |
| `replay.py` | ReplayHarness + ReplayResult + CachedSnapshot + diff_projection_vs_snapshot pure comparator + pytest helper |

Tests pass: `tests/test_event_store.py` 13/13 + `test_replay.py` 15/15.

---

## 1. Test scenarios

### TC-1 Happy path (event stream complete + replay)
- **Given** workflow run completes 5 nodes
- **When** load_event_stream(run_id) + project_state
- **Then** events: workflow_created/started + 5× node_started/completed + workflow_completed = ≥12 events; projection matches workflow_runs + workflow_run_nodes tables

### TC-2 Pause-resume continuity
- **Given** Approval gate paused at card 3; later resumed
- **When** load events + project_state at each step
- **Then** events include: workflow_paused (at gate) + approval_resolved + workflow_resumed; projection continuous monotone sequence_no

### TC-3 Drift detection
- **Given** Manual DB tampering: someone UPDATE workflow_runs.status='completed' directly (skipping events)
- **When** ReplayHarness runs nightly diff
- **Then** diff detects mismatch: cached row says completed, projection says paused; alert SEC NFR-SEC-19

### TC-4 Immutability trigger
- **Given** SQL `UPDATE workflow_events SET event_type='x' WHERE id=Y`
- **When** execute
- **Then** Postgres trigger raises ERROR; UPDATE/DELETE blocked; INSERT still allowed

## 2. Negative scenarios (NFRS §13.3)

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Normal workflow execution | TC-1 |
| **Validation** | Append event với invalid event_type | Enum check raises 400 |
| **Permission** | Non-admin try to query workflow_events | RLS blocks (K-1) |
| **Dependency** | event_store DB write fail | Caller retry per `db_retry.py` exponential backoff; workflow_runner.py best-effort log + continue (don't fail run because event store down) |

## 3. K-rule invariants

- **K-2** workflow_events append-only (immutability trigger) ✓
- **K-19** OTel span every append_event call

## 4. Performance

| NFR | Target |
|---|---|
| append_event P99 | <50ms |
| load_event_stream (1000 events) | <200ms |
| ReplayHarness 1 run | <500ms |

## 5. UAT execution checklist

- [ ] Verify mig 094 applied + 15 event types in enum
- [ ] Run sample workflow → verify events appended with monotonic sequence_no
- [ ] Try UPDATE/DELETE on workflow_events → verify trigger blocks
- [ ] ReplayHarness: project_state(events) === cached workflow_runs row
- [ ] Drift simulation: manually tamper row → verify diff detection
- [ ] Performance: 10k event append → <50ms P99

---

*UAT ID: UAT-WORKFLOW-EVENTS-001 · Owner Platform Eng*
