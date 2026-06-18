"""Tests for ADR-0035 B5 — typed connection ports in the runner: topo-sort
follows only 'main' edges; ai_* edges are side connections surfaced via
WorkflowRunner.side_connections. Static methods → no DB needed.
"""
from uuid import uuid4

from ai_orchestrator.workflow_runtime.runner import WorkflowRunner, WorkflowSnapshot


def _snap(nodes, edges):
    return WorkflowSnapshot(workflow_id=uuid4(), enterprise_id=uuid4(),
                            workspace_id=None, nodes=nodes, edges=edges)


def _order(nodes, edges):
    return [n["node_id"] for n in WorkflowRunner.topological_order(_snap(nodes, edges))]


# ── topo-sort follows only 'main' edges ──────────────────────────────────────

def test_main_edge_orders_flow():
    a, b = uuid4(), uuid4()
    nodes = [{"node_id": a, "sequence_order": 1}, {"node_id": b, "sequence_order": 2}]
    order = _order(nodes, [{"source_node_id": a, "target_node_id": b, "port_type": "main"}])
    assert order == [a, b]


def test_missing_port_type_defaults_main():
    a, b = uuid4(), uuid4()
    nodes = [{"node_id": a, "sequence_order": 1}, {"node_id": b, "sequence_order": 2}]
    order = _order(nodes, [{"source_node_id": a, "target_node_id": b}])   # no port_type
    assert order == [a, b]


def test_ai_tool_edge_not_a_flow_step():
    agent, tool, nxt = uuid4(), uuid4(), uuid4()
    nodes = [{"node_id": agent, "sequence_order": 1},
             {"node_id": tool, "sequence_order": 2},
             {"node_id": nxt, "sequence_order": 3}]
    edges = [
        {"source_node_id": agent, "target_node_id": nxt, "port_type": "main"},
        {"source_node_id": tool, "target_node_id": agent, "port_type": "ai_tool"},
    ]
    order = _order(nodes, edges)
    assert set(order) == {agent, tool, nxt}        # every node still scheduled
    assert order.index(agent) < order.index(nxt)   # main flow preserved
    # the ai_tool edge added NO ordering constraint between tool and agent
    # (agent has zero main-indegree → not forced after tool)


# ── side_connections surfaces typed ports for an agent node ──────────────────

def test_side_connections_groups_by_port_excluding_main():
    agent, t1, t2, mem, prev = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    edges = [
        {"source_node_id": t1, "target_node_id": agent, "port_type": "ai_tool"},
        {"source_node_id": t2, "target_node_id": agent, "port_type": "ai_tool"},
        {"source_node_id": mem, "target_node_id": agent, "port_type": "ai_memory"},
        {"source_node_id": prev, "target_node_id": agent, "port_type": "main"},
    ]
    conns = WorkflowRunner.side_connections(edges, agent)
    assert set(conns["ai_tool"]) == {str(t1), str(t2)}
    assert conns["ai_memory"] == [str(mem)]
    assert "main" not in conns                     # flow edges aren't side connections


def test_side_connections_empty_for_plain_node():
    a, b = uuid4(), uuid4()
    edges = [{"source_node_id": a, "target_node_id": b, "port_type": "main"}]
    assert WorkflowRunner.side_connections(edges, b) == {}
