"""Per-tier storage backends.

This commit ships ONE backend per tier (InMemoryTierStore handles
all 4 tiers). Phase 2 wires:
  - Redis for L2 (per-tenant key prefix)
  - Postgres + pgvector for L3
  - Neo4j + vector DB + feature store for L4

Each backend implements the same TierStore ABC so MemoryService can
swap them independently per tier.
"""
from __future__ import annotations

import abc
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from .types import MemoryRecord, MemoryTier


class TierStore(abc.ABC):
    """One backend per tier. Stateless callers; the store holds state."""

    @abc.abstractmethod
    async def put(self, record: MemoryRecord) -> MemoryRecord: ...

    @abc.abstractmethod
    async def get(self, tenant_id: UUID, record_id: UUID) -> Optional[MemoryRecord]: ...

    @abc.abstractmethod
    async def list_all(self, tenant_id: UUID) -> list[MemoryRecord]:
        """All records for the tenant in this tier — used for tests +
        consolidate/promote scans."""
        ...

    @abc.abstractmethod
    async def delete(self, tenant_id: UUID, record_id: UUID) -> bool: ...

    @abc.abstractmethod
    async def forget(self, tenant_id: UUID) -> int:
        """Wipe entire tenant footprint in THIS tier."""
        ...


class InMemoryTierStore(TierStore):
    """In-memory dict-backed store. Single-process, no concurrent
    writers expected (same constraint as InMemoryOntologyStore)."""

    def __init__(self, tier: MemoryTier):
        self.tier = tier
        # (tenant_id, record_id) → MemoryRecord
        self._records: dict[tuple[UUID, UUID], MemoryRecord] = {}
        # tenant_id → set[record_id] for fast list_all
        self._by_tenant: dict[UUID, set[UUID]] = defaultdict(set)

    async def put(self, record: MemoryRecord) -> MemoryRecord:
        record.tier = self.tier
        self._records[(record.tenant_id, record.record_id)] = record
        self._by_tenant[record.tenant_id].add(record.record_id)
        return record

    async def get(self, tenant_id: UUID, record_id: UUID) -> Optional[MemoryRecord]:
        return self._records.get((tenant_id, record_id))

    async def list_all(self, tenant_id: UUID) -> list[MemoryRecord]:
        ids = list(self._by_tenant.get(tenant_id, set()))
        return [self._records[(tenant_id, rid)] for rid in ids
                 if (tenant_id, rid) in self._records]

    async def delete(self, tenant_id: UUID, record_id: UUID) -> bool:
        key = (tenant_id, record_id)
        if key not in self._records:
            return False
        del self._records[key]
        self._by_tenant[tenant_id].discard(record_id)
        return True

    async def forget(self, tenant_id: UUID) -> int:
        ids = list(self._by_tenant.get(tenant_id, set()))
        for rid in ids:
            self._records.pop((tenant_id, rid), None)
        self._by_tenant.pop(tenant_id, None)
        return len(ids)


def cheap_text_match(query: str, text: str) -> float:
    """Tiny retrieval scoring for in-memory mode. Token-set jaccard
    similarity 0-1. Real impl swaps to pgvector embedding similarity
    when L3 is wired Phase 2.

    Vietnamese-aware: lowercases + strips punctuation + splits on
    whitespace. Good enough for tests + Pilot demo Phase 1.5."""
    def _tokens(s: str) -> set[str]:
        return set(re.findall(r"\w+", s.lower(), re.UNICODE))
    q, t = _tokens(query), _tokens(text)
    if not q or not t:
        return 0.0
    return len(q & t) / len(q | t)
