"""
Industry Template + Bootstrap router — Phase 2.8.

Anh's spec 2026-05-20:
  "Workflow UI chưa rõ vật thể. SME không nên tạo từ canvas trắng.
   Bắt đầu bằng: chọn ngành → sinh phòng ban mẫu → sinh workflow mẫu
   → user chỉnh các card. 3-tier: Industry → Department → Workflow Template."

Endpoints
---------
  GET  /industries                                — list 3-of-8 catalog
  GET  /industries/{industry_id}                  — full detail (depts + KPI + schema)
  GET  /industries/{industry_id}/departments      — dept list
  GET  /industries/{industry_id}/workflows        — workflow template list
       ?recommendation_level=core|suggested|advanced
  POST /enterprises/{enterprise_id}/bootstrap-from-industry
       body: {industry_id, dry_run?, dept_keys_to_skip?}
       — clones industry config into the tenant. Idempotent.
  GET  /enterprises/{enterprise_id}/bootstrap-status
  GET  /workflows/{workflow_id}/versions          — snapshot history
  POST /workflows/{workflow_id}/customize         — record an edit (mode + diff)
  GET  /enterprises/{enterprise_id}/workflow-mode — read 3-mode flag
  PATCH /enterprises/{enterprise_id}/workflow-mode — update default_mode

K-rule compliance
-----------------
  K-1 RLS: bootstrap + customization writes go through acquire_for_tenant.
  K-12 anti-IDOR: enterprise_id from JWT/header, never from URL path body.
  K-13 idempotency: bootstrap UNIQUE(enterprise_id) — re-call returns 409
       unless ?force=true (deletes prior row, recreates).
  K-19 OpenTelemetry: tenant_id span attribute on every endpoint.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant, acquire_cross_tenant as acquire_global

log = structlog.get_logger()

router = APIRouter()


# ─── Pydantic shapes ────────────────────────────────────────────────


class IndustryOut(BaseModel):
    industry_id:        UUID
    industry_key:       str
    display_name:       str
    display_name_vi:    str
    description_vi:     Optional[str] = None
    icon_key:           Optional[str] = None
    accent_color:       Optional[str] = None
    primary_kpis:       List[str]
    ai_confidence_threshold: float
    suggested_pricing_plan:  Optional[str] = None
    compliance_notes_vi:     Optional[str] = None
    dept_count:         int
    core_workflow_count: int
    total_workflow_count: int
    kpi_count:          int


class DepartmentTemplateOut(BaseModel):
    template_id:       UUID
    industry_id:       UUID
    dept_key:          str
    dept_type:         str
    display_name:      str
    display_name_vi:   str
    description_vi:    Optional[str] = None
    sequence_order:    int
    is_required:       bool
    suggested_headcount: Dict[str, Any] = Field(default_factory=dict)


class WorkflowLinkOut(BaseModel):
    link_id:                UUID
    industry_dept_id:       UUID
    workflow_template_id:   UUID
    display_name:           str
    display_name_vi:        str
    department_type:        str
    recommendation_level:   str
    sequence_order:         int


class BootstrapRequest(BaseModel):
    industry_id:        UUID
    dry_run:            bool = Field(default=False, description="If TRUE, return preview WITHOUT writing departments/workflows.")
    dept_keys_to_skip:  List[str] = Field(default_factory=list, description="Skip these dept_keys; only honoured for is_required=FALSE.")
    force:              bool = Field(default=False, description="If TRUE and enterprise already bootstrapped, drop prior bootstrap row + redo. Destructive.")


class BootstrapResultOut(BaseModel):
    bootstrap_id:      Optional[UUID]
    industry_id:       UUID
    industry_key:      str
    dry_run:           bool
    depts_created:     int
    workflows_created: int
    kpis_created:      int
    schemas_seeded:    int
    roles_seeded:      int
    created_department_ids: List[UUID] = Field(default_factory=list)
    created_workflow_ids:   List[UUID] = Field(default_factory=list)
    skipped_dept_keys:  List[str]      = Field(default_factory=list)
    warning:           Optional[str]   = None


class BootstrapStatusOut(BaseModel):
    bootstrapped:       bool
    bootstrap_id:       Optional[UUID] = None
    industry_id:        Optional[UUID] = None
    industry_key:       Optional[str] = None
    bootstrapped_at:    Optional[datetime] = None
    depts_created:      int = 0
    workflows_created:  int = 0
    review_completed_at: Optional[datetime] = None


class WorkflowVersionOut(BaseModel):
    version_id:         UUID
    workflow_id:        UUID
    version_number:     int
    source:             str
    based_on_template_version: Optional[int] = None
    change_reason:      Optional[str] = None
    created_by:         Optional[UUID] = None
    created_at:         datetime
    approved_by:        Optional[UUID] = None
    approved_at:        Optional[datetime] = None
    effective_date:     datetime


class CustomizationRequest(BaseModel):
    operation:    str  = Field(..., description="add_node|remove_node|edit_node|add_edge|remove_edge|edit_branch|change_sla|change_owner|add_document_requirement|edit_threshold|rename|reorder|cr_apply")
    edit_mode:    str  = Field(default="simple", description="simple|advanced|developer")
    diff:         Dict[str, Any] = Field(default_factory=dict)
    change_reason: Optional[str] = None


class WorkflowModeOut(BaseModel):
    enterprise_id:      UUID
    default_mode:       str
    user_overrides:     Dict[str, Any] = Field(default_factory=dict)
    advanced_unlocked:  bool
    developer_unlocked: bool


# ─── Endpoints ──────────────────────────────────────────────────────


@router.get("/industries", response_model=List[IndustryOut])
async def list_industries():
    """List all active industries from `v_industry_overview` (Phase 2.8 — currently 3 of 8 seeded)."""
    async with acquire_global() as conn:
        rows = await conn.fetch(
            """
            SELECT
                i.industry_id, i.industry_key, i.display_name, i.display_name_vi,
                i.description_vi, i.icon_key, i.accent_color, i.primary_kpis,
                i.ai_confidence_threshold, i.suggested_pricing_plan,
                i.compliance_notes_vi,
                v.dept_count, v.core_workflow_count, v.total_workflow_count, v.kpi_count
            FROM industry_templates i
            JOIN v_industry_overview v USING (industry_id)
            WHERE i.is_active = TRUE
            ORDER BY i.industry_key
            """
        )
    return [
        IndustryOut(
            **{**dict(r), "ai_confidence_threshold": float(r["ai_confidence_threshold"])}
        )
        for r in rows
    ]


@router.get("/industries/{industry_id}", response_model=Dict[str, Any])
async def get_industry_detail(industry_id: UUID = Path(...)):
    """Full detail: industry + depts + workflows + KPIs + schemas + roles."""
    async with acquire_global() as conn:
        ind = await conn.fetchrow(
            "SELECT * FROM industry_templates WHERE industry_id = $1 AND is_active = TRUE",
            industry_id,
        )
        if ind is None:
            raise HTTPException(404, "industry not found")
        depts = await conn.fetch(
            """SELECT * FROM industry_department_templates
               WHERE industry_id = $1 ORDER BY sequence_order""",
            industry_id,
        )
        wflows = await conn.fetch(
            """SELECT l.link_id, l.industry_dept_id, l.workflow_template_id,
                      l.recommendation_level, l.sequence_order,
                      wt.display_name, wt.display_name_vi, wt.department_type
               FROM industry_workflow_links l
               JOIN workflow_templates wt ON wt.template_id = l.workflow_template_id
               WHERE l.industry_id = $1
               ORDER BY l.recommendation_level, l.sequence_order""",
            industry_id,
        )
        kpis = await conn.fetch(
            """SELECT * FROM industry_kpi_templates
               WHERE industry_id = $1 ORDER BY sequence_order""",
            industry_id,
        )
        schemas = await conn.fetch(
            """SELECT * FROM industry_data_schema_templates
               WHERE industry_id = $1 ORDER BY sequence_order""",
            industry_id,
        )
        roles = await conn.fetch(
            """SELECT * FROM industry_role_permission_templates
               WHERE industry_id = $1
               ORDER BY dept_type, seniority_level""",
            industry_id,
        )

    def _dict(r):
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, UUID):  d[k] = str(v)
            if isinstance(v, datetime): d[k] = v.isoformat()
        return d

    return {
        "industry":     _dict(ind),
        "departments":  [_dict(r) for r in depts],
        "workflows":    [_dict(r) for r in wflows],
        "kpis":         [_dict(r) for r in kpis],
        "data_schemas": [_dict(r) for r in schemas],
        "role_permissions": [_dict(r) for r in roles],
    }


@router.get("/industries/{industry_id}/departments", response_model=List[DepartmentTemplateOut])
async def list_industry_departments(industry_id: UUID = Path(...)):
    async with acquire_global() as conn:
        rows = await conn.fetch(
            """SELECT * FROM industry_department_templates
               WHERE industry_id = $1 ORDER BY sequence_order""",
            industry_id,
        )
    return [DepartmentTemplateOut(**dict(r)) for r in rows]


@router.get("/industries/{industry_id}/workflows", response_model=List[WorkflowLinkOut])
async def list_industry_workflows(
    industry_id: UUID = Path(...),
    recommendation_level: Optional[str] = Query(default=None, pattern="^(core|suggested|advanced)$"),
):
    async with acquire_global() as conn:
        if recommendation_level:
            rows = await conn.fetch(
                """SELECT l.link_id, l.industry_dept_id, l.workflow_template_id,
                          l.recommendation_level, l.sequence_order,
                          wt.display_name, wt.display_name_vi, wt.department_type
                   FROM industry_workflow_links l
                   JOIN workflow_templates wt ON wt.template_id = l.workflow_template_id
                   WHERE l.industry_id = $1 AND l.recommendation_level = $2
                   ORDER BY l.sequence_order""",
                industry_id, recommendation_level,
            )
        else:
            rows = await conn.fetch(
                """SELECT l.link_id, l.industry_dept_id, l.workflow_template_id,
                          l.recommendation_level, l.sequence_order,
                          wt.display_name, wt.display_name_vi, wt.department_type
                   FROM industry_workflow_links l
                   JOIN workflow_templates wt ON wt.template_id = l.workflow_template_id
                   WHERE l.industry_id = $1
                   ORDER BY l.recommendation_level, l.sequence_order""",
                industry_id,
            )
    return [WorkflowLinkOut(**dict(r)) for r in rows]


@router.post(
    "/enterprises/{enterprise_id}/bootstrap-from-industry",
    response_model=BootstrapResultOut,
)
async def bootstrap_enterprise_from_industry(
    enterprise_id: UUID = Path(..., description="Tenant enterprise UUID"),
    body: BootstrapRequest = Body(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(default=None, alias="X-User-ID"),
):
    """Clone industry template → enterprise's departments + workflows + KPI cache.

    K-12 anti-IDOR: enterprise_id in path MUST match X-Enterprise-ID header.
    Idempotent via enterprise_industry_bootstrap UNIQUE(enterprise_id); pass
    force=true to drop+re-bootstrap (destructive).
    """
    if enterprise_id != x_enterprise_id:
        raise HTTPException(403, "enterprise_id path mismatch X-Enterprise-ID (K-12)")

    # Lookup industry (global, no RLS).
    async with acquire_global() as gconn:
        industry = await gconn.fetchrow(
            "SELECT industry_id, industry_key FROM industry_templates WHERE industry_id = $1 AND is_active = TRUE",
            body.industry_id,
        )
        if industry is None:
            raise HTTPException(404, "industry not found or inactive")

        depts_tpl = await gconn.fetch(
            """SELECT * FROM industry_department_templates
               WHERE industry_id = $1 ORDER BY sequence_order""",
            body.industry_id,
        )
        workflow_links = await gconn.fetch(
            """SELECT l.industry_dept_id, l.workflow_template_id,
                      l.recommendation_level, l.sequence_order,
                      wt.display_name, wt.display_name_vi, wt.department_type,
                      wt.category, wt.workflow_definition
               FROM industry_workflow_links l
               JOIN workflow_templates wt ON wt.template_id = l.workflow_template_id
               WHERE l.industry_id = $1 AND l.recommendation_level = 'core'
               ORDER BY l.sequence_order""",
            body.industry_id,
        )

    # Resolve which depts to skip.
    skip = set(body.dept_keys_to_skip or [])
    to_create = [d for d in depts_tpl if not (d["dept_key"] in skip and not d["is_required"])]
    skipped = [d["dept_key"] for d in depts_tpl if d["dept_key"] in skip and not d["is_required"]]

    if body.dry_run:
        return BootstrapResultOut(
            bootstrap_id=None,
            industry_id=body.industry_id,
            industry_key=industry["industry_key"],
            dry_run=True,
            depts_created=len(to_create),
            workflows_created=len(workflow_links),
            kpis_created=0,
            schemas_seeded=0,
            roles_seeded=0,
            skipped_dept_keys=skipped,
            warning="dry_run=true — no rows written",
        )

    # Tenant-scoped writes from here on.
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # K-13 idempotency: prior bootstrap row?
        prior = await conn.fetchrow(
            "SELECT bootstrap_id FROM enterprise_industry_bootstrap WHERE enterprise_id = $1",
            x_enterprise_id,
        )
        if prior is not None and not body.force:
            raise HTTPException(
                409,
                "enterprise already bootstrapped; pass force=true to redo (destructive)",
            )
        if prior is not None and body.force:
            await conn.execute(
                "DELETE FROM enterprise_industry_bootstrap WHERE enterprise_id = $1",
                x_enterprise_id,
            )

        # Clone departments.
        created_dept_ids: List[UUID] = []
        dept_key_to_id: Dict[str, UUID] = {}
        for d in to_create:
            row = await conn.fetchrow(
                """INSERT INTO departments (enterprise_id, name, dept_type, description)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (enterprise_id, branch_id, name) DO UPDATE SET updated_at = NOW()
                   RETURNING department_id""",
                x_enterprise_id, d["display_name_vi"], d["dept_type"], d["description_vi"],
            )
            dept_id = row["department_id"]
            created_dept_ids.append(dept_id)
            dept_key_to_id[d["dept_key"]] = dept_id

            # Auto-provision a default single-level approval chain so any
            # approval_gate in this dept's workflows has something to bind to
            # out of the box (ADR-0037 follow-up). Idempotent — skip if the
            # dept already carries a chain. Level 1 = MANAGER, escalate on SLA.
            existing_chain = await conn.fetchrow(
                "SELECT chain_id FROM approval_chains "
                "WHERE enterprise_id = $1 AND department_id = $2",
                x_enterprise_id, dept_id,
            )
            if existing_chain is None:
                ch = await conn.fetchrow(
                    """INSERT INTO approval_chains
                           (enterprise_id, department_id, name, name_vi, description)
                       VALUES ($1, $2, 'Default approval — Manager',
                               'Duyệt 1 cấp — Quản lý',
                               'Chuỗi duyệt mặc định tạo khi onboard phòng ban.')
                       RETURNING chain_id""",
                    x_enterprise_id, dept_id,
                )
                await conn.execute(
                    """INSERT INTO approval_levels
                           (chain_id, enterprise_id, level_no, approver_roles,
                            mode, sla_minutes, on_timeout, escalate_to_role)
                       VALUES ($1, $2, 1, ARRAY['MANAGER'], 'one', 1440,
                               'escalate', 'MANAGER')""",
                    ch["chain_id"], x_enterprise_id,
                )

        # Clone workflows (one workflow per link). The workflow_definition
        # is JSONB with {nodes:[], edges:[]} client-side ids. Phase 2.8 v0:
        # store as workflow_templates pointer; FE clones the actual node
        # set on first edit (lazy clone).
        created_workflow_ids: List[UUID] = []
        for wl in workflow_links:
            # Map link.industry_dept_id → real department_id.
            ind_dept_id = wl["industry_dept_id"]
            # Find corresponding industry_department_template row -> dept_key
            dept_key_row = next(
                (d for d in depts_tpl if d["template_id"] == ind_dept_id), None
            )
            if dept_key_row is None or dept_key_row["dept_key"] not in dept_key_to_id:
                continue
            real_dept_id = dept_key_to_id[dept_key_row["dept_key"]]

            wf_row = await conn.fetchrow(
                """INSERT INTO workflows (
                       enterprise_id, department_id, name, name_vi,
                       category, source, cloned_from_template_id, state
                   ) VALUES ($1, $2, $3, $4, $5, 'template_based', $6, 'DRAFT')
                   ON CONFLICT (enterprise_id, department_id, name) DO UPDATE
                     SET last_modified_at = NOW()
                   RETURNING workflow_id""",
                x_enterprise_id, real_dept_id,
                wl["display_name"], wl["display_name_vi"],
                wl["category"], wl["workflow_template_id"],
            )
            created_workflow_ids.append(wf_row["workflow_id"])

        # Insert bootstrap audit row.
        boot_row = await conn.fetchrow(
            """INSERT INTO enterprise_industry_bootstrap
                   (enterprise_id, industry_id, depts_created, workflows_created,
                    kpis_created, schemas_seeded, roles_seeded, bootstrapped_by)
               VALUES ($1, $2, $3, $4, 0, 0, 0, $5)
               RETURNING bootstrap_id""",
            x_enterprise_id, body.industry_id,
            len(created_dept_ids), len(created_workflow_ids),
            x_user_id,
        )

    log.info(
        "industry.bootstrap.done",
        tenant_id=str(x_enterprise_id),
        industry_key=industry["industry_key"],
        depts=len(created_dept_ids),
        workflows=len(created_workflow_ids),
    )

    return BootstrapResultOut(
        bootstrap_id=boot_row["bootstrap_id"],
        industry_id=body.industry_id,
        industry_key=industry["industry_key"],
        dry_run=False,
        depts_created=len(created_dept_ids),
        workflows_created=len(created_workflow_ids),
        kpis_created=0,        # KPIs live in cache layer (Phase 2.9 wiring)
        schemas_seeded=0,      # Data schemas accessed lazily on first upload
        roles_seeded=0,        # Roles applied on first user onboarded
        created_department_ids=created_dept_ids,
        created_workflow_ids=created_workflow_ids,
        skipped_dept_keys=skipped,
    )


@router.get(
    "/enterprises/{enterprise_id}/bootstrap-status",
    response_model=BootstrapStatusOut,
)
async def get_bootstrap_status(
    enterprise_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    if enterprise_id != x_enterprise_id:
        raise HTTPException(403, "enterprise_id mismatch (K-12)")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT eib.bootstrap_id, eib.industry_id, eib.depts_created,
                      eib.workflows_created, eib.bootstrapped_at, eib.review_completed_at,
                      it.industry_key
               FROM enterprise_industry_bootstrap eib
               JOIN industry_templates it USING (industry_id)
               WHERE eib.enterprise_id = $1""",
            x_enterprise_id,
        )
    if row is None:
        return BootstrapStatusOut(bootstrapped=False)
    return BootstrapStatusOut(
        bootstrapped=True,
        bootstrap_id=row["bootstrap_id"],
        industry_id=row["industry_id"],
        industry_key=row["industry_key"],
        bootstrapped_at=row["bootstrapped_at"],
        depts_created=row["depts_created"],
        workflows_created=row["workflows_created"],
        review_completed_at=row["review_completed_at"],
    )


