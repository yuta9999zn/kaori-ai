"""
P15-S11 Tuần 8 Step 5 — Workflow Builder CRUD.

Per anh's directive 2026-05-15: build the drag-drop workflow feature
first, before the Pipeline Wizard FE. This router is the BE side —
the drag-drop FE (React Flow) writes here.

Endpoints
---------

  GET    /workflows                        — list workflows (filter by dept)
  POST   /workflows                        — create empty workflow
  GET    /workflows/{id}                   — get workflow + nodes + edges
  PUT    /workflows/{id}                   — update name/description/state
  DELETE /workflows/{id}                   — delete (cascade nodes/edges/attachments)

  GET    /workflows/{id}/tree              — tree shape for FE viewer
                                              workflow → nodes (with docs) → edges

  POST   /workflows/{id}/nodes             — add a node (card)
  PUT    /workflows/{id}/nodes/{nid}       — update node (title/note/hashtags/etc)
  DELETE /workflows/{id}/nodes/{nid}       — remove node

  POST   /workflows/{id}/edges             — add an edge
  DELETE /workflows/{id}/edges/{eid}       — remove an edge

  GET    /workflow-templates               — list global templates
  POST   /workflows/from-template          — clone a template → real workflow

K-1 / K-12: tenant scope from X-Enterprise-ID JWT header, never from body.
ABAC: when X-Department-ID supplied, RLS narrows visibility to that dept.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Pydantic shapes ─────────────────────────────────────────────────


class WorkflowCreate(BaseModel):
    name:               str = Field(..., min_length=1, max_length=200)
    name_vi:            Optional[str] = Field(default=None, max_length=200)
    description:        Optional[str] = Field(default=None, max_length=4000)
    department_id:      UUID
    branch_id:          Optional[UUID] = None
    category:           Optional[str] = Field(default=None, max_length=50)
    business_function:  Optional[str] = Field(default=None, max_length=100)


class WorkflowUpdate(BaseModel):
    name:               Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_vi:            Optional[str] = Field(default=None, max_length=200)
    description:        Optional[str] = Field(default=None, max_length=4000)
    state:              Optional[str] = Field(
        default=None,
        pattern=r"^(DRAFT|TESTING|ACTIVE_BASELINE|ARCHIVED|BROKEN)$",
    )
    category:           Optional[str] = Field(default=None, max_length=50)


class WorkflowOut(BaseModel):
    workflow_id:        UUID
    enterprise_id:      UUID
    department_id:      UUID
    # Real department name + type, resolved by JOIN. The FE MUST render
    # department_name (never a hardcoded dept_type→label map, which collapses
    # distinct depts of the same type — e.g. "JM" and "Kinh doanh" are both
    # dept_type=sales). dept_type stays available for grouping/icons only.
    department_name:    Optional[str] = None
    dept_type:          Optional[str] = None
    branch_id:          Optional[UUID]
    name:               str
    name_vi:            Optional[str]
    description:        Optional[str]
    category:           Optional[str]
    state:              str
    version:            int
    source:             str
    created_at:         datetime
    last_modified_at:   datetime


class NodeCreate(BaseModel):
    title:              str = Field(..., min_length=1, max_length=200)
    title_vi:           Optional[str] = Field(default=None, max_length=200)
    note:               Optional[str] = Field(default=None, max_length=4000)
    hashtags:           list[str] = Field(default_factory=list)
    required_document_types: list[dict] = Field(default_factory=list)
    expected_mapping_template_id: Optional[UUID] = None
    node_type:          str = Field(
        default="step",
        pattern=(
            r"^(step|decision_if_else|decision_switch|approval_gate"
            # Path B 2026-05-15
            r"|wait_event|sla_timer|parallel_split|parallel_join"
            r"|subworkflow|notification|loop_foreach|loop_end)$"
        ),
        max_length=50,
    )
    category:           str = Field(default="data_input", max_length=30)
    # K-17 — defaults to read_only; _default_side_effect() overrides when
    # body doesn't explicitly set it (Path B node types each have a
    # natural side_effect_class default).
    side_effect_class:  str = Field(default="read_only", max_length=30)
    position_x:         float = 0
    position_y:         float = 0
    sequence_order:     int = 0
    config:             dict = Field(default_factory=dict)
    # Phase 2 — decision_config: shape varies per node_type. See mig 058
    # column comment. step nodes ignore this field.
    decision_config:    dict = Field(default_factory=dict)
    # mig 117 — executor key the runner routes on. None = design-only node
    # (no executor); the structural node_type alone never reaches the runner.
    node_type_catalog_key: Optional[str] = Field(default=None, max_length=60)
    # #9 — role/lane responsible (BPMN swimlane); also settable later via PUT.
    lane_name:          Optional[str] = Field(default=None, max_length=120)


class NodeUpdate(BaseModel):
    # min_length=0 — FE sends PUT on every keystroke; empty title means
    # "user cleared the field mid-edit", not "set title to empty". The
    # handler skips empty strings rather than rejecting the whole request.
    title:              Optional[str] = Field(default=None, max_length=200)
    title_vi:           Optional[str] = Field(default=None, max_length=200)
    note:               Optional[str] = Field(default=None, max_length=4000)
    hashtags:           Optional[list[str]] = None
    required_document_types: Optional[list[dict]] = None
    expected_mapping_template_id: Optional[UUID] = None
    position_x:         Optional[float] = None
    position_y:         Optional[float] = None
    sequence_order:     Optional[int] = None
    config:             Optional[dict] = None
    decision_config:    Optional[dict] = None
    node_type:          Optional[str] = Field(
        default=None,
        pattern=(
            r"^(step|decision_if_else|decision_switch|approval_gate"
            # Path B 2026-05-15
            r"|wait_event|sla_timer|parallel_split|parallel_join"
            r"|subworkflow|notification|loop_foreach|loop_end)$"
        ),
    )
    # mig 117 — let the builder assign a Kaori action (executor key) in-place.
    node_type_catalog_key: Optional[str] = Field(default=None, max_length=60)
    # #9 — the role/lane responsible for this step (BPMN swimlane). '' clears it.
    lane_name:          Optional[str] = Field(default=None, max_length=120)


class NodeOut(BaseModel):
    node_id:            UUID
    workflow_id:        UUID
    title:              str
    title_vi:           Optional[str]
    note:               Optional[str]
    hashtags:           list[str]
    required_document_types: list[dict]
    expected_mapping_template_id: Optional[UUID]
    node_type:          str
    category:           str
    side_effect_class:  str
    position_x:         float
    position_y:         float
    sequence_order:     int
    decision_config:    dict = Field(default_factory=dict)
    # mig 116/117 — BPMN-origin metadata (NULL for legacy/hand-built nodes).
    # node_type_catalog_key = executor key the runner routes on (mig 117).
    bpmn_element_id:        Optional[str] = None
    bpmn_type:              Optional[str] = None
    node_type_catalog_key:  Optional[str] = None
    pool_name:              Optional[str] = None
    lane_name:              Optional[str] = None
    event_definition:       Optional[str] = None
    attached_to_ref:        Optional[str] = None


class EdgeCreate(BaseModel):
    source_node_id:     UUID
    target_node_id:     UUID
    condition:          Optional[str] = Field(default=None, max_length=1000)
    label:              Optional[str] = Field(default=None, max_length=100)
    # ADR-0035 B5 — typed port. 'main' = data flow (runner topo-sorts these);
    # ai_tool/ai_memory/ai_model = side connections wiring an agent. Default
    # 'main' keeps every existing caller behaving identically.
    port_type:          Literal["main", "ai_tool", "ai_memory", "ai_model"] = "main"


class EdgeOut(BaseModel):
    edge_id:            UUID
    workflow_id:        UUID
    source_node_id:     UUID
    target_node_id:     UUID
    condition:          Optional[str]
    label:              Optional[str]
    port_type:          str = "main"   # ADR-0035 B5 — see EdgeCreate.port_type


class CloneFromTemplateRequest(BaseModel):
    template_id:        UUID
    department_id:      UUID
    branch_id:          Optional[UUID] = None
    custom_name:        Optional[str] = Field(default=None, max_length=200)


class WorkflowTreeOut(BaseModel):
    """Hierarchical shape for FE tree viewer."""
    workflow:           WorkflowOut
    nodes:              list[dict]   # NodeOut + attached_documents list
    edges:              list[EdgeOut]


# ─── Helpers ─────────────────────────────────────────────────────────


async def _assert_dept_in_enterprise(conn, enterprise_id: UUID, department_id: UUID) -> None:
    """Reject X-Department-ID values that point outside the enterprise.

    Used by clone-from-template + node CRUD (intra-enterprise scope).
    POST /workflows uses _resolve_dept_workspace_match instead — Vingroup
    HQ users can create workflows under any subsidiary in their workspace.
    """
    row = await conn.fetchrow(
        "SELECT 1 FROM departments WHERE enterprise_id = $1 AND department_id = $2",
        enterprise_id, department_id,
    )
    if row is None:
        raise HTTPException(status_code=400, detail="department_id not in this enterprise")


async def _resolve_dept_workspace_match(conn, caller_enterprise_id: UUID, department_id: UUID):
    """Look up the dept's enterprise + workspace; verify same-workspace as caller.

    Returns (target_enterprise_id, workspace_id) tuple. Raises 400 if the
    dept lives in a different workspace, 404 if it doesn't exist.
    Supports Vingroup-class flow: caller logged in as Vinhomes MANAGER can
    create a workflow at any VinMart / VinFast / … dept within the same
    Vingroup Holdings workspace.
    """
    row = await conn.fetchrow(
        """SELECT d.enterprise_id, e.workspace_id, ec.workspace_id AS caller_workspace_id
           FROM departments d
           JOIN enterprises e  ON e.enterprise_id  = d.enterprise_id
           JOIN enterprises ec ON ec.enterprise_id = $1
           WHERE d.department_id = $2
           LIMIT 1""",
        caller_enterprise_id, department_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="department_id not found")
    if row["workspace_id"] != row["caller_workspace_id"]:
        raise HTTPException(
            status_code=403,
            detail="department belongs to a different workspace",
        )
    return row["enterprise_id"], row["workspace_id"]


# Canonical workflow SELECT — always LEFT JOIN departments so WorkflowOut
# carries the real department_name/dept_type and the FE never has to guess a
# label from dept_type. Callers append their own WHERE (qualify with `w.`).
_WF_SELECT = (
    "SELECT w.*, d.name AS department_name, d.dept_type "
    "FROM workflows w LEFT JOIN departments d ON d.department_id = w.department_id"
)


def _row_to_workflow(row) -> WorkflowOut:
    return WorkflowOut(
        workflow_id=row["workflow_id"],
        enterprise_id=row["enterprise_id"],
        department_id=row["department_id"],
        department_name=row.get("department_name") if hasattr(row, "get") else None,
        dept_type=row.get("dept_type") if hasattr(row, "get") else None,
        branch_id=row["branch_id"],
        name=row["name"],
        name_vi=row["name_vi"],
        description=row["description"],
        category=row["category"],
        state=row["state"],
        version=row["version"],
        source=row["source"],
        created_at=row["created_at"],
        last_modified_at=row["last_modified_at"],
    )


def _row_to_node(row) -> NodeOut:
    """Convert asyncpg Record → NodeOut.

    asyncpg returns JSONB columns as `str` (not parsed) when you don't
    register a custom codec. Both required_document_types + decision_config
    need json.loads() before Pydantic accepts them.
    """
    import json as _j

    def _to_obj(v, default):
        if v is None:
            return default
        if isinstance(v, str):
            try:
                return _j.loads(v)
            except Exception:
                return default
        return v

    raw_dc = None
    try:
        raw_dc = row["decision_config"]
    except (KeyError, IndexError):
        raw_dc = {}
    decision_cfg = _to_obj(raw_dc, {})

    raw_req = row["required_document_types"]
    required_docs = _to_obj(raw_req, [])

    # mig 116 columns — tolerant read so rows from before the migration
    # (column absent) just yield None instead of raising.
    def _opt(key):
        return row.get(key) if hasattr(row, "get") else None

    return NodeOut(
        node_id=row["node_id"],
        workflow_id=row["workflow_id"],
        title=row["title"],
        title_vi=row["title_vi"],
        note=row["note"],
        hashtags=list(row["hashtags"] or []),
        required_document_types=required_docs,
        expected_mapping_template_id=row["expected_mapping_template_id"],
        node_type=row["node_type"],
        category=row["category"],
        side_effect_class=row["side_effect_class"],
        position_x=float(row["position_x"]),
        position_y=float(row["position_y"]),
        sequence_order=row["sequence_order"],
        decision_config=decision_cfg if isinstance(decision_cfg, dict) else {},
        bpmn_element_id=_opt("bpmn_element_id"),
        bpmn_type=_opt("bpmn_type"),
        node_type_catalog_key=_opt("node_type_catalog_key"),
        pool_name=_opt("pool_name"),
        lane_name=_opt("lane_name"),
        event_definition=_opt("event_definition"),
        attached_to_ref=_opt("attached_to_ref"),
    )


def _row_to_edge(row) -> EdgeOut:
    return EdgeOut(
        edge_id=row["edge_id"],
        workflow_id=row["workflow_id"],
        source_node_id=row["source_node_id"],
        target_node_id=row["target_node_id"],
        condition=row["condition"],
        label=row["label"],
        # Tolerate rows from before mig 114 (column absent) → default 'main'.
        port_type=(row.get("port_type") or "main"),
    )


# Gap 5 — state transitions that activate the workflow runtime contract.
# Any state in this set means the workflow can be picked up by Temporal
# (Phase 2) or by manual "Đang chạy" play; the IF/ELSE/Switch dangling
# guard runs on the transition.
_RUNTIME_STATES = frozenset({"TESTING", "ACTIVE_BASELINE"})


async def _check_dangling_branches(conn, workflow_id: UUID) -> list[dict]:
    """Return dangling-branch issues for decision/fan-out nodes.

    decision_if_else      → ≥2 distinct outgoing edges (IF_TRUE + ELSE_FALSE)
    decision_switch       → ≥(len(cases)+1) outgoing edges (cases + default),
                            min 2 when decision_config is empty/missing
    parallel_split        → ≥2 outgoing edges (fan-out branches)
    """
    import json as _j

    rows = await conn.fetch(
        """SELECT n.node_id, n.node_type, n.title, n.title_vi,
                  n.decision_config,
                  COALESCE(e.cnt, 0) AS outgoing_count
           FROM workflow_nodes n
           LEFT JOIN (
                 SELECT source_node_id,
                        COUNT(DISTINCT target_node_id) AS cnt
                 FROM workflow_edges
                 WHERE workflow_id = $1
                 GROUP BY source_node_id
           ) e ON e.source_node_id = n.node_id
           WHERE n.workflow_id = $1
             AND n.node_type IN ('decision_if_else', 'decision_switch',
                                  'parallel_split')""",
        workflow_id,
    )

    issues: list[dict] = []
    for r in rows:
        nt = r["node_type"]
        actual = int(r["outgoing_count"] or 0)
        if nt == "decision_switch":
            raw_dc = r["decision_config"]
            if isinstance(raw_dc, str):
                try:
                    dc = _j.loads(raw_dc)
                except Exception:
                    dc = {}
            else:
                dc = raw_dc or {}
            cases = dc.get("cases") or []
            expected = max(len(cases) + 1, 2)   # cases + default, min 2
        else:
            expected = 2

        if actual < expected:
            issues.append({
                "node_id":        str(r["node_id"]),
                "node_type":      nt,
                "title":          r["title_vi"] or r["title"],
                "expected_edges": expected,
                "actual_edges":   actual,
            })
    return issues


async def _check_approval_gates(conn, workflow_id: UUID) -> list[dict]:
    """Return empty-permission issues for approval_gate nodes.

    A gate may bind approvers two ways (ADR-0037 + mig 127):
      • approval_chain_id → a chain that MUST exist and carry ≥1 level
        (the runtime opens the gate at level 1 — a level-less chain would
        pause forever with nobody to approve).
      • approver_role     → a non-empty single-role / role-list fallback.

    A gate with neither is "rỗng quyền" — it would pause a live run with no
    approver and no SLA owner. Block the runtime transition (gap 5). The chain
    lookup runs under the same tenant connection so RLS scopes it (K-1).
    """
    import json as _j

    # A gate is identified by the executor key (node_type_catalog_key) — the
    # linear builder stores the "Phê duyệt" action there while node_type stays
    # 'step'. Match both so older nodes that set the structural type are covered.
    rows = await conn.fetch(
        """SELECT node_id, title, title_vi, decision_config
           FROM workflow_nodes
           WHERE workflow_id = $1
             AND (node_type_catalog_key = 'approval_gate'
                  OR node_type = 'approval_gate')""",
        workflow_id,
    )

    issues: list[dict] = []
    for r in rows:
        raw = r["decision_config"]
        if isinstance(raw, str):
            try:
                cfg = _j.loads(raw)
            except Exception:
                cfg = {}
        else:
            cfg = raw or {}

        chain_id = cfg.get("approval_chain_id")
        role_raw = cfg.get("approver_role")
        has_role = bool(
            (isinstance(role_raw, str) and role_raw.strip())
            or (isinstance(role_raw, list) and any(str(x).strip() for x in role_raw))
        )

        reason = None
        if chain_id:
            # chain must resolve in this tenant AND have at least one level
            try:
                cid = UUID(str(chain_id))
            except (ValueError, TypeError):
                cid = None
            lvls = 0
            if cid is not None:
                lvls = await conn.fetchval(
                    """SELECT COUNT(*) FROM approval_levels l
                       JOIN approval_chains c ON c.chain_id = l.chain_id
                       WHERE l.chain_id = $1""",
                    cid,
                )
            if not lvls:
                reason = "approval_chain_empty"   # chain missing/invalid or no levels
        elif not has_role:
            reason = "no_approver"                # neither chain nor role

        if reason:
            issues.append({
                "node_id":    str(r["node_id"]),
                "node_type":  "approval_gate",
                "title":      r["title_vi"] or r["title"],
                "reason":     reason,
            })
    return issues


async def _check_prohibited_use(conn, workflow_id: UUID) -> bool:
    """True if the latest EU AI Act classification for this workflow is
    'prohibited' (ADR-0041 K-22). Reads ai_use_risk_register under the same
    tenant connection so RLS scopes it (K-1). Tolerates the table being
    absent on lean deployments (returns False)."""
    try:
        row = await conn.fetchrow(
            """SELECT risk_tier FROM ai_use_risk_register
               WHERE workflow_id = $1
               ORDER BY classified_at DESC
               LIMIT 1""",
            workflow_id,
        )
    except Exception:
        return False
    return bool(row) and row["risk_tier"] == "prohibited"


def _prohibited_problem(workflow_id: UUID) -> JSONResponse:
    """RFC 7807 envelope for a blocked prohibited-tier workflow (K-22).
    Returned directly (not via HTTPException) so the COMPLIANCE.* code
    survives — shared/errors.py only honours str detail."""
    return JSONResponse(
        status_code=403,
        media_type="application/problem+json",
        content={
            "type":     "/problems/compliance-prohibited-use",
            "title":    "Workflow bị chặn — phân loại rủi ro EU AI Act = prohibited",
            "status":   403,
            "code":     "COMPLIANCE.PROHIBITED_USE",
            "instance": f"/workflows/{workflow_id}",
        },
    )


# ─── Workflow CRUD ───────────────────────────────────────────────────


class DepartmentDetailOut(BaseModel):
    department_id:   UUID
    enterprise_id:   UUID
    enterprise_name: Optional[str] = None
    branch_id:       Optional[UUID] = None
    branch_name:     Optional[str] = None
    workspace_id:    UUID
    name:            str
    dept_type:       str
    status:          str
    description:     Optional[str] = None
    workflow_count:  int = 0
    active_count:    int = 0


@router.get("/departments/{department_id}", response_model=DepartmentDetailOut)
async def get_department(
    department_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Department lookup. Workspace-scoped — Vingroup HQ user can read any
    department in the same workspace (VinMart, VinFast, …). Used by the FE
    department-workflows page to show dept name + parent enterprise.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await _resolve_dept_workspace_match(conn, x_enterprise_id, department_id)
        row = await conn.fetchrow(
            """SELECT
                   d.department_id,
                   d.enterprise_id,
                   e.name AS enterprise_name,
                   e.workspace_id,
                   d.branch_id,
                   b.name AS branch_name,
                   d.name,
                   d.dept_type,
                   d.status,
                   d.description,
                   (SELECT COUNT(*) FROM workflows w
                       WHERE w.department_id = d.department_id) AS workflow_count,
                   (SELECT COUNT(*) FROM workflows w
                       WHERE w.department_id = d.department_id
                         AND w.state = 'ACTIVE_BASELINE') AS active_count
               FROM departments d
               JOIN enterprises e ON e.enterprise_id = d.enterprise_id
               LEFT JOIN branches b ON b.branch_id = d.branch_id
               WHERE d.department_id = $1""",
            department_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="department_id not found")
    return DepartmentDetailOut(**dict(row))


# ─── Department list + create (MANAGER UX gap) ───────────────────────


class DepartmentSummaryOut(BaseModel):
    department_id:   UUID
    name:            str
    dept_type:       str
    status:          str
    description:     Optional[str] = None
    pii_sensitivity: str
    workflow_count:  int = 0
    created_at:      datetime


class DepartmentCreate(BaseModel):
    name:            str = Field(..., min_length=1, max_length=200)
    dept_type:       str = Field(
        ...,
        pattern=r"^(marketing|sales|customer_service|warehouse|hr|finance|custom)$",
    )
    description:     Optional[str] = Field(default=None, max_length=2000)
    pii_sensitivity: str = Field(default="normal", pattern=r"^(low|normal|high|restricted)$")


@router.get("/departments", response_model=list[DepartmentSummaryOut])
async def list_departments(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """List active departments for the current enterprise. RLS scopes
    via acquire_for_tenant — MANAGER sees own enterprise only."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT d.department_id, d.name, d.dept_type, d.status,
                      d.description, d.pii_sensitivity, d.created_at,
                      (SELECT COUNT(*) FROM workflows w
                          WHERE w.department_id = d.department_id) AS workflow_count
                 FROM departments d
                ORDER BY d.created_at ASC"""
        )
    return [DepartmentSummaryOut(**dict(r)) for r in rows]


@router.post("/departments", response_model=DepartmentSummaryOut, status_code=201)
async def create_department(
    body: DepartmentCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Create a department under the caller's enterprise. enterprise_id
    comes from JWT-forwarded X-Enterprise-ID (K-12), never from body."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO departments
                   (enterprise_id, name, dept_type, status, pii_sensitivity, description)
               VALUES ($1, $2, $3, 'active', $4, $5)
            RETURNING department_id, name, dept_type, status,
                      description, pii_sensitivity, created_at""",
            x_enterprise_id, body.name, body.dept_type, body.pii_sensitivity, body.description,
        )
        # Seed the default 'Manual upload' source so uploads attributed to
        # this dept resolve a source_id (mirrors mig 046 §5 per-dept seed).
        # Without it, org_resolver raises "Department has no Manual upload
        # source" for any in-app-created department. Idempotent via the
        # UNIQUE(enterprise_id, department_id, name) constraint.
        await conn.execute(
            """INSERT INTO data_sources
                   (enterprise_id, department_id, name, source_kind)
               VALUES ($1, $2, 'Manual upload', 'manual_upload')
            ON CONFLICT (enterprise_id, department_id, name) DO NOTHING""",
            x_enterprise_id, row["department_id"],
        )
    log.info(
        "departments.create",
        department_id=str(row["department_id"]),
        enterprise_id=str(x_enterprise_id),
        dept_type=body.dept_type,
    )
    return DepartmentSummaryOut(workflow_count=0, **dict(row))


