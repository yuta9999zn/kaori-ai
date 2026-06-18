"""Unit tests for workflow_runtime/bpmn_mapper.py.

Builder pivot 2026-05-29 (WORKFLOW_BUILDER_REDESIGN.md §11 / #9):
BPMN 2.0 XML ↔ Kaori workflow_nodes/edges. Pure transform — no DB, no app.

Covers: type resolution, executability vs design-only, sequenceFlow→edge,
gateway split/join refinement, conditions/labels, known_node_types filter,
DOCTYPE/malformed rejection, and a full parse→build→parse round-trip.
"""
from __future__ import annotations

import pytest

from ai_orchestrator.workflow_runtime.bpmn_mapper import (
    BpmnParseError,
    MappedEdge,
    MappedNode,
    build_bpmn_xml,
    is_executable,
    parse_bpmn_xml,
    resolve_node_type,
    summarize,
)


def _wrap(process_body: str, *, di: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:kaori="http://kaori.ai/bpmn"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  id="Definitions_1" targetNamespace="http://kaori.ai/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    {process_body}
  </bpmn:process>
  {di}
</bpmn:definitions>"""


# ── Pure type helpers ────────────────────────────────────────────────────────

class TestResolveAndExecutable:

    def test_kaori_nodetype_wins(self):
        assert resolve_node_type("bpmn:ServiceTask", "classify_text") == "classify_text"

    def test_gateway_structural_fallback(self):
        assert resolve_node_type("bpmn:ExclusiveGateway", None) == "if_else"
        assert resolve_node_type("bpmn:ParallelGateway", None) == "split"

    def test_task_without_nodetype_unresolved(self):
        assert resolve_node_type("bpmn:ServiceTask", None) is None

    def test_known_set_filters_typo_key(self):
        # Stale/typo kaori:nodeType outside the live catalog → ignored.
        known = {"classify_text", "send_email"}
        assert resolve_node_type("bpmn:ServiceTask", "clasify_txt", known) is None
        assert resolve_node_type("bpmn:ServiceTask", "classify_text", known) == "classify_text"

    def test_executable_task_needs_action(self):
        assert is_executable("bpmn:ServiceTask", "classify_text") is True
        assert is_executable("bpmn:ServiceTask", None) is False

    def test_gateways_and_events_executable_directly(self):
        assert is_executable("bpmn:ExclusiveGateway", None) is True
        assert is_executable("bpmn:StartEvent", None) is True

    def test_unknown_bpmn_type_not_executable(self):
        assert is_executable("bpmn:TextAnnotation", None) is False

    def test_plain_events_resolve_to_noop(self):
        # Bug #15/#16: a plain start/end event must resolve to a real executor
        # ('noop'), not None — else the runner fails "No executor for None".
        assert resolve_node_type("bpmn:StartEvent", None) == "noop"
        assert resolve_node_type("bpmn:EndEvent", None) == "noop"
        # an annotated start event still keeps its kaori action
        assert resolve_node_type("bpmn:StartEvent", "scheduled_trigger") == "scheduled_trigger"


# ── Parse ────────────────────────────────────────────────────────────────────

class TestParse:

    def test_linear_flow(self):
        xml = _wrap("""
          <bpmn:startEvent id="Start_1" name="Nhận lead">
            <bpmn:messageEventDefinition/>
            <bpmn:outgoing>Flow_1</bpmn:outgoing>
          </bpmn:startEvent>
          <bpmn:serviceTask id="Task_1" name="Phân loại" kaori:nodeType="classify_text">
            <bpmn:incoming>Flow_1</bpmn:incoming>
            <bpmn:outgoing>Flow_2</bpmn:outgoing>
          </bpmn:serviceTask>
          <bpmn:endEvent id="End_1" name="Xong">
            <bpmn:incoming>Flow_2</bpmn:incoming>
          </bpmn:endEvent>
          <bpmn:sequenceFlow id="Flow_1" sourceRef="Start_1" targetRef="Task_1"/>
          <bpmn:sequenceFlow id="Flow_2" sourceRef="Task_1" targetRef="End_1"/>
        """)
        d = parse_bpmn_xml(xml)
        assert len(d.nodes) == 3
        assert len(d.edges) == 2
        by_id = {n.client_id: n for n in d.nodes}
        assert by_id["Start_1"].is_trigger is True
        assert by_id["Start_1"].event_definition == "message"
        assert by_id["Task_1"].node_type == "classify_text"
        assert by_id["Task_1"].executable is True
        assert all(e.port_type == "main" for e in d.edges)
        # every node executable + has a trigger → no warnings
        assert d.warnings == []

    def test_exclusive_gateway_with_conditions(self):
        xml = _wrap("""
          <bpmn:exclusiveGateway id="Gw_1" name="Đủ điều kiện?">
            <bpmn:incoming>F0</bpmn:incoming>
            <bpmn:outgoing>F_yes</bpmn:outgoing>
            <bpmn:outgoing>F_no</bpmn:outgoing>
          </bpmn:exclusiveGateway>
          <bpmn:task id="A" name="A" kaori:nodeType="send_email"/>
          <bpmn:task id="B" name="B" kaori:nodeType="send_email"/>
          <bpmn:startEvent id="S" name="S"><bpmn:outgoing>F0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:sequenceFlow id="F0" sourceRef="S" targetRef="Gw_1"/>
          <bpmn:sequenceFlow id="F_yes" name="Có" sourceRef="Gw_1" targetRef="A">
            <bpmn:conditionExpression>${score &gt;= 80}</bpmn:conditionExpression>
          </bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="F_no" name="Không" sourceRef="Gw_1" targetRef="B"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        gw = next(n for n in d.nodes if n.client_id == "Gw_1")
        assert gw.node_type == "if_else"
        yes = next(e for e in d.edges if e.client_id == "F_yes")
        assert yes.label == "Có"
        assert "score" in yes.condition

    def test_parallel_gateway_join_by_degree(self):
        # Gw_split: 1 in / 2 out → split; Gw_join: 2 in / 1 out → join.
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:parallelGateway id="Gw_split"/>
          <bpmn:task id="A" kaori:nodeType="send_email"/>
          <bpmn:task id="B" kaori:nodeType="send_email"/>
          <bpmn:parallelGateway id="Gw_join"/>
          <bpmn:endEvent id="E"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="Gw_split"/>
          <bpmn:sequenceFlow id="f1" sourceRef="Gw_split" targetRef="A"/>
          <bpmn:sequenceFlow id="f2" sourceRef="Gw_split" targetRef="B"/>
          <bpmn:sequenceFlow id="f3" sourceRef="A" targetRef="Gw_join"/>
          <bpmn:sequenceFlow id="f4" sourceRef="B" targetRef="Gw_join"/>
          <bpmn:sequenceFlow id="f5" sourceRef="Gw_join" targetRef="E"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        by_id = {n.client_id: n for n in d.nodes}
        assert by_id["Gw_split"].node_type == "split"
        assert by_id["Gw_join"].node_type == "join"

    def test_non_executable_task_warns(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f</bpmn:outgoing></bpmn:startEvent>
          <bpmn:serviceTask id="T" name="Chưa gán"/>
          <bpmn:sequenceFlow id="f" sourceRef="S" targetRef="T"/>
        """)
        d = parse_bpmn_xml(xml)
        t = next(n for n in d.nodes if n.client_id == "T")
        assert t.executable is False
        assert any("Chưa gán" in w for w in d.warnings)

    def test_missing_start_event_warns(self):
        xml = _wrap("""
          <bpmn:task id="T" kaori:nodeType="send_email"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        assert any("điểm bắt đầu" in w for w in d.warnings)

    def test_reads_di_bounds(self):
        di = """
        <bpmndi:BPMNDiagram id="D"><bpmndi:BPMNPlane id="P" bpmnElement="Process_1">
          <bpmndi:BPMNShape id="T_di" bpmnElement="T">
            <dc:Bounds x="320" y="140" width="100" height="80"/>
          </bpmndi:BPMNShape>
        </bpmndi:BPMNPlane></bpmndi:BPMNDiagram>"""
        xml = _wrap("""<bpmn:task id="T" kaori:nodeType="send_email"/>""", di=di)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        t = next(n for n in d.nodes if n.client_id == "T")
        assert (t.position_x, t.position_y) == (320.0, 140.0)


class TestParseErrors:

    def test_empty_raises(self):
        with pytest.raises(BpmnParseError):
            parse_bpmn_xml("   ")

    def test_malformed_raises(self):
        with pytest.raises(BpmnParseError):
            parse_bpmn_xml("<bpmn:definitions><unclosed>")

    def test_doctype_rejected(self):
        bomb = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "x">]>'
                '<bpmn:definitions/>')
        with pytest.raises(BpmnParseError):
            parse_bpmn_xml(bomb)


