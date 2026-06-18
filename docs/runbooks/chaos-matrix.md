# Chaos matrix — failure mode × verification point

> Authored 2026-05-20 as the runbook companion to the chaos test
> harness landed in commits `<chaos-1>` (llm-gateway) + `<chaos-2>`
> (ai-orchestrator). Every failure mode in this matrix has at least
> one passing pytest pinning the documented behaviour.
>
> **Use this when:** ops sees a metric anomaly + needs to know if the
> matching failure mode is one the platform already absorbs. Cross-
> reference the test column to confirm the contract is still pinned.

## How to read the matrix

- **Failure mode** = a realistic infrastructure or contract failure
  that production has hit or could hit.
- **Verification point** = WHERE this failure can occur in the request
  lifecycle.
- **Expected behaviour** = what the system DOES (passing chaos test
  proves it).
- **Surfacing** = where ops sees evidence: log line / metric / response.
- **Test** = the pytest that pins the behaviour.

Fail-OPEN vs fail-CLOSED rule of thumb:
- **Infra failure** (DB down, pool exhausted, timeout) → fail-OPEN —
  primary path keeps going, audit/quota/lineage gap is recoverable.
- **Explicit rejection** (QuotaExceeded, policy `deny` action,
  StateTransitionDenied) → fail-CLOSED — the answer is "no" and the
  caller gets 429/4xx.

---

## L1 — llm-gateway dispatch (`POST /v1/infer` + embed + ocr)

| Failure mode | Where | Expected | Surfacing | Test |
|---|---|---|---|---|
| AI governance pool exhausted | `record_ai_call` acquire | LLM call completes, response 200; gov row dropped | `log.ai_governance.write_failed` + `log.governance_audit_unexpected_failure` (router defense-in-depth) | `test_chaos_p27_wiring.py::TestGovAuditFailOpen::test_pool_exhausted_returns_200` |
| AI governance connection refused | `record_ai_call` execute | 200; gov row dropped | `log.ai_governance.write_failed` | `…::test_connection_refused_returns_200` |
| AI governance query timeout | `record_ai_call` fetchrow | 200; gov row dropped | `log.ai_governance.write_failed` | `…::test_query_timeout_returns_200` |
| RLS GUC SET fails | `set_config(app.enterprise_id, …, true)` | 200; gov row dropped | `log.ai_governance.write_failed` | `…::test_rls_guc_set_failure_returns_200` |
| Quota table down (infra) | `tenant_quotas.check_and_consume` raises non-QuotaExceeded | 200; quota gauge stale this call | `log.tenant_quota.infra_error.fail_open` + `log.quota_check_unexpected_failure` (router defense-in-depth) | `…::TestQuotaFailOpen::test_pool_exhausted_during_quota_check_returns_200` |
| No quota row configured | `tenant_quotas.check_and_consume` returns None | 200; tenant has no limit configured (default seed) | `log.tenant_quota.no_row.fail_open` | `…::test_quota_table_completely_missing_does_not_break` |
| Both governance + quota down | Compound | 200; both writes dropped, primary path lives | Both warnings in logs | `…::TestCompoundFailure::test_both_governance_and_quota_db_down_returns_200` |
| **Quota exceeded** (NOT chaos) | `check_and_consume` raises `QuotaExceeded` | 429 RFC 7807; LLM never called; **NO governance row** | `log.quota_exceeded` + RFC 7807 body w/ quota_type + period | `…::TestQuotaExceededNotChaos` |
| Upstream provider 5xx | `providers.invoke` raises | 502; `AI_CALLS_TOTAL{status="upstream_error"}` incremented | `log.provider_failed` | `test_router_pinned_and_metrics.py::test_provider_failure_increments_upstream_error_counter` |

**Performance budget**: each gov/quota call adds ≤ 5ms p50 latency on a
healthy DB. Under chaos, the try/except wrappers add < 1ms (no DB
round-trip). The user never pays for governance failure.

---

## L2 — workflow runner (`POST /workflows/{id}/run` + background execution)

### Pre-flight (router handler)

| Failure mode | Where | Expected | Surfacing | Test |
|---|---|---|---|---|
| Quota check infra error | `tenant_quotas.check_and_consume` (workflow_concurrent) | 202; run starts (fail-OPEN); quota gauge stale | `log.tenant_quota.infra_error.fail_open` | `test_chaos_p27_wiring.py::TestWorkflowRunQuotaChaos::test_quota_check_pool_exhausted_fails_open` |
| **workflow_concurrent exceeded** | `QuotaExceeded` raised | 429 RFC 7807; **workflow_runs row NOT created**; **background task NOT scheduled** | RFC 7807 body w/ quota_type=workflow_concurrent | `…::TestQuotaExceededNotAffectedByChaos::test_quota_exceeded_returns_429_with_compound_chaos` |
| Executor coverage missing | `REGISTRY.has(node_type_key)` false | 422 RFC 7807; lists missing keys + registered keys; run row NOT created | RFC 7807 body w/ `missing_node_types` | `test_workflow_builder_router.py` (workflow-start error tests) |

