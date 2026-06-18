"""BPMN 2.0 XML ↔ Kaori workflow_nodes/edges mapper.

Builder pivot 2026-05-29 (WORKFLOW_BUILDER_REDESIGN.md §11):
  Tầng 1  BPMN (bpmn-js)        = diagram source-of-truth (BPMN 2.0 XML)
  Tầng 2  engine Kaori (runner) = executes workflow_nodes/edges

The bpmn-js editor stores BPMN XML on ``workflows.bpmn_xml`` (mig 115). The
runner only understands nodes + edges, so this module is the two-way bridge:

  parse_bpmn_xml(xml)  → MappedDiagram(nodes, edges, pools, warnings)
  build_bpmn_xml(...)  → BPMN 2.0 XML (inverse, for round-trip / export)

It is a **pure** transform — no DB, no I/O — so it stays trivially testable
and safe to call inside a request.

Coverage (full-fidelity per OMG BPMN 2.0.2 spec, formal/2013-12-09):
  • Collaboration → Pool (participant) + Lane (role)  §9.3 / §10.8
  • Message Flow between pools                          §9.4
  • All Tasks / Sub-Process (recursed) / Call Activity  §10.3
  • Start / Intermediate (catch+throw) / End / Boundary §10.5
  • All event definitions (message/timer/conditional/   §10.5.5
    signal/error/escalation/compensation/cancel/
    terminate/link/multiple/parallelMultiple)
  • Exclusive / Inclusive / Parallel / Complex /        §10.6
    Event-Based gateways (+ ``default`` flow)
Out of scope (drawable in bpmn-js, NOT executed): Conversation §9.5,
Choreography §11, data objects/stores, artifacts (group/text annotation).

The structural maps below MIRROR the FE catalog
``frontend/lib/bpmn/bpmn-elements.ts`` (Approach A) — keep the two in sync.
The 45 executable action keys are NOT hardcoded here; node_type_catalog (DB)
stays source of truth — callers pass the live key set via ``known_node_types``.

bpmn-js / Camunda-moddle name element types as ``bpmn:PascalCase`` (e.g.
``bpmn:ServiceTask``) while the XML element local-name is camelCase
(``serviceTask``). We normalise XML local-names to the ``bpmn:`` form so the
maps match the FE catalog exactly.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

# BPMN 2.0 namespaces.
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
# Kaori extension namespace — carries kaori:nodeType on task carriers.
KAORI_NS = "http://kaori.ai/bpmn"

# ── Structural maps — MIRROR frontend/lib/bpmn/bpmn-elements.ts ──────────────
# Structural BPMN elements (gateways) → node_type when no kaori:nodeType is set.
BPMN_TO_NODETYPE: dict[str, str] = {
    "bpmn:ExclusiveGateway": "if_else",
    "bpmn:InclusiveGateway": "switch",
    "bpmn:ParallelGateway": "split",   # refined to 'join' by in/out degree
    "bpmn:ComplexGateway": "switch",
    "bpmn:EventBasedGateway": "switch",
    # Flow markers with no Kaori action → no-op pass-through, so a plain
    # start/end/intermediate/boundary event doesn't fail the run with
    # "No executor for node_type_key=None". A start event annotated with a
    # kaori:nodeType (e.g. scheduled_trigger) still wins via resolve_node_type.
    "bpmn:StartEvent": "noop",
    "bpmn:EndEvent": "noop",
    "bpmn:IntermediateThrowEvent": "noop",
    "bpmn:IntermediateCatchEvent": "noop",
    "bpmn:BoundaryEvent": "noop",
}

# BPMN element types Kaori can execute (outside this set = design-only).
EXECUTABLE_BPMN_TYPES: frozenset[str] = frozenset({
    "bpmn:Task", "bpmn:ServiceTask", "bpmn:SendTask", "bpmn:ReceiveTask",
    "bpmn:UserTask", "bpmn:BusinessRuleTask", "bpmn:ScriptTask", "bpmn:ManualTask",
    "bpmn:ExclusiveGateway", "bpmn:InclusiveGateway", "bpmn:ParallelGateway",
    "bpmn:ComplexGateway", "bpmn:EventBasedGateway",
    "bpmn:StartEvent", "bpmn:EndEvent", "bpmn:IntermediateCatchEvent",
    "bpmn:IntermediateThrowEvent", "bpmn:BoundaryEvent",
    "bpmn:CallActivity", "bpmn:SubProcess",
})

# Structural node_type enum (workflow_nodes CHECK, mig 060) we map onto when
# persisting. Coarse buckets — the real BPMN type is preserved on bpmn_type.
_STRUCTURAL_TYPES = frozenset({
    "step", "decision_if_else", "decision_switch", "approval_gate",
    "wait_event", "sla_timer", "parallel_split", "parallel_join",
    "subworkflow", "notification",
})

# XML local-names we treat as flow nodes.
_TASK_LOCALS = {
    "task", "serviceTask", "sendTask", "receiveTask", "userTask",
    "businessRuleTask", "scriptTask", "manualTask", "callActivity",
    "subProcess", "transaction", "adHocSubProcess",
}
_EVENT_LOCALS = {
    "startEvent", "endEvent", "intermediateCatchEvent",
    "intermediateThrowEvent", "boundaryEvent",
}
_GATEWAY_LOCALS = {
    "exclusiveGateway", "inclusiveGateway", "parallelGateway",
    "complexGateway", "eventBasedGateway",
}
_NODE_LOCALS = _TASK_LOCALS | _EVENT_LOCALS | _GATEWAY_LOCALS
# Containers we recurse into (their own element is also a node).
_CONTAINER_LOCALS = {"subProcess", "transaction", "adHocSubProcess"}

# Event-definition child local-name → marker token.
_EVENT_DEF_MARKERS = {
    "timerEventDefinition": "timer",
    "messageEventDefinition": "message",
    "signalEventDefinition": "signal",
    "conditionalEventDefinition": "conditional",
    "errorEventDefinition": "error",
    "escalationEventDefinition": "escalation",
    "compensateEventDefinition": "compensation",
    "cancelEventDefinition": "cancel",
    "terminateEventDefinition": "terminate",
    "linkEventDefinition": "link",
}


class BpmnParseError(ValueError):
    """Raised when the supplied string is not parseable BPMN 2.0 XML."""


@dataclass
class MappedNode:
    """A BPMN flow element mapped onto the Kaori node shape.

    ``node_type`` = node_type_catalog_key (executor key) when known, else the
    structural fallback, else None (design-only). ``structural_type`` is the
    coarse workflow_nodes.node_type enum bucket used when persisting.
    ``client_id`` mirrors the workflow_template definition convention.
    """
    client_id: str
    bpmn_type: str
    title: str
    node_type: Optional[str]
    structural_type: str
    executable: bool
    kaori_node_type: Optional[str] = None
    event_definition: Optional[str] = None      # timer | message | error | …
    is_trigger: bool = False
    is_throw: bool = False
    pool: Optional[str] = None                   # participant (organisation/system)
    lane: Optional[str] = None                   # role within the pool
    attached_to: Optional[str] = None            # host id for boundaryEvent
    parent_id: Optional[str] = None              # containing sub-process id
    position_x: float = 0.0
    position_y: float = 0.0
    # Executor config derived from the diagram (e.g. if_else gateway → the
    # condition parsed from its outgoing flow). Persisted to workflow_nodes.config.
    config: dict = field(default_factory=dict)


@dataclass
class MappedEdge:
    """A BPMN sequenceFlow / messageFlow mapped onto the Kaori edge shape."""
    client_id: str
    source_client_id: str
    target_client_id: str
    condition: Optional[str] = None              # raw BPMN conditionExpression text
    label: Optional[str] = None
    port_type: str = "main"                      # ADR-0035 — always 'main'
    flow_kind: str = "sequence"                  # sequence | message (cross-pool)
    is_default: bool = False                     # gateway/activity default branch
    # Runner branch token ('true'/'false'/case) — set when a gateway condition is
    # lifted into the decision node's config. The runner's branch-gating matches
    # this; the raw expression moves to the node config. None = use `condition`.
    branch: Optional[str] = None


@dataclass
class MappedPool:
    pool_id: str
    name: str
    lanes: list[dict] = field(default_factory=list)   # [{"id","name"}]


@dataclass
class MappedDiagram:
    nodes: list[MappedNode] = field(default_factory=list)
    edges: list[MappedEdge] = field(default_factory=list)
    pools: list[MappedPool] = field(default_factory=list)
    # Human-readable VN warnings for design-only elements + structural problems.
    warnings: list[str] = field(default_factory=list)


# ── Type helpers ─────────────────────────────────────────────────────────────

def _to_bpmn_type(local_name: str) -> str:
    """serviceTask → bpmn:ServiceTask (bpmn-js / moddle naming)."""
    if not local_name:
        return ""
    return "bpmn:" + local_name[0].upper() + local_name[1:]


def _local(tag: str) -> str:
    """Strip the {namespace} prefix ET puts on tags."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def resolve_node_type(
    bpmn_type: str,
    kaori_node_type: Optional[str] = None,
    known_node_types: Optional[set[str]] = None,
) -> Optional[str]:
    """node_type_catalog_key for a BPMN element (kaori:nodeType wins).

    When ``known_node_types`` is given (live node_type_catalog keys), a
    kaori:nodeType outside it is ignored and we fall back to the structural
    map — so a stale/typo'd extension never produces a phantom executor key.
    """
    if kaori_node_type and (known_node_types is None or kaori_node_type in known_node_types):
        return kaori_node_type
    return BPMN_TO_NODETYPE.get(bpmn_type)


