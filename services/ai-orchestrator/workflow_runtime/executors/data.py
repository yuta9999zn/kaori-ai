"""
Data-access executors — read_table + update_record.

K-1 / K-12: RLS enforced via acquire_for_tenant. Caller's enterprise_id
flows from JWT through NodeContext.

Whitelist
---------
Both executors use a strict table whitelist to avoid arbitrary SQL.
The whitelist lives in TABLE_WHITELIST below — adding a new table is a
deliberate code change reviewed for tenant scoping.
"""
from __future__ import annotations

from typing import Any

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


# Allowed tables (lowercase). All tables here MUST have enterprise_id
# column + RLS policy so acquire_for_tenant scopes them automatically.
TABLE_WHITELIST: set[str] = {
    "silver_customers",
    "silver_transactions",
    "silver_products",
    "silver_orders",
    "tenant_interventions",
    "decision_audit_log",
    "workflow_runs",
    "enterprise_users",
}

# Allowed columns per table for write_idempotent UPDATE. Same defensive
# stance — explicit allowlist beats blacklist.
UPDATABLE_COLUMNS: dict[str, set[str]] = {
    "tenant_interventions": {"status", "outcome", "notes"},
    "enterprise_users":     {"role", "status"},
    "decision_audit_log":   {"is_actioned"},
}


def _validate_identifier(name: str, kind: str) -> str:
    """Strict identifier validator. ASCII letters/digits/underscore only,
    must start with letter/underscore. Defense-in-depth over the
    whitelist."""
    if not name or not isinstance(name, str):
        raise NodeExecutorError(f"{kind} must be a non-empty string")
    if not (name[0].isalpha() or name[0] == "_"):
        raise NodeExecutorError(f"{kind}={name!r} invalid first char")
    for ch in name:
        if not (ch.isalnum() or ch == "_"):
            raise NodeExecutorError(f"{kind}={name!r} invalid char")
    return name


class ReadTableExecutor(NodeExecutor):
    """read_table — SELECT from a whitelisted Silver/Gold table.

    Config:
      table:    'silver_transactions'      (must be in TABLE_WHITELIST)
      columns:  ['col1', 'col2', ...]      (optional — default *)
      filter:   {col: value, ...}          (optional — equality only)
      limit:    int                        (optional — default 500, max 5000)
      order_by: 'col'                       (optional)
      order_dir: 'asc' | 'desc'             (optional — default 'asc')
    Output:
      {rows: list[dict], row_count: int, table: str}

    K-12: tenant_id always enforced via RLS — caller cannot bypass.
    """
    node_type_key = "read_table"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        table = config.get("table")
        if table not in TABLE_WHITELIST:
            raise NodeExecutorError(
                f"read_table.table={table!r} not in whitelist {sorted(TABLE_WHITELIST)}"
            )
        cols_raw = config.get("columns")
        if cols_raw:
            if not isinstance(cols_raw, list):
                raise NodeExecutorError("read_table.columns must be list[str]")
            cols = [_validate_identifier(c, "column") for c in cols_raw]
            select_list = ", ".join(cols)
        else:
            select_list = "*"

        # Lazy import to avoid circular dep in tests
        from ai_orchestrator.shared.db import acquire_for_tenant

        filters = config.get("filter") or {}
        if not isinstance(filters, dict):
            raise NodeExecutorError("read_table.filter must be a dict")

        where_clauses: list[str] = []
        args: list[Any] = []
        for i, (col, value) in enumerate(filters.items(), start=1):
            _validate_identifier(col, "filter column")
            where_clauses.append(f"{col} = ${i}")
            args.append(_resolve(value, ctx))
        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        order_sql = ""
        order_by = config.get("order_by")
        if order_by:
            _validate_identifier(order_by, "order_by")
            order_dir = (config.get("order_dir") or "asc").lower()
            if order_dir not in ("asc", "desc"):
                raise NodeExecutorError("read_table.order_dir must be 'asc' or 'desc'")
            order_sql = f" ORDER BY {order_by} {order_dir.upper()}"

        limit = int(config.get("limit") or 500)
        if limit < 1 or limit > 5000:
            raise NodeExecutorError("read_table.limit must be 1..5000")

        sql = f"SELECT {select_list} FROM {table}{where_sql}{order_sql} LIMIT {limit}"

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            records = await conn.fetch(sql, *args)
        rows = [dict(r) for r in records]
        log.info("read_table.done", table=table, count=len(rows),
                 enterprise_id=str(ctx.enterprise_id))
        return NodeResult(
            status="completed",
            output_data={"rows": rows, "row_count": len(rows), "table": table},
        )


