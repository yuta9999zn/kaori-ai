"""
F-038 Reports — DB layer.

asyncpg-based repository functions. Every query takes a connection
acquired via ``acquire_for_tenant`` (sets ``app.enterprise_id``) so
tenant RLS does the isolation work — we never pass enterprise_id as
a SQL filter again, matching the K-1 enforcement boundary on
NOBYPASSRLS-cutover Postgres (migration 025).
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import asyncpg


# ─── Templates ───────────────────────────────────────────────────

async def fetch_template(conn: asyncpg.Connection, template_id: UUID) -> Optional[dict]:
    """Return the template row as a plain dict, or None when not
    visible (caller is wrong tenant + template isn't built-in). The
    RLS policies (tenant + built_in_visible) handle the visibility
    decision automatically."""
    row = await conn.fetchrow(
        """
        SELECT template_id, enterprise_id, name, description,
               system_prompt, output_schema, is_built_in
        FROM report_templates
        WHERE template_id = $1
        """,
        template_id,
    )
    if row is None:
        return None
    return _template_row(row)


async def list_templates(conn: asyncpg.Connection) -> list[dict]:
    """All templates the current tenant can see — built-ins + their
    own (the RLS policies handle the OR). Ordered: built-ins first
    (stable id), then tenant templates by created_at DESC."""
    rows = await conn.fetch(
        """
        SELECT template_id, enterprise_id, name, description,
               system_prompt, output_schema, is_built_in
        FROM report_templates
        ORDER BY is_built_in DESC, created_at DESC
        """
    )
    return [_template_row(r) for r in rows]


def _template_row(row: asyncpg.Record) -> dict:
    # output_schema comes back as a JSONB column. asyncpg returns it as
    # a string when no codec is registered (default), so decode to dict
    # before handing back to callers.
    schema = row["output_schema"]
    if isinstance(schema, str):
        schema = json.loads(schema)
    return {
        "template_id":   row["template_id"],
        "enterprise_id": row["enterprise_id"],
        "name":          row["name"],
        "description":   row["description"],
        "system_prompt": row["system_prompt"],
        "output_schema": schema,
        "is_built_in":   row["is_built_in"],
    }


# ─── Reports — write side ────────────────────────────────────────

async def create_report(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    template_id: UUID,
    title: str,
    owner_email: str,
    params: dict,
) -> UUID:
    """Insert a queued report row in the caller's transaction. Returns
    the new report_id."""
    row = await conn.fetchrow(
        """
        INSERT INTO reports
            (enterprise_id, template_id, title, owner_email, params, status)
        VALUES ($1, $2, $3, $4, $5::jsonb, 'queued')
        RETURNING report_id
        """,
        enterprise_id,
        template_id,
        title,
        owner_email,
        json.dumps(params or {}),
    )
    return row["report_id"]


async def mark_running(conn: asyncpg.Connection, report_id: UUID) -> None:
    await conn.execute(
        "UPDATE reports SET status='running' WHERE report_id=$1",
        report_id,
    )


async def mark_ready(
    conn: asyncpg.Connection,
    report_id: UUID,
    *,
    content_json: dict,
    narrative: Optional[str],
) -> None:
    await conn.execute(
        """
        UPDATE reports
           SET status='ready', completed_at=NOW(),
               content_json=$2::jsonb, narrative=$3, last_error=NULL
         WHERE report_id=$1
        """,
        report_id,
        json.dumps(content_json),
        narrative,
    )


async def mark_failed(conn: asyncpg.Connection, report_id: UUID, error: str) -> None:
    await conn.execute(
        """
        UPDATE reports
           SET status='failed', completed_at=NOW(), last_error=$2
         WHERE report_id=$1
        """,
        report_id,
        _truncate(error),
    )


# ─── Reports — read side ─────────────────────────────────────────

async def list_reports(
    conn: asyncpg.Connection,
    *,
    limit: int = 50,
    cursor_created_at=None,
    cursor_report_id=None,
) -> list[dict]:
    """Cursor-paginated list. K-1 isolation via the active tenant
    GUC — no enterprise_id filter in the WHERE clause."""
    if cursor_created_at is None:
        rows = await conn.fetch(
            """
            SELECT report_id, template_id, title, owner_email, status,
                   narrative, created_at, completed_at, last_error
              FROM reports
             ORDER BY created_at DESC, report_id DESC
             LIMIT $1
            """,
            limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT report_id, template_id, title, owner_email, status,
                   narrative, created_at, completed_at, last_error
              FROM reports
             WHERE (created_at, report_id) < ($1, $2)
             ORDER BY created_at DESC, report_id DESC
             LIMIT $3
            """,
            cursor_created_at, cursor_report_id, limit,
        )
    return [_report_row(r) for r in rows]