def is_executable(
    bpmn_type: str,
    kaori_node_type: Optional[str] = None,
    known_node_types: Optional[set[str]] = None,
) -> bool:
    """Can Kaori run this element (vs. design-only)? Mirrors FE isExecutable()."""
    if bpmn_type not in EXECUTABLE_BPMN_TYPES:
        return False
    is_task_carrier = (
        bpmn_type.endswith("Task")
        or bpmn_type in ("bpmn:CallActivity", "bpmn:SubProcess")
    )
    if is_task_carrier:
        return bool(
            kaori_node_type
            and (known_node_types is None or kaori_node_type in known_node_types)
        )
    return True  # gateway / event map directly


def structural_type_for(bpmn_type: str, kaori_node_type: Optional[str] = None) -> str:
    """Map a BPMN element onto the coarse workflow_nodes.node_type enum bucket.

    The exact BPMN type is preserved separately (bpmn_type column); this only
    feeds the legacy structural CHECK constraint (mig 060).
    """
    if bpmn_type == "bpmn:ParallelGateway":
        return "parallel_split"   # refined to parallel_join by degree later
    if bpmn_type == "bpmn:ExclusiveGateway":
        return "decision_if_else"
    if bpmn_type in ("bpmn:InclusiveGateway", "bpmn:ComplexGateway", "bpmn:EventBasedGateway"):
        return "decision_switch"
    if bpmn_type in ("bpmn:ReceiveTask", "bpmn:IntermediateCatchEvent"):
        return "wait_event"
    if bpmn_type == "bpmn:SendTask":
        return "notification"
    if bpmn_type in ("bpmn:CallActivity", "bpmn:SubProcess"):
        return "subworkflow"
    if bpmn_type == "bpmn:UserTask" and kaori_node_type in ("approval_gate", "create_task"):
        return "approval_gate"
    if kaori_node_type == "approval_gate":
        return "approval_gate"
    return "step"


