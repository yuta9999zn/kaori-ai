"""
Stage 7 — Memory System (4-tier hierarchy + RAG read flow).

Per docs/strategic/PIPELINE_UNIFIED.md §7.1-7.8. The "remembering"
tier of the Reasoning Layer — tracks events through 4 TTL buckets and
exposes a uniform write/retrieve/promote/forget API.

4 tiers
-------
  L1 WORKING   — in-process Python dict; TTL = request lifetime (seconds)
  L2 SHORT     — session-scoped; TTL = 24h default (Redis Phase 2; in-memory now)
  L3 EPISODIC  — recent events (30-90d); Postgres + pgvector embedding
  L4 LONG-TERM — knowledge / patterns; KG + Vector + Feature Store

5 memory types
--------------
  Episodic    → L3
  Semantic    → L4 (shared knowledge)
  Procedural  → L4 (workflow library)
  Operational → L3-L4 hybrid (action outcomes)
  Decision    → L4 (decision history, KG-linked)

Public API (per spec §7.6)
--------------------------
  write(tenant_id, memory_type, content, metadata) -> MemoryRecord
  retrieve(tenant_id, query, top_k=5, tier='auto')  -> list[MemoryRecord]
  consolidate(tenant_id)                            -> int (L2 → L3 promotion count)
  promote(tenant_id)                                -> int (L3 → L4 promotion count)
  forget(tenant_id, criteria)                       -> int (rows wiped — GDPR)
  introspect(tenant_id, entity_id)                  -> list[MemoryRecord]
  compute_importance(record)                        -> float (0-1)

K-1: every memory carries tenant_id; all ops filter on it.
K-19: each tier op emits a span attribute (caller's responsibility to
       open the span; this module does the tier label).
"""
from __future__ import annotations

from .service import MemoryService
from .stores import InMemoryTierStore
from .types import (
    MemoryRecord,
    MemoryTier,
    MemoryType,
    compute_importance,
)

__all__ = [
    "InMemoryTierStore",
    "MemoryRecord",
    "MemoryService",
    "MemoryTier",
    "MemoryType",
    "compute_importance",
]
