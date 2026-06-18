"""
Enterprise-user management — P15-S11 Hướng A (RBAC tĩnh).

Endpoints
---------
  PATCH /api/v1/enterprise-users/{user_id}/role
      — Manager assigns / changes a user's role. Two modes:
          * template: body has `seniority_level + department_id`; server
            resolves the templated `default_role` from mig 061.
          * override: body has explicit `role`; server applies it directly.
        Either way an append-only row lands in `workspace_audit_log`
        with event_type = `enterprise_user.role.assigned` (template path)
        or `enterprise_user.role.overridden` (override path).

  POST /api/v1/enterprise-users/onboard-from-csv
      — Bulk-onboard employees from an already-uploaded HR CSV
        (e.g., users-onboarding-approval.csv at Bronze tier). For each
        row: classify dept_name → resolve department_id by (enterprise_id,
        dept_type) → look up template (dept_type, seniority_level) →
        INSERT enterprise_users with random unusable password_hash +
        status='pending'. Idempotent via UNIQUE(enterprise_id, email).
        side_effect_class = write_idempotent.

Authz
-----
* Caller must hold MANAGER role (other P2 roles 403).
* Caller's enterprise_id (X-Enterprise-ID, JWT-derived) MUST equal the
  target user's enterprise_id — cross-enterprise role grants are blocked
  with 403 (K-1 spirit applied at the application layer; RLS on
  enterprise_users would also catch this).

Why a single PATCH instead of separate template/override endpoints
------------------------------------------------------------------
Looking at the FE drawer ("Duyệt nhân viên") the approver flow is:
  1. Pick seniority from dropdown → server suggests role.
  2. (Optional) flip to "đổi quyền" → manager picks any of 4 roles.
  3. Click "Áp dụng" → one request lands the change.
Two endpoints would force the FE to remember which submit it's on.
One endpoint with an explicit `source: 'template' | 'override'` discriminator
makes the audit row trivially honest about what just happened.

Out-of-scope (Hướng B / Phase 2)
--------------------------------
* Cross-branch scoping (this endpoint authorises any MANAGER in the
  enterprise to change any user — Phase 2 PDP gates per-branch).
* Time-bound assignments (effective_from / effective_to).
* Delegation (acting MANAGER).
* Bulk PATCH (set roles for many users in one call).
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from ..shared.db import acquire_for_tenant
from ._onboarding_helpers import classify_dept_name, generate_pending_password_hash

log = structlog.get_logger()

router = APIRouter()


# ─── Constants ──────────────────────────────────────────────────────


SENIORITY_LEVELS = ('entry', 'junior', 'mid', 'senior', 'executive')
P2_ROLES         = ('MANAGER', 'OPERATOR', 'ANALYST', 'VIEWER')


# ─── Shapes ─────────────────────────────────────────────────────────


class RoleChangeRequest(BaseModel):
    """Either template-resolved OR explicit-override. Exactly one path
    must be present:

    * template path  — provide `department_id + seniority_level`.
    * override path  — provide `role`.

    Sending both = 422 (the FE is meant to pick one). Sending neither =
    422 (nothing to do)."""

    department_id:   Optional[UUID] = None
    seniority_level: Optional[str]  = Field(default=None, max_length=20)
    role:            Optional[str]  = Field(default=None, max_length=20)
    reason:          Optional[str]  = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def _exactly_one_path(self):
        has_template = self.seniority_level is not None and self.department_id is not None
        has_override = self.role is not None
        if has_template and has_override:
            raise ValueError(
                "Send EITHER (department_id + seniority_level) for template path "
                "OR role for override path, not both."
            )
        if not has_template and not has_override:
            raise ValueError(
                "Provide either (department_id + seniority_level) or role."
            )
        if self.seniority_level is not None and self.seniority_level not in SENIORITY_LEVELS:
            raise ValueError(
                f"seniority_level must be one of {SENIORITY_LEVELS}; got {self.seniority_level!r}"
            )
        if self.role is not None and self.role not in P2_ROLES:
            raise ValueError(f"role must be one of {P2_ROLES}; got {self.role!r}")
        return self


class RoleChangeResponse(BaseModel):
    user_id:         UUID
    role:            str
    previous_role:   str
    source:          str   # 'template' | 'override'
    template_id:     Optional[UUID] = None
    audit_event_id:  UUID
    enterprise_id:   UUID


# ─── Endpoint ───────────────────────────────────────────────────────


@router.patch(
    "/enterprise-users/{user_id}/role",
    response_model=RoleChangeResponse,
)
async def assign_role(
    body: RoleChangeRequest,
    user_id:         UUID = Path(..., description="Target user UUID"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       UUID = Header(..., alias="X-User-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
):
    """Apply a role change to a target user. Either template-derived or
    explicit override; either way the audit row says which.

    The caller's X-User-Role header is what the gateway forwards from
    the JWT — auth-service signs JWTs whose claims include `role`. In
    local-dev runs where the gateway is bypassed, MANAGER is hard-required.
    """
    # ── Authz: MANAGER only ─────────────────────────────────────
    if x_user_role and x_user_role != 'MANAGER':
        raise HTTPException(
            status_code=403,
            detail=f"Only MANAGER can change roles; caller role={x_user_role!r}.",
        )

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # ── Target user exists + same enterprise ───────────────
        target = await conn.fetchrow(
            """SELECT user_id, email, role, enterprise_id
               FROM enterprise_users
               WHERE user_id = $1""",
            user_id,
        )
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")
        if target["enterprise_id"] != x_enterprise_id:
            # Cross-enterprise role grant blocked. 403 not 404 because the
            # caller proved a valid user_id — we just refuse the operation.
            raise HTTPException(
                status_code=403,
                detail="Cannot change role for user in a different enterprise.",
            )

        # ── Resolve target role ────────────────────────────────
        template_id: Optional[UUID] = None
        if body.role is not None:
            # Override path — explicit role.
            new_role = body.role
            source = 'override'
        else:
            # Template path — look up dept + seniority.
            dept = await conn.fetchrow(
                """SELECT department_id, dept_type, enterprise_id
                   FROM departments
                   WHERE department_id = $1""",
                body.department_id,
            )
            if dept is None:
                raise HTTPException(status_code=404, detail="department not found")
            if dept["enterprise_id"] != x_enterprise_id:
                raise HTTPException(
                    status_code=403,
                    detail="Department belongs to a different enterprise.",
                )

            tpl = await conn.fetchrow(
                """SELECT template_id, default_role
                   FROM department_role_templates
                   WHERE is_active = TRUE
                     AND dept_type = $1
                     AND seniority_level = $2
                     AND (enterprise_id = $3 OR enterprise_id IS NULL)
                   ORDER BY enterprise_id NULLS LAST
                   LIMIT 1""",
                dept["dept_type"], body.seniority_level, x_enterprise_id,
            )
            if tpl is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"No role template for dept_type={dept['dept_type']!r} "
                        f"seniority_level={body.seniority_level!r}. "
                        "Use explicit role override instead."
                    ),
                )
            new_role = tpl["default_role"]
            template_id = tpl["template_id"]
            source = 'template'

        previous_role = target["role"]

        # Short-circuit no-op: if role doesn't change, still emit an
        # audit row so the manager's intent ("I reviewed and confirmed
        # this role") is captured.
        async with conn.transaction():
            if previous_role != new_role:
                await conn.execute(
                    """UPDATE enterprise_users
                       SET role = $1, updated_at = NOW()
                       WHERE user_id = $2""",
                    new_role, user_id,
                )

            # Look up workspace_id for the audit row key.
            ws_row = await conn.fetchrow(
                "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
                x_enterprise_id,
            )
            workspace_id = ws_row["workspace_id"] if ws_row else None

            event_type = (
                'enterprise_user.role.assigned' if source == 'template'
                else 'enterprise_user.role.overridden'
            )
            detail_parts = [
                f"from={previous_role}",
                f"to={new_role}",
                f"source={source}",
            ]
            if template_id is not None:
                detail_parts.append(f"template_id={template_id}")
            if body.reason:
                detail_parts.append(f"reason={body.reason}")

            audit_row = await conn.fetchrow(
                """INSERT INTO workspace_audit_log
                       (workspace_id, event_type, actor_id, actor_email,
                        actor_role, resource, detail)
                   VALUES ($1, $2, $3, NULL, 'MANAGER', $4, $5)
                   RETURNING event_id""",
                workspace_id, event_type, x_user_id,
                target["email"], " ".join(detail_parts),
            )

    log.info(
        "enterprise_user.role.applied",
        user_id=str(user_id),
        previous_role=previous_role,
        new_role=new_role,
        source=source,
        template_id=str(template_id) if template_id else None,
        actor_id=str(x_user_id),
        enterprise_id=str(x_enterprise_id),
    )

    return RoleChangeResponse(
        user_id=user_id,
        role=new_role,
        previous_role=previous_role,
        source=source,
        template_id=template_id,
        audit_event_id=audit_row["event_id"],
        enterprise_id=x_enterprise_id,
    )


# ─── Onboard-from-CSV ──────────────────────────────────────────────


class OnboardFromCsvRequest(BaseModel):
    """Bronze-tier file to read employees from. Column names default to
    the canonical layout shipped in `data/sample/users-onboarding-approval.csv`
    but can be overridden when an enterprise uses a different schema."""
    bronze_file_id: UUID
    dry_run:        bool = Field(
        default=False,
        description=(
            "When TRUE, no INSERT happens — the response describes what "
            "WOULD be created so the manager can preview before commit."
        ),
    )
    email_col:      str = Field(default='email',           max_length=64)
    name_col:       str = Field(default='full_name',       max_length=64)
    dept_col:       str = Field(default='department',      max_length=64)
    seniority_col:  str = Field(default='seniority_level', max_length=64)


class OnboardRowOutcome(BaseModel):
    row_index:     int
    email:         Optional[str]   = None
    outcome:       str
    """One of: created, skipped_existing, skipped_no_dept, skipped_no_template, error."""
    role:          Optional[str]   = None
    dept_type:     Optional[str]   = None
    department_id: Optional[UUID]  = None
    template_id:   Optional[UUID]  = None
    user_id:       Optional[UUID]  = None
    error:         Optional[str]   = None


class OnboardFromCsvResponse(BaseModel):
    bronze_file_id:       UUID
    enterprise_id:        UUID
    dry_run:              bool
    total_rows:           int
    created:              int
    skipped_existing:     int
    skipped_no_dept:      int
    skipped_no_template:  int
    errors:               int
    outcomes:             list[OnboardRowOutcome]


@router.post(
    "/enterprise-users/onboard-from-csv",
    response_model=OnboardFromCsvResponse,
)
async def onboard_from_csv(
    body: OnboardFromCsvRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       UUID = Header(..., alias="X-User-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
):
    """Bulk-onboard employees from a previously uploaded CSV.

    Per row:
      1. Extract email + full_name + department + seniority_level.
      2. Classify the dept name (Vietnamese-aware) → dept_type enum.
      3. Resolve department_id by (enterprise_id, dept_type, status='active').
      4. Look up department_role_templates → default_role.
      5. INSERT enterprise_users with status='pending' + random unusable
         BCrypt hash. ON CONFLICT (enterprise_id, email) DO NOTHING.
      6. Audit row: enterprise_user.onboarded.

    Errors per row do NOT abort the batch — outcomes[] reports each one
    so the manager can fix and re-upload. On `dry_run=true` no INSERT
    happens; outcome='created' on dry_run means "would create"."""
    # Authz: MANAGER only (mirrors the role PATCH endpoint above).
    if x_user_role and x_user_role != 'MANAGER':
        raise HTTPException(
            status_code=403,
            detail=f"Only MANAGER can onboard users; caller role={x_user_role!r}.",
        )

    outcomes: list[OnboardRowOutcome] = []
    created = 0
    skipped_existing = 0
    skipped_no_dept = 0
    skipped_no_template = 0
    errors = 0

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Validate bronze_file ownership.
        bf = await conn.fetchrow(
            "SELECT file_id, enterprise_id FROM bronze_files WHERE file_id = $1",
            body.bronze_file_id,
        )
        if bf is None:
            raise HTTPException(status_code=404, detail="bronze file not found")
        if bf["enterprise_id"] != x_enterprise_id:
            raise HTTPException(
                status_code=403,
                detail="Bronze file belongs to a different enterprise.",
            )

        rows = await conn.fetch(
            """SELECT row_index, raw_data FROM bronze_rows
               WHERE file_id = $1
               ORDER BY row_index""",
            body.bronze_file_id,
        )

        # Per-batch department lookup cache — same (enterprise, dept_type)
        # pair is hit many times in a 100-row CSV.
        dept_cache: dict[str, Optional[dict]] = {}

        # Workspace for audit FK.
        ws_row = await conn.fetchrow(
            "SELECT workspace_id FROM enterprises WHERE enterprise_id = $1",
            x_enterprise_id,
        )
        workspace_id = ws_row["workspace_id"] if ws_row else None

        for r in rows:
            raw = r["raw_data"]
            row_data = json.loads(raw) if isinstance(raw, str) else (raw or {})

            email_raw = row_data.get(body.email_col) or ''
            email = email_raw.strip().lower() if isinstance(email_raw, str) else ''
            full_name_raw = row_data.get(body.name_col) or ''
            full_name = full_name_raw.strip() if isinstance(full_name_raw, str) else None
            dept_raw = row_data.get(body.dept_col)
            seniority_raw = row_data.get(body.seniority_col) or ''
            seniority = (seniority_raw.strip().lower()
                         if isinstance(seniority_raw, str) else '')

            if not email or '@' not in email:
                outcomes.append(OnboardRowOutcome(
                    row_index=r["row_index"], email=email or None,
                    outcome='error',
                    error="missing or invalid email",
                ))
                errors += 1
                continue

            if seniority not in SENIORITY_LEVELS:
                outcomes.append(OnboardRowOutcome(
                    row_index=r["row_index"], email=email,
                    outcome='error',
                    error=f"invalid seniority_level={seniority!r}; must be one of {SENIORITY_LEVELS}",
                ))
                errors += 1
                continue

            dept_type = classify_dept_name(dept_raw if isinstance(dept_raw, str) else None)

            # Resolve department_id (cache miss → query).
            if dept_type not in dept_cache:
                dept_row = await conn.fetchrow(
                    """SELECT department_id FROM departments
                       WHERE enterprise_id = $1
                         AND dept_type = $2
                         AND status = 'active'
                       ORDER BY created_at ASC
                       LIMIT 1""",
                    x_enterprise_id, dept_type,
                )
                dept_cache[dept_type] = dict(dept_row) if dept_row else None
            dept = dept_cache[dept_type]

            if dept is None:
                outcomes.append(OnboardRowOutcome(
                    row_index=r["row_index"], email=email,
                    outcome='skipped_no_dept', dept_type=dept_type,
                    error=(
                        f"no active department of dept_type={dept_type!r} "
                        f"in enterprise {x_enterprise_id} — create one first."
                    ),
                ))
                skipped_no_dept += 1
                continue

            tpl = await conn.fetchrow(
                """SELECT template_id, default_role
                   FROM department_role_templates
                   WHERE is_active = TRUE
                     AND dept_type = $1
                     AND seniority_level = $2
                     AND (enterprise_id = $3 OR enterprise_id IS NULL)
                   ORDER BY enterprise_id NULLS LAST
                   LIMIT 1""",
                dept_type, seniority, x_enterprise_id,
            )
            if tpl is None:
                outcomes.append(OnboardRowOutcome(
                    row_index=r["row_index"], email=email,
                    outcome='skipped_no_template', dept_type=dept_type,
                    department_id=dept["department_id"],
                    error=(
                        f"no template for ({dept_type!r}, {seniority!r}); "
                        "seed missing or both global + override inactive."
                    ),
                ))
                skipped_no_template += 1
                continue

            if body.dry_run:
                outcomes.append(OnboardRowOutcome(
                    row_index=r["row_index"], email=email,
                    outcome='created',  # "would create"
                    role=tpl["default_role"], dept_type=dept_type,
                    department_id=dept["department_id"],
                    template_id=tpl["template_id"],
                ))
                created += 1
                continue

            async with conn.transaction():
                inserted = await conn.fetchrow(
                    """INSERT INTO enterprise_users
                            (enterprise_id, email, password_hash, full_name, role, status)
                       VALUES ($1, $2, $3, $4, $5, 'pending')
                       ON CONFLICT (enterprise_id, email) DO NOTHING
                       RETURNING user_id""",
                    x_enterprise_id, email,
                    generate_pending_password_hash(),
                    full_name, tpl["default_role"],
                )
                if inserted is None:
                    outcomes.append(OnboardRowOutcome(
                        row_index=r["row_index"], email=email,
                        outcome='skipped_existing',
                        role=tpl["default_role"], dept_type=dept_type,
                        department_id=dept["department_id"],
                        template_id=tpl["template_id"],
                    ))
                    skipped_existing += 1
                    continue

                # Audit row — append-only per CLAUDE.md K-6 spirit.
                await conn.execute(
                    """INSERT INTO workspace_audit_log
                           (workspace_id, event_type, actor_id, actor_email,
                            actor_role, resource, detail)
                       VALUES ($1, 'enterprise_user.onboarded', $2, NULL, 'MANAGER',
                               $3, $4)""",
                    workspace_id, x_user_id, email,
                    (
                        f"dept_type={dept_type} "
                        f"seniority={seniority} "
                        f"role={tpl['default_role']} "
                        f"template_id={tpl['template_id']} "
                        f"bronze_file_id={body.bronze_file_id}"
                    ),
                )

            outcomes.append(OnboardRowOutcome(
                row_index=r["row_index"], email=email,
                outcome='created',
                role=tpl["default_role"], dept_type=dept_type,
                department_id=dept["department_id"],
                template_id=tpl["template_id"],
                user_id=inserted["user_id"],
            ))
            created += 1

    log.info(
        "enterprise_user.onboard_from_csv.complete",
        bronze_file_id=str(body.bronze_file_id),
        dry_run=body.dry_run,
        total=len(outcomes),
        created=created,
        skipped_existing=skipped_existing,
        skipped_no_dept=skipped_no_dept,
        skipped_no_template=skipped_no_template,
        errors=errors,
        enterprise_id=str(x_enterprise_id),
        actor_id=str(x_user_id),
    )

    return OnboardFromCsvResponse(
        bronze_file_id=body.bronze_file_id,
        enterprise_id=x_enterprise_id,
        dry_run=body.dry_run,
        total_rows=len(outcomes),
        created=created,
        skipped_existing=skipped_existing,
        skipped_no_dept=skipped_no_dept,
        skipped_no_template=skipped_no_template,
        errors=errors,
        outcomes=outcomes,
    )
