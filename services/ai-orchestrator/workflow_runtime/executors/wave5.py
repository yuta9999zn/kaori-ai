"""
Wave-5 executors — fills the last 11 unregistered catalog keys so
ai-orchestrator covers all 45 mig-068 node types (100%).

11 executors:
  sort                 pure        — list sort by column + direction
  merge                pure        — concat / interleave N lists
  deduplicate          pure        — distinct rows by composite keys
  enrich               read_only   — left-join with a master lookup table
  wait_for_condition   read_only   — poll a SELECT until match or timeout
  read_api             read_only   — generic HTTP GET (mirror of call_api)
  read_calendar        read_only   — claim row from workflow_calendar_intake
  read_chat            read_only   — claim row from workflow_chat_intake
  read_file_upload     read_only   — lookup bronze_files by file_id
  send_sms             external    — INSERT chat_outbox channel='sms'
  export_file          write_idempotent — INSERT workflow_export_files

K-1/K-12 RLS enforced via acquire_for_tenant on every DB hop.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from typing import Any, Optional
from uuid import UUID

import httpx
import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import SKIPPED, _eval_condition, _resolve, require_rows
from .data import _validate_identifier, TABLE_WHITELIST

log = structlog.get_logger()


def _validate_ident_local(name: str, kind: str) -> str:
    """Lightweight reimplementation so wave5 doesn't reach across
    visibility boundaries; same rule as data._validate_identifier."""
    if not name or not isinstance(name, str):
        raise NodeExecutorError(f"{kind} must be non-empty string")
    if not (name[0].isalpha() or name[0] == "_"):
        raise NodeExecutorError(f"{kind}={name!r} invalid first char")
    for ch in name:
        if not (ch.isalnum() or ch == "_"):
            raise NodeExecutorError(f"{kind}={name!r} invalid char")
    return name


# ═════════════════════════════════════════════════════════════════════
# Pure executors
# ═════════════════════════════════════════════════════════════════════


class SortExecutor(NodeExecutor):
    """sort — pure list sort by column.

    Config:
      rows:      $.upstream.rows
      by:        'amount' | ['priority', 'created_at']   (column or list)
      direction: 'asc' | 'desc'  (default 'asc'; applies to all keys)
      nulls:     'first' | 'last'  (default 'last')
    Output:
      {rows: list[dict], by: list[str], total: int}
    """
    node_type_key = "sort"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = require_rows(config.get("rows"), ctx, "sort.rows")

        by_raw = config.get("by")
        if isinstance(by_raw, str):
            by_cols = [by_raw]
        elif isinstance(by_raw, list):
            by_cols = [str(c) for c in by_raw if str(c).strip()]
        else:
            raise NodeExecutorError("sort.by required (string or list[string])")
        if not by_cols:
            raise NodeExecutorError("sort.by must be non-empty")

        direction = (config.get("direction") or "asc").lower()
        if direction not in ("asc", "desc"):
            raise NodeExecutorError("sort.direction must be 'asc' or 'desc'")
        reverse = direction == "desc"

        nulls = (config.get("nulls") or "last").lower()
        if nulls not in ("first", "last"):
            raise NodeExecutorError("sort.nulls must be 'first' or 'last'")
        nulls_first = nulls == "first"

        def _key(row: Any) -> tuple:
            if not isinstance(row, dict):
                return (1,) * len(by_cols) * 2 if nulls_first else (0,) * 0
            parts: list[Any] = []
            for col in by_cols:
                v = row.get(col)
                # Pack (is_null_sort_bucket, value); coerce to str for
                # cross-type safety.
                is_null = v is None
                bucket = 0 if (is_null and nulls_first) else (1 if is_null else (1 if not nulls_first else 0))
                # When reverse: invert string sentinel so nulls land correctly
                parts.append((bucket if not reverse else (1 - bucket), str(v) if v is not None else ""))
            return tuple(parts)

        try:
            sorted_rows = sorted(rows, key=_key, reverse=reverse)
        except TypeError:
            # Fallback: coerce all to str on TypeError
            sorted_rows = sorted(
                rows,
                key=lambda r: tuple(str(r.get(c, "")) if isinstance(r, dict) else "" for c in by_cols),
                reverse=reverse,
            )

        return NodeResult(
            status="completed",
            output_data={
                "rows":  sorted_rows,
                "by":    by_cols,
                "total": len(sorted_rows),
            },
        )


class MergeExecutor(NodeExecutor):
    """merge — pure concat / interleave of N lists.

    Config:
      inputs:       [$.a.rows, $.b.rows, ...]   (list of list refs/literals)
      strategy:     'concat' | 'interleave'    (default 'concat')
      dedupe_keys:  ['id']    (optional — drop duplicates by key tuple)
    Output:
      {rows: list, total: int, strategy: str}
    """
    node_type_key = "merge"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        inputs_raw = config.get("inputs")
        if not isinstance(inputs_raw, list) or not inputs_raw:
            raise NodeExecutorError("merge.inputs required (non-empty list)")

        sources: list[list[Any]] = []
        for inp in inputs_raw:
            resolved = _resolve(inp, ctx)
            if resolved is SKIPPED:
                raise NodeExecutorError(
                    "merge.inputs entry reads from a skipped upstream node (dead branch)")
            if resolved is None:
                resolved = []
            if not isinstance(resolved, list):
                raise NodeExecutorError("merge.inputs entry must resolve to list")
            sources.append(resolved)

        strategy = (config.get("strategy") or "concat").lower()
        if strategy not in ("concat", "interleave"):
            raise NodeExecutorError("merge.strategy must be 'concat' or 'interleave'")

        if strategy == "concat":
            combined: list[Any] = []
            for src in sources:
                combined.extend(src)
        else:  # interleave
            combined = []
            max_len = max((len(s) for s in sources), default=0)
            for i in range(max_len):
                for src in sources:
                    if i < len(src):
                        combined.append(src[i])

        # Dedup
        dedupe_keys = config.get("dedupe_keys")
        if dedupe_keys:
            if not isinstance(dedupe_keys, list):
                raise NodeExecutorError("merge.dedupe_keys must be list[str]")
            seen: set[tuple] = set()
            out: list[Any] = []
            for row in combined:
                if not isinstance(row, dict):
                    out.append(row)
                    continue
                key = tuple(row.get(k) for k in dedupe_keys)
                if key in seen:
                    continue
                seen.add(key)
                out.append(row)
            combined = out

        return NodeResult(
            status="completed",
            output_data={
                "rows":     combined,
                "total":    len(combined),
                "strategy": strategy,
                "source_count": len(sources),
            },
        )


class DeduplicateExecutor(NodeExecutor):
    """deduplicate — pure distinct over caller-provided rows.

    Generic version of reasoning.record_dedup (which operates on
    ExtractedRow). This works on plain dicts.

    Config:
      rows:        $.upstream.rows
      keys:        ['email', 'phone']    (composite key columns)
      keep:        'first' | 'last'      (default 'first')
    Output:
      {rows: list, dropped: int, total_in: int}
    """
    node_type_key = "deduplicate"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = require_rows(config.get("rows"), ctx, "deduplicate.rows")

        keys = config.get("keys")
        if not isinstance(keys, list) or not keys:
            raise NodeExecutorError("deduplicate.keys required (non-empty list)")
        keys = [str(k) for k in keys if str(k).strip()]
        if not keys:
            raise NodeExecutorError("deduplicate.keys all empty after normalisation")

        keep = (config.get("keep") or "first").lower()
        if keep not in ("first", "last"):
            raise NodeExecutorError("deduplicate.keep must be 'first' or 'last'")

        seen: dict[tuple, int] = {}
        if keep == "first":
            kept: list[Any] = []
            for row in rows:
                if not isinstance(row, dict):
                    kept.append(row)
                    continue
                key = tuple(row.get(k) for k in keys)
                if key in seen:
                    continue
                seen[key] = len(kept)
                kept.append(row)
        else:  # keep last
            # Iterate, overwriting position in seen index; rebuild from seen.
            indexed: dict[tuple, Any] = {}
            order: list[tuple] = []
            for row in rows:
                if not isinstance(row, dict):
                    # Non-dict rows: keep all, separate bucket
                    indexed[(id(row),)] = row
                    order.append((id(row),))
                    continue
                key = tuple(row.get(k) for k in keys)
                if key not in indexed:
                    order.append(key)
                indexed[key] = row
            kept = [indexed[k] for k in order]

        return NodeResult(
            status="completed",
            output_data={
                "rows":     kept,
                "total_in": len(rows),
                "dropped":  len(rows) - len(kept),
                "keys":     keys,
                "keep":     keep,
            },
        )


# ═════════════════════════════════════════════════════════════════════
# Read-only executors
# ═════════════════════════════════════════════════════════════════════


class EnrichExecutor(NodeExecutor):
    """enrich — read_only left-join with a master/lookup table.

    Different from `join` (pure, joins 2 in-memory lists) — enrich pulls
    the right side from a whitelisted DB table at execution time.

    Config:
      rows:           $.upstream.rows       (left side, list[dict])
      lookup_table:   'silver_customers'    (must be in TABLE_WHITELIST)
      lookup_key:     'customer_id'          (column in lookup table)
      from_column:    'customer_id'          (column in rows providing key value)
      attach_columns: ['name','tier','region']  (lookup cols to attach)
      prefix:         'cust_'   (optional — avoid collision)
    Output:
      {rows: list[dict], matched: int, missed: int}
    """
    node_type_key = "enrich"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = _resolve(config.get("rows"), ctx)
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise NodeExecutorError("enrich.rows must resolve to list")

        lookup_table = config.get("lookup_table")
        if lookup_table not in TABLE_WHITELIST:
            raise NodeExecutorError(
                f"enrich.lookup_table={lookup_table!r} not in whitelist"
            )
        lookup_key = config.get("lookup_key")
        if not lookup_key or not isinstance(lookup_key, str):
            raise NodeExecutorError("enrich.lookup_key required (string)")
        _validate_ident_local(lookup_key, "lookup_key")

        from_column = config.get("from_column") or lookup_key
        if not isinstance(from_column, str):
            raise NodeExecutorError("enrich.from_column must be string")

        attach = config.get("attach_columns")
        if not isinstance(attach, list) or not attach:
            raise NodeExecutorError("enrich.attach_columns required (non-empty list)")
        attach_cols = [_validate_ident_local(str(c), "attach column") for c in attach]

        prefix = config.get("prefix") or ""
        if not isinstance(prefix, str):
            raise NodeExecutorError("enrich.prefix must be string")

        # Collect unique key values from rows
        wanted_keys: set[Any] = set()
        for r in rows:
            if isinstance(r, dict) and from_column in r:
                wanted_keys.add(r[from_column])
        wanted_keys.discard(None)

        if not wanted_keys:
            return NodeResult(
                status="completed",
                output_data={"rows": rows, "matched": 0, "missed": len(rows)},
            )

        select_cols = ", ".join([lookup_key] + attach_cols)
        sql = f"SELECT {select_cols} FROM {lookup_table} WHERE {lookup_key} = ANY($1)"

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            records = await conn.fetch(sql, list(wanted_keys))

        lookup_index: dict[Any, dict[str, Any]] = {}
        for rec in records:
            d = dict(rec)
            key_val = d.pop(lookup_key)
            lookup_index[key_val] = d

        out: list[dict[str, Any]] = []
        matched = 0
        for r in rows:
            if not isinstance(r, dict):
                out.append(r)
                continue
            merged = dict(r)
            key_val = r.get(from_column)
            if key_val in lookup_index:
                matched += 1
                for col, val in lookup_index[key_val].items():
                    merged[prefix + col] = val
            out.append(merged)

        return NodeResult(
            status="completed",
            output_data={
                "rows":         out,
                "matched":      matched,
                "missed":       len(rows) - matched,
                "lookup_table": lookup_table,
            },
        )


class WaitForConditionExecutor(NodeExecutor):
    """wait_for_condition — poll a whitelisted SELECT until match or timeout.

    Useful for workflows that wait for an external signal (e.g. customer
    response logged into a table, payment confirmation INSERTed by webhook).

    Config:
      check_table:           'workflow_form_submissions'  (whitelisted)
      check_filter:          {col: value}    (equality, AND)
      max_wait_seconds:      120  (1..3600)
      poll_interval_seconds: 2    (1..60)
    Output:
      {found: bool, row: dict | null, waited_seconds: float, polls: int}
    """
    node_type_key = "wait_for_condition"
    side_effect_class = SideEffectClass.READ_ONLY

    # Tables this node may poll. Conservative — extend as workflows need.
    POLL_WHITELIST: set[str] = {
        "workflow_form_submissions",
        "workflow_email_intake",
        "workflow_webhook_intake",
        "workflow_chat_intake",
        "workflow_approvals",
    }

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        table = config.get("check_table")
        if table not in self.POLL_WHITELIST:
            raise NodeExecutorError(
                f"wait_for_condition.check_table={table!r} not in whitelist "
                f"{sorted(self.POLL_WHITELIST)}"
            )

        filter_raw = config.get("check_filter") or {}
        if not isinstance(filter_raw, dict) or not filter_raw:
            raise NodeExecutorError("wait_for_condition.check_filter required (non-empty dict)")

        max_wait = float(config.get("max_wait_seconds") or 120)
        if max_wait < 1 or max_wait > 3600:
            raise NodeExecutorError("wait_for_condition.max_wait_seconds must be 1..3600")

        poll_interval = float(config.get("poll_interval_seconds") or 2)
        if poll_interval < 1 or poll_interval > 60:
            raise NodeExecutorError("wait_for_condition.poll_interval_seconds must be 1..60")

        where_parts: list[str] = []
        args: list[Any] = []
        for i, (col, val) in enumerate(filter_raw.items(), start=1):
            _validate_ident_local(col, "filter column")
            where_parts.append(f"{col} = ${i}")
            args.append(_resolve(val, ctx))
        sql = f"SELECT * FROM {table} WHERE {' AND '.join(where_parts)} LIMIT 1"

        from ai_orchestrator.shared.db import acquire_for_tenant

        start = time.monotonic()
        polls = 0
        deadline = start + max_wait
        while time.monotonic() < deadline:
            polls += 1
            async with acquire_for_tenant(ctx.enterprise_id) as conn:
                record = await conn.fetchrow(sql, *args)
            if record is not None:
                # Normalise JSONB columns
                row = {}
                for k, v in dict(record).items():
                    if isinstance(v, str) and v and (v[0] == "{" or v[0] == "["):
                        try:
                            v = json.loads(v)
                        except Exception:  # noqa: BLE001
                            pass
                    row[k] = v
                return NodeResult(
                    status="completed",
                    output_data={
                        "found":          True,
                        "row":            _coerce_for_json(row),
                        "waited_seconds": round(time.monotonic() - start, 3),
                        "polls":          polls,
                    },
                )
            # Don't sleep past the deadline
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(poll_interval, remaining))

        return NodeResult(
            status="completed",
            output_data={
                "found":          False,
                "row":            None,
                "waited_seconds": round(time.monotonic() - start, 3),
                "polls":          polls,
            },
        )


def _coerce_for_json(value: Any) -> Any:
    """Recursively coerce UUID/datetime to strings so the executor's
    output_data is JSON-serialisable (the runner json.dumps it before
    persisting)."""
    from datetime import datetime, date
    from uuid import UUID as _UUID
    if isinstance(value, dict):
        return {k: _coerce_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_for_json(v) for v in value]
    if isinstance(value, _UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class ReadApiExecutor(NodeExecutor):
    """read_api — generic HTTP GET (mirror of call_api but read-only).

    Config:
      url:       (required; host must be in WORKFLOW_CALL_API_ALLOWED_HOSTS)
      headers:   {Key: value}   (optional)
      timeout_s: 30  (1..120)
    Output:
      {status_code, response_body, url}
    """
    node_type_key = "read_api"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        url = _resolve(config.get("url"), ctx)
        if not isinstance(url, str) or not url.strip():
            raise NodeExecutorError("read_api.url required (non-empty)")
        url = url.strip()

        from urllib.parse import urlparse
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:  # noqa: BLE001
            raise NodeExecutorError(f"read_api.url not parseable: {url!r}")
        if not host:
            raise NodeExecutorError("read_api.url missing host")

        # Reuse same allowlist env as call_api
        from .action import _allowed_hosts
        whitelist = _allowed_hosts()
        if host not in whitelist:
            raise NodeExecutorError(
                f"read_api host {host!r} not in allowlist {sorted(whitelist)}"
            )

        timeout_s = float(config.get("timeout_s") or 30)
        if timeout_s < 1 or timeout_s > 120:
            raise NodeExecutorError("read_api.timeout_s must be 1..120")

        headers_raw = config.get("headers") or {}
        if not isinstance(headers_raw, dict):
            raise NodeExecutorError("read_api.headers must be dict")
        headers = {
            str(k)[:200]: str(_resolve(v, ctx))[:1000]
            for k, v in headers_raw.items()
            if _resolve(v, ctx) is not None
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise NodeExecutorError(f"read_api GET {url} failed: {type(exc).__name__}")

        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = resp.text[:5000]

        return NodeResult(
            status="completed",
            output_data={
                "status_code":   resp.status_code,
                "response_body": body,
                "url":           url,
            },
        )


class _IntakeClaimer:
    """Mixin for read_calendar / read_chat — same claim pattern as
    read_email/read_webhook but parameterised by table + columns."""

    table_name: str = ""
    primary_key: str = ""
    select_columns: tuple[str, ...] = ()
    order_column: str = "received_at"

    async def _claim(
        self,
        ctx: NodeContext,
        queue_key: str,
        consume: bool,
        latest_first: bool,
    ) -> Optional[dict[str, Any]]:
        order_dir = "DESC" if latest_first else "ASC"
        select_list = ", ".join((self.primary_key,) + self.select_columns)
        sql = (
            f"SELECT {select_list} FROM {self.table_name} "
            f"WHERE queue_key = $1 AND status = 'pending' "
            f"ORDER BY {self.order_column} {order_dir} LIMIT 1 "
            f"FOR UPDATE SKIP LOCKED"
        )
        update_sql = (
            f"UPDATE {self.table_name} "
            f"SET status='consumed', consumed_at=NOW(), consumed_by_run_id=$1 "
            f"WHERE {self.primary_key}=$2"
        )

        from ai_orchestrator.shared.db import acquire_for_tenant
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            async with conn.transaction():
                row = await conn.fetchrow(sql, queue_key)
                if row is None:
                    return None
                pk_value = row[self.primary_key]
                if consume:
                    await conn.execute(update_sql, ctx.run_id, pk_value)
        return _coerce_for_json(dict(row))


class ReadCalendarExecutor(_IntakeClaimer, NodeExecutor):
    """read_calendar — claim next pending calendar event from
    workflow_calendar_intake."""
    node_type_key = "read_calendar"
    side_effect_class = SideEffectClass.READ_ONLY
    table_name = "workflow_calendar_intake"
    primary_key = "event_id"
    select_columns = (
        "calendar_source", "external_event_id", "organizer", "attendees",
        "summary", "description", "location",
        "start_at", "end_at", "payload", "received_at",
    )
    order_column = "start_at"

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        queue_key = config.get("queue_key")
        if not isinstance(queue_key, str) or not queue_key.strip():
            raise NodeExecutorError("read_calendar.queue_key required")
        queue_key = queue_key.strip()[:64]
        consume = bool(config.get("consume", True))
        latest_first = bool(config.get("latest_first"))

        row = await self._claim(ctx, queue_key, consume, latest_first)
        if row is None:
            return NodeResult(
                status="completed",
                output_data={
                    "found":      False,
                    "queue_key":  queue_key,
                    "event_id":   None,
                },
            )
        log.info("read_calendar.claimed" if consume else "read_calendar.peeked",
                  event_id=row.get("event_id"), queue_key=queue_key,
                  enterprise_id=str(ctx.enterprise_id))
        return NodeResult(
            status="completed",
            output_data={
                "found":      True,
                "queue_key":  queue_key,
                "claimed":    consume,
                **row,
            },
        )


class ReadChatExecutor(_IntakeClaimer, NodeExecutor):
    """read_chat — claim next inbound chat message from
    workflow_chat_intake."""
    node_type_key = "read_chat"
    side_effect_class = SideEffectClass.READ_ONLY
    table_name = "workflow_chat_intake"
    primary_key = "message_id"
    select_columns = (
        "channel", "external_message_id", "sender", "sender_display_name",
        "target", "message", "attachments", "received_at",
    )
    order_column = "received_at"

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        queue_key = config.get("queue_key")
        if not isinstance(queue_key, str) or not queue_key.strip():
            raise NodeExecutorError("read_chat.queue_key required")
        queue_key = queue_key.strip()[:64]
        consume = bool(config.get("consume", True))
        latest_first = bool(config.get("latest_first"))

        row = await self._claim(ctx, queue_key, consume, latest_first)
        if row is None:
            return NodeResult(
                status="completed",
                output_data={
                    "found":       False,
                    "queue_key":   queue_key,
                    "message_id":  None,
                },
            )
        log.info("read_chat.claimed" if consume else "read_chat.peeked",
                  message_id=row.get("message_id"), queue_key=queue_key,
                  enterprise_id=str(ctx.enterprise_id))
        return NodeResult(
            status="completed",
            output_data={
                "found":      True,
                "queue_key":  queue_key,
                "claimed":    consume,
                **row,
            },
        )


class ReadFileUploadExecutor(NodeExecutor):
    """read_file_upload — lookup a Bronze file row by file_id.

    Wraps the existing Stage-1 Bronze table. Returns metadata + status
    + storage path. The actual file content is fetched lazily by
    downstream nodes that need bytes (vd extract pipeline).

    Config:
      file_id:        $.input.file_id  (UUID)
      include_status: True  (default — include silver/processing status)
    Output:
      found=False if not in tenant scope.
      found=True with {file_id, filename, sha256, mime_type,
                       storage_path, uploaded_by, uploaded_at, size_bytes}
    """
    node_type_key = "read_file_upload"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        file_id_raw = _resolve(config.get("file_id"), ctx)
        if not file_id_raw and "file_id" in (ctx.input_data or {}):
            file_id_raw = ctx.input_data["file_id"]
        if not file_id_raw:
            raise NodeExecutorError("read_file_upload.file_id required")
        try:
            file_id = UUID(str(file_id_raw))
        except ValueError:
            raise NodeExecutorError(f"read_file_upload.file_id not UUID: {file_id_raw!r}")

        from ai_orchestrator.shared.db import acquire_for_tenant
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """SELECT file_id, original_filename, sha256_hex, mime_type,
                          storage_path, uploaded_by_user_id, uploaded_at,
                          size_bytes
                   FROM bronze_files WHERE file_id = $1""",
                file_id,
            )
        if row is None:
            return NodeResult(
                status="completed",
                output_data={
                    "found":   False,
                    "file_id": str(file_id),
                },
            )

        return NodeResult(
            status="completed",
            output_data={
                "found":             True,
                "file_id":           str(row["file_id"]),
                "filename":          row["original_filename"],
                "sha256":            row["sha256_hex"],
                "mime_type":         row["mime_type"],
                "storage_path":      row["storage_path"],
                "uploaded_by":       (str(row["uploaded_by_user_id"])
                                       if row["uploaded_by_user_id"] else None),
                "uploaded_at":       row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "size_bytes":        row["size_bytes"],
            },
        )


# ═════════════════════════════════════════════════════════════════════
# External / write executors
# ═════════════════════════════════════════════════════════════════════


class SendSmsExecutor(NodeExecutor):
    """send_sms — INSERT into workflow_chat_outbox with channel='sms'.

    Reuses the chat outbox infrastructure (mig 092 + ALTER in mig 093)
    so the same bot adapter pattern dispatches SMS via Twilio / Telnyx /
    Speedshift VN gateway etc.

    Config:
      target:    '+84912345678'   (E.164 phone format — required)
      message:   $.upstream.body  (required, ≤500 chars per SMS limits)
      metadata:  {}  (optional)
    Output:
      {outbox_id, target, queued, dedup_hit}
    """
    node_type_key = "send_sms"
    side_effect_class = SideEffectClass.EXTERNAL

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        target = _resolve(config.get("target"), ctx)
        if not isinstance(target, str) or not target.strip():
            raise NodeExecutorError("send_sms.target required (phone number)")
        target = target.strip()
        # Loose E.164 sanity — caller's K-5 PII redaction owns full validation
        if not (target.startswith("+") or target.isdigit() or target[0] == "0"):
            raise NodeExecutorError(f"send_sms.target {target!r} doesn't look like a phone number")
        if len(target) > 320:
            raise NodeExecutorError("send_sms.target too long")

        message_resolved = _resolve(config.get("message"), ctx)
        message = str(message_resolved or "").strip()
        if not message:
            raise NodeExecutorError("send_sms.message required")
        if len(message) > 500:
            raise NodeExecutorError("send_sms.message > 500 chars (SMS limit)")

        metadata_raw = config.get("metadata") or {}
        if not isinstance(metadata_raw, dict):
            raise NodeExecutorError("send_sms.metadata must be dict")

        source_ref = ctx.idempotency_key or f"wfsms:{ctx.run_id}:{ctx.node_id}"

        from ai_orchestrator.shared.db import acquire_for_tenant
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            existing = await conn.fetchrow(
                "SELECT outbox_id FROM workflow_chat_outbox "
                "WHERE enterprise_id = $1 AND source_ref = $2 LIMIT 1",
                ctx.enterprise_id, source_ref,
            )
            if existing:
                return NodeResult(
                    status="completed",
                    output_data={
                        "outbox_id": str(existing["outbox_id"]),
                        "target":    target,
                        "queued":    True,
                        "dedup_hit": True,
                    },
                )
            row = await conn.fetchrow(
                """INSERT INTO workflow_chat_outbox
                       (enterprise_id, run_id, node_id, channel, target,
                        message, metadata, source_ref)
                   VALUES ($1, $2, $3, 'sms', $4, $5, $6, $7)
                   RETURNING outbox_id""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id,
                target, message, json.dumps(metadata_raw), source_ref,
            )

        log.info("send_sms.queued",
                  outbox_id=str(row["outbox_id"]),
                  target=target[:6] + "***",  # PII-friendly log
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "outbox_id": str(row["outbox_id"]),
                "target":    target,
                "queued":    True,
                "dedup_hit": False,
            },
        )