# ── Parse ─────────────────────────────────────────────────────────────────────

def parse_bpmn_xml(
    xml: str,
    known_node_types: Optional[set[str]] = None,
) -> MappedDiagram:
    """Parse BPMN 2.0 XML → MappedDiagram(nodes, edges, pools, warnings).

    Reads collaboration (pools/participants + message flows) and every process
    (incl. nested sub-processes). Each non-flow element becomes a node tagged
    with its pool/lane; sequenceFlow → 'main' sequence edge; messageFlow →
    cross-pool 'message' edge. Elements Kaori can't execute add a warning
    instead of being dropped. Raises BpmnParseError on malformed XML.
    """
    if not xml or not xml.strip():
        raise BpmnParseError("empty BPMN XML")
    # Cheap hardening against XML-entity expansion (billion-laughs) — the
    # builder never emits a DOCTYPE, so refuse one rather than pull in a dep.
    if re.search(r"<!(DOCTYPE|ENTITY)", xml, re.IGNORECASE):
        raise BpmnParseError("DOCTYPE/ENTITY declarations not allowed in BPMN XML")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise BpmnParseError(f"invalid BPMN XML: {exc}") from exc

    diagram = MappedDiagram()

    # 1. DI bounds (bpmnElement → (x, y)).
    bounds: dict[str, tuple[float, float]] = {}
    for shape in root.iter(f"{{{BPMNDI_NS}}}BPMNShape"):
        ref = shape.get("bpmnElement")
        b = shape.find(f"{{{DC_NS}}}Bounds")
        if ref and b is not None:
            try:
                bounds[ref] = (float(b.get("x", 0)), float(b.get("y", 0)))
            except (TypeError, ValueError):
                pass

    # 2. Collaboration → pools + participant.processRef + message flows.
    process_pool: dict[str, str] = {}   # processRef id → pool display name
    raw_message_flows: list[ET.Element] = []
    for collab in root.iter(f"{{{BPMN_NS}}}collaboration"):
        for part in collab.findall(f"{{{BPMN_NS}}}participant"):
            pname = (part.get("name") or part.get("id") or "").strip()
            proc_ref = part.get("processRef")
            pool = MappedPool(pool_id=part.get("id") or pname, name=pname)
            diagram.pools.append(pool)
            if proc_ref:
                process_pool[proc_ref] = pname
        raw_message_flows.extend(collab.findall(f"{{{BPMN_NS}}}messageFlow"))

    # 3. Walk every top-level process (recurse sub-processes ourselves).
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    valid_ids: set[str] = set()
    default_flow_ids: set[str] = set()
    raw_edges: list[MappedEdge] = []

    def _walk(container: ET.Element, pool_name: Optional[str],
              lane_of: dict[str, str], parent_id: Optional[str]) -> None:
        for el in list(container):
            local = _local(el.tag)
            el_id = el.get("id")
            if local == "sequenceFlow":
                src, tgt = el.get("sourceRef"), el.get("targetRef")
                if not src or not tgt:
                    diagram.warnings.append(
                        f"Bỏ qua luồng '{el_id}' thiếu source/target.")
                    continue
                cond_el = el.find(f"{{{BPMN_NS}}}conditionExpression")
                condition = (cond_el.text or "").strip() if cond_el is not None else None
                raw_edges.append(MappedEdge(
                    client_id=el_id or f"{src}->{tgt}",
                    source_client_id=src, target_client_id=tgt,
                    condition=condition or None,
                    label=(el.get("name") or "").strip() or None,
                ))
                out_degree[src] = out_degree.get(src, 0) + 1
                in_degree[tgt] = in_degree.get(tgt, 0) + 1
                continue
            if local in ("laneSet", "extensionElements", "ioSpecification",
                         "documentation"):
                continue
            if local not in _NODE_LOCALS:
                # dataObject / dataStoreReference / textAnnotation / group /
                # association / etc. — drawable, not a flow node. Skip quietly.
                continue
            if not el_id:
                continue

            valid_ids.add(el_id)
            bpmn_type = _to_bpmn_type(local)
            kaori_nt = el.get(f"{{{KAORI_NS}}}nodeType")
            node_type = resolve_node_type(bpmn_type, kaori_nt, known_node_types)
            stype = structural_type_for(bpmn_type, kaori_nt)
            px, py = bounds.get(el_id, (0.0, 0.0))
            default_ref = el.get("default")
            if default_ref:
                default_flow_ids.add(default_ref)
            diagram.nodes.append(MappedNode(
                client_id=el_id,
                bpmn_type=bpmn_type,
                title=(el.get("name") or "").strip() or el_id,
                node_type=node_type,
                structural_type=stype,
                executable=is_executable(bpmn_type, kaori_nt, known_node_types),
                kaori_node_type=kaori_nt,
                event_definition=_event_marker(el),
                is_trigger=(local == "startEvent"),
                is_throw=(local in ("endEvent", "intermediateThrowEvent")),
                pool=pool_name,
                lane=lane_of.get(el_id),
                attached_to=el.get("attachedToRef") if local == "boundaryEvent" else None,
                parent_id=parent_id,
                position_x=px, position_y=py,
            ))
            # Recurse into sub-process containers.
            if local in _CONTAINER_LOCALS:
                _walk(el, pool_name, lane_of, el_id)

    for proc in root.findall(f"{{{BPMN_NS}}}process"):
        proc_id = proc.get("id") or ""
        pool_name = process_pool.get(proc_id)
        # lane membership: flowNodeRef under each lane.
        lane_of: dict[str, str] = {}
        for lane_set in proc.iter(f"{{{BPMN_NS}}}lane"):
            lname = (lane_set.get("name") or lane_set.get("id") or "").strip()
            for ref in lane_set.findall(f"{{{BPMN_NS}}}flowNodeRef"):
                if ref.text:
                    lane_of[ref.text.strip()] = lname
            # attach lanes to their pool summary
            for p in diagram.pools:
                if p.name == pool_name:
                    p.lanes.append({"id": lane_set.get("id") or lname, "name": lname})
        _walk(proc, pool_name, lane_of, None)

    # 4. Message flows (cross-pool).
    for mf in raw_message_flows:
        src, tgt = mf.get("sourceRef"), mf.get("targetRef")
        if not src or not tgt:
            continue
        raw_edges.append(MappedEdge(
            client_id=mf.get("id") or f"{src}~>{tgt}",
            source_client_id=src, target_client_id=tgt,
            label=(mf.get("name") or "").strip() or None,
            flow_kind="message",
        ))

    # 5. Refine parallel gateways (split vs join) + default flags + warnings.
    for n in diagram.nodes:
        if n.bpmn_type == "bpmn:ParallelGateway":
            ins, outs = in_degree.get(n.client_id, 0), out_degree.get(n.client_id, 0)
            if ins > 1 and outs <= 1:
                n.node_type = "join"
                n.structural_type = "parallel_join"
        if not n.executable:
            diagram.warnings.append(
                f"'{n.title}' ({n.bpmn_type}) chưa gán hành động Kaori — "
                "⚙ Thiết kế, chưa thực thi.")

    # 6. Keep edges with real endpoints (message flows may target a node).
    for e in raw_edges:
        if e.client_id in default_flow_ids:
            e.is_default = True
        if e.source_client_id in valid_ids and e.target_client_id in valid_ids:
            diagram.edges.append(e)
        else:
            diagram.warnings.append(
                f"Bỏ qua luồng '{e.client_id}' nối tới phần tử không phải node.")

    if not any(n.is_trigger for n in diagram.nodes):
        diagram.warnings.append("Quy trình chưa có điểm bắt đầu (Start Event / trigger).")

    # Lift exclusive-gateway flow conditions into the if_else node config + tag
    # the arms with runner branch tokens.
    _derive_gateway_conditions(diagram)

    return diagram