class ReadEmailExecutor(NodeExecutor):
    """read_email — pull the next pending email from workflow_email_intake.

    Webhook / IMAP fetcher INSERTs rows into workflow_email_intake; this
    executor claims the next pending row for a queue_key + flips status to
    'consumed'. The claim is K-12 RLS-scoped + uses SELECT FOR UPDATE to
    avoid two concurrent runs grabbing the same row.

    Config:
      queue_key:     'ap_invoices' | 'support_tickets' | ...  (required)
      consume:       True  (default — flip status to 'consumed')
                      False — peek without claim (testing)
      latest_first:  False  (default = FIFO; True = LIFO)
    Output:
      found=False if no pending row.
      found=True with {email_id, sender, subject, body_text, body_html,
                       attachments, received_at, claimed: bool}
    """
    node_type_key = "read_email"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        queue_key = config.get("queue_key")
        if not isinstance(queue_key, str) or not queue_key.strip():
            raise NodeExecutorError("read_email.queue_key required (non-empty string)")
        queue_key = queue_key.strip()[:64]

        consume = bool(config.get("consume", True))
        latest_first = bool(config.get("latest_first"))
        order_dir = "DESC" if latest_first else "ASC"

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"""SELECT email_id, sender, recipients, subject,
                              body_text, body_html, attachments,
                              received_at, message_id
                       FROM workflow_email_intake
                       WHERE queue_key = $1 AND status = 'pending'
                       ORDER BY received_at {order_dir}
                       LIMIT 1
                       FOR UPDATE SKIP LOCKED""",
                    queue_key,
                )
                if row is None:
                    return NodeResult(
                        status="completed",
                        output_data={
                            "found":      False,
                            "queue_key":  queue_key,
                            "email_id":   None,
                        },
                    )
                if consume:
                    await conn.execute(
                        """UPDATE workflow_email_intake
                           SET status = 'consumed',
                               consumed_at = NOW(),
                               consumed_by_run_id = $1
                           WHERE email_id = $2""",
                        ctx.run_id, row["email_id"],
                    )

        attachments = row["attachments"]
        if isinstance(attachments, str):
            import json as _j
            try:
                attachments = _j.loads(attachments) if attachments else []
            except Exception:  # noqa: BLE001
                attachments = []

        log.info("read_email.claimed" if consume else "read_email.peeked",
                  email_id=str(row["email_id"]),
                  queue_key=queue_key,
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "found":        True,
                "queue_key":    queue_key,
                "email_id":     str(row["email_id"]),
                "message_id":   row["message_id"],
                "sender":       row["sender"],
                "recipients":   list(row["recipients"] or []),
                "subject":      row["subject"],
                "body_text":    row["body_text"] or "",
                "body_html":    row["body_html"] or "",
                "attachments":  attachments,
                "received_at":  row["received_at"].isoformat(),
                "claimed":      consume,
            },
        )


class UpdateRecordExecutor(NodeExecutor):
    """update_record — write_idempotent UPDATE on a whitelisted table.

    Config:
      table:    'tenant_interventions'  (must be in UPDATABLE_COLUMNS)
      pk_col:   'intervention_id'        (primary key column)
      pk_value: $.upstream.id            (resolved value)
      set:      {col: value, ...}        (columns in UPDATABLE_COLUMNS[table])
    Output:
      {table: str, rows_updated: int, pk_value: Any}

    K-12: RLS via acquire_for_tenant. K-17: write_idempotent — same
    pk + same values = identical row state on retry.
    """
    node_type_key = "update_record"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        table = config.get("table")
        if table not in UPDATABLE_COLUMNS:
            raise NodeExecutorError(
                f"update_record.table={table!r} not updatable. "
                f"Allowed: {sorted(UPDATABLE_COLUMNS.keys())}"
            )
        allowed = UPDATABLE_COLUMNS[table]

        pk_col = config.get("pk_col")
        if not pk_col:
            raise NodeExecutorError("update_record.pk_col required")
        _validate_identifier(pk_col, "pk_col")

        pk_value = _resolve(config.get("pk_value"), ctx)
        if pk_value is None:
            raise NodeExecutorError("update_record.pk_value resolved to None")

        set_map = config.get("set") or {}
        if not isinstance(set_map, dict) or not set_map:
            raise NodeExecutorError("update_record.set must be non-empty dict")

        set_clauses: list[str] = []
        args: list[Any] = []
        for i, (col, raw_value) in enumerate(set_map.items(), start=1):
            if col not in allowed:
                raise NodeExecutorError(
                    f"update_record.set.{col} not in allowed cols for {table}: "
                    f"{sorted(allowed)}"
                )
            _validate_identifier(col, "set column")
            set_clauses.append(f"{col} = ${i}")
            args.append(_resolve(raw_value, ctx))

        args.append(pk_value)
        sql = (
            f"UPDATE {table} SET {', '.join(set_clauses)}"
            f" WHERE {pk_col} = ${len(args)}"
        )

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            result = await conn.execute(sql, *args)
        # asyncpg returns 'UPDATE N' — extract count
        try:
            rows_updated = int(result.rsplit(" ", 1)[-1])
        except (ValueError, IndexError):
            rows_updated = 0

        log.info("update_record.done", table=table, rows_updated=rows_updated,
                 enterprise_id=str(ctx.enterprise_id))
        return NodeResult(
            status="completed",
            output_data={
                "table": table,
                "rows_updated": rows_updated,
                "pk_value": pk_value,
            },
        )
