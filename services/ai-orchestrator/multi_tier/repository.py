"""
F-033 Multi-tier Analysis — DB layer.

asyncpg repository for the extended ``analysis_runs`` table (migration
036). Same RLS pattern as F-034 frameworks: every query takes a
connection acquired via ``acquire_for_tenant`` so the GUC enforces
tenant scoping — no enterprise_id in the WHERE clause.

The wizard endpoint (``POST /api/v1/analytics/runs``) and this module
share the table; they write disjoint column subsets. Wizard rows have
``tier='basic'`` / ``scope='single'`` (defaults from the migration) plus
the legacy ``run_id`` + ``templates`` + ``config`` columns. Multi-tier
rows additionally carry ``question``, ``framework``, ``source_ids``,
``narrative``, ``output_schema_repaired`` etc.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncpg


# ─── Write side ──────────────────────────────────────────────────


async def create_basic_run(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    pipeline_run_id: UUID,
    templates_: list[str],
    question: Optional[str],
    config: Optional[dict],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued basic-tier row. Anchored on ``pipeline_run_id``
    so the existing wizard runner can pick it up."""
    row = await conn.fetchrow(
        """
        INSERT INTO analysis_runs
            (enterprise_id, run_id, templates, config,
             tier, scope, question,
             consent_external, created_by_user, status)
        VALUES ($1, $2, $3, $4::jsonb,
                'basic', 'single', $5,
                $6, $7, 'queued')
        RETURNING id
        """,
        enterprise_id,
        pipeline_run_id,
        templates_,
        json.dumps(config or {}),
        question,
        consent_external,
        created_by_user,
    )
    return row["id"]