async def fetch_report(conn: asyncpg.Connection, report_id: UUID) -> Optional[dict]:
    """Single report with full content_json. Returns None when not
    visible (RLS enforces tenant scoping)."""
    row = await conn.fetchrow(
        """
        SELECT report_id, template_id, title, owner_email, status,
               narrative, content_json, created_at, completed_at, last_error
        FROM reports
        WHERE report_id = $1
        """,
        report_id,
    )
    if row is None:
        return None
    base = _report_row(row)
    content = row["content_json"]
    if isinstance(content, str):
        content = json.loads(content)
    base["content_json"] = content
    return base


def _report_row(row: asyncpg.Record) -> dict:
    return {
        "report_id":    row["report_id"],
        "template_id":  row["template_id"],
        "title":        row["title"],
        "owner_email":  row["owner_email"],
        "status":       row["status"],
        "narrative":    row["narrative"],
        "created_at":   row["created_at"],
        "completed_at": row["completed_at"],
        "last_error":   row["last_error"],
    }


def _truncate(text: Optional[str], limit: int = 4000) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


# ─── Distributions (F-038 follow-up — migration 029) ──────────────

async def create_distribution(
    conn: asyncpg.Connection,
    *,
    enterprise_id: UUID,
    report_id: UUID,
    recipient_email: str,
    channel: str,
    outbox_id: Optional[UUID],
    status: str,
    custom_message: Optional[str],
    triggered_by_user: Optional[UUID],
    last_error: Optional[str],
) -> UUID:
    """Insert one row in report_distributions. The caller is expected
    to have already enqueued the matching notification_outbox row (or
    captured an enqueue error, in which case ``status='failed'`` and
    ``outbox_id`` is None)."""
    row = await conn.fetchrow(
        """
        INSERT INTO report_distributions
            (enterprise_id, report_id, recipient_email, channel,
             outbox_id, status, custom_message, triggered_by_user,
             last_error)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING distribution_id
        """,
        enterprise_id,
        report_id,
        recipient_email,
        channel,
        outbox_id,
        status,
        custom_message,
        triggered_by_user,
        _truncate(last_error),
    )
    return row["distribution_id"]


async def list_distributions(conn: asyncpg.Connection, report_id: UUID) -> list[dict]:
    """List distributions for a report. Joins notification_outbox so
    the FE gets the live SMTP state without a second query.
    Tenant-scoped via RLS GUC on the connection."""
    rows = await conn.fetch(
        """
        SELECT d.distribution_id, d.report_id, d.recipient_email, d.channel,
               d.outbox_id, d.status AS dispatch_status, d.custom_message,
               d.triggered_by_user, d.last_error AS dispatch_error,
               d.created_at,
               n.status      AS outbox_status,
               n.attempts    AS outbox_attempts,
               n.last_error  AS outbox_error,
               n.sent_at     AS outbox_sent_at
          FROM report_distributions d
          LEFT JOIN notification_outbox n ON n.outbox_id = d.outbox_id
         WHERE d.report_id = $1
         ORDER BY d.created_at DESC
        """,
        report_id,
    )
    return [
        {
            "distribution_id":   r["distribution_id"],
            "report_id":         r["report_id"],
            "recipient_email":   r["recipient_email"],
            "channel":           r["channel"],
            "outbox_id":         r["outbox_id"],
            "dispatch_status":   r["dispatch_status"],
            "custom_message":    r["custom_message"],
            "triggered_by_user": r["triggered_by_user"],
            "dispatch_error":    r["dispatch_error"],
            "created_at":        r["created_at"],
            "outbox_status":     r["outbox_status"],
            "outbox_attempts":   r["outbox_attempts"],
            "outbox_error":      r["outbox_error"],
            "outbox_sent_at":    r["outbox_sent_at"],
        }
        for r in rows
    ]
