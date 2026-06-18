"""Combination + audit-fix end-to-end tests for the workflow engine.

Anh 2026-05-30: "tổ hợp các loại workflow … test thực thi hết các item, xem
logic có chỗ nào lỗi không." A multi-agent audit found 21 logic bugs; this file
proves the fixes by driving the REAL runner (+ real executors, + the BPMN
mapper) through a stubbed state_store (no DB). It covers:
  • BPMN XML → mapper → runner control-flow (gateway lift) end-to-end
  • start/end events run as noop (no "No executor for None")
  • a data pipeline chaining filter → sort → aggregate
  • regression guards for each confirmed audit bug (message-flow cycle, typo /
    untagged decision tokens, missing branch signal, parallel join all-arms)
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from ai_orchestrator.workflow_runtime import executors as _execs  # noqa: F401 — registers
from ai_orchestrator.workflow_runtime.node_executor import (
    NodeExecutor, NodeResult, REGISTRY,
)
from ai_orchestrator.workflow_runtime.runner import WorkflowRunner
from ai_orchestrator.workflow_runtime.side_effect import SideEffectClass
from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_bpmn_xml


@pytest.fixture(scope="module", autouse=True)
def _register():
    # a generic pass-through used as a plain step
    class _Pass(NodeExecutor):
        node_type_key = "_combo_pass"
        side_effect_class = SideEffectClass.PURE

        async def execute(self, ctx, config):
            return NodeResult(status="completed", output_data={"ok": True})

    if not REGISTRY.has("_combo_pass"):
        REGISTRY.register(_Pass())
    yield


# ─── stub state_store + runner side-effects ──────────────────────────────────

def _stub(monkeypatch, *, nodes, edges, wf_id, eid, input_data=None):
    from ai_orchestrator.workflow_runtime import state_store as _store
    from ai_orchestrator.workflow_runtime import runner as _runner

    async def _load_def(_e, _w):
        return {"workflow_id": wf_id, "enterprise_id": eid,
                "workspace_id": uuid4(), "nodes": nodes, "edges": edges}
    monkeypatch.setattr(_store, "load_workflow_definition", _load_def)
    monkeypatch.setattr(_store, "fetch_run_status",
                        lambda *a, **k: _async("pending"))
    monkeypatch.setattr(_store, "load_run",
                        lambda *a, **k: _async({"workflow_id": wf_id, "input_data": input_data or {}}))
    monkeypatch.setattr(_store, "load_completed_node_outputs", lambda *a, **k: _async({}))
    monkeypatch.setattr(_store, "load_resolved_approvals", lambda *a, **k: _async({}))

    recorded: list[dict] = []

    async def _upsert(**kw):
        recorded.append(kw)
    monkeypatch.setattr(_store, "upsert_run_node", _upsert)
    monkeypatch.setattr(_store, "upsert_run_side_columns", lambda **k: _async(None))

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


def _async(value):
    async def _coro():
        return value
    return _coro()


def _by_node(recorded, id_map):
    """name → {status, output_data} from recorded upserts."""
    out = {}
    for kw in recorded:
        node = kw.get("node")
        if node is not None:
            out[str(node["node_id"])] = kw
    return {name: out.get(str(nid)) for name, nid in id_map.items()}


def _node(nid, key, *, config=None, seq=0):
    return {"node_id": nid, "node_type_catalog_key": key,
            "config_json": config or {}, "sequence_order": seq, "type_version": 1}


def _edge(src, tgt, *, condition_expr=None, label=None, is_default=False,
          flow_kind="sequence", port_type="main"):
    return {"source_node_id": src, "target_node_id": tgt,
            "condition_expr": condition_expr, "label": label,
            "is_default": is_default, "flow_kind": flow_kind, "port_type": port_type}


# ─── BPMN XML → mapper → runner (full pipeline) ───────────────────────────────

def _diagram_to_runner(diagram):
    id_map = {n.client_id: uuid4() for n in diagram.nodes}
    nodes = [_node(id_map[n.client_id], n.node_type, config=n.config, seq=i)
             for i, n in enumerate(diagram.nodes)]
    edges = [_edge(id_map[e.source_client_id], id_map[e.target_client_id],
                   condition_expr=(e.branch or e.condition), label=e.label,
                   is_default=e.is_default, flow_kind=e.flow_kind, port_type=e.port_type)
             for e in diagram.edges
             if e.source_client_id in id_map and e.target_client_id in id_map]
    return nodes, edges, id_map


_BPMN_GATEWAY = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:kaori="http://kaori.ai/bpmn" id="D" targetNamespace="http://kaori.ai/bpmn">
  <bpmn:process id="P" isExecutable="true">
    <bpmn:startEvent id="Start"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
    <bpmn:exclusiveGateway id="Gw" name="Đủ điểm?" default="f_no"><bpmn:incoming>f0</bpmn:incoming></bpmn:exclusiveGateway>
    <bpmn:task id="Approve" name="Duyệt" kaori:nodeType="noop"/>
    <bpmn:task id="Reject" name="Từ chối" kaori:nodeType="noop"/>
    <bpmn:endEvent id="End"/>
    <bpmn:sequenceFlow id="f0" sourceRef="Start" targetRef="Gw"/>
    <bpmn:sequenceFlow id="f_yes" sourceRef="Gw" targetRef="Approve">
      <bpmn:conditionExpression>${score &gt;= 80}</bpmn:conditionExpression>
    </bpmn:sequenceFlow>
    <bpmn:sequenceFlow id="f_no" sourceRef="Gw" targetRef="Reject"/>
    <bpmn:sequenceFlow id="f_a" sourceRef="Approve" targetRef="End"/>
    <bpmn:sequenceFlow id="f_r" sourceRef="Reject" targetRef="End"/>
  </bpmn:process>
</bpmn:definitions>"""


