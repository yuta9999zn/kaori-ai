# ADR-0034 — Workflow data model: item envelope + declarative node schema

> **Status:** proposed
> **Date:** 2026-05-28
> **Deciders:** Nguyen Truong An
> **Related:** `workflow_runtime/node_executor.py` (NodeContext/NodeResult) · `workflow_runtime/runner.py` · `routers/workflow_builder.py` · `node_type_catalog` (mig 068) · n8n (github.com/n8n-io/n8n) · K-13 · K-17 · K-20 · Engineering Tenet 13

## Context

Phase 6 of the NNL-Harness/n8n study. Kaori's `workflow_runtime` is, on the execution axis, **more** production-hardened than n8n: saga compensation, per-node idempotency (K-13), `side_effect_class` retry policy (K-17), Temporal-readiness, replay/reconcile, and multi-tenant RLS — none of which n8n provides out of the box. So we do **not** adopt n8n's engine. What n8n does better, and what Kaori lacks, is two things in the **data model + builder UX**:

1. **A uniform item envelope.** Every n8n node receives and returns an *array of items* — `[{ json, binary?, pairedItem? }]`. Kaori passes a **single dict per node**: `NodeContext.prior_outputs: dict[node_id → output_data dict]`, `NodeResult.output_data: dict`. One dict per node means per-row fan-out, batching, and "process each record" have to be hand-coded in each executor, and there is no built-in record-level lineage. n8n's `pairedItem` records *which input item produced which output item* — lineage carried *in the data*, complementing Kaori's separate `shared/lineage`.

2. **Declarative node schema driving the UI.** n8n nodes ship one `description.properties[]` that both validates config and auto-renders the builder form. Kaori already has `node_type_catalog.config_schema_json` (JSONSchema) used for BE validation, but the FE builder renders node config with bespoke per-node code → drift between what BE accepts and what the FE offers.

Forces in tension: the item envelope is the right model, but `NodeContext`/`NodeResult` is the contract **every** executor + the runner + `state_store` depend on — a breaking rewrite is high blast-radius on a live, saga/idempotency-wired engine. Versus: a half-measure that bolts items onto some nodes and not others fragments the contract.

## Decision

Adopt the n8n **item envelope** and **declarative-schema-drives-UI** patterns, **additively and opt-in** — no breaking change to existing executors or the engine.

**1. Canonical item envelope (B1), backward-compatible.** Define the node I/O shape:
```python
# workflow_runtime/items.py
Item   = { "json": dict, "binary": dict | None, "pairedItem": {"item": int, "input": int} | None }
Items  = list[Item]
```
- The runner treats a node's output uniformly as `Items`. An executor that still returns a plain `output_data: dict` is **wrapped** by the runner as the degenerate one-item list `[{"json": output_data}]` — **zero change to existing executors**.
- An executor opts into multi-item by returning `Items` (or setting `emits_items=True`); only then does fan-out/batch apply.
- `prior_outputs` keeps its `{node_id → output_data}` shape for back-compat, **plus** a new `prior_items: {node_id → Items}` view so item-aware nodes read upstream items + walk `pairedItem` lineage.
- `pairedItem` lineage feeds K-6/`shared/lineage` (record-level provenance) — set automatically when the runner maps 1→1, declared by the executor when it fans out/aggregates.
- `state_store.output_data` (jsonb) already holds arbitrary JSON — a list serialises fine; **no migration** for storage. Per-item failure → degraded item + warning, not run abort (Tenet 13).

**2. Declarative node schema → auto-UI (B4).** Make `node_type_catalog.config_schema_json` the **single source of truth** for both BE validation and FE form rendering. Add a read endpoint (`GET /workflow/node-types` returning `{node_type_key, config_schema_json, ui_hints, side_effect_class, type_version}`) that the builder consumes to render config forms generically — no bespoke per-node FE code. New UI-only hints (labels_vi, widget, group) live in an additive `ui_schema_json` column so they never affect validation. This directly unblocks the paused FE workflow builder (§2 CLAUDE.md).

**3. Node `type_version` (B3).** Add `type_version` to `node_type_catalog` + persist it on `workflow_nodes` at creation. The executor registry keys on `(node_type_key, type_version)` so upgrading a node type's behaviour leaves existing workflows pinned to the version they were built on (K-20 extended from LLM models to node types — drift control + reproducible runs).

## Consequences

### Positive
- Per-row fan-out, batching, and record-level lineage (`pairedItem`) become first-class — without rewriting executors (legacy dict auto-wraps).
- The builder renders any node from its schema; one schema validates BE + drives FE → kills config drift, unblocks the FE workflow builder.
- `type_version` makes node upgrades non-breaking for live workflows (K-20 spirit).
- We keep Kaori's superior engine (saga/idempotency/Temporal/RLS) untouched — we only enrich the data envelope + the authoring surface.

### Negative / accepted trade-offs
- Two co-existing read shapes during transition (`prior_outputs` dict + `prior_items`) — modestly more runner code; retired once all executors are item-aware.
- `pairedItem` lineage is only as good as each fan-out/aggregate executor declaring it (1→1 is automatic).
- `type_version` adds a column (mig) + a registry keying change; old rows default to version 1.
- `ui_schema_json` is editorial work per node type (labels_vi, widgets).

### Neutral / follow-ups
- Phased delivery (one PR each): **PR1** `items.py` foundation (pure module + helpers + tests; no engine change). **PR2** runner auto-wrap + `prior_items` view (the ONLY PR that touches the saga-wired runner — ship with the chaos/idempotency/replay suites green). **PR3** `GET /workflow/node-types` + `ui_schema_json` (mig) for the builder. **PR4** node `type_version` (mig + registry keying). Typed AI ports (B5: ai_tool/ai_memory/ai_model connections) and trigger-node modelling of `ingestion/connectors/*` (B6) are later ADRs once the envelope lands.
- Recommended ship ORDER (decoupled from PR numbers): PR1 → **PR3** (low-risk, unblocks the paused FE builder) → PR2 (runner, highest risk; let PR3 run first for real signal) → PR4. PR3 does not depend on `items.py`, so it can land in parallel.
- "Pinned data" for node-level dev/test (n8n) maps onto the existing `replay`/`event_store` — a small builder-side affordance, deferred.
- Item envelope makes the chat/agent tool-calling path (F-061) expressible as item streams too — revisit when B5 typed ports land.
