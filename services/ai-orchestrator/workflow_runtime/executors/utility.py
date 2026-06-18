"""
Utility executors — wave 4 of workflow-gap closeout.

8 nodes that round out the remaining 25/25 templates:
  scheduled_trigger   pure marker (Temporal Schedule wires actual cron)
  filter              pure list filter
  transform           pure list map/project
  split               pure list split (by midpoint or predicate)
  join                pure list join (inner / left)
  log                 pure-ish structured log emission
  send_chat_message   external — INSERT into workflow_chat_outbox
  read_webhook        read_only — claim pending row from
                                   workflow_webhook_intake

side_effect_class per K-17:
  pure         filter, transform, split, join, log, scheduled_trigger
  external     send_chat_message (queue + bot adapter dispatches)
  read_only    read_webhook
"""
from __future__ import annotations

import json
import operator
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import SKIPPED, _eval_condition, _resolve, require_rows

log = structlog.get_logger()


# ─── 1. scheduled_trigger ──────────────────────────────────────────


class ScheduledTriggerExecutor(NodeExecutor):
    """scheduled_trigger — workflow entry-point marker.

    The actual cron is configured externally (Temporal Schedule per runbook
    §3c). When a run STARTS from a schedule, this node is the first one
    that executes — it records the schedule_spec + triggered_at into the
    run's prior_outputs so downstream nodes can branch on the schedule
    metadata.

    Config:
      cron:           '0 9 * * 1-5'   (informational only — not enforced
                                        here; documents the schedule)
      schedule_id:    'contract-renewal-daily'   (informational)
      timezone:       'Asia/Ho_Chi_Minh'   (default 'UTC')
    Output:
      {triggered_at: ISO-ts, cron: str, schedule_id: str, timezone: str,
       trigger_source: 'manual'|'schedule'|...}
    """
    node_type_key = "scheduled_trigger"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        cron = config.get("cron")
        if cron is not None and not isinstance(cron, str):
            raise NodeExecutorError("scheduled_trigger.cron must be string if set")

        schedule_id = config.get("schedule_id")
        if schedule_id is not None and not isinstance(schedule_id, str):
            raise NodeExecutorError("scheduled_trigger.schedule_id must be string if set")

        tz = config.get("timezone") or "UTC"
        triggered_at = datetime.now(timezone.utc).isoformat()

        log.info("scheduled_trigger.fired",
                  schedule_id=schedule_id, cron=cron,
                  enterprise_id=str(ctx.enterprise_id),
                  run_id=str(ctx.run_id))

        return NodeResult(
            status="completed",
            output_data={
                "triggered_at":   triggered_at,
                "cron":           cron,
                "schedule_id":    schedule_id,
                "timezone":       tz,
                "trigger_source": "schedule",
            },
        )


# ─── 2. filter ──────────────────────────────────────────────────────


class FilterExecutor(NodeExecutor):
    """filter — pure list filter by predicate.

    Config:
      rows:      $.upstream.rows  (list of dicts)
      condition: {left, op, right} or compound {and/or: [...]}
                 (reuses pure._eval_condition; supports == != > >= < <= in notin
                  + compound and/or)
      negate:    False   (default — drop non-matching; True = drop matching)
      limit:     0       (0 = no limit)
    Output:
      {rows: list[dict], dropped: int, total: int}

    Each row becomes ctx.prior_outputs['__row'] during predicate eval so
    the condition can reference $._row.<column>.
    """
    node_type_key = "filter"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = require_rows(config.get("rows"), ctx, "filter.rows")

        condition = config.get("condition")
        if not isinstance(condition, dict):
            raise NodeExecutorError("filter.condition required (dict)")

        negate = bool(config.get("negate"))
        limit = int(config.get("limit") or 0)
        if limit < 0 or limit > 100000:
            raise NodeExecutorError("filter.limit must be 0..100000")

        kept: list[Any] = []
        dropped = 0
        for row_idx, row in enumerate(rows):
            # Build a per-row context shadowing prior_outputs with '_row'.
            row_dict = row if isinstance(row, dict) else {"value": row}
            row_ctx = NodeContext(
                enterprise_id=ctx.enterprise_id,
                workspace_id=ctx.workspace_id,
                workflow_id=ctx.workflow_id,
                run_id=ctx.run_id,
                node_id=ctx.node_id,
                user_id=ctx.user_id,
                input_data=ctx.input_data,
                prior_outputs={**ctx.prior_outputs, "_row": row_dict},
                idempotency_key=ctx.idempotency_key,
            )
            try:
                passed = _eval_condition(condition, row_ctx)
            except NodeExecutorError as e:
                # Bad predicate at row level — drop + count, but LOG which row +
                # why (a typo'd op would otherwise silently discard every row).
                dropped += 1
                log.warning("filter.row_predicate_failed",
                            row_index=row_idx, error=str(e),
                            run_id=str(ctx.run_id))
                continue
            keep = (not passed) if negate else passed
            if keep:
                kept.append(row)
                if limit and len(kept) >= limit:
                    break
            else:
                dropped += 1

        return NodeResult(
            status="completed",
            output_data={
                "rows":     kept,
                "dropped":  dropped,
                "total":    len(rows),
            },
        )