@pytest.mark.asyncio
async def test_bpmn_gateway_end_to_end_true_arm(monkeypatch):
    """Author BPMN with an exclusive gateway → parse → run. Start/End events run
    as noop; the gateway condition routes to the matching arm; the other arm and
    end events all behave. Proves the whole BPMN→execution pipeline."""
    d = parse_bpmn_xml(_BPMN_GATEWAY)   # known=None → accept kaori:nodeType='noop'
    nodes, edges, idm = _diagram_to_runner(d)
    eid, wf = uuid4(), uuid4()
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                input_data={"score": 90})
    out = await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    assert out["status"] == "completed", out
    st = _by_node(rec, idm)
    assert st["Start"]["status"] == "completed"     # start event ran (noop)
    assert st["Gw"]["status"] == "completed"
    assert st["Approve"]["status"] == "completed"   # score>=80 → true arm
    assert st["Reject"]["status"] == "skipped"      # else arm pruned
    assert st["End"]["status"] == "completed"


@pytest.mark.asyncio
async def test_bpmn_gateway_end_to_end_false_arm(monkeypatch):
    d = parse_bpmn_xml(_BPMN_GATEWAY)
    nodes, edges, idm = _diagram_to_runner(d)
    eid, wf = uuid4(), uuid4()
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                input_data={"score": 40})
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st = _by_node(rec, idm)
    assert st["Reject"]["status"] == "completed"    # default arm
    assert st["Approve"]["status"] == "skipped"


# ─── data pipeline: filter → sort → aggregate ─────────────────────────────────

@pytest.mark.asyncio
async def test_data_pipeline_filter_sort_aggregate(monkeypatch):
    eid, wf = uuid4(), uuid4()
    F, S, A = uuid4(), uuid4(), uuid4()
    nodes = [
        _node(F, "filter", config={
            "rows": "$.input.rows",
            "condition": {"left": "$._row.amount", "op": ">=", "right": 100}}, seq=0),
        _node(S, "sort", config={"rows": f"$.{F}.rows", "by": "amount", "direction": "desc"}, seq=1),
        _node(A, "aggregate", config={"rows": f"$.{S}.rows", "metric": "amount", "fn": "sum"}, seq=2),
    ]
    edges = [_edge(F, S), _edge(S, A)]
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid,
                input_data={"rows": [{"amount": 50}, {"amount": 150}, {"amount": 200}]})
    out = await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    assert out["status"] == "completed", out
    st = _by_node(rec, {"F": F, "S": S, "A": A})
    assert st["F"]["output_data"]["dropped"] == 1          # 50 dropped
    assert st["S"]["output_data"]["rows"][0]["amount"] == 200   # desc sort
    assert st["A"]["output_data"]["groups"][0]["value"] == 350  # 150+200


# ─── audit-fix regression guards ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_flow_does_not_create_cycle(monkeypatch):
    """Bug #7: message flows were topo-sorted as 'main' edges. A sequence
    A→B plus a message flow B→A would be a false cycle → run failed. With the
    fix, message flows are excluded from ordering → no cycle."""
    eid, wf = uuid4(), uuid4()
    A, B = uuid4(), uuid4()
    nodes = [_node(A, "noop", seq=0), _node(B, "noop", seq=1)]
    edges = [_edge(A, B),                                  # sequence
             _edge(B, A, flow_kind="message")]            # cross-pool signal
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    assert out["status"] == "completed"                   # not "Cycle detected"
    st = _by_node(rec, {"A": A, "B": B})
    assert st["A"]["status"] == "completed" and st["B"]["status"] == "completed"


@pytest.mark.asyncio
async def test_typo_token_does_not_double_fire(monkeypatch):
    """Bug #1: an unrecognised token ('tru') on a decision arm used to fall
    through as a catch-all (live for both branches). Now it's dead."""
    eid, wf = uuid4(), uuid4()
    D, A, B = uuid4(), uuid4(), uuid4()
    nodes = [_node(D, "if_else", config={"condition": {"left": 1, "op": "<", "right": 2}}, seq=0),
             _node(A, "noop", seq=1), _node(B, "noop", seq=1)]
    edges = [_edge(D, A, condition_expr="tru"),     # typo of 'true'
             _edge(D, B, condition_expr="true")]
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st = _by_node(rec, {"A": A, "B": B})
    assert st["B"]["status"] == "completed"          # real 'true' arm
    assert st["A"]["status"] == "skipped"            # typo arm no longer fires


