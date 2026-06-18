"""
F5 chaos test — Memory L3 via Redis Streams (gated producer).

Verifies that the Redis Streams alternative L3 producer:
  - Stays OFF by default (env flag controls)
  - Produces stream entries with the correct flat encoding
  - Tolerates XADD failure by propagating to the caller's
    best_effort wrapper (MemoryService.write absorbs)
  - Drain worker consumes a batch + INSERTs into pgvector
  - Tenant isolation: stream key contains tenant_id
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.memory import redis_stream_l3 as rs
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord, MemoryTier, MemoryType,
)


def _sample_record(tenant_id=None) -> MemoryRecord:
    return MemoryRecord(
        tenant_id=tenant_id or uuid4(),
        memory_type=MemoryType.DECISION,
        content="Sample memory content with diacritics: việc khen thưởng",
        tier=MemoryTier.L3_CONSOLIDATED,
        session_id="s1",
        entity_id=None,
        metadata={"score": 0.8, "tags": ["finance"]},
        user_flagged_important=True,
        linked_outcome_value=1_500_000.0,
        session_appearance_count=3,
    )


# ─── F5.1: env flag default OFF ──────────────────────────────────────


def test_is_enabled_default_off(monkeypatch):
    monkeypatch.delenv("MEMORY_L3_VIA_REDIS_STREAMS", raising=False)
    assert rs.is_enabled() is False


def test_is_enabled_when_truthy(monkeypatch):
    monkeypatch.setenv("MEMORY_L3_VIA_REDIS_STREAMS", "true")
    assert rs.is_enabled() is True

    monkeypatch.setenv("MEMORY_L3_VIA_REDIS_STREAMS", "1")
    assert rs.is_enabled() is True

    monkeypatch.setenv("MEMORY_L3_VIA_REDIS_STREAMS", "yes")
    assert rs.is_enabled() is True


def test_is_enabled_when_falsy(monkeypatch):
    for val in ("0", "false", "no", ""):
        monkeypatch.setenv("MEMORY_L3_VIA_REDIS_STREAMS", val)
        assert rs.is_enabled() is False


# ─── F5.2: stream key includes tenant_id ─────────────────────────────


def test_stream_key_per_tenant():
    tenant = uuid4()
    key = rs._stream_key(tenant)
    assert str(tenant) in key
    assert key.startswith("s:")
    assert key.endswith(":memory_l3")


# ─── F5.3: put() issues XADD with correct fields ────────────────────


@pytest.mark.asyncio
async def test_producer_put_issues_xadd(monkeypatch):
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1234567890-0")

    producer = rs.RedisStreamL3Producer(redis=redis)
    record = _sample_record()

    result = await producer.put(record)

    # Returned record matches input
    assert result.record_id == record.record_id

    # XADD invoked once
    redis.xadd.assert_awaited_once()
    args, kwargs = redis.xadd.await_args
    # First positional = stream key, second = fields dict
    assert args[0] == rs._stream_key(record.tenant_id)
    fields = args[1]

    # Required keys present + flat values
    assert fields["record_id"] == str(record.record_id)
    assert fields["tenant_id"] == str(record.tenant_id)
    assert fields["memory_type"] == "DECISION"
    assert fields["content"] == record.content
    assert fields["user_flagged_important"] == "1"
    # extra_metadata is JSON-encoded
    parsed = json.loads(fields["extra_metadata"])
    assert parsed == record.metadata


# ─── F5.4: XADD failure propagates to caller ────────────────────────


@pytest.mark.asyncio
async def test_producer_put_xadd_failure_propagates():
    """The producer doesn't absorb errors — MemoryService.write's
    best_effort wrapper does. This pins that the producer surfaces
    the original exception so the wrapper can decide."""
    redis = MagicMock()
    redis.xadd = AsyncMock(side_effect=ConnectionRefusedError("Redis down"))

    producer = rs.RedisStreamL3Producer(redis=redis)
    with pytest.raises(ConnectionRefusedError):
        await producer.put(_sample_record())


# ─── F5.5: forget() deletes the per-tenant stream ────────────────────


@pytest.mark.asyncio
async def test_producer_forget_deletes_stream():
    redis = MagicMock()
    redis.delete = AsyncMock(return_value=1)

    producer = rs.RedisStreamL3Producer(redis=redis)
    count = await producer.forget(uuid4())
    assert count == 1
    redis.delete.assert_awaited_once()


# ─── F5.6: drain_one_batch consumes + ACKs ──────────────────────────


@pytest.mark.asyncio
async def test_drain_consumes_batch_acks():
    tenant = uuid4()
    record = _sample_record(tenant_id=tenant)

    # Encode record back into stream-field shape (bytes, like real Redis)
    fields_bytes = {
        b"record_id":              str(record.record_id).encode(),
        b"tenant_id":              str(tenant).encode(),
        b"memory_type":            b"DECISION",
        b"content":                record.content.encode(),
        b"session_id":             b"s1",
        b"entity_id":              b"",
        b"occurred_at":            record.occurred_at.isoformat().encode(),
        b"user_flagged_important": b"1",
        b"linked_outcome_value":   b"1500000.0",
        b"session_appearance_count": b"3",
        b"extra_metadata":         json.dumps({"x": 1}).encode(),
    }

    redis = MagicMock()
    redis.xgroup_create = AsyncMock(return_value=b"OK")
    redis.xreadgroup = AsyncMock(return_value=[
        (rs._stream_key(tenant).encode(), [
            (b"1234-0", fields_bytes),
        ]),
    ])
    redis.xack = AsyncMock(return_value=1)

    pg_store = MagicMock()
    pg_store.put = AsyncMock(side_effect=lambda r: r)

    count = await rs.drain_one_batch(
        redis=redis, tenant_id=tenant, pg_store=pg_store,
    )

    assert count == 1
    pg_store.put.assert_awaited_once()
    redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_drain_empty_stream_returns_zero():
    """XREADGROUP returns [] when nothing to consume (block timeout)."""
    redis = MagicMock()
    redis.xgroup_create = AsyncMock(return_value=b"OK")
    redis.xreadgroup = AsyncMock(return_value=[])
    redis.xack = AsyncMock()

    pg_store = MagicMock()
    pg_store.put = AsyncMock()

    count = await rs.drain_one_batch(
        redis=redis, tenant_id=uuid4(), pg_store=pg_store,
    )
    assert count == 0
    pg_store.put.assert_not_awaited()
    redis.xack.assert_not_awaited()


@pytest.mark.asyncio
async def test_drain_pg_put_failure_leaves_entry_unack():
    """When pg_store.put fails for a record, that entry is NOT ACK'd
    → Redis will re-deliver on next XREADGROUP. The drain count
    reflects only successful inserts."""
    tenant = uuid4()
    fields_bytes = {
        b"record_id":              str(uuid4()).encode(),
        b"tenant_id":              str(tenant).encode(),
        b"memory_type":            b"DECISION",
        b"content":                b"x",
        b"session_id":             b"",
        b"entity_id":              b"",
        b"occurred_at":            datetime.now(timezone.utc).isoformat().encode(),
        b"user_flagged_important": b"0",
        b"linked_outcome_value":   b"0",
        b"session_appearance_count": b"0",
        b"extra_metadata":         b"{}",
    }
    redis = MagicMock()
    redis.xgroup_create = AsyncMock(return_value=b"OK")
    redis.xreadgroup = AsyncMock(return_value=[
        (rs._stream_key(tenant).encode(), [(b"1-0", fields_bytes)]),
    ])
    redis.xack = AsyncMock(return_value=0)

    pg_store = MagicMock()
    pg_store.put = AsyncMock(side_effect=RuntimeError("pgvector down"))

    count = await rs.drain_one_batch(
        redis=redis, tenant_id=tenant, pg_store=pg_store,
    )
    assert count == 0
    # XACK was NOT called for the failed entry
    redis.xack.assert_not_awaited()


# ─── F5.7: BUSYGROUP error tolerated (group already exists) ─────────


@pytest.mark.asyncio
async def test_drain_busygroup_is_tolerated():
    """xgroup_create raises 'BUSYGROUP' when the consumer group already
    exists. That's expected — drain should proceed to XREADGROUP."""
    redis = MagicMock()
    redis.xgroup_create = AsyncMock(
        side_effect=Exception("BUSYGROUP Consumer Group name already exists"),
    )
    redis.xreadgroup = AsyncMock(return_value=[])
    redis.xack = AsyncMock()

    pg_store = MagicMock()
    count = await rs.drain_one_batch(
        redis=redis, tenant_id=uuid4(), pg_store=pg_store,
    )
    assert count == 0  # nothing was in the stream, but drain didn't crash
    redis.xreadgroup.assert_awaited_once()