async def create_advanced_run(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    framework: str,
    question: str,
    source_ids: list[dict],
    workspace_ids: list[UUID],
    requires_approval: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued advanced-tier row.

    Advanced ALWAYS sets consent_external=true (DB CHECK enforces K-4).
    `requires_approval` decided by the service from tenant settings —
    when true, the dispatcher in service.py will short-circuit and wait
    for ``approve_run`` to flip ``approved_at``."""
    initial_status = "queued"  # service decides whether to dispatch
    row = await conn.fetchrow(
        """
        INSERT INTO analysis_runs                       -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
            (enterprise_id, templates, config,
             tier, scope, framework, question, source_ids,
             workspace_ids, consent_external,
             requires_approval, created_by_user, status)
        VALUES ($1, ARRAY[]::TEXT[], '{}'::jsonb,
                'advanced', 'cross', $2, $3, $4::jsonb,
                $5, TRUE,
                $6, $7, $8)
        RETURNING id
        """,
        enterprise_id,
        framework,
        question,
        json.dumps(source_ids),
        workspace_ids,
        requires_approval,
        created_by_user,
        initial_status,
    )
    return row["id"]


async def approve_run(
    conn: asyncpg.Connection,
    run_id: UUID,
    *,
    approver_user_id: UUID,
) -> Optional[dict]:
    """Flip the approval columns for a pending advanced run. Returns
    the post-approval row, or None when the row didn't exist / wasn't
    pending. Idempotent re-approval is rejected at the SQL level (the
    WHERE clause excludes already-approved rows)."""
    row = await conn.fetchrow(
        """
        UPDATE analysis_runs                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
           SET approved_by = $2, approved_at = NOW()
         WHERE id = $1
           AND tier = 'advanced'
           AND requires_approval = TRUE
           AND approved_at IS NULL
        RETURNING id, status
        """,
        run_id,
        approver_user_id,
    )
    if row is None:
        return None
    return dict(row)


async def fetch_tenant_consent(
    conn: asyncpg.Connection,
    enterprise_id: UUID,
) -> bool:
    """Return tenant_settings.consent_external_ai for the calling
    tenant. Defaults to FALSE when the row is absent (tenant hasn't
    visited Settings yet)."""
    val = await conn.fetchval(
        """
        SELECT consent_external_ai
          FROM tenant_settings                          -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
         WHERE enterprise_id = $1
        """,
        enterprise_id,
    )
    return bool(val)


async def fetch_external_ai_usage(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    period_start: datetime,
) -> int:
    """Count external-LLM completions billed to this tenant in the
    current month. Reads decision_audit_log because every llm-gateway
    call writes an audit row (K-3) tagged with the provider; the
    `external` rows are the ones we charge against the quota."""
    val = await conn.fetchval(
        """
        SELECT COUNT(*)
          FROM decision_audit_log                       -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
         WHERE created_at >= $1
           AND llm_provider IS NOT NULL
           AND llm_provider <> 'qwen-internal'
        """,
        period_start,
    )
    return int(val or 0)


async def create_intermediate_run(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    framework: str,
    question: str,
    source_ids: list[dict],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued intermediate-tier row. Not anchored on a
    pipeline_run — references silver/gold sources via ``source_ids``."""
    row = await conn.fetchrow(
        """
        INSERT INTO analysis_runs
            (enterprise_id, templates, config,
             tier, scope, framework, question, source_ids,
             consent_external, created_by_user, status)
        VALUES ($1, ARRAY[]::TEXT[], '{}'::jsonb,
                'intermediate', 'multi', $2, $3, $4::jsonb,
                $5, $6, 'queued')
        RETURNING id
        """,
        enterprise_id,
        framework,
        question,
        json.dumps(source_ids),
        consent_external,
        created_by_user,
    )
    return row["id"]


async def mark_running(conn: asyncpg.Connection, run_id: UUID) -> None:
    await conn.execute(
        "UPDATE analysis_runs SET status='running', started_at=NOW() WHERE id=$1  -- tenant-filter-lint: allow (RLS via acquire_for_tenant)",
        run_id,
    )


async def mark_done(
    conn: asyncpg.Connection,
    run_id: UUID,
    *,
    overview: Optional[dict] = None,
    narrative: Optional[str] = None,
    output_schema_repaired: Optional[bool] = None,
) -> None:
    """Flip to terminal state ``status='done'``. Persists the
    cross-template overview (basic) or framework JSON (intermediate)
    into ``overview``, the LLM-generated paragraph into ``narrative``,
    and the Issue #3 repair flag into ``output_schema_repaired``."""
    await conn.execute(
        """
        UPDATE analysis_runs                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
           SET status='done',
               completed_at=NOW(),
               overview=$2::jsonb,
               narrative=$3,
               output_schema_repaired=$4
         WHERE id=$1
        """,
        run_id,
        json.dumps(overview) if overview is not None else None,
        narrative,
        output_schema_repaired,
    )


async def mark_error(conn: asyncpg.Connection, run_id: UUID, error: str) -> None:
    await conn.execute(
        """
        UPDATE analysis_runs                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
           SET status='error', completed_at=NOW(),
               overview=jsonb_build_object('error', $2::text)
         WHERE id=$1
        """,
        run_id,
        _truncate(error),
    )


# ─── Read side ───────────────────────────────────────────────────


async def fetch_run(conn: asyncpg.Connection, run_id: UUID) -> Optional[dict]:
    """Single row. Returns None when not visible to the calling tenant
    (RLS prunes cross-tenant rows so 404 just falls out of the SELECT)."""
    row = await conn.fetchrow(
        """
        SELECT id, enterprise_id, run_id, tier, scope,
               templates, config, framework, question, source_ids,
               workspace_ids, consent_external,
               requires_approval, approved_by, approved_at,
               status, overview, narrative, output_schema_repaired,
               started_at, completed_at, created_by_user, created_at
          FROM analysis_runs                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
         WHERE id = $1
        """,
        run_id,
    )
    if row is None:
        return None
    return _run_row(row)


async def list_runs(
    conn: asyncpg.Connection,
    *,
    limit: int = 50,
    tier: Optional[str] = None,
    cursor_created_at: Optional[datetime] = None,
    cursor_run_id: Optional[UUID] = None,
) -> list[dict]:
    """Cursor-paginated list. ``overview`` + ``config`` omitted to keep
    payload small — fetch the detail endpoint for those."""
    base_select = """
        SELECT id, run_id AS pipeline_run_id, tier, scope,
               framework, question, source_ids,
               consent_external, status, narrative,
               started_at, completed_at, created_by_user, created_at
          FROM analysis_runs                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
    """

    params: list = []
    where_parts: list[str] = []

    if tier is not None:
        params.append(tier)
        where_parts.append(f"tier = ${len(params)}")

    if cursor_created_at is not None and cursor_run_id is not None:
        params.append(cursor_created_at)
        params.append(cursor_run_id)
        where_parts.append(f"(created_at, id) < (${len(params) - 1}, ${len(params)})")

    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    params.append(limit)
    sql = f"""
        {base_select}
        {where_clause}
        ORDER BY created_at DESC, id DESC
        LIMIT ${len(params)}
    """

    rows = await conn.fetch(sql, *params)
    return [_list_row(r) for r in rows]


# ─── Source listing — Silver / Gold catalogue ─────────────────────


async def list_silver_sources(conn: asyncpg.Connection) -> list[dict]:
    """Distinct (run_id, filename) pairs that have silver_rows for the
    calling tenant. Only completed runs — RLS filters enterprise scope
    automatically. Returns lightweight metadata; intermediate-tier picker
    uses these as its left-pane list."""
    rows = await conn.fetch(
        """
        SELECT pr.run_id, pr.filename, pr.row_count_silver
          FROM pipeline_runs pr                         -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
         WHERE pr.status IN ('analysis_complete', 'silver_complete', 'analyzing')
           AND pr.row_count_silver > 0
         ORDER BY pr.created_at DESC
         LIMIT 100
        """,
    )
    return [
        {
            "id": str(r["run_id"]),
            "label": r["filename"] or str(r["run_id"]),
            "layer": "silver",
            "row_count": r["row_count_silver"] or 0,
        }
        for r in rows
    ]


# Pilot DB carries the v3-era WIDE gold_features (one row per customer,
# fixed feature columns) instead of the long (feature_name, feature_value)
# shape — the long query raises UndefinedColumnError there (incident
# 2026-07-10, /analysis/sources 500). These are the wide columns exposed
# as picker "features" on that schema.
_GOLD_WIDE_FEATURE_COLS = (
    "revenue_at_risk", "total_purchases", "purchase_count", "avg_purchase_value",
)


async def list_gold_sources(conn: asyncpg.Connection) -> list[dict]:
    """Gold features available to the calling tenant. Returns the
    distinct feature names + sample row count so the picker can show
    coverage. Handles both gold_features shapes: long (feature_name /
    feature_value) and the pilot's wide per-customer table."""
    try:
        rows = await conn.fetch(
            """
            SELECT feature_name, COUNT(*) AS row_count
              FROM gold_features                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
             WHERE feature_value IS NOT NULL
             GROUP BY feature_name
             ORDER BY row_count DESC
             LIMIT 100
            """,
        )
    except asyncpg.exceptions.UndefinedColumnError:
        counts = await conn.fetchrow(
            """
            SELECT COUNT(revenue_at_risk)    AS revenue_at_risk,
                   COUNT(total_purchases)    AS total_purchases,
                   COUNT(purchase_count)     AS purchase_count,
                   COUNT(avg_purchase_value) AS avg_purchase_value
              FROM gold_features                            -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
            """,
        )
        return [
            {
                "id": col,
                "label": col,
                "layer": "gold",
                "row_count": int(counts[col] or 0),
            }
            for col in _GOLD_WIDE_FEATURE_COLS
            if (counts[col] or 0) > 0
        ]
    return [
        {
            "id": r["feature_name"],
            "label": r["feature_name"],
            "layer": "gold",
            "row_count": r["row_count"],
        }
        for r in rows
    ]


# ─── Helpers ─────────────────────────────────────────────────────


def _run_row(row: asyncpg.Record) -> dict:
    overview = row["overview"]
    if isinstance(overview, str):
        overview = json.loads(overview)
    config = row["config"]
    if isinstance(config, str):
        config = json.loads(config)
    source_ids = row["source_ids"]
    if isinstance(source_ids, str):
        source_ids = json.loads(source_ids)
    return {
        "id":               row["id"],
        "enterprise_id":    row["enterprise_id"],
        "pipeline_run_id":  row["run_id"],
        "tier":             row["tier"],
        "scope":            row["scope"],
        "templates":        list(row["templates"] or []),
        "config":           config or {},
        "framework":        row["framework"],
        "question":         row["question"],
        "source_ids":       source_ids,
        "workspace_ids":    list(row["workspace_ids"] or []) if row["workspace_ids"] else [],
        "consent_external": row["consent_external"],
        "requires_approval": row["requires_approval"],
        "approved_by":      row["approved_by"],
        "approved_at":      row["approved_at"],
        "status":           row["status"],
        "overview":         overview,
        "narrative":        row["narrative"],
        "output_schema_repaired": row["output_schema_repaired"],
        "started_at":       row["started_at"],
        "completed_at":     row["completed_at"],
        "created_by_user":  row["created_by_user"],
        "created_at":       row["created_at"],
    }


def _list_row(row: asyncpg.Record) -> dict:
    source_ids = row["source_ids"]
    if isinstance(source_ids, str):
        source_ids = json.loads(source_ids)
    return {
        "id":               row["id"],
        "pipeline_run_id":  row["pipeline_run_id"],
        "tier":             row["tier"],
        "scope":            row["scope"],
        "framework":        row["framework"],
        "question":         row["question"],
        "source_ids":       source_ids,
        "consent_external": row["consent_external"],
        "status":           row["status"],
        "narrative":        row["narrative"],
        "started_at":       row["started_at"],
        "completed_at":     row["completed_at"],
        "created_by_user":  row["created_by_user"],
        "created_at":       row["created_at"],
    }


def _truncate(text: Optional[str], limit: int = 4000) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
