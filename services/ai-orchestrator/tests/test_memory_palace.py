"""Tests for ADR-0032 memory palace: maturation (confidence learning-curve +
tenant experience) and associative recall (1-hop link expansion).

Maturation is the growth counterpart to ADR-0030 decay: a used/validated memory
grows more certain, and the tenant's experience climbs as MAINTAINED trusted
knowledge accumulates over the months ("càng nhiều tháng càng biết nhiều").
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord,
    MemoryTier,
    MemoryType,
    experience_level,
    reinforce_confidence,
)

T = uuid4()
NOW = datetime(2026, 5, 27, tzinfo=timezone.utc)


def _rec(memory_type, content, *, confidence=0.7, age_days=0, source=None):
    return MemoryRecord(
        tenant_id=T, memory_type=memory_type, content=content,
        tier=MemoryTier.L4_LONG, confidence=confidence, trust_source=source,
        occurred_at=NOW - timedelta(days=age_days),
    )


# ── confidence reinforcement (learning curve) ────────────────────────────────

def test_reinforce_climbs_with_diminishing_returns():
    r = _rec(MemoryType.SEMANTIC, "x", confidence=0.5, source="consolidate")  # ceiling 0.90
    c1 = reinforce_confidence(r)
    c2 = reinforce_confidence(r)
    assert 0.5 < c1 < c2 <= 0.90
    assert (c1 - 0.5) > (c2 - c1)          # each confirmation adds less


def test_reinforce_never_exceeds_ceiling():
    r = _rec(MemoryType.SEMANTIC, "x", confidence=0.5, source="derived")        # ceiling 0.85
    for _ in range(200):
        reinforce_confidence(r)
    assert r.confidence <= 0.85


def test_ceiling_per_source_user_beats_derived():
    user = _rec(MemoryType.SEMANTIC, "x", confidence=0.5, source="user")        # 0.98
    derived = _rec(MemoryType.SEMANTIC, "x", confidence=0.5, source="derived")  # 0.85
    for _ in range(200):
        reinforce_confidence(user)
        reinforce_confidence(derived)
    assert user.confidence > derived.confidence


# ── tenant experience ("càng nhiều tháng càng biết nhiều") ───────────────────

def test_experience_empty_is_novice():
    e = experience_level([], now=NOW)
    assert e["experience"] == 0.0 and e["band"] == "mới" and e["n"] == 0


def test_experience_grows_with_accumulated_knowledge():
    few = [_rec(MemoryType.SEMANTIC, f"f{i}", confidence=0.9) for i in range(2)]
    many = [_rec(MemoryType.SEMANTIC, f"f{i}", confidence=0.9) for i in range(30)]
    assert experience_level(many, now=NOW)["experience"] > experience_level(few, now=NOW)["experience"]


def test_experience_reports_tenure_days():
    recs = [_rec(MemoryType.SEMANTIC, "x", age_days=200),
            _rec(MemoryType.SEMANTIC, "y", age_days=40)]
    assert experience_level(recs, now=NOW)["tenure_days"] == 200    # oldest memory


def test_experience_stale_knowledge_does_not_count():
    # EPISODIC half-life 30d; 1000d-old memories have ≈0 trust → near-zero mass.
    stale = [_rec(MemoryType.EPISODIC, f"e{i}", confidence=0.9, age_days=1000) for i in range(30)]
    assert experience_level(stale, now=NOW)["experience"] < 0.1


# ── service: reinforce-on-use ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_reinforce_raises_confidence_and_verifies():
    svc = MemoryService()
    r = _rec(MemoryType.SEMANTIC, "insight đáng nhớ", confidence=0.5, source="consolidate")
    await svc.l4.put(r)
    ok = await svc.reinforce(T, r.record_id)
    assert ok
    after = await svc.l4.get(T, r.record_id)
    assert after.confidence > 0.5 and after.last_verified_at is not None


@pytest.mark.asyncio
async def test_service_experience_grows_over_time():
    svc = MemoryService()
    assert (await svc.experience(T))["experience"] == 0.0
    for i in range(20):
        await svc.l4.put(_rec(MemoryType.SEMANTIC, f"insight {i}", confidence=0.9))
    e = await svc.experience(T)
    assert e["experience"] > 0.0 and e["n"] == 20 and e["band"] != "mới"


# ── associative recall (1-hop link expansion) ────────────────────────────────

@pytest.mark.asyncio
async def test_associative_recall_pulls_linked_neighbour():
    svc = MemoryService()
    a = _rec(MemoryType.SEMANTIC, "doanh thu khách VIP Hà Nội")   # matches query
    b = _rec(MemoryType.SEMANTIC, "chương trình loyalty mùa hè")  # NO query overlap
    await svc.l4.put(a)
    await svc.l4.put(b)
    await svc.link(T, a.record_id, b.record_id)

    results = await svc.retrieve(T, "doanh thu VIP", top_k=5)
    ids = {str(r.record_id) for r in results}
    assert str(a.record_id) in ids          # direct hit
    assert str(b.record_id) in ids          # pulled in via the link
    nb = next(r for r in results if r.record_id == b.record_id)
    assert nb.metadata.get("_via") == str(a.record_id)


@pytest.mark.asyncio
async def test_link_is_mutual_by_default():
    svc = MemoryService()
    a = _rec(MemoryType.SEMANTIC, "alpha")
    b = _rec(MemoryType.SEMANTIC, "beta")
    await svc.l4.put(a)
    await svc.l4.put(b)
    await svc.link(T, a.record_id, b.record_id)
    a2 = await svc.l4.get(T, a.record_id)
    b2 = await svc.l4.get(T, b.record_id)
    assert str(b.record_id) in a2.metadata["links"]
    assert str(a.record_id) in b2.metadata["links"]
