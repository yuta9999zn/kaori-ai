"""
asyncpg pool for notification-service — added with Issue #6 outbox.

Mirrors the shape used by services/llm-gateway/db.py so a future ops
runbook can describe both services with one paragraph. Pool sizing is
intentionally small: the only consumer is the outbox poller, which
serialises batches via FOR UPDATE SKIP LOCKED, so 2-3 concurrent
connections is enough.
"""
from __future__ import annotations

from typing import Optional

import asyncpg
import structlog

from config import Settings

log = structlog.get_logger()

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool(settings: Settings) -> asyncpg.Pool:
    """Create the pool. Idempotent — returns the existing pool on
    repeat calls so test fixtures can share one across modules without
    bookkeeping."""
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(
        settings.database_url, min_size=1, max_size=3
    )
    log.info("notification.db.pool_ready", min=1, max=3)
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_db_pool() first.")
    return _pool
