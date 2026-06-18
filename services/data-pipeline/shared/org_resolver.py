"""
org_resolver.py — P15-S11 Tuần 8 Step 4.1.

Resolve branch_id / department_id / source_id for uploads + per-dept reads
when the caller does not supply them explicitly.

Default resolution rules (mig 046-047 backfill convention):
  - branch_id  default → enterprise's `is_default=TRUE` branch
                         ("Trụ sở chính" auto-seeded by mig 046)
  - dept_id    default → enterprise's `dept_type='marketing'` department
                         if present (mig 046), else the oldest active
                         department (custom-org SMEs without Marketing)
  - source_id  default → that dept's `source_kind='manual_upload'` source
                         (auto-seeded by mig 046 per-dept)

All resolvers run inside an `acquire_for_tenant` connection so RLS
isolates per-enterprise. Returning `None` means the enterprise has not
been backfilled — caller should raise 422 with a clear message.

Mapping template lookup:
  - match_mapping_template(conn, enterprise_id, source_id, filename) →
    first active template whose `file_pattern` glob matches filename
    (case-insensitive). Returns the full template row dict or None.
"""
from __future__ import annotations

import fnmatch
from typing import Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


async def resolve_default_branch(
    conn,
    enterprise_id: UUID | str,
) -> Optional[UUID]:
    """Return enterprise's default branch (`is_default=TRUE`) or None."""
    row = await conn.fetchrow(
        """SELECT branch_id FROM branches
           WHERE enterprise_id = $1 AND is_default = TRUE AND status = 'active'
           LIMIT 1""",
        _coerce(enterprise_id),
    )
    return row["branch_id"] if row else None


async def resolve_default_department(
    conn,
    enterprise_id: UUID | str,
) -> Optional[UUID]:
    """Return the enterprise's default attribution department, or None.

    Prefers the Marketing department (mig-046 seeds one for every
    canonically-provisioned enterprise), but falls back to the oldest
    active department when no Marketing department exists — so SMEs with
    a custom org structure (no Marketing dept) can still upload without
    an explicit X-Department-ID. Returns None only when the enterprise
    has no active department at all.
    """
    row = await conn.fetchrow(
        """SELECT department_id FROM departments
           WHERE enterprise_id = $1
             AND status        = 'active'
           ORDER BY (dept_type = 'marketing') DESC, created_at ASC
           LIMIT 1""",
        _coerce(enterprise_id),
    )
    return row["department_id"] if row else None


async def resolve_default_source(
    conn,
    enterprise_id: UUID | str,
    department_id: UUID | str,
) -> Optional[UUID]:
    """Return the dept's Manual upload source or None."""
    row = await conn.fetchrow(
        """SELECT source_id FROM data_sources
           WHERE enterprise_id = $1
             AND department_id = $2
             AND source_kind   = 'manual_upload'
             AND status        = 'active'
           ORDER BY created_at ASC
           LIMIT 1""",
        _coerce(enterprise_id),
        _coerce(department_id),
    )
    return row["source_id"] if row else None


async def assert_department_in_enterprise(
    conn,
    enterprise_id: UUID | str,
    department_id: UUID | str,
) -> bool:
    """True iff department belongs to the enterprise (active or archived).

    Used by upload to reject X-Department-ID values that point at another
    enterprise's department — cross-tenant guard layered on top of RLS.
    """
    row = await conn.fetchrow(
        """SELECT 1 FROM departments
           WHERE enterprise_id = $1 AND department_id = $2
           LIMIT 1""",
        _coerce(enterprise_id),
        _coerce(department_id),
    )
    return row is not None


async def assert_branch_in_enterprise(
    conn,
    enterprise_id: UUID | str,
    branch_id: UUID | str,
) -> bool:
    row = await conn.fetchrow(
        """SELECT 1 FROM branches
           WHERE enterprise_id = $1 AND branch_id = $2
           LIMIT 1""",
        _coerce(enterprise_id),
        _coerce(branch_id),
    )
    return row is not None