@pytest.mark.asyncio
async def test_untagged_decision_edge_is_dead(monkeypatch):
    """Bug #2: an edge with NO token off a decision used to always fire."""
    eid, wf = uuid4(), uuid4()
    D, A, B = uuid4(), uuid4(), uuid4()
    nodes = [_node(D, "if_else", config={"condition": {"left": 1, "op": "<", "right": 2}}, seq=0),
             _node(A, "noop", seq=1), _node(B, "noop", seq=1)]
    edges = [_edge(D, A),                             # no token
             _edge(D, B, condition_expr="true")]
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st = _by_node(rec, {"A": A, "B": B})
    assert st["B"]["status"] == "completed"
    assert st["A"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_decision_missing_branch_signal_fails_run(monkeypatch):
    """Bug #3/H: if an if_else executor returns no 'branch', the run must FAIL
    loud instead of firing every arm. We monkeypatch the registered executor."""
    from ai_orchestrator.workflow_runtime.node_executor import REGISTRY as _R

    class _NoBranch(NodeExecutor):
        node_type_key = "if_else"
        side_effect_class = SideEffectClass.PURE

        async def execute(self, ctx, config):
            return NodeResult(status="completed", output_data={"value": 1})

    monkeypatch.setitem(_R._by_key, "if_else", _NoBranch())
    eid, wf = uuid4(), uuid4()
    D, A = uuid4(), uuid4()
    d_node = _node(D, "if_else", config={"condition": {"left": 1, "op": "<", "right": 2}}, seq=0)
    d_node["type_version"] = 99   # force get_versioned to fall back to _by_key (our stub)
    nodes = [d_node, _node(A, "noop", seq=1)]
    edges = [_edge(D, A, condition_expr="true")]
    _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    assert out["status"] == "failed"
    assert "did not emit" in out["error"]


@pytest.mark.asyncio
async def test_join_requires_all_arms(monkeypatch):
    """Bug #5/G: a parallel join must wait for ALL incoming arms. If one arm is
    dead (pruned via an upstream decision), the join is skipped, not run on
    partial input."""
    eid, wf = uuid4(), uuid4()
    D, A, B, J = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [
        _node(D, "if_else", config={"condition": {"left": 1, "op": "<", "right": 2}}, seq=0),
        _node(A, "noop", seq=1),     # true arm
        _node(B, "noop", seq=1),     # false arm (will be pruned)
        _node(J, "join", config={"left_rows": [], "right_rows": []}, seq=2),
    ]
    edges = [_edge(D, A, condition_expr="true"), _edge(D, B, condition_expr="false"),
             _edge(A, J), _edge(B, J)]
    rec = _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    st = _by_node(rec, {"A": A, "B": B, "J": J})
    assert st["A"]["status"] == "completed"
    assert st["B"]["status"] == "skipped"
    assert st["J"]["status"] == "skipped"     # all() gate: B arm dead → join skipped


@pytest.mark.asyncio
async def test_node_reading_skipped_branch_fails_loud(monkeypatch):
    """Bug #17: a node that RUNS (live path) but references a node on a DEAD
    branch used to silently aggregate over []. Now require_rows fails loud."""
    eid, wf = uuid4(), uuid4()
    D, Live, Dead, Agg = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [
        _node(D, "if_else", config={"condition": {"left": 1, "op": "<", "right": 2}}, seq=0),
        _node(Live, "noop", seq=1),    # true arm runs
        _node(Dead, "noop", seq=1),    # false arm → skipped
        _node(Agg, "aggregate", config={"rows": f"$.{Dead}.rows",
              "metric": "x", "fn": "sum"}, seq=2),
    ]
    edges = [_edge(D, Live, condition_expr="true"), _edge(D, Dead, condition_expr="false"),
             _edge(Live, Agg)]   # Agg reachable via live arm → it RUNS
    _stub(monkeypatch, nodes=nodes, edges=edges, wf_id=wf, eid=eid)
    out = await WorkflowRunner().run(run_id=uuid4(), enterprise_id=eid)
    assert out["status"] == "failed"
    assert "skipped" in out["error"].lower()


# ─── approval whitespace-role guard (bug I) ───────────────────────────────────

@pytest.mark.asyncio
async def test_approval_rejects_whitespace_only_roles():
    from ai_orchestrator.workflow_runtime.executors.approval import ApprovalGateExecutor
    from ai_orchestrator.workflow_runtime.node_executor import NodeContext, NodeExecutorError

    ctx = NodeContext(enterprise_id=uuid4(), workspace_id=uuid4(), workflow_id=uuid4(),
                      run_id=uuid4(), node_id=uuid4(), user_id=None,
                      input_data={}, prior_outputs={})
    with pytest.raises(NodeExecutorError):
        await ApprovalGateExecutor().execute(ctx, {"approver_role": ["  ", "\t"]})
