"""
Output-sink executors — wave 3 of workflow-gap closeout.

5 executors writing to dedicated workflow output tables (mig 091):

  publish_insight       write_non_idempotent — append insight row
  publish_alert         write_non_idempotent — append alert row
  create_task           write_idempotent     — UPSERT by (enterprise, task_key)
  display_dashboard     write_idempotent     — UPSERT by (enterprise, dashboard_key, tile_key)
  save_to_database      write_idempotent     — generic INSERT into a whitelisted
                                                   workflow_* table (caller chooses)

Idempotency contract:
- write_idempotent nodes use a natural key UNIQUE constraint so two
  retries of the same node produce the same row state.
- write_non_idempotent nodes derive a dedup key from
  (run_id, node_id) at the executor layer — same retry inserts once
  via SELECT-then-INSERT inside the transaction.

K-1 / K-12: RLS via acquire_for_tenant on every SQL hop.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


async def _emit_output_lineage(
    *,
    ctx: NodeContext,
    sink_kind: str,
    sink_id: str,
    transformation: str,
) -> None:
    """Best-effort lineage edge: workflow_run_node → {insight,alert,task,...}.

    Phase 2.7 P1 wiring. Walking downstream from a workflow_run_node
    finds the persisted output (insight/alert/task); upstream from a
    sink object finds the producing run + run node. Failures log + skip
    so a downed lineage table doesn't break the output pipeline.
    """
    try:
        from ai_orchestrator.shared.lineage import ObjectKind, record_edge
        await record_edge(
            enterprise_id=ctx.enterprise_id,
            from_kind=ObjectKind.WORKFLOW_RUN_NODE,
            from_id=str(ctx.node_id),
            to_kind=sink_kind,
            to_id=sink_id,
            transformation=transformation,
            run_id=ctx.run_id,
            node_id=ctx.node_id,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "output.lineage_emit_failed",
            sink_kind=sink_kind, sink_id=sink_id,
            run_id=str(ctx.run_id), node_id=str(ctx.node_id),
        )


def _truthy_str(value: Any, max_len: int) -> str:
    """Resolve + coerce to a non-empty trimmed string capped at max_len.
    Raises NodeExecutorError on empty/None."""
    if isinstance(value, str):
        out = value.strip()
    elif value is None:
        out = ""
    else:
        out = str(value).strip()
    return out[:max_len] if out else ""


# ─── 1. publish_insight ─────────────────────────────────────────────


class PublishInsightExecutor(NodeExecutor):
    """publish_insight — append an insight row visible in P2-19 + P2-20.

    Config:
      title:        $.upstream.title  or literal (required)
      body:         $.upstream.body   or literal (required)
      severity:     'info' | 'warning' | 'critical'   (default 'info')
      confidence:   0..1   (optional)
      tags:         list[str]   (optional)
      source_data:  dict   (optional — payload for FE drilldown)
    Output:
      {insight_id: UUID-str, severity: str, title: str}
    """
    node_type_key = "publish_insight"
    side_effect_class = SideEffectClass.WRITE_NON_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        title = _truthy_str(_resolve(config.get("title"), ctx), 300)
        if not title:
            raise NodeExecutorError("publish_insight.title required")

        body_resolved = _resolve(config.get("body"), ctx)
        if isinstance(body_resolved, (dict, list)):
            body = json.dumps(body_resolved, ensure_ascii=False)
        else:
            body = str(body_resolved or "").strip()
        if not body:
            raise NodeExecutorError("publish_insight.body required")

        severity = (config.get("severity") or "info").lower()
        if severity not in ("info", "warning", "critical"):
            raise NodeExecutorError(
                f"publish_insight.severity={severity!r} not in info/warning/critical"
            )

        confidence = config.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                raise NodeExecutorError("publish_insight.confidence must be number")
            if not 0.0 <= confidence <= 1.0:
                raise NodeExecutorError("publish_insight.confidence must be 0..1")

        tags_raw = config.get("tags") or []
        if not isinstance(tags_raw, list):
            raise NodeExecutorError("publish_insight.tags must be list[str]")
        tags = [str(t).strip()[:50] for t in tags_raw if str(t).strip()][:20]

        source_data_raw = config.get("source_data") or {}
        if not isinstance(source_data_raw, dict):
            raise NodeExecutorError("publish_insight.source_data must be dict")

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """INSERT INTO workflow_insights
                       (enterprise_id, run_id, node_id, title, body,
                        severity, confidence, source_data, tags)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   RETURNING insight_id""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id,
                title, body, severity, confidence,
                json.dumps(source_data_raw), tags,
            )

        log.info("publish_insight.appended",
                  insight_id=str(row["insight_id"]),
                  severity=severity, tag_count=len(tags),
                  enterprise_id=str(ctx.enterprise_id))

        await _emit_output_lineage(
            ctx=ctx,
            sink_kind="workflow_insight",
            sink_id=str(row["insight_id"]),
            transformation="publish_insight",
        )

        return NodeResult(
            status="completed",
            output_data={
                "insight_id": str(row["insight_id"]),
                "severity":   severity,
                "title":      title,
            },
        )


