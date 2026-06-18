"""
P15-S11 Tuần 8 — Corporate hierarchy CRUD + tree view (Vingroup-class).

Endpoints
---------

  GET    /corporate-tree                     — flat list of nodes (level,
                                                node_id, parent_id, name)
  GET    /corporate-tree/nested              — nested tree shape for FE

  POST   /corporate-groups                   — create tập đoàn
  GET    /corporate-groups/{id}              — get one
  PUT    /corporate-groups/{id}              — update
  DELETE /corporate-groups/{id}              — archive (soft)

  POST   /business-divisions                 — create mảng kinh doanh
  PUT    /business-divisions/{id}            — update
  DELETE /business-divisions/{id}            — delete

  PUT    /enterprises/{id}/parent             — re-parent (drag-drop in FE)
                                                {corporate_group_id?,
                                                 business_division_id?,
                                                 parent_enterprise_id?}

K-1 RLS uses `app.current_workspace_id` GUC (set by gateway from JWT).
For now the data-pipeline + ai-orchestrator share the existing
`app.current_enterprise_id` GUC; an enterprise-level user reading the
corporate tree sees only their own corporate_group via the workspace_id
join in the underlying view.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Pydantic shapes ─────────────────────────────────────────────────


class CorporateGroupCreate(BaseModel):
    workspace_id:  UUID
    name:          str = Field(..., min_length=1, max_length=200)
    name_vi:       Optional[str] = Field(default=None, max_length=200)
    description:   Optional[str] = Field(default=None, max_length=4000)
    founded_year:  Optional[int] = Field(default=None, ge=1800, le=2100)
    headquarters:  Optional[str] = Field(default=None, max_length=200)
    website:       Optional[str] = Field(default=None, max_length=200)


class CorporateGroupUpdate(BaseModel):
    name:         Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_vi:      Optional[str] = Field(default=None, max_length=200)
    description:  Optional[str] = Field(default=None, max_length=4000)
    headquarters: Optional[str] = Field(default=None, max_length=200)
    website:      Optional[str] = Field(default=None, max_length=200)
    status:       Optional[str] = Field(default=None, pattern=r"^(active|archived)$")


class CorporateGroupOut(BaseModel):
    corporate_group_id: UUID
    workspace_id:       UUID
    name:               str
    name_vi:            Optional[str]
    description:        Optional[str]
    founded_year:       Optional[int]
    headquarters:       Optional[str]
    website:            Optional[str]
    status:             str
    created_at:         datetime


class BusinessDivisionCreate(BaseModel):
    corporate_group_id: UUID
    name:               str = Field(..., min_length=1, max_length=200)
    name_vi:            Optional[str] = Field(default=None, max_length=200)
    description:        Optional[str] = Field(default=None, max_length=4000)
    industry_hint:      Optional[str] = Field(default=None, max_length=50)
    sort_order:         int = 0


class BusinessDivisionUpdate(BaseModel):
    name:           Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_vi:        Optional[str] = Field(default=None, max_length=200)
    description:    Optional[str] = Field(default=None, max_length=4000)
    industry_hint:  Optional[str] = Field(default=None, max_length=50)
    sort_order:     Optional[int] = None
    status:         Optional[str] = Field(default=None, pattern=r"^(active|archived)$")


class BusinessDivisionOut(BaseModel):
    division_id:        UUID
    corporate_group_id: UUID
    workspace_id:       UUID
    name:               str
    name_vi:            Optional[str]
    description:        Optional[str]
    industry_hint:      Optional[str]
    sort_order:         int
    status:             str


class EnterpriseParentUpdate(BaseModel):
    """Drag-drop re-parent payload — at most one of the three FKs at a time."""
    corporate_group_id:   Optional[UUID] = None
    business_division_id: Optional[UUID] = None
    parent_enterprise_id: Optional[UUID] = None


class TreeNodeOut(BaseModel):
    level:        int
    node_type:    str
    node_id:      UUID
    parent_id:    Optional[UUID]
    workspace_id: UUID
    name:         str
    display_name: str
    status:       str
    sort_order:   int


# ─── Helpers ─────────────────────────────────────────────────────────


def _row_to_corp_group(row) -> CorporateGroupOut:
    return CorporateGroupOut(
        corporate_group_id=row["corporate_group_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        name_vi=row["name_vi"],
        description=row["description"],
        founded_year=row["founded_year"],
        headquarters=row["headquarters"],
        website=row["website"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _row_to_division(row) -> BusinessDivisionOut:
    return BusinessDivisionOut(
        division_id=row["division_id"],
        corporate_group_id=row["corporate_group_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        name_vi=row["name_vi"],
        description=row["description"],
        industry_hint=row["industry_hint"],
        sort_order=row["sort_order"],
        status=row["status"],
    )


def _row_to_tree_node(row) -> TreeNodeOut:
    return TreeNodeOut(
        level=row["level"],
        node_type=row["node_type"],
        node_id=row["node_id"],
        parent_id=row["parent_id"],
        workspace_id=row["workspace_id"],
        name=row["name"],
        display_name=row["display_name"],
        status=row["status"],
        sort_order=row["sort_order"],
    )


# ─── Tree view ───────────────────────────────────────────────────────


@router.get("/corporate-tree", response_model=List[TreeNodeOut])
async def list_tree(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Flat list of all org nodes (group → division → enterprise) for
    the caller's workspace. FE renders the tree by parent_id linking."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Caller's workspace_id from the enterprise (RLS-safe lookup).
        ws_row = await conn.fetchrow(
            "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
            x_enterprise_id,
        )
        if ws_row is None:
            raise HTTPException(status_code=404, detail="enterprise not found")
        rows = await conn.fetch(
            """SELECT level, node_type, node_id, parent_id, workspace_id,
                      name, display_name, status, sort_order
               FROM v_corporate_tree
               WHERE workspace_id = $1
               ORDER BY level ASC, sort_order ASC, display_name ASC""",
            ws_row["workspace_id"],
        )
    return [_row_to_tree_node(r) for r in rows]


@router.get("/corporate-tree/nested")
async def get_nested_tree(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Build a nested tree shape from the flat view rows.

    Shape:
      {
        "groups": [
          { ...group..., "divisions": [
              { ...division..., "enterprises": [ { ...enterprise..., "children": [...] } ] }
          ]}
        ]
      }
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        ws_row = await conn.fetchrow(
            "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
            x_enterprise_id,
        )
        if ws_row is None:
            raise HTTPException(status_code=404, detail="enterprise not found")
        rows = await conn.fetch(
            """SELECT level, node_type, node_id, parent_id, workspace_id,
                      name, display_name, status, sort_order
               FROM v_corporate_tree
               WHERE workspace_id = $1
               ORDER BY level ASC, sort_order ASC, display_name ASC""",
            ws_row["workspace_id"],
        )

    by_id: dict[str, dict] = {}
    roots: List[dict] = []
    for r in rows:
        node = {
            "node_type":    r["node_type"],
            "node_id":      str(r["node_id"]),
            "parent_id":    str(r["parent_id"]) if r["parent_id"] else None,
            "name":         r["name"],
            "display_name": r["display_name"],
            "status":       r["status"],
            "sort_order":   r["sort_order"],
            "level":        r["level"],
            "children":     [],
        }
        by_id[node["node_id"]] = node

    for node in by_id.values():
        pid = node["parent_id"]
        if pid and pid in by_id:
            by_id[pid]["children"].append(node)
        else:
            roots.append(node)

    return {"roots": roots, "count": len(by_id)}


# ─── Corporate group CRUD ────────────────────────────────────────────


@router.post("/corporate-groups", response_model=CorporateGroupOut, status_code=201)
async def create_corporate_group(
    body: CorporateGroupCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Verify caller's enterprise belongs to the supplied workspace_id.
        guard = await conn.fetchrow(
            "SELECT 1 FROM enterprises WHERE enterprise_id = $1 AND workspace_id = $2",
            x_enterprise_id, body.workspace_id,
        )
        if guard is None:
            raise HTTPException(status_code=403, detail="workspace_id outside caller's enterprise")
        row = await conn.fetchrow(
            """INSERT INTO corporate_groups
                  (workspace_id, name, name_vi, description,
                   founded_year, headquarters, website, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING *""",
            body.workspace_id, body.name, body.name_vi, body.description,
            body.founded_year, body.headquarters, body.website, x_user_id,
        )
    return _row_to_corp_group(row)


@router.get("/corporate-groups/{group_id}", response_model=CorporateGroupOut)
async def get_corporate_group(
    group_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM corporate_groups WHERE corporate_group_id = $1",
            group_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="corporate group not found")
    return _row_to_corp_group(row)


@router.put("/corporate-groups/{group_id}", response_model=CorporateGroupOut)
async def update_corporate_group(
    body: CorporateGroupUpdate,
    group_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    sets, params = [], []
    for col, val in (
        ("name", body.name), ("name_vi", body.name_vi),
        ("description", body.description),
        ("headquarters", body.headquarters), ("website", body.website),
        ("status", body.status),
    ):
        if val is not None:
            params.append(val)
            sets.append(f"{col} = ${len(params)}")
    if not sets:
        return await get_corporate_group(group_id, x_enterprise_id)
    sets.append("updated_at = NOW()")
    params.append(group_id)
    sql = (
        f"UPDATE corporate_groups SET {', '.join(sets)} "
        f"WHERE corporate_group_id = ${len(params)} RETURNING *"
    )
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(sql, *params)
    if row is None:
        raise HTTPException(status_code=404, detail="corporate group not found")
    return _row_to_corp_group(row)


@router.delete("/corporate-groups/{group_id}", status_code=204)
async def archive_corporate_group(
    group_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Soft delete — sets status='archived'. Hard delete is intentionally
    not supported (would cascade-orphan subsidiaries; do that via the
    enterprise re-parent endpoint first)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            """UPDATE corporate_groups SET status = 'archived', updated_at = NOW()
               WHERE corporate_group_id = $1 AND status = 'active'""",
            group_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="corporate group not found or already archived")


# ─── Business division CRUD ──────────────────────────────────────────


@router.post("/business-divisions", response_model=BusinessDivisionOut, status_code=201)
async def create_business_division(
    body: BusinessDivisionCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Resolve workspace_id from the corporate_group (RLS-safe — must be
        # visible to the caller's workspace scope).
        cg = await conn.fetchrow(
            "SELECT workspace_id FROM corporate_groups WHERE corporate_group_id = $1",
            body.corporate_group_id,
        )
        if cg is None:
            raise HTTPException(status_code=404, detail="corporate group not found")
        row = await conn.fetchrow(
            """INSERT INTO business_divisions
                  (corporate_group_id, workspace_id, name, name_vi,
                   description, industry_hint, sort_order)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            body.corporate_group_id, cg["workspace_id"], body.name, body.name_vi,
            body.description, body.industry_hint, body.sort_order,
        )
    return _row_to_division(row)


