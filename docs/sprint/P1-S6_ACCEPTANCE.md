# Sprint P1-S6 — Acceptance Mapping

> **Sprint goal:** "Workflow Engine (Temporal) + builder UI"
> **Status:** ✅ contract surface shipped (5 features full Phase 1) + 18 REL-* deferred to P1.5+ + 4 Enterprise mapped to existing
> **Branch:** `feat/v4-p1-s6` (parent: `feat/v4-p1-s5`)
> **Date:** 2026-05-08

This sprint materialises the **Phase 1 contract surface** for Temporal-based workflow orchestration: 5 side-effect class taxonomy (K-17), idempotency framework (REL-004/005), and workflow YAML schema with K-17 + per-class validation. Real Temporal worker process + saga orchestrator + DLQ admin UI defer to Phase 1.5+ when the FPT Cloud K8s cluster lands (per ADR-0010 + ADR-0011).

The choice not to ship Temporal yet is deliberate: the workflow contract is the load-bearing piece (every node MUST declare side_effect_class for retry policy + saga compensation to work). The Temporal worker is the *execution engine* — once the contract is locked, swapping in Temporal vs an alternative orchestrator is a self-contained change.

---

## Net new work shipped this sprint

| Feature code | Description | Implementation |
|---|---|---|
| **REL-001 ⭐ + K-17** | Side-effect classification taxonomy (5 classes) | `services/ai-orchestrator/workflow_runtime/side_effect.py` — `SideEffectClass` str enum (PURE/READ_ONLY/WRITE_IDEMPOTENT/WRITE_NON_IDEMPOTENT/EXTERNAL) + `validate_side_effect_class()` + per-class capability helpers (needs_idempotency_dedup, needs_distributed_lock, needs_compensation). Single source of truth across YAML schema + idempotency_records column + audit log. |
| **REL-002 ⭐** | Per-node side-effect declaration in YAML | `workflow_runtime/yaml_schema.py` — JSONSchema (Draft 2020-12) for the workflow YAML, exported via `workflow_yaml_schema()`. `validate_workflow_yaml(doc)` enforces JSONSchema PLUS K-17 (every node has side_effect_class) + REL-012 (external requires compensation) + REL-006 (write_non_idempotent requires lock). Errors carry `node_id` so builder UI can highlight the offending node. |
| **REL-004 ⭐** | Idempotency key generation (deterministic) | `workflow_runtime/idempotency.py` — `derive_idempotency_key(workflow_id, node_id, run_id, input_data)` returns sha256(canonical-json) hex. Sort-keys JSON ensures dict ordering doesn't drift the hash. |
| **REL-005 ⭐** | Postgres idempotency_records table with TTL | Migration `041_idempotency_records.sql` — table + 7-day generated `expires_at` + RLS policy (K-1) + GRANT to `kaori_app`. Indexes on (tenant, workflow_id) + (tenant, run_id) + expires_at for purge. CHECK constraint enforces side_effect_class IN taxonomy (DB-side guard against typos in app code). |
| 24 unit tests | Contract enforcement | `services/ai-orchestrator/tests/test_workflow_runtime.py` — 5 enum/taxonomy tests, 3 capability helper tests, 6 derive_idempotency_key tests (determinism, ordering, run-id sensitivity, empty-input baseline, string vs UUID), 10 YAML schema tests including K-17/REL-006/REL-012 enforcement + node_id error hint. |

---

## 18 REL-* features deferred to Phase 1.5+ (contract ready, runtime defer)

These are documented in the deferred section because the **contract surface for them is shipped this sprint** (taxonomy classes drive retry/lock/compensation strategy in the YAML); only the runtime execution engine (Temporal worker) needs P1.5+ infrastructure. Each REL-XXX below references where Phase 1 already nails the contract:

| Feature | Phase 1 contract | P1.5+ runtime work |
|---|---|---|
| REL-003 Class-aware execution path | `needs_idempotency_dedup`, `needs_distributed_lock`, `needs_compensation` helpers (this sprint) | Action Runtime activity wrapper that branches on these helpers |
| REL-006 Distributed lock for write_non_idempotent | YAML `lock` schema + REL-006 validation (this sprint) | Redis SET NX EX integration in Action Runtime |
| REL-007 Provider-side dedup integration | (Phase 2) | SendGrid X-MC-Unique-Email, Twilio idempotency-key, Stripe idempotency-key adapters |
| REL-008 Retry policy per node | YAML `retry` block schema (this sprint) | Temporal RetryPolicy mapping in worker |
| REL-009 Retry-After header respect | (Phase 1.5+) | HTTP client middleware in providers/ |
| REL-010 Per-tenant rate limiting on retries | (Phase 1.5+) | Redis sliding-window counter |
| REL-011 Saga pattern for irreversible | YAML `compensation` schema + REL-012 validation (this sprint) | Temporal Saga workflow type wrapper |
| REL-012 Compensation action declarations | YAML schema enforced (this sprint) | Same |
| REL-013 Saga orchestrator (Temporal-based) | Contract via compensation YAML (this sprint) | Temporal SDK code (P15-S9 K8s deploy) |
| REL-015 Dead Letter Queue (DLQ) | (Phase 1.5+) | Postgres `workflow_dlq` table + consumer |
| REL-016 DLQ admin UI | (Phase 2) | FE feature — frontend paused |
| REL-017 DLQ alerting | (Phase 1.5+) | Prometheus alert rule on dlq_depth |
| REL-018 Circuit breaker per external service | (Phase 1.5+) | Resilience4j Java already has; Python TBD |
| REL-020 Per-node timeout configuration | YAML `timeout_ms` schema (this sprint) | Temporal Activity timeout binding |
| REL-021 Heartbeating for long-running activities | (Phase 1.5+) | Temporal heartbeat API in worker |
| REL-022 Per-tenant connection pool isolation | (Phase 1.5+) | asyncpg pool partition by tenant_id |
| REL-023 Per-tenant thread pool limits | (Phase 1.5+) | Worker config + uvloop concurrency cap |
| OBS-004 Workflow_run_id correlation across services | structlog log_context binding (P1-S1 ✅ shipped) extends to workflow_id when worker fires | Worker emits structured logs with workflow_id |
| OBS-007 Custom metrics: workflow_executions_total | (Phase 1.5+) | Prometheus Counter in Action Runtime |

