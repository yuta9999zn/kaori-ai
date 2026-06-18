"""
WorkflowRunner — in-process workflow execution.

Phase 1 implementation: synchronous topo-sort + sequential node
execution, persisting state in ``workflow_runs`` + ``workflow_run_nodes``
(mig 088). Closes the "templates are seed-only" gap from the 2026-05-19
workflow-gap audit.

The runner is intentionally Temporal-free for the simplest path: it
runs inside the ai-orchestrator process as a background task spawned
from POST /workflows/{id}/run. Phase 2 wraps the same NodeExecutor.execute
calls inside Temporal activities for crash-recovery + retries — the
executor contract doesn't change.

State machine
=============
  pending           — row created, ready to start
  running           — runner picked up + executing nodes
  awaiting_approval — paused at an approval_gate node (resume API
                      flips back to running)
  completed         — every reachable node done (success terminal)
  failed            — a node raised + retries exhausted (terminal)
  cancelled         — user cancelled before completion

Topological ordering
====================
Workflow edges form a DAG (mig 053 enforces no cycles at save). The
runner does Kahn's algorithm + executes in that order. Approval_gate
PAUSES the run by recording awaiting_approval status on the run + node;
later POST /workflow-runs/{run_id}/approve resumes from there.

K-1 / K-12: enterprise_id flows through every persistence call via
acquire_for_tenant. NodeContext carries it through to each executor.

K-13: workflow_runs.idempotency_key UNIQUE per tenant — same caller
POST /workflows/{id}/run with same Idempotency-Key returns the existing
run_id instead of starting a duplicate run.

K-17: every workflow_run_nodes row records the node's side_effect_class
for post-mortem.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from .node_executor import (
    NodeContext,
    NodeExecutor,
    NodeExecutorError,
    NodeResult,
    REGISTRY,
)
from .side_effect import SideEffectClass
from .items import as_items
from .event_store import EventType, append_event
from .state_machine import (
    StateTransitionDenied,
    transition_node_status,
    transition_workflow_status,
)
from . import state_store as _store
from .compensation import run_compensation_chain

# Force builtin executors to register at import.
from . import executors as _executors  # noqa: F401

log = structlog.get_logger()


@dataclass
class WorkflowSnapshot:
    """Workflow definition pulled from DB at run start."""
    workflow_id:    UUID
    enterprise_id:  UUID
    workspace_id:   Optional[UUID]
    nodes:          list[dict]   # node_id, node_type_catalog_key, config_json, sequence_order
    edges:          list[dict]   # source_node_id, target_node_id, condition_expr


class WorkflowRunError(Exception):
    """Runner-level failure that should fail the run + propagate."""


# ─── Branch gating (if_else / switch) ────────────────────────────────────────
# A decision node emits which arm it took (if_else → output.branch 'true'/'false';
# switch → output.matched_case). The runner uses that to mark the NOT-taken
# branch's edges dead, so downstream nodes on the dead arm are skipped instead of
# all running unconditionally. Convention: an outgoing edge identifies its arm via
# condition_expr / label token, or is_default. Unrecognised token → edge stays
# live (never silently prune what we can't interpret — back-compat for edges that
# carry a raw expression rather than a branch token).

_TRUE_TOKENS = {"true", "yes", "có", "co", "t", "1", "pass", "passed"}
_FALSE_TOKENS = {"false", "no", "không", "khong", "else", "f", "0", "default", "fail"}


def _edge_branch_token(edge: dict[str, Any]) -> Optional[str]:
    # is_default wins: a default arm is identified by the flag, not by any
    # leftover raw condition text it may also carry.
    if edge.get("is_default"):
        return "default"
    for k in ("condition_expr", "label"):
        v = edge.get(k)
        if v:
            t = str(v).strip().lower()
            if t:
                return t
    return None


def _edge_is_live(edge: dict[str, Any], src_output: Optional[dict[str, Any]]) -> bool:
    """Is this outgoing edge taken, given its source node's output?

    src_output is None when the source was itself skipped (dead upstream) → the
    edge is dead, propagating the skip down the branch.

    When the source IS a decision (emits 'branch' / 'matched_case'), an arm
    fires ONLY if its token matches the chosen branch. An edge with no token or
    an unrecognised token is treated as DEAD — a decision picked a specific arm,
    so a mistagged/untagged edge must not become a silent catch-all that fires
    on every branch. (Non-decision sources keep every outgoing edge live.)
    """
    # None = source not in prior_outputs; {__skipped__} = source was skipped.
    # Both mean a dead upstream → edge dead (propagate the skip).
    if src_output is None:
        return False
    if isinstance(src_output, dict) and src_output.get("__skipped__") is True:
        return False
    branch = src_output.get("branch") if isinstance(src_output, dict) else None
    matched = src_output.get("matched_case") if isinstance(src_output, dict) else None
    token = _edge_branch_token(edge)

    if branch in ("true", "false"):
        if token in _TRUE_TOKENS:
            return branch == "true"
        if token in _FALSE_TOKENS:
            return branch == "false"
        return False  # decision took a specific arm; this edge isn't tagged for it
    if matched is not None:
        if token == "default":
            return str(matched).lower() == "default"
        if token is None:
            return False
        return token == str(matched).lower()
    return True  # non-decision source → always live


class WorkflowRunner:
    """In-process runner. Caller instantiates once per run and awaits
    ``run()``."""

    def __init__(self) -> None:
        self._registry = REGISTRY

    # ─── Topo sort ───────────────────────────────────────────────────

    @staticmethod
    def topological_order(snapshot: WorkflowSnapshot) -> list[dict]:
        """Kahn's algorithm. Returns nodes in execution order.
        Raises WorkflowRunError on cycle (mig 053 enforces no cycle at
        save time, so this is defensive)."""
        nodes_by_id = {n["node_id"]: n for n in snapshot.nodes}
        indegree: dict[str, int] = {nid: 0 for nid in nodes_by_id}
        adj: dict[str, list[str]] = {nid: [] for nid in nodes_by_id}
        for e in snapshot.edges:
            # ADR-0035 B5: only 'main' edges are data flow → DAG ordering. ai_*
            # ports are side connections (agent tools/memory/model), not steps.
            if (e.get("port_type") or "main") != "main":
                continue
            # BPMN message flows are cross-pool async signals, NOT sequence
            # steps — they must not create a topological dependency.
            if e.get("flow_kind") == "message":
                continue
            src = str(e["source_node_id"])
            tgt = str(e["target_node_id"])
            if src not in indegree or tgt not in indegree:
                continue
            adj[src].append(tgt)
            indegree[tgt] += 1

        # Stable seed: nodes with zero indegree, ordered by sequence_order.
        ready: list[str] = sorted(
            (nid for nid, d in indegree.items() if d == 0),
            key=lambda nid: (nodes_by_id[nid].get("sequence_order", 0), nid),
        )
        order: list[dict] = []
        while ready:
            nid = ready.pop(0)
            order.append(nodes_by_id[nid])
            for next_nid in sorted(adj[nid]):
                indegree[next_nid] -= 1
                if indegree[next_nid] == 0:
                    ready.append(next_nid)

        if len(order) != len(nodes_by_id):
            raise WorkflowRunError(
                f"Cycle detected in workflow — visited {len(order)}/{len(nodes_by_id)} nodes"
            )
        return order

    @staticmethod
    def side_connections(edges: list[dict], node_id) -> dict[str, list[str]]:
        """ADR-0035 B5 — typed side connections feeding ``node_id``, grouped by
        port_type ({'ai_tool': [src,...], ...}). Only non-'main' edges; the
        agent executor reads this to find its tools/memory/model."""
        out: dict[str, list[str]] = {}
        tgt = str(node_id)
        for e in edges:
            port = e.get("port_type") or "main"
            if port == "main" or str(e["target_node_id"]) != tgt:
                continue
            out.setdefault(port, []).append(str(e["source_node_id"]))
        return out

    # ─── DB persistence ──────────────────────────────────────────────

    @staticmethod
    async def load_workflow(workflow_id: UUID, enterprise_id: UUID) -> WorkflowSnapshot:
        """P1.1 — delegates SQL to state_store; runner stays orchestration-only."""
        wf = await _store.load_workflow_definition(enterprise_id, workflow_id)
        if wf is None:
            raise WorkflowRunError(f"Workflow {workflow_id} not found or not visible")
        return WorkflowSnapshot(
            workflow_id=wf["workflow_id"],
            enterprise_id=wf["enterprise_id"],
            workspace_id=wf["workspace_id"],
            nodes=wf["nodes"],
            edges=wf["edges"],
        )

    @staticmethod
    async def create_run(
        *,
        workflow_id:      UUID,
        enterprise_id:    UUID,
        workspace_id:     Optional[UUID],
        triggered_by:     Optional[UUID],
        trigger_source:   str,
        input_data:       dict[str, Any],
        idempotency_key:  Optional[str],
    ) -> UUID:
        """Insert workflow_runs row (or return existing on idempotency hit).
        Returns run_id."""
        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(enterprise_id) as conn:
            if idempotency_key:
                existing = await conn.fetchrow(
                    "SELECT run_id FROM workflow_runs "
                    "WHERE enterprise_id = $1 AND idempotency_key = $2",
                    enterprise_id, idempotency_key,
                )
                if existing:
                    log.info("workflow_run.idempotency_hit",
                              run_id=str(existing["run_id"]),
                              idempotency_key=idempotency_key)
                    return existing["run_id"]
            row = await conn.fetchrow(
                """INSERT INTO workflow_runs
                       (workflow_id, enterprise_id, workspace_id, status,
                        triggered_by_user_id, trigger_source,
                        input_data, idempotency_key)
                   VALUES ($1, $2, $3, 'pending', $4, $5, $6, $7)
                   RETURNING run_id""",
                workflow_id, enterprise_id, workspace_id,
                triggered_by, trigger_source,
                json.dumps(input_data), idempotency_key,
            )
        run_id = row["run_id"]
        # P0.1 event sourcing — emit workflow_created on creation. Errors
        # during event append are non-fatal at this stage (the run row
        # already exists; admin reconciliation can backfill).
        try:
            await append_event(
                enterprise_id=enterprise_id,
                run_id=run_id,
                event_type=EventType.WORKFLOW_CREATED,
                payload={
                    "workflow_id":     str(workflow_id),
                    "trigger_source":  trigger_source,
                    "idempotency_key": idempotency_key,
                    "input_keys":      sorted(input_data.keys()) if isinstance(input_data, dict) else [],
                },
                actor_user_id=triggered_by,
            )
        except Exception:  # noqa: BLE001
            log.exception("workflow_event.create_failed",
                           run_id=str(run_id), enterprise_id=str(enterprise_id))
        return run_id

    @staticmethod
    async def _update_run_status(
        run_id:        UUID,
        enterprise_id: UUID,
        *,
        status:        str,
        output_data:   Optional[dict] = None,
        error_summary: Optional[str] = None,
        ended:         bool = False,
    ) -> None:
        """Update workflow_runs row via the formal state machine (P0.2).

        Status changes go through transition_workflow_status() which
        validates the FROM→TO pair against ALLOWED_WORKFLOW. The side
        columns (output_data, error_summary, ended_at) are written
        unconditionally inside the same transaction.

        Gap 1: wrapped with retry + DbWriteExhausted absorber so a
        transient DB blip doesn't abort the run loop. After retries
        exhausted, the runner continues with a stale workflow_runs
        row + emits a metric so ops can spot the divergence.
        """
        async def _do():
            from ai_orchestrator.shared.db import acquire_for_tenant
            async with acquire_for_tenant(enterprise_id) as conn:
                async with conn.transaction():
                    try:
                        await transition_workflow_status(
                            conn, run_id=run_id, new_status=status,
                        )
                    except StateTransitionDenied as e:
                        log.warning("workflow_run.transition_denied",
                                      run_id=str(run_id),
                                      from_state=e.from_state,
                                      to_state=e.to_state)
                        return
                    side_params: list[Any] = []
                    side_clauses: list[str] = []
                    if output_data is not None:
                        side_clauses.append(f"output_data = ${len(side_params) + 1}")
                        side_params.append(json.dumps(output_data))
                    if error_summary is not None:
                        side_clauses.append(f"error_summary = ${len(side_params) + 1}")
                        side_params.append(error_summary)
                    if ended:
                        side_clauses.append(f"ended_at = ${len(side_params) + 1}")
                        side_params.append(datetime.now(timezone.utc))
                    if side_clauses:
                        side_params.append(run_id)
                        side_sql = (
                            f"UPDATE workflow_runs SET {', '.join(side_clauses)} "
                            f"WHERE run_id = ${len(side_params)}"
                        )
                        await conn.execute(side_sql, *side_params)

        try:
            await _store._retry_db_write("_update_run_status", _do)
        except _store.DbWriteExhausted:
            # Runner continues — state_store.exhausted log already
            # recorded the failure with full detail. The runner's view
            # of `current_status` is now in memory only; the DB row
            # stays at the prior status. Caller (admin / FE poller)
            # sees a stale row but the run still completes its loop.
            log.error(
                "workflow_run.state_write_unreachable",
                run_id=str(run_id),
                attempted_status=status,
            )

    @staticmethod
    async def _record_node(
        *,
        run_id:           UUID,
        node:             dict,
        enterprise_id:    UUID,
        side_effect_class: str,
        status:           str,
        input_data:       dict,
        output_data:      Optional[dict] = None,
        error_message:    Optional[str] = None,
    ) -> None:
        """UPSERT a workflow_run_nodes row for this (run, node).

        P1.1 — delegates to state_store. Runner no longer owns the SQL.
        Gap 1 — absorbs DbWriteExhausted so runner loop survives the
        per-node write failing after retries.
        """
        try:
            await _store.upsert_run_node(
                run_id=run_id, node=node, enterprise_id=enterprise_id,
                side_effect_class=side_effect_class, status=status,
                input_data=input_data, output_data=output_data,
                error_message=error_message,
            )
        except _store.DbWriteExhausted:
            log.error(
                "workflow_run.node_write_unreachable",
                run_id=str(run_id),
                node_id=str(node.get("node_id")),
                node_type_key=node.get("node_type_catalog_key"),
                attempted_status=status,
            )

    # ─── #7 B2 — loop/for-each ───────────────────────────────────────

    @staticmethod
    def _find_loop_regions(snapshot: "WorkflowSnapshot") -> tuple[dict, set]:
        """Map each loop_foreach node_id → {loop_end, body:[node_ids]} and the
        set of body+loop_end nodes the loops own (skipped in the main pass).
        Body = nodes on the main-edge path from loop_foreach to loop_end."""
        nodes_by_id = {str(n["node_id"]): n for n in snapshot.nodes}
        main_adj: dict[str, list[str]] = {}
        for e in snapshot.edges:
            if (e.get("port_type") or "main") != "main":
                continue
            if e.get("flow_kind") == "message":
                continue
            main_adj.setdefault(str(e["source_node_id"]), []).append(
                str(e["target_node_id"]))
        regions: dict[str, dict] = {}
        owned: set[str] = set()
        for nid, n in nodes_by_id.items():
            if n.get("node_type_catalog_key") != "loop_foreach":
                continue
            body: list[str] = []
            seen: set[str] = set()
            loop_end: Optional[str] = None
            queue = list(main_adj.get(nid, []))
            while queue:
                cur = queue.pop(0)
                if cur in seen:
                    continue
                seen.add(cur)
                cn = nodes_by_id.get(cur)
                if cn is None:
                    continue
                if cn.get("node_type_catalog_key") == "loop_end" \
                        or cn.get("node_type") == "loop_end":
                    loop_end = cur
                    continue   # marker — don't traverse past it
                body.append(cur)
                owned.add(cur)
                queue.extend(main_adj.get(cur, []))
            if loop_end:
                owned.add(loop_end)
            body.sort(key=lambda b: (nodes_by_id[b].get("sequence_order", 0), b))
            regions[nid] = {"loop_end": loop_end, "body": body}
        return regions, owned

    @staticmethod
    def _resolve_loop_items(items_ref, initial_input, prior_outputs) -> list:
        """Resolve config.items ($.input.x / $.nodeId.field / literal list) → list."""
        if isinstance(items_ref, list):
            return items_ref
        if not isinstance(items_ref, str) or not items_ref.startswith("$."):
            return []
        path = items_ref[2:].split(".")
        cur: Any = initial_input if path[0] == "input" else prior_outputs.get(path[0])
        for part in path[1:]:
            cur = cur.get(part) if isinstance(cur, dict) else None
        return cur if isinstance(cur, list) else []

    async def _execute_loop(self, *, loop_node, region, nodes_by_id, snapshot,
                            prior_outputs, prior_items, run_id, enterprise_id,
                            user_id, initial_input) -> dict:
        """Run a loop_foreach's body once per item.

        Per iteration: each body node's executor runs with the item injected at
        ``prior_outputs[item_var]`` (so the body reads ``$.<item_var>.<field>``),
        emitting NODE_STARTED/COMPLETED with the iteration index. After all items,
        each body node's run_node row is UPSERTed ONCE (final state) — the
        UNIQUE(run_id, node_id) means we can't keep N rows — and exposed in
        prior_outputs so after-loop nodes can read ``$.bodyNode.*``. Decisions
        INSIDE the body are branch-gated per iteration (only the taken arm runs).
        Returns {count} on success or {failed, error, stalled_node}."""
        config = loop_node.get("config_json") or {}
        if isinstance(config, str):
            config = json.loads(config) if config else {}
        item_var = config.get("item_var") or "item"
        items = self._resolve_loop_items(
            config.get("items"), initial_input, prior_outputs)
        max_iter = config.get("max_iterations")
        if isinstance(max_iter, int) and max_iter >= 0:
            items = items[:max_iter]
        body_nodes = [nodes_by_id[b] for b in region.get("body", []) if b in nodes_by_id]

        # Branch-gating WITHIN the body: edges between body nodes gate execution
        # the same way the main pass does, so a decision INSIDE the loop ("với
        # mỗi X, nếu … thì …") routes one arm instead of running both. body_nodes
        # are in sequence_order = a valid topo order for the forward-DAG body, so
        # predecessors run (and stamp iter_outputs) before their successors.
        body_ids = {str(b["node_id"]) for b in body_nodes}
        body_in: dict[str, list] = {}
        for e in snapshot.edges:
            if (e.get("port_type") or "main") != "main" or e.get("flow_kind") == "message":
                continue
            s, t = str(e["source_node_id"]), str(e["target_node_id"])
            if s in body_ids and t in body_ids:
                body_in.setdefault(t, []).append(e)

        await self._emit(
            run_id, enterprise_id, EventType.NODE_STARTED,
            node_id=loop_node["node_id"],
            payload={"node_type_key": "loop_foreach", "iterations": len(items)})

        last_output: dict[str, Any] = {}
        for idx, item in enumerate(items):
            iter_outputs = dict(prior_outputs)
            iter_outputs[item_var] = item
            iter_items = dict(prior_items)
            for bnode in body_nodes:
                bkey = bnode.get("node_type_catalog_key")
                bid = str(bnode["node_id"])
                # Gate on in-body incoming arms: a body node with incoming edges
                # from other body nodes runs only if a live arm reaches it (join
                # waits for ALL arms, others fire on ANY). Dead → mark skipped so
                # downstream gating + $.node reads see the skip sentinel.
                preds = body_in.get(bid, [])
                gate = all if bkey == "join" else any
                if preds and not gate(
                    _edge_is_live(e, iter_outputs.get(str(e["source_node_id"])))
                    for e in preds
                ):
                    iter_outputs[bid] = {"__skipped__": True}
                    await self._emit(
                        run_id, enterprise_id, EventType.NODE_SKIPPED,
                        node_id=bnode["node_id"],
                        payload={"iteration": idx, "reason": "branch_not_taken"})
                    continue
                version = int(bnode.get("type_version") or 1)
                executor = self._registry.get_versioned(bkey, version)
                bconfig = bnode.get("config_json") or {}
                if isinstance(bconfig, str):
                    bconfig = json.loads(bconfig) if bconfig else {}
                ctx = NodeContext(
                    enterprise_id=enterprise_id,
                    workspace_id=snapshot.workspace_id,
                    workflow_id=snapshot.workflow_id,
                    run_id=run_id, node_id=bnode["node_id"], user_id=user_id,
                    input_data=initial_input, prior_outputs=iter_outputs,
                    prior_items=iter_items,
                    connections=self.side_connections(snapshot.edges, bnode["node_id"]),
                )
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_STARTED,
                    node_id=bnode["node_id"],
                    payload={"iteration": idx, "loop_item_var": item_var})
                try:
                    result = await executor.execute(ctx, bconfig)
                except Exception as e:  # noqa: BLE001
                    msg = (f"loop body failed (iteration {idx}): "
                           f"{type(e).__name__}: {e}")
                    log.exception("workflow_run.loop_body_exception",
                                  run_id=str(run_id),
                                  node_id=str(bnode["node_id"]), iteration=idx)
                    await self._record_node(
                        run_id=run_id, node=bnode, enterprise_id=enterprise_id,
                        side_effect_class=executor.side_effect_class.value,
                        status="failed", input_data=bconfig, error_message=msg)
                    await self._emit(
                        run_id, enterprise_id, EventType.NODE_FAILED,
                        node_id=bnode["node_id"],
                        payload={"error": msg, "iteration": idx})
                    await self._update_run_status(
                        run_id, enterprise_id, status="failed",
                        error_summary=msg, ended=True)
                    await self._emit(
                        run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                        payload={"error": msg, "stalled_node": str(bnode["node_id"])})
                    return {"failed": True, "error": msg,
                            "stalled_node": str(bnode["node_id"])}
                iter_outputs[str(bnode["node_id"])] = result.output_data
                iter_items[str(bnode["node_id"])] = as_items(result.output_data)
                last_output[str(bnode["node_id"])] = result.output_data
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_COMPLETED,
                    node_id=bnode["node_id"],
                    payload={"iteration": idx, "output_data": result.output_data})
                if result.status == "failed":
                    msg = result.error_message or "loop body node failed"
                    await self._record_node(
                        run_id=run_id, node=bnode, enterprise_id=enterprise_id,
                        side_effect_class=executor.side_effect_class.value,
                        status="failed", input_data=bconfig, error_message=msg)
                    await self._update_run_status(
                        run_id, enterprise_id, status="failed",
                        error_summary=msg, ended=True)
                    await self._emit(
                        run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                        payload={"error": msg, "stalled_node": str(bnode["node_id"])})
                    return {"failed": True, "error": msg,
                            "stalled_node": str(bnode["node_id"])}

        # Persist body rows once (final state) + expose for after-loop reads.
        for bnode in body_nodes:
            bid = str(bnode["node_id"])
            out = last_output.get(bid, {"loop_iterations": len(items)})
            try:
                sec = self._registry.get_versioned(
                    bnode.get("node_type_catalog_key"),
                    int(bnode.get("type_version") or 1)).side_effect_class.value
            except Exception:  # noqa: BLE001
                sec = "pure"
            await self._record_node(
                run_id=run_id, node=bnode, enterprise_id=enterprise_id,
                side_effect_class=sec, status="completed",
                input_data={"loop_iterations": len(items)}, output_data=out)
            prior_outputs[bid] = out
            prior_items[bid] = as_items(out)

        loop_out = {"iterations": len(items), "completed": True}
        await self._record_node(
            run_id=run_id, node=loop_node, enterprise_id=enterprise_id,
            side_effect_class="pure", status="completed",
            input_data=config, output_data=loop_out)
        prior_outputs[str(loop_node["node_id"])] = loop_out
        prior_items[str(loop_node["node_id"])] = as_items(loop_out)
        await self._emit(
            run_id, enterprise_id, EventType.NODE_COMPLETED,
            node_id=loop_node["node_id"], payload=loop_out)
        return {"count": len(items)}

    # ─── Run loop ────────────────────────────────────────────────────

    async def run(
        self,
        *,
        run_id:        UUID,
        enterprise_id: UUID,
        user_id:       Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Execute the run end-to-end. Returns terminal state summary.

        Resume-aware: on a second call (e.g. after approval resume), nodes
        already marked 'completed' in workflow_run_nodes are skipped + their
        outputs reloaded into prior_outputs. approval_gate nodes with a
        resolved workflow_approvals row are treated as 'completed' before
        the executor runs."""
        # Determine if this is a fresh start or a resume (for event tagging)
        current = await self._fetch_run_status(run_id, enterprise_id)
        is_resume = current in ("awaiting_approval", "running")

        await self._update_run_status(run_id, enterprise_id, status="running")
        await self._emit(
            run_id, enterprise_id,
            EventType.WORKFLOW_RESUMED if is_resume else EventType.WORKFLOW_STARTED,
            actor_user_id=user_id,
        )

        try:
            run_row = await self._load_run(run_id, enterprise_id)
            snapshot = await self.load_workflow(run_row["workflow_id"], enterprise_id)
            ordered = self.topological_order(snapshot)
        except WorkflowRunError as e:
            await self._update_run_status(
                run_id, enterprise_id,
                status="failed", error_summary=str(e), ended=True,
            )
            await self._emit(run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                              payload={"error": str(e)})
            return {"status": "failed", "error": str(e)}

        # Preload completed nodes + resolved approvals for resume safety
        prior_completed = await self._load_completed_outputs(run_id, enterprise_id)
        resolved_approvals = await self._load_resolved_approvals(run_id, enterprise_id)

        prior_outputs: dict[str, dict[str, Any]] = dict(prior_completed)
        # ADR-0034: item-envelope view of completed outputs, rebuilt from the
        # persisted single dicts (each → a one-item envelope). Runs alongside
        # prior_outputs; nothing persisted changes. Lossless for today's
        # single-dict executors; multi-item persistence is a later PR.
        prior_items: dict[str, list] = {
            nid: as_items(od) for nid, od in prior_completed.items()
        }
        initial_input = run_row.get("input_data") or {}
        if isinstance(initial_input, str):
            initial_input = json.loads(initial_input) if initial_input else {}

        # Branch gating: incoming 'main' edges per node + the set of nodes
        # skipped because their branch wasn't taken. topo order guarantees a
        # node's predecessors are processed before it, so prior_outputs/skipped
        # are authoritative by the time we reach each node.
        incoming_main: dict[str, list[dict]] = {}
        for e in snapshot.edges:
            if (e.get("port_type") or "main") != "main":
                continue
            if e.get("flow_kind") == "message":   # async signal, not a gating arm
                continue
            incoming_main.setdefault(str(e["target_node_id"]), []).append(e)
        skipped: set[str] = set()

        # #7 B2 — loop regions. Each loop_foreach owns the body chain up to its
        # loop_end; the runner runs that body once per item and SKIPS the owned
        # nodes in the main pass (they're not standalone steps).
        loop_regions, loop_owned = self._find_loop_regions(snapshot)
        nodes_by_id = {str(n["node_id"]): n for n in snapshot.nodes}

        for node in ordered:
            node_key = str(node["node_id"])

            # Body / loop_end nodes are executed by their loop_foreach (or are a
            # marker) — never as a standalone step in the main pass.
            if node_key in loop_owned:
                continue

            # Skip nodes already completed in a prior run() invocation.
            if node_key in prior_completed:
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_SKIPPED,
                    node_id=node["node_id"],
                    payload={"output_data": prior_completed[node_key]},
                )
                continue

            # Branch gating — a node with incoming 'main' edges runs only if at
            # least one of them is live (taken arm of an upstream decision, or a
            # plain edge from a completed node). All arms dead → skip the node
            # (and, transitively, everything only reachable through it).
            # A 'join' (parallel_join) must wait for ALL its incoming arms to be
            # live (its whole point is to converge the parallel branches); every
            # other node activates if ANY incoming arm is live (a decision merge).
            preds = incoming_main.get(node_key, [])
            _gate = all if node["node_type_catalog_key"] == "join" else any
            if preds and not _gate(
                _edge_is_live(e, prior_outputs.get(str(e["source_node_id"])))
                for e in preds
            ):
                skipped.add(node_key)
                # Mark the skip in prior_outputs so a downstream node that reads
                # $.thisNode.* gets the SKIPPED sentinel (fail loud) instead of a
                # silent None/[] — and so _edge_is_live keeps propagating the skip.
                prior_outputs[node_key] = {"__skipped__": True}
                await self._record_node(
                    run_id=run_id, node=node, enterprise_id=enterprise_id,
                    side_effect_class="skipped", status="skipped",
                    input_data={"reason": "branch_not_taken"},
                )
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_SKIPPED,
                    node_id=node["node_id"],
                    payload={"reason": "branch_not_taken"},
                )
                continue

            # #7 B2 — loop_foreach: run the body region once per item instead of
            # the normal single executor pass. Returns the iteration count on
            # success, or a failure dict that ends the run.
            if node["node_type_catalog_key"] == "loop_foreach":
                loop_res = await self._execute_loop(
                    loop_node=node,
                    region=loop_regions.get(node_key, {"loop_end": None, "body": []}),
                    nodes_by_id=nodes_by_id,
                    snapshot=snapshot,
                    prior_outputs=prior_outputs,
                    prior_items=prior_items,
                    run_id=run_id,
                    enterprise_id=enterprise_id,
                    user_id=user_id,
                    initial_input=initial_input,
                )
                if loop_res.get("failed"):
                    return {"status": "failed", "error": loop_res.get("error"),
                            "stalled_node": loop_res.get("stalled_node")}
                continue

            # approval_gate: if workflow_approvals.status='approved',
            # convert to completed without re-invoking executor.
            if node["node_type_catalog_key"] == "approval_gate":
                resolved = resolved_approvals.get(node_key)
                if resolved and resolved["status"] == "approved":
                    output = {
                        "paused": False,
                        "auto_approved": False,
                        "approval_id": str(resolved["approval_id"]),
                        "resolved_by_user_id": (
                            str(resolved["resolved_by_user_id"])
                            if resolved["resolved_by_user_id"] else None
                        ),
                        "decision_note": resolved["decision_note"] or "",
                    }
                    await self._record_node(
                        run_id=run_id, node=node, enterprise_id=enterprise_id,
                        side_effect_class="write_idempotent",
                        status="completed",
                        input_data={},
                        output_data=output,
                    )
                    await self._emit(
                        run_id, enterprise_id, EventType.APPROVAL_RESOLVED,
                        node_id=node["node_id"],
                        payload={
                            "decision":     "approved",
                            "approval_id":  str(resolved["approval_id"]),
                            "decision_note": resolved["decision_note"] or "",
                        },
                        actor_user_id=resolved["resolved_by_user_id"],
                    )
                    await self._emit(
                        run_id, enterprise_id, EventType.NODE_COMPLETED,
                        node_id=node["node_id"],
                        payload={"output_data": output},
                    )
                    prior_outputs[node_key] = output
                    prior_items[node_key] = as_items(output)
                    continue
                if resolved and resolved["status"] == "rejected":
                    await self._emit(
                        run_id, enterprise_id, EventType.APPROVAL_RESOLVED,
                        node_id=node["node_id"],
                        payload={"decision": "rejected",
                                  "approval_id": str(resolved["approval_id"]),
                                  "decision_note": resolved["decision_note"] or ""},
                        actor_user_id=resolved["resolved_by_user_id"],
                    )
                    await self._update_run_status(
                        run_id, enterprise_id,
                        status="failed",
                        error_summary=f"Approval rejected at node {node_key}",
                        ended=True,
                    )
                    await self._emit(
                        run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                        payload={"error": "approval_rejected",
                                  "stalled_node": node_key},
                    )
                    return {"status": "failed",
                             "error": "approval_rejected",
                             "stalled_node": node_key}
            node_type_key = node["node_type_catalog_key"]
            if not self._registry.has(node_type_key):
                await self._record_node(
                    run_id=run_id, node=node, enterprise_id=enterprise_id,
                    side_effect_class="unknown",
                    status="failed",
                    input_data={"reason": "no executor registered"},
                    error_message=f"No executor for node_type_key={node_type_key!r}",
                )
                await self._update_run_status(
                    run_id, enterprise_id,
                    status="failed",
                    error_summary=f"No executor for {node_type_key!r}",
                    ended=True,
                )
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_FAILED,
                    node_id=node["node_id"],
                    payload={"error": f"No executor for {node_type_key!r}",
                              "node_type_key": node_type_key},
                )
                await self._emit(
                    run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                    payload={"error": f"No executor for {node_type_key!r}",
                              "stalled_node": str(node["node_id"])},
                )
                return {"status": "failed",
                         "error": f"No executor for {node_type_key!r}",
                         "stalled_node": str(node["node_id"])}

            # ADR-0034 B3: pin the node-type version the node was built on
            # (snapshot in workflow_nodes.type_version), falling back to the
            # registered executor when only that version exists.
            node_type_version = int(node.get("type_version") or 1)
            executor: NodeExecutor = self._registry.get_versioned(
                node_type_key, node_type_version)
            ctx = NodeContext(
                enterprise_id=enterprise_id,
                workspace_id=snapshot.workspace_id,
                workflow_id=snapshot.workflow_id,
                run_id=run_id,
                node_id=node["node_id"],
                user_id=user_id,
                input_data=initial_input,
                prior_outputs=prior_outputs,
                prior_items=prior_items,
                connections=self.side_connections(snapshot.edges, node["node_id"]),
            )
            config = node.get("config_json") or {}
            if isinstance(config, str):
                config = json.loads(config) if config else {}

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

            await self._emit(
                run_id, enterprise_id, EventType.NODE_STARTED,
                node_id=node["node_id"],
                payload={"node_type_key": node_type_key,
                          "side_effect_class": executor.side_effect_class.value,
                          "type_version": node_type_version},
            )

            try:
                result: NodeResult = await executor.execute(ctx, config)
            except NodeExecutorError as e:
                await self._record_node(
                    run_id=run_id, node=node, enterprise_id=enterprise_id,
                    side_effect_class=executor.side_effect_class.value,
                    status="failed",
                    input_data=config,
                    error_message=str(e),
                )
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_FAILED,
                    node_id=node["node_id"],
                    payload={"error": str(e),
                              "error_type": type(e).__name__},
                )
                await self._update_run_status(
                    run_id, enterprise_id,
                    status="failed", error_summary=str(e), ended=True,
                )
                await self._emit(
                    run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                    payload={"error": str(e),
                              "stalled_node": str(node["node_id"])},
                )
                await self._compensate_safe(run_id, enterprise_id, node["node_id"])
                return {"status": "failed", "error": str(e),
                         "stalled_node": str(node["node_id"])}
            except Exception as e:  # noqa: BLE001
                log.exception("workflow_run.node_exception",
                              run_id=str(run_id), node_id=str(node["node_id"]))
                await self._record_node(
                    run_id=run_id, node=node, enterprise_id=enterprise_id,
                    side_effect_class=executor.side_effect_class.value,
                    status="failed",
                    input_data=config,
                    error_message=f"{type(e).__name__}: {e}",
                )
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_FAILED,
                    node_id=node["node_id"],
                    payload={"error": f"{type(e).__name__}: {e}",
                              "error_type": type(e).__name__},
                )
                await self._update_run_status(
                    run_id, enterprise_id,
                    status="failed",
                    error_summary=f"{type(e).__name__}: {e}",
                    ended=True,
                )
                await self._emit(
                    run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                    payload={"error": f"{type(e).__name__}: {e}",
                              "stalled_node": str(node["node_id"])},
                )
                await self._compensate_safe(run_id, enterprise_id, node["node_id"])
                return {"status": "failed",
                         "error": f"{type(e).__name__}: {e}",
                         "stalled_node": str(node["node_id"])}

            # Decision contract guard: if_else/switch MUST emit the branch signal
            # the gating relies on. If a (mis)modified executor omits it, fail
            # loud instead of letting _edge_is_live treat the node as non-decision
            # and fire EVERY arm.
            if result.status == "completed" and node_type_key in ("if_else", "switch"):
                _need = "branch" if node_type_key == "if_else" else "matched_case"
                if not (isinstance(result.output_data, dict)
                        and _need in result.output_data):
                    msg = (f"decision node {node_type_key!r} did not emit "
                           f"{_need!r} — cannot route branches")
                    await self._record_node(
                        run_id=run_id, node=node, enterprise_id=enterprise_id,
                        side_effect_class=executor.side_effect_class.value,
                        status="failed", input_data=config, error_message=msg,
                    )
                    await self._emit(
                        run_id, enterprise_id, EventType.NODE_FAILED,
                        node_id=node["node_id"],
                        payload={"error": msg, "error_type": "DecisionContractError"})
                    await self._update_run_status(
                        run_id, enterprise_id, status="failed",
                        error_summary=msg, ended=True)
                    await self._emit(
                        run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                        payload={"error": msg, "stalled_node": str(node["node_id"])})
                    return {"status": "failed", "error": msg,
                            "stalled_node": str(node["node_id"])}

            await self._record_node(
                run_id=run_id, node=node, enterprise_id=enterprise_id,
                side_effect_class=executor.side_effect_class.value,
                status=result.status,
                input_data=config,
                output_data=result.output_data,
                error_message=result.error_message,
            )
            prior_outputs[str(node["node_id"])] = result.output_data
            prior_items[str(node["node_id"])] = as_items(result.output_data)

            if result.status == "awaiting_approval":
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_PAUSED,
                    node_id=node["node_id"],
                    payload={"output_data": result.output_data},
                )
                await self._update_run_status(
                    run_id, enterprise_id,
                    status="awaiting_approval",
                )
                await self._emit(
                    run_id, enterprise_id, EventType.WORKFLOW_PAUSED,
                    payload={"paused_at_node": str(node["node_id"])},
                )
                return {"status": "awaiting_approval",
                         "paused_at_node": str(node["node_id"])}
            if result.status == "failed":
                await self._emit(
                    run_id, enterprise_id, EventType.NODE_FAILED,
                    node_id=node["node_id"],
                    payload={"error": result.error_message},
                )
                await self._update_run_status(
                    run_id, enterprise_id,
                    status="failed",
                    error_summary=result.error_message,
                    ended=True,
                )
                await self._emit(
                    run_id, enterprise_id, EventType.WORKFLOW_FAILED,
                    payload={"error": result.error_message,
                              "stalled_node": str(node["node_id"])},
                )
                await self._compensate_safe(run_id, enterprise_id, node["node_id"])
                return {"status": "failed",
                         "error": result.error_message,
                         "stalled_node": str(node["node_id"])}

            # Success path
            await self._emit(
                run_id, enterprise_id, EventType.NODE_COMPLETED,
                node_id=node["node_id"],
                payload={"output_data": result.output_data},
            )

        await self._update_run_status(
            run_id, enterprise_id,
            status="completed",
            output_data=prior_outputs,
            ended=True,
        )
        executed = len(ordered) - len(skipped)
        await self._emit(
            run_id, enterprise_id, EventType.WORKFLOW_COMPLETED,
            payload={"nodes_executed": executed,
                      "nodes_skipped":  len(skipped),
                      "output_data":   prior_outputs},
        )
        return {"status": "completed", "nodes_executed": executed,
                 "nodes_skipped": len(skipped)}

    # ─── K-23 EU AI Act human-oversight gate (ADR-0041 Layer 3) ──────

    @staticmethod
    async def _oversight_required(
        *, run_id, enterprise_id, workflow_id, node_id, side_effect_class: str,
    ) -> bool:
        """K-23 — does this node need human oversight before executing?

        High-risk workflow (Layer 2 ai_use_risk_register) + impactful
        side-effect + not already granted. Cheap short-circuit for
        reversible classes (no DB). Fail-open on any DB error / missing
        table (lean deployments) so a hiccup never deadlocks a run.
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
        return oversight_applies(
            side_effect_class, risk_tier, already_granted=bool(granted))

    @staticmethod
    async def _pause_for_oversight(
        *, run_id, enterprise_id, node, side_effect_class: str,
    ) -> dict:
        """Synthesize an awaiting_approval pause for a K-23 oversight gate —
        mirrors the executor pause path (~985-1000) for a node we have NOT
        executed yet."""
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
                "Quy trình rủi ro cao (EU AI Act) — cần người phê duyệt "
                "trước bước có tác động.",
            )
        await WorkflowRunner._record_node(
            run_id=run_id, node=node, enterprise_id=enterprise_id,
            side_effect_class=side_effect_class, status="awaiting_approval",
            input_data={"oversight": "eu_ai_act_high_risk"},
        )
        await WorkflowRunner._emit(
            run_id, enterprise_id, EventType.NODE_PAUSED, node_id=node_id,
            payload={"oversight": True, "side_effect_class": side_effect_class},
        )
        await WorkflowRunner._update_run_status(
            run_id, enterprise_id, status="awaiting_approval")
        await WorkflowRunner._emit(
            run_id, enterprise_id, EventType.WORKFLOW_PAUSED,
            payload={"paused_at_node": str(node_id), "oversight": True},
        )
        try:
            from ai_orchestrator.shared.ai_governance import record_ai_call
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

    # ─── Compensation hook (P1.4) ───────────────────────────────────

    @staticmethod
    async def _compensate_safe(
        run_id:         UUID,
        enterprise_id:  UUID,
        failed_node_id: UUID,
    ) -> None:
        """Best-effort compensation chain — never raises. The runner
        already in a failure return path; compensation is bonus.
        """
        try:
            await run_compensation_chain(
                enterprise_id=enterprise_id,
                run_id=run_id,
                failed_node_id=failed_node_id,
            )
        except Exception:  # noqa: BLE001
            log.exception("compensation.chain_top_level_error",
                            run_id=str(run_id))

    # ─── Event store integration (P0.1) ─────────────────────────────

    @staticmethod
    async def _emit(
        run_id:         UUID,
        enterprise_id:  UUID,
        event_type:     EventType,
        *,
        node_id:        Optional[UUID] = None,
        payload:        Optional[dict[str, Any]] = None,
        actor_user_id:  Optional[UUID] = None,
    ) -> None:
        """Best-effort event emission. Failures logged but don't block
        the runner — workflow_runs.status remains the immediate view of
        truth; events provide the audit + replay trail."""
        try:
            await append_event(
                enterprise_id=enterprise_id,
                run_id=run_id,
                event_type=event_type,
                node_id=node_id,
                payload=payload or {},
                actor_user_id=actor_user_id,
            )
        except Exception:  # noqa: BLE001
            log.exception("workflow_event.emit_failed",
                           run_id=str(run_id),
                           event_type=event_type.value)

    # P1.1 — these methods now thin-wrap state_store so callers + tests
    # keep their import surface unchanged.
    @staticmethod
    async def _fetch_run_status(run_id: UUID, enterprise_id: UUID) -> Optional[str]:
        return await _store.fetch_run_status(enterprise_id, run_id)

    @staticmethod
    async def _load_run(run_id: UUID, enterprise_id: UUID) -> dict[str, Any]:
        row = await _store.load_run(enterprise_id, run_id)
        if row is None:
            raise WorkflowRunError(f"Run {run_id} not found")
        return row

    @staticmethod
    async def _load_completed_outputs(
        run_id:        UUID,
        enterprise_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        return await _store.load_completed_node_outputs(enterprise_id, run_id)

    @staticmethod
    async def _load_resolved_approvals(
        run_id:        UUID,
        enterprise_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        return await _store.load_resolved_approvals(enterprise_id, run_id)


async def run_in_background(
    *,
    run_id:        UUID,
    enterprise_id: UUID,
    user_id:       Optional[UUID] = None,
) -> None:
    """Spawn-and-forget entry point for FastAPI BackgroundTasks.
    Catches all exceptions so a failed run never crashes the parent
    process — the failure already lives in workflow_runs.error_summary."""
    try:
        runner = WorkflowRunner()
        await runner.run(
            run_id=run_id,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )
    except Exception:  # noqa: BLE001
        log.exception("workflow_run.background_crashed",
                       run_id=str(run_id),
                       enterprise_id=str(enterprise_id))


async def resume_after_approval(
    *,
    run_id:         UUID,
    enterprise_id:  UUID,
    user_id:        Optional[UUID] = None,
) -> dict[str, Any]:
    """Resume an awaiting_approval run by re-walking from where it paused.

    The runner's topological loop will re-encounter the approval_gate
    node (now resolved to status='approved' in workflow_approvals) and
    convert it to 'completed' via _replay_approval, then proceed to
    downstream nodes.
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    # Sanity check: run actually in awaiting_approval state
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT status FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
    if row is None:
        raise WorkflowRunError(f"Run {run_id} not found")
    if row["status"] != "awaiting_approval":
        raise WorkflowRunError(
            f"Run {run_id} status={row['status']!r}, cannot resume"
        )

    runner = WorkflowRunner()
    return await runner.run(
        run_id=run_id,
        enterprise_id=enterprise_id,
        user_id=user_id,
    )
