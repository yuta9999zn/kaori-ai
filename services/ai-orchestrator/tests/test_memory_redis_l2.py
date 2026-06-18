"""Redis L2 adapter tests.

Mocks the redis.asyncio.Redis client. No live Redis. Validates:
  * Key prefix + index discipline (mem:l2:{tenant}:...)
  * 24h TTL via SETEX
  * Tenant isolation enforced by key prefix (cross-tenant get returns None)
  * Stale index entries cleaned up on list_all
  * forget wipes the index + all record keys
  * Round-trip (de)serialisation preserves field shape
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.memory.redis_l2 import (
    KEY_PREFIX,
    L2_TTL_SECONDS,
    RedisTierStore,
    _dict_to_record,
    _record_to_dict,
)
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord,
    MemoryTier,
    MemoryType,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")


# ─── (de)serialisation ──────────────────────────────────────────────


class TestSerialisation:

    def test_round_trip(self):
        ent_id = uuid4()
        rec = MemoryRecord(
            tenant_id=T1, memory_type=MemoryType.EPISODIC,
            content="khách hàng VIP",
            session_id="s1", entity_id=ent_id,
            user_flagged_important=True, linked_outcome_value=20_000_000,
            session_appearance_count=3,
            metadata={"foo": "bar", "n": 1},
        )
        d = _record_to_dict(rec)
        out = _dict_to_record(d)
        assert out.tenant_id   == T1
        assert out.content     == "khách hàng VIP"
        assert out.session_id  == "s1"
        assert out.entity_id   == ent_id
        assert out.user_flagged_important is True
        assert out.linked_outcome_value == 20_000_000
        assert out.metadata    == {"foo": "bar", "n": 1}

    def test_optional_fields_nullable(self):
        rec = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x")
        d = _record_to_dict(rec)
        assert d["session_id"] is None
        assert d["entity_id"] is None
        out = _dict_to_record(d)
        assert out.session_id is None
        assert out.entity_id is None


# ─── Key helpers ────────────────────────────────────────────────────


class TestKeyDiscipline:

    def test_record_key_prefix(self):
        rid = uuid4()
        k = RedisTierStore._record_key(T1, rid)
        assert k.startswith(f"{KEY_PREFIX}:{T1}:")
        assert k.endswith(str(rid))

    def test_index_key_prefix(self):
        k = RedisTierStore._index_key(T1)
        assert k == f"{KEY_PREFIX}:{T1}:index"

    def test_different_tenants_have_disjoint_prefixes(self):
        rid = uuid4()
        k1 = RedisTierStore._record_key(T1, rid)
        k2 = RedisTierStore._record_key(T2, rid)
        assert k1 != k2
        # K-1: cross-tenant get cannot collide
        assert str(T1) in k1 and str(T2) not in k1


# ─── Redis client mock fixture ──────────────────────────────────────


def _make_pipeline():
    """Pipeline must support async context manager + execute()."""
    pipe = MagicMock()
    pipe.setex   = MagicMock()
    pipe.sadd    = MagicMock()
    pipe.expire  = MagicMock()
    pipe.delete  = MagicMock()
    pipe.srem    = MagicMock()
    pipe.execute = AsyncMock(return_value=[1, 1, 1])
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__  = AsyncMock(return_value=None)
    return pipe


@pytest.fixture
def redis_mock():
    r = MagicMock()
    r.pipeline = MagicMock(side_effect=_make_pipeline)
    r.get      = AsyncMock(return_value=None)
    r.smembers = AsyncMock(return_value=set())
    r.mget     = AsyncMock(return_value=[])
    r.srem     = AsyncMock(return_value=0)
    r.delete   = AsyncMock(return_value=0)
    return r


@pytest.fixture
def store(redis_mock):
    return RedisTierStore(redis_client=redis_mock)


# ─── put ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_uses_setex_with_24h_ttl(store, redis_mock):
    rec = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x")
    pipes_used = []

    def _capture_pipe():
        p = _make_pipeline()
        pipes_used.append(p)
        return p
    redis_mock.pipeline = MagicMock(side_effect=_capture_pipe)

    await store.put(rec)

    assert len(pipes_used) == 1
    p = pipes_used[0]
    p.setex.assert_called_once()
    # (key, ttl, value) — ttl should be 86400 default
    args = p.setex.call_args.args
    assert args[1] == L2_TTL_SECONDS
    # Tier overwritten to L2 on put
    assert rec.tier == MemoryTier.L2_SHORT


@pytest.mark.asyncio
async def test_put_adds_to_per_tenant_index(store, redis_mock):
    rec = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x")
    pipes_used = []
    def _capture_pipe():
        p = _make_pipeline()
        pipes_used.append(p)
        return p
    redis_mock.pipeline = MagicMock(side_effect=_capture_pipe)

    await store.put(rec)
    p = pipes_used[0]
    p.sadd.assert_called_once()
    args = p.sadd.call_args.args
    assert args[0] == RedisTierStore._index_key(T1)
    assert args[1] == str(rec.record_id)


# ─── get ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_round_trip(store, redis_mock):
    rec = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="hello")
    payload = __import__("json").dumps(_record_to_dict(rec))
    redis_mock.get = AsyncMock(return_value=payload)
    got = await store.get(T1, rec.record_id)
    assert got is not None
    assert got.content == "hello"
    redis_mock.get.assert_awaited_once_with(
        RedisTierStore._record_key(T1, rec.record_id)
    )


@pytest.mark.asyncio
async def test_get_miss_returns_none(store, redis_mock):
    redis_mock.get = AsyncMock(return_value=None)
    got = await store.get(T1, uuid4())
    assert got is None


@pytest.mark.asyncio
async def test_get_other_tenant_uses_different_key(store, redis_mock):
    """If a caller passes T2 instead of T1, the GET targets a key
    that wouldn't exist for T1's record — K-1 enforced by prefix."""
    rid = uuid4()
    # Set up redis so the T1 key exists but T2 key doesn't
    payload = __import__("json").dumps(_record_to_dict(
        MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="t1 data",
                      record_id=rid)
    ))
    def _get(key):
        if key == RedisTierStore._record_key(T1, rid):
            return payload
        return None
    redis_mock.get = AsyncMock(side_effect=_get)

    assert await store.get(T2, rid) is None
    assert await store.get(T1, rid) is not None


# ─── list_all ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_all_returns_records(store, redis_mock):
    rec1 = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="a")
    rec2 = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="b")
    redis_mock.smembers = AsyncMock(return_value={
        str(rec1.record_id).encode(), str(rec2.record_id).encode(),
    })
    import json as _j
    redis_mock.mget = AsyncMock(return_value=[
        _j.dumps(_record_to_dict(rec1)),
        _j.dumps(_record_to_dict(rec2)),
    ])
    out = await store.list_all(T1)
    assert {r.content for r in out} == {"a", "b"}


@pytest.mark.asyncio
async def test_list_all_cleans_up_stale_index_entries(store, redis_mock):
    """A record can expire (TTL hit) while its id still sits in the
    index SET. list_all should detect (mget returns None) and SREM."""
    stale_id = uuid4()
    redis_mock.smembers = AsyncMock(return_value={str(stale_id).encode()})
    redis_mock.mget     = AsyncMock(return_value=[None])
    out = await store.list_all(T1)
    assert out == []
    redis_mock.srem.assert_awaited_once()


# ─── delete ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_returns_true_when_existed(store, redis_mock):
    pipe = _make_pipeline()
    pipe.execute = AsyncMock(return_value=[1, 1])
    redis_mock.pipeline = MagicMock(return_value=pipe)
    assert await store.delete(T1, uuid4()) is True


@pytest.mark.asyncio
async def test_delete_returns_false_when_missing(store, redis_mock):
    pipe = _make_pipeline()
    pipe.execute = AsyncMock(return_value=[0, 0])
    redis_mock.pipeline = MagicMock(return_value=pipe)
    assert await store.delete(T1, uuid4()) is False


# ─── forget ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forget_empty_tenant_returns_zero(store, redis_mock):
    redis_mock.smembers = AsyncMock(return_value=set())
    assert await store.forget(T1) == 0


@pytest.mark.asyncio
async def test_forget_wipes_index_and_records(store, redis_mock):
    rid = uuid4()
    redis_mock.smembers = AsyncMock(return_value={str(rid).encode()})
    pipe = _make_pipeline()
    pipe.execute = AsyncMock(return_value=[1, 1])
    redis_mock.pipeline = MagicMock(return_value=pipe)
    n = await store.forget(T1)
    assert n == 1
    # Pipeline saw 2 deletes: records keys + index key
    pipe.delete.assert_called()
