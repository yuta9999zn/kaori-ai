"""
Tenant quota enforcement — P2 of Phase 2.7.

Per anh's review §3E "Tenant governance / quotas / noisy neighbor".

Pre-2.7: only enterprise_monthly_billing tracked customer count. No
limits on AI token spend / workflow concurrency / API rate.

This module exposes a pre-call gate:

  await check_and_consume(
      enterprise_id=...,
      quota_type='llm_tokens_external',
      amount=token_count,
  )

Raises QuotaExceeded if the increment would exceed `max_value` for the
current window. Returns the remaining headroom on success.

Window math:
  per_minute  — window_start = floor(now, minute)
  per_hour    — window_start = floor(now, hour)
  per_day     — window_start = floor(now, day) UTC
  per_month   — window_start = floor(now, month-start)
  rolling     — window_start = now() - 1 minute (concurrent gauge)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


class QuotaNotConfigured(Exception):
    """No quota row for (enterprise, quota_type, period). Caller decides
    whether to fail-open (allow) or fail-closed (deny)."""


class QuotaExceeded(Exception):
    """Increment would push current_value past max_value. Action layer
    should return 429 to the caller."""

    def __init__(self, quota_type: str, current: int, max_value: int, period: str):
        super().__init__(
            f"Quota exceeded for {quota_type} ({period}): "
            f"current={current} + delta > max={max_value}"
        )
        self.quota_type = quota_type
        self.current = current
        self.max_value = max_value
        self.period = period


@dataclass(frozen=True)
class QuotaCheck:
    quota_type:  str
    period:      str
    max_value:   int
    current:     int
    headroom:    int


def _window_bounds(period: str, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Pure window math — same `now` always produces same bounds.
    Tests can pass a fixed `now` for determinism."""
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
        # Next month boundary
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    if period == "rolling":
        # Rolling 1-minute window for concurrency-gauge use case
        return now - timedelta(minutes=1), now + timedelta(minutes=1)
    raise ValueError(f"Unknown period={period!r}")


async def check_and_consume(
    *,
    enterprise_id: UUID,
    quota_type:    str,
    amount:        int = 1,
    fail_open_if_unconfigured: bool = True,
    fail_open_on_infra_error:  Optional[bool] = None,
) -> QuotaCheck:
    """Atomic check + UPSERT increment within one transaction.

    Returns QuotaCheck with remaining headroom.

    Raises:
      QuotaNotConfigured — no row in tenant_quotas (unless fail_open).
      QuotaExceeded      — increment would exceed max_value.

    `fail_open_on_infra_error` (F2 follow-up 2026-05-20):
      None    — read the `fail_open` column on tenant_quotas (per-quota
                self-declared policy: default TRUE in mig 100;
                workflow_concurrent flipped to FALSE).
      True    — force fail-open regardless of DB column.
      False   — force fail-closed regardless of DB column.
    """
    if amount < 0:
        raise ValueError("amount must be >= 0")

    # Single-element list used as a mutable container so the inner
    # function can populate the per-quota policy after it reads the
    # tenant_quotas row. Avoids a second DB round-trip + lets the
    # outer except see the policy regardless of where the inner raises.
    policy_holder: list[Optional[bool]] = [None]
    if fail_open_on_infra_error is not None:
        policy_holder[0] = bool(fail_open_on_infra_error)

    try:
        return await _check_and_consume_inner(
            enterprise_id=enterprise_id,
            quota_type=quota_type,
            amount=amount,
            fail_open_if_unconfigured=fail_open_if_unconfigured,
            policy_holder=policy_holder,
        )
    except (QuotaExceeded, QuotaNotConfigured):
        raise
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        # Apply policy. When the inner failed BEFORE reading the row,
        # policy_holder[0] is still None → default to TRUE (preserve
        # uptime; matches pre-F2 behaviour).
        effective = policy_holder[0] if policy_holder[0] is not None else True
        if not effective:
            log.warning(
                "tenant_quota.infra_error.fail_closed",
                quota_type=quota_type,
                enterprise_id=str(enterprise_id),
                error=type(exc).__name__,
                detail=str(exc),
            )
            raise
        log.warning(
            "tenant_quota.infra_error.fail_open",
            quota_type=quota_type,
            enterprise_id=str(enterprise_id),
            error=type(exc).__name__,
            detail=str(exc),
        )
        return QuotaCheck(
            quota_type=quota_type, period="infra_error",
            max_value=2**31, current=0, headroom=2**31,
        )


