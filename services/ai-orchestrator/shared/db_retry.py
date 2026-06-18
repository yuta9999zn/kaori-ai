"""
Shared DB-write retry helper — Gap 1 / Gap 2 of chaos-matrix.md.

Was originally introduced in workflow_runtime/state_store.py (Gap 1).
Hoisted to shared/ so reasoning/memory/postgres_l3.py + other write-
heavy modules can reuse without cross-layer import.

API
---
  DbWriteExhausted   — exception raised after all retries fail
  retry_db_write()   — wrap any async DB call with retry+backoff

Retry policy: 1 immediate + 3 backoff attempts (0.1s / 0.5s / 2.0s).
Classifier `is_retryable()` returns True for connection-class /
timeout / deadlock errors; False for ValueError / TypeError /
KeyError / AttributeError (caller bugs — retrying won't help).
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, TypeVar

import structlog

log = structlog.get_logger()


class DbWriteExhausted(Exception):
    """All retry attempts for a DB write exhausted. Caller should log +
    emit metric + mark the unit-of-work gracefully."""


_T = TypeVar("_T")

_RETRY_DELAYS_S = (0.1, 0.5, 2.0)


def is_retryable(exc: BaseException) -> bool:
    """Heuristic: retry on connection-class + serialisation errors;
    propagate caller-bug exceptions immediately."""
    if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
        return False
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if any(s in name for s in (
        "connection", "interface", "pool", "operationalerror",
        "querycancel", "timeout", "deadlock",
    )):
        return True
    if any(s in msg for s in (
        "connection", "pool", "timeout", "deadlock", "could not",
        "server closed", "reset by peer",
    )):
        return True
    return False


async def retry_db_write(
    op_name: str,
    fn: Callable[[], Awaitable[_T]],
) -> _T:
    """Run `fn()` with 1 + 3 retry attempts on connection-class
    failures. Raises DbWriteExhausted after exhaustion.

    Each retry logged at warning; exhaustion at error. Ops dashboards
    can chart `state_store.retry` + `state_store.exhausted` rates."""
    last_exc: Optional[BaseException] = None
    for i, delay in enumerate((0.0,) + _RETRY_DELAYS_S):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            return await fn()
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            if not is_retryable(exc):
                raise
            log.warning(
                "state_store.retry",
                op=op_name, attempt=i + 1,
                of=len(_RETRY_DELAYS_S) + 1,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
            continue
    log.error(
        "state_store.exhausted",
        op=op_name, attempts=len(_RETRY_DELAYS_S) + 1,
        last_error_type=type(last_exc).__name__ if last_exc else None,
        last_detail=str(last_exc)[:200] if last_exc else None,
    )
    raise DbWriteExhausted(
        f"{op_name} failed after {len(_RETRY_DELAYS_S) + 1} attempts: {last_exc}"
    ) from last_exc
