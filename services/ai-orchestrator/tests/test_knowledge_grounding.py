"""Tests for ADR-0033 CDFL |OR| coupling (reasoning/knowledge/grounding.py):
authority-boosted ranking + foundational knowledge_coverage + the
"học 1 hiểu 10" generalisation gate.
"""
from ai_orchestrator.reasoning.knowledge.store import KnowledgeDocument
from ai_orchestrator.reasoning.knowledge.grounding import (
    authority_score,
    coverage_gate,
    knowledge_coverage,
    rank_by_authority,
)


def _doc(tier, distance, confidence=0.8):
    return KnowledgeDocument(title="t", content="c", tier=tier,
                             distance=distance, confidence=confidence)


# ── authority-boosted ranking ────────────────────────────────────────────────

def test_curated_outranks_market_at_similar_distance():
    market = _doc(tier=3, distance=0.18, confidence=0.8)      # slightly closer
    curated = _doc(tier=2, distance=0.20, confidence=0.9)     # foundational + matured
    ranked = rank_by_authority([market, curated])
    assert ranked[0] is curated                              # authority breaks the near-tie


def test_strong_similarity_still_wins():
    near = _doc(tier=3, distance=0.02, confidence=0.7)        # much closer
    far_curated = _doc(tier=1, distance=0.6, confidence=0.98)
    ranked = rank_by_authority([far_curated, near])
    assert ranked[0] is near                                 # similarity dominates


def test_authority_score_components():
    s = authority_score(_doc(tier=1, distance=0.2, confidence=0.9))
    assert s > 0.8                                           # boosted above raw sim 0.8


# ── foundational coverage ────────────────────────────────────────────────────

def test_coverage_empty_is_zero():
    assert knowledge_coverage([]) == 0.0


def test_coverage_ignores_volatile_and_tenant_tiers():
    docs = [_doc(tier=3, distance=0.05, confidence=0.9),
            _doc(tier=4, distance=0.05, confidence=0.9)]
    assert knowledge_coverage(docs) == 0.0


def test_coverage_grows_with_foundational_hits():
    few = [_doc(tier=2, distance=0.3, confidence=0.7)]
    many = [_doc(tier=2, distance=0.1, confidence=0.9) for _ in range(6)]
    assert knowledge_coverage(many) > knowledge_coverage(few)
    assert 0.0 < knowledge_coverage(few) < 1.0


def test_coverage_saturates_near_one():
    docs = [_doc(tier=1, distance=0.0, confidence=0.98) for _ in range(50)]
    cov = knowledge_coverage(docs)
    assert 0.99 <= cov <= 1.0                # saturating curve plateaus near 1


# ── generalisation gate ──────────────────────────────────────────────────────

def test_gate_high_coverage_generalises():
    g = coverage_gate(0.8)
    assert g["can_generalize"] is True and g["band"] == "đủ"


def test_gate_mid_coverage_cautious():
    g = coverage_gate(0.45)
    assert g["can_generalize"] is True and g["band"] == "thận trọng"


def test_gate_low_coverage_declines():
    g = coverage_gate(0.1)
    assert g["can_generalize"] is False and g["band"] == "chưa đủ"
    assert "cần bổ sung" in g["note"]