async def assert_source_in_department(
    conn,
    enterprise_id: UUID | str,
    department_id: UUID | str,
    source_id: UUID | str,
) -> bool:
    row = await conn.fetchrow(
        """SELECT 1 FROM data_sources
           WHERE enterprise_id = $1 AND department_id = $2 AND source_id = $3
           LIMIT 1""",
        _coerce(enterprise_id),
        _coerce(department_id),
        _coerce(source_id),
    )
    return row is not None


async def resolve_org_attribution(
    conn,
    enterprise_id: UUID | str,
    *,
    branch_id: UUID | str | None = None,
    department_id: UUID | str | None = None,
    source_id: UUID | str | None = None,
) -> dict:
    """Resolve the (branch_id, department_id, source_id) triple for an upload.

    Caller passes whatever was supplied via headers; missing values are
    filled from the enterprise's defaults. The returned dict always has
    all three keys with valid UUIDs, or raises ValueError naming the
    first missing piece.

    Cross-tenant guard: any non-null caller value must belong to the
    enterprise — otherwise a ValueError fires before any write happens.
    """
    eid = _coerce(enterprise_id)

    # 1. Department ----------------------------------------------------
    if department_id is not None:
        if not await assert_department_in_enterprise(conn, eid, department_id):
            raise ValueError(
                f"X-Department-ID {department_id} does not belong to enterprise"
            )
        dept_id = _coerce(department_id)
    else:
        resolved = await resolve_default_department(conn, eid)
        if resolved is None:
            raise ValueError(
                "Enterprise has no active department to attribute the upload "
                "to — create at least one department first"
            )
        dept_id = resolved

    # 2. Branch --------------------------------------------------------
    if branch_id is not None:
        if not await assert_branch_in_enterprise(conn, eid, branch_id):
            raise ValueError(
                f"X-Branch-ID {branch_id} does not belong to enterprise"
            )
        br_id = _coerce(branch_id)
    else:
        resolved = await resolve_default_branch(conn, eid)
        if resolved is None:
            raise ValueError(
                "Enterprise has no default branch — "
                "run migration 046_org_hierarchy.sql"
            )
        br_id = resolved

    # 3. Source --------------------------------------------------------
    if source_id is not None:
        if not await assert_source_in_department(conn, eid, dept_id, source_id):
            raise ValueError(
                f"X-Source-ID {source_id} does not belong to the resolved department"
            )
        src_id = _coerce(source_id)
    else:
        resolved = await resolve_default_source(conn, eid, dept_id)
        if resolved is None:
            raise ValueError(
                "Department has no Manual upload source — "
                "run migration 046_org_hierarchy.sql"
            )
        src_id = resolved

    return {
        "branch_id":     br_id,
        "department_id": dept_id,
        "source_id":     src_id,
    }


async def match_mapping_template(
    conn,
    enterprise_id: UUID | str,
    source_id: UUID | str,
    filename: str,
) -> Optional[dict]:
    """Find the first active template whose file_pattern matches `filename`.

    Glob matching is case-insensitive (Vietnamese filenames frequently
    mix case). Returns the full row as a plain dict, or None.

    `confirmed_count` + `last_used_at` are NOT incremented here — that
    happens when the user actually accepts the auto-loaded mapping at
    Stage 2C. Matching alone is a read.
    """
    rows = await conn.fetch(
        """SELECT template_id, name, file_pattern, file_kind,
                  column_mapping, domain, confirmed_count, last_used_at
           FROM mapping_templates
           WHERE enterprise_id = $1
             AND source_id     = $2
             AND is_active     = TRUE
           ORDER BY confirmed_count DESC, last_used_at DESC NULLS LAST""",
        _coerce(enterprise_id),
        _coerce(source_id),
    )
    if not rows:
        return None

    lower_filename = filename.lower()
    for row in rows:
        pattern = (row["file_pattern"] or "").lower()
        if pattern and fnmatch.fnmatch(lower_filename, pattern):
            return dict(row)
    return None


def _coerce(value: UUID | str) -> UUID:
    """Accept UUID or str, return UUID. Raises ValueError on bad input."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