# Comparison operators recognised in a BPMN conditionExpression, longest first
# so '>=' wins over '>' and '==' over '='.
_COND_OPS = ("==", "!=", ">=", "<=", ">", "<", "=")
_COND_OP_NORM = {"=": "=="}


def _coerce_operand(tok: str):
    """Coerce a literal operand: quoted string | number | bool | bare string."""
    t = tok.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        return t[1:-1]
    low = t.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _coerce_left(tok: str):
    """Left operand: a bare identifier becomes an input ref ($.input.<name>) so
    the if_else executor resolves it from run input; literals stay literals."""
    t = tok.strip()
    if t.startswith("$."):
        return t
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        return t[1:-1]
    if _IDENT_RE.match(t) and t.lower() not in ("true", "false"):
        try:
            float(t)
        except ValueError:
            ref = t if t.startswith("input.") else f"input.{t}"
            return f"$.{ref}"
    return _coerce_operand(t)


def _split_logical(s: str, connectors: tuple[str, ...]) -> list[str]:
    """Split a string on top-level logical connectors (word-boundary for
    alphabetic 'and'/'or', literal for '&&'/'||'). No paren nesting (v0)."""
    pats = []
    for c in connectors:
        pats.append(rf"\b{re.escape(c)}\b" if c.isalpha() else re.escape(c))
    parts = re.split("|".join(pats), s, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _mask_quotes(s: str) -> str:
    """Replace characters INSIDE single/double quotes with NUL (same length),
    so operator scanning never splits on an operator that lives in a string
    literal, e.g. name == "a > b"."""
    out, q = [], None
    for ch in s:
        if q is not None:
            out.append(ch if ch == q else "\0")
            if ch == q:
                q = None
        elif ch in ("'", '"'):
            q = ch
            out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _parse_comparison(s: str) -> Optional[dict]:
    """Parse a single comparison ``<left> <op> <right>`` → {left, op, right}.

    Operator search runs over a quote-masked copy so an operator inside a
    quoted string isn't mistaken for the split point; the split itself uses the
    real string so the operands keep their original text."""
    s = s.strip()
    masked = _mask_quotes(s)
    for op in _COND_OPS:
        idx = masked.find(op)
        if idx <= 0:
            continue
        left, right = s[:idx], s[idx + len(op):]
        if not left.strip() or not right.strip():
            return None
        return {
            "left": _coerce_left(left),
            "op": _COND_OP_NORM.get(op, op),
            "right": _coerce_operand(right),
        }
    return None


def _parse_expr(s: str) -> Optional[dict]:
    """Recursive: OR (lowest precedence) → AND → single comparison.

    Returns {or:[...]} / {and:[...]} / {left,op,right}, matching the shape
    IfElseExecutor._eval_condition evaluates. None if any leaf is unparseable.
    """
    s = s.strip()
    for connectors, key in ((("or", "||"), "or"), (("and", "&&"), "and")):
        parts = _split_logical(s, connectors)
        if len(parts) > 1:
            subs = [_parse_expr(p) for p in parts]
            if any(x is None for x in subs):
                return None
            return {key: subs}
    return _parse_comparison(s)


def parse_condition_expression(text: Optional[str]) -> Optional[dict]:
    """Best-effort parse a BPMN conditionExpression → Kaori condition.

    Handles ``${ … }`` / ``#{ … }`` wrappers, a single comparison, AND compound
    ``and`` / ``or`` (``&&`` / ``||``) chains → ``{and:[…]}`` / ``{or:[…]}`` (OR
    binds looser than AND). A bare identifier on the left becomes
    ``$.input.<name>``. Returns None for anything it can't confidently parse
    (function calls, no operator, ``not``) — the caller keeps the raw text +
    warns so a human can refine it in the properties panel.
    """
    if not text or not str(text).strip():
        return None
    s = str(text).strip()
    m = re.match(r"^[#$]\{(.*)\}$", s, re.DOTALL)
    if m:
        s = m.group(1).strip()
    return _parse_expr(s)


_GATEWAY_BPMN_TYPES = frozenset({
    "bpmn:ExclusiveGateway", "bpmn:InclusiveGateway",
    "bpmn:ComplexGateway", "bpmn:EventBasedGateway",
})


def _derive_gateway_conditions(diagram: MappedDiagram) -> None:
    """Lift gateway flow conditions into the decision node's executor config +
    tag each outgoing arm with a runner branch token.

      • Exclusive, exactly 2 outgoing (1 condition + other/default) → **if_else**:
        node.config = {condition: <parsed>}; arms tagged 'true' / 'false'.
      • Any gateway with ≥2 conditional flows whose conditions are all equality
        on the SAME variable (``x == v``) → **switch**: node.config =
        {input, cases:[{when,then}], default}; case arms tagged str(v), default
        arm tagged 'default'. (Covers >2-way exclusive, inclusive, complex.)
      • Otherwise (non-uniform conditions, ranges, unparseable, event-based with
        no conditions) → keep raw + warn → configure in the properties panel.
    """
    by_src: dict[str, list[MappedEdge]] = {}
    for e in diagram.edges:
        if e.flow_kind == "sequence":
            by_src.setdefault(e.source_client_id, []).append(e)

    for n in diagram.nodes:
        if n.bpmn_type not in _GATEWAY_BPMN_TYPES:
            continue
        outs = by_src.get(n.client_id, [])
        if len(outs) < 2:
            continue
        default_e = next((e for e in outs if e.is_default), None)
        cond_es = [e for e in outs if e is not default_e and e.condition]
        if not cond_es:
            diagram.warnings.append(
                f"Cổng '{n.title}' chưa có điều kiện trên nhánh — đặt ở properties panel.")
            continue

        # ── 2-way exclusive → if_else ──
        # Works whether the else arm is a default flow, a plain flow, OR also
        # carries a condition (the complement): the conditional flow is the
        # 'true' arm, the OTHER flow is the 'false'/else arm. Without this, a
        # gateway whose both arms have conditions left every edge with a raw
        # token → runner couldn't prune → BOTH arms fired.
        if n.bpmn_type == "bpmn:ExclusiveGateway" and len(outs) == 2:
            true_e = next((e for e in outs if not e.is_default and e.condition), None) \
                or cond_es[0]
            parsed = parse_condition_expression(true_e.condition)
            if parsed is None:
                diagram.warnings.append(
                    f"Cổng '{n.title}': điều kiện \"{true_e.condition}\" chưa parse "
                    "được — giữ nguyên, chỉnh tay ở properties panel.")
                continue
            n.node_type = "if_else"
            n.structural_type = "decision_if_else"
            n.config = {"condition": parsed}
            true_e.branch = "true"
            other = next((e for e in outs if e is not true_e), None)
            if other is not None:
                other.branch = "false"
            continue

        # ── N-way → switch (uniform equality on one variable) ──
        parsed_pairs = [(e, parse_condition_expression(e.condition)) for e in cond_es]
        if any(p is None for _, p in parsed_pairs):
            diagram.warnings.append(
                f"Cổng '{n.title}' có nhánh chưa parse được — chỉnh ở properties panel.")
            continue
        lefts = {p["left"] for _, p in parsed_pairs}
        if len(lefts) == 1 and all(p.get("op") == "==" for _, p in parsed_pairs):
            cases = []
            for e, p in parsed_pairs:
                val = p["right"]
                cases.append({"when": val, "then": val})
                e.branch = str(val)
            n.node_type = "switch"
            n.structural_type = "decision_switch"
            n.config = {"input": lefts.pop(), "cases": cases, "default": None}
            if default_e is not None:
                default_e.branch = "default"
            continue

        diagram.warnings.append(
            f"Cổng '{n.title}': điều kiện các nhánh không đồng nhất (không phải "
            "'==' trên cùng một biến) — chưa map switch tự động; cấu hình ở "
            "properties panel.")


def _event_marker(el: ET.Element) -> Optional[str]:
    """Detect the event-definition child (timer/message/error/…)."""
    markers = [
        _EVENT_DEF_MARKERS[_local(c.tag)]
        for c in el if _local(c.tag) in _EVENT_DEF_MARKERS
    ]
    if not markers:
        return None
    return markers[0] if len(markers) == 1 else "multiple"


# ── Build (inverse) ────────────────────────────────────────────────────────────

def build_bpmn_xml(
    nodes: list[MappedNode],
    edges: list[MappedEdge],
    *,
    process_id: str = "Process_kaori",
    process_name: str = "",
    include_di: bool = True,
    lanes: Optional[list] = None,
) -> str:
    """Generate BPMN 2.0 XML from mapped nodes + edges (inverse of parse).

    Emits a single-process diagram. With ``include_di=True`` a minimal
    BPMNDiagram (linear positions) is written so bpmn-js renders immediately.
    With ``include_di=False`` only the semantics are emitted — the FE's
    bpmn-auto-layout then computes a proper branched tree layout (the nodes→BPMN
    projection uses this so gateways visually fork instead of a straight line).
    Round-trips the semantic content parse_bpmn_xml produced for a single-pool
    process (pools/message-flows are export-only metadata — a full collaboration
    writer is a later step; see WORKFLOW_BUILDER_REDESIGN.md).
    """
    ET.register_namespace("bpmn", BPMN_NS)
    ET.register_namespace("bpmndi", BPMNDI_NS)
    ET.register_namespace("di", DI_NS)
    ET.register_namespace("dc", DC_NS)
    ET.register_namespace("kaori", KAORI_NS)

    defs = ET.Element(f"{{{BPMN_NS}}}definitions", {
        "id": "Definitions_kaori", "targetNamespace": KAORI_NS,
    })
    proc = ET.SubElement(defs, f"{{{BPMN_NS}}}process",
                         {"id": process_id, "isExecutable": "true"})
    if process_name:
        proc.set("name", process_name)

    seq_edges = [e for e in edges if e.flow_kind != "message"]
    incoming: dict[str, list[str]] = {}
    outgoing: dict[str, list[str]] = {}
    for e in seq_edges:
        outgoing.setdefault(e.source_client_id, []).append(e.client_id)
        incoming.setdefault(e.target_client_id, []).append(e.client_id)
    default_of: dict[str, str] = {
        e.source_client_id: e.client_id for e in seq_edges if e.is_default
    }

    for n in nodes:
        local = n.bpmn_type.split(":", 1)[-1]
        local = local[0].lower() + local[1:] if local else "task"
        attrs = {"id": n.client_id}
        if n.title and n.title != n.client_id:
            attrs["name"] = n.title
        if n.kaori_node_type:
            attrs[f"{{{KAORI_NS}}}nodeType"] = n.kaori_node_type
        if n.attached_to:
            attrs["attachedToRef"] = n.attached_to
        if n.client_id in default_of:
            attrs["default"] = default_of[n.client_id]
        el = ET.SubElement(proc, f"{{{BPMN_NS}}}{local}", attrs)
        if n.event_definition and n.event_definition != "multiple":
            tag = next((k for k, v in _EVENT_DEF_MARKERS.items()
                        if v == n.event_definition), None)
            if tag:
                ET.SubElement(el, f"{{{BPMN_NS}}}{tag}")
        for fid in incoming.get(n.client_id, []):
            ET.SubElement(el, f"{{{BPMN_NS}}}incoming").text = fid
        for fid in outgoing.get(n.client_id, []):
            ET.SubElement(el, f"{{{BPMN_NS}}}outgoing").text = fid

    for e in seq_edges:
        attrs = {"id": e.client_id, "sourceRef": e.source_client_id,
                 "targetRef": e.target_client_id}
        if e.label:
            attrs["name"] = e.label
        flow = ET.SubElement(proc, f"{{{BPMN_NS}}}sequenceFlow", attrs)
        if e.condition:
            ET.SubElement(flow, f"{{{BPMN_NS}}}conditionExpression").text = e.condition

    # #9 — swimlane pool: emit a collaboration (1 pool) + a laneSet (one lane per
    # role) and a computed DI (bpmn-auto-layout can't lay out pools). Each lane is
    # a horizontal band; nodes sit in their lane at a column by flow order.
    if lanes:
        # Column = longest-path depth from the roots, so branches that CONVERGE
        # (e.g. every approval arm → "Ghi sổ") share a column instead of fanning
        # out to N columns — far fewer cross-lane crossings than 1-column-per-node.
        _pred: dict[str, list] = {}
        for e in seq_edges:
            _pred.setdefault(e.target_client_id, []).append(e.source_client_id)
        _depth: dict[str, int] = {}

        def _rank(cid: str, stack: set) -> int:
            if cid in _depth:
                return _depth[cid]
            if cid in stack:        # cycle guard (shouldn't happen — DAG)
                return 0
            stack.add(cid)
            preds = _pred.get(cid, [])
            d = 0 if not preds else 1 + max(_rank(p, stack) for p in preds)
            stack.discard(cid)
            _depth[cid] = d
            return d

        for n in nodes:
            _rank(n.client_id, set())

        # Order lanes by flow progression — each lane sorts by the earliest
        # column (min depth) of any node it owns. The cross-functional flow
        # then descends monotonically left→right as a clean staircase instead
        # of zig-zagging back up across lanes (the main source of edge
        # crossings). Empty lanes sink to the bottom; ties keep input order.
        _BIG = len(nodes) + 1
        lanes = sorted(
            lanes,
            key=lambda li_pair: min(
                (_depth.get(cid, _BIG) for cid in li_pair[1]), default=_BIG
            ),
        )

        node_lane: dict[str, int] = {}
        for i, (_, ids) in enumerate(lanes):
            for cid in ids:
                node_lane[cid] = i
        # Resolve two nodes landing in the same (column, lane) cell by bumping the
        # later one to the next free column so they don't overlap.
        _used: set = set()
        col_of: dict[str, int] = {}
        for n in nodes:
            c = _depth.get(n.client_id, 0)
            li = node_lane.get(n.client_id, len(lanes) - 1)
            while (c, li) in _used:
                c += 1
            _used.add((c, li))
            col_of[n.client_id] = c

        lane_set = ET.SubElement(proc, f"{{{BPMN_NS}}}laneSet", {"id": "LaneSet_kaori"})
        for i, (label, ids) in enumerate(lanes):
            lane_el = ET.SubElement(lane_set, f"{{{BPMN_NS}}}lane",
                                    {"id": f"Lane_{i}", "name": label or "Chung"})
            for cid in ids:
                ET.SubElement(lane_el, f"{{{BPMN_NS}}}flowNodeRef").text = cid

        collab = ET.Element(f"{{{BPMN_NS}}}collaboration", {"id": "Collaboration_kaori"})
        ET.SubElement(collab, f"{{{BPMN_NS}}}participant",
                      {"id": "Participant_kaori",
                       "name": process_name or "Quy trình",
                       "processRef": process_id})
        defs.insert(0, collab)   # collaboration precedes the process

        POOL_X, POOL_Y = 160, 80
        LABELS_W = 60          # pool (30) + lane (30) vertical title bands
        COL_W, NODE_W, NODE_H, LANE_H = 160, 100, 70, 110
        n_cols = (max(col_of.values()) + 1) if col_of else 1
        pool_w = LABELS_W + 20 + n_cols * COL_W + 20
        pool_h = max(len(lanes), 1) * LANE_H
        node_x = lambda c: POOL_X + LABELS_W + 20 + c * COL_W
        lane_y = lambda i: POOL_Y + i * LANE_H
        node_y = lambda i: lane_y(i) + (LANE_H - NODE_H) // 2
        centre: dict[str, tuple] = {}

        diag = ET.SubElement(defs, f"{{{BPMNDI_NS}}}BPMNDiagram", {"id": "Diagram_kaori"})
        plane = ET.SubElement(diag, f"{{{BPMNDI_NS}}}BPMNPlane",
                              {"id": "Plane_kaori", "bpmnElement": "Collaboration_kaori"})
        # pool shape
        psh = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                            {"id": "Participant_kaori_di", "bpmnElement": "Participant_kaori",
                             "isHorizontal": "true"})
        ET.SubElement(psh, f"{{{DC_NS}}}Bounds",
                      {"x": str(POOL_X), "y": str(POOL_Y), "width": str(pool_w), "height": str(pool_h)})
        # lane shapes (after the pool's 30px label band)
        for i, _ in enumerate(lanes):
            lsh = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                                {"id": f"Lane_{i}_di", "bpmnElement": f"Lane_{i}",
                                 "isHorizontal": "true"})
            ET.SubElement(lsh, f"{{{DC_NS}}}Bounds",
                          {"x": str(POOL_X + 30), "y": str(lane_y(i)),
                           "width": str(pool_w - 30), "height": str(LANE_H)})
        # node shapes within their lane band
        for n in nodes:
            c = col_of[n.client_id]
            li = node_lane.get(n.client_id, len(lanes) - 1)
            x, y = node_x(c), node_y(li)
            centre[n.client_id] = (x + NODE_W // 2, y + NODE_H // 2)
            nsh = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                                {"id": f"{n.client_id}_di", "bpmnElement": n.client_id})
            ET.SubElement(nsh, f"{{{DC_NS}}}Bounds",
                          {"x": str(x), "y": str(y), "width": str(NODE_W), "height": str(NODE_H)})
        # edges centre→centre
        for e in seq_edges:
            sx, sy = centre.get(e.source_client_id, (POOL_X, POOL_Y))
            tx, ty = centre.get(e.target_client_id, (POOL_X, POOL_Y))
            edge_el = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge",
                                    {"id": f"{e.client_id}_di", "bpmnElement": e.client_id})
            ET.SubElement(edge_el, f"{{{DI_NS}}}waypoint", {"x": str(int(sx)), "y": str(int(sy))})
            ET.SubElement(edge_el, f"{{{DI_NS}}}waypoint", {"x": str(int(tx)), "y": str(int(ty))})
        return ET.tostring(defs, encoding="unicode", xml_declaration=True)

    if not include_di:
        # Semantics only → the FE auto-layouts into a branched tree.
        return ET.tostring(defs, encoding="unicode", xml_declaration=True)

    # Minimal DI so bpmn-js renders without auto-layout surprises.
    diag = ET.SubElement(defs, f"{{{BPMNDI_NS}}}BPMNDiagram", {"id": "Diagram_kaori"})
    plane = ET.SubElement(diag, f"{{{BPMNDI_NS}}}BPMNPlane",
                          {"id": "Plane_kaori", "bpmnElement": process_id})
    pos = {n.client_id: (n.position_x, n.position_y) for n in nodes}
    for n in nodes:
        x, y = pos[n.client_id]
        shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                              {"id": f"{n.client_id}_di", "bpmnElement": n.client_id})
        ET.SubElement(shape, f"{{{DC_NS}}}Bounds",
                      {"x": str(int(x)), "y": str(int(y)), "width": "100", "height": "80"})
    for e in seq_edges:
        sx, sy = pos.get(e.source_client_id, (0.0, 0.0))
        tx, ty = pos.get(e.target_client_id, (0.0, 0.0))
        edge_el = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge",
                                {"id": f"{e.client_id}_di", "bpmnElement": e.client_id})
        ET.SubElement(edge_el, f"{{{DI_NS}}}waypoint", {"x": str(int(sx)), "y": str(int(sy))})
        ET.SubElement(edge_el, f"{{{DI_NS}}}waypoint", {"x": str(int(tx)), "y": str(int(ty))})

    return ET.tostring(defs, encoding="unicode", xml_declaration=True)


def summarize(diagram: MappedDiagram) -> dict:
    """Compact design summary for the PUT /bpmn response + builder badge."""
    return {
        "node_count": len(diagram.nodes),
        "edge_count": len(diagram.edges),
        "executable_count": sum(1 for n in diagram.nodes if n.executable),
        "trigger_count": sum(1 for n in diagram.nodes if n.is_trigger),
        "message_flow_count": sum(1 for e in diagram.edges if e.flow_kind == "message"),
        "boundary_count": sum(1 for n in diagram.nodes if n.bpmn_type == "bpmn:BoundaryEvent"),
        "pools": [
            {"name": p.name, "lanes": [lane["name"] for lane in p.lanes]}
            for p in diagram.pools
        ],
        "design_only": [
            {"id": n.client_id, "title": n.title, "bpmn_type": n.bpmn_type}
            for n in diagram.nodes if not n.executable
        ],
        "warnings": diagram.warnings,
    }