# ── Round-trip ───────────────────────────────────────────────────────────────

class TestRoundTrip:

    def test_parse_build_parse_preserves_semantics(self):
        xml = _wrap("""
          <bpmn:startEvent id="S" name="Bắt đầu"><bpmn:outgoing>F0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:serviceTask id="T" name="Phân loại" kaori:nodeType="classify_text">
            <bpmn:incoming>F0</bpmn:incoming><bpmn:outgoing>F1</bpmn:outgoing>
          </bpmn:serviceTask>
          <bpmn:exclusiveGateway id="G" name="OK?">
            <bpmn:incoming>F1</bpmn:incoming>
            <bpmn:outgoing>F_y</bpmn:outgoing><bpmn:outgoing>F_n</bpmn:outgoing>
          </bpmn:exclusiveGateway>
          <bpmn:sendTask id="M" name="Gửi mail" kaori:nodeType="send_email"/>
          <bpmn:endEvent id="E"/>
          <bpmn:sequenceFlow id="F0" sourceRef="S" targetRef="T"/>
          <bpmn:sequenceFlow id="F1" sourceRef="T" targetRef="G"/>
          <bpmn:sequenceFlow id="F_y" name="Có" sourceRef="G" targetRef="M">
            <bpmn:conditionExpression>${ok}</bpmn:conditionExpression>
          </bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="F_n" name="Không" sourceRef="G" targetRef="E"/>
        """)
        known = {"classify_text", "send_email"}
        d1 = parse_bpmn_xml(xml, known_node_types=known)
        rebuilt = build_bpmn_xml(d1.nodes, d1.edges, process_name="Demo")
        d2 = parse_bpmn_xml(rebuilt, known_node_types=known)

        def norm(d):
            nodes = sorted(
                (n.client_id, n.bpmn_type, n.title, n.node_type, n.kaori_node_type)
                for n in d.nodes
            )
            edges = sorted(
                (e.source_client_id, e.target_client_id, e.label, e.condition, e.port_type)
                for e in d.edges
            )
            return nodes, edges

        assert norm(d1) == norm(d2)

    def test_summarize_counts(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f</bpmn:outgoing></bpmn:startEvent>
          <bpmn:serviceTask id="T1" kaori:nodeType="classify_text"/>
          <bpmn:serviceTask id="T2" name="design only"/>
          <bpmn:sequenceFlow id="f" sourceRef="S" targetRef="T1"/>
        """)
        s = summarize(parse_bpmn_xml(xml, known_node_types={"classify_text"}))
        assert s["node_count"] == 3
        assert s["edge_count"] == 1
        assert s["executable_count"] == 2   # start + T1 (T2 design-only)
        assert s["trigger_count"] == 1
        assert any("design only" in w for w in s["warnings"])


# ── Full-fidelity: pools/lanes, message flows, boundary, subprocess, etc ──────

def _collab(body: str) -> str:
    """Wrap a full collaboration (2 pools) + processes."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:kaori="http://kaori.ai/bpmn" id="Defs"
                  targetNamespace="http://kaori.ai/bpmn">
{body}
</bpmn:definitions>"""


class TestPoolsAndLanes:

    def test_pools_lanes_message_flow(self):
        xml = _collab("""
          <bpmn:collaboration id="C">
            <bpmn:participant id="P_sales" name="Phòng Sales" processRef="Proc_sales"/>
            <bpmn:participant id="P_cust" name="Khách hàng" processRef="Proc_cust"/>
            <bpmn:messageFlow id="MF1" name="Báo giá" sourceRef="T_quote" targetRef="T_recv"/>
          </bpmn:collaboration>
          <bpmn:process id="Proc_sales">
            <bpmn:laneSet>
              <bpmn:lane id="L_rep" name="Nhân viên">
                <bpmn:flowNodeRef>T_quote</bpmn:flowNodeRef>
              </bpmn:lane>
              <bpmn:lane id="L_mgr" name="Quản lý">
                <bpmn:flowNodeRef>G1</bpmn:flowNodeRef>
              </bpmn:lane>
            </bpmn:laneSet>
            <bpmn:sendTask id="T_quote" name="Gửi báo giá" kaori:nodeType="send_email"/>
            <bpmn:exclusiveGateway id="G1" name="Duyệt?"/>
          </bpmn:process>
          <bpmn:process id="Proc_cust">
            <bpmn:receiveTask id="T_recv" name="Nhận báo giá"/>
          </bpmn:process>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        by_id = {n.client_id: n for n in d.nodes}
        assert by_id["T_quote"].pool == "Phòng Sales"
        assert by_id["T_quote"].lane == "Nhân viên"
        assert by_id["G1"].lane == "Quản lý"
        assert by_id["T_recv"].pool == "Khách hàng"
        # message flow captured as a cross-pool edge
        mf = next(e for e in d.edges if e.flow_kind == "message")
        assert mf.label == "Báo giá"
        # pools surfaced in summary
        s = summarize(d)
        names = {p["name"] for p in s["pools"]}
        assert names == {"Phòng Sales", "Khách hàng"}
        assert s["message_flow_count"] == 1


class TestBoundaryAndSubprocess:

    def test_boundary_event_attached(self):
        xml = _wrap("""
          <bpmn:userTask id="T" name="Duyệt" kaori:nodeType="approval_gate"/>
          <bpmn:boundaryEvent id="B" name="Quá hạn" attachedToRef="T">
            <bpmn:timerEventDefinition/>
          </bpmn:boundaryEvent>
          <bpmn:startEvent id="S"><bpmn:outgoing>f</bpmn:outgoing></bpmn:startEvent>
          <bpmn:sequenceFlow id="f" sourceRef="S" targetRef="T"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"approval_gate"})
        b = next(n for n in d.nodes if n.client_id == "B")
        assert b.bpmn_type == "bpmn:BoundaryEvent"
        assert b.attached_to == "T"
        assert b.event_definition == "timer"

    def test_subprocess_children_recursed(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f</bpmn:outgoing></bpmn:startEvent>
          <bpmn:subProcess id="Sub" name="Xử lý con">
            <bpmn:task id="Inner" name="Bước trong" kaori:nodeType="send_email"/>
          </bpmn:subProcess>
          <bpmn:sequenceFlow id="f" sourceRef="S" targetRef="Sub"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        ids = {n.client_id for n in d.nodes}
        assert {"S", "Sub", "Inner"} <= ids
        inner = next(n for n in d.nodes if n.client_id == "Inner")
        assert inner.parent_id == "Sub"

    def test_default_flow_flagged(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:exclusiveGateway id="G" default="F_def"><bpmn:incoming>f0</bpmn:incoming></bpmn:exclusiveGateway>
          <bpmn:task id="A" kaori:nodeType="send_email"/>
          <bpmn:task id="B" kaori:nodeType="send_email"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="G"/>
          <bpmn:sequenceFlow id="F_cond" sourceRef="G" targetRef="A">
            <bpmn:conditionExpression>${x}</bpmn:conditionExpression>
          </bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="F_def" sourceRef="G" targetRef="B"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        defaults = [e.client_id for e in d.edges if e.is_default]
        assert defaults == ["F_def"]


class TestEventDefinitions:

    @pytest.mark.parametrize("tag,marker", [
        ("errorEventDefinition", "error"),
        ("escalationEventDefinition", "escalation"),
        ("compensateEventDefinition", "compensation"),
        ("cancelEventDefinition", "cancel"),
        ("terminateEventDefinition", "terminate"),
        ("signalEventDefinition", "signal"),
        ("linkEventDefinition", "link"),
    ])
    def test_end_event_definitions(self, tag, marker):
        xml = _wrap(f"""
          <bpmn:startEvent id="S"><bpmn:outgoing>f</bpmn:outgoing></bpmn:startEvent>
          <bpmn:endEvent id="E"><bpmn:{tag}/></bpmn:endEvent>
          <bpmn:sequenceFlow id="f" sourceRef="S" targetRef="E"/>
        """)
        d = parse_bpmn_xml(xml)
        e = next(n for n in d.nodes if n.client_id == "E")
        assert e.event_definition == marker
        assert e.is_throw is True

    def test_structural_type_buckets(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import structural_type_for
        assert structural_type_for("bpmn:ExclusiveGateway") == "decision_if_else"
        assert structural_type_for("bpmn:InclusiveGateway") == "decision_switch"
        assert structural_type_for("bpmn:ParallelGateway") == "parallel_split"
        assert structural_type_for("bpmn:SendTask") == "notification"
        assert structural_type_for("bpmn:CallActivity") == "subworkflow"
        assert structural_type_for("bpmn:UserTask", "approval_gate") == "approval_gate"
        assert structural_type_for("bpmn:ServiceTask", "classify_text") == "step"


# ── Gateway condition → if_else config ───────────────────────────────────────

class TestConditionExpressionParse:

    def test_strips_juel_wrapper_and_parses_comparison(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("${score >= 80}") == {
            "left": "$.input.score", "op": ">=", "right": 80}

    def test_string_and_eq_normalisation(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("tier = 'gold'") == {
            "left": "$.input.tier", "op": "==", "right": "gold"}

    def test_bool_and_float_operands(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("active != false")["right"] is False
        assert parse_condition_expression("ratio < 0.5")["right"] == 0.5

    def test_existing_ref_left_kept(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("$.n1.amount > 100")["left"] == "$.n1.amount"

    def test_quoted_string_with_operator_inside(self):
        # Bug #9: '>' inside the quoted literal must not be the split point.
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression('name == "John > Mary"') == {
            "left": "$.input.name", "op": "==", "right": "John > Mary"}

    def test_compound_and(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("${score >= 80 and tier == 'gold'}") == {
            "and": [
                {"left": "$.input.score", "op": ">=", "right": 80},
                {"left": "$.input.tier", "op": "==", "right": "gold"},
            ]
        }

    def test_compound_or(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("a == 1 or a == 2") == {
            "or": [
                {"left": "$.input.a", "op": "==", "right": 1},
                {"left": "$.input.a", "op": "==", "right": 2},
            ]
        }

    def test_or_binds_looser_than_and(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        # a and b or c  →  {or: [{and:[a,b]}, c]}
        out = parse_condition_expression("x > 1 and y < 2 or z == 3")
        assert "or" in out and len(out["or"]) == 2
        assert "and" in out["or"][0]
        assert out["or"][1] == {"left": "$.input.z", "op": "==", "right": 3}

    def test_unparseable_return_none(self):
        from ai_orchestrator.workflow_runtime.bpmn_mapper import parse_condition_expression
        assert parse_condition_expression("doSomething()") is None
        assert parse_condition_expression("") is None
        # compound where one leaf is unparseable → whole thing None
        assert parse_condition_expression("score > 5 and doStuff()") is None


class TestGatewaySwitchLift:

    def _wrap3(self, conds):
        """Exclusive gateway with 3 conditional flows + default."""
        flows = "".join(
            f'<bpmn:sequenceFlow id="F{i}" sourceRef="G" targetRef="T{i}">'
            f'<bpmn:conditionExpression>{c}</bpmn:conditionExpression></bpmn:sequenceFlow>'
            f'<bpmn:task id="T{i}" kaori:nodeType="send_email"/>'
            for i, c in enumerate(conds)
        )
        return _wrap(f"""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:exclusiveGateway id="G" name="Hạng?" default="F_def">
            <bpmn:incoming>f0</bpmn:incoming></bpmn:exclusiveGateway>
          <bpmn:task id="Tdef" kaori:nodeType="send_email"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="G"/>
          {flows}
          <bpmn:sequenceFlow id="F_def" sourceRef="G" targetRef="Tdef"/>
        """)

    def test_uniform_equality_becomes_switch(self):
        xml = self._wrap3(["${tier == 'gold'}", "${tier == 'silver'}", "${tier == 'bronze'}"])
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        g = next(n for n in d.nodes if n.client_id == "G")
        assert g.node_type == "switch"
        assert g.structural_type == "decision_switch"
        assert g.config["input"] == "$.input.tier"
        assert {c["when"] for c in g.config["cases"]} == {"gold", "silver", "bronze"}
        # each case arm tagged with its value; default arm tagged 'default'
        tokens = {e.client_id: e.branch for e in d.edges if e.branch}
        assert tokens["F0"] == "gold" and tokens["F_def"] == "default"

    def test_non_uniform_conditions_warn_not_switch(self):
        # ranges on a var → not '==' uniform → stays a gateway, warns
        xml = self._wrap3(["${score > 80}", "${score > 50}", "${score > 0}"])
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        g = next(n for n in d.nodes if n.client_id == "G")
        assert g.config == {}
        assert any("không đồng nhất" in w for w in d.warnings)

    def test_inclusive_gateway_uniform_equality_switch(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:inclusiveGateway id="G" default="F_def"><bpmn:incoming>f0</bpmn:incoming></bpmn:inclusiveGateway>
          <bpmn:task id="A" kaori:nodeType="send_email"/>
          <bpmn:task id="B" kaori:nodeType="send_email"/>
          <bpmn:task id="C" kaori:nodeType="send_email"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="G"/>
          <bpmn:sequenceFlow id="Fa" sourceRef="G" targetRef="A"><bpmn:conditionExpression>${region == 'north'}</bpmn:conditionExpression></bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="Fb" sourceRef="G" targetRef="B"><bpmn:conditionExpression>${region == 'south'}</bpmn:conditionExpression></bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="F_def" sourceRef="G" targetRef="C"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        g = next(n for n in d.nodes if n.client_id == "G")
        assert g.node_type == "switch"
        assert g.config["input"] == "$.input.region"


class TestGatewayConditionLift:

    def test_exclusive_gateway_condition_lifted_to_if_else_config(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:exclusiveGateway id="G" name="Đủ điểm?" default="F_def">
            <bpmn:incoming>f0</bpmn:incoming>
          </bpmn:exclusiveGateway>
          <bpmn:task id="A" name="Duyệt" kaori:nodeType="send_email"/>
          <bpmn:task id="B" name="Từ chối" kaori:nodeType="send_email"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="G"/>
          <bpmn:sequenceFlow id="F_cond" sourceRef="G" targetRef="A">
            <bpmn:conditionExpression>${score &gt;= 80}</bpmn:conditionExpression>
          </bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="F_def" sourceRef="G" targetRef="B"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        g = next(n for n in d.nodes if n.client_id == "G")
        assert g.node_type == "if_else"
        assert g.config == {"condition": {"left": "$.input.score", "op": ">=", "right": 80}}
        cond = next(e for e in d.edges if e.client_id == "F_cond")
        deflt = next(e for e in d.edges if e.client_id == "F_def")
        assert cond.branch == "true"
        assert deflt.branch == "false"

    def test_two_way_both_conditions_no_default(self):
        # Bug #10: a 2-way exclusive gateway where BOTH arms carry a condition
        # (no default) must still become an if_else with true/false tokens —
        # otherwise both arms fired at runtime.
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:exclusiveGateway id="G"><bpmn:incoming>f0</bpmn:incoming></bpmn:exclusiveGateway>
          <bpmn:task id="A" kaori:nodeType="send_email"/>
          <bpmn:task id="B" kaori:nodeType="send_email"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="G"/>
          <bpmn:sequenceFlow id="Fhi" sourceRef="G" targetRef="A"><bpmn:conditionExpression>${score &gt;= 80}</bpmn:conditionExpression></bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="Flo" sourceRef="G" targetRef="B"><bpmn:conditionExpression>${score &lt; 80}</bpmn:conditionExpression></bpmn:sequenceFlow>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        g = next(n for n in d.nodes if n.client_id == "G")
        assert g.node_type == "if_else"
        assert g.config == {"condition": {"left": "$.input.score", "op": ">=", "right": 80}}
        tokens = {e.client_id: e.branch for e in d.edges}
        assert tokens["Fhi"] == "true" and tokens["Flo"] == "false"

    def test_unparseable_condition_warns_keeps_raw(self):
        xml = _wrap("""
          <bpmn:startEvent id="S"><bpmn:outgoing>f0</bpmn:outgoing></bpmn:startEvent>
          <bpmn:exclusiveGateway id="G" default="F_def"><bpmn:incoming>f0</bpmn:incoming></bpmn:exclusiveGateway>
          <bpmn:task id="A" kaori:nodeType="send_email"/>
          <bpmn:task id="B" kaori:nodeType="send_email"/>
          <bpmn:sequenceFlow id="f0" sourceRef="S" targetRef="G"/>
          <bpmn:sequenceFlow id="F_cond" sourceRef="G" targetRef="A">
            <bpmn:conditionExpression>${complexFn(x) and y}</bpmn:conditionExpression>
          </bpmn:sequenceFlow>
          <bpmn:sequenceFlow id="F_def" sourceRef="G" targetRef="B"/>
        """)
        d = parse_bpmn_xml(xml, known_node_types={"send_email"})
        g = next(n for n in d.nodes if n.client_id == "G")
        assert g.config == {}                       # not lifted
        assert any("chưa parse" in w for w in d.warnings)
        cond = next(e for e in d.edges if e.client_id == "F_cond")
        assert cond.branch is None                  # raw condition kept on edge


import re as _re


class TestSwimlaneLayout:
    """build_bpmn_xml DI layout for cross-functional (multi-lane) flows."""

    def _N(self, cid, title, bt="bpmn:Task"):
        return MappedNode(client_id=cid, bpmn_type=bt, title=title,
                          node_type=None, structural_type="step", executable=True)

    def test_lanes_reordered_by_flow_so_staircase_is_monotonic(self):
        # A procurement flow that visits lanes in the order
        # Thu mua → QA → Kho → Kế toán, but whose lanes are SUPPLIED in a
        # different order (Kế toán before QA/Kho). The DI must reorder lanes
        # by flow progression so the cross-lane flow descends monotonically
        # (no edge zig-zagging back up — the main source of crossings).
        nodes = [
            self._N("S", "Bắt đầu", "bpmn:StartEvent"),
            self._N("quote", "Báo giá"),
            self._N("sign", "Ký hợp đồng"),
            self._N("qa", "Nhận hàng + QA"),
            self._N("stock", "Nhập kho"),
            self._N("pay", "Thanh toán"),
            self._N("E", "Kết thúc", "bpmn:EndEvent"),
        ]
        seq = [("S", "quote"), ("quote", "sign"), ("sign", "qa"),
               ("qa", "stock"), ("stock", "pay"), ("pay", "E")]
        edges = [MappedEdge(client_id=f"f{i}", source_client_id=a, target_client_id=b)
                 for i, (a, b) in enumerate(seq)]
        lanes = [
            ("Thu mua", ["S", "quote", "sign"]),
            ("Kế toán", ["pay", "E"]),          # supplied early, but used last
            ("QA", ["qa"]),
            ("Kho", ["stock"]),
        ]
        xml = build_bpmn_xml(nodes, edges, process_name="Thu mua", lanes=lanes)

        # Lanes emitted in flow order, not supply order.
        order = _re.findall(r'<bpmn:lane [^>]*name="([^"]*)"', xml)
        assert order == ["Thu mua", "QA", "Kho", "Kế toán"], order

        # Node Y by flow sequence must be non-decreasing (clean staircase).
        ys = {m.group(1): int(m.group(2)) for m in _re.finditer(
            r'BPMNShape[^>]*bpmnElement="([^"]+)"[^>]*>\s*<dc:Bounds x="[\-\d]+" y="([\-\d]+)"', xml)}
        flow_y = [ys[c] for c in ["S", "quote", "sign", "qa", "stock", "pay", "E"]]
        assert flow_y == sorted(flow_y), flow_y