@router.get("/workflows", response_model=list[WorkflowOut])
async def list_workflows(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    department_id: Optional[UUID] = Query(None),
    state: Optional[str] = Query(None, pattern=r"^(DRAFT|TESTING|ACTIVE_BASELINE|ARCHIVED|BROKEN)$"),
    limit: int = Query(100, ge=1, le=500),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Mig 059 — workspace-scoped RLS. No explicit enterprise filter
        # at app layer; RLS narrows via app.current_workspace_id GUC.
        sql = _WF_SELECT + " WHERE TRUE"
        params: list[Any] = []
        if department_id is not None:
            sql += f" AND w.department_id = ${len(params) + 1}"
            params.append(department_id)
        if state is not None:
            sql += f" AND w.state = ${len(params) + 1}"
            params.append(state)
        sql += " ORDER BY w.last_modified_at DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        rows = await conn.fetch(sql, *params)
    return [_row_to_workflow(r) for r in rows]


@router.post("/workflows", response_model=WorkflowOut, status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Create workflow. department_id can be ANY dept in the caller's
    workspace (Vingroup HQ user creating a workflow under a VinMart dept
    is valid). enterprise_id is derived from the dept, not from caller."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        target_enterprise_id, workspace_id = await _resolve_dept_workspace_match(
            conn, x_enterprise_id, body.department_id,
        )
        inserted = await conn.fetchrow(
            """INSERT INTO workflows
                  (enterprise_id, workspace_id, branch_id, department_id,
                   name, name_vi, description, category, business_function,
                   state, source, created_by, last_modified_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'DRAFT', 'user_built', $10, $10)
               RETURNING workflow_id""",
            target_enterprise_id, workspace_id, body.branch_id, body.department_id,
            body.name, body.name_vi, body.description,
            body.category, body.business_function,
            x_user_id,
        )
        # Re-fetch with the JOIN so the response carries department_name/dept_type.
        row = await conn.fetchrow(
            _WF_SELECT + " WHERE w.workflow_id = $1", inserted["workflow_id"],
        )
    return _row_to_workflow(row)


@router.get("/workflows/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            _WF_SELECT + " WHERE w.workflow_id = $1",
            workflow_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return _row_to_workflow(row)


@router.put("/workflows/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    body: WorkflowUpdate,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    sets, params = [], []
    for col, val in (
        ("name", body.name), ("name_vi", body.name_vi),
        ("description", body.description), ("state", body.state),
        ("category", body.category),
    ):
        if val is not None:
            params.append(val)
            sets.append(f"{col} = ${len(params)}")
    if not sets:
        return await get_workflow(workflow_id, x_enterprise_id)
    sets.append(f"last_modified_at = NOW()")
    sets.append(f"last_modified_by = ${len(params) + 1}")
    params.append(x_user_id)
    params.append(workflow_id)
    sql = (
        f"UPDATE workflows SET {', '.join(sets)} "
        f"WHERE workflow_id = ${len(params)} "
        f"RETURNING *"
    )
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Gap 5 — before flipping a workflow to a runtime state, every
        # decision/fan-out node must have all branches wired. Otherwise the
        # K-17 side_effect_class promise breaks: a dangling IF_TRUE arm
        # would silently fall through past the gate.
        #
        # Returns the RFC 7807 envelope directly (not via HTTPException +
        # global handler) so the `code` + `issues[]` custom fields survive
        # — shared/errors.py:73 only honours str detail and would
        # otherwise rewrite the body to VALIDATION.GENERIC.
        if body.state in _RUNTIME_STATES:
            # K-22 (ADR-0041) — an AI use classified 'prohibited' under the
            # EU AI Act may never go live. Block the runtime transition before
            # any other gate so the workflow row is never flipped.
            if await _check_prohibited_use(conn, workflow_id):
                return _prohibited_problem(workflow_id)
            issues = await _check_dangling_branches(conn, workflow_id)
            if issues:
                return JSONResponse(
                    status_code=400,
                    media_type="application/problem+json",
                    content={
                        "type":     "/problems/workflow-dangling-branch",
                        "title":    "Workflow has decision nodes with missing branches",
                        "status":   400,
                        "code":     "WORKFLOW.DANGLING_BRANCH",
                        "instance": f"/workflows/{workflow_id}",
                        "issues":   issues,
                    },
                )
            # Gap 5 — an approval_gate with no chain (or a level-less chain) and
            # no approver_role is "rỗng quyền": a live run would pause forever
            # with nobody able to approve. Block the runtime transition.
            gate_issues = await _check_approval_gates(conn, workflow_id)
            if gate_issues:
                return JSONResponse(
                    status_code=400,
                    media_type="application/problem+json",
                    content={
                        "type":     "/problems/workflow-empty-approval-gate",
                        "title":    "Cổng phê duyệt chưa gắn người duyệt",
                        "status":   400,
                        "code":     "WORKFLOW.EMPTY_APPROVAL_GATE",
                        "instance": f"/workflows/{workflow_id}",
                        "issues":   gate_issues,
                    },
                )
        row = await conn.fetchrow(sql, *params)
        if row is not None:
            # Re-fetch with the JOIN so the response carries department_name.
            row = await conn.fetchrow(
                _WF_SELECT + " WHERE w.workflow_id = $1", workflow_id,
            )
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return _row_to_workflow(row)


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "DELETE FROM workflows WHERE workflow_id = $1",
            workflow_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="workflow not found")


# ─── Node (card) CRUD ────────────────────────────────────────────────


# Path B 2026-05-15 — K-17 invariant default mapping. FE doesn't ask user
# for side_effect_class (too technical); BE derives from node_type unless
# body explicitly overrides. Categories likewise.
_NODE_TYPE_DEFAULTS: dict[str, tuple[str, str]] = {
    # node_type:        (default_category,  default_side_effect_class)
    "step":             ("processing",      "read_only"),
    "decision_if_else": ("decision",        "pure"),
    "decision_switch":  ("decision",        "pure"),
    "approval_gate":    ("action",          "write_idempotent"),
    "wait_event":       ("wait",            "read_only"),
    "sla_timer":        ("wait",            "pure"),
    "parallel_split":   ("orchestration",   "pure"),
    "parallel_join":    ("orchestration",   "pure"),
    "subworkflow":      ("orchestration",   "write_idempotent"),
    "notification":     ("communication",   "external_irreversible"),
}


def _resolve_node_defaults(body: "NodeCreate") -> tuple[str, str]:
    """Return (category, side_effect_class). If body sets them to their
    Pydantic defaults, derive from node_type. Otherwise honour caller."""
    default_cat, default_se = _NODE_TYPE_DEFAULTS.get(
        body.node_type, ("processing", "read_only"),
    )
    category = body.category if body.category != "data_input" else default_cat
    side_effect = body.side_effect_class if body.side_effect_class != "read_only" else default_se
    return category, side_effect


@router.post("/workflows/{workflow_id}/nodes", response_model=NodeOut, status_code=201)
async def create_node(
    body: NodeCreate,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Workspace-scoped read after mig 059 — caller can see workflows
        # of any subsidiary in their workspace.
        wf = await conn.fetchrow(
            "SELECT enterprise_id, department_id, workspace_id FROM workflows WHERE workflow_id = $1",
            workflow_id,
        )
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        resolved_category, resolved_side_effect = _resolve_node_defaults(body)
        row = await conn.fetchrow(
            """INSERT INTO workflow_nodes
                  (workflow_id, enterprise_id, workspace_id, department_id,
                   node_type, category, side_effect_class,
                   position_x, position_y,
                   title, title_vi, note, hashtags,
                   required_document_types, expected_mapping_template_id,
                   config, sequence_order, decision_config, node_type_catalog_key,
                   lane_name)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                       $14::jsonb, $15, $16::jsonb, $17, $18::jsonb, $19, $20)
               RETURNING *""",
            workflow_id, wf["enterprise_id"], wf["workspace_id"], wf["department_id"],
            body.node_type, resolved_category, resolved_side_effect,
            body.position_x, body.position_y,
            body.title, body.title_vi, body.note, body.hashtags,
            _json(body.required_document_types), body.expected_mapping_template_id,
            _json(body.config), body.sequence_order, _json(body.decision_config),
            body.node_type_catalog_key, body.lane_name or None,
        )
    return _row_to_node(row)


@router.put("/workflows/{workflow_id}/nodes/{node_id}", response_model=NodeOut)
async def update_node(
    body: NodeUpdate,
    workflow_id: UUID = Path(...),
    node_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    sets, params = [], []
    for col, val in (
        ("title", body.title), ("title_vi", body.title_vi),
        ("note", body.note),
        ("position_x", body.position_x), ("position_y", body.position_y),
        ("sequence_order", body.sequence_order),
        ("expected_mapping_template_id", body.expected_mapping_template_id),
    ):
        if val is not None:
            params.append(val)
            sets.append(f"{col} = ${len(params)}")
    if body.hashtags is not None:
        params.append(body.hashtags)
        sets.append(f"hashtags = ${len(params)}")
    if body.required_document_types is not None:
        params.append(_json(body.required_document_types))
        sets.append(f"required_document_types = ${len(params)}::jsonb")
    if body.config is not None:
        params.append(_json(body.config))
        sets.append(f"config = ${len(params)}::jsonb")
    if body.decision_config is not None:
        params.append(_json(body.decision_config))
        sets.append(f"decision_config = ${len(params)}::jsonb")
    if body.node_type is not None:
        params.append(body.node_type)
        sets.append(f"node_type = ${len(params)}")
    if body.node_type_catalog_key is not None:
        # empty string clears it (back to design-only); else set the executor key.
        params.append(body.node_type_catalog_key or None)
        sets.append(f"node_type_catalog_key = ${len(params)}")
    if body.lane_name is not None:
        # '' clears the lane (→ default "Chung" lane in the BPMN swimlane).
        params.append(body.lane_name or None)
        sets.append(f"lane_name = ${len(params)}")
    if not sets:
        # No-op update — fetch + return.
        async with acquire_for_tenant(x_enterprise_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_nodes WHERE node_id = $1 AND workflow_id = $2",
                node_id, workflow_id,
            )
        if row is None:
            raise HTTPException(status_code=404, detail="node not found")
        return _row_to_node(row)
    sets.append("updated_at = NOW()")
    params.extend([node_id, workflow_id])
    sql = (
        f"UPDATE workflow_nodes SET {', '.join(sets)} "
        f"WHERE node_id = ${len(params) - 1} AND workflow_id = ${len(params)} "
        f"RETURNING *"
    )
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(sql, *params)
    if row is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _row_to_node(row)


@router.delete("/workflows/{workflow_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    workflow_id: UUID = Path(...),
    node_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "DELETE FROM workflow_nodes WHERE node_id = $1 AND workflow_id = $2",
            node_id, workflow_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="node not found")


# ─── Edge CRUD ───────────────────────────────────────────────────────


@router.post("/workflows/{workflow_id}/edges", response_model=EdgeOut, status_code=201)
async def create_edge(
    body: EdgeCreate,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    if body.source_node_id == body.target_node_id:
        raise HTTPException(status_code=400, detail="self-loop edges not allowed")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            "SELECT enterprise_id, workspace_id FROM workflows WHERE workflow_id = $1",
            workflow_id,
        )
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        # Validate both endpoints belong to this workflow (workspace-scoped RLS).
        endpoints = await conn.fetch(
            """SELECT node_id FROM workflow_nodes
               WHERE workflow_id = $1 AND node_id = ANY($2::uuid[])""",
            workflow_id,
            [body.source_node_id, body.target_node_id],
        )
        if len(endpoints) != 2:
            raise HTTPException(
                status_code=400,
                detail="both source_node_id and target_node_id must belong to this workflow",
            )
        # NOTE: port_type column requires mig 114 (ADR-0035). Canonical/main DB
        # has it; pilot must apply migs 106–114 first (see pilot-db-state.md).
        row = await conn.fetchrow(
            """INSERT INTO workflow_edges
                  (workflow_id, enterprise_id, workspace_id, source_node_id, target_node_id, condition, label, port_type)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               ON CONFLICT (workflow_id, source_node_id, target_node_id) DO UPDATE
                  SET condition = EXCLUDED.condition, label = EXCLUDED.label,
                      port_type = EXCLUDED.port_type
               RETURNING *""",
            workflow_id, wf["enterprise_id"], wf["workspace_id"],
            body.source_node_id, body.target_node_id,
            body.condition, body.label, body.port_type,
        )
    return _row_to_edge(row)


@router.delete("/workflows/{workflow_id}/edges/{edge_id}", status_code=204)
async def delete_edge(
    workflow_id: UUID = Path(...),
    edge_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "DELETE FROM workflow_edges WHERE edge_id = $1 AND workflow_id = $2",
            edge_id, workflow_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="edge not found")


# ─── Tree view (anh's "sơ đồ tree") ──────────────────────────────────


@router.get("/workflows/{workflow_id}/tree", response_model=WorkflowTreeOut)
async def get_workflow_tree(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Hierarchical tree: workflow → nodes (each with attached_documents[]) → edges.

    FE renders this as the file-organizer view — user sees their workflow
    as a tree of cards, each card showing the documents uploaded into it.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Workspace-scoped RLS — drop caller-enterprise filter so a
        # Vingroup HQ user can read any subsidiary's workflow tree.
        wf_row = await conn.fetchrow(
            _WF_SELECT + " WHERE w.workflow_id = $1",
            workflow_id,
        )
        if wf_row is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        nodes = await conn.fetch(
            "SELECT * FROM workflow_nodes WHERE workflow_id = $1 ORDER BY sequence_order, created_at",
            workflow_id,
        )
        edges = await conn.fetch(
            "SELECT * FROM workflow_edges WHERE workflow_id = $1",
            workflow_id,
        )
        # Attached documents grouped by node_id. Single query (faster than N+1).
        # filename + sha256 live on pipeline_runs (joined via run_id) —
        # bronze_files only carries sheet_name + row_count + file_format.
        # tenant-filter-lint: allow JOIN to bronze_files + pipeline_runs is indirect
        # via workflow_step_documents (RLS-scoped by workflow_id ownership chain).
        # acquire_for_tenant GUC already set by caller — RLS enforces enterprise_id
        # on workflow_step_documents → safe transitively for the joined rows.
        docs = await conn.fetch(
            """SELECT sd.attachment_id, sd.node_id, sd.file_id, sd.document_kind,
                      sd.uploaded_at, sd.uploaded_by, sd.notes,
                      COALESCE(pr.filename, bf.sheet_name) AS filename,
                      bf.row_count,
                      COALESCE(pr.file_sha256, '') AS sha256
               FROM workflow_step_documents sd
               JOIN bronze_files bf ON bf.file_id = sd.file_id  -- tenant-filter-lint: allow
               LEFT JOIN pipeline_runs pr ON pr.run_id = bf.run_id  -- tenant-filter-lint: allow
               WHERE sd.workflow_id = $1
               ORDER BY sd.uploaded_at DESC""",
            workflow_id,
        )
    by_node: dict[UUID, list[dict]] = {}
    for d in docs:
        by_node.setdefault(d["node_id"], []).append({
            "attachment_id": str(d["attachment_id"]),
            "file_id":       str(d["file_id"]),
            "filename":      d["filename"],
            "row_count":     d["row_count"],
            "sha256":        d["sha256"],
            "document_kind": d["document_kind"],
            "uploaded_at":   d["uploaded_at"].isoformat() if d["uploaded_at"] else None,
            "uploaded_by":   str(d["uploaded_by"]) if d["uploaded_by"] else None,
            "notes":         d["notes"],
        })
    node_payloads = []
    for n in nodes:
        node_dict = _row_to_node(n).model_dump()
        node_dict["attached_documents"] = by_node.get(n["node_id"], [])
        node_payloads.append(node_dict)
    return WorkflowTreeOut(
        workflow=_row_to_workflow(wf_row),
        nodes=node_payloads,
        edges=[_row_to_edge(e) for e in edges],
    )


# ─── BPMN diagram (builder pivot 2026-05-29, mig 115) ────────────────


class BpmnDocOut(BaseModel):
    """The BPMN 2.0 XML authored in the bpmn-js builder for a workflow."""
    workflow_id:      UUID
    bpmn_xml:         Optional[str] = None
    last_modified_at: datetime
    # Design summary from the mapper — node/edge counts + non-executable
    # warnings (badge "⚙ Thiết kế — chưa thực thi"). None for GET when no
    # diagram is stored yet, or when the stored XML fails to parse.
    design_summary:   Optional[dict] = None


class BpmnDocUpdate(BaseModel):
    bpmn_xml:         str = Field(..., min_length=1, max_length=2_000_000)


@router.get("/workflows/{workflow_id}/bpmn", response_model=BpmnDocOut)
async def get_workflow_bpmn(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Return the stored BPMN 2.0 XML for a workflow (NULL = not authored;
    FE opens an empty canvas). Workspace-scoped RLS via acquire_for_tenant."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM workflows WHERE workflow_id = $1", workflow_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    # Tolerate DBs from before mig 115 (column absent) → bpmn_xml None.
    xml = row.get("bpmn_xml") if hasattr(row, "get") else None
    summary = None
    if xml:
        try:
            from ..workflow_runtime.bpmn_mapper import parse_bpmn_xml, summarize
            summary = summarize(parse_bpmn_xml(xml))
        except Exception:  # noqa: BLE001 — best-effort summary, never block GET
            summary = None
    return BpmnDocOut(
        workflow_id=row["workflow_id"],
        bpmn_xml=xml,
        last_modified_at=row["last_modified_at"],
        design_summary=summary,
    )


@router.put("/workflows/{workflow_id}/bpmn", response_model=BpmnDocOut)
async def put_workflow_bpmn(
    body: BpmnDocUpdate,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Store the BPMN XML authored in the builder. Validates it parses as
    BPMN 2.0 first (400 on malformed) and returns the design summary so the
    FE can show executable-coverage + ⚙ design-only badges immediately."""
    from ..workflow_runtime.bpmn_mapper import (
        BpmnParseError, parse_bpmn_xml, summarize,
    )

    try:
        diagram = parse_bpmn_xml(body.bpmn_xml)
    except BpmnParseError as exc:
        return JSONResponse(
            status_code=400,
            media_type="application/problem+json",
            content={
                "type":     "/problems/workflow-invalid-bpmn",
                "title":    "Invalid BPMN 2.0 XML",
                "status":   400,
                "code":     "WORKFLOW.INVALID_BPMN",
                "instance": f"/workflows/{workflow_id}/bpmn",
                "detail":   str(exc),
            },
        )

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE workflows
                  SET bpmn_xml = $1, last_modified_at = NOW(), last_modified_by = $2
               WHERE workflow_id = $3
               RETURNING *""",
            body.bpmn_xml, x_user_id, workflow_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return BpmnDocOut(
        workflow_id=row["workflow_id"],
        bpmn_xml=row.get("bpmn_xml") if hasattr(row, "get") else body.bpmn_xml,
        last_modified_at=row["last_modified_at"],
        design_summary=summarize(diagram),
    )


# structural workflow_nodes.node_type → BPMN element local-name (inverse of
# bpmn_mapper.structural_type_for, for the nodes→BPMN projection below).
_STRUCT_TO_BPMN_LOCAL = {
    "step":             "task",
    "decision_if_else": "exclusiveGateway",
    "decision_switch":  "inclusiveGateway",
    "approval_gate":    "userTask",
    "parallel_split":   "parallelGateway",
    "parallel_join":    "parallelGateway",
    "wait_event":       "intermediateCatchEvent",
    "sla_timer":        "intermediateCatchEvent",
    "notification":     "sendTask",
    "subworkflow":      "callActivity",
    "loop_foreach":     "subProcess",
    "loop_end":         "task",
}


@router.post("/workflows/{workflow_id}/bpmn/from-steps", response_model=BpmnDocOut)
async def project_steps_to_bpmn(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Reverse of /bpmn/sync — project the Builder's workflow_nodes + edges INTO a
    BPMN diagram so the BPMN tab renders the linear-Builder steps.

    READ-ONLY on the steps (writes only workflows.bpmn_xml), so unlike sync
    (BPMN→nodes *replace*) it never destroys builder work. Synthesises a start +
    end event around the step graph so bpmn-js imports a valid single-pool
    process. Idempotent — same steps → same diagram.
    """
    from ..workflow_runtime.bpmn_mapper import (
        MappedEdge, MappedNode, _to_bpmn_type, build_bpmn_xml,
        parse_bpmn_xml, summarize,
    )

    def _cid(prefix: str, raw) -> str:
        return prefix + str(raw).replace("-", "")

    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            "SELECT * FROM workflows WHERE workflow_id = $1", workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        node_rows = await conn.fetch(
            "SELECT * FROM workflow_nodes WHERE workflow_id = $1 "
            "ORDER BY sequence_order, created_at", workflow_id)
        edge_rows = await conn.fetch(
            "SELECT * FROM workflow_edges WHERE workflow_id = $1", workflow_id)
        if not node_rows:
            raise HTTPException(
                status_code=422, detail="workflow has no steps to project")

        import json as _j

        def _fmt_condition(dc) -> Optional[str]:
            """Format an if_else node's condition {left,op,right} → readable text
            so the BPMN gateway's outgoing flow can show it (e.g. so_tien >= 10000000)."""
            if isinstance(dc, str):
                try:
                    dc = _j.loads(dc)
                except Exception:
                    return None
            cond = (dc or {}).get("condition") if isinstance(dc, dict) else None
            if not isinstance(cond, dict):
                return None
            left = str(cond.get("left", "")).replace("$.input.", "").replace("$.upstream.", "")
            op, right = cond.get("op", ""), cond.get("right", "")
            return f"{left} {op} {right}".strip() or None

        id_map: dict = {}
        ifelse_cond: dict = {}   # source node_id → formatted condition text
        lane_of: dict = {}       # #9 — client_id → lane label (role responsible)
        any_lane = False
        mnodes: list[MappedNode] = []
        for i, n in enumerate(node_rows):
            nt = n["node_type"]
            local = _STRUCT_TO_BPMN_LOCAL.get(nt, "task")
            cid = n["bpmn_element_id"] or _cid("node_", n["node_id"])
            id_map[n["node_id"]] = cid
            if nt == "decision_if_else":
                ifelse_cond[n["node_id"]] = _fmt_condition(n["decision_config"])
            ln = (n["lane_name"] or "").strip() if "lane_name" in n else ""
            lane_of[cid] = ln or "Chung"
            if ln:
                any_lane = True
            px = float(n["position_x"]) if n["position_x"] is not None else 180.0 + i * 160.0
            py = float(n["position_y"]) if n["position_y"] is not None else 140.0
            mnodes.append(MappedNode(
                client_id=cid, bpmn_type=_to_bpmn_type(local),
                title=n["title_vi"] or n["title"] or "Bước",
                node_type=n["node_type_catalog_key"] or nt,
                structural_type=nt, executable=True,
                kaori_node_type=n["node_type_catalog_key"] or nt,
                event_definition=n["event_definition"],
                position_x=px, position_y=py,
            ))

        _TRUE = {"true", "yes", "có", "co", "t", "1", "pass", "passed"}
        medges: list[MappedEdge] = []
        for e in edge_rows:
            s = id_map.get(e["source_node_id"])
            t = id_map.get(e["target_node_id"])
            if not s or not t:
                continue
            cond_text = e["condition"]
            is_default = bool(e["is_default"])
            disp_label = e["label"]
            # For an if_else gateway: surface the node's condition on the TRUE
            # arm — both as the visible flow NAME ("so_tien >= 10000000" instead
            # of "có") and as a conditionExpression — and mark the SAI arm as the
            # gateway default flow. Pure display — the runner still routes by the
            # DB edge label token ('có'/'không') + the node config condition.
            src_cond = ifelse_cond.get(e["source_node_id"])
            if src_cond is not None:
                if str(e["label"] or "").strip().lower() in _TRUE:
                    cond_text = cond_text or src_cond
                    disp_label = src_cond or disp_label
                else:
                    is_default = True
                    disp_label = disp_label or "ngược lại"
            medges.append(MappedEdge(
                client_id=_cid("edge_", e["edge_id"]),
                source_client_id=s, target_client_id=t,
                condition=cond_text, label=disp_label,
                flow_kind=e["flow_kind"] or "sequence",
                is_default=is_default,
            ))

        # Synthesise start/end events so bpmn-js renders a valid process.
        has_in = {m.target_client_id for m in medges}
        has_out = {m.source_client_id for m in medges}
        roots = [m for m in mnodes if m.client_id not in has_in]
        leaves = [m for m in mnodes if m.client_id not in has_out]
        min_x = min((m.position_x for m in mnodes), default=180.0)
        max_x = max((m.position_x for m in mnodes), default=180.0)
        row_y = mnodes[0].position_y
        start = MappedNode(
            client_id="StartEvent_kaori", bpmn_type="bpmn:StartEvent",
            title="Bắt đầu", node_type=None, structural_type="step",
            executable=True, position_x=min_x - 140, position_y=row_y)
        end = MappedNode(
            client_id="EndEvent_kaori", bpmn_type="bpmn:EndEvent",
            title="Kết thúc", node_type=None, structural_type="step",
            executable=True, position_x=max_x + 160, position_y=row_y)
        for j, r in enumerate(roots or mnodes[:1]):
            medges.append(MappedEdge(
                client_id=f"edge_start_{j}",
                source_client_id="StartEvent_kaori", target_client_id=r.client_id))
        for j, lf in enumerate(leaves or mnodes[-1:]):
            medges.append(MappedEdge(
                client_id=f"edge_end_{j}",
                source_client_id=lf.client_id, target_client_id="EndEvent_kaori"))
        mnodes = [start] + mnodes + [end]
        # Start/End belong in the lane of the chain they bookend.
        lane_of["StartEvent_kaori"] = lane_of.get(
            (roots[0].client_id if roots else mnodes[1].client_id), "Chung")
        lane_of["EndEvent_kaori"] = lane_of.get(
            (leaves[0].client_id if leaves else mnodes[-2].client_id), "Chung")

        wf_name = (wf.get("name_vi") or wf.get("name") or "") if hasattr(wf, "get") else ""
        if any_lane:
            # #9 — at least one step has a role/lane → render a swimlane pool.
            # Group nodes by lane, preserving first-seen order; a node with no
            # explicit lane lands in "Chung".
            lane_order: list = []
            lane_members: dict = {}
            for m in mnodes:
                ln = lane_of.get(m.client_id, "Chung")
                if ln not in lane_members:
                    lane_members[ln] = []
                    lane_order.append(ln)
                lane_members[ln].append(m.client_id)
            lanes_grouping = [(ln, lane_members[ln]) for ln in lane_order]
            xml = build_bpmn_xml(mnodes, medges, process_name=wf_name, lanes=lanes_grouping)
        else:
            # No DI → the FE's bpmn-auto-layout lays the graph out as a branched
            # tree (gateways fork) instead of a straight line.
            xml = build_bpmn_xml(mnodes, medges, process_name=wf_name, include_di=False)
        saved = await conn.fetchrow(
            "UPDATE workflows SET bpmn_xml = $1, last_modified_at = NOW(), "
            "last_modified_by = $2 WHERE workflow_id = $3 RETURNING last_modified_at",
            xml, x_user_id, workflow_id)

    summary = None
    try:
        summary = summarize(parse_bpmn_xml(xml))
    except Exception:  # noqa: BLE001 — best-effort summary, never block
        summary = None
    return BpmnDocOut(
        workflow_id=workflow_id, bpmn_xml=xml,
        last_modified_at=saved["last_modified_at"], design_summary=summary,
    )


# ─── Dry-run (sample-record simulation) ──────────────────────────────
# Walk the graph statically with a sample input, evaluating decision nodes the
# same way the runtime does (if_else condition, switch ranges) — NO executor,
# NO side effects — so the builder can highlight the path a record would take.

class DryRunRequest(BaseModel):
    input: dict = Field(default_factory=dict)


class DryRunOut(BaseModel):
    visited_node_ids: list[str]
    taken_edge_ids:   list[str]
    trace:            list[dict]
    unreached:        list[str]


_DR_OPS = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    ">":  lambda a, b: a > b,  ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,  "<=": lambda a, b: a <= b,
}
_DR_TRUE = {"true", "yes", "có", "co", "t", "1", "pass", "passed"}
_DR_FALSE = {"false", "no", "không", "khong", "else", "f", "0", "default", "fail"}


def _dr_num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _dr_resolve(ref, inp):
    if isinstance(ref, str) and ref.startswith("$.input."):
        return inp.get(ref[len("$.input."):])
    if isinstance(ref, str) and ref.startswith("$."):
        return None   # upstream refs aren't known in a static dry-run
    return ref


def _dr_eval_cond(cond, inp) -> bool:
    if not isinstance(cond, dict):
        return False
    if "and" in cond:
        return all(_dr_eval_cond(c, inp) for c in cond["and"])
    if "or" in cond:
        return any(_dr_eval_cond(c, inp) for c in cond["or"])
    fn = _DR_OPS.get(cond.get("op"))
    if fn is None:
        return False
    left = _dr_resolve(cond.get("left"), inp)
    right = _dr_resolve(cond.get("right"), inp)
    if cond.get("op") in (">", ">=", "<", "<="):
        ln, rn = _dr_num(left), _dr_num(right)
        if ln is None or rn is None:
            return False
        left, right = ln, rn
    try:
        return bool(fn(left, right))
    except TypeError:
        return False


def _dr_switch_case(cfg, inp) -> str:
    val = _dr_resolve(cfg.get("input"), inp)
    for case in (cfg.get("cases") or []):
        if not isinstance(case, dict):
            continue
        if "min" in case or "max" in case:
            v, lo, hi = _dr_num(val), _dr_num(case.get("min")), _dr_num(case.get("max"))
            if v is None:
                continue
            if (lo is None or v >= lo) and (hi is None or v < hi):
                lbl = case.get("label")
                return str(lbl if lbl is not None else f"{case.get('min')}-{case.get('max')}").lower()
        else:
            if str(case.get("when")).strip().lower() == str(val).strip().lower():
                lbl = case.get("label")
                return str(lbl if lbl is not None else case.get("when")).lower()
    return "default"


@router.post("/workflows/{workflow_id}/dry-run", response_model=DryRunOut)
async def dry_run_workflow(
    body: DryRunRequest,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Simulate a sample record flowing through the workflow. Returns the nodes
    visited + edges taken so the builder can highlight the path — decision nodes
    are evaluated exactly as the runtime would, but nothing is executed."""
    import json as _j

    async with acquire_for_tenant(x_enterprise_id) as conn:
        nrows = await conn.fetch(
            "SELECT node_id, node_type, node_type_catalog_key, title, title_vi, "
            "       (COALESCE(config,'{}'::jsonb) "
            "        || COALESCE(decision_config,'{}'::jsonb)) AS cfg "
            "FROM workflow_nodes WHERE workflow_id = $1", workflow_id)
        erows = await conn.fetch(
            "SELECT edge_id, source_node_id, target_node_id, label, is_default, "
            "       port_type FROM workflow_edges WHERE workflow_id = $1", workflow_id)
    if not nrows:
        raise HTTPException(status_code=404, detail="workflow has no steps")

    nodes = {str(n["node_id"]): n for n in nrows}
    out_edges: dict = {}
    incoming: set = set()
    for e in erows:
        if (e["port_type"] or "main") != "main":
            continue
        s, t = str(e["source_node_id"]), str(e["target_node_id"])
        out_edges.setdefault(s, []).append(e)
        incoming.add(t)
    roots = [str(n["node_id"]) for n in nrows if str(n["node_id"]) not in incoming] \
        or [str(nrows[0]["node_id"])]

    inp = body.input or {}
    visited, taken, trace, seen = [], [], [], set()
    queue = list(roots)
    while queue:
        nid = queue.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        visited.append(nid)
        n = nodes.get(nid)
        if n is None:
            continue
        cfg = n["cfg"]
        if isinstance(cfg, str):
            try:
                cfg = _j.loads(cfg)
            except Exception:
                cfg = {}
        cfg = cfg or {}
        nt, key = n["node_type"], n["node_type_catalog_key"]
        outs = out_edges.get(nid, [])
        title = n["title_vi"] or n["title"]

        if nt == "decision_if_else" or key == "if_else":
            passed = _dr_eval_cond(cfg.get("condition"), inp)
            want = _DR_TRUE if passed else _DR_FALSE
            chosen = [e for e in outs
                      if str(e["label"] or "").strip().lower() in want
                      or (e["is_default"] and not passed)]
            trace.append({"node_id": nid, "title": title, "kind": "if_else",
                          "detail": "điều kiện ĐÚNG" if passed else "điều kiện SAI"})
        elif nt == "decision_switch" or key == "switch":
            mc = _dr_switch_case(cfg, inp)
            chosen = [e for e in outs
                      if str(e["label"] or "").strip().lower() == mc
                      or (e["is_default"] and mc == "default")]
            if not chosen:
                chosen = [e for e in outs
                          if str(e["label"] or "").strip().lower() == "default" or e["is_default"]]
            trace.append({"node_id": nid, "title": title, "kind": "switch",
                          "detail": f"khớp mức “{mc}”"})
        elif nt == "loop_foreach" or key == "loop_foreach":
            items_ref = cfg.get("items")
            items_val = _dr_resolve(items_ref, inp)
            n_items = len(items_val) if isinstance(items_val, list) else (
                0 if items_val is None else 1)
            fld = items_ref.replace("$.input.", "").replace("$.upstream.", "") if isinstance(items_ref, str) else "?"
            trace.append({"node_id": nid, "title": title, "kind": "loop",
                          "detail": f"lặp {n_items} lần qua “{fld}”"})
            chosen = outs   # follow into the body (highlighted; runs ×n_items at runtime)
        else:
            chosen = outs   # non-decision → every main edge is live

        for e in chosen:
            taken.append(str(e["edge_id"]))
            queue.append(str(e["target_node_id"]))

    unreached = [str(n["node_id"]) for n in nrows if str(n["node_id"]) not in seen]
    return DryRunOut(visited_node_ids=visited, taken_edge_ids=taken,
                     trace=trace, unreached=unreached)


class BpmnSyncOut(BaseModel):
    """Result of projecting the BPMN diagram onto workflow_nodes/edges."""
    workflow_id:        UUID
    nodes_created:      int
    edges_created:      int
    design_summary:     dict
    # Run-readiness: decision/fan-out nodes whose branches aren't fully wired
    # (reuses the same validator the state-transition gate uses). Empty = the
    # control-flow topology won't trip the dangling-branch guard.
    dangling_branches:  list[dict] = Field(default_factory=list)


@router.post("/workflows/{workflow_id}/bpmn/sync", response_model=BpmnSyncOut)
async def sync_workflow_bpmn(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Project the stored BPMN diagram → workflow_nodes + workflow_edges.

    Model A (anh chốt 2026-05-29): BPMN XML is the single source of truth, so
    this is a full **replace** of the workflow's nodes/edges from the diagram.
    The tree view + builder then render the BPMN-authored steps (with pool /
    lane / event-definition metadata, mig 116). Idempotent — re-running with the
    same XML yields the same graph.

    Returns counts + the design summary (design-only elements get the
    ⚙ "chưa thực thi" badge; running them on the runner is a later step that
    needs node_type_catalog_key reconcile — see WORKFLOW_BUILDER_REDESIGN.md).
    """
    from ..workflow_runtime.bpmn_mapper import (
        _STRUCTURAL_TYPES, BpmnParseError, parse_bpmn_xml, summarize,
    )

    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            "SELECT * FROM workflows WHERE workflow_id = $1", workflow_id,
        )
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        xml = wf.get("bpmn_xml") if hasattr(wf, "get") else None
        if not xml:
            raise HTTPException(
                status_code=422,
                detail="workflow has no BPMN diagram (PUT /bpmn first)",
            )

        # node_type_catalog keys are the source of truth for executor intent;
        # tolerate the table being absent on lean deployments.
        known: Optional[set] = None
        try:
            rows = await conn.fetch("SELECT node_type_key FROM node_type_catalog")
            known = {r["node_type_key"] for r in rows} or None
        except Exception:  # noqa: BLE001
            known = None

        try:
            diagram = parse_bpmn_xml(xml, known_node_types=known)
        except BpmnParseError as exc:
            return JSONResponse(
                status_code=400,
                media_type="application/problem+json",
                content={
                    "type":     "/problems/workflow-invalid-bpmn",
                    "title":    "Stored BPMN XML is invalid",
                    "status":   400,
                    "code":     "WORKFLOW.INVALID_BPMN",
                    "instance": f"/workflows/{workflow_id}/bpmn/sync",
                    "detail":   str(exc),
                },
            )

        ent_id, ws_id, dept_id = wf["enterprise_id"], wf["workspace_id"], wf["department_id"]
        client_to_real: dict[str, UUID] = {}

        async with conn.transaction():
            # Full replace — BPMN is the source of truth.
            await conn.execute(
                "DELETE FROM workflow_edges WHERE workflow_id = $1", workflow_id)
            await conn.execute(
                "DELETE FROM workflow_nodes WHERE workflow_id = $1", workflow_id)

            for idx, n in enumerate(diagram.nodes):
                new_id = uuid4()
                client_to_real[n.client_id] = new_id
                stype = n.structural_type if n.structural_type in _STRUCTURAL_TYPES else "step"
                category, side_effect = _NODE_TYPE_DEFAULTS.get(
                    stype, ("processing", "read_only"))
                await conn.execute(
                    """INSERT INTO workflow_nodes
                          (node_id, workflow_id, enterprise_id, workspace_id, department_id,
                           node_type, category, side_effect_class,
                           position_x, position_y, title, sequence_order,
                           required_document_types, config, decision_config,
                           bpmn_element_id, bpmn_type, node_type_catalog_key,
                           pool_name, lane_name, event_definition, attached_to_ref)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                               '[]'::jsonb, $20::jsonb, '{}'::jsonb,
                               $13,$14,$15,$16,$17,$18,$19)""",
                    new_id, workflow_id, ent_id, ws_id, dept_id,
                    stype, category, side_effect,
                    n.position_x, n.position_y, n.title, idx,
                    # node_type_catalog_key = the RESOLVED executor key (n.node_type),
                    # not the raw kaori attr (None on gateways/events). This is what
                    # the runner routes on (mig 117).
                    n.client_id, n.bpmn_type, n.node_type,
                    n.pool, n.lane, n.event_definition, n.attached_to,
                    # config — e.g. if_else condition lifted from the gateway flow.
                    _json(n.config or {}),
                )

            edges_created = 0
            for e in diagram.edges:
                src = client_to_real.get(e.source_client_id)
                tgt = client_to_real.get(e.target_client_id)
                if not src or not tgt or src == tgt:
                    continue
                await conn.execute(
                    """INSERT INTO workflow_edges
                          (workflow_id, enterprise_id, workspace_id,
                           source_node_id, target_node_id, condition, label,
                           port_type, flow_kind, is_default)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                       ON CONFLICT (workflow_id, source_node_id, target_node_id)
                          DO UPDATE SET condition = EXCLUDED.condition,
                                        label = EXCLUDED.label,
                                        flow_kind = EXCLUDED.flow_kind,
                                        is_default = EXCLUDED.is_default""",
                    workflow_id, ent_id, ws_id, src, tgt,
                    # condition column feeds the runner's branch-gating: prefer
                    # the lifted branch token ('true'/'false') over the raw expr,
                    # which now lives in the decision node's config.
                    (e.branch or e.condition), e.label, e.port_type, e.flow_kind, e.is_default,
                )
                edges_created += 1

        # Run-readiness: reuse the dangling-branch validator (same gate as the
        # TESTING/ACTIVE_BASELINE transition) so the builder can flag unwired
        # decision arms right after a sync.
        dangling = await _check_dangling_branches(conn, workflow_id)

    log.info(
        "workflow.bpmn.sync",
        workflow_id=str(workflow_id),
        nodes=len(client_to_real),
        edges=edges_created,
        dangling=len(dangling),
    )
    return BpmnSyncOut(
        workflow_id=workflow_id,
        nodes_created=len(client_to_real),
        edges_created=edges_created,
        design_summary=summarize(diagram),
        dangling_branches=dangling,
    )


# ─── Templates ───────────────────────────────────────────────────────


class WorkflowTemplateOut(BaseModel):
    template_id:        UUID
    display_name:       str
    display_name_vi:    str
    description:        Optional[str]
    department_type:    str
    category:           Optional[str]
    industry_vertical:  Optional[str]
    estimated_setup_minutes: int
    node_count:         int
    edge_count:         int


@router.get("/workflow-templates", response_model=list[WorkflowTemplateOut])
async def list_workflow_templates(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    department_type: Optional[str] = Query(
        None,
        pattern=r"^(marketing|sales|customer_service|warehouse|hr|finance|custom)$",
    ),
    industry: Optional[str] = Query(
        None,
        pattern=r"^(general|retail|manufacturing|fintech|logistics|healthcare|fmcg|saas)$",
        description="P2-S15: filter by industry_vertical for cohort-style template discovery (AI-HSC-016).",
    ),
):
    """List global workflow templates. Filter by dept_type and/or
    industry for the 'New Workflow' picker UI."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = """SELECT template_id, display_name, display_name_vi, description,
                        department_type, category, industry_vertical,
                        estimated_setup_minutes, workflow_definition
                 FROM workflow_templates
                 WHERE is_active = TRUE"""
        params: list[Any] = []
        if department_type is not None:
            params.append(department_type)
            sql += f" AND department_type = ${len(params)}"
        if industry is not None:
            params.append(industry)
            sql += f" AND industry_vertical = ${len(params)}"
        sql += " ORDER BY department_type, display_name"
        rows = await conn.fetch(sql, *params)
    out = []
    for r in rows:
        wf_def = r["workflow_definition"] or {}
        if isinstance(wf_def, str):
            import json
            wf_def = json.loads(wf_def)
        out.append(WorkflowTemplateOut(
            template_id=r["template_id"],
            display_name=r["display_name"],
            display_name_vi=r["display_name_vi"],
            description=r["description"],
            department_type=r["department_type"],
            category=r["category"],
            industry_vertical=r["industry_vertical"],
            estimated_setup_minutes=r["estimated_setup_minutes"],
            node_count=len(wf_def.get("nodes", [])),
            edge_count=len(wf_def.get("edges", [])),
        ))
    return out


# ─── P2-S15: node_type_catalog endpoints (mig 068) ───────────────────


class NodeTypeCatalogOut(BaseModel):
    """One row of mig 068 node_type_catalog — drives builder palette + retry policy."""
    node_type_key:          str
    category:               str
    side_effect_class:      str
    is_irreversible:        bool
    requires_saga:          bool
    default_retry_policy:   dict
    config_schema_json:     dict
    # ADR-0034 B4 — FE-only render hints (labels_vi / widget / group); never
    # affects validation (that stays config_schema_json). {} = render from schema.
    ui_schema_json:         dict = {}
    cost_band:              str
    pricing_tier_required:  Optional[str]
    rate_limit_json:        Optional[dict]
    compensating_action:    Optional[str]
    description_vi:         str
    sort_order:             int
    # ADR-0034 B3 / K-20 — node-type version (bump on behaviour change).
    type_version:           int = 1
    # ADR-0035 B6 — TRUE for trigger (event/entry) node types; builder shows
    # them as trigger blocks.
    is_trigger:             bool = False


@router.get("/workflow-node-types", response_model=list[NodeTypeCatalogOut])
async def list_node_types(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    category: Optional[str] = Query(
        None,
        pattern=r"^(data_input|processing|decision|ai|action|output)$",
        description="Filter to one of the 6 categories. Omit to get all 45 rows.",
    ),
):
    """List the 45-row node_type_catalog (mig 068). FE builder palette
    reads this to render draggable node options."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = """SELECT node_type_key, category, side_effect_class,
                        is_irreversible, requires_saga, default_retry_policy,
                        config_schema_json, ui_schema_json, cost_band,
                        pricing_tier_required, rate_limit_json,
                        compensating_action, description_vi, sort_order,
                        type_version, is_trigger
                 FROM node_type_catalog"""
        params: list[Any] = []
        if category is not None:
            params.append(category)
            sql += f" WHERE category = ${len(params)}"
        sql += " ORDER BY sort_order"
        rows = await conn.fetch(sql, *params)
    import json
    out = []
    for r in rows:
        def _maybe_load(v):
            if v is None:
                return None
            if isinstance(v, str):
                return json.loads(v)
            return v
        out.append(NodeTypeCatalogOut(
            node_type_key=r["node_type_key"],
            category=r["category"],
            side_effect_class=r["side_effect_class"],
            is_irreversible=r["is_irreversible"],
            requires_saga=r["requires_saga"],
            default_retry_policy=_maybe_load(r["default_retry_policy"]),
            config_schema_json=_maybe_load(r["config_schema_json"]),
            ui_schema_json=_maybe_load(r["ui_schema_json"]) or {},
            cost_band=r["cost_band"],
            pricing_tier_required=r["pricing_tier_required"],
            rate_limit_json=_maybe_load(r["rate_limit_json"]),
            compensating_action=r["compensating_action"],
            description_vi=r["description_vi"],
            sort_order=r["sort_order"],
            type_version=r["type_version"],
            is_trigger=r["is_trigger"],
        ))
    return out


@router.post("/workflows/from-template", response_model=WorkflowOut, status_code=201)
async def clone_from_template(
    body: CloneFromTemplateRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Clone a global template → real workflow + nodes + edges for this enterprise.

    The template's node `client_id`s ("n1", "n2"...) are replaced with
    real UUIDs before insert, and the edges' `source_client_id` /
    `target_client_id` are rewritten to point at those UUIDs.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Workspace-aware dept lookup — caller can clone into any dept in
        # their workspace (Vingroup HQ → any subsidiary).
        target_enterprise_id, workspace_id = await _resolve_dept_workspace_match(
            conn, x_enterprise_id, body.department_id,
        )
        tpl = await conn.fetchrow(
            "SELECT * FROM workflow_templates WHERE template_id = $1 AND is_active = TRUE",
            body.template_id,
        )
        if tpl is None:
            raise HTTPException(status_code=404, detail="template not found or inactive")

        wf_def = tpl["workflow_definition"]
        if isinstance(wf_def, str):
            import json
            wf_def = json.loads(wf_def)

        async with conn.transaction():
            wf_row = await conn.fetchrow(
                """INSERT INTO workflows
                      (enterprise_id, workspace_id, branch_id, department_id,
                       name, name_vi, description, category, business_function,
                       state, source, cloned_from_template_id, created_by, last_modified_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULL, 'DRAFT',
                           'template_based', $9, $10, $10)
                   RETURNING *""",
                target_enterprise_id, workspace_id, body.branch_id, body.department_id,
                body.custom_name or tpl["display_name"],
                tpl["display_name_vi"],
                tpl["description"],
                tpl["category"],
                body.template_id,
                x_user_id,
            )

            client_to_real: dict[str, UUID] = {}
            for raw_node in wf_def.get("nodes", []):
                new_id = uuid4()
                client_to_real[raw_node["client_id"]] = new_id
                await conn.execute(
                    """INSERT INTO workflow_nodes
                          (node_id, workflow_id, enterprise_id, workspace_id, department_id,
                           node_type, category, side_effect_class,
                           position_x, position_y,
                           title, title_vi, note, hashtags,
                           required_document_types, sequence_order, node_type_catalog_key)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                               $15::jsonb, $16, $17)""",
                    new_id, wf_row["workflow_id"], target_enterprise_id, workspace_id, body.department_id,
                    raw_node.get("node_type", "step"),
                    raw_node.get("category", "data_input"),
                    raw_node.get("side_effect_class", "read_only"),
                    raw_node.get("position_x", 0),
                    raw_node.get("position_y", 0),
                    raw_node["title"],
                    raw_node.get("title_vi"),
                    raw_node.get("note"),
                    raw_node.get("hashtags", []),
                    _json(raw_node.get("required_document_types", [])),
                    raw_node.get("sequence_order", 0),
                    # Carry the executor key from the template def so the cloned
                    # workflow is runnable (mig 117). NULL if the template omits it.
                    raw_node.get("node_type_catalog_key"),
                )

            for raw_edge in wf_def.get("edges", []):
                src = client_to_real.get(raw_edge["source_client_id"])
                tgt = client_to_real.get(raw_edge["target_client_id"])
                if not src or not tgt:
                    continue
                await conn.execute(
                    """INSERT INTO workflow_edges
                          (workflow_id, enterprise_id, workspace_id, source_node_id, target_node_id, label)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    wf_row["workflow_id"], target_enterprise_id, workspace_id, src, tgt,
                    raw_edge.get("label"),
                )
    return _row_to_workflow(wf_row)


# ─── Folder CRUD (mig 058) ───────────────────────────────────────────


class FolderCreate(BaseModel):
    workflow_id:      UUID
    node_id:          UUID
    name:             str = Field(..., min_length=1, max_length=200)
    parent_folder_id: Optional[UUID] = None
    sort_order:       int = 0


class FolderOut(BaseModel):
    folder_id:        UUID
    workflow_id:      UUID
    node_id:          UUID
    parent_folder_id: Optional[UUID]
    name:             str
    sort_order:       int
    status:           str


@router.post("/workflow-step-folders", response_model=FolderOut, status_code=201)
async def create_folder(
    body: FolderCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Create a folder under a workflow card. Optional parent_folder_id
    for nested sub-folders Windows-style. Per anh's directive 'sắp xếp
    ngăn nắp giống folder Win' 2026-05-15."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        node = await conn.fetchrow(
            """SELECT enterprise_id, workspace_id, department_id FROM workflow_nodes
               WHERE node_id = $1 AND workflow_id = $2""",
            body.node_id, body.workflow_id,
        )
        if node is None:
            raise HTTPException(status_code=404, detail="workflow node not found")

        # Validate parent folder if supplied — must be under same node.
        if body.parent_folder_id is not None:
            parent = await conn.fetchrow(
                """SELECT 1 FROM workflow_step_folders
                   WHERE folder_id = $1 AND node_id = $2 AND status = 'active'""",
                body.parent_folder_id, body.node_id,
            )
            if parent is None:
                raise HTTPException(
                    status_code=400,
                    detail="parent_folder_id not found under this node",
                )

        row = await conn.fetchrow(
            """INSERT INTO workflow_step_folders
                  (workflow_id, node_id, enterprise_id, workspace_id, department_id,
                   parent_folder_id, name, sort_order, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING *""",
            body.workflow_id, body.node_id, node["enterprise_id"], node["workspace_id"], node["department_id"],
            body.parent_folder_id, body.name, body.sort_order, x_user_id,
        )
    return FolderOut(
        folder_id=row["folder_id"],
        workflow_id=row["workflow_id"],
        node_id=row["node_id"],
        parent_folder_id=row["parent_folder_id"],
        name=row["name"],
        sort_order=row["sort_order"],
        status=row["status"],
    )


@router.delete("/workflow-step-folders/{folder_id}", status_code=204)
async def archive_folder(
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Soft-delete (sets status='archived'). Attached files stay; their
    folder_id remains pointing here but FE filters out archived."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            """UPDATE workflow_step_folders SET status='archived', updated_at=NOW()
               WHERE folder_id = $1 AND status = 'active'""",
            folder_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="folder not found or already archived")


# ─── Workflow stats (báo cáo per workflow — mig 058 Phase 2) ────────


@router.get("/workflows/{workflow_id}/stats")
async def get_workflow_stats(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Aggregate báo cáo + thống kê for a workflow.

    Returns:
      - file counts (total + per-step + per-document_kind)
      - cross-link counts (incoming + outgoing)
      - folder count
      - per-dept KPI snapshots (joins kpi_measurements via the workflow's
        department_id — caller's responsibility to ensure the dept has
        recent KPI computations).

    Read-only aggregation; no Temporal needed (Phase 1 static digital twin).
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            """SELECT workflow_id, name, name_vi, department_id, enterprise_id, branch_id
               FROM workflows WHERE workflow_id = $1""",
            workflow_id,
        )
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        # Per-step file counts + per-kind file counts in 1 query.
        file_rows = await conn.fetch(
            """SELECT sd.node_id, COUNT(*) AS file_count,
                      COALESCE(sd.document_kind, 'unknown') AS document_kind
               FROM workflow_step_documents sd
               WHERE sd.workflow_id = $1
                 AND sd.is_current = TRUE  -- count current docs, not superseded versions
               GROUP BY sd.node_id, sd.document_kind""",
            workflow_id,
        )
        total_files = sum(r["file_count"] for r in file_rows)
        per_step: dict[str, int] = {}
        per_kind: dict[str, int] = {}
        for r in file_rows:
            nid = str(r["node_id"])
            per_step[nid] = per_step.get(nid, 0) + r["file_count"]
            per_kind[r["document_kind"]] = per_kind.get(r["document_kind"], 0) + r["file_count"]

        # Cross-link counts.
        cross_counts = await conn.fetchrow(
            """SELECT
                 COUNT(*) FILTER (WHERE source_workflow_id = $1) AS outgoing,
                 COUNT(*) FILTER (WHERE target_workflow_id = $1) AS incoming
               FROM workflow_cross_links
               WHERE (source_workflow_id = $1 OR target_workflow_id = $1)
                 AND is_active = TRUE""",
            workflow_id,
        )

        # Folder count.
        folder_count = await conn.fetchval(
            """SELECT COUNT(*) FROM workflow_step_folders
               WHERE workflow_id = $1 AND status = 'active'""",
            workflow_id,
        ) or 0

        # Node + edge counts.
        node_count = await conn.fetchval(
            "SELECT COUNT(*) FROM workflow_nodes WHERE workflow_id = $1",
            workflow_id,
        ) or 0
        edge_count = await conn.fetchval(
            "SELECT COUNT(*) FROM workflow_edges WHERE workflow_id = $1",
            workflow_id,
        ) or 0

        # KPI snapshots for the dept. kpi_measurements may not exist
        # yet (no compute run); return [] in that case.
        kpis = []
        try:
            kpi_rows = await conn.fetch(
                """SELECT kpi_code, raw_value, classification,
                          period_kind, period_start, period_end, computed_at
                   FROM kpi_measurements
                   WHERE enterprise_id = $1 AND department_id = $2
                   ORDER BY computed_at DESC
                   LIMIT 30""",
                x_enterprise_id, wf["department_id"],
            )
            for k in kpi_rows:
                kpis.append({
                    "kpi_code":       k["kpi_code"],
                    "raw_value":      float(k["raw_value"]) if k["raw_value"] is not None else None,
                    "classification": k["classification"],
                    "period_kind":    k["period_kind"],
                    "period_start":   k["period_start"].isoformat() if k["period_start"] else None,
                    "period_end":     k["period_end"].isoformat() if k["period_end"] else None,
                    "computed_at":    k["computed_at"].isoformat() if k["computed_at"] else None,
                })
        except Exception:
            # kpi_measurements may not exist on every deployment — best
            # effort.
            kpis = []

    return {
        "workflow_id":     str(workflow_id),
        "workflow_name":   wf["name_vi"] or wf["name"],
        "department_id":   str(wf["department_id"]),
        "node_count":      node_count,
        "edge_count":      edge_count,
        "folder_count":    folder_count,
        "total_files":     total_files,
        "files_per_step":  per_step,
        "files_per_kind":  per_kind,
        "cross_links": {
            "incoming": cross_counts["incoming"] if cross_counts else 0,
            "outgoing": cross_counts["outgoing"] if cross_counts else 0,
        },
        "recent_kpis":     kpis,
    }


# ─── Cross-workflow links (mig 057) ──────────────────────────────────


class CrossLinkCreate(BaseModel):
    source_workflow_id: UUID
    source_node_id:     Optional[UUID] = None
    target_workflow_id: UUID
    target_node_id:     Optional[UUID] = None
    link_type:          str = Field(default="triggers", pattern=r"^(triggers|depends_on|notifies|data_handoff)$")
    condition:          Optional[str] = Field(default=None, max_length=2000)
    label:              Optional[str] = Field(default=None, max_length=200)


class CrossLinkOut(BaseModel):
    link_id:                UUID
    workspace_id:           UUID
    source_workflow_id:     UUID
    source_node_id:         Optional[UUID]
    target_workflow_id:     UUID
    target_node_id:         Optional[UUID]
    link_type:              str
    condition:              Optional[str]
    label:                  Optional[str]
    is_active:              bool


class CrossLinkEnrichedOut(CrossLinkOut):
    """Tree-viewer shape — adds display names + cross-dimension flags."""
    source_workflow_name:    Optional[str]
    source_workflow_name_vi: Optional[str]
    source_enterprise_name:  Optional[str]
    source_node_title:       Optional[str]
    source_node_title_vi:    Optional[str]
    source_department_name:  Optional[str]
    source_dept_type:        Optional[str]
    target_workflow_name:    Optional[str]
    target_workflow_name_vi: Optional[str]
    target_enterprise_name:  Optional[str]
    target_node_title:       Optional[str]
    target_node_title_vi:    Optional[str]
    target_department_name:  Optional[str]
    target_dept_type:        Optional[str]
    crosses_enterprise:      bool
    crosses_department:      bool
    crosses_branch:          bool
    crosses_division:        bool
    crosses_corporate_group: bool


@router.post("/workflow-cross-links", response_model=CrossLinkOut, status_code=201)
async def create_cross_link(
    body: CrossLinkCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Declare a cross-workflow dependency.

    Per anh 2026-05-15: 1 phòng ban có nhiều workflow; workflow phòng A
    có thể liên quan workflow phòng B của công ty khác / chi nhánh khác /
    mảng khác. This endpoint records the link statically; Phase 2 Temporal
    runtime will fire on link_type='triggers'.
    """
    if body.source_workflow_id == body.target_workflow_id:
        raise HTTPException(status_code=400, detail="source and target workflow must differ")

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Resolve both workflows + verify same workspace.
        rows = await conn.fetch(
            """SELECT w.workflow_id, w.enterprise_id, w.department_id, e.workspace_id
               FROM workflows w
               JOIN enterprises e ON e.enterprise_id = w.enterprise_id
               WHERE w.workflow_id = ANY($1::uuid[])""",
            [body.source_workflow_id, body.target_workflow_id],
        )
        if len(rows) != 2:
            raise HTTPException(status_code=404, detail="one or both workflows not found")
        src = next((r for r in rows if r["workflow_id"] == body.source_workflow_id), None)
        tgt = next((r for r in rows if r["workflow_id"] == body.target_workflow_id), None)
        if src is None or tgt is None:
            raise HTTPException(status_code=404, detail="workflow lookup failed")
        if src["workspace_id"] != tgt["workspace_id"]:
            raise HTTPException(
                status_code=400,
                detail="cross-workspace links not supported (Phase 2)",
            )

        row = await conn.fetchrow(
            """INSERT INTO workflow_cross_links
                  (workspace_id,
                   source_workflow_id, source_node_id,
                   target_workflow_id, target_node_id,
                   link_type, condition, label,
                   source_enterprise_id, source_department_id,
                   target_enterprise_id, target_department_id,
                   created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
               ON CONFLICT (source_workflow_id, target_workflow_id, link_type)
                  WHERE is_active = TRUE
               DO UPDATE SET condition = EXCLUDED.condition, label = EXCLUDED.label
               RETURNING *""",
            src["workspace_id"],
            body.source_workflow_id, body.source_node_id,
            body.target_workflow_id, body.target_node_id,
            body.link_type, body.condition, body.label,
            src["enterprise_id"], src["department_id"],
            tgt["enterprise_id"], tgt["department_id"],
            x_user_id,
        )
    return CrossLinkOut(
        link_id=row["link_id"],
        workspace_id=row["workspace_id"],
        source_workflow_id=row["source_workflow_id"],
        source_node_id=row["source_node_id"],
        target_workflow_id=row["target_workflow_id"],
        target_node_id=row["target_node_id"],
        link_type=row["link_type"],
        condition=row["condition"],
        label=row["label"],
        is_active=row["is_active"],
    )


@router.get("/workflow-cross-links", response_model=list[CrossLinkEnrichedOut])
async def list_cross_links(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    workflow_id: Optional[UUID] = None,
):
    """List cross-workflow links visible to the caller. When workflow_id
    is supplied, returns only links touching that workflow (in or out)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = """SELECT * FROM v_workflow_cross_links_enriched
                 WHERE is_active = TRUE"""
        params: list[Any] = []
        if workflow_id is not None:
            sql += " AND (source_workflow_id = $1 OR target_workflow_id = $1)"
            params.append(workflow_id)
        sql += " ORDER BY created_at DESC"
        rows = await conn.fetch(sql, *params)
    return [CrossLinkEnrichedOut(
        link_id=r["link_id"], workspace_id=r["workspace_id"],
        source_workflow_id=r["source_workflow_id"], source_node_id=r["source_node_id"],
        target_workflow_id=r["target_workflow_id"], target_node_id=r["target_node_id"],
        link_type=r["link_type"], condition=r["condition"], label=r["label"],
        is_active=r["is_active"],
        source_workflow_name=r["source_workflow_name"],
        source_workflow_name_vi=r["source_workflow_name_vi"],
        source_enterprise_name=r["source_enterprise_name"],
        source_node_title=r["source_node_title"],
        source_node_title_vi=r["source_node_title_vi"],
        source_department_name=r["source_department_name"],
        source_dept_type=r["source_dept_type"],
        target_workflow_name=r["target_workflow_name"],
        target_workflow_name_vi=r["target_workflow_name_vi"],
        target_enterprise_name=r["target_enterprise_name"],
        target_node_title=r["target_node_title"],
        target_node_title_vi=r["target_node_title_vi"],
        target_department_name=r["target_department_name"],
        target_dept_type=r["target_dept_type"],
        crosses_enterprise=r["crosses_enterprise"] or False,
        crosses_department=r["crosses_department"] or False,
        crosses_branch=r["crosses_branch"] or False,
        crosses_division=r["crosses_division"] or False,
        crosses_corporate_group=r["crosses_corporate_group"] or False,
    ) for r in rows]


@router.delete("/workflow-cross-links/{link_id}", status_code=204)
async def delete_cross_link(
    link_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "DELETE FROM workflow_cross_links WHERE link_id = $1", link_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="cross-link not found")


# ─── Workflow run endpoints (mig 088 — execution state) ─────────────


class WorkflowRunCreate(BaseModel):
    """Body for POST /workflows/{id}/run. enterprise_id from JWT header only."""
    input_data:       dict[str, Any] = Field(default_factory=dict)
    trigger_source:   str = Field(default="manual",
                                   pattern=r"^(manual|schedule|webhook|event|api)$")


class WorkflowRunOut(BaseModel):
    run_id:           UUID
    workflow_id:      UUID
    status:           str
    trigger_source:   str
    started_at:       datetime
    ended_at:         Optional[datetime] = None
    triggered_by_user_id: Optional[UUID] = None
    input_data:       dict[str, Any]
    output_data:      Optional[dict[str, Any]] = None
    error_summary:    Optional[str] = None


class WorkflowRunNodeOut(BaseModel):
    run_node_id:      UUID
    node_id:          UUID
    node_type_key:    str
    side_effect_class: str
    sequence_order:   int
    status:           str
    input_data:       dict[str, Any]
    output_data:      Optional[dict[str, Any]] = None
    error_message:    Optional[str] = None
    retry_count:      int
    started_at:       Optional[datetime] = None
    ended_at:         Optional[datetime] = None


@router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunOut, status_code=202)
async def start_workflow_run(
    background_tasks:   BackgroundTasks,
    body:               WorkflowRunCreate,
    workflow_id:        UUID = Path(...),
    x_enterprise_id:    UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:          Optional[UUID] = Header(default=None, alias="X-User-ID"),
    idempotency_key:    Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Start a new workflow run.

    Validates every node in the workflow has a registered executor
    before persisting the run row — fail-fast prevents starting runs
    that will stall halfway. Returns 202 with the run_id; the caller
    polls GET /workflow-runs/{id} for status.

    K-13 idempotency: pass Idempotency-Key header; duplicate POSTs
    return the existing run_id.
    """
    # Lazy imports — keep router boot fast + avoid circular imports
    from ..workflow_runtime.node_executor import REGISTRY
    from ..workflow_runtime.runner import WorkflowRunner, run_in_background
    from ..workflow_runtime import executors as _ensure_registered  # noqa: F401

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # K-22 (ADR-0041) — refuse to start a run for an AI use classified
        # 'prohibited' under the EU AI Act, before any run side-effect.
        if await _check_prohibited_use(conn, workflow_id):
            return _prohibited_problem(workflow_id)
        wf = await conn.fetchrow(
            # NB: only workspace_id is used below; `status` was an unused column
            # that doesn't exist on the lean pilot schema (it has `state`) and
            # crashed the run trigger with UndefinedColumn.
            "SELECT workflow_id, workspace_id FROM workflows "
            "WHERE workflow_id = $1",
            workflow_id,
        )
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        nodes = await conn.fetch(
            "SELECT node_id, node_type_catalog_key FROM workflow_nodes "
            "WHERE workflow_id = $1",
            workflow_id,
        )

    if not nodes:
        raise HTTPException(status_code=422, detail="workflow has no nodes")

    missing = [
        r["node_type_catalog_key"] for r in nodes
        if not REGISTRY.has(r["node_type_catalog_key"])
    ]
    if missing:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=422,
            media_type="application/problem+json",
            content={
                "type":    "https://kaori.ai/errors/workflow.executor-missing",
                "title":   "Workflow has nodes without registered executors",
                "status":  422,
                "detail":  "Cannot start run — at least one node type is not implemented yet.",
                "missing_node_types": sorted(set(missing)),
                "registered_node_types": REGISTRY.list_keys(),
            },
        )

    # Phase 2.7 P2 — concurrent-workflow quota pre-flight gate. Consume
    # one unit from workflow_concurrent (default 20, rolling 1-min
    # window per tenant_quotas seed). On QuotaExceeded → 429 RFC 7807
    # WITHOUT creating the workflow_runs row, so the failed attempt
    # doesn't pollute the run history.
    try:
        from ..shared import tenant_quotas as _quotas
        await _quotas.check_and_consume(
            enterprise_id=x_enterprise_id,
            quota_type="workflow_concurrent",
            amount=1,
        )
    except _quotas.QuotaExceeded as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            media_type="application/problem+json",
            content={
                "type":       "https://kaori.ai/errors/workflow.quota-exceeded",
                "title":      "Workflow concurrent-run quota exceeded",
                "status":     429,
                "detail":     str(exc),
                "quota_type": exc.quota_type,
                "period":     exc.period,
                "max_value":  exc.max_value,
                "current":    exc.current,
            },
        )

    run_id = await WorkflowRunner.create_run(
        workflow_id=workflow_id,
        enterprise_id=x_enterprise_id,
        workspace_id=wf["workspace_id"],
        triggered_by=x_user_id,
        trigger_source=body.trigger_source,
        input_data=body.input_data,
        idempotency_key=idempotency_key,
    )

    background_tasks.add_task(
        run_in_background,
        run_id=run_id,
        enterprise_id=x_enterprise_id,
        user_id=x_user_id,
    )

    return await _fetch_run(x_enterprise_id, run_id)


@router.get("/workflow-runs/{run_id}", response_model=WorkflowRunOut)
async def get_workflow_run(
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Poll run status. RLS scopes via enterprise_id GUC."""
    return await _fetch_run(x_enterprise_id, run_id)


@router.get("/workflow-runs/{run_id}/nodes", response_model=list[WorkflowRunNodeOut])
async def list_workflow_run_nodes(
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Per-node execution detail. Ordered by sequence_order then started_at."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT run_node_id, node_id, node_type_key, side_effect_class, "
            "       sequence_order, status, input_data, output_data, "
            "       error_message, retry_count, started_at, ended_at "
            "FROM workflow_run_nodes WHERE run_id = $1 "
            "ORDER BY sequence_order, started_at NULLS LAST",
            run_id,
        )
    return [WorkflowRunNodeOut(**_coerce_jsonb_row(dict(r))) for r in rows]


@router.get("/workflows/{workflow_id}/runs", response_model=list[WorkflowRunOut])
async def list_workflow_runs(
    workflow_id:      UUID = Path(...),
    limit:            int  = Query(default=50, ge=1, le=500),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
):
    """List recent runs of a workflow."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT run_id, workflow_id, status, trigger_source, started_at, "
            "       ended_at, triggered_by_user_id, input_data, output_data, "
            "       error_summary "
            "FROM workflow_runs WHERE workflow_id = $1 "
            "ORDER BY started_at DESC LIMIT $2",
            workflow_id, limit,
        )
    return [WorkflowRunOut(**_coerce_jsonb_row(dict(r))) for r in rows]


# ─── Approval endpoints (resume awaiting_approval runs) ─────────────


class WorkflowApprovalAction(BaseModel):
    """Body for POST /workflow-runs/{run_id}/approve."""
    decision:        str = Field(..., pattern=r"^(approve|reject)$")
    decision_note:   Optional[str] = Field(default=None, max_length=2000)


class WorkflowApprovalOut(BaseModel):
    approval_id:        UUID
    run_id:             UUID
    node_id:            UUID
    approver_roles:     list[str]
    approver_user_id:   Optional[UUID] = None
    sla_minutes:        int
    reason_prompt:      str
    status:             str
    resolved_by_user_id: Optional[UUID] = None
    resolved_at:        Optional[datetime] = None
    decision_note:      Optional[str] = None
    created_at:         datetime


@router.get("/workflow-runs/{run_id}/approvals", response_model=list[WorkflowApprovalOut])
async def list_workflow_approvals(
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
):
    """List approval gates for a run (pending + historical)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT approval_id, run_id, node_id, approver_roles, "
            "       approver_user_id, sla_minutes, reason_prompt, status, "
            "       resolved_by_user_id, resolved_at, decision_note, created_at "
            "FROM workflow_approvals WHERE run_id = $1 "
            "ORDER BY created_at",
            run_id,
        )
    return [WorkflowApprovalOut(**dict(r)) for r in rows]


@router.post("/workflow-runs/{run_id}/approve", response_model=WorkflowRunOut)
async def approve_workflow_run(
    background_tasks: BackgroundTasks,
    body:             WorkflowApprovalAction,
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:        Optional[UUID] = Header(default=None, alias="X-User-ID"),
    x_user_role:      Optional[str]  = Header(default=None, alias="X-User-Role"),
):
    """Approve or reject the pending approval gate of a run.

    Body: {decision: 'approve'|'reject', decision_note: str?}

    Authorization: caller's role (X-User-Role from gateway-injected JWT)
    must be in workflow_approvals.approver_roles for the pending gate.
    If approver_user_id is set, X-User-ID must match exactly.

    K-13 anti-IDOR: server cross-checks role + user_id against the
    pending row — cannot approve gates outside your remit.

    On 'approve': run resumes in background via resume_after_approval.
    On 'reject':  run fails terminally; no resume.
    """
    from ..workflow_runtime.runner import resume_after_approval

    async with acquire_for_tenant(x_enterprise_id) as conn:
        pending = await conn.fetchrow(
            "SELECT approval_id, node_id, approver_roles, approver_user_id, "
            "       chain_id, level_no "
            "FROM workflow_approvals WHERE run_id = $1 AND status = 'pending' "
            "LIMIT 1",
            run_id,
        )
        if pending is None:
            raise HTTPException(
                status_code=404,
                detail="No pending approval for this run",
            )

        # K-13 authz check
        allowed_roles = set(pending["approver_roles"] or [])
        if x_user_role and x_user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"role {x_user_role!r} not in approver_roles {sorted(allowed_roles)}",
            )
        if pending["approver_user_id"] and pending["approver_user_id"] != x_user_id:
            raise HTTPException(
                status_code=403,
                detail="approval pinned to a different user",
            )

        # ADR-0037 Phase 2 — chained gate. Approve at a non-final level ADVANCES
        # the same row to the next level (stays paused); only the final level (or
        # a non-chained gate) resumes. A reject fails at any level.
        from ..workflow_runtime import approval_chain as _ac
        action = "resume"
        if pending["chain_id"] and pending["level_no"] is not None:
            level_nos = [r["level_no"] for r in await conn.fetch(
                "SELECT level_no FROM approval_levels WHERE chain_id = $1", pending["chain_id"])]
            action, next_no = _ac.advance_decision(body.decision, pending["level_no"], level_nos)
            if action == "advance":
                nxt = await conn.fetchrow(
                    "SELECT approver_roles, sla_minutes FROM approval_levels "
                    "WHERE chain_id = $1 AND level_no = $2", pending["chain_id"], next_no)
                # record this level's approval in the audit, then re-open next level
                # IN-PLACE (resolved_* cleared, created_at reset for the new SLA clock).
                await conn.execute(
                    "UPDATE workflow_approvals SET level_no = $2, "
                    "    approver_roles = $3, sla_minutes = $4, created_at = NOW(), "
                    "    resolved_by_user_id = NULL, resolved_at = NULL, decision_note = NULL "
                    "WHERE approval_id = $1",
                    pending["approval_id"], next_no,
                    list(nxt["approver_roles"]) if nxt else pending["approver_roles"],
                    (nxt["sla_minutes"] if nxt else None) or 1440)

        if action != "advance":
            new_status = "approved" if body.decision == "approve" else "rejected"
            await conn.execute(
                "UPDATE workflow_approvals SET status = $1, "
                "    resolved_by_user_id = $2, resolved_at = NOW(), "
                "    decision_note = $3 "
                "WHERE approval_id = $4",
                new_status, x_user_id, body.decision_note,
                pending["approval_id"],
            )

    # A level advance keeps the run paused — return current state, no resume/fail.
    if action == "advance":
        return await _fetch_run(x_enterprise_id, run_id)

    if body.decision == "approve":
        background_tasks.add_task(
            resume_after_approval,
            run_id=run_id,
            enterprise_id=x_enterprise_id,
            user_id=x_user_id,
        )
    # On reject: runner will pick up the rejection on next run() call
    # OR the next status fetch will reflect 'failed' after we update
    # workflow_runs manually here.
    else:
        async with acquire_for_tenant(x_enterprise_id) as conn:
            await conn.execute(
                "UPDATE workflow_runs SET status = 'failed', "
                "    error_summary = 'approval_rejected', "
                "    ended_at = NOW() "
                "WHERE run_id = $1 AND status = 'awaiting_approval'",
                run_id,
            )

    return await _fetch_run(x_enterprise_id, run_id)


# ─── Stop endpoint (human oversight — EU AI Act Art 14 / K-23) ──────


class WorkflowStopAction(BaseModel):
    """Body for POST /workflow-runs/{run_id}/stop (K-23 — human can stop a run)."""
    reason: Optional[str] = Field(default=None, max_length=2000)


_STOPPABLE_STATES = ("awaiting_approval", "running", "queued")


@router.post("/workflow-runs/{run_id}/stop", response_model=WorkflowRunOut)
async def stop_workflow_run(
    body:             WorkflowStopAction,
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:        Optional[UUID] = Header(default=None, alias="X-User-ID"),
):
    """Stop a run under human oversight (EU AI Act Art 14 / K-23): cancel the
    run + fire saga compensation for already-executed impactful nodes.
    Idempotent (K-13): stopping an already-cancelled run returns its state."""
    from ..workflow_runtime.compensation import run_compensation_chain

    async with acquire_for_tenant(x_enterprise_id) as conn:
        run = await conn.fetchrow(
            "SELECT status FROM workflow_runs WHERE run_id = $1", run_id,
        )
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        if run["status"] == "cancelled":
            return await _fetch_run(x_enterprise_id, run_id)   # idempotent
        if run["status"] not in _STOPPABLE_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"run status={run['status']!r} is not stoppable",
            )
        anchor = await conn.fetchrow(
            "SELECT node_id FROM workflow_run_nodes WHERE run_id = $1 "
            "ORDER BY ended_at DESC NULLS LAST LIMIT 1",
            run_id,
        )
        await conn.execute(
            "UPDATE workflow_approvals SET status = 'cancelled', resolved_at = NOW() "
            "WHERE run_id = $1 AND status = 'pending'",
            run_id,
        )
        await conn.execute(
            "UPDATE workflow_runs SET status = 'cancelled', ended_at = NOW() "
            "WHERE run_id = $1",
            run_id,
        )

    if anchor is not None:
        await run_compensation_chain(
            enterprise_id=x_enterprise_id, run_id=run_id,
            failed_node_id=anchor["node_id"],
        )

    try:
        from ..shared.ai_governance import record_ai_call
        await record_ai_call(
            enterprise_id=x_enterprise_id, task_kind="human_oversight_stop",
            model_version="rules-only", model_provider="kaori-compliance",
            prompt=f"stop|run={run_id}|reason={body.reason or ''}",
            output="run_cancelled", confidence=None, run_id=run_id,
        )
    except Exception:  # noqa: BLE001 — audit must not break the stop
        pass

    return await _fetch_run(x_enterprise_id, run_id)


# ─── Form submission ingest (for read_form_submission node) ────────


class FormSubmissionCreate(BaseModel):
    form_key:        str = Field(..., min_length=1, max_length=64)
    payload:         dict[str, Any]
    source_channel:  str = Field(default="web",
                                  pattern=r"^(web|mobile|webhook|email|zalo|api)$")


class FormSubmissionOut(BaseModel):
    submission_id:        UUID
    form_key:             str
    payload:              dict[str, Any]
    submitted_by_user_id: Optional[UUID] = None
    submitted_at:         datetime
    status:               str
    source_channel:       str


@router.post("/workflow-form-submissions",
              response_model=FormSubmissionOut, status_code=201)
async def create_form_submission(
    body:             FormSubmissionCreate,
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:        Optional[UUID] = Header(default=None, alias="X-User-ID"),
):
    """Ingest a form submission. Workflows with read_form_submission node
    pick this up on next run."""
    import json
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO workflow_form_submissions
                   (enterprise_id, form_key, payload,
                    submitted_by_user_id, source_channel)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING submission_id, form_key, payload,
                         submitted_by_user_id, submitted_at, status,
                         source_channel""",
            x_enterprise_id, body.form_key,
            json.dumps(body.payload), x_user_id, body.source_channel,
        )
    return FormSubmissionOut(**_coerce_jsonb_row(dict(row)))


async def _fetch_run(enterprise_id: UUID, run_id: UUID) -> WorkflowRunOut:
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT run_id, workflow_id, status, trigger_source, started_at, "
            "       ended_at, triggered_by_user_id, input_data, output_data, "
            "       error_summary "
            "FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return WorkflowRunOut(**_coerce_jsonb_row(dict(row)))


def _coerce_jsonb_row(row: dict[str, Any]) -> dict[str, Any]:
    """asyncpg JSONB returns str — Pydantic dict[str,Any] expects dict.
    Parse the few jsonb columns we round-trip."""
    import json
    for key in ("input_data", "output_data", "payload"):
        val = row.get(key)
        if isinstance(val, str):
            row[key] = json.loads(val) if val else None
    return row


# ─── Helpers ─────────────────────────────────────────────────────────


def _json(obj) -> str:
    """Compact JSON for asyncpg ::jsonb cast."""
    import json
    return json.dumps(obj, ensure_ascii=False)