### Background execution (runner)

| Failure mode | Where | Expected | Surfacing | Test |
|---|---|---|---|---|
| Node executor raises arbitrary `Exception` | `executor.execute(ctx, config)` | run marked failed; node row recorded failed; `NODE_FAILED` + `WORKFLOW_FAILED` events emitted; compensation chain runs | `log.workflow_run.node_exception` | `test_chaos_workflow_runner.py::test_c1_executor_generic_exception_marked_failed` |
| Node raises `NodeExecutorError` (typed) | `executor.execute(...)` | run marked failed; error_summary contains the typed message verbatim | `log.workflow_run.node_exception` | `…::test_c2_node_executor_error_marked_failed` |
| Compensation handler raises mid-chain | `run_compensation_chain` raises | `_compensate_safe` absorbs, runner still returns `{"status": "failed"}` | `log.compensation.chain_top_level_error` | `…::test_c3_compensation_handler_raises_runner_still_returns_failed` |
| Event store INSERT fails (NODE_STARTED) | `append_event` raises | `_emit` internal try/except absorbs; executor still runs; run completes | `log.workflow_event.emit_failed` | `…::test_c4_event_store_append_fails_runner_continues` |
| Event store INSERT fails during failure path (NODE_FAILED + WORKFLOW_FAILED) | `append_event` raises while in except block | runner still returns `{"status": "failed"}`; event audit gap recorded in logs | `log.workflow_event.emit_failed` × 2 | `…::test_c5_event_store_fails_during_failure_path` |
| State transition denied (race with cancel) | `transition_workflow_status` raises | logs the denial, skips the update, run completes its current path | `log.workflow_run.transition_denied` | `…::test_c6_state_transition_denied_doesnt_break_runner` |
| Policy engine DB unreachable | `policy_engine._load_rules_from_db` raises | executor try/except absorbs; falls through to config defaults (no override applied) | `log.policy_engine.cache_reload_failed` | `test_chaos_p27_wiring.py::TestApprovalGatePolicyChaos::test_policy_db_error_falls_through_to_config` |

### Output executors (publish_insight / publish_alert / create_task)

| Failure mode | Where | Expected | Surfacing | Test |
|---|---|---|---|---|
| Lineage edge INSERT fails | `_emit_output_lineage` | insight/alert/task row IS created; lineage edge skipped | `log.output.lineage_emit_failed` + `log.lineage.write_failed` | `test_chaos_p27_wiring.py::TestOutputLineageChaos::test_lineage_emit_db_error_does_not_break_publish_insight` |
| Compound: lineage DB + policy DB both down | both gov layers fail | insight row created; both gov gaps logged | both warnings | `…::TestCompoundGovernanceFailure::test_all_governance_layers_down_publish_insight_succeeds` |

---

## L3 — data-pipeline ingestion (`/clean` apply rules)

| Failure mode | Where | Expected | Surfacing | Test |
|---|---|---|---|---|
| Lineage edge INSERT fails | `shared.lineage.record_edge` | `/clean` returns 200 with silver_complete status; lineage edge dropped (best-effort) | `log.lineage.write_failed` | `test_lineage_writer.py::test_record_edge_db_error_returns_false` |
| Lineage unknown kind | caller passes typo | `record_edge` returns False; primary path continues | `log.lineage.unknown_kind` | `…::test_record_edge_unknown_kind_returns_false` |

---

## Known gaps — status (2026-05-20)

All 5 gaps from the original 2026-05-19 audit are now CLOSED with code
+ tests. The runtime-reliability score should move "Khá" → "Khá-cao"
per anh's grading rubric.

| Failure mode | Where | Status | Commit | Tests |
|---|---|---|---|---|
| `workflow_runs` row INSERT/UPDATE fails | `_update_run_status` / `_record_node` | ✅ Closed (Gap 1) — retry+exhaust + runner absorbs DbWriteExhausted | `e927454` | 8 in `test_chaos_state_store_retry.py` |
| pgvector embedding INSERT fails | `PostgresTierStore.put` / `MemoryService.write` | ✅ Closed (Gap 2) — retry + `best_effort=True` default | `<gap-2>` | 7 in `test_chaos_memory_l3.py` |
| Temporal worker missing for activated cron | `TEMPORAL_ENABLE_WORKER=true` w/o worker process | ✅ Closed (Gap 3) — `/health/temporal` endpoint, K8s readiness wires up | `<gap-3>` | 5 in `test_chaos_temporal_health.py` |
| llm-gateway pool exhausted on init | `init_db_pool` after DB blip | ✅ Closed (Gap 4) — init retry + `ensure_pool_alive` re-init + `acquire_with_retry` | `fc4a166` | 8 in `test_chaos_pool_retry.py` |
| `SELECT FOR UPDATE` multi-second block | `tenant_quotas.check_and_consume` | ✅ Closed (Gap 5) — `SET LOCAL lock_timeout='2s'` + `statement_timeout='5s'` + fail-open wrapper | `e58c1d5` | 5 in `test_chaos_quota_contention.py` |

