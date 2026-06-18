"""ADR-0036 — classic-type view + memory→KB promotion loop + procedural seed.

Drives the real MemoryService (in-memory tier stores) against a fake
KnowledgeStore — no DB. Verifies:
  • classic_memory_class maps the 5 MemoryTypes onto the cognitive taxonomy.
  • promote_to_knowledge lifts a MATURE procedural/semantic memory into the
    tenant's tier-4 KB (idempotent, flagged once, immature memories skipped).
  • seed_procedural_from_kb bootstraps the PROCEDURAL room from foundational KB
    with thin pointer recipes (idempotent).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord, MemoryTier, MemoryType, classic_memory_class,
)
from ai_orchestrator.reasoning.knowledge.store import KnowledgeDocument


def test_classic_memory_class_view():
    assert classic_memory_class(MemoryType.EPISODIC) == "episodic"
    assert classic_memory_class(MemoryType.DECISION) == "episodic"
    assert classic_memory_class(MemoryType.SEMANTIC) == "semantic"
    assert classic_memory_class(MemoryType.PROCEDURAL) == "procedural"
    assert classic_memory_class(MemoryType.OPERATIONAL) == "procedural"


class _FakeKB:
    def __init__(self, listing=None):
        self.put_calls: list = []
        self._listing = listing or []

    async def put(self, doc, *, scope_tenant_id=None):
        self.put_calls.append((doc, scope_tenant_id))
        return doc.document_id

    async def list_documents(self, scope, *, status="active", category=None, limit=100):
        return self._listing


def _mature(tenant, mtype=MemoryType.PROCEDURAL, **kw):
    r = MemoryRecord(
        tenant_id=tenant, memory_type=mtype, content="Gộp đơn cùng KH trong tháng",
        tier=MemoryTier.L4_LONG, confidence=0.9, session_appearance_count=3,
        occurred_at=datetime.now(timezone.utc), trust_source="consolidate",
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


@pytest.mark.asyncio
async def test_promote_mature_memory_to_kb():
    t = uuid4()
    svc = MemoryService()
    await svc.l4.put(_mature(t))
    kb = _FakeKB()
    n = await svc.promote_to_knowledge(t, knowledge_store=kb)
    assert n == 1
    doc, scope = kb.put_calls[0]
    assert scope == t and doc.tier == 4 and doc.tenant_id == t
    assert doc.category == "procedural" and doc.source == "memory_promotion"


@pytest.mark.asyncio
async def test_promote_skips_immature_and_is_idempotent():
    t = uuid4()
    svc = MemoryService()
    # immature: only 1 appearance → skipped
    await svc.l4.put(_mature(t, session_appearance_count=1))
    # low trust: confidence below threshold → skipped
    await svc.l4.put(_mature(t, confidence=0.5))
    kb = _FakeKB()
    assert await svc.promote_to_knowledge(t, knowledge_store=kb) == 0

    # a mature one promotes once, then never again (flagged)
    await svc.l4.put(_mature(t))
    assert await svc.promote_to_knowledge(t, knowledge_store=kb) == 1
    assert await svc.promote_to_knowledge(t, knowledge_store=kb) == 0


@pytest.mark.asyncio
async def test_promote_gate_falls_back_to_ai_config_knobs(monkeypatch):
    """ADR-0036 follow-up — when the caller pins no thresholds, the maturity gate
    reads the platform knobs. A knob raising min_appearances above the memory's
    count must suppress promotion (proves the knob is consulted, not the const)."""
    import ai_orchestrator.shared.ai_config as ai_config

    async def fake_float(key, default):
        return default          # leave trust gate at the const default

    async def fake_int(key, default):
        return 5 if key == "memory_kb_promote_min_appearances" else default

    monkeypatch.setattr(ai_config, "get_float", fake_float)
    monkeypatch.setattr(ai_config, "get_int", fake_int)

    t = uuid4()
    svc = MemoryService()
    await svc.l4.put(_mature(t))   # 3 appearances < knob's 5 → skipped
    kb = _FakeKB()
    assert await svc.promote_to_knowledge(t, knowledge_store=kb) == 0


@pytest.mark.asyncio
async def test_seed_procedural_from_kb():
    t = uuid4()
    svc = MemoryService()
    kb = _FakeKB(listing=[
        KnowledgeDocument(title="Pareto 80/20", content="...", tier=2),
        KnowledgeDocument(title="RFM segmentation", content="...", tier=1),
        KnowledgeDocument(title="Market churn note", content="...", tier=3),  # not foundational
    ])
    n = await svc.seed_procedural_from_kb(t, knowledge_store=kb)
    assert n == 2   # only tier 1-2 (foundational) seeded
    recs = await svc.l4.list_all(t)
    assert all(r.memory_type == MemoryType.PROCEDURAL for r in recs)
    assert any("Pareto" in r.content for r in recs)
    # idempotent — re-seed overwrites the same deterministic ids
    await svc.seed_procedural_from_kb(t, knowledge_store=kb)
    assert len(await svc.l4.list_all(t)) == 2
