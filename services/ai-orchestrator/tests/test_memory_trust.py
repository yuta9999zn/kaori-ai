"""Tests for the ADR-0030 memory trust layer.

Trust = believability (decays by per-type half-life), distinct from importance
(retention). Covers compute_trust / trust_factor, the confident-but-unchecked
flag, verify() resetting decay, and retrieve() down-ranking stale memories.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord,
    MemoryTier,
    MemoryType,
    compute_trust,
    halflife_days,
    trust_factor,
)

T = uuid4()
NOW = datetime(2026, 5, 27, tzinfo=timezone.utc)


def _rec(memory_type, content, *, confidence=0.7, age_days=0, verified_days=None):
    return MemoryRecord(
        tenant_id=T, memory_type=memory_type, content=content,
        tier=MemoryTier.L4_LONG, confidence=confidence,
        occurred_at=NOW - timedelta(days=age_days),
        last_verified_at=(NOW - timedelta(days=verified_days)) if verified_days is not None else None,
    )


# ── compute_trust ────────────────────────────────────────────────────────────

def test_fresh_recent_high_confidence():
    t = compute_trust(_rec(MemoryType.SEMANTIC, "x", confidence=0.9, age_days=0), now=NOW)
    assert t["level"] == "fresh" and t["score"] >= 0.85 and not t["unchecked"]


def test_stale_old_episodic_decays():
    # EPISODIC half-life 30d; 120d ≈ 4 half-lives → 0.7 * 0.5^4 ≈ 0.044
    t = compute_trust(_rec(MemoryType.EPISODIC, "x", confidence=0.7, age_days=120), now=NOW)
    assert t["level"] == "stale" and t["score"] < 0.1


def test_confident_but_unchecked_flag():
    # high confidence, never verified, past one half-life (SEMANTIC 365d)
    t = compute_trust(_rec(MemoryType.SEMANTIC, "x", confidence=0.9, age_days=400), now=NOW)
    assert t["unchecked"] is True


def test_verified_recently_not_unchecked():
    t = compute_trust(
        _rec(MemoryType.SEMANTIC, "x", confidence=0.9, age_days=400, verified_days=1), now=NOW)
    assert t["unchecked"] is False and t["verified"] is True and t["level"] == "fresh"


def test_halflife_per_type_semantic_outlasts_episodic():
    age = 60
    sem = compute_trust(_rec(MemoryType.SEMANTIC, "x", age_days=age), now=NOW)["score"]
    epi = compute_trust(_rec(MemoryType.EPISODIC, "x", age_days=age), now=NOW)["score"]
    assert sem > epi
    assert halflife_days(MemoryType.SEMANTIC) > halflife_days(MemoryType.EPISODIC)


def test_trust_factor_band():
    # factor stays within [0.4, 1.0] regardless of decay
    hi = trust_factor(_rec(MemoryType.SEMANTIC, "x", confidence=1.0, age_days=0), now=NOW)
    lo = trust_factor(_rec(MemoryType.EPISODIC, "x", confidence=0.5, age_days=9999), now=NOW)
    assert 0.4 <= lo < hi <= 1.0


# ── retrieve ranking ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_downranks_stale_memory():
    svc = MemoryService()
    fresh = _rec(MemoryType.SEMANTIC, "doanh thu khách VIP", age_days=0)
    stale = _rec(MemoryType.SEMANTIC, "doanh thu khách VIP", age_days=800)
    await svc.l4.put(fresh)
    await svc.l4.put(stale)
    results = await svc.retrieve(T, "doanh thu VIP", top_k=2)
    assert results[0].record_id == fresh.record_id    # same text match → trust breaks the tie


# ── verify resets decay ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_resets_trust_to_fresh():
    svc = MemoryService()
    rec = _rec(MemoryType.SEMANTIC, "fact đáng nhớ", confidence=0.9, age_days=800)
    await svc.l4.put(rec)
    assert compute_trust(rec)["level"] == "stale"

    ok = await svc.verify(T, rec.record_id)
    assert ok is True

    refreshed = await svc.l4.get(T, rec.record_id)
    assert refreshed.last_verified_at is not None
    assert compute_trust(refreshed)["level"] == "fresh"


@pytest.mark.asyncio
async def test_verify_missing_record_returns_false():
    svc = MemoryService()
    assert await svc.verify(T, uuid4()) is False