# ─── 3. transform ──────────────────────────────────────────────────


class TransformExecutor(NodeExecutor):
    """transform — pure list project/rename/derive.

    Config:
      rows:    $.upstream.rows  (list of dicts)
      output_columns: [
        {name: 'final_amount',  from: 'amount'},                # rename
        {name: 'is_paid',       from: 'status', map: {'PAID': true, '*': false}},
        {name: 'currency',      literal: 'VND'},                # constant
        {name: 'qty_double',    from: 'qty',    fn: 'mul', arg: 2},
        {name: 'name_upper',    from: 'name',   fn: 'upper'},
      ]
    Output:
      {rows: list[dict], total: int}
    """
    node_type_key = "transform"
    side_effect_class = SideEffectClass.PURE

    @staticmethod
    def _apply_op(value: Any, spec: dict[str, Any]) -> Any:
        """Apply optional fn/map/arg to a sourced value."""
        # mapping: {value: replacement, '*': default}
        mapping = spec.get("map")
        if isinstance(mapping, dict):
            if value in mapping:
                return mapping[value]
            if "*" in mapping:
                return mapping["*"]
            return value

        fn = spec.get("fn")
        if fn:
            try:
                if fn == "upper":
                    return str(value).upper()
                if fn == "lower":
                    return str(value).lower()
                if fn == "len":
                    return len(value) if hasattr(value, "__len__") else 0
                arg = spec.get("arg")
                if fn == "mul" and isinstance(value, (int, float)):
                    return value * float(arg)
                if fn == "add" and isinstance(value, (int, float)):
                    return value + float(arg)
                if fn == "div" and isinstance(value, (int, float)) and float(arg) != 0:
                    return value / float(arg)
                if fn == "round" and isinstance(value, (int, float)):
                    return round(value, int(arg or 0))
            except (TypeError, ValueError):
                return None
        return value

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = require_rows(config.get("rows"), ctx, "transform.rows")

        cols = config.get("output_columns")
        if not isinstance(cols, list) or not cols:
            raise NodeExecutorError("transform.output_columns required (non-empty list)")

        out_rows: list[dict[str, Any]] = []
        for row in rows:
            row_dict = row if isinstance(row, dict) else {"value": row}
            new_row: dict[str, Any] = {}
            for col_spec in cols:
                if not isinstance(col_spec, dict):
                    continue
                name = col_spec.get("name")
                if not name or not isinstance(name, str):
                    raise NodeExecutorError("transform.output_columns[].name required")
                # literal takes priority
                if "literal" in col_spec:
                    new_row[name] = col_spec["literal"]
                    continue
                src = col_spec.get("from")
                if not src or not isinstance(src, str):
                    new_row[name] = None
                    continue
                raw_value = row_dict.get(src)
                new_row[name] = self._apply_op(raw_value, col_spec)
            out_rows.append(new_row)

        return NodeResult(
            status="completed",
            output_data={"rows": out_rows, "total": len(out_rows)},
        )


# ─── 4. split ──────────────────────────────────────────────────────