### Follow-up items — status (2026-05-20 PM)

All 5 Phase 3 follow-ups are now CLOSED. The runtime reliability axis
should move "Khá-cao" → "Cao" per anh's grading rubric.

| Item | Status | Commit | Tests |
|---|---|---|---|
| F1 — llm-gateway routers use acquire_with_retry | ✅ Closed | `0ef26dc` | 8 in `test_chaos_pool_retry.py` (G4.4–G4.7 updated to new CM pattern) |
| F2 — per-quota-type fail-open knob (workflow_concurrent fails-CLOSED) | ✅ Closed | `5dd1a4a` | 6 in `test_chaos_quota_fail_open_knob.py` + mig 100 |
| F3 — replay-driven reconciler for missed state writes | ✅ Closed | `<gap-3-final-tbd>` | 9 in `test_chaos_reconciler.py` + 2 admin endpoints |
| F4 — compound failure chaos test | ✅ Closed | `d3c85b8` | 4 in `test_chaos_compound_failure.py` |
| F5 — Memory L3 via Redis Streams (gated) | ✅ Closed | `<gap-5-tbd>` | 14 in `test_chaos_redis_stream_l3.py` |

### What this means for the platform

The full chaos defence layer (5 gaps + 5 follow-ups) now covers:

  Failure mode               | Fail-OPEN | Fail-CLOSED | Recovery path
  ---------------------------|-----------|-------------|---------------
  pool exhausted             | ✓ (retry) | (caller opt-in)  | acquire_with_retry
  query timeout              | ✓ (Gap 5) | per-quota (F2)   | SET LOCAL
  state writes exhausted     | ✓ (runner) | -               | replay reconciler (F3)
  event store fails          | ✓ (_emit) | -               | -
  pgvector L3 fails          | ✓ (best_effort) | -          | Redis Streams (F5)
  llm-gateway pool dead      | ✓ (retry) | -               | ensure_pool_alive
  policy_engine DB unreach   | ✓ (fall through) | -        | -
  compensation handler raise | ✓ (_compensate_safe) | -    | -
  state transition denied    | ✓ (log+skip) | -            | -
  Temporal worker missing    | -          | ✓ (503 ready probe) | -
  workflow_concurrent excess | -          | ✓ (429 RFC 7807)   | -
  llm_tokens_external excess | -          | ✓ (429 RFC 7807)   | -

### Remaining gaps — Phase 4 candidates

These would push the platform from "Cao" → "Rất cao" (production-
hardened at scale). Not blocked on code; gated on adoption or scale.

- Customer-signal-driven fail-open tuning: today every quota type
  defaults to TRUE except workflow_concurrent. Real production
  signal (which quotas have NEVER hit the fail-open path in 90 days?)
  could move more to FALSE.
- Reconciler scheduled as Temporal cron: F3 ships manual + endpoint;
  hourly automated sweep needs `TEMPORAL_ENABLE_WORKER=true`.
- Redis Streams L3 actually wired in production: F5 ships the
  producer + drain; switching MemoryService.write to use it needs
  `MEMORY_L3_VIA_REDIS_STREAMS=true` + Redis Streams cluster
  provisioned.
- Multi-region active-active for the chaos itself: today our defence
  layers assume a single Postgres/Temporal/Redis. A regional outage
  is unrecoverable. ADR + Phase 3 work.

---

## Test inventory

11 chaos tests across 3 files; all pass under the standard pytest run:

```
services/llm-gateway/tests/test_chaos_p27_wiring.py     8 tests
services/ai-orchestrator/tests/test_chaos_p27_wiring.py 5 tests
services/ai-orchestrator/tests/test_chaos_workflow_runner.py 6 tests
                                                       --
                                                       19 tests total
```

Run all chaos tests:

```bash
# All in one go from the repo root
pytest services/llm-gateway/tests/test_chaos_p27_wiring.py \
       services/ai-orchestrator/tests/test_chaos_p27_wiring.py \
       services/ai-orchestrator/tests/test_chaos_workflow_runner.py
```

When adding a new fail-open contract:
1. Wire the producer with try/except (defense in depth at the call
   site, not just inside the helper).
2. Add a chaos test that injects the realistic failure mode at the
   level you DIDN'T protect (e.g. inject at `append_event` to test
   `_emit`'s wrapper, NOT at `_emit` itself).
3. Update this matrix with the row.
4. Update the "Known gaps" section if your wiring leaves any failure
   path unwrapped.