# ─── F5.8: read-side methods raise NotImplementedError ──────────────


@pytest.mark.asyncio
async def test_producer_get_not_implemented():
    redis = MagicMock()
    producer = rs.RedisStreamL3Producer(redis=redis)
    with pytest.raises(NotImplementedError):
        await producer.get(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_producer_list_all_not_implemented():
    redis = MagicMock()
    producer = rs.RedisStreamL3Producer(redis=redis)
    with pytest.raises(NotImplementedError):
        await producer.list_all(uuid4())


# ─── F5.9: round-trip — produce + drain produce identical record ────


@pytest.mark.asyncio
async def test_round_trip_produce_then_drain(monkeypatch):
    """End-to-end: producer.put → captured fields → drain rehydrates
    → pgvector.put receives the SAME record (modulo serialization)."""
    tenant = uuid4()
    captured_fields = {}

    redis = MagicMock()

    async def _xadd(key, fields, **k):
        captured_fields.update(fields)
        return b"1-0"
    redis.xadd = AsyncMock(side_effect=_xadd)

    redis.xgroup_create = AsyncMock(return_value=b"OK")
    redis.xreadgroup = AsyncMock(side_effect=lambda **k: [
        (rs._stream_key(tenant).encode(), [
            (b"1-0", {k.encode(): v.encode() for k, v in captured_fields.items()}),
        ]),
    ])
    redis.xack = AsyncMock(return_value=1)

    producer = rs.RedisStreamL3Producer(redis=redis)
    original = _sample_record(tenant_id=tenant)
    await producer.put(original)

    pg_store = MagicMock()
    pg_received = []
    async def _put(r):
        pg_received.append(r)
        return r
    pg_store.put = AsyncMock(side_effect=_put)

    await rs.drain_one_batch(redis=redis, tenant_id=tenant, pg_store=pg_store)

    assert len(pg_received) == 1
    landed = pg_received[0]
    assert landed.record_id == original.record_id
    assert landed.tenant_id == original.tenant_id
    assert landed.content == original.content
    assert landed.memory_type == original.memory_type
    assert landed.user_flagged_important == original.user_flagged_important
    assert landed.metadata == original.metadata