class SplitExecutor(NodeExecutor):
    """split — pure list split into 2 buckets.

    Config:
      rows:       $.upstream.rows
      mode:       'half' | 'predicate' | 'fraction'
      condition:  (when mode='predicate') — reused from filter logic
      fraction:   (when mode='fraction') — 0.5 = first half, 0.7 = first 70%
      seed:       (optional — when mode='half', shuffle deterministically)
    Output:
      {first: list, second: list, mode: str, first_count: int, second_count: int}
    """
    node_type_key = "split"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = require_rows(config.get("rows"), ctx, "split.rows")

        mode = (config.get("mode") or "half").lower()
        if mode not in ("half", "predicate", "fraction"):
            raise NodeExecutorError(f"split.mode={mode!r} invalid")

        if mode == "predicate":
            condition = config.get("condition")
            if not isinstance(condition, dict):
                raise NodeExecutorError("split.condition required for mode=predicate")
            first: list[Any] = []
            second: list[Any] = []
            for row in rows:
                row_dict = row if isinstance(row, dict) else {"value": row}
                row_ctx = NodeContext(
                    enterprise_id=ctx.enterprise_id,
                    workspace_id=ctx.workspace_id,
                    workflow_id=ctx.workflow_id,
                    run_id=ctx.run_id,
                    node_id=ctx.node_id,
                    user_id=ctx.user_id,
                    input_data=ctx.input_data,
                    prior_outputs={**ctx.prior_outputs, "_row": row_dict},
                    idempotency_key=ctx.idempotency_key,
                )
                try:
                    matched = _eval_condition(condition, row_ctx)
                except NodeExecutorError:
                    matched = False
                (first if matched else second).append(row)
        elif mode == "fraction":
            try:
                frac = float(config.get("fraction"))
            except (TypeError, ValueError):
                raise NodeExecutorError("split.fraction must be number 0..1")
            if not 0.0 <= frac <= 1.0:
                raise NodeExecutorError("split.fraction must be 0..1")
            cut = int(round(len(rows) * frac))
            first = rows[:cut]
            second = rows[cut:]
        else:  # half
            seed = config.get("seed")
            if seed is not None:
                import random
                rng = random.Random(int(seed))
                # Deterministic shuffle
                shuffled = list(rows)
                rng.shuffle(shuffled)
            else:
                shuffled = rows
            cut = len(shuffled) // 2
            first = shuffled[:cut]
            second = shuffled[cut:]

        return NodeResult(
            status="completed",
            output_data={
                "mode":          mode,
                "first":         first,
                "second":        second,
                "first_count":   len(first),
                "second_count": len(second),
            },
        )


# ─── 5. join ───────────────────────────────────────────────────────


class JoinExecutor(NodeExecutor):
    """join — pure list join.

    Config:
      left_rows:    $.upstream_a.rows
      right_rows:   $.upstream_b.rows
      left_key:     'invoice_id'    (column in left)
      right_key:    'invoice_id'    (column in right; defaults to left_key)
      mode:         'inner' | 'left'   (default 'inner')
      prefix_right: '_'  (column prefix to avoid collision; default '')
    Output:
      {rows: list[dict], left_count: int, right_count: int, joined_count: int}
    """
    node_type_key = "join"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        left = require_rows(config.get("left_rows"), ctx, "join.left_rows")
        right = require_rows(config.get("right_rows"), ctx, "join.right_rows")

        left_key = config.get("left_key")
        if not left_key or not isinstance(left_key, str):
            raise NodeExecutorError("join.left_key required (string)")
        right_key = config.get("right_key") or left_key
        if not isinstance(right_key, str):
            raise NodeExecutorError("join.right_key must be string if set")

        mode = (config.get("mode") or "inner").lower()
        if mode not in ("inner", "left"):
            raise NodeExecutorError(f"join.mode={mode!r} invalid (inner|left)")

        prefix_right = config.get("prefix_right") or ""
        if not isinstance(prefix_right, str):
            raise NodeExecutorError("join.prefix_right must be string")

        # Index right side by key for O(L+R) lookup.
        right_index: dict[Any, list[dict]] = {}
        for r in right:
            if not isinstance(r, dict):
                continue
            k = r.get(right_key)
            right_index.setdefault(k, []).append(r)

        out_rows: list[dict[str, Any]] = []
        for lrow in left:
            if not isinstance(lrow, dict):
                continue
            lkey = lrow.get(left_key)
            matches = right_index.get(lkey, [])
            if not matches:
                if mode == "left":
                    out_rows.append(dict(lrow))
                # inner mode drops unmatched
                continue
            for rrow in matches:
                merged = dict(lrow)
                for rcol, rval in rrow.items():
                    if rcol == right_key:
                        continue
                    merged[prefix_right + rcol if prefix_right else rcol] = rval
                out_rows.append(merged)

        return NodeResult(
            status="completed",
            output_data={
                "rows":          out_rows,
                "left_count":    len(left),
                "right_count":   len(right),
                "joined_count":  len(out_rows),
                "mode":          mode,
            },
        )