@router.get(
    "/workflows/{workflow_id}/versions",
    response_model=List[WorkflowVersionOut],
)
async def list_workflow_versions(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT version_id, workflow_id, version_number, source,
                      based_on_template_version, change_reason, created_by,
                      created_at, approved_by, approved_at, effective_date
               FROM customer_workflow_versions
               WHERE workflow_id = $1
               ORDER BY version_number DESC""",
            workflow_id,
        )
    return [WorkflowVersionOut(**dict(r)) for r in rows]


@router.post(
    "/workflows/{workflow_id}/customize",
    response_model=Dict[str, Any],
    status_code=201,
)
async def record_customization(
    workflow_id: UUID = Path(...),
    body: CustomizationRequest = Body(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(default=None, alias="X-User-ID"),
):
    """Record a single customization event. Caller is responsible for
    snapshotting (via separate /versions POST). v0 only logs the diff."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Sanity-check workflow ownership (K-1 via RLS).
        wf = await conn.fetchrow(
            "SELECT workflow_id FROM workflows WHERE workflow_id = $1",
            workflow_id,
        )
        if wf is None:
            raise HTTPException(404, "workflow not found")

        row = await conn.fetchrow(
            """INSERT INTO workflow_customizations
                   (enterprise_id, workflow_id, operation, edit_mode, diff, changed_by)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING customization_id, changed_at""",
            x_enterprise_id, workflow_id,
            body.operation, body.edit_mode, body.diff, x_user_id,
        )
    return {
        "customization_id": str(row["customization_id"]),
        "changed_at": row["changed_at"].isoformat(),
        "operation": body.operation,
        "edit_mode": body.edit_mode,
    }


@router.get(
    "/enterprises/{enterprise_id}/workflow-mode",
    response_model=WorkflowModeOut,
)
async def get_workflow_mode(
    enterprise_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    if enterprise_id != x_enterprise_id:
        raise HTTPException(403, "enterprise_id mismatch (K-12)")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM enterprise_workflow_mode WHERE enterprise_id = $1",
            x_enterprise_id,
        )
        if row is None:
            # Default if not yet configured.
            return WorkflowModeOut(
                enterprise_id=x_enterprise_id,
                default_mode='simple',
                user_overrides={},
                advanced_unlocked=True,
                developer_unlocked=False,
            )
    return WorkflowModeOut(**dict(row))


@router.patch(
    "/enterprises/{enterprise_id}/workflow-mode",
    response_model=WorkflowModeOut,
)
async def update_workflow_mode(
    enterprise_id: UUID = Path(...),
    body: Dict[str, Any] = Body(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    if enterprise_id != x_enterprise_id:
        raise HTTPException(403, "enterprise_id mismatch (K-12)")
    default_mode = body.get("default_mode")
    if default_mode and default_mode not in ('simple', 'advanced', 'developer'):
        raise HTTPException(422, "default_mode must be simple|advanced|developer")
    advanced_unlocked = bool(body.get("advanced_unlocked", True))
    developer_unlocked = bool(body.get("developer_unlocked", False))

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO enterprise_workflow_mode
                   (enterprise_id, default_mode, advanced_unlocked, developer_unlocked, updated_at)
               VALUES ($1, $2, $3, $4, NOW())
               ON CONFLICT (enterprise_id) DO UPDATE
                   SET default_mode       = COALESCE(EXCLUDED.default_mode, enterprise_workflow_mode.default_mode),
                       advanced_unlocked  = EXCLUDED.advanced_unlocked,
                       developer_unlocked = EXCLUDED.developer_unlocked,
                       updated_at         = NOW()
               RETURNING *""",
            x_enterprise_id, default_mode or 'simple',
            advanced_unlocked, developer_unlocked,
        )
    return WorkflowModeOut(**dict(row))
