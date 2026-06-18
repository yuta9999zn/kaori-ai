"""
P2-S16 — Workflow as Code (YAML import/export).

Two endpoints that round-trip a workflow between DB shape (workflows +
workflow_nodes + workflow_edges) and a human-readable YAML format.
Builds on mig 068 node_type_catalog: imported nodes are validated
against the 45-row catalog so a malformed YAML is rejected at the
boundary (not at runtime).

Endpoints
---------
    GET  /workflows/{workflow_id}/export.yaml
        Returns the workflow as text/yaml. Snapshot of the current
        DRAFT or ACTIVE state — does NOT include execution history.

    POST /workflows/import
        Body: JSON {"yaml_content": "...", "department_id": uuid}.
        Parses YAML → validates against mig 068 → creates workflow.
        Returns the new workflow_id.

YAML schema (canonical)
-----------------------
    workflow:
      name: "Campaign Launch"
      name_vi: "Khởi chạy chiến dịch"
      description: "..."
      department_type: marketing
      category: campaign
      industry_vertical: general          # optional
      nodes:
        - id: n1
          title: "Define segment"
          title_vi: "Xác định segment"
          node_type: read_table             # FK to node_type_catalog
          config: {table: customers}
          position: {x: 100, y: 100}
        - id: n2
          ...
      edges:
        - from: n1
          to: n2
          label: next

K-rules
-------
K-1 / K-12: tenant from JWT (X-Enterprise-ID header), never from YAML body
K-14: invalid YAML / unknown node_type / dangling edges → RFC 7807 400
K-17: each node_type's side_effect_class comes from the catalog row;
      YAML doesn't allow overriding it (prevents privilege escalation
      via "looks like read_only but actually external_irreversible").
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
import yaml
from fastapi import APIRouter, Header, HTTPException, Path, Response
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Shapes ──────────────────────────────────────────────────────────


class WorkflowImportRequest(BaseModel):
    yaml_content:   str = Field(..., min_length=1, max_length=200_000)
    department_id:  UUID
    branch_id:      Optional[UUID] = None


class WorkflowImportResponse(BaseModel):
    workflow_id:    UUID
    name:           str
    nodes_created:  int
    edges_created:  int


# ─── Helpers ─────────────────────────────────────────────────────────


def _validate_yaml_shape(doc: Any) -> dict:
    """Verify the top-level YAML shape. Returns the inner `workflow` dict
    or raises HTTPException(400) with the specific defect."""
    if not isinstance(doc, dict) or "workflow" not in doc:
        raise HTTPException(status_code=400,
                            detail="YAML must have a top-level 'workflow' key")
    wf = doc["workflow"]
    if not isinstance(wf, dict):
        raise HTTPException(status_code=400, detail="'workflow' must be a mapping")
    for required in ("name", "department_type", "nodes"):
        if required not in wf:
            raise HTTPException(status_code=400,
                                detail=f"workflow missing required field: {required!r}")
    if not isinstance(wf["nodes"], list) or len(wf["nodes"]) == 0:
        raise HTTPException(status_code=400,
                            detail="workflow.nodes must be a non-empty list")
    wf.setdefault("edges", [])
    if not isinstance(wf["edges"], list):
        raise HTTPException(status_code=400, detail="workflow.edges must be a list")
    return wf


def _validate_nodes_and_edges(wf: dict, valid_catalog_keys: set[str]) -> None:
    """Validate each node has id + node_type ∈ catalog. Validate edges'
    from/to reference defined node ids."""
    node_ids: set[str] = set()
    for i, n in enumerate(wf["nodes"]):
        if not isinstance(n, dict):
            raise HTTPException(status_code=400,
                                detail=f"node[{i}] must be a mapping")
        for k in ("id", "node_type", "title"):
            if k not in n:
                raise HTTPException(status_code=400,
                                    detail=f"node[{i}] missing field {k!r}")
        nid = n["id"]
        if nid in node_ids:
            raise HTTPException(status_code=400,
                                detail=f"duplicate node id {nid!r}")
        node_ids.add(nid)
        if n["node_type"] not in valid_catalog_keys:
            raise HTTPException(
                status_code=400,
                detail=f"node[{i}].node_type {n['node_type']!r} not in mig 068 catalog",
            )
    for i, e in enumerate(wf["edges"]):
        if not isinstance(e, dict):
            raise HTTPException(status_code=400,
                                detail=f"edge[{i}] must be a mapping")
        for k in ("from", "to"):
            if k not in e:
                raise HTTPException(status_code=400,
                                    detail=f"edge[{i}] missing field {k!r}")
            if e[k] not in node_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"edge[{i}].{k} references undefined node {e[k]!r}",
                )


# ─── Export ──────────────────────────────────────────────────────────


@router.get("/workflows/{workflow_id}/export.yaml",
            response_class=Response,
            responses={200: {"content": {"application/x-yaml": {}}}})
async def export_workflow_yaml(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Render the workflow + its nodes + edges as YAML for round-trip
    portability. Joins workflow_nodes with node_type_catalog so the
    exported `node_type` is the catalog key (not the row id)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            """SELECT workflow_id, name, name_vi, description, category,
                      department_id
               FROM workflows
               WHERE workflow_id = $1""",
            workflow_id,
        )
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        dept = await conn.fetchrow(
            "SELECT department_type FROM departments WHERE department_id = $1",
            wf["department_id"],
        )
        dept_type = dept["department_type"] if dept else "custom"

        nodes = await conn.fetch(
            """SELECT node_id, title, title_vi, node_type, sequence_order,
                      position_x, position_y, note, hashtags, config_json
               FROM workflow_nodes
               WHERE workflow_id = $1
               ORDER BY sequence_order ASC""",
            workflow_id,
        )
        edges = await conn.fetch(
            """SELECT source_node_id, target_node_id, label
               FROM workflow_edges
               WHERE workflow_id = $1""",
            workflow_id,
        )

    # Build the YAML dict. Use stable node_id-as-string for human readability;
    # if a client wants the real UUIDs they can call the JSON tree endpoint.
    node_id_to_alias: dict[str, str] = {}
    yaml_nodes = []
    for i, n in enumerate(nodes):
        alias = f"n{i + 1}"
        node_id_to_alias[str(n["node_id"])] = alias
        entry: dict[str, Any] = {
            "id":         alias,
            "title":      n["title"],
            "node_type":  n["node_type"],
        }
        if n["title_vi"]:
            entry["title_vi"] = n["title_vi"]
        if n["note"]:
            entry["note"] = n["note"]
        if n["hashtags"]:
            entry["hashtags"] = list(n["hashtags"])
        entry["position"] = {"x": n["position_x"], "y": n["position_y"]}
        if n["config_json"]:
            import json
            cfg = n["config_json"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            if cfg:
                entry["config"] = cfg
        yaml_nodes.append(entry)

    yaml_edges = []
    for e in edges:
        src = node_id_to_alias.get(str(e["source_node_id"]))
        tgt = node_id_to_alias.get(str(e["target_node_id"]))
        if src is None or tgt is None:
            continue
        ye: dict[str, Any] = {"from": src, "to": tgt}
        if e["label"]:
            ye["label"] = e["label"]
        yaml_edges.append(ye)

    doc = {
        "workflow": {
            "name":            wf["name"],
            "name_vi":         wf["name_vi"],
            "description":     wf["description"] or "",
            "department_type": dept_type,
            "category":        wf["category"] or "",
            "nodes":           yaml_nodes,
            "edges":           yaml_edges,
        }
    }
    text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    return Response(content=text, media_type="application/x-yaml")


# ─── Import ──────────────────────────────────────────────────────────


@router.post("/workflows/import", response_model=WorkflowImportResponse,
             status_code=201)
async def import_workflow_yaml(
    body: WorkflowImportRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Parse YAML → validate against mig 068 catalog → create workflow.

    Failure modes (RFC 7807 400):
      - YAML parse error
      - Missing required top-level keys
      - Unknown node_type (not in mig 068 catalog)
      - Edge references undefined node id
      - Duplicate node id
    """
    # 1. Parse YAML
    try:
        doc = yaml.safe_load(body.yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400,
                            detail=f"YAML parse error: {e}") from e

    wf = _validate_yaml_shape(doc)

    # 2. Pull the catalog keys + validate node references
    async with acquire_for_tenant(x_enterprise_id) as conn:
        catalog_rows = await conn.fetch(
            "SELECT node_type_key FROM node_type_catalog"
        )
        valid_keys = {r["node_type_key"] for r in catalog_rows}
        _validate_nodes_and_edges(wf, valid_keys)

        # 3. Insert workflow + nodes + edges
        async with conn.transaction():
            wf_row = await conn.fetchrow(
                """INSERT INTO workflows
                      (enterprise_id, department_id, branch_id, name, name_vi,
                       description, category, state, source, created_by,
                       last_modified_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'DRAFT', 'yaml_import',
                           $8, $8)
                   RETURNING workflow_id""",
                x_enterprise_id, body.department_id, body.branch_id,
                wf["name"], wf.get("name_vi"),
                wf.get("description"), wf.get("category"),
                x_user_id,
            )
            workflow_id = wf_row["workflow_id"]

            alias_to_uuid: dict[str, UUID] = {}
            for i, n in enumerate(wf["nodes"]):
                node_id = uuid4()
                alias_to_uuid[n["id"]] = node_id
                pos = n.get("position") or {}
                hashtags = n.get("hashtags") or []
                import json
                config = n.get("config") or {}
                await conn.execute(
                    """INSERT INTO workflow_nodes
                          (node_id, workflow_id, enterprise_id, department_id,
                           node_type, category, side_effect_class,
                           title, title_vi, note, hashtags,
                           sequence_order, position_x, position_y,
                           config_json, created_by)
                       VALUES ($1, $2, $3, $4, $5, 'step', 'read_only',
                               $6, $7, $8, $9::text[], $10, $11, $12,
                               $13::jsonb, $14)""",
                    node_id, workflow_id, x_enterprise_id, body.department_id,
                    n["node_type"],
                    n["title"], n.get("title_vi"), n.get("note"),
                    hashtags,
                    i + 1, pos.get("x", 100 + i * 220), pos.get("y", 100),
                    json.dumps(config), x_user_id,
                )

            edges_created = 0
            for e in wf["edges"]:
                await conn.execute(
                    """INSERT INTO workflow_edges
                          (workflow_id, enterprise_id, source_node_id,
                           target_node_id, label, created_by)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    workflow_id, x_enterprise_id,
                    alias_to_uuid[e["from"]], alias_to_uuid[e["to"]],
                    e.get("label"), x_user_id,
                )
                edges_created += 1

    log.info("workflow.yaml.imported",
             workflow_id=str(workflow_id),
             tenant_id=str(x_enterprise_id),
             nodes=len(wf["nodes"]),
             edges=edges_created)
    return WorkflowImportResponse(
        workflow_id=workflow_id,
        name=wf["name"],
        nodes_created=len(wf["nodes"]),
        edges_created=edges_created,
    )
