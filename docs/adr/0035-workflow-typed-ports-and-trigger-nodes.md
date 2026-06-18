# ADR-0035 — Workflow typed connection ports + trigger nodes

> **Status:** proposed
> **Date:** 2026-05-28
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0034 (item envelope + declarative node schema — names B5/B6 as follow-ups) · `workflow_edges` (mig 053) · `node_type_catalog` (mig 068) · `workflow_runtime/runner.py` topo-sort · F-061 Agent Framework · n8n typed connections + trigger nodes

## Context

The last two n8n patterns named in ADR-0034. Today Kaori workflow **edges are untyped** — every edge is "flow" (source → target, consumed by the runner's Kahn topo-sort) — and **triggers are implicit** (a `data_input` node with no incoming edge happens to start the run, but nothing declares "this is the entry").

Two gaps:
1. **Typed ports (B5).** n8n connects an AI agent to its tools / memory / model over *typed* ports (`ai_tool`, `ai_memory`, `ai_model`), distinct from the `main` data-flow. Without this, wiring an agent's tools means either bespoke config or — worse — modelling a tool as a `main`-flow edge, which would make the tool a *sequential step* in the topo order (wrong: a tool is a capability the agent calls, not the next node). F-061's agent framework needs to know "these nodes are my tools", declaratively.
2. **Trigger nodes (B6).** A workflow's entry should be explicit so the builder + ingestion can answer "what starts this?" and so connectors (`scheduled_trigger`, `read_webhook`, `read_form_submission`, inbound email) are first-class entry points, not just data nodes.

Force in tension: both want richer connection/entry semantics, but the runner's topo-sort + the edge/catalog contracts are live (saga/idempotency wired). A breaking change is unacceptable.

## Decision

Add both **additively**, defaulting so existing workflows behave identically.

**1. Typed connection ports (B5).** `workflow_edges.port_type` (default `'main'`, CHECK ∈ `{main, ai_tool, ai_memory, ai_model}`).
- The runner's `topological_order` follows **only `main` edges** for the DAG — `ai_*` edges are *side connections*, never flow steps. Default `'main'` ⇒ every existing edge is flow ⇒ topo unchanged.
- `NodeContext.connections: {port_type → [source_node_id]}` (default `{}`) — the runner populates it from the non-`main` edges whose target is this node, so an agent node reads `ctx.connections['ai_tool']` to find its tools/memory/model. (The agent *using* them is F-061 integration; this PR delivers the wiring + the runtime contract.)

**2. Trigger nodes (B6).** `node_type_catalog.is_trigger` (default `false`), set `true` for the event/entry node types (`scheduled_trigger`, `read_webhook`, `read_form_submission`, `read_email`). Exposed in `GET /workflow-node-types` so the builder renders them as trigger blocks and a workflow's entry is explicit. No runtime change — a trigger node is just a `data_input` node flagged as an entry point.

**3. Fix a latent gap from ADR-0034 B3.** `load_workflow_definition`'s node SELECT didn't project `type_version`, so the runner's `get_versioned(..., node.get('type_version', 1))` always saw `1`. Add `type_version` (and `port_type` for edges) to the SELECTs so B3 actually pins the built version.

## Consequences

### Positive
- Agents wire tools/memory/model declaratively over typed ports; the runner keeps them out of the flow order (correctness).
- Workflow entry is explicit → builder trigger blocks + connectors-as-triggers, unblocking event-driven workflows.
- B3 `type_version` pinning now works end-to-end.
- Fully additive: defaults (`port_type='main'`, `is_trigger=false`) leave every existing workflow + run identical.

### Negative / accepted trade-offs
- Touches the saga-wired runner (topo filter + NodeContext) — mitigated: additive + proven by the full runner/chaos/idempotency suite.
- mig 114 adds 2 columns + a catalog UPDATE (additive, nullable defaults).
- `ai_*` ports are *declared + wired* here; the agent runtime that consumes them is F-061 (follow-up) — this PR doesn't make agents call tools yet.

### Neutral / follow-ups
- F-061 agent executor reads `ctx.connections` to dispatch tools/memory/model — the consumer PR.
- Modelling each `ingestion/connectors/*` as a concrete trigger node type (beyond flagging existing ones) is incremental seed work.
- Builder UX for typed-port wiring + trigger blocks consumes `port_type` + `is_trigger` from the endpoints (FE work, gated on the FE restructure §2).
