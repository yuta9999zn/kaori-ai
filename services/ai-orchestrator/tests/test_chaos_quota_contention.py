"""
Gap 5 chaos test — tenant_quotas under SELECT FOR UPDATE contention.

When two workers hit the same (tenant, quota_type, window) row
simultaneously, Postgres serialises them via FOR UPDATE. If one holds
the lock too long, the second blocks indefinitely. Gap 5 mitigation:

  1. SET LOCAL lock_timeout = '2s'    inside the txn
  2. SET LOCAL statement_timeout = '5s'  inside the txn
  3. Function-level fail_open_on_infra_error=True absorbs the
     QueryCanceledError → returns sentinel QuotaCheck.

These tests prove the mitigation by injecting timeout / connection
failures at the asyncpg layer and asserting the caller gets a
"infra_error" sentinel back, NOT an exception.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ai_orchestrator.shared import tenant_quotas


# ─── Helpers ──────────────────────────────────────────────────────────


def _stub_acquire(monkeypatch, conn):
    @asynccontextmanager
    async def _fake(_eid):
        yield conn
    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _fake)


# ─── G5.1: lock_timeout fires → fail-open ────────────────────────────


@pytest.mark.asyncio
async def test_lock_timeout_returns_infra_error_sentinel(monkeypatch):
    """asyncpg raises QueryCanceledError when lock_timeout fires.
    Function-level wrapper absorbs → returns sentinel."""

    # Conn that succeeds the SET LOCAL pair but raises on the first
    # SELECT FOR UPDATE.
    conn = AsyncMock()
    set_local_count = {"n": 0}

    async def _exec(sql, *args):
        if "SET LOCAL" in sql:
            set_local_count["n"] += 1
            return None
        return None
    conn.execute = AsyncMock(side_effect=_exec)

    # Imagine: quota row found → tries SELECT FOR UPDATE → lock_timeout fires
    async def _fetchrow(sql, *args):
        if "FROM tenant_quotas" in sql:
            return {"max_value": 1000, "period": "rolling"}
        if "FOR UPDATE" in sql:
            # Simulate lock_timeout firing
            raise RuntimeError("canceling statement due to lock timeout")
        return None
    conn.fetchrow = AsyncMock(side_effect=_fetchrow)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    _stub_acquire(monkeypatch, conn)

    result = await tenant_quotas.check_and_consume(
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=100,
    )

    # CONTRACT: lock_timeout → fail-open sentinel, NOT exception.
    assert result.period == "infra_error"
    assert result.max_value == 2**31

    # SET LOCAL was actually issued (proves the timeout config is alive)
    assert set_local_count["n"] == 2  # lock_timeout + statement_timeout


# ─── G5.2: statement_timeout fires → fail-open ───────────────────────


@pytest.mark.asyncio
async def test_statement_timeout_returns_infra_error_sentinel(monkeypatch):
    """5s statement_timeout firing during the SELECT acquires."""
    conn = AsyncMock()

    async def _exec(sql, *args):
        return None
    conn.execute = AsyncMock(side_effect=_exec)

    # First fetchrow (lookup quota_row) hangs → timeout
    async def _fetchrow(sql, *args):
        raise RuntimeError("canceling statement due to statement timeout")
    conn.fetchrow = AsyncMock(side_effect=_fetchrow)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    _stub_acquire(monkeypatch, conn)

    result = await tenant_quotas.check_and_consume(
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=100,
    )
    assert result.period == "infra_error"


# ─── G5.3: fail_open_on_infra_error=False propagates ──────────────────


@pytest.mark.asyncio
async def test_fail_closed_flag_propagates_timeout(monkeypatch):
    """For test / audit contexts: caller may want to SEE the
    infra failure. flag=False forces propagation."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)

    async def _raise(*a, **k):
        raise RuntimeError("canceling statement due to lock timeout")
    conn.fetchrow = AsyncMock(side_effect=_raise)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    _stub_acquire(monkeypatch, conn)

    with pytest.raises(RuntimeError, match="lock timeout"):
        await tenant_quotas.check_and_consume(
            enterprise_id=uuid4(),
            quota_type="llm_tokens_external",
            amount=100,
            fail_open_on_infra_error=False,
        )


# ─── G5.4: QuotaExceeded still propagates (NOT chaos) ─────────────────


@pytest.mark.asyncio
async def test_quota_exceeded_still_propagates_even_with_fail_open(monkeypatch):
    """fail_open is ONLY for infra errors. Intentional QuotaExceeded
    rejection must bubble up even when fail_open=True."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)

    fetched = [
        {"max_value": 100, "period": "rolling", "fail_open": True},  # quota
        {"usage_id": uuid4(), "current_value": 95},                  # usage
    ]

    async def _fr(*a, **k):
        return fetched.pop(0) if fetched else None
    conn.fetchrow = AsyncMock(side_effect=_fr)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    _stub_acquire(monkeypatch, conn)

    # 95 + 100 > 100 → QuotaExceeded
    with pytest.raises(tenant_quotas.QuotaExceeded):
        await tenant_quotas.check_and_consume(
            enterprise_id=uuid4(),
            quota_type="llm_tokens_external",
            amount=100,
        )


# ─── G5.5: pool exhausted → fail-open ────────────────────────────────


@pytest.mark.asyncio
async def test_pool_acquire_failure_returns_sentinel(monkeypatch):
    """When acquire_for_tenant itself fails (pool exhausted, DB down),
    function wrapper absorbs → sentinel."""
    @asynccontextmanager
    async def _fake(_eid):
        raise ConnectionRefusedError("pool exhausted / DB unreachable")
        yield None  # unreachable
    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _fake)

    result = await tenant_quotas.check_and_consume(
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=100,
    )
    assert result.period == "infra_error"
    assert result.headroom == 2**31