class ExportFileExecutor(NodeExecutor):
    """export_file — write_idempotent record of an export request.

    v0 ships the queue + tracking row. A future renderer + MinIO writer
    poll workflow_export_files WHERE status='queued', render the file,
    fill in minio_object_path + flip to 'ready'. Pattern mirrors
    generate_report.

    Config:
      export_key:    'invoice-batch-2026-05'  (UNIQUE per tenant; retry-safe)
      file_format:   'csv' | 'xlsx' | 'json' | 'pdf' | 'txt' | 'parquet'
      filename:      'invoices.csv'
      rows:          $.upstream.rows   (source data — recorded in metadata)
      row_count:     (optional override; default len(rows))
    Output:
      {export_id, status: 'queued'|'requeued', export_key, file_format}
    """
    node_type_key = "export_file"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        export_key = _resolve(config.get("export_key"), ctx)
        if not isinstance(export_key, str) or not export_key.strip():
            raise NodeExecutorError("export_file.export_key required")
        export_key = export_key.strip()[:200]

        file_format = (config.get("file_format") or "").lower()
        if file_format not in ("csv", "xlsx", "json", "pdf", "txt", "parquet"):
            raise NodeExecutorError(f"export_file.file_format={file_format!r} invalid")

        filename = config.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            raise NodeExecutorError("export_file.filename required")
        filename = filename.strip()[:300]

        rows = _resolve(config.get("rows"), ctx)
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise NodeExecutorError("export_file.rows must resolve to list")
        row_count = int(config.get("row_count") or len(rows))

        # Don't stash the full rows in metadata (could be MB); record
        # a summary + schema for the renderer to pull lazily.
        meta = {
            "row_count": row_count,
            "schema":    list(rows[0].keys()) if rows and isinstance(rows[0], dict) else [],
        }

        from ai_orchestrator.shared.db import acquire_for_tenant
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """INSERT INTO workflow_export_files
                       (enterprise_id, run_id, node_id, export_key,
                        file_format, filename, metadata, row_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (enterprise_id, export_key) DO UPDATE
                   SET file_format = EXCLUDED.file_format,
                       filename    = EXCLUDED.filename,
                       metadata    = EXCLUDED.metadata,
                       row_count   = EXCLUDED.row_count
                   RETURNING export_id, (xmax = 0) AS inserted""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id, export_key,
                file_format, filename, json.dumps(meta), row_count,
            )

        status = "queued" if row["inserted"] else "requeued"
        return NodeResult(
            status="completed",
            output_data={
                "export_id":   str(row["export_id"]),
                "export_key":  export_key,
                "file_format": file_format,
                "filename":    filename,
                "row_count":   row_count,
                "status":      status,
            },
        )
