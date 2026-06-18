"""Unit tests for the Qwen Workflow Advisor detectors + scoring (ADR-0040).

Pure — no DB, no LLM. Feeds hand-built `profile` dicts to the detectors and
asserts the deterministic findings + overall_health roll-up.
"""
from __future__ import annotations

from ai_orchestrator.reasoning.workflow_advisor import detectors, schema


def _node(node_id, **kw):
    base = {
        "node_id": node_id, "node_type": "step", "catalog_key": "log_action",
        "title": f"Bước {node_id}", "decision_config": {}, "is_terminal": False,
        "has_action": True, "is_approval_gate": False, "has_approver": False,
        "outgoing_count": 1, "expected_edges": None,
    }
    base.update(kw)
    return base


def _profile(nodes, edges=None, docs=None, runtime=None):
    return {
        "workflow_id": "wf", "name": "Test WF", "state": "draft",
        "nodes": nodes, "edges": edges or [], "doc_requirements": docs or [],
        "runtime": runtime,
    }


# ─── static detectors ────────────────────────────────────────────────────

def test_incomplete_step_flagged():
    p = _profile([_node("a", catalog_key=None, has_action=False)])
    out = detectors.detect_incomplete(p)
    assert len(out) == 1 and out[0]["category"] == "incomplete"
    assert out[0]["severity"] == "high"


def test_terminal_node_not_incomplete():
    p = _profile([_node("end", node_type="end", has_action=False, is_terminal=True)])
    assert detectors.detect_incomplete(p) == []


def test_branch_error_when_missing_outgoing():
    n = _node("d", node_type="decision_if_else", outgoing_count=1, expected_edges=2)
    out = detectors.detect_branch_errors(_profile([n]))
    assert len(out) == 1 and out[0]["category"] == "branch_error"


def test_branch_ok_when_enough_edges():
    n = _node("d", node_type="decision_if_else", outgoing_count=2, expected_edges=2)
    assert detectors.detect_branch_errors(_profile([n])) == []


def test_empty_approval_gate_flagged_compliance():
    g = _node("g", is_approval_gate=True, has_approver=False)
    out = detectors.detect_compliance(_profile([g]))
    assert len(out) == 1 and out[0]["category"] == "compliance"


def test_bound_approval_gate_ok():
    g = _node("g", is_approval_gate=True, has_approver=True)
    assert detectors.detect_compliance(_profile([g])) == []


def test_missing_required_doc():
    docs = [{"node_id": "a", "name_vi": "Đơn", "is_required": True, "has_current": False}]
    out = detectors.detect_missing_doc(_profile([_node("a")], docs=docs))
    assert len(out) == 1 and out[0]["category"] == "missing_doc"


def test_submitted_doc_not_flagged():
    docs = [{"node_id": "a", "name_vi": "Đơn", "is_required": True, "has_current": True}]
    assert detectors.detect_missing_doc(_profile([_node("a")], docs=docs)) == []


def test_redundant_consecutive_same_action():
    nodes = [_node("a", catalog_key="log_action"), _node("b", catalog_key="log_action")]
    edges = [{"source": "a", "target": "b", "is_default": False, "label": None}]
    out = detectors.detect_redundant(_profile(nodes, edges=edges))
    assert len(out) == 1 and out[0]["category"] == "redundant"


# ─── runtime detectors ─────────────────────────────────────────────────────

def test_dead_branch_after_enough_runs():
    rt = {"run_count": 5, "per_node": {"a": {"visits": 5, "failures": 0, "avg_ms": 10}}}
    nodes = [_node("a"), _node("b")]  # b never visited
    out = detectors.detect_dead_branch(_profile(nodes, runtime=rt))
    assert len(out) == 1 and out[0]["step_id"] == "b"


def test_dead_branch_suppressed_below_min_runs():
    rt = {"run_count": 1, "per_node": {"a": {"visits": 1, "failures": 0, "avg_ms": 10}}}
    nodes = [_node("a"), _node("b")]
    assert detectors.detect_dead_branch(_profile(nodes, runtime=rt)) == []


def test_no_action_on_path_when_visited_but_empty():
    rt = {"run_count": 2, "per_node": {"a": {"visits": 2, "failures": 0, "avg_ms": 5}}}
    nodes = [_node("a", catalog_key=None, has_action=False)]
    out = detectors.detect_no_action_on_path(_profile(nodes, runtime=rt))
    assert len(out) == 1 and out[0]["category"] == "no_action_on_path"


def test_bottleneck_high_failure_rate():
    rt = {"run_count": 4, "per_node": {"a": {"visits": 4, "failures": 3, "avg_ms": 10}}}
    out = detectors.detect_bottleneck(_profile([_node("a")], runtime=rt))
    assert len(out) == 1 and out[0]["category"] == "bottleneck"


# ─── scoring ───────────────────────────────────────────────────────────────

def test_overall_health_clean_is_one():
    assert schema.overall_health([]) == 1.0


def test_overall_health_drops_with_high_findings():
    f = [schema.finding(category="incomplete", severity="high", title="x",
                        detail="x", suggestion="x")]
    assert schema.overall_health(f) < 1.0


def test_run_all_clean_workflow_no_findings():
    # a complete, well-formed 2-step linear workflow
    nodes = [_node("a"), _node("b")]
    edges = [{"source": "a", "target": "b", "is_default": False, "label": None}]
    nodes[0]["catalog_key"] = "classify"  # different actions → not redundant
    nodes[1]["catalog_key"] = "log_action"
    assert detectors.run_all(_profile(nodes, edges=edges)) == []