@router.put("/business-divisions/{division_id}", response_model=BusinessDivisionOut)
async def update_business_division(
    body: BusinessDivisionUpdate,
    division_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    sets, params = [], []
    for col, val in (
        ("name", body.name), ("name_vi", body.name_vi),
        ("description", body.description), ("industry_hint", body.industry_hint),
        ("sort_order", body.sort_order), ("status", body.status),
    ):
        if val is not None:
            params.append(val)
            sets.append(f"{col} = ${len(params)}")
    if not sets:
        async with acquire_for_tenant(x_enterprise_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM business_divisions WHERE division_id = $1",
                division_id,
            )
        if row is None:
            raise HTTPException(status_code=404, detail="division not found")
        return _row_to_division(row)
    sets.append("updated_at = NOW()")
    params.append(division_id)
    sql = (
        f"UPDATE business_divisions SET {', '.join(sets)} "
        f"WHERE division_id = ${len(params)} RETURNING *"
    )
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(sql, *params)
    if row is None:
        raise HTTPException(status_code=404, detail="division not found")
    return _row_to_division(row)


@router.delete("/business-divisions/{division_id}", status_code=204)
async def delete_business_division(
    division_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Prevent delete if there are non-archived enterprises under it.
        in_use = await conn.fetchval(
            """SELECT COUNT(*) FROM enterprises
               WHERE business_division_id = $1 AND status = 'active'""",
            division_id,
        )
        if in_use and in_use > 0:
            raise HTTPException(
                status_code=409,
                detail=f"division has {in_use} active enterprises; "
                       f"re-parent them via PUT /enterprises/{{id}}/parent first",
            )
        result = await conn.execute(
            "DELETE FROM business_divisions WHERE division_id = $1",
            division_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="division not found")


# ─── Enterprise org-detail (branches + departments) ─────────────────


@router.get("/enterprises/{enterprise_id}/org-detail")
async def get_enterprise_org_detail(
    enterprise_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Return the branches + departments under an enterprise.

    The FE org tree page calls this when the user expands an enterprise
    leaf to show its internal structure (chi nhánh + phòng ban). Sits at
    the bottom of v_corporate_tree (group → division → enterprise) — we
    drop down two more levels here.

    Authz: caller's enterprise must share workspace with the target
    enterprise. Otherwise 403.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Workspace match guard.
        caller = await conn.fetchrow(
            "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
            x_enterprise_id,
        )
        target = await conn.fetchrow(
            """SELECT enterprise_id, workspace_id, name,
                      corporate_group_id, business_division_id, parent_enterprise_id, industry, status
               FROM enterprises WHERE enterprise_id = $1""",
            enterprise_id,
        )
        if caller is None or target is None:
            raise HTTPException(status_code=404, detail="enterprise not found")
        if caller["workspace_id"] != target["workspace_id"]:
            raise HTTPException(status_code=403, detail="enterprise in different workspace")

        # P15-S11 live-test 2026-05-15: branches/departments are RLS-scoped
        # by app.current_enterprise_id. acquire_for_tenant set it to the
        # caller's enterprise; we need TARGET's. Since the workspace_id
        # match guard above already proves cross-tenant safety within this
        # workspace, switching the GUC is correct here.
        await conn.execute(
            "SELECT set_config('app.enterprise_id',         $1, true), "
            "       set_config('app.current_enterprise_id', $1, true)",
            str(enterprise_id),
        )

        branches = await conn.fetch(
            """SELECT branch_id, name, code, is_default, timezone, status
               FROM branches WHERE enterprise_id = $1
               ORDER BY is_default DESC, name""",
            enterprise_id,
        )
        depts = await conn.fetch(
            """SELECT department_id, branch_id, name, dept_type, status, pii_sensitivity, description
               FROM departments WHERE enterprise_id = $1
               ORDER BY dept_type, name""",
            enterprise_id,
        )

    branch_list = [
        {
            "branch_id":  str(b["branch_id"]),
            "name":       b["name"],
            "code":       b["code"],
            "is_default": b["is_default"],
            "timezone":   b["timezone"],
            "status":     b["status"],
        } for b in branches
    ]
    dept_list = [
        {
            "department_id":    str(d["department_id"]),
            "branch_id":        str(d["branch_id"]) if d["branch_id"] else None,
            "name":             d["name"],
            "dept_type":        d["dept_type"],
            "status":           d["status"],
            "pii_sensitivity":  d["pii_sensitivity"],
            "description":      d["description"],
        } for d in depts
    ]
    return {
        "enterprise": {
            "enterprise_id":         str(target["enterprise_id"]),
            "name":                  target["name"],
            "industry":              target["industry"],
            "status":                target["status"],
            "corporate_group_id":    str(target["corporate_group_id"]) if target["corporate_group_id"] else None,
            "business_division_id":  str(target["business_division_id"]) if target["business_division_id"] else None,
            "parent_enterprise_id":  str(target["parent_enterprise_id"]) if target["parent_enterprise_id"] else None,
        },
        "branches":    branch_list,
        "departments": dept_list,
    }


# ─── Enterprise re-parent (drag-drop) ────────────────────────────────


@router.put("/enterprises/{enterprise_id}/parent")
async def move_enterprise(
    body: EnterpriseParentUpdate,
    enterprise_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Re-parent an enterprise within the org tree.

    Exactly one of the three FK fields determines the new parent:
      - corporate_group_id   → enterprise sits directly under the group
                                (no division — for ungrouped subsidiaries)
      - business_division_id → enterprise sits under a division
      - parent_enterprise_id → enterprise is a sub-subsidiary of another
                                enterprise (e.g. VinFast Auto under VinFast)

    Validation:
      - target FK must point at a node in the same workspace
      - parent_enterprise_id must not create a cycle through this enterprise
    """
    supplied = sum(1 for v in [
        body.corporate_group_id, body.business_division_id, body.parent_enterprise_id
    ] if v is not None)
    if supplied != 1:
        raise HTTPException(
            status_code=400,
            detail="exactly one of corporate_group_id / business_division_id / "
                   "parent_enterprise_id must be supplied",
        )

    async with acquire_for_tenant(x_enterprise_id) as conn:
        ent = await conn.fetchrow(
            "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
            enterprise_id,
        )
        if ent is None:
            raise HTTPException(status_code=404, detail="enterprise not found")

        # Validate target FK + workspace match.
        if body.corporate_group_id is not None:
            target = await conn.fetchrow(
                "SELECT workspace_id FROM corporate_groups WHERE corporate_group_id = $1",
                body.corporate_group_id,
            )
        elif body.business_division_id is not None:
            target = await conn.fetchrow(
                "SELECT workspace_id FROM business_divisions WHERE division_id = $1",
                body.business_division_id,
            )
        else:
            target = await conn.fetchrow(
                "SELECT workspace_id, parent_enterprise_id FROM enterprises "
                "WHERE enterprise_id = $1",
                body.parent_enterprise_id,
            )
            # Cycle guard: walk parent chain; reject if we hit enterprise_id.
            current = target
            depth = 0
            while current and current["parent_enterprise_id"]:
                if current["parent_enterprise_id"] == enterprise_id:
                    raise HTTPException(status_code=400, detail="would create a cycle")
                depth += 1
                if depth > 16:
                    raise HTTPException(status_code=400, detail="parent chain too deep")
                current = await conn.fetchrow(
                    "SELECT workspace_id, parent_enterprise_id FROM enterprises "
                    "WHERE enterprise_id = $1",
                    current["parent_enterprise_id"],
                )

        if target is None:
            raise HTTPException(status_code=404, detail="target parent not found")
        if target["workspace_id"] != ent["workspace_id"]:
            raise HTTPException(
                status_code=400,
                detail="target parent is in a different workspace",
            )

        # Clear all three FKs then set the supplied one.
        await conn.execute(
            """UPDATE enterprises
               SET corporate_group_id   = $1,
                   business_division_id = $2,
                   parent_enterprise_id = $3,
                   updated_at           = NOW()
               WHERE enterprise_id = $4""",
            body.corporate_group_id, body.business_division_id, body.parent_enterprise_id,
            enterprise_id,
        )
    return {"status": "ok", "enterprise_id": str(enterprise_id)}
