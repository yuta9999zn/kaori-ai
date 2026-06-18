"""
Phase 2.7 P2 — Tenant quota pre-call gate (llm-gateway local writer).

Mirrors services/ai-orchestrator/shared/tenant_quotas.py but uses
llm-gateway's own asyncpg.Pool + sets `app.enterprise_id` GUC LOCAL=true
inside the transaction so RLS on tenant_quotas / tenant_quota_usage
passes.

Called as a PRE-flight gate on /v1/infer. Estimate of usage =
len(prompt_chars) + max_tokens × 4 (rough char-per-token average). On
QuotaExceeded the router responds with 429 RFC 7807.

Best-effort failure mode: if the quota check itself fails for an
infra reason (DB down, etc.), we fail OPEN — the primary LLM path
must not be blocked because the quota table is unreachable. The
governance audit will record the call and a downstream sweep can
reconcile.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import asyncpg
import structlog

log = structlog.get_logger()


class QuotaExceeded(Exception):
    """Increment would push current_value past max_value."""

    def __init__(self, quota_type: str, current: int, max_value: int, period: str):
        super().__init__(
            f"Quota exceeded for {quota_type} ({period}): "
            f"current={current} > max={max_value}"
        )
        self.quota_type = quota_type
        self.current = current
        self.max_value = max_value
        self.period = period


@dataclass(frozen=True)
class QuotaCheck:
    quota_type: str
    period:     str
    max_value:  int
    current:    int
    headroom:   int


def _window_bounds(period: str, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Pure window math — same as the ai-orchestrator copy. Tests can
    pin `now` for determinism."""
    if now is None:
        now = datetime.now(timezone.utc)
    if period == "per_minute":
        start = now.replace(second=0, microsecond=0)
        return start, start + timedelta(minutes=1)
    if period == "per_hour":
        start = now.replace(minute=0, second=0, microsecond=0)
        return start, start + timedelta(hours=1)
    if period == "per_day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    if period == "per_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    if period == "rolling":
        return now - timedelta(minutes=1), now + timedelta(minutes=1)
    raise ValueError(f"Unknown period={period!r}")


async def check_and_consume(
    pool: Optional[asyncpg.Pool] = None,
    *,
    enterprise_id: str | UUID,
    quota_type:    str,
    amount:        int = 1,
    fail_open_if_unconfigured: bool = True,
    fail_open_on_infra_error:  bool = True,
) -> Optional[QuotaCheck]:
    """Atomic check + UPSERT increment. Raises QuotaExceeded on hard
    overrun. Returns None if quota_type not configured (and fail_open
    True). Returns QuotaCheck on success.

    `fail_open_on_infra_error` controls behaviour when the quota table
    itself is unreachable — default True so a downed quota path does
    not block legitimate traffic. Set False in tests + audit contexts
    where we'd rather see the infra failure than miss a quota event.
    """
    if amount < 0:
        raise ValueError("amount must be >= 0")
    if not enterprise_id:
        return None

    ent_uuid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))

    # F1 follow-up — prefer retry helper but honor explicit pool.
    if pool is not None:
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def _cm():
            async with pool.acquire() as c:
                yield c
        acquire_cm = _cm()
    else:
        from .db import acquire_with_retry
        acquire_cm = acquire_with_retry()

    try:
        async with acquire_cm as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.enterprise_id', $1, true)",
                    str(ent_uuid),
                )

                quota_row = await conn.fetchrow(
                    """SELECT max_value, period FROM tenant_quotas
                       WHERE enterprise_id = $1 AND quota_type = $2 AND enabled = TRUE
                       ORDER BY period LIMIT 1""",
                    ent_uuid, quota_type,
                )
                if quota_row is None:
                    if fail_open_if_unconfigured:
                        return None
                    raise QuotaExceeded(quota_type, 0, 0, "unconfigured")

                max_value = int(quota_row["max_value"])
                period = quota_row["period"]
                start, end = _window_bounds(period)

                usage_row = await conn.fetchrow(
                    """SELECT usage_id, current_value FROM tenant_quota_usage
                       WHERE enterprise_id = $1 AND quota_type = $2
                         AND window_start = $3
                       FOR UPDATE""",
                    ent_uuid, quota_type, start,
                )
                current = int(usage_row["current_value"]) if usage_row else 0

                if current + amount > max_value:
                    raise QuotaExceeded(quota_type, current + amount, max_value, period)

                new_value = current + amount

                if usage_row is None:
                    await conn.execute(
                        """INSERT INTO tenant_quota_usage
                               (enterprise_id, quota_type, window_start,
                                window_end, current_value)
                           VALUES ($1, $2, $3, $4, $5)
                           ON CONFLICT (enterprise_id, quota_type, window_start) DO UPDATE
                               SET current_value = tenant_quota_usage.current_value + EXCLUDED.current_value,
                                   last_inc_at   = NOW()""",
                        ent_uuid, quota_type, start, end, amount,
                    )
                else:
                    await conn.execute(
                        """UPDATE tenant_quota_usage
                           SET current_value = $1, last_inc_at = NOW()
                           WHERE usage_id = $2""",
                        new_value, usage_row["usage_id"],
                    )
    except QuotaExceeded:
        raise
    except Exception as exc:
        if fail_open_on_infra_error:
            log.warning(
                "tenant_quota.infra_error.fail_open",
                quota_type=quota_type, enterprise_id=str(ent_uuid),
                error=str(exc),
            )
            return None
        raise

    return QuotaCheck(
        quota_type=quota_type, period=period,
        max_value=max_value, current=new_value,
        headroom=max_value - new_value,
    )