# ─── 6. log ────────────────────────────────────────────────────────


class LogExecutor(NodeExecutor):
    """log — emit a structured log row.

    Pure-ish — uses structlog (no DB write). Side-effect class is pure
    because retry is free + idempotent (logs are append-only by nature
    in the log aggregator's storage).

    Config:
      level:    'debug'|'info'|'warning'|'error'   (default 'info')
      event:    'workflow.audit.x'                  (logger event name)
      payload:  dict   (key/values logged as structlog kwargs)
    Output:
      {logged: True, level: str, event: str}
    """
    node_type_key = "log"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        level = (config.get("level") or "info").lower()
        if level not in ("debug", "info", "warning", "error"):
            raise NodeExecutorError(
                f"log.level={level!r} not in debug/info/warning/error"
            )

        event = config.get("event")
        if not event or not isinstance(event, str):
            raise NodeExecutorError("log.event required (non-empty string)")
        event = event.strip()[:200]

        payload_raw = config.get("payload") or {}
        if not isinstance(payload_raw, dict):
            raise NodeExecutorError("log.payload must be dict")
        # Resolve any $.refs in payload values; coerce non-primitive values
        resolved: dict[str, Any] = {}
        for k, v in payload_raw.items():
            val = _resolve(v, ctx)
            if isinstance(val, (dict, list)):
                try:
                    val = json.dumps(val, ensure_ascii=False)[:1000]
                except Exception:  # noqa: BLE001
                    val = str(val)[:1000]
            resolved[str(k)[:100]] = val

        fn = getattr(log, level, log.info)
        fn(event,
           enterprise_id=str(ctx.enterprise_id),
           run_id=str(ctx.run_id),
           node_id=str(ctx.node_id),
           **resolved)

        return NodeResult(
            status="completed",
            output_data={
                "logged": True,
                "level":  level,
                "event":  event,
            },
        )


# ─── 7. send_chat_message ─────────────────────────────────────────


