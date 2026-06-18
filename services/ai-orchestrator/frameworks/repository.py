"""
F-034 Frameworks — DB layer.

asyncpg-based repository for ``framework_runs`` (migration 030).
Every query takes a connection acquired via ``acquire_for_tenant``
so RLS does the tenant scoping — same pattern as F-038 reports.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import asyncpg


# ─── Write side ──────────────────────────────────────────────────

async def create_run(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    framework_code: str,
    question: str,
    source_ref: Optional[str],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued framework_runs row in the caller's transaction.
    Returns the new run_id."""
    row = await conn.fetchrow(
        """
        INSERT INTO framework_runs
            (enterprise_id, framework_code, question, source_ref,
             consent_external, created_by_user, status)
        VALUES ($1, $2, $3, $4, $5, $6, 'queued')
        RETURNING run_id
        """,
        enterprise_id,
        framework_code,
        question,
        source_ref,
        consent_external,
        created_by_user,
    )
    return row["run_id"]


async def mark_running(conn: asyncpg.Connection, run_id: UUID) -> None:
    await conn.execute(
        "UPDATE framework_runs SET status='running' WHERE run_id=$1",
        run_id,
    )


async def mark_ready(
    conn: asyncpg.Connection,
    run_id: UUID,
    *,
    content_json: dict,
    narrative: Optional[str],
) -> None:
    await conn.execute(
        """
        UPDATE framework_runs
           SET status='ready', completed_at=NOW(),
               content_json=$2::jsonb, narrative=$3, last_error=NULL
         WHERE run_id=$1
        """,
        run_id,
        json.dumps(content_json),
        narrative,
    )


async def mark_failed(conn: asyncpg.Connection, run_id: UUID, error: str) -> None:
    await conn.execute(
        """
        UPDATE framework_runs
           SET status='failed', completed_at=NOW(), last_error=$2
         WHERE run_id=$1
        """,
        run_id,
        _truncate(error),
    )


# ─── Read side ───────────────────────────────────────────────────

async def list_runs(
    conn: asyncpg.Connection,
    *,
    limit: int = 50,
    cursor_created_at=None,
    cursor_run_id=None,
) -> list[dict]:
    """Cursor-paginated list. Tenant isolation via RLS GUC on the
    connection — no enterprise_id filter in the WHERE clause."""
    if cursor_created_at is None:
        rows = await conn.fetch(
            """
            SELECT run_id, framework_code, question, source_ref,
                   consent_external, status, narrative,
                   created_by_user, created_at, completed_at, last_error
              FROM framework_runs
             ORDER BY created_at DESC, run_id DESC
             LIMIT $1
            """,
            limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT run_id, framework_code, question, source_ref,
                   consent_external, status, narrative,
                   created_by_user, created_at, completed_at, last_error
              FROM framework_runs
             WHERE (created_at, run_id) < ($1, $2)
             ORDER BY created_at DESC, run_id DESC
             LIMIT $3
            """,
            cursor_created_at, cursor_run_id, limit,
        )
    return [_run_row(r) for r in rows]


async def fetch_run(conn: asyncpg.Connection, run_id: UUID) -> Optional[dict]:
    """Single row + content_json. Returns None when not visible (RLS
    enforces tenant scoping)."""
    row = await conn.fetchrow(
        """
        SELECT run_id, framework_code, question, source_ref,
               consent_external, status, narrative, content_json,
               created_by_user, created_at, completed_at, last_error
        FROM framework_runs
        WHERE run_id = $1
        """,
        run_id,
    )
    if row is None:
        return None
    base = _run_row(row)
    content = row["content_json"]
    if isinstance(content, str):
        content = json.loads(content)
    base["content_json"] = content
    return base


# ─── Helpers ─────────────────────────────────────────────────────

def _run_row(row: asyncpg.Record) -> dict:
    return {
        "run_id":           row["run_id"],
        "framework_code":   row["framework_code"],
        "question":         row["question"],
        "source_ref":       row["source_ref"],
        "consent_external": row["consent_external"],
        "status":           row["status"],
        "narrative":        row["narrative"],
        "created_by_user":  row["created_by_user"],
        "created_at":       row["created_at"],
        "completed_at":     row["completed_at"],
        "last_error":       row["last_error"],
    }


def _truncate(text: Optional[str], limit: int = 4000) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
