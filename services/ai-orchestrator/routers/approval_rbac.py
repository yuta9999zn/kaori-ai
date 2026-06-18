"""ADR-0037 Phase 2 — approval-chain config + delegation + functional RBAC.

  Chains (builder-time):
    POST /approval-chains                      — create chain
    GET  /approval-chains                      — list (dept-scoped)
    POST /approval-chains/{chain_id}/levels    — add a level
    GET  /approval-chains/{chain_id}           — chain + ordered levels

  Functional roles (who plays what in a department):
    POST   /user-department-roles
    GET    /user-department-roles?department_id=
    DELETE /user-department-roles/{id}

  Delegation (OOO cover):
    POST   /approval-delegations
    GET    /approval-delegations
    DELETE /approval-delegations/{id}          — revoke

The RBAC matrix is code-side (shared/doc_rbac.py); `resolve_functional_roles`
reads user_department_roles for permission checks. K-1 RLS via acquire_for_tenant.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant
from ..shared import doc_rbac as rb
from ..workflow_runtime import approval_chain as ac

router = APIRouter()


# ─────────────────── approver inbox (cross-run) ───────────────────
@router.get("/approval-inbox")
async def approval_inbox(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
):
    """Pending approvals awaiting THIS caller across every run — the approver
    inbox. Filters to rows where the caller's role is in approver_roles (or they
    are the pinned approver). No role header → all pending (manager/admin view).
    Carries run/workflow context + SLA remaining + chain level."""
    from datetime import datetime, timezone
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT a.approval_id, a.run_id, a.node_id, a.approver_roles,
                      a.sla_minutes, a.reason_prompt, a.created_at,
                      a.chain_id, a.level_no, a.approver_user_id,
                      r.workflow_id, COALESCE(w.name_vi, w.name) AS workflow_name,
                      n.title_vi, n.title
               FROM workflow_approvals a
               JOIN workflow_runs r   ON r.run_id = a.run_id           -- tenant-filter-lint: allow
               JOIN workflows w       ON w.workflow_id = r.workflow_id -- tenant-filter-lint: allow
               LEFT JOIN workflow_nodes n ON n.node_id = a.node_id     -- tenant-filter-lint: allow
               WHERE a.status = 'pending'
                 AND ($1::text IS NULL
                      OR $1 = ANY(a.approver_roles)
                      OR a.approver_user_id = $2)
               ORDER BY a.created_at ASC""",
            x_user_role, x_user_id)
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        created = r["created_at"]
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed_min = int((now - created).total_seconds() / 60) if created else 0
        remaining = (r["sla_minutes"] or 0) - elapsed_min
        out.append({
            "approval_id": str(r["approval_id"]), "run_id": str(r["run_id"]),
            "workflow_name": r["workflow_name"],
            "step_title": r["title_vi"] or r["title"],
            "approver_roles": list(r["approver_roles"] or []),
            "reason_prompt": r["reason_prompt"],
            "level_no": r["level_no"], "is_chained": r["chain_id"] is not None,
            "sla_minutes": r["sla_minutes"],
            "sla_remaining_min": remaining,
            "overdue": remaining < 0,
            "requested_at": created.isoformat() if created else None,
        })
    return {"pending": out}


# ─────────────────────────── models ───────────────────────────
class ChainIn(BaseModel):
    department_id: UUID
    name: str
    name_vi: Optional[str] = None
    description: Optional[str] = None


class LevelIn(BaseModel):
    level_no: int = Field(..., ge=1)
    approver_roles: list[str]
    mode: str = "one"
    required_count: Optional[int] = None
    sla_minutes: int = 1440
    on_timeout: str = "escalate"
    escalate_to_role: Optional[str] = None


class DeptRoleIn(BaseModel):
    user_id: UUID
    department_id: UUID
    functional_role: str


class DelegationIn(BaseModel):
    to_user_id: UUID
    reason: Optional[str] = None
    expires_at: Optional[str] = None


