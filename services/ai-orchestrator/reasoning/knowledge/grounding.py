"""ADR-0033 — CDFL |OR| coupling for the knowledge base.

Pure functions over retrieved KnowledgeDocuments (no DB, no LLM — trivially
testable):

  rank_by_authority  — rerank cosine hits by authority tier + maturity
  knowledge_coverage — how well FOUNDATIONAL knowledge covers a query, in [0,1]
  coverage_gate      — turn coverage into a generalize / "chưa đủ" decision

The coverage signal is the **"học 1 hiểu 10" gate**: high coverage (rich, mature,
relevant *foundational* knowledge) lets the reasoner generalise confidently; low
coverage makes it decline and ask for more knowledge instead of hallucinating
(K-3 / anti-bịa). As the foundational KB ages and grows (ADR-0033 aging),
coverage rises and more generalisation unlocks — the |OR| (IF↔MF overlap,
`cdfl/hilbert_metric.py`) made operational for the knowledge layer.

Only foundational tiers (1 regulatory, 2 curated) count toward coverage: it is
the *durable* understanding that grows "càng nhiều tháng càng biết nhiều", not
the volatile market tier (3) or tenant notes (4).
"""
from __future__ import annotations

import math
import os

from .store import KnowledgeDocument

FOUNDATIONAL_TIERS = (1, 2)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Similarity dominates ranking; authority + maturity only break near-ties so a
# curated, well-validated principle wins over a market note at similar sim.
_W_AUTHORITY = _env_float("KAORI_KB_W_AUTHORITY", 0.15)
_W_MATURITY = _env_float("KAORI_KB_W_MATURITY", 0.10)
# Saturation rate of the coverage curve, and the generalisation thresholds.
_COVERAGE_K = _env_float("KAORI_KB_COVERAGE_K", 0.6)
_GEN_MIN = _env_float("KAORI_KB_GEN_MIN", 0.60)        # ≥ → generalise
_GEN_CAUTION = _env_float("KAORI_KB_GEN_CAUTION", 0.30)  # ≥ → generalise cautiously


def _similarity(doc: KnowledgeDocument) -> float:
    """pgvector cosine DISTANCE → similarity in [0,1] (smaller distance = closer)."""
    d = doc.distance
    if d is None:
        return 0.0
    return max(0.0, 1.0 - d)


def _tier_rank(tier: int) -> float:
    """tier 1 → 1.0 (highest authority) … tier 4 → 0.25."""
    return max(0.0, (5 - tier) / 4.0)


def authority_score(doc: KnowledgeDocument, *,
                    w_authority: float = _W_AUTHORITY,
                    w_maturity: float = _W_MATURITY) -> float:
    """Combined rank: semantic similarity nudged by authority tier + maturity."""
    return (_similarity(doc)
            + w_authority * _tier_rank(doc.tier)
            + w_maturity * float(doc.confidence))


def rank_by_authority(docs: list[KnowledgeDocument], *,
                      w_authority: float = _W_AUTHORITY,
                      w_maturity: float = _W_MATURITY) -> list[KnowledgeDocument]:
    """Rerank cosine hits by authority_score, highest first (stable)."""
    return sorted(
        docs,
        key=lambda d: authority_score(d, w_authority=w_authority, w_maturity=w_maturity),
        reverse=True,
    )


def knowledge_coverage(docs: list[KnowledgeDocument], *, k: float = _COVERAGE_K) -> float:
    """Saturating coverage of a query by FOUNDATIONAL knowledge, in [0,1):
    ``1 − exp(−k × Σ sim_i × confidence_i)`` over tier 1/2 docs. More relevant +
    more confident foundational hits → higher coverage. Volatile (tier 3) and
    tenant (tier 4) docs do NOT count — coverage measures durable understanding."""
    mass = sum(_similarity(d) * float(d.confidence)
               for d in docs if d.tier in FOUNDATIONAL_TIERS)
    return round(1.0 - math.exp(-k * mass), 4)


def coverage_gate(coverage: float) -> dict:
    """The "học 1 hiểu 10" gate: high coverage → generalise; mid → generalise
    cautiously; low → decline (don't hallucinate, ask for foundational knowledge).
    Returns {can_generalize, band, note} for the insight/narrative layer."""
    if coverage >= _GEN_MIN:
        return {"can_generalize": True, "band": "đủ", "coverage": coverage,
                "note": f"Độ phủ tri thức nền {coverage:.0%} — đủ để khái quát hoá (học 1 hiểu 10)."}
    if coverage >= _GEN_CAUTION:
        return {"can_generalize": True, "band": "thận trọng", "coverage": coverage,
                "note": f"Độ phủ tri thức nền {coverage:.0%} — khái quát hoá THẬN TRỌNG, nêu rõ giả định."}
    return {"can_generalize": False, "band": "chưa đủ", "coverage": coverage,
            "note": f"Độ phủ tri thức nền chỉ {coverage:.0%} — CHƯA khái quát hoá; cần bổ sung kiến thức nền."}