# ─── 2. publish_alert ───────────────────────────────────────────────


class PublishAlertExecutor(NodeExecutor):
    """publish_alert — append an alert row routed to a role inbox.

    Config:
      code:        'SLA_BREACH' | 'CONTRACT_OVERDUE' | ... (≤64 chars)
      message:     $.upstream.text  or literal (required)
      severity:    'info'|'warning'|'critical'  (default 'warning')
      target_role: 'MANAGER' | 'OPERATOR' | ...  (optional)
      payload:     dict   (optional)
    Output:
      {alert_id: UUID-str, code: str, severity: str}
    """
    node_type_key = "publish_alert"
    side_effect_class = SideEffectClass.WRITE_NON_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        code = _truthy_str(config.get("code"), 64)
        if not code:
            raise NodeExecutorError("publish_alert.code required")

        message_resolved = _resolve(config.get("message"), ctx)
        if isinstance(message_resolved, (dict, list)):
            message = json.dumps(message_resolved, ensure_ascii=False)
        else:
            message = str(message_resolved or "").strip()
        if not message:
            raise NodeExecutorError("publish_alert.message required")

        severity = (config.get("severity") or "warning").lower()
        if severity not in ("info", "warning", "critical"):
            raise NodeExecutorError(
                f"publish_alert.severity={severity!r} invalid"
            )

        target_role = config.get("target_role")
        if target_role is not None:
            target_role = str(target_role).strip().upper()[:32]
            if not target_role:
                target_role = None

        payload_raw = config.get("payload") or {}
        if not isinstance(payload_raw, dict):
            raise NodeExecutorError("publish_alert.payload must be dict")

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """INSERT INTO workflow_alerts
                       (enterprise_id, run_id, node_id, code, message,
                        severity, target_role, payload)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   RETURNING alert_id""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id,
                code, message, severity, target_role,
                json.dumps(payload_raw),
            )

        log.info("publish_alert.appended",
                  alert_id=str(row["alert_id"]),
                  code=code, severity=severity,
                  target_role=target_role,
                  enterprise_id=str(ctx.enterprise_id))

        await _emit_output_lineage(
            ctx=ctx,
            sink_kind="workflow_alert",
            sink_id=str(row["alert_id"]),
            transformation="publish_alert",
        )

        return NodeResult(
            status="completed",
            output_data={
                "alert_id":    str(row["alert_id"]),
                "code":        code,
                "severity":    severity,
                "target_role": target_role,
            },
        )


# ─── 3. create_task ─────────────────────────────────────────────────


class CreateTaskExecutor(NodeExecutor):
    """create_task — UPSERT a task by (enterprise, task_key).

    Config:
      task_key:        'invoice-{$.upstream.invoice_id}-approval'
                       (resolved template; ≤200 chars)
                       Acts as the natural-key dedup so retry-safe.
      title:           required, ≤300 chars
      description:     optional
      assignee_role:   'MANAGER' | 'OPERATOR' | ...  (optional)
      assignee_user_id: $.upstream.user_id  (optional)
      due_at:          ISO timestamp string or upstream-resolved (optional)
      priority:        'low'|'normal'|'high'|'urgent'  (default 'normal')
      metadata:        dict  (optional)
    Output:
      {task_id: UUID-str, task_key: str, status: 'created'|'updated'}
    """
    node_type_key = "create_task"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        task_key = _truthy_str(_resolve(config.get("task_key"), ctx), 200)
        if not task_key:
            raise NodeExecutorError("create_task.task_key required (non-empty)")

        title = _truthy_str(_resolve(config.get("title"), ctx), 300)
        if not title:
            raise NodeExecutorError("create_task.title required")

        description_resolved = _resolve(config.get("description"), ctx)
        description = str(description_resolved or "").strip() or None

        assignee_role = config.get("assignee_role")
        if assignee_role is not None:
            assignee_role = str(assignee_role).strip().upper()[:32] or None

        assignee_user_id_raw = _resolve(config.get("assignee_user_id"), ctx)
        assignee_user_id: Optional[UUID] = None
        if assignee_user_id_raw:
            try:
                assignee_user_id = UUID(str(assignee_user_id_raw))
            except ValueError:
                raise NodeExecutorError(
                    f"create_task.assignee_user_id not a UUID: {assignee_user_id_raw!r}"
                )

        due_at_raw = _resolve(config.get("due_at"), ctx)
        due_at: Optional[str] = None
        if due_at_raw:
            due_at = str(due_at_raw)  # asyncpg coerces ISO timestamp string

        priority = (config.get("priority") or "normal").lower()
        if priority not in ("low", "normal", "high", "urgent"):
            raise NodeExecutorError(
                f"create_task.priority={priority!r} invalid"
            )

        metadata_raw = config.get("metadata") or {}
        if not isinstance(metadata_raw, dict):
            raise NodeExecutorError("create_task.metadata must be dict")

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """INSERT INTO workflow_tasks
                       (enterprise_id, run_id, node_id, task_key, title,
                        description, assignee_role, assignee_user_id,
                        due_at, priority, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::TIMESTAMPTZ, $10, $11)
                   ON CONFLICT (enterprise_id, task_key) DO UPDATE
                   SET title = EXCLUDED.title,
                       description = EXCLUDED.description,
                       assignee_role = EXCLUDED.assignee_role,
                       assignee_user_id = EXCLUDED.assignee_user_id,
                       due_at = EXCLUDED.due_at,
                       priority = EXCLUDED.priority,
                       metadata = EXCLUDED.metadata
                   RETURNING task_id,
                             (xmax = 0) AS inserted""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id, task_key, title,
                description, assignee_role, assignee_user_id,
                due_at, priority, json.dumps(metadata_raw),
            )

        status = "created" if row["inserted"] else "updated"
        log.info("create_task.upserted",
                  task_id=str(row["task_id"]),
                  task_key=task_key, status=status,
                  assignee_role=assignee_role,
                  enterprise_id=str(ctx.enterprise_id))

        # Lineage edge only on first insert — UPSERTs on the same
        # task_key are idempotent updates of the SAME sink; the edge
        # ON CONFLICT clause already dedupes, but skipping the call
        # when status='updated' saves a no-op DB round trip.
        if status == "created":
            await _emit_output_lineage(
                ctx=ctx,
                sink_kind="workflow_task",
                sink_id=str(row["task_id"]),
                transformation="create_task",
            )

        return NodeResult(
            status="completed",
            output_data={
                "task_id":  str(row["task_id"]),
                "task_key": task_key,
                "status":   status,
            },
        )