# ─────────────────────── chain CRUD ───────────────────────
@router.post("/approval-chains", status_code=201)
async def create_chain(body: ChainIn, x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO approval_chains (enterprise_id, department_id, name, name_vi, description)
               VALUES ($1,$2,$3,$4,$5) RETURNING chain_id""",
            x_enterprise_id, body.department_id, body.name, body.name_vi, body.description)
    return {"chain_id": str(row["chain_id"])}


@router.get("/approval-chains")
async def list_chains(x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT chain_id, department_id, name, name_vi, description FROM approval_chains ORDER BY name")
    return {"chains": [{**dict(r), "chain_id": str(r["chain_id"]),
                        "department_id": str(r["department_id"])} for r in rows]}


@router.post("/approval-chains/{chain_id}/levels", status_code=201)
async def add_level(body: LevelIn, chain_id: UUID = Path(...),
                    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    if body.mode not in ac.MODES:
        raise HTTPException(400, f"mode must be one of {ac.MODES}")
    if not body.approver_roles:
        raise HTTPException(400, "approver_roles required")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        owns = await conn.fetchrow("SELECT 1 FROM approval_chains WHERE chain_id=$1", chain_id)
        if owns is None:
            raise HTTPException(404, "chain not found")
        try:
            row = await conn.fetchrow(
                """INSERT INTO approval_levels
                       (chain_id, enterprise_id, level_no, approver_roles, mode,
                        required_count, sla_minutes, on_timeout, escalate_to_role)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING level_id""",
                chain_id, x_enterprise_id, body.level_no, body.approver_roles, body.mode,
                body.required_count, body.sla_minutes, body.on_timeout, body.escalate_to_role)
        except Exception as exc:  # noqa: BLE001
            if "uq_approval_level" in str(exc):
                raise HTTPException(409, f"level {body.level_no} already exists on this chain")
            raise
    return {"level_id": str(row["level_id"])}


@router.get("/approval-chains/{chain_id}")
async def get_chain(chain_id: UUID = Path(...), x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        chain = await conn.fetchrow(
            "SELECT chain_id, department_id, name, name_vi, description FROM approval_chains WHERE chain_id=$1",
            chain_id)
        if chain is None:
            raise HTTPException(404, "chain not found")
        levels = await conn.fetch(
            """SELECT level_id, level_no, approver_roles, mode, required_count,
                      sla_minutes, on_timeout, escalate_to_role
               FROM approval_levels WHERE chain_id=$1 ORDER BY level_no""", chain_id)
    return {
        "chain_id": str(chain["chain_id"]), "department_id": str(chain["department_id"]),
        "name": chain["name"], "name_vi": chain["name_vi"], "description": chain["description"],
        "levels": [{**dict(l), "level_id": str(l["level_id"])} for l in levels],
    }


# ─────────────────── functional roles ───────────────────
async def resolve_functional_roles(conn, user_id: UUID, department_id: UUID) -> list[str]:
    """The functional roles a user holds in a department (for RBAC checks)."""
    rows = await conn.fetch(
        "SELECT functional_role FROM user_department_roles WHERE user_id=$1 AND department_id=$2",
        user_id, department_id)
    return [r["functional_role"] for r in rows]


@router.post("/user-department-roles", status_code=201)
async def grant_dept_role(body: DeptRoleIn, x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    if body.functional_role not in rb._RANK:
        raise HTTPException(400, f"functional_role must be one of {sorted(rb._RANK)}")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        try:
            row = await conn.fetchrow(
                """INSERT INTO user_department_roles (enterprise_id, user_id, department_id, functional_role)
                   VALUES ($1,$2,$3,$4) RETURNING id""",
                x_enterprise_id, body.user_id, body.department_id, body.functional_role)
        except Exception as exc:  # noqa: BLE001
            if "uq_udr" in str(exc):
                raise HTTPException(409, "user already has this role in this department")
            raise
    return {"id": str(row["id"])}


@router.get("/user-department-roles")
async def list_dept_roles(department_id: UUID = Query(...),
                          x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT id, user_id, functional_role FROM user_department_roles WHERE department_id=$1",
            department_id)
    return {"roles": [{"id": str(r["id"]), "user_id": str(r["user_id"]),
                       "functional_role": r["functional_role"]} for r in rows]}


@router.delete("/user-department-roles/{role_id}", status_code=204)
async def revoke_dept_role(role_id: UUID = Path(...), x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute("DELETE FROM user_department_roles WHERE id=$1", role_id)
    return None


# ─────────────────── delegations ───────────────────
@router.post("/approval-delegations", status_code=201)
async def create_delegation(body: DelegationIn,
                            x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
                            x_user_id: UUID = Header(..., alias="X-User-ID")):
    if body.to_user_id == x_user_id:
        raise HTTPException(400, "không thể uỷ quyền cho chính mình")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO approval_delegations (enterprise_id, from_user_id, to_user_id, reason, expires_at)
               VALUES ($1,$2,$3,$4,$5) RETURNING delegation_id""",
            x_enterprise_id, x_user_id, body.to_user_id, body.reason, body.expires_at)
    return {"delegation_id": str(row["delegation_id"])}


@router.get("/approval-delegations")
async def list_delegations(x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT delegation_id, from_user_id, to_user_id, reason, is_active, expires_at
               FROM approval_delegations WHERE is_active ORDER BY created_at DESC""")
    return {"delegations": [{**dict(r), "delegation_id": str(r["delegation_id"]),
                             "from_user_id": str(r["from_user_id"]),
                             "to_user_id": str(r["to_user_id"]),
                             "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None}
                            for r in rows]}


@router.delete("/approval-delegations/{delegation_id}", status_code=204)
async def revoke_delegation(delegation_id: UUID = Path(...),
                            x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            "UPDATE approval_delegations SET is_active=FALSE WHERE delegation_id=$1", delegation_id)
    return None