class SendChatMessageExecutor(NodeExecutor):
    """send_chat_message — enqueue chat message in workflow_chat_outbox.

    Bot adapter (Slack / Telegram / Zalo / Teams) reads pending rows +
    dispatches. v0 ships the queue; adapter implementation lives in
    notification-service or a dedicated bot worker (out of scope here).

    Config:
      channel:  'slack' | 'telegram' | 'zalo' | 'teams' | 'generic'
      target:   '#sales-alerts'   or  '@manager-an'  or  'group_id_xxx'
      message:  $.upstream.body  or literal (required, ≤4000 chars)
      metadata: {thread_id, mentions: [...], ...}   (optional)
    Output:
      {outbox_id: UUID-str, channel: str, target: str, queued: bool,
       dedup_hit: bool}

    K-13 dedup: source_ref = "wfchat:{run}:{node}" so retries hit the
    UNIQUE constraint + we return the existing outbox row.
    """
    node_type_key = "send_chat_message"
    side_effect_class = SideEffectClass.EXTERNAL

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        channel = (config.get("channel") or "").lower().strip()
        if channel not in ("slack", "telegram", "zalo", "teams", "generic"):
            raise NodeExecutorError(
                f"send_chat_message.channel={channel!r} invalid"
            )

        target = _resolve(config.get("target"), ctx)
        if not isinstance(target, str) or not target.strip():
            raise NodeExecutorError("send_chat_message.target required (non-empty string)")
        target = target.strip()[:320]

        message_resolved = _resolve(config.get("message"), ctx)
        if isinstance(message_resolved, (dict, list)):
            message = json.dumps(message_resolved, ensure_ascii=False)
        else:
            message = str(message_resolved or "").strip()
        if not message:
            raise NodeExecutorError("send_chat_message.message required")
        if len(message) > 4000:
            raise NodeExecutorError("send_chat_message.message > 4000 chars")

        metadata_raw = config.get("metadata") or {}
        if not isinstance(metadata_raw, dict):
            raise NodeExecutorError("send_chat_message.metadata must be dict")

        source_ref = ctx.idempotency_key or f"wfchat:{ctx.run_id}:{ctx.node_id}"

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            existing = await conn.fetchrow(
                "SELECT outbox_id FROM workflow_chat_outbox "
                "WHERE enterprise_id = $1 AND source_ref = $2 LIMIT 1",
                ctx.enterprise_id, source_ref,
            )
            if existing:
                log.info("send_chat_message.dedup_hit",
                          source_ref=source_ref,
                          enterprise_id=str(ctx.enterprise_id))
                return NodeResult(
                    status="completed",
                    output_data={
                        "outbox_id":  str(existing["outbox_id"]),
                        "channel":    channel,
                        "target":     target,
                        "queued":     True,
                        "dedup_hit":  True,
                    },
                )
            row = await conn.fetchrow(
                """INSERT INTO workflow_chat_outbox
                       (enterprise_id, run_id, node_id, channel, target,
                        message, metadata, source_ref)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   RETURNING outbox_id""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id,
                channel, target, message,
                json.dumps(metadata_raw), source_ref,
            )

        log.info("send_chat_message.queued",
                  outbox_id=str(row["outbox_id"]),
                  channel=channel, target=target,
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "outbox_id":  str(row["outbox_id"]),
                "channel":    channel,
                "target":     target,
                "queued":     True,
                "dedup_hit":  False,
            },
        )


# ─── 8. read_webhook ──────────────────────────────────────────────


class ReadWebhookExecutor(NodeExecutor):
    """read_webhook — claim the next pending webhook event from
    workflow_webhook_intake. Webhook receiver POSTs into the table; this
    executor pulls + flips status='consumed'. Same pattern as read_email.

    Config:
      queue_key:     'stripe_events' | 'zapier_lead_form' | ...
      consume:       True (default)
      latest_first:  False (FIFO)
    Output:
      found=False if no pending row.
      found=True with {webhook_id, source, external_event_id, headers,
                       payload, received_at, claimed}
    """
    node_type_key = "read_webhook"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        queue_key = config.get("queue_key")
        if not isinstance(queue_key, str) or not queue_key.strip():
            raise NodeExecutorError("read_webhook.queue_key required (non-empty string)")
        queue_key = queue_key.strip()[:64]

        consume = bool(config.get("consume", True))
        latest_first = bool(config.get("latest_first"))
        order_dir = "DESC" if latest_first else "ASC"

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    f"""SELECT webhook_id, source, external_event_id,
                              headers, payload, received_at
                       FROM workflow_webhook_intake
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
                            "webhook_id": None,
                        },
                    )
                if consume:
                    await conn.execute(
                        """UPDATE workflow_webhook_intake
                           SET status = 'consumed',
                               consumed_at = NOW(),
                               consumed_by_run_id = $1
                           WHERE webhook_id = $2""",
                        ctx.run_id, row["webhook_id"],
                    )

        def _coerce_jsonb(val: Any) -> Any:
            if isinstance(val, str):
                try:
                    return json.loads(val) if val else {}
                except Exception:  # noqa: BLE001
                    return {}
            return val or {}

        log.info("read_webhook.claimed" if consume else "read_webhook.peeked",
                  webhook_id=str(row["webhook_id"]),
                  queue_key=queue_key, source=row["source"],
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "found":              True,
                "queue_key":          queue_key,
                "webhook_id":         str(row["webhook_id"]),
                "source":             row["source"],
                "external_event_id":  row["external_event_id"],
                "headers":            _coerce_jsonb(row["headers"]),
                "payload":            _coerce_jsonb(row["payload"]),
                "received_at":        row["received_at"].isoformat(),
                "claimed":            consume,
            },
        )
