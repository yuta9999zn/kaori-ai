"""
asyncpg pool for the llm-gateway service.

Same shape as services/data-pipeline/shared/db.py (without the G4a
acquire_for_tenant helper — the gateway is system-wide, not tenant-
scoped at the connection level). Kept minimal.

Gap 4 (chaos-matrix.md follow-up, 2026-05-20):
  - init_db_pool now retries pool creation 3 times on failure with
    exponential backoff so a transient DB blip during startup doesn't
    leave the service permanently broken.
  - ensure_pool_alive() detects pool-closed state and lazily re-inits
    after a DB restart.
  - acquire_with_retry() helper retries pool.acquire() on connection-
    class errors with backoff; routers can swap pool.acquire() for
    this when they want to absorb transient failures.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import structlog

log = structlog.get_logger()

_pool: Optional[asyncpg.Pool] = None
_dsn: Optional[str] = None


_INIT_RETRY_DELAYS_S = (0.5, 2.0, 5.0)  # 3 retries; total ≈ 7.5s worst case
_ACQUIRE_RETRY_DELAYS_S = (0.1, 0.5, 2.0)


def _resolve_dsn() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://kaori_app:kaori_app_password@localhost:5432/kaori",
    )


async def init_db_pool() -> None:
    """Create the pool with bounded retries. Raises on final failure
    so the service fails LOUDLY at startup if DB is genuinely gone."""
    global _pool, _dsn
    _dsn = _resolve_dsn()
    last_exc: Optional[BaseException] = None
    for i, delay in enumerate((0.0,) + _INIT_RETRY_DELAYS_S):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            _pool = await asyncpg.create_pool(_dsn, min_size=2, max_size=5)
            log.info("llm_gateway.db.pool_ready",
                       attempt=i + 1)
            return
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            log.warning(
                "llm_gateway.db.pool_init_retry",
                attempt=i + 1,
                of=len(_INIT_RETRY_DELAYS_S) + 1,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
    log.error(
        "llm_gateway.db.pool_init_exhausted",
        attempts=len(_INIT_RETRY_DELAYS_S) + 1,
        last_error_type=type(last_exc).__name__ if last_exc else None,
    )
    raise RuntimeError(
        f"llm-gateway DB pool init failed after "
        f"{len(_INIT_RETRY_DELAYS_S) + 1} attempts: {last_exc}"
    ) from last_exc


async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_db_pool() first.")
    return _pool


async def ensure_pool_alive() -> asyncpg.Pool:
    """Return a live pool. If the pool reports closed (e.g. after a
    DB restart killed all connections), re-init lazily before returning.

    Use this when a hot path needs to be resilient to pool death;
    get_pool() is fine for paths that fire often + can tolerate a
    one-time 500 after a DB outage."""
    global _pool
    if _pool is None:
        await init_db_pool()
        return _pool  # type: ignore[return-value]
    if _pool._closed:  # asyncpg.Pool exposes _closed flag
        log.warning("llm_gateway.db.pool_closed_re_init")
        await init_db_pool()
    return _pool  # type: ignore[return-value]


def _is_pool_retryable(exc: BaseException) -> bool:
    """Same heuristic as state_store._is_retryable but for the gateway
    pool's acquire path. Pool-class + connection-class errors retry."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if isinstance(exc, (ValueError, TypeError)):
        return False
    if any(s in name for s in (
        "connection", "interfaceerror", "pool", "timeout",
        "operationalerror",
    )):
        return True
    if any(s in msg for s in (
        "connection", "pool", "server closed", "reset by peer",
        "too many",
    )):
        return True
    return False


async def _resolve_acquire_cm():
    """Internal — fetch the asyncpg-native acquire context manager with
    retries on connection-class failures. Returns the CM uncalled so
    `acquire_with_retry` can re-yield it."""
    last_exc: Optional[BaseException] = None
    for i, delay in enumerate((0.0,) + _ACQUIRE_RETRY_DELAYS_S):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            pool = await ensure_pool_alive()
            return pool.acquire()
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_pool_retryable(exc):
                raise
            log.warning(
                "llm_gateway.db.acquire_retry",
                attempt=i + 1,
                of=len(_ACQUIRE_RETRY_DELAYS_S) + 1,
                error_type=type(exc).__name__,
            )
    log.error(
        "llm_gateway.db.acquire_exhausted",
        attempts=len(_ACQUIRE_RETRY_DELAYS_S) + 1,
        last_error_type=type(last_exc).__name__ if last_exc else None,
    )
    raise last_exc  # type: ignore[misc]


@asynccontextmanager
async def acquire_with_retry():
    """Async context manager wrapping pool.acquire() with retries.

    Usage:
        async with acquire_with_retry() as conn:
            await conn.execute("SELECT 1")

    On exhaustion, raises the ORIGINAL exception type so the caller
    sees the real failure (PostgresConnectionError / TooManyConnections /
    etc.) — don't disguise as RuntimeError. Auditors can distinguish
    'pool dead' from 'query failed' from the trace.
    """
    cm = await _resolve_acquire_cm()
    async with cm as conn:
        yield conn