async def _check_and_consume_inner(
    *,
    enterprise_id: UUID,
    quota_type:    str,
    amount:        int,
    fail_open_if_unconfigured: bool,
    policy_holder: Optional[list] = None,
) -> QuotaCheck:
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        async with conn.transaction():
            # Gap 5 — contention guard. SELECT FOR UPDATE below can block
            # indefinitely if another worker holds the row lock. Set
            # txn-local timeouts so a slow path fails fast → existing
            # try/except (caller) → fail-open → primary call proceeds.
            await conn.execute("SET LOCAL lock_timeout = '2s'")
            await conn.execute("SET LOCAL statement_timeout = '5s'")

            # F2 — SELECT fail_open along with the existing columns so
            # the outer wrapper can apply per-quota policy without a
            # second round trip. Tolerates absent column (mig 100 not
            # yet applied) via dict-access guard.
            quota_row = await conn.fetchrow(
                """SELECT max_value, period,
                          COALESCE(fail_open, TRUE) AS fail_open
                   FROM tenant_quotas
                   WHERE enterprise_id = $1 AND quota_type = $2 AND enabled = TRUE
                   ORDER BY period LIMIT 1""",
                enterprise_id, quota_type,
            )
            if quota_row is None:
                if fail_open_if_unconfigured:
                    log.debug("tenant_quota.no_row.fail_open",
                                enterprise_id=str(enterprise_id),
                                quota_type=quota_type)
                    return QuotaCheck(
                        quota_type=quota_type, period="unconfigured",
                        max_value=2**31, current=0, headroom=2**31,
                    )
                raise QuotaNotConfigured(
                    f"No tenant_quotas row for {quota_type!r}"
                )

            # F2 — populate policy holder so the outer wrapper sees it
            # if a subsequent failure fires. Test rows that DON'T set
            # the column fall through to the COALESCE default (TRUE).
            try:
                row_fail_open = bool(quota_row["fail_open"])
            except (KeyError, TypeError):
                row_fail_open = True
            if policy_holder is not None and policy_holder[0] is None:
                policy_holder[0] = row_fail_open

            max_value = int(quota_row["max_value"])
            period = quota_row["period"]
            start, end = _window_bounds(period)

            # SELECT current with FOR UPDATE to serialise concurrent increments
            usage_row = await conn.fetchrow(
                """SELECT usage_id, current_value FROM tenant_quota_usage
                   WHERE enterprise_id = $1 AND quota_type = $2
                     AND window_start = $3
                   FOR UPDATE""",
                enterprise_id, quota_type, start,
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
                    enterprise_id, quota_type, start, end, amount,
                )
            else:
                await conn.execute(
                    """UPDATE tenant_quota_usage
                       SET current_value = $1, last_inc_at = NOW()
                       WHERE usage_id = $2""",
                    new_value, usage_row["usage_id"],
                )

    log.debug("tenant_quota.consumed",
                enterprise_id=str(enterprise_id),
                quota_type=quota_type, amount=amount,
                current=new_value, max_value=max_value)
    return QuotaCheck(
        quota_type=quota_type, period=period,
        max_value=max_value, current=new_value,
        headroom=max_value - new_value,
    )


async def get_usage(
    *,
    enterprise_id: UUID,
    quota_type:    str,
) -> Optional[QuotaCheck]:
    """Read current usage without incrementing. Returns None if no
    quota row is configured."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        quota_row = await conn.fetchrow(
            """SELECT max_value, period FROM tenant_quotas
               WHERE enterprise_id = $1 AND quota_type = $2 AND enabled = TRUE
               LIMIT 1""",
            enterprise_id, quota_type,
        )
        if quota_row is None:
            return None
        max_value = int(quota_row["max_value"])
        period = quota_row["period"]
        start, _end = _window_bounds(period)
        usage_row = await conn.fetchrow(
            """SELECT current_value FROM tenant_quota_usage
               WHERE enterprise_id = $1 AND quota_type = $2
                 AND window_start = $3""",
            enterprise_id, quota_type, start,
        )
        current = int(usage_row["current_value"]) if usage_row else 0
    return QuotaCheck(
        quota_type=quota_type, period=period,
        max_value=max_value, current=current,
        headroom=max(0, max_value - current),
    )