**Why this split is OK Phase 1**: the workflow YAML enforces every reliability contract a Phase 1.5+ Temporal worker will need. A workflow author writing YAML today gets the same guard rails (K-17 + REL-006/012) regardless of whether the runtime runs Temporal or a Phase 1 single-process executor.

---

## 4 Enterprise features mapped to existing

| Feature | Existing impl | Test |
|---|---|---|
| `P2-M26-045` Config form auto-generate từ template | `routers/analyze.py` POST `/analyze/run` accepts template config; FE auto-form Phase 2 (paused) | Existing analyze tests |
| `P2-M26-058` Save analysis as template | F-NEW3 `analysis_templates` table + endpoint | Existing test |
| `P2-M27-006` Đề xuất quy trình quản lý data (workflow recommendation) | F-041 explainability + F-061 agent framework recommendations (deprecated experiment merged main; mapped here as informational) | Existing |
| `P2-M27-009` Save workflow template cho lần sau | Same as P2-M26-058 — template registry pattern reused | Same |

---

## Quick-run smoke command

```bash
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q       # 460 pass (+24 new)
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q          # 367 pass + 1 skip
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q            # 96 pass
cd "D:\Kaori System\services\notification-service" && python -m pytest -q   # 17 pass
```

**Total: 940 Python pass** (was 916 after P1-S5, +24 from workflow_runtime tests).

---

## Files touched this sprint (P1-S6)

```
infrastructure/postgres/migrations/
  041_idempotency_records.sql                     NEW (table + RLS + grants)

services/ai-orchestrator/
  workflow_runtime/__init__.py                    NEW (package marker + re-exports)
  workflow_runtime/side_effect.py                 NEW (SideEffectClass + helpers)
  workflow_runtime/idempotency.py                 NEW (derive_idempotency_key)
  workflow_runtime/yaml_schema.py                 NEW (JSONSchema + K-17/REL-006/012 validator)
  tests/test_workflow_runtime.py                  NEW (24 tests)

docs/sprint/P1-S6_ACCEPTANCE.md                  NEW (this file)
```

5 NEW Python files + 1 migration + 1 acceptance doc. **Smallest sprint footprint so far** — pure contract surface, no Temporal binding yet.

---

## What this sprint did NOT do (deferred / not in scope)

- **Temporal cluster deploy** — defers to P15-S9 with K8s per ADR-0011 + ADR-0010. infrastructure/temporal/README.md (Phase B-1) documents the deploy plan.
- **Action Runtime activity wrapper** — needs Temporal SDK; lands P1-S7 alongside Process Mining workflows that exercise it.
- **Saga orchestrator + DLQ + circuit breaker + heartbeat** — runtime work, Phase 1.5+.
- **45 node types catalog** — only the contract for ANY node is shipped; concrete node implementations land per use case (Process Mining nodes P1-S7, Reports nodes already exist via F-038, etc.).
- **Workflow Builder UI** — frontend paused.
- **drift Olist 12 file** — still stashed `stash@{0}`.

---

## Phase B-2 progress after Sprint P1-S6

```
services/ai-orchestrator/
├── reasoning/                           ← P1-S5 ✅
│   ├── legacy_analytics/                ← moved from analytics/
│   ├── insight_engine/ ... profiling/   ← skeletons (P1-S6+)
├── workflow_runtime/                    ← NEW this sprint
│   ├── __init__.py
│   ├── side_effect.py                   ← REL-001 / K-17 taxonomy
│   ├── idempotency.py                   ← REL-004 derive_idempotency_key
│   └── yaml_schema.py                   ← REL-002 + REL-006 + REL-012 validation
├── chat/                                ← stays (CHAT_TOOL_REGISTRY_V4 plan)
├── org_intel/                           ← Sprint P1-S7 will create
└── (frameworks, explainability, multi_tier, reports, agents — stay)
```

---

## Sprint dependency map

P1-S6 unblocks:
- P1-S7 Process Mining v1 — Process Mining workflows declare side_effect_class per node + use idempotency keys for re-mineable sessions
- Phase 1.5+ Temporal worker deploy — picks up YAML schema + side_effect class taxonomy as the worker-side contract
- F-061 successor (agent framework redesign Phase 2) — agent loop uses same taxonomy

P1-S6 depends on:
- ADR-0011 (Temporal choice locked)
- ADR-0014 (at-least-once + idempotency strategy locked)
- K-17 + K-20 invariants in CLAUDE.md

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S6 (27 features)
- `docs/strategic/WORKFLOW_SYSTEM.md` PART V (Workflow Engine Architecture) + Phần 9 (Reliability) + Phần 2.1 (5 side-effect classes)
- `docs/adr/0011-temporal-for-workflow-orchestration.md`
- `docs/adr/0014-at-least-once-plus-idempotency.md`
- `CLAUDE.md` K-17 (side-effect class declaration mandatory)
- `services/workflow-engine/README.md` — Phase 2 extract target (skeleton from Phase B-1)
- `infrastructure/temporal/README.md` — Phase 1.5+ deploy plan
- `docs/_v4_extract/sprint_phase1.json` — raw 27-feature list
