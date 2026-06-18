"""
Gap 4 chaos test — llm-gateway pool init + acquire retry wrapper.

The gateway pool is unique in that it's NOT tenant-scoped — every
/v1/* call hits the same pool. A blip during startup or a DB restart
mid-day would 5xx every subsequent dispatch. Gap 4 mitigation:

  init_db_pool      — 1 + 3 retries (0.5s/2s/5s) on create failure;
                       fails LOUDLY on final exhaustion so K8s can
                       restart the pod.
  ensure_pool_alive — detects pool._closed flag (set after DB restart
                       severs all connections); re-inits transparently.
  acquire_with_retry — 1 + 3 retries (0.1s/0.5s/2s) on connection-
                        class failure during pool.acquire().

Tests pin each path with asyncio.sleep monkey-patched to zero.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from llm_gateway import db


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _noop(*a, **k): return None
    monkeypatch.setattr("asyncio.sleep", _noop)


@pytest.fixture(autouse=True)
def _reset_pool():
    """Each test starts with no pool — avoids leakage from a prior
    test's successful init keeping module state alive."""
    db._pool = None
    yield
    db._pool = None


# ─── G4.1: init retries on transient failure ────────────────────────


@pytest.mark.asyncio
async def test_init_retries_and_recovers(monkeypatch):
    """First create_pool raises; second succeeds. init_db_pool returns
    without raising; _pool is the second attempt."""
    call_count = {"n": 0}

    async def _flaky_create_pool(*a, **k):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ConnectionRefusedError("transient blip")
        return MagicMock(_closed=False)

    monkeypatch.setattr("asyncpg.create_pool", _flaky_create_pool)
    await db.init_db_pool()
    assert call_count["n"] == 2
    assert db._pool is not None


# ─── G4.2: init exhaustion raises RuntimeError ──────────────────────


@pytest.mark.asyncio
async def test_init_exhaustion_raises(monkeypatch):
    """All 4 attempts fail → RuntimeError with detail + last_exc as
    __cause__. The service should crash on this, NOT silently start
    with a None pool."""
    async def _always_fail(*a, **k):
        raise ConnectionRefusedError("DB unreachable")

    monkeypatch.setattr("asyncpg.create_pool", _always_fail)

    with pytest.raises(RuntimeError) as exc_info:
        await db.init_db_pool()
    assert "init failed" in str(exc_info.value)
    assert "4 attempts" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ConnectionRefusedError)


# ─── G4.3: ensure_pool_alive re-inits on closed pool ────────────────


@pytest.mark.asyncio
async def test_ensure_pool_alive_re_inits_closed_pool(monkeypatch):
    """When _pool._closed is True (e.g. after DB restart killed all
    connections), ensure_pool_alive transparently re-inits."""
    # First: a closed pool, then a fresh one.
    closed_pool = MagicMock(_closed=True)
    fresh_pool = MagicMock(_closed=False)
    db._pool = closed_pool

    create_count = {"n": 0}
    async def _create(*a, **k):
        create_count["n"] += 1
        return fresh_pool
    monkeypatch.setattr("asyncpg.create_pool", _create)

    result = await db.ensure_pool_alive()
    assert result is fresh_pool
    assert create_count["n"] == 1


@pytest.mark.asyncio
async def test_ensure_pool_alive_returns_existing_when_open(monkeypatch):
    """Open pool is returned as-is — no unnecessary re-init."""
    open_pool = MagicMock(_closed=False)
    db._pool = open_pool

    # If anything tries to create_pool, fail loudly.
    monkeypatch.setattr("asyncpg.create_pool",
                          AsyncMock(side_effect=AssertionError("should not re-init")))

    result = await db.ensure_pool_alive()
    assert result is open_pool


# ─── G4.4: acquire_with_retry retries connection errors ─────────────


@pytest.mark.asyncio
async def test_acquire_retries_on_connection_error(monkeypatch):
    """When ensure_pool_alive() raises a connection-class error on
    first attempt but succeeds on second, `async with
    acquire_with_retry() as conn` yields the conn from the second
    attempt's pool."""
    fresh_pool = MagicMock(_closed=False)
    # asyncpg-style: pool.acquire() returns an async-CM that yields conn
    sentinel_conn = MagicMock(name="conn_from_fresh_pool")
    acquired_cm = MagicMock()
    acquired_cm.__aenter__ = AsyncMock(return_value=sentinel_conn)
    acquired_cm.__aexit__ = AsyncMock(return_value=False)
    fresh_pool.acquire = MagicMock(return_value=acquired_cm)

    call_count = {"n": 0}
    async def _flaky_ensure():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ConnectionRefusedError("first try fail")
        return fresh_pool

    monkeypatch.setattr(db, "ensure_pool_alive", _flaky_ensure)

    async with db.acquire_with_retry() as conn:
        assert conn is sentinel_conn
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_acquire_exhaustion_propagates_last_exc(monkeypatch):
    """All 4 acquire attempts fail → original ConnectionRefusedError
    propagates (not wrapped in RuntimeError) so callers can tell the
    real failure class from the trace."""
    async def _always_fail():
        raise ConnectionRefusedError("pool dead")
    monkeypatch.setattr(db, "ensure_pool_alive", _always_fail)

    with pytest.raises(ConnectionRefusedError):
        async with db.acquire_with_retry() as _:
            pass


# ─── G4.5: caller-bug exceptions propagate immediately ──────────────


@pytest.mark.asyncio
async def test_acquire_value_error_not_retried(monkeypatch):
    """ValueError = caller bug → no retries, propagate first attempt."""
    call_count = {"n": 0}
    async def _bug():
        call_count["n"] += 1
        raise ValueError("bad arg")
    monkeypatch.setattr(db, "ensure_pool_alive", _bug)

    with pytest.raises(ValueError):
        async with db.acquire_with_retry() as _:
            pass
    assert call_count["n"] == 1  # no wasted retries


# ─── G4.6: classification heuristic ─────────────────────────────────


def test_is_pool_retryable_class_names():
    """Common connection-class error names should retry."""
    assert db._is_pool_retryable(ConnectionRefusedError("x"))
    assert db._is_pool_retryable(TimeoutError("x"))

    class _Custom(Exception): pass
    assert db._is_pool_retryable(_Custom("connection reset by peer"))
    assert db._is_pool_retryable(_Custom("too many connections"))
    assert db._is_pool_retryable(_Custom("server closed the connection"))

    assert not db._is_pool_retryable(ValueError("x"))
    assert not db._is_pool_retryable(TypeError("x"))
