"""
P2-S23 SH-M56a-021..024 — guardrail_violations DB layer.

Three concerns:
  - record_violation()           — insert one row (mig 082 partitioned)
  - list_violations()            — paginated read for dashboard
  - top_patterns() + per_rule()  — aggregations for SH-M56a-022 dashboard
  - run_retention()              — SH-M56a-024 drop partitions > 180d

A dependency injection seam lets tests pass a fake pool — the engine
calls `record_violation(v, pool=fake)` from tests, real production
defaults to the gateway's own pool.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import structlog

from .on_fail import OnFailAction
from .types import Layer, Severity, Violation

log = structlog.get_logger()


# Soft dependency on the gateway pool; tests pass their own.
def _default_pool():
    try:
        from ..db import get_pool
        return get_pool()
    except Exception:  # noqa: BLE001
        return None


def _truncate(s: Optional[str], limit: int = 500) -> Optional[str]:
    if s is None:
        return None
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


async def record_violation(
    v: Violation,
    *,
    on_fail_action: OnFailAction,
    pool=None,
) -> None:
    """Insert one row. Swallows errors with a warning so a guardrail
    persist failure NEVER blocks an LLM call."""
    pool = pool if pool is not None else _default_pool()
    if pool is None:
        log.debug("guardrails.persist_skipped_no_pool", rule=v.rule_name)
        return

    layer = v.layer.value if hasattr(v.layer, "value") else str(v.layer)
    severity = v.severity.value if hasattr(v.severity, "value") else str(v.severity)
    action = on_fail_action.value if hasattr(on_fail_action, "value") else str(on_fail_action)

    metadata_json = json.dumps(v.rule_metadata, default=str)
    excerpt = _truncate(v.offending_excerpt)

    sql = """
        INSERT INTO guardrail_violations (
            enterprise_id, user_id, rule_name, layer, severity,
            on_fail_action, request_id, model_id,
            offending_excerpt, rule_metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                sql,
                v.enterprise_id, v.user_id, v.rule_name, layer, severity,
                action, v.request_id, v.model_id, excerpt, metadata_json,
            )
    except Exception as e:  # noqa: BLE001
        log.warning("guardrails.insert_failed",
                    rule=v.rule_name, error=str(e))


# ─── Read paths for SH-M56a-022 dashboard ────────────────────────────


async def list_violations(
    *,
    enterprise_id,
    since: Optional[datetime] = None,
    layer: Optional[str] = None,
    rule_name: Optional[str] = None,
    limit: int = 100,
    pool=None,
) -> list[dict[str, Any]]:
    pool = pool if pool is not None else _default_pool()
    if pool is None:
        return []

    where = ["enterprise_id = $1"]
    params: list = [enterprise_id]
    if since is not None:
        where.append(f"created_at >= ${len(params) + 1}")
        params.append(since)
    if layer is not None:
        where.append(f"layer = ${len(params) + 1}")
        params.append(layer)
    if rule_name is not None:
        where.append(f"rule_name = ${len(params) + 1}")
        params.append(rule_name)

    sql = f"""
        SELECT violation_id, enterprise_id, user_id, rule_name, layer,
               severity, on_fail_action, request_id, model_id,
               offending_excerpt, rule_metadata, created_at
        FROM guardrail_violations
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT {int(limit)}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [dict(r) for r in rows]


async def top_patterns(
    *,
    enterprise_id,
    since: Optional[datetime] = None,
    limit: int = 10,
    pool=None,
) -> list[dict[str, Any]]:
    """SH-M56a-022 — top violation patterns dashboard."""
    pool = pool if pool is not None else _default_pool()
    if pool is None:
        return []

    sql = """
        SELECT rule_name, layer, severity, COUNT(*) AS n
        FROM guardrail_violations
        WHERE enterprise_id = $1
          AND ($2::TIMESTAMPTZ IS NULL OR created_at >= $2)
        GROUP BY rule_name, layer, severity
        ORDER BY n DESC
        LIMIT $3
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, enterprise_id, since, limit)
    return [dict(r) for r in rows]


# ─── SH-M56a-024 retention ───────────────────────────────────────────


async def run_retention(
    *,
    keep_days: int = 180,
    pool=None,
) -> list[str]:
    """Drop partitions older than `keep_days`. Also creates the next
    month's partition if missing (idempotent — safe to run daily).

    Returns the list of partition names dropped (for audit / cron log).
    """
    pool = pool if pool is not None else _default_pool()
    if pool is None:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).date()
    cutoff = cutoff.replace(day=1)

    dropped: list[str] = []

    # 1. Drop old partitions
    async with pool.acquire() as conn:
        old_parts = await conn.fetch(
            """
            SELECT child.relname AS part_name,
                   pg_get_expr(child.relpartbound, child.oid) AS bound
            FROM pg_inherits i
            JOIN pg_class parent ON parent.oid = i.inhparent
            JOIN pg_class child  ON child.oid  = i.inhrelid
            WHERE parent.relname = 'guardrail_violations'
            """
        )
        for row in old_parts:
            part_name = row["part_name"]
            bound = row["bound"] or ""
            # Bound shape: "FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')"
            import re
            m = re.search(r"FROM \('([^']+)'\)", bound)
            if m is None:
                continue
            try:
                part_start = date.fromisoformat(m.group(1))
            except ValueError:
                continue
            if part_start < cutoff:
                await conn.execute(f'DROP TABLE IF EXISTS {part_name}')
                dropped.append(part_name)

        # 2. Ensure the next 2 months have partitions
        cur_month = datetime.now(timezone.utc).date().replace(day=1)
        for i in range(0, 3):
            year = cur_month.year + (cur_month.month + i - 1) // 12
            month = (cur_month.month + i - 1) % 12 + 1
            start = date(year, month, 1)
            next_month_year = year + (month // 12)
            next_month = month % 12 + 1
            end = date(next_month_year, next_month, 1)
            part_name = f"guardrail_violations_{start.strftime('%Y_%m')}"
            await conn.execute(
                f"""CREATE TABLE IF NOT EXISTS {part_name}
                     PARTITION OF guardrail_violations
                     FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"""
            )

    if dropped:
        log.info("guardrails.retention_dropped",
                 count=len(dropped), partitions=dropped)
    return dropped
