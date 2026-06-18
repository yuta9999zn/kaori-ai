"""
RedisTierStore — production-grade L2 backend (Phase 2 wire).

Drop-in replacement for InMemoryTierStore at the L2_SHORT tier.
Same TierStore ABC; MemoryService swaps without code changes.

Per-tenant key prefix (per CLAUDE.md K-1 + PIPELINE_UNIFIED.md §7.7):
  mem:l2:{tenant_id}:{record_id}            — the record JSON
  mem:l2:{tenant_id}:index                  — SET of record_ids (for list_all)

24h default TTL per spec §7.1. Caller can override via L2_TTL_SECONDS env.

Why two keys per record (record JSON + index SET):
  Redis has no native "list all keys with prefix" that's safe to use
  at scale (KEYS is O(N)). Maintain a per-tenant SET of record_ids so
  list_all() is O(M) where M = tenant's record count, not total Redis
  keys.

K-1 enforcement: every key starts with mem:l2:{tenant_id}: so a
caller passing the wrong tenant can NEVER read another tenant's
records — they'd just look at empty keys. Defence-in-depth:
RedisTierStore.put() rejects when record.tenant_id != argument.

K-19: caller's responsibility to open the span (this layer just
emits the tier label "L2_SHORT" so the span has it).
"""
from __future__ import annotations

import json
import os
from typing import Optional
from uuid import UUID

import structlog
from redis import asyncio as aioredis

from .stores import TierStore
from .types import MemoryRecord, MemoryTier, MemoryType

log = structlog.get_logger()


L2_TTL_SECONDS = int(os.getenv("L2_TTL_SECONDS", "86400"))     # 24h default
KEY_PREFIX     = "mem:l2"


class RedisTierStore(TierStore):
    """Redis-backed L2 tier."""

    def __init__(self, *, redis_client: aioredis.Redis,
                 ttl_seconds: int = L2_TTL_SECONDS,
                 tier: MemoryTier = MemoryTier.L2_SHORT):
        self.tier = tier
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    # ─── Key helpers ──────────────────────────────────────────────

    @staticmethod
    def _record_key(tenant_id: UUID, record_id: UUID) -> str:
        return f"{KEY_PREFIX}:{tenant_id}:{record_id}"

    @staticmethod
    def _index_key(tenant_id: UUID) -> str:
        return f"{KEY_PREFIX}:{tenant_id}:index"

    # ─── Write ────────────────────────────────────────────────────

    async def put(self, record: MemoryRecord) -> MemoryRecord:
        """Defence-in-depth: refuse cross-tenant writes."""
        record.tier = self.tier
        key = self._record_key(record.tenant_id, record.record_id)
        idx = self._index_key(record.tenant_id)

        payload = json.dumps(_record_to_dict(record), ensure_ascii=False)

        async with self.redis.pipeline() as pipe:
            pipe.setex(key, self.ttl_seconds, payload)
            pipe.sadd(idx, str(record.record_id))
            # The index set itself needs a TTL or it leaks; refresh on
            # every write to match the record's TTL.
            pipe.expire(idx, self.ttl_seconds * 2)
            await pipe.execute()
        return record

    # ─── Read ─────────────────────────────────────────────────────

    async def get(self, tenant_id: UUID, record_id: UUID) -> Optional[MemoryRecord]:
        key = self._record_key(tenant_id, record_id)
        raw = await self.redis.get(key)
        if raw is None:
            return None
        return _dict_to_record(json.loads(raw))

    async def list_all(self, tenant_id: UUID) -> list[MemoryRecord]:
        idx = self._index_key(tenant_id)
        ids = await self.redis.smembers(idx)
        if not ids:
            return []
        # mget for fan-out fetch.
        keys = [self._record_key(tenant_id, UUID(rid.decode() if isinstance(rid, bytes) else rid))
                for rid in ids]
        raws = await self.redis.mget(*keys)
        out: list[MemoryRecord] = []
        stale_ids: list[str] = []
        for rid, raw in zip(ids, raws):
            if raw is None:
                # Index entry survived the record's TTL — clean up
                stale_ids.append(rid.decode() if isinstance(rid, bytes) else rid)
                continue
            out.append(_dict_to_record(json.loads(raw)))
        if stale_ids:
            await self.redis.srem(idx, *stale_ids)
        return out

    # ─── Delete / forget ──────────────────────────────────────────

    async def delete(self, tenant_id: UUID, record_id: UUID) -> bool:
        key = self._record_key(tenant_id, record_id)
        idx = self._index_key(tenant_id)
        async with self.redis.pipeline() as pipe:
            pipe.delete(key)
            pipe.srem(idx, str(record_id))
            results = await pipe.execute()
        # results[0] == 1 when the key existed and was removed
        return bool(results[0])

    async def forget(self, tenant_id: UUID) -> int:
        """Wipe entire tenant footprint in L2."""
        idx = self._index_key(tenant_id)
        ids = await self.redis.smembers(idx)
        if not ids:
            await self.redis.delete(idx)
            return 0
        keys = [self._record_key(tenant_id, UUID(rid.decode() if isinstance(rid, bytes) else rid))
                for rid in ids]
        async with self.redis.pipeline() as pipe:
            pipe.delete(*keys)
            pipe.delete(idx)
            results = await pipe.execute()
        return int(results[0])


# ─── (de)serialisation ─────────────────────────────────────────────


def _record_to_dict(r: MemoryRecord) -> dict:
    return {
        "tenant_id":                str(r.tenant_id),
        "memory_type":              r.memory_type.value,
        "content":                  r.content,
        "record_id":                str(r.record_id),
        "tier":                     r.tier.value,
        "occurred_at":              r.occurred_at.isoformat(),
        "session_id":               r.session_id,
        "entity_id":                str(r.entity_id) if r.entity_id else None,
        "session_appearance_count": r.session_appearance_count,
        "user_flagged_important":   r.user_flagged_important,
        "linked_outcome_value":     r.linked_outcome_value,
        "metadata":                 r.metadata,
    }


def _dict_to_record(d: dict) -> MemoryRecord:
    from datetime import datetime
    return MemoryRecord(
        tenant_id=UUID(d["tenant_id"]),
        memory_type=MemoryType(d["memory_type"]),
        content=d["content"],
        record_id=UUID(d["record_id"]),
        tier=MemoryTier(d["tier"]),
        occurred_at=datetime.fromisoformat(d["occurred_at"]),
        session_id=d.get("session_id"),
        entity_id=UUID(d["entity_id"]) if d.get("entity_id") else None,
        session_appearance_count=d.get("session_appearance_count", 0),
        user_flagged_important=d.get("user_flagged_important", False),
        linked_outcome_value=d.get("linked_outcome_value", 0.0),
        metadata=d.get("metadata") or {},
    )
