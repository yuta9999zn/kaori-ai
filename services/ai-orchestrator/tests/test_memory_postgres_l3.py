"""Postgres+pgvector L3 adapter tests.

Mocks asyncpg connection; no live DB. Validates the SQL shape +
behaviour contract — actual SQL exec is exercised in CI's
migration-test workflow against the real Postgres container.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.memory.embedding_worker import (
    embed_pending_for_tenant,
)
from ai_orchestrator.reasoning.memory.postgres_l3 import (
    PostgresTierStore,
    _vec_to_pg,
)
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord,
    MemoryTier,
    MemoryType,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")


# ─── _vec_to_pg ─────────────────────────────────────────────────────


class TestVecToPg:
    def test_basic(self):
        assert _vec_to_pg([1.0, 2.0, 3.0]) == "[1.0,2.0,3.0]"

    def test_empty(self):
        assert _vec_to_pg([]) == "[]"

    def test_int_input_coerced_to_float(self):
        out = _vec_to_pg([1, 2, 3])
        assert "1.0" in out


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.execute   = AsyncMock(return_value="DELETE 0")
    conn.fetchrow  = AsyncMock(return_value=None)
    conn.fetch     = AsyncMock(return_value=[])
    return conn


@pytest.fixture
def store(mock_conn):
    @asynccontextmanager
    async def _acq(_tenant):
        yield mock_conn
    return PostgresTierStore(acquire_for_tenant=_acq)


# ─── put ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_executes_insert(store, mock_conn):
    rec = MemoryRecord(tenant_id=T1, memory_type=MemoryType.DECISION,
                        content="approved INV-001")
    await store.put(rec)
    mock_conn.execute.assert_awaited_once()
    sql = mock_conn.execute.await_args.args[0]
    assert "INSERT INTO memory_l3" in sql
    assert "ON CONFLICT" in sql
    # Tier overwritten on put
    assert rec.tier == MemoryTier.L3_CONSOLIDATED


# ─── get ────────────────────────────────────────────────────────────


def _row(record_id=None, **kw):
    row = MagicMock()
    base = {
        "record_id":                 record_id or uuid4(),
        "tenant_id":                 T1,
        "memory_type":               "DECISION",
        "content":                   "x",
        "session_id":                None,
        "entity_id":                 None,
        "occurred_at":               __import__("datetime").datetime(2026, 5, 17),
        "user_flagged_important":    False,
        "linked_outcome_value":      0,
        "session_appearance_count":  0,
        "extra_metadata":            {},
        "confidence":                0.70,   # ADR-0030 trust columns
        "trust_source":              None,
        "last_verified_at":          None,
    }
    base.update(kw)
    row.__getitem__ = lambda _s, k: base[k]
    return row


@pytest.mark.asyncio
async def test_get_round_trip(store, mock_conn):
    rid = uuid4()
    mock_conn.fetchrow = AsyncMock(return_value=_row(record_id=rid, content="hello"))
    got = await store.get(T1, rid)
    assert got is not None
    assert got.record_id == rid
    assert got.content == "hello"
    assert got.memory_type == MemoryType.DECISION


@pytest.mark.asyncio
async def test_get_miss_returns_none(store, mock_conn):
    mock_conn.fetchrow = AsyncMock(return_value=None)
    got = await store.get(T1, uuid4())
    assert got is None


# ─── list_all ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_all_returns_records(store, mock_conn):
    mock_conn.fetch = AsyncMock(return_value=[_row(), _row()])
    out = await store.list_all(T1)
    assert len(out) == 2


# ─── delete ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_one_row_returns_true(store, mock_conn):
    mock_conn.execute = AsyncMock(return_value="DELETE 1")
    assert await store.delete(T1, uuid4()) is True


@pytest.mark.asyncio
async def test_delete_no_row_returns_false(store, mock_conn):
    mock_conn.execute = AsyncMock(return_value="DELETE 0")
    assert await store.delete(T1, uuid4()) is False


# ─── semantic_search ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_semantic_search_filters_by_model_and_orders_by_distance(store, mock_conn):
    """Verifies the SQL fragment + filter clause; mocked row.distance."""
    rows = [_row(distance=0.1), _row(distance=0.2), _row(distance=0.3)]
    mock_conn.fetch = AsyncMock(return_value=rows)
    out = await store.semantic_search(T1, [0.5] * 1024, top_k=3,
                                        model_name="bge-m3")
    assert len(out) == 3
    # Returned as (record, distance) tuples
    assert out[0][1] == pytest.approx(0.1)
    sql = mock_conn.fetch.await_args.args[0]
    assert "embedding <=>" in sql
    assert "embedding_model = $2" in sql
    assert "ORDER BY embedding <=>" in sql


# ─── set_embedding ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_embedding_returns_true_on_hit(store, mock_conn):
    mock_conn.fetchrow = AsyncMock(return_value=_row())
    ok = await store.set_embedding(T1, uuid4(), [0.0] * 1024)
    assert ok is True


@pytest.mark.asyncio
async def test_set_embedding_returns_false_on_miss(store, mock_conn):
    mock_conn.fetchrow = AsyncMock(return_value=None)
    ok = await store.set_embedding(T1, uuid4(), [0.0] * 1024)
    assert ok is False


# ─── list_unembedded ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_unembedded_uses_null_filter(store, mock_conn):
    mock_conn.fetch = AsyncMock(return_value=[_row()])
    out = await store.list_unembedded(T1, limit=10)
    assert len(out) == 1
    sql = mock_conn.fetch.await_args.args[0]
    assert "embedding IS NULL" in sql


# ─── embedding_worker ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_pending_calls_gateway_per_record(store, mock_conn):
    """Worker pulls pending → embeds → set_embedding for each."""
    rec1 = MemoryRecord(tenant_id=T1, memory_type=MemoryType.DECISION, content="a")
    rec2 = MemoryRecord(tenant_id=T1, memory_type=MemoryType.DECISION, content="b")
    store.list_unembedded = AsyncMock(return_value=[rec1, rec2])
    store.set_embedding   = AsyncMock(return_value=True)

    from unittest.mock import patch
    embed_resp = MagicMock()
    embed_resp.raise_for_status = MagicMock()
    embed_resp.json = MagicMock(return_value={"vector": [0.1] * 1024, "dim": 1024,
                                                "model_used": "bge-m3", "latency_ms": 5})
    client = AsyncMock()
    client.post = AsyncMock(return_value=embed_resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.memory.embedding_worker.httpx.AsyncClient",
                return_value=client):
        n = await embed_pending_for_tenant(store, T1)
    assert n == 2
    assert store.set_embedding.await_count == 2


@pytest.mark.asyncio
async def test_embed_pending_empty_short_circuits(store, mock_conn):
    store.list_unembedded = AsyncMock(return_value=[])
    n = await embed_pending_for_tenant(store, T1)
    assert n == 0


@pytest.mark.asyncio
async def test_embed_pending_gateway_failure_skips_record(store, mock_conn):
    rec = MemoryRecord(tenant_id=T1, memory_type=MemoryType.DECISION, content="x")
    store.list_unembedded = AsyncMock(return_value=[rec])
    store.set_embedding   = AsyncMock(return_value=True)

    from unittest.mock import patch
    import httpx as _hx
    client = AsyncMock()
    client.post = AsyncMock(side_effect=_hx.HTTPError("gateway down"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.memory.embedding_worker.httpx.AsyncClient",
                return_value=client):
        n = await embed_pending_for_tenant(store, T1)
    assert n == 0
    store.set_embedding.assert_not_awaited()
