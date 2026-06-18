"""
Tests for Phase 2.7 P2 — services/llm-gateway/tenant_quotas.py.

The gateway version mirrors ai-orchestrator's shared/tenant_quotas.py
but uses the gateway's own pool + sets `app.enterprise_id` GUC LOCAL=
true so the RLS policy on tenant_quotas / tenant_quota_usage lets the
SELECT FOR UPDATE + UPSERT through.

Fail-open semantics differ from the orchestrator copy:
  - fail_open_if_unconfigured: same (default True)
  - fail_open_on_infra_error:  new flag; default True so a quota table
    outage doesn't block the primary LLM path.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from llm_gateway import tenant_quotas  # noqa: E402  registered in conftest.py


# ─── Window math (pure) ────────────────────────────────────────────────


class TestWindowBounds:
    def test_per_minute(self):
        now = datetime(2026, 5, 20, 10, 30, 45, tzinfo=timezone.utc)
        s, e = tenant_quotas._window_bounds("per_minute", now)
        assert s == datetime(2026, 5, 20, 10, 30, 0, tzinfo=timezone.utc)
        assert (e - s).total_seconds() == 60

    def test_per_day(self):
        now = datetime(2026, 5, 20, 23, 59, 59, tzinfo=timezone.utc)
        s, e = tenant_quotas._window_bounds("per_day", now)
        assert s == datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)
        assert (e - s).total_seconds() == 86400

    def test_per_month_december_rolls_over(self):
        now = datetime(2026, 12, 15, 10, 0, 0, tzinfo=timezone.utc)
        s, e = tenant_quotas._window_bounds("per_month", now)
        assert s == datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert e == datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_rolling_bounds_around_now(self):
        now = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        s, e = tenant_quotas._window_bounds("rolling", now)
        # ±1 minute around now
        assert (now - s).total_seconds() == 60
        assert (e - now).total_seconds() == 60

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError):
            tenant_quotas._window_bounds("yearly")


# ─── Pool / connection scaffold ────────────────────────────────────────


def _mock_pool(
    *,
    quota_row=None,
    usage_row=None,
    execute_fail_on=None,
):
    """Build a pool whose acquire→transaction→conn methods yield the
    given quota_row + usage_row. execute_fail_on is a str matched against
    the SQL of `conn.execute` to inject failure (e.g. simulate UPSERT
    failure mid-txn)."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[quota_row, usage_row])

    async def _execute(sql, *args):
        if execute_fail_on and execute_fail_on in sql:
            raise RuntimeError("simulated db failure")
        return None

    conn.execute = AsyncMock(side_effect=_execute)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


# ─── Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consume_within_quota_returns_headroom():
    pool, conn = _mock_pool(
        quota_row={"max_value": 1000, "period": "per_day"},
        usage_row=None,
    )
    out = await tenant_quotas.check_and_consume(
        pool,
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=300,
    )
    assert out is not None
    assert out.quota_type == "llm_tokens_external"
    assert out.max_value == 1000
    assert out.current == 300
    assert out.headroom == 700


@pytest.mark.asyncio
async def test_consume_increments_existing_row():
    pool, conn = _mock_pool(
        quota_row={"max_value": 1000, "period": "per_day"},
        usage_row={"usage_id": uuid4(), "current_value": 250},
    )
    out = await tenant_quotas.check_and_consume(
        pool,
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=100,
    )
    assert out is not None
    assert out.current == 350
    assert out.headroom == 650


# ─── Quota exceeded ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quota_exceeded_raises():
    pool, _ = _mock_pool(
        quota_row={"max_value": 1000, "period": "per_day"},
        usage_row={"usage_id": uuid4(), "current_value": 950},
    )
    with pytest.raises(tenant_quotas.QuotaExceeded) as exc_info:
        await tenant_quotas.check_and_consume(
            pool,
            enterprise_id=uuid4(),
            quota_type="llm_tokens_external",
            amount=100,
        )
    assert exc_info.value.quota_type == "llm_tokens_external"
    assert exc_info.value.max_value == 1000


# ─── Skip / fail-open ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_none_when_unconfigured_fail_open():
    pool, _ = _mock_pool(quota_row=None)
    out = await tenant_quotas.check_and_consume(
        pool,
        enterprise_id=uuid4(),
        quota_type="brand_new_quota",
        amount=1,
        fail_open_if_unconfigured=True,
    )
    assert out is None


@pytest.mark.asyncio
async def test_raises_when_unconfigured_fail_closed():
    pool, _ = _mock_pool(quota_row=None)
    with pytest.raises(tenant_quotas.QuotaExceeded):
        await tenant_quotas.check_and_consume(
            pool,
            enterprise_id=uuid4(),
            quota_type="brand_new_quota",
            amount=1,
            fail_open_if_unconfigured=False,
        )


@pytest.mark.asyncio
async def test_returns_none_when_enterprise_id_empty():
    pool = MagicMock()
    out = await tenant_quotas.check_and_consume(
        pool,
        enterprise_id="",
        quota_type="x",
        amount=1,
    )
    assert out is None
    pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_infra_failure_fails_open_by_default():
    """A connection / pool failure must NOT block the primary call —
    quota outage is recoverable; a 5xx because quota table is down is
    not."""
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=RuntimeError("pool exhausted"))

    out = await tenant_quotas.check_and_consume(
        pool,
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=1,
    )
    assert out is None


@pytest.mark.asyncio
async def test_infra_failure_raises_when_fail_open_false():
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=RuntimeError("pool exhausted"))

    with pytest.raises(RuntimeError):
        await tenant_quotas.check_and_consume(
            pool,
            enterprise_id=uuid4(),
            quota_type="llm_tokens_external",
            amount=1,
            fail_open_on_infra_error=False,
        )


@pytest.mark.asyncio
async def test_negative_amount_raises():
    pool = MagicMock()
    with pytest.raises(ValueError):
        await tenant_quotas.check_and_consume(
            pool,
            enterprise_id=uuid4(),
            quota_type="x",
            amount=-5,
        )