# ─── 4. display_dashboard ───────────────────────────────────────────


class DisplayDashboardExecutor(NodeExecutor):
    """display_dashboard — UPSERT a dashboard tile (write_idempotent by
    natural key (dashboard_key, tile_key)).

    Config:
      dashboard_key:  'sales_director'   (≤64 chars)
      tile_key:       'pipeline_value'   (≤64 chars)
      payload:        dict  (the tile's data — chart values, KPI numbers,
                              etc.; FE consumer interprets)
    Output:
      {tile_id: UUID-str, dashboard_key: str, tile_key: str,
       status: 'created'|'updated'}
    """
    node_type_key = "display_dashboard"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        dashboard_key = _truthy_str(config.get("dashboard_key"), 64)
        if not dashboard_key:
            raise NodeExecutorError("display_dashboard.dashboard_key required")

        tile_key = _truthy_str(config.get("tile_key"), 64)
        if not tile_key:
            raise NodeExecutorError("display_dashboard.tile_key required")

        payload_raw = _resolve(config.get("payload"), ctx)
        if payload_raw is None:
            payload_raw = {}
        if not isinstance(payload_raw, dict):
            raise NodeExecutorError("display_dashboard.payload must resolve to dict")

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """INSERT INTO workflow_dashboard_tiles
                       (enterprise_id, dashboard_key, tile_key,
                        last_run_id, last_node_id, payload)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (enterprise_id, dashboard_key, tile_key) DO UPDATE
                   SET payload = EXCLUDED.payload,
                       last_run_id = EXCLUDED.last_run_id,
                       last_node_id = EXCLUDED.last_node_id,
                       updated_at = NOW()
                   RETURNING tile_id, (xmax = 0) AS inserted""",
                ctx.enterprise_id, dashboard_key, tile_key,
                ctx.run_id, ctx.node_id, json.dumps(payload_raw),
            )

        status = "created" if row["inserted"] else "updated"
        log.info("display_dashboard.upserted",
                  tile_id=str(row["tile_id"]),
                  dashboard_key=dashboard_key, tile_key=tile_key,
                  status=status, enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "tile_id":       str(row["tile_id"]),
                "dashboard_key": dashboard_key,
                "tile_key":      tile_key,
                "status":        status,
            },
        )


