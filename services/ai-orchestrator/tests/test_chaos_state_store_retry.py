"""
Gap 1 chaos test — state_store retry-with-backoff + DbWriteExhausted.

Proves that:
  G1.1  A transient connection blip on first attempt → retries → succeeds.
  G1.2  All 4 attempts fail → raises DbWriteExhausted with detail intact.
  G1.3  Non-retryable error (ValueError) → propagates immediately, no retries.
  G1.4  Runner's _update_run_status absorbs DbWriteExhausted gracefully
        (logs + continues; doesn't crash run loop).
  G1.5  Runner's _record_node absorbs DbWriteExhausted gracefully.

Retry delays are mocked to zero so the test suite stays fast.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ai_orchestrator.workflow_runtime import state_store as _store


# ─── Fast retry delays so tests run in <1s ─────────────────────────────


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Replace asyncio.sleep with no-op so 0.1+0.5+2.0s backoff doesn't
    slow the test suite."""
    async def _noop(*a, **k): return None
    monkeypatch.setattr("asyncio.sleep", _noop)


# ─── G1.1: transient blip recovers on retry ────────────────────────────


@pytest.mark.asyncio
async def test_retry_recovers_on_second_attempt():
    """First call raises ConnectionRefusedError; second call succeeds."""
    call_count = {"n": 0}

    async def _fn():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ConnectionRefusedError("transient blip")
        return "ok"

    result = await _store._retry_db_write("test_op", _fn)
    assert result == "ok"
    assert call_count["n"] == 2


# ─── G1.2: exhaustion raises DbWriteExhausted ─────────────────────────


@pytest.mark.asyncio
async def test_exhaustion_raises_with_detail():
    """All 4 attempts (1 + 3 retries) raise → DbWriteExhausted with
    last error wrapped."""
    async def _fail():
        raise ConnectionRefusedError("connection refused (pool full)")

    with pytest.raises(_store.DbWriteExhausted) as exc_info:
        await _store._retry_db_write("test_op", _fail)

    assert "test_op" in str(exc_info.value)
    assert "4 attempts" in str(exc_info.value)
    # Original error preserved as __cause__
    assert isinstance(exc_info.value.__cause__, ConnectionRefusedError)


@pytest.mark.asyncio
async def test_exhaustion_attempted_4_times():
    """Pins the retry count — 1 immediate + 3 backoff."""
    call_count = {"n": 0}

    async def _fail():
        call_count["n"] += 1
        raise TimeoutError("timeout")

    with pytest.raises(_store.DbWriteExhausted):
        await _store._retry_db_write("test_op", _fail)
    assert call_count["n"] == 4


# ─── G1.3: non-retryable error propagates immediately ─────────────────


@pytest.mark.asyncio
async def test_value_error_not_retried():
    """Caller-bug exceptions (ValueError, TypeError) propagate on
    first attempt without retry — they won't get better with retries."""
    call_count = {"n": 0}

    async def _bug():
        call_count["n"] += 1
        raise ValueError("bad arg shape")

    with pytest.raises(ValueError):
        await _store._retry_db_write("test_op", _bug)
    assert call_count["n"] == 1  # no retries


@pytest.mark.asyncio
async def test_type_error_not_retried():
    call_count = {"n": 0}

    async def _bug():
        call_count["n"] += 1
        raise TypeError("wrong type")

    with pytest.raises(TypeError):
        await _store._retry_db_write("test_op", _bug)
    assert call_count["n"] == 1


# ─── G1.4: runner._update_run_status absorbs exhaustion ───────────────


@pytest.mark.asyncio
async def test_runner_update_run_status_absorbs_exhaustion(monkeypatch):
    """When state_store exhausts retries during a workflow status
    update, the runner logs + returns None instead of raising. Runner
    loop continues."""
    from ai_orchestrator.workflow_runtime.runner import WorkflowRunner

    async def _always_fail(op, fn):
        raise _store.DbWriteExhausted(f"{op} failed (chaos)")
    monkeypatch.setattr(_store, "_retry_db_write", _always_fail)

    # Should NOT raise — runner absorbs the exhaustion.
    await WorkflowRunner._update_run_status(
        run_id=uuid4(), enterprise_id=uuid4(),
        status="running",
    )


# ─── G1.5: runner._record_node absorbs exhaustion ─────────────────────


@pytest.mark.asyncio
async def test_runner_record_node_absorbs_exhaustion(monkeypatch):
    """Per-node write failure after retries → runner logs + skips,
    doesn't abort the run loop."""
    from ai_orchestrator.workflow_runtime.runner import WorkflowRunner

    async def _failing_upsert(**kwargs):
        raise _store.DbWriteExhausted("upsert_run_node failed (chaos)")
    monkeypatch.setattr(_store, "upsert_run_node", _failing_upsert)

    await WorkflowRunner._record_node(
        run_id=uuid4(),
        node={"node_id": uuid4(), "node_type_catalog_key": "send_email",
                "sequence_order": 0},
        enterprise_id=uuid4(),
        side_effect_class="external",
        status="completed",
        input_data={},
    )


# ─── G1.6: retryable-class detection covers common asyncpg errors ────


@pytest.mark.asyncio
async def test_retryable_class_detection():
    """The heuristic catches the common connection-class error names
    that asyncpg + asyncio emit."""
    # Class-name based
    assert _store._is_retryable(ConnectionRefusedError("x"))
    assert _store._is_retryable(TimeoutError("x"))

    # Message-based fallback
    class _Custom(Exception): pass
    assert _store._is_retryable(_Custom("could not connect to server"))
    assert _store._is_retryable(_Custom("connection reset by peer"))
    assert _store._is_retryable(_Custom("deadlock detected"))

    # Caller bugs should NOT be retryable
    assert not _store._is_retryable(ValueError("bad arg"))
    assert not _store._is_retryable(TypeError("bad type"))
    assert not _store._is_retryable(KeyError("k"))
    assert not _store._is_retryable(AttributeError("attr"))
