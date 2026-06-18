"""ADR-0037 Phase 2 — functional-RBAC enforcement guard.

Bridges the pure matrix (doc_rbac) to a DB-backed check on user_department_roles.
Enforcement is OPT-IN per department: if a department has NO functional-role
config yet, the check falls through (existing coarse RBAC still applies), so
turning the feature on is incremental and never silently locks out a tenant that
hasn't configured roles. Once any role is granted in a department, the matrix is
enforced there.

  assert_permission(conn, user_id, department_id, action) → raises 403 or returns.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from . import doc_rbac as rb


async def resolve_functional_roles(conn, user_id: UUID, department_id: UUID) -> list[str]:
    """Functional roles a user holds in a department (empty if none)."""
    if user_id is None or department_id is None:
        return []
    rows = await conn.fetch(
        "SELECT functional_role FROM user_department_roles "
        "WHERE user_id = $1 AND department_id = $2",
        user_id, department_id)
    return [r["functional_role"] for r in rows]


async def _dept_has_role_config(conn, department_id: UUID) -> bool:
    return bool(await conn.fetchval(
        "SELECT 1 FROM user_department_roles WHERE department_id = $1 LIMIT 1",
        department_id))


async def assert_permission(
    conn, *, user_id: Optional[UUID], department_id: Optional[UUID], action: str,
) -> None:
    """Enforce the functional-RBAC matrix for an action in a department.

    - user has a role here → allow iff the matrix permits the action (else 403).
    - user has no role here, but the dept IS role-controlled → 403.
    - dept has no role config at all → allow (feature not activated for this dept).
    """
    if department_id is None:
        return  # no dept context → nothing to scope on
    roles = await resolve_functional_roles(conn, user_id, department_id)
    if roles:
        if not rb.can_any(roles, action):
            raise HTTPException(
                status_code=403,
                detail=f"vai trò của bạn không có quyền '{action}' với tài liệu/hợp đồng này")
        return
    # No role for this user here — enforce only if the dept is role-controlled.
    if await _dept_has_role_config(conn, department_id):
        raise HTTPException(
            status_code=403,
            detail="bạn chưa được phân vai trò trong phòng ban này")
    # else: department hasn't activated functional roles → fall through (allow).
