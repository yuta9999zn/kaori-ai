"""Four-fold DE report (NNL-NTHT 12-axiom) — a Dark-Existence dashboard.

DE is the unknown across four faces (Tiên đề 4-5): không gian (X), thời gian (T),
IF chưa biết, MF chưa biết — and DE ≠ DE_IF + DE_MF (they overlap; reported as
faces, not summed). This module ASSEMBLES the four faces from signals Kaori
already computes — it is a typed gauge/dashboard, NOT a new measurement:

  x   (không gian) : data not yet pulled into OR        ← analysis data coverage
  t   (thời gian)  : staleness of cited knowledge        ← aging/freshness (ADR-0033)
  if_ (IF chưa biết): foundational-knowledge coverage gap ← knowledge_coverage (đốm trắng)
  mf  (MF chưa biết): claims not grounded in measured data ← grounding score (đốm đen)

Each input is a manifest-fraction in [0,1] (1 = fully known on that face); the
DE face = 1 − signal. `manifest_or` is the rough fraction of "light" overall.
A dashboard, not a proof (same honesty caveat as grounding.py / hilbert_metric).
"""
from __future__ import annotations

from dataclasses import dataclass


def _clip01(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else float(v)


@dataclass(frozen=True)
class FourFoldDE:
    x: float    # không-gian-tối  (1 = much data unseen)
    t: float    # thời-gian-tối   (1 = knowledge stale)
    if_: float  # IF-tối          (1 = foundational coverage thin)
    mf: float   # MF-tối          (1 = claims ungrounded)

    @property
    def faces(self) -> dict[str, float]:
        return {"x": self.x, "t": self.t, "if": self.if_, "mf": self.mf}

    def max_dark(self) -> float:
        """The worst face — the binding constraint on trusting an insight."""
        return max(self.x, self.t, self.if_, self.mf)

    def manifest_or(self) -> float:
        """Rough fraction of 'light' = 1 − mean(dark faces). Gauge only."""
        return 1.0 - (self.x + self.t + self.if_ + self.mf) / 4.0


def assemble_de(
    *,
    data_coverage: float,
    knowledge_freshness: float,
    knowledge_coverage: float,
    grounding_score: float,
) -> FourFoldDE:
    """Build the four-fold DE from four manifest-fractions in [0,1].

    data_coverage      — share of needed analysis data actually pulled (X-face)
    knowledge_freshness — 1 = cited KB fresh, 0 = stale (T-face; ADR-0033 aging)
    knowledge_coverage — foundational coverage of the question (IF-face; ADR-0033)
    grounding_score    — share of numeric claims matched to facts (MF-face; grounding.py)
    """
    return FourFoldDE(
        x=1.0 - _clip01(data_coverage),
        t=1.0 - _clip01(knowledge_freshness),
        if_=1.0 - _clip01(knowledge_coverage),
        mf=1.0 - _clip01(grounding_score),
    )
