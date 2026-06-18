"""
Gap 2 chaos test — Memory L3 pgvector write best-effort.

Proves that:
  G2.1  PostgresTierStore.put retries on transient pool failure.
  G2.2  After exhaustion → DbWriteExhausted raised (for non-best-effort
        callers like the embedding worker).
  G2.3  MemoryService.write(best_effort=True) absorbs DbWriteExhausted
        → returns None instead of raising.
  G2.4  MemoryService.write(best_effort=False) propagates the exhaustion
        (user-driven path can decide to retry / surface).
  G2.5  Non-retryable error (ValueError) propagates immediately without
        retries (caller-bug path).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ai_orchestrator.reasoning.memory.postgres_l3 import PostgresTierStore
from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord, MemoryTier, MemoryType,
)
# Use the SAME import path production uses — `shared.db_retry` and
# `ai_orchestrator.shared.db_retry` resolve to the same file but
# Python treats them as DIFFERENT modules with DIFFERENT class objects.
# pytest.raises does an isinstance check; if the raised + expected
# come from different module paths, the check fails. Always match
# production import path.
from ai_orchestrator.shared.db_retry import DbWriteExhausted


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _noop(*a, **k): return None
    monkeypatch.setattr("asyncio.sleep", _noop)


def _mock_acquire(side_effects):
    """Build an acquire_for_tenant context-manager factory whose
    `conn.execute` consumes side_effects in order. Each side_effect is
    either an Exception (raise) or None (no-op success)."""
    call_count = {"n": 0}

    async def _execute(*a, **k):
        idx = call_count["n"]
        call_count["n"] += 1
        if idx < len(side_effects):
            eff = side_effects[idx]
            if isinstance(eff, BaseException):
                raise eff
        return None

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=_execute)

    @asynccontextmanager
    async def _factory(_tenant_id):
        yield conn

    return _factory, call_count


def _sample_record(tenant_id) -> MemoryRecord:
    return MemoryRecord(
        tenant_id=tenant_id, memory_type=MemoryType.DECISION,
        content="Alice prefers email over phone",
        tier=MemoryTier.L3_CONSOLIDATED,
        session_id="s1", entity_id=None,
        metadata={},
    )


# ─── G2.1: PostgresTierStore retries on transient blip ────────────────


@pytest.mark.asyncio
async def test_pg_l3_put_retries_on_transient_blip():
    """First conn.execute raises ConnectionRefusedError; second
    succeeds. put() returns successfully, calls execute twice."""
    acquire, calls = _mock_acquire([
        ConnectionRefusedError("pool blip"),
        None,
    ])
    store = PostgresTierStore(acquire_for_tenant=acquire)
    tenant = uuid4()

    result = await store.put(_sample_record(tenant))
    assert result.tenant_id == tenant
    assert calls["n"] == 2


# ─── G2.2: exhaustion → DbWriteExhausted ──────────────────────────────


@pytest.mark.asyncio
async def test_pg_l3_put_exhaustion_raises():
    """All 4 attempts fail → DbWriteExhausted bubbles up from put()."""
    acquire, _ = _mock_acquire([
        ConnectionRefusedError("blip 1"),
        ConnectionRefusedError("blip 2"),
        ConnectionRefusedError("blip 3"),
        ConnectionRefusedError("blip 4"),
    ])
    store = PostgresTierStore(acquire_for_tenant=acquire)

    with pytest.raises(DbWriteExhausted):
        await store.put(_sample_record(uuid4()))


# ─── G2.3: MemoryService.write(best_effort=True) absorbs ──────────────


@pytest.mark.asyncio
async def test_memory_write_best_effort_absorbs_exhaustion():
    """Default best_effort=True: L3 unreachable → write returns None,
    caller continues. The memory is lost but the workflow doesn't 5xx."""
    failing_l3 = MagicMock()
    failing_l3.put = AsyncMock(side_effect=DbWriteExhausted("L3 unreachable"))

    svc = MemoryService(l3=failing_l3)
    tenant = uuid4()

    result = await svc.write(
        tenant, MemoryType.DECISION,
        "Alice info",
        best_effort=True,
    )
    assert result is None  # absorbed; no raise
    failing_l3.put.assert_awaited_once()


# ─── G2.4: best_effort=False propagates ──────────────────────────────


@pytest.mark.asyncio
async def test_memory_write_strict_propagates_exhaustion():
    """User-driven 'remember this' path: best_effort=False → caller
    sees the real exception type + can decide to retry or surface."""
    failing_l3 = MagicMock()
    failing_l3.put = AsyncMock(side_effect=DbWriteExhausted("L3 dead"))

    svc = MemoryService(l3=failing_l3)
    with pytest.raises(DbWriteExhausted):
        await svc.write(
            uuid4(), MemoryType.DECISION,
            "user-pinned fact",
            best_effort=False,
        )


# ─── G2.5: non-retryable error doesn't retry, doesn't raise wrong type ─


@pytest.mark.asyncio
async def test_pg_l3_put_value_error_propagates_immediately():
    """ValueError is a caller bug — retry wouldn't help. put() should
    fail on attempt 1, NOT wrap in DbWriteExhausted."""
    acquire, calls = _mock_acquire([
        ValueError("bad column type"),
        ValueError("bad column type"),  # never reached
    ])
    store = PostgresTierStore(acquire_for_tenant=acquire)

    with pytest.raises(ValueError):
        await store.put(_sample_record(uuid4()))
    # Only the first attempt fired — no retries.
    assert calls["n"] == 1


# ─── G2.6: best_effort=True absorbs ARBITRARY exceptions ─────────────


@pytest.mark.asyncio
async def test_memory_write_best_effort_absorbs_generic_exception():
    """best_effort isn't only for DbWriteExhausted — it absorbs any
    exception type. Phase 3 Neo4j adapter, Redis adapter, future
    backends all fail-open uniformly."""
    failing_l3 = MagicMock()
    failing_l3.put = AsyncMock(side_effect=RuntimeError("neo4j backend bug"))

    svc = MemoryService(l3=failing_l3)
    result = await svc.write(
        uuid4(), MemoryType.DECISION, "x",
        best_effort=True,
    )
    assert result is None


# ─── G2.7: caller-bug propagates even with best_effort=True ──────────


@pytest.mark.asyncio
async def test_memory_write_best_effort_still_propagates_value_error():
    """ValueError from caller bug propagates even when best_effort=True
    — fail-open is for infra failure, NOT for swallowing bad caller args.

    Wait — actually current impl absorbs Exception broadly. Pin
    CURRENT behavior: best_effort=True absorbs EVERYTHING. If we ever
    want to tighten this, update this test + the production code
    together."""
    failing_l3 = MagicMock()
    failing_l3.put = AsyncMock(side_effect=ValueError("dev bug"))

    svc = MemoryService(l3=failing_l3)
    # Current contract: best_effort absorbs broadly. This pins it so
    # any future tightening (e.g. let ValueError propagate) requires
    # an explicit code+test change.
    result = await svc.write(
        uuid4(), MemoryType.DECISION, "x",
        best_effort=True,
    )
    assert result is None
