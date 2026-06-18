"""
Role-template lookup — P15-S11 Hướng A (RBAC tĩnh).

Endpoints
---------
  GET /api/v1/role-templates                    — list global defaults
                                                   (caller filters client-side
                                                   in the FE picker).
  GET /api/v1/departments/{dept_id}/role-template?seniority_level=<lvl>
                                                — resolve the suggested
                                                  default role for a given
                                                  dept + seniority. Honours
                                                  enterprise-specific
                                                  override when present;
                                                  falls back to global.

Anh chốt 2026-05-16: ship Hướng A trước (1.5-2 ngày), defer B (RBAC+ABAC
+PDP per SAD v2 Phần 6) sang Phase 2 P2-S13+. Out-of-scope at the table
level (per-permission granularity, cross-branch scoping, time-bound
roles, delegation) lives in Hướng B; this router stays narrow on
template lookup.

K-1 / K-19: dept lookup is RLS-scoped via `acquire_for_tenant`. Template
table itself is shared-reference (no RLS) until enterprise overrides
ship — for now, every enterprise reads the same 35 global rows.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Shapes ─────────────────────────────────────────────────────────


SENIORITY_LEVELS = ('entry', 'junior', 'mid', 'senior', 'executive')


class RoleTemplateOut(BaseModel):
    template_id:     UUID
    enterprise_id:   Optional[UUID]   # NULL = global default
    dept_type:       str
    seniority_level: str
    default_role:    str
    overridable:     bool
    description_vi:  Optional[str]
    is_active:       bool
    is_override:     bool = Field(
        default=False,
        description=(
            'TRUE when this row was an enterprise-specific override '
            '(enterprise_id matched). FALSE when the resolver fell back '
            'to a global default row.'
        ),
    )


class RoleTemplateResolveOut(BaseModel):
    """Response shape for the dept-scoped resolve endpoint. Bundles the
    chosen template plus the dept info the FE needs to render the
    \"đề xuất quyền: MANAGER\" hint next to the approve button."""
    department_id:   UUID
    dept_type:       str
    seniority_level: str
    template:        RoleTemplateOut


# ─── Endpoints ──────────────────────────────────────────────────────


@router.get("/role-templates", response_model=List[RoleTemplateOut])
async def list_role_templates(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    dept_type:       Optional[str] = Query(default=None, max_length=32),
    include_overrides: bool = Query(default=True),
):
    """List role templates visible to the caller.

    Default returns 35 global rows. When `include_overrides=true` and the
    caller's enterprise has overrides, those shadow the globals in the
    response (only the override row is returned per `(dept_type,
    seniority)` pair). Set `include_overrides=false` to always read the
    raw global defaults (admin use case).
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        if include_overrides:
            rows = await conn.fetch(
                """SELECT DISTINCT ON (dept_type, seniority_level)
                          template_id, enterprise_id, dept_type, seniority_level,
                          default_role, overridable, description_vi, is_active,
                          (enterprise_id IS NOT NULL) AS is_override
                   FROM department_role_templates
                   WHERE is_active = TRUE
                     AND (enterprise_id = $1 OR enterprise_id IS NULL)
                     AND ($2::text IS NULL OR dept_type = $2)
                   ORDER BY dept_type, seniority_level,
                            -- prefer enterprise-scoped over global
                            enterprise_id NULLS LAST""",
                x_enterprise_id, dept_type,
            )
        else:
            rows = await conn.fetch(
                """SELECT template_id, enterprise_id, dept_type, seniority_level,
                          default_role, overridable, description_vi, is_active,
                          FALSE AS is_override
                   FROM department_role_templates
                   WHERE is_active = TRUE
                     AND enterprise_id IS NULL
                     AND ($1::text IS NULL OR dept_type = $1)
                   ORDER BY dept_type, seniority_level""",
                dept_type,
            )
    return [RoleTemplateOut(**dict(r)) for r in rows]


@router.get(
    "/departments/{department_id}/role-template",
    response_model=RoleTemplateResolveOut,
)
async def resolve_role_template(
    department_id:   UUID = Path(..., description="Department UUID"),
    seniority_level: str  = Query(..., min_length=1, max_length=20),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Resolve `(dept_type, seniority_level) → default_role` for an
    onboarding approval flow. FE calls this when the approver opens the
    "duyệt nhân viên" drawer; the response drives the "Đề xuất quyền"
    hint + the writer payload when approve is clicked.

    Resolution order:
      1. Enterprise-specific override for (enterprise_id, dept_type,
         seniority).
      2. Global default for (dept_type, seniority).
      3. 404 — caller must pick a role manually.
    """
    if seniority_level not in SENIORITY_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"seniority_level must be one of {SENIORITY_LEVELS}; "
                f"got {seniority_level!r}"
            ),
        )

    async with acquire_for_tenant(x_enterprise_id) as conn:
        dept = await conn.fetchrow(
            "SELECT department_id, dept_type FROM departments WHERE department_id = $1",
            department_id,
        )
        if dept is None:
            raise HTTPException(status_code=404, detail="department not found")

        # Single query: order by enterprise_id NULLS LAST means the
        # override row (if any) sorts before the global row, so LIMIT 1
        # picks the right one.
        tpl = await conn.fetchrow(
            """SELECT template_id, enterprise_id, dept_type, seniority_level,
                      default_role, overridable, description_vi, is_active,
                      (enterprise_id IS NOT NULL) AS is_override
               FROM department_role_templates
               WHERE is_active = TRUE
                 AND dept_type = $1
                 AND seniority_level = $2
                 AND (enterprise_id = $3 OR enterprise_id IS NULL)
               ORDER BY enterprise_id NULLS LAST
               LIMIT 1""",
            dept["dept_type"], seniority_level, x_enterprise_id,
        )

    if tpl is None:
        # No global seed for this (dept_type, seniority) — should never
        # happen with the 35-row seed, but surface the gap loudly.
        log.warning(
            "role_template.missing",
            dept_type=dept["dept_type"],
            seniority_level=seniority_level,
        )
        raise HTTPException(
            status_code=404,
            detail=(
                f"No role template for dept_type={dept['dept_type']!r} "
                f"seniority_level={seniority_level!r}. Pick a role manually."
            ),
        )

    return RoleTemplateResolveOut(
        department_id=dept["department_id"],
        dept_type=dept["dept_type"],
        seniority_level=seniority_level,
        template=RoleTemplateOut(**dict(tpl)),
    )
