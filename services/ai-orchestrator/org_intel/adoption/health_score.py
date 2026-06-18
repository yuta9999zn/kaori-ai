"""
AI-HSC-010..015 (P1-S7) — Adoption health score aggregation.

Composite health score (0-100) per workflow / department / tenant.
Plus classification (EXCELLENT / HEALTHY / AT_RISK / STRUGGLING) and
trend analysis (improving / declining / stable).

Phase 1 ships an unweighted average. Phase 1.5 adds per-signal
weighting based on tenant industry baselines.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .signals import SignalSample


class HealthClassification(str, Enum):
    """AI-HSC-014 — discretised health bucket for dashboard tiles."""
    EXCELLENT = "excellent"   # score ≥ 85
    HEALTHY = "healthy"       # 70 ≤ score < 85
    AT_RISK = "at_risk"       # 50 ≤ score < 70
    STRUGGLING = "struggling" # score < 50


@dataclass(frozen=True)
class HealthScore:
    """AI-HSC-010 — composite score wrapper.

    composite is 0-100 (display-friendly); per_signal is the underlying
    samples for drill-down.
    """
    composite: float
    classification: HealthClassification
    per_signal: tuple[SignalSample, ...]

    def __post_init__(self) -> None:
        if not (0.0 <= self.composite <= 100.0):
            raise ValueError(
                f"HealthScore.composite must be in [0, 100]; got {self.composite}"
            )


def compute_composite_score(samples: Iterable[SignalSample]) -> HealthScore:
    """AI-HSC-010 — average sample.score × 100 + classify.

    Empty input is treated as EXCELLENT (no signal = no resistance
    yet observed). UX may suppress the tile entirely in that state.
    """
    sample_list = tuple(samples)
    if not sample_list:
        return HealthScore(
            composite=100.0,
            classification=HealthClassification.EXCELLENT,
            per_signal=(),
        )
    avg = sum(s.score for s in sample_list) / len(sample_list)
    composite = round(avg * 100.0, 1)
    return HealthScore(
        composite=composite,
        classification=classify_health(composite),
        per_signal=sample_list,
    )


def classify_health(composite: float) -> HealthClassification:
    """AI-HSC-014 — bucketise the composite score."""
    if composite >= 85:
        return HealthClassification.EXCELLENT
    if composite >= 70:
        return HealthClassification.HEALTHY
    if composite >= 50:
        return HealthClassification.AT_RISK
    return HealthClassification.STRUGGLING


def detect_trend(scores_over_time: list[float]) -> str:
    """AI-HSC-015 — simple slope-based trend classifier.

    Uses linear regression on the score series. A small, dependency-
    free implementation (Phase 1 — no scipy needed). Phase 1.5 swaps in
    a smoothed series with seasonality detection.

    Returns 'improving' / 'declining' / 'stable'. Stable when |slope|
    < 1.0 score-points-per-period (noise floor).
    """
    if len(scores_over_time) < 2:
        return "stable"

    n = len(scores_over_time)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(scores_over_time) / n
    num = sum((xs[i] - mean_x) * (scores_over_time[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return "stable"
    slope = num / den
    if slope > 1.0:
        return "improving"
    if slope < -1.0:
        return "declining"
    return "stable"
