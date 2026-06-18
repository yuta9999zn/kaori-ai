"""Stage 7 — Memory System tests.

Pure Python; in-memory tier stores. Validates:
  * Compute importance per §7.5 formula
  * Write lands at default tier per type
  * Retrieve scores by token-set similarity across tiers + session filter
  * Consolidate drains L2 → L3
  * Promote moves L3 → L4 above threshold
  * Forget — TTL mode and full-tenant-wipe mode
  * Introspect groups by entity_id across all tiers
  * K-1: every method tenant-filtered (cross-tenant rows ignored)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.memory import (
    InMemoryTierStore,
    MemoryRecord,
    MemoryService,
    MemoryTier,
    MemoryType,
    compute_importance,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")


# ─── compute_importance ─────────────────────────────────────────────


class TestComputeImportance:

    def test_brand_new_no_flags(self):
        r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x")
        s = compute_importance(r)
        # Fresh record (days_old=0) → recency 1.0 * 0.2; no other contributors.
        assert s == pytest.approx(0.2, abs=1e-6)

    def test_user_flagged_lifts_score(self):
        r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x",
                          user_flagged_important=True)
        # 0.2 recency + 0.3 flag = 0.5
        assert compute_importance(r) == pytest.approx(0.5, abs=1e-6)

    def test_high_value_outcome_lifts_score(self):
        r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.OPERATIONAL, content="x",
                          linked_outcome_value=20_000_000)
        # 0.2 recency + 0.2 outcome = 0.4
        assert compute_importance(r) == pytest.approx(0.4, abs=1e-6)

    def test_repeated_appearances_lifts_score(self):
        r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x",
                          session_appearance_count=10)   # caps at min(1, 10/5)=1
        # 0.2 recency + 0.3 repeat = 0.5
        assert compute_importance(r) == pytest.approx(0.5, abs=1e-6)

    def test_old_record_loses_recency(self):
        r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x",
                          occurred_at=datetime.now(timezone.utc) - timedelta(days=180))
        # 180 days old → recency component = max(0, 1 - 180/90) = 0
        s = compute_importance(r)
        assert s == pytest.approx(0.0, abs=1e-6)

    def test_capped_at_1(self):
        r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x",
                          user_flagged_important=True,
                          linked_outcome_value=20_000_000,
                          session_appearance_count=20)
        s = compute_importance(r)
        # 0.2 + 0.3 + 0.3 + 0.2 = 1.0 exact
        assert s == pytest.approx(1.0, abs=1e-6)


# ─── Write tier routing ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_episodic_lands_at_l2():
    svc = MemoryService()
    r = await svc.write(T1, MemoryType.EPISODIC, "user said hi")
    assert r.tier == MemoryTier.L2_SHORT


@pytest.mark.asyncio
async def test_write_semantic_lands_at_l4():
    svc = MemoryService()
    r = await svc.write(T1, MemoryType.SEMANTIC, "VN retail Q1 lull")
    assert r.tier == MemoryTier.L4_LONG


@pytest.mark.asyncio
async def test_write_decision_lands_at_l3():
    svc = MemoryService()
    r = await svc.write(T1, MemoryType.DECISION, "approved invoice INV-001")
    assert r.tier == MemoryTier.L3_CONSOLIDATED


# ─── Retrieve ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retrieve_token_match_scores_higher():
    svc = MemoryService()
    await svc.write(T1, MemoryType.EPISODIC, "Khách hàng VIP chi nhánh Hà Nội")
    await svc.write(T1, MemoryType.EPISODIC, "Sản phẩm mới ra mắt tháng 5")
    out = await svc.retrieve(T1, "khách hàng Hà Nội", top_k=5)
    assert len(out) >= 1
    assert "Hà Nội" in out[0].content


@pytest.mark.asyncio
async def test_retrieve_min_score_drops_weak_overlap():
    """A query sharing only one generic token must be droppable via min_score.

    Audit 2026-06-02: an off-domain question recalled retention memories on a
    pure-stopword overlap (Jaccard ~0.1), and each weak hit inflated the |OR|
    coverage gate's memory mass. A relevance floor stops that. Default floor
    is 0.0 (unchanged: only score>0 kept)."""
    svc = MemoryService()
    await svc.write(T1, MemoryType.EPISODIC, "alpha beta gamma delta epsilon")
    q = "alpha one two three four"               # shares only "alpha" → Jaccard ≈ 0.11
    kept = await svc.retrieve(T1, q, top_k=5)                       # default floor 0 → kept
    assert len(kept) == 1
    dropped = await svc.retrieve(T1, q, top_k=5, min_score=0.5)     # floor → dropped
    assert dropped == []


@pytest.mark.asyncio
async def test_retrieve_tenant_isolated():
    svc = MemoryService()
    await svc.write(T1, MemoryType.EPISODIC, "tenant 1 secret data")
    out = await svc.retrieve(T2, "secret data", top_k=5)
    assert out == []


@pytest.mark.asyncio
async def test_retrieve_session_filter_on_l2():
    svc = MemoryService()
    # L2 records — session-scoped
    await svc.write(T1, MemoryType.EPISODIC, "alpha", session_id="s1")
    await svc.write(T1, MemoryType.EPISODIC, "alpha", session_id="s2")
    # When session_id specified, only L2 records of that session pass
    out = await svc.retrieve(T1, "alpha", top_k=5, session_id="s1")
    assert len(out) == 1
    assert out[0].session_id == "s1"


@pytest.mark.asyncio
async def test_retrieve_tier_restriction():
    svc = MemoryService()
    await svc.write(T1, MemoryType.SEMANTIC, "VN retail lull")        # → L4
    await svc.write(T1, MemoryType.DECISION, "approved INV-001 retail")  # → L3
    out_l4 = await svc.retrieve(T1, "retail", top_k=5, tier="L4_LONG")
    assert len(out_l4) == 1
    assert out_l4[0].memory_type == MemoryType.SEMANTIC


@pytest.mark.asyncio
async def test_retrieve_invalid_tier_rejects():
    svc = MemoryService()
    with pytest.raises(ValueError, match="tier must be"):
        await svc.retrieve(T1, "x", tier="L5_FAKE")


# ─── Consolidate (L2 → L3) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_consolidate_drains_l2_to_l3():
    svc = MemoryService()
    await svc.write(T1, MemoryType.EPISODIC, "a")
    await svc.write(T1, MemoryType.EPISODIC, "b")
    moved = await svc.consolidate(T1)
    assert moved == 2
    # L2 empty, L3 has 2
    assert await svc.l2.list_all(T1) == []
    assert len(await svc.l3.list_all(T1)) == 2


@pytest.mark.asyncio
async def test_consolidate_only_target_tenant():
    svc = MemoryService()
    await svc.write(T1, MemoryType.EPISODIC, "t1")
    await svc.write(T2, MemoryType.EPISODIC, "t2")
    await svc.consolidate(T1)
    # T2's L2 record untouched
    t2_l2 = await svc.l2.list_all(T2)
    assert len(t2_l2) == 1


# ─── Promote (L3 → L4) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_above_threshold_moves_to_l4():
    svc = MemoryService()
    high = await svc.write(T1, MemoryType.DECISION, "important decision",
                            user_flagged_important=True, linked_outcome_value=50_000_000)
    low = await svc.write(T1, MemoryType.OPERATIONAL, "tiny outcome")
    moved = await svc.promote(T1)
    # high: 0.2 + 0.3 (flag) + 0.2 (outcome) = 0.7 → not strictly > 0.7
    # Need higher score → bump appearance count first
    pass

    # Run again with the appearance count: retrieve doesn't bump unless
    # text matches; do it explicitly here for the test.
    high.session_appearance_count = 5
    moved = await svc.promote(T1)
    # high score now 0.2 + 0.3 + 0.3 + 0.2 = 1.0 > 0.7 → move
    # low score 0.2 < 0.7 → stay
    assert moved >= 1
    l4_recs = await svc.l4.list_all(T1)
    assert any(r.record_id == high.record_id for r in l4_recs)


# ─── Forget ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forget_full_tenant_wipes_all_tiers():
    svc = MemoryService()
    await svc.write(T1, MemoryType.EPISODIC, "in L2")
    await svc.write(T1, MemoryType.DECISION, "in L3")
    await svc.write(T1, MemoryType.SEMANTIC, "in L4")
    # Also put a T2 record to verify isolation
    await svc.write(T2, MemoryType.SEMANTIC, "t2 untouched")

    wiped = await svc.forget(T1, full_tenant_wipe=True)
    assert wiped >= 3

    # All T1 tiers empty
    for t in (svc.l1, svc.l2, svc.l3, svc.l4):
        assert await t.list_all(T1) == []
    # T2 intact
    assert len(await svc.l4.list_all(T2)) == 1


@pytest.mark.asyncio
async def test_forget_ttl_sweep_skips_recent_and_important():
    svc = MemoryService()
    # Old + low score → should be wiped
    r_old_low = await svc.write(T1, MemoryType.OPERATIONAL, "noise")
    r_old_low.occurred_at = datetime.now(timezone.utc) - timedelta(days=200)
    # Old + high score (user flagged) → KEEP
    r_old_high = await svc.write(T1, MemoryType.OPERATIONAL, "important", user_flagged_important=True)
    r_old_high.occurred_at = datetime.now(timezone.utc) - timedelta(days=200)
    # Recent + low score → KEEP (TTL doesn't fire yet)
    await svc.write(T1, MemoryType.OPERATIONAL, "fresh")

    wiped = await svc.forget(T1)
    assert wiped == 1   # only r_old_low matched the criteria
    remaining = await svc.l3.list_all(T1)
    assert any(r.record_id == r_old_high.record_id for r in remaining)


# ─── Introspect ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_introspect_groups_by_entity_across_tiers():
    svc = MemoryService()
    ent_a = uuid4()
    ent_b = uuid4()
    # Place memories about entity A across 3 tiers + one about B
    await svc.write(T1, MemoryType.EPISODIC, "a-l2-1", entity_id=ent_a)        # L2
    await svc.write(T1, MemoryType.DECISION, "a-l3-1", entity_id=ent_a)        # L3
    await svc.write(T1, MemoryType.SEMANTIC, "a-l4-1", entity_id=ent_a)        # L4
    await svc.write(T1, MemoryType.SEMANTIC, "b-l4-1", entity_id=ent_b)        # L4

    out = await svc.introspect(T1, ent_a)
    assert len(out) == 3
    assert all(r.entity_id == ent_a for r in out)


# ─── Defensive: InMemoryTierStore round-trip ────────────────────────


@pytest.mark.asyncio
async def test_in_memory_tier_store_round_trip():
    store = InMemoryTierStore(MemoryTier.L3_CONSOLIDATED)
    r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.OPERATIONAL, content="x")
    await store.put(r)
    got = await store.get(T1, r.record_id)
    assert got is not None
    # Tier is overwritten to the store's tier on put
    assert got.tier == MemoryTier.L3_CONSOLIDATED


@pytest.mark.asyncio
async def test_in_memory_tier_store_delete():
    store = InMemoryTierStore(MemoryTier.L2_SHORT)
    r = MemoryRecord(tenant_id=T1, memory_type=MemoryType.EPISODIC, content="x")
    await store.put(r)
    assert await store.delete(T1, r.record_id) is True
    assert await store.delete(T1, r.record_id) is False   # idempotent miss


@pytest.mark.asyncio
async def test_in_memory_tier_store_forget_isolates_tenant():
    store = InMemoryTierStore(MemoryTier.L4_LONG)
    await store.put(MemoryRecord(tenant_id=T1, memory_type=MemoryType.SEMANTIC, content="t1"))
    await store.put(MemoryRecord(tenant_id=T2, memory_type=MemoryType.SEMANTIC, content="t2"))
    n = await store.forget(T1)
    assert n == 1
    assert len(await store.list_all(T2)) == 1