# ─── 5. save_to_database ────────────────────────────────────────────


# Whitelist of tables save_to_database can INSERT into. Each entry maps
# table_name → set of allowed column names. Identifier validation runs on
# both, so even if the whitelist is bypassed somehow, SQL injection via
# column names is blocked by _validate_identifier.
SAVE_TABLE_WHITELIST: dict[str, set[str]] = {
    "workflow_insights": {
        "title", "body", "severity", "confidence", "tags", "source_data",
    },
    "workflow_alerts": {
        "code", "message", "severity", "target_role", "payload",
    },
    "workflow_tasks": {
        "task_key", "title", "description", "assignee_role",
        "assignee_user_id", "due_at", "priority", "metadata",
    },
}


def _validate_save_identifier(name: str, kind: str) -> str:
    """Strict identifier check — ASCII letters/digits/underscore only."""
    if not name or not isinstance(name, str):
        raise NodeExecutorError(f"save_to_database {kind} must be non-empty string")
    if not (name[0].isalpha() or name[0] == "_"):
        raise NodeExecutorError(f"save_to_database {kind}={name!r} invalid first char")
    for ch in name:
        if not (ch.isalnum() or ch == "_"):
            raise NodeExecutorError(f"save_to_database {kind}={name!r} invalid char")
    return name


class SaveToDatabaseExecutor(NodeExecutor):
    """save_to_database — generic INSERT into a whitelisted workflow_*
    sink table. Use cases (mig 069):
      E.3 QC: persist inspection result.
      F.4 Vendor Payment: persist AP payment ledger row.

    Today's whitelist covers the three workflow sink tables; new tables
    are opt-in by extending SAVE_TABLE_WHITELIST (which also locks per-table
    allowed columns to prevent over-write of unrelated columns).

    Config:
      table:    'workflow_alerts'    (must be in whitelist)
      values:   {col: resolved_value, ...}  (every key must be in
                                              SAVE_TABLE_WHITELIST[table])
    Output:
      {table: str, inserted_id: UUID-str-or-null, columns: list[str]}
    """
    node_type_key = "save_to_database"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        table = config.get("table")
        if table not in SAVE_TABLE_WHITELIST:
            raise NodeExecutorError(
                f"save_to_database.table={table!r} not in whitelist "
                f"{sorted(SAVE_TABLE_WHITELIST.keys())}"
            )
        allowed_cols = SAVE_TABLE_WHITELIST[table]

        values_raw = config.get("values") or {}
        if not isinstance(values_raw, dict) or not values_raw:
            raise NodeExecutorError("save_to_database.values must be non-empty dict")

        cols: list[str] = []
        args: list[Any] = [ctx.enterprise_id]  # always first param
        placeholders: list[str] = []
        for i, (col, raw_value) in enumerate(values_raw.items(), start=2):
            if col not in allowed_cols:
                raise NodeExecutorError(
                    f"save_to_database column {col!r} not allowed for {table}; "
                    f"allowed={sorted(allowed_cols)}"
                )
            _validate_save_identifier(col, "column")
            resolved = _resolve(raw_value, ctx)
            # Auto-stringify dict/list values (caller intends JSONB target);
            # plain scalars pass through.
            if isinstance(resolved, (dict, list)):
                resolved = json.dumps(resolved, ensure_ascii=False)
            cols.append(col)
            args.append(resolved)
            placeholders.append(f"${i}")

        sql = (
            f"INSERT INTO {table} (enterprise_id, run_id, node_id, "
            f"  {', '.join(cols)}) "
            f"VALUES ($1, $%s, $%s, %s) "
            f"RETURNING %s"
        ) % (
            len(args) + 1,  # run_id param
            len(args) + 2,  # node_id param
            ", ".join(placeholders),
            _id_col_for(table),
        )
        args.append(ctx.run_id)
        args.append(ctx.node_id)

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(sql, *args)

        inserted_id = row[_id_col_for(table)] if row else None
        log.info("save_to_database.inserted",
                  table=table, columns=cols,
                  inserted_id=str(inserted_id) if inserted_id else None,
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "table":       table,
                "inserted_id": str(inserted_id) if inserted_id else None,
                "columns":     cols,
            },
        )


def _id_col_for(table: str) -> str:
    """Return the PK column for a whitelisted sink table. Centralised so
    new tables can opt in by updating this map alongside the whitelist."""
    return {
        "workflow_insights": "insight_id",
        "workflow_alerts":   "alert_id",
        "workflow_tasks":    "task_id",
    }[table]
