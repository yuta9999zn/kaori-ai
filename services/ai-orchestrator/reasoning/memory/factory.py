"""Shared MemoryService factory (RAG×harness step 3).

Wires the EPISODIC tier (L3) to the persistent Postgres store so that what one
agent session CONSOLIDATES is recalled by the next — the loop that grows the
Internal Field (IF) over time. L1/L2/L4 stay in-memory for now (Phase 1.5);
L3 is the durable episodic tier consolidation lands in and recall_memory reads.

Both the orchestrator's consolidate step and the recall_memory tool build the
service through here so they share the same persistent store. Falls back to the
all-in-memory service if Postgres wiring is unavailable (best-effort).
"""
from __future__ import annotations

import structlog

log = structlog.get_logger()

_SINGLETON = None


def build_memory_service():
    """MemoryService with a persistent Postgres L3 (episodic) tier."""
    global _SINGLETON
    if _SINGLETON is not None:
        return _SINGLETON
    from .service import MemoryService
    try:
        from .postgres_l3 import PostgresTierStore
        from ai_orchestrator.shared.db import acquire_for_tenant
        _SINGLETON = MemoryService(l3=PostgresTierStore(acquire_for_tenant=acquire_for_tenant))
    except Exception as e:  # pragma: no cover - degrade to in-memory
        log.warning("memory.factory.postgres_unavailable", error=str(e))
        _SINGLETON = MemoryService()
    return _SINGLETON
