"""End-to-end branch-routing tests for the workflow runner.

Anh 2026-05-29: "test sâu hành vi rẽ nhánh if/else end-to-end" — dựng workflow
if/else 2 nhánh → chạy → kiểm đi đúng nhánh.

These drive the REAL runner + REAL IfElseExecutor / SwitchExecutor through a
fully stubbed state_store (no DB). They assert the runner now executes only the
TAKEN branch and skips the not-taken branch (and everything reachable only
through it). Before the branch-gating fix the runner ran every node in topo
order regardless of the decision outcome — these tests pin the corrected
behaviour.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from ai_orchestrator.workflow_runtime.node_executor import (
    NodeExecutor, NodeResult, REGISTRY,
)
from ai_orchestrator.workflow_runtime.runner import WorkflowRunner
from ai_orchestrator.workflow_runtime.side_effect import SideEffectClass


class _BranchPass(NodeExecutor):
    """Trivial pure node — records that it ran by completing."""
    node_type_key = "_branch_pass"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx, config):
        return NodeResult(status="completed", output_data={"ok": True})


@pytest.fixture(scope="module", autouse=True)
def _register():
    if not REGISTRY.has("_branch_pass"):
        REGISTRY.register(_BranchPass())
    yield


def _stub(monkeypatch, *, nodes, edges, wf_id, eid, input_data=None):
    from ai_orchestrator.workflow_runtime import state_store as _store
    from ai_orchestrator.workflow_runtime import runner as _runner

    async def _load_def(_e, _w):
        return {"workflow_id": wf_id, "enterprise_id": eid,
                "workspace_id": uuid4(), "nodes": nodes, "edges": edges}
    monkeypatch.setattr(_store, "load_workflow_definition", _load_def)

    async def _fetch_status(_e, _r):
        return "pending"
    monkeypatch.setattr(_store, "fetch_run_status", _fetch_status)

    async def _load_run(_e, _r):
        return {"workflow_id": wf_id, "input_data": input_data or {}}
    monkeypatch.setattr(_store, "load_run", _load_run)

    async def _load_completed(_e, _r):
        return {}
    monkeypatch.setattr(_store, "load_completed_node_outputs", _load_completed)

    async def _load_approvals(_e, _r):
        return {}
    monkeypatch.setattr(_store, "load_resolved_approvals", _load_approvals)

    recorded: list[dict] = []

    async def _upsert(**kw):
        recorded.append(kw)
    monkeypatch.setattr(_store, "upsert_run_node", _upsert)

    async def _upsert_side(**kw):
        pass
    monkeypatch.setattr(_store, "upsert_run_side_columns", _upsert_side)

    async def _noop_status(run_id, enterprise_id, *, status,
                           output_data=None, error_summary=None, ended=False):
        pass
    monkeypatch.setattr(_runner.WorkflowRunner, "_update_run_status",
                        staticmethod(_noop_status))

    async def _emit(run_id, enterprise_id, event_type, *,
                    node_id=None, payload=None, actor_user_id=None):
        pass
    monkeypatch.setattr(_runner.WorkflowRunner, "_emit", staticmethod(_emit))

    return recorded


def _status_by_node(recorded, ids: dict[str, object]) -> dict[str, str]:
    """Map friendly node name → last recorded status."""
    by_id = {}
    for kw in recorded:
        node = kw.get("node")
        if node is not None:
            by_id[str(node["node_id"])] = kw.get("status")
    return {name: by_id.get(str(nid)) for name, nid in ids.items()}


def _node(nid, key, *, config=None, seq=0):
    return {"node_id": nid, "node_type_catalog_key": key,
            "config_json": config or {}, "sequence_order": seq, "type_version": 1}


def _edge(src, tgt, *, condition_expr=None, label=None, is_default=False):
    return {"source_node_id": src, "target_node_id": tgt,
            "condition_expr": condition_expr, "label": label,
            "is_default": is_default, "port_type": "main"}


# ── if/else ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_if_else_takes_true_branch(monkeypatch):
    eid, wf, run = uuid4(), uuid4(), uuid4()
    D, T, F, MT, GF = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [
        _node(D, "if_else", config={"condition": {"left": 10, "op": ">", "right": 5}}, seq=0),
        _node(T, "_branch_pass", seq=1),
        _node(F, "_branch_pass", seq=1),
        _node(MT, "_branch_pass", seq=2),   # after T
        _node(GF, "_branch_pass", seq=2),   # after F
    ]
    edges = [
        _edge(D, T, condition_expr="true"),
        _edge(D, F, condition_expr="false"),
        _edge(T, MT),
        _edge(F, GF),
    ]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=run, enterprise_id=eid)

    assert out["status"] == "completed"
    st = _status_by_node(recorded, {"D": D, "T": T, "F": F, "MT": MT, "GF": GF})
    assert st["D"] == "completed"
    assert st["T"] == "completed"          # taken arm runs
    assert st["MT"] == "completed"         # downstream of taken arm runs
    assert st["F"] == "skipped"            # not-taken arm skipped
    assert st["GF"] == "skipped"           # transitively skipped
    assert out["nodes_executed"] == 3 and out["nodes_skipped"] == 2


@pytest.mark.asyncio
async def test_if_else_takes_false_branch(monkeypatch):
    eid, wf, run = uuid4(), uuid4(), uuid4()
    D, T, F = uuid4(), uuid4(), uuid4()
    nodes = [
        _node(D, "if_else", config={"condition": {"left": 1, "op": ">", "right": 5}}, seq=0),
        _node(T, "_branch_pass", seq=1),
        _node(F, "_branch_pass", seq=1),
    ]
    edges = [
        _edge(D, T, label="Có", condition_expr="true"),
        _edge(D, F, label="Không", condition_expr="false"),
    ]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=run, enterprise_id=eid)

    st = _status_by_node(recorded, {"T": T, "F": F})
    assert st["F"] == "completed"          # condition false → else arm
    assert st["T"] == "skipped"
    assert out["nodes_skipped"] == 1


@pytest.mark.asyncio
async def test_if_else_merge_point_still_runs(monkeypatch):
    """A merge node reachable from BOTH arms runs as long as ONE arm is live."""
    eid, wf, run = uuid4(), uuid4(), uuid4()
    D, T, F, M = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [
        _node(D, "if_else", config={"condition": {"left": 10, "op": ">", "right": 5}}, seq=0),
        _node(T, "_branch_pass", seq=1),
        _node(F, "_branch_pass", seq=1),
        _node(M, "_branch_pass", seq=2),
    ]
    edges = [
        _edge(D, T, condition_expr="true"),
        _edge(D, F, condition_expr="false"),
        _edge(T, M),
        _edge(F, M),
    ]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=run, enterprise_id=eid)

    st = _status_by_node(recorded, {"T": T, "F": F, "M": M})
    assert st["T"] == "completed"
    assert st["F"] == "skipped"
    assert st["M"] == "completed"          # live via T even though F is dead


# ── switch ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_switch_routes_to_matched_case(monkeypatch):
    eid, wf, run = uuid4(), uuid4(), uuid4()
    S, A, B, C = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [
        _node(S, "switch", config={"input": "gold",
              "cases": [{"when": "gold", "then": 1}, {"when": "silver", "then": 2}],
              "default": 0}, seq=0),
        _node(A, "_branch_pass", seq=1),   # gold
        _node(B, "_branch_pass", seq=1),   # silver
        _node(C, "_branch_pass", seq=1),   # default
    ]
    edges = [
        _edge(S, A, condition_expr="gold"),
        _edge(S, B, condition_expr="silver"),
        _edge(S, C, is_default=True),
    ]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=run, enterprise_id=eid)

    st = _status_by_node(recorded, {"A": A, "B": B, "C": C})
    assert st["A"] == "completed"          # matched 'gold'
    assert st["B"] == "skipped"
    assert st["C"] == "skipped"            # default not taken


@pytest.mark.asyncio
async def test_switch_falls_through_to_default(monkeypatch):
    eid, wf, run = uuid4(), uuid4(), uuid4()
    S, A, C = uuid4(), uuid4(), uuid4()
    nodes = [
        _node(S, "switch", config={"input": "bronze",
              "cases": [{"when": "gold", "then": 1}], "default": 0}, seq=0),
        _node(A, "_branch_pass", seq=1),
        _node(C, "_branch_pass", seq=1),
    ]
    edges = [
        _edge(S, A, condition_expr="gold"),
        _edge(S, C, is_default=True),
    ]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=run, enterprise_id=eid)

    st = _status_by_node(recorded, {"A": A, "C": C})
    assert st["A"] == "skipped"            # no case matched
    assert st["C"] == "completed"          # default arm taken


# ── if/else condition resolved from run input ($.input.x) ────────────────────
# Mirrors what a BPMN exclusive gateway produces after bpmn/sync: the gateway
# flow condition is lifted to if_else config {left:'$.input.score', op, right}
# and the arms carry 'true'/'false' tokens.

@pytest.mark.asyncio
async def test_if_else_condition_from_run_input(monkeypatch):
    eid, wf, run = uuid4(), uuid4(), uuid4()
    D, T, F = uuid4(), uuid4(), uuid4()
    cond = {"condition": {"left": "$.input.score", "op": ">=", "right": 80}}
    nodes = [
        _node(D, "if_else", config=cond, seq=0),
        _node(T, "_branch_pass", seq=1),
        _node(F, "_branch_pass", seq=1),
    ]
    edges = [
        _edge(D, T, condition_expr="true"),
        _edge(D, F, condition_expr="false"),
    ]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                     input_data={"score": 90})
    await WorkflowRunner().run(run_id=run, enterprise_id=eid)
    st = _status_by_node(recorded, {"T": T, "F": F})
    assert st["T"] == "completed" and st["F"] == "skipped"   # 90 >= 80 → true arm

    # Same workflow, score below threshold → false arm.
    recorded2 = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                      input_data={"score": 50})
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st2 = _status_by_node(recorded2, {"T": T, "F": F})
    assert st2["F"] == "completed" and st2["T"] == "skipped"


# ── compound condition (and/or) end-to-end ───────────────────────────────────

@pytest.mark.asyncio
async def test_if_else_compound_and_condition(monkeypatch):
    eid, wf = uuid4(), uuid4()
    D, T, F = uuid4(), uuid4(), uuid4()
    cond = {"condition": {"and": [
        {"left": "$.input.score", "op": ">=", "right": 80},
        {"left": "$.input.tier", "op": "==", "right": "gold"},
    ]}}
    nodes = [_node(D, "if_else", config=cond, seq=0),
             _node(T, "_branch_pass", seq=1), _node(F, "_branch_pass", seq=1)]
    edges = [_edge(D, T, condition_expr="true"), _edge(D, F, condition_expr="false")]

    # both clauses true → true arm
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                input_data={"score": 90, "tier": "gold"})
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st = _status_by_node(rec, {"T": T, "F": F})
    assert st["T"] == "completed" and st["F"] == "skipped"

    # one clause false → false arm
    rec2 = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                 input_data={"score": 90, "tier": "silver"})
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st2 = _status_by_node(rec2, {"T": T, "F": F})
    assert st2["F"] == "completed" and st2["T"] == "skipped"


@pytest.mark.asyncio
async def test_switch_three_way_from_input(monkeypatch):
    """N-way switch (as a >2 gateway lifts to) routes by input value."""
    eid, wf = uuid4(), uuid4()
    S, A, B, C, D = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    cfg = {"input": "$.input.tier",
           "cases": [{"when": "gold", "then": "gold"}, {"when": "silver", "then": "silver"}],
           "default": None}
    nodes = [_node(S, "switch", config=cfg, seq=0),
             _node(A, "_branch_pass", seq=1), _node(B, "_branch_pass", seq=1),
             _node(C, "_branch_pass", seq=1)]
    edges = [_edge(S, A, condition_expr="gold"), _edge(S, B, condition_expr="silver"),
             _edge(S, C, is_default=True)]
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                input_data={"tier": "silver"})
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st = _status_by_node(rec, {"A": A, "B": B, "C": C})
    assert st["B"] == "completed"            # matched silver
    assert st["A"] == "skipped" and st["C"] == "skipped"


# ── back-compat: no decision → nothing pruned ─────────────────────────────────

@pytest.mark.asyncio
async def test_linear_workflow_runs_every_node(monkeypatch):
    eid, wf, run = uuid4(), uuid4(), uuid4()
    A, B, C = uuid4(), uuid4(), uuid4()
    nodes = [_node(A, "_branch_pass", seq=0), _node(B, "_branch_pass", seq=1),
             _node(C, "_branch_pass", seq=2)]
    edges = [_edge(A, B), _edge(B, C)]
    recorded = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=run, enterprise_id=eid)

    st = _status_by_node(recorded, {"A": A, "B": B, "C": C})
    assert all(v == "completed" for v in st.values())
    assert out["nodes_skipped"] == 0
