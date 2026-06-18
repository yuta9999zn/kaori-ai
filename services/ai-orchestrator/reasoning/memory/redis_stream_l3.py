"""
F5 — Memory L3 via Redis Streams producer (gated, default OFF).

Decouples the user-facing write latency on Memory L3 from pgvector
INSERT latency. Pattern:

  caller.write() → producer.put()       (sub-millisecond, Redis XADD)
                       │
                       ▼ Redis Stream s:{tenant}:memory_l3
                       │
                       ▼ embedding_drain_worker (background)
                       │
                       ▼ PostgresTierStore.put()  (real pgvector)

Why
---
The pgvector INSERT is dominated by:
  - HNSW index update (~10-50ms per row)
  - 24-byte float vector serialisation
  - Transaction + WAL fsync

Under heavy memory-write load (e.g. workflow agent flooding L3 with
DECISION memories per step), the pgvector path becomes a bottleneck.
Redis Streams XADD is sub-millisecond; the drain worker batches.

Activation
----------
Off by default. Flip via env:
  MEMORY_L3_VIA_REDIS_STREAMS=true
  REDIS_STREAMS_HOST=redis.kaori.internal:6379
  REDIS_STREAMS_MAXLEN=100000  (per tenant trim ceiling)

When OFF, MemoryService.write() keeps going directly to
PostgresTierStore.put() — F5 has zero effect.

K-1: stream key includes tenant_id; consumer must enforce tenant
isolation when draining + writing to pgvector. Bridge identity via
stream entry payload, never cross-pollute tenant scope.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID

import structlog

from .stores import TierStore
from .types import MemoryRecord, MemoryTier

if TYPE_CHECKING:  # pragma: no cover
    from redis.asyncio import Redis

log = structlog.get_logger()


def is_enabled() -> bool:
    """Env-gate the entire Redis Streams path. Default OFF — current
    production keeps the direct pgvector path."""
    return os.getenv("MEMORY_L3_VIA_REDIS_STREAMS", "").lower() in (
        "1", "true", "yes",
    )


def _stream_key(tenant_id: UUID) -> str:
    return f"s:{tenant_id}:memory_l3"


def _maxlen() -> int:
    """Per-tenant stream trim ceiling. Older entries past this get
    auto-trimmed (XADD MAXLEN). 100K default ~ 30 days of typical
    workflow agent memory at 1 write per minute."""
    try:
        return int(os.getenv("REDIS_STREAMS_MAXLEN", "100000"))
    except ValueError:
        return 100000


class RedisStreamL3Producer(TierStore):
    """Write-side L3 store that publishes to a Redis Stream instead
    of pgvector directly. Reads are NOT supported here — the drain
    worker writes to the real PostgresTierStore which serves reads.

    Construct with an already-opened redis.asyncio.Redis client.
    """

    tier = MemoryTier.L3_CONSOLIDATED

    def __init__(self, *, redis: "Redis"):
        self._redis = redis

    async def put(self, record: MemoryRecord) -> MemoryRecord:
        """XADD the record to the per-tenant stream. Returns the
        record (unchanged) so the contract matches PostgresTierStore.put.

        The stream entry is a flat dict-of-strings (Redis requirement).
        Drain worker reverses the encoding on consume.
        """
        record.tier = self.tier
        key = _stream_key(record.tenant_id)

        # Serialise to a flat dict-of-strings (Redis Streams field/value
        # pairs are bytes/strings, not nested). UUIDs + datetimes get
        # stringified; metadata gets JSON-encoded.
        fields: dict[str, str] = {
            "record_id":              str(record.record_id),
            "tenant_id":              str(record.tenant_id),
            "memory_type":            record.memory_type.value,
            "content":                record.content,
            "session_id":             record.session_id or "",
            "entity_id":              str(record.entity_id) if record.entity_id else "",
            "occurred_at":            record.occurred_at.isoformat(),
            "user_flagged_important": "1" if record.user_flagged_important else "0",
            "linked_outcome_value":   str(record.linked_outcome_value),
            "session_appearance_count": str(record.session_appearance_count),
            "extra_metadata":         json.dumps(
                record.metadata, ensure_ascii=False,
            ),
        }

        try:
            # MAXLEN ~ enables approximate trim — fast + bounded memory.
            await self._redis.xadd(
                key, fields, maxlen=_maxlen(), approximate=True,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "memory.l3.stream_xadd_failed",
                tenant_id=str(record.tenant_id),
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )
            raise  # let MemoryService.write best_effort wrap absorb
        return record

    async def get(self, *a, **k):
        raise NotImplementedError(
            "RedisStreamL3Producer is write-only; reads come from "
            "PostgresTierStore once drain worker has consumed."
        )

    async def list_all(self, *a, **k):
        raise NotImplementedError(
            "RedisStreamL3Producer is write-only."
        )

    async def delete(self, *a, **k):
        raise NotImplementedError(
            "RedisStreamL3Producer is write-only. Use PostgresTierStore."
        )

    async def forget(self, tenant_id: UUID) -> int:
        """Wipe the per-tenant stream. The drain worker should also be
        notified to skip in-flight entries for this tenant (out-of-
        scope for v0 — manual coordination if you call forget())."""
        key = _stream_key(tenant_id)
        try:
            return int(await self._redis.delete(key))
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "memory.l3.stream_delete_failed",
                tenant_id=str(tenant_id),
                error_type=type(exc).__name__,
            )
            return 0


async def drain_one_batch(
    *,
    redis: "Redis",
    tenant_id: UUID,
    pg_store: TierStore,
    consumer_group: str = "memory_l3_drain",
    consumer_name: str = "drain-worker-1",
    batch_size: int = 50,
    block_ms: int = 1000,
) -> int:
    """Single drain iteration — XREADGROUP one batch, INSERT each
    record into pg_store, ACK the entries.

    Worker entrypoint should loop this. Returns the count of records
    successfully drained.

    Tenant isolation: takes a SINGLE tenant_id and only reads that
    tenant's stream. Multi-tenant drain loops over the active tenants
    list (caller's responsibility — typically a 30s sweep that pulls
    DISTINCT tenant_id from a recent-activity view).
    """
    key = _stream_key(tenant_id)

    # Ensure consumer group exists. MKSTREAM creates the stream if
    # not yet present (caller may invoke before first XADD).
    try:
        await redis.xgroup_create(
            key, consumer_group, id="0", mkstream=True,
        )
    except Exception as exc:  # noqa: BLE001
        # BUSYGROUP — group already exists. Anything else is real
        # infra failure, surface to caller.
        if "BUSYGROUP" not in str(exc):
            log.warning(
                "memory.l3.drain_group_create_failed",
                tenant_id=str(tenant_id),
                error_type=type(exc).__name__,
            )

    # Read up to batch_size entries.
    try:
        msgs = await redis.xreadgroup(
            groupname=consumer_group,
            consumername=consumer_name,
            streams={key: ">"},
            count=batch_size,
            block=block_ms,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "memory.l3.drain_xreadgroup_failed",
            tenant_id=str(tenant_id),
            error_type=type(exc).__name__,
        )
        return 0

    if not msgs:
        return 0

    drained = 0
    ids_to_ack: list[bytes] = []

    for _stream_key_bytes, entries in msgs:
        for entry_id, fields in entries:
            # Fields come back as bytes; decode + reconstruct.
            try:
                record = _record_from_stream_fields(fields)
                await pg_store.put(record)
                ids_to_ack.append(entry_id)
                drained += 1
            except Exception as exc:  # noqa: BLE001
                # Record failed to land in pgvector. Leave entry
                # un-ACK'd so it gets re-delivered next sweep (Redis
                # XPENDING surface).
                log.warning(
                    "memory.l3.drain_insert_failed",
                    tenant_id=str(tenant_id),
                    entry_id=entry_id,
                    error_type=type(exc).__name__,
                    detail=str(exc)[:200],
                )

    if ids_to_ack:
        try:
            await redis.xack(key, consumer_group, *ids_to_ack)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "memory.l3.drain_xack_failed",
                tenant_id=str(tenant_id),
                error_type=type(exc).__name__,
            )

    return drained


def _record_from_stream_fields(fields: dict) -> MemoryRecord:
    """Reverse of RedisStreamL3Producer.put encoding. Tolerant of
    bytes-vs-str (Redis returns bytes by default unless decode_responses
    set on client)."""
    from .types import MemoryType

    def _s(v) -> str:
        return v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)

    decoded = {_s(k): _s(v) for k, v in fields.items()}

    occurred_at = datetime.fromisoformat(decoded["occurred_at"])
    metadata = json.loads(decoded.get("extra_metadata", "{}") or "{}")

    return MemoryRecord(
        tenant_id=UUID(decoded["tenant_id"]),
        memory_type=MemoryType(decoded["memory_type"]),
        content=decoded["content"],
        record_id=UUID(decoded["record_id"]),
        tier=MemoryTier.L3_CONSOLIDATED,
        occurred_at=occurred_at,
        session_id=decoded.get("session_id") or None,
        entity_id=UUID(decoded["entity_id"]) if decoded.get("entity_id") else None,
        session_appearance_count=int(decoded.get("session_appearance_count", "0")),
        user_flagged_important=decoded.get("user_flagged_important") == "1",
        linked_outcome_value=float(decoded.get("linked_outcome_value", "0")),
        metadata=metadata,
    )
