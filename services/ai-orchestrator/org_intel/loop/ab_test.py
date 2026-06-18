"""90-day A/B testing framework.

Pulls control samples from BaselineTracker (60-day baseline) and
treatment samples from the experiment window (90 days default).
Computes:
  * Relative lift = (treatment_mean - control_mean) / control_mean
  * Welch's t-statistic (unequal variances)
  * Conclusion: 'treatment_wins' / 'control_wins' / 'inconclusive'

Phase 1.5 uses a threshold-based decision (lift ≥ MIN_LIFT and
|t-stat| ≥ TSTAT_THRESHOLD). Phase 2 swaps for proper power calc +
multiple-test correction.

Defaults justified:
  MIN_LIFT          = 0.05  — 5% relative lift is the minimum practical
                              improvement for a manager to act on
  TSTAT_THRESHOLD   = 1.96  — two-sided ~95% (standard normal proxy
                              when n>30; Phase 2 use t-distribution
                              tables)
  EXPERIMENT_DAYS   = 90    — per CLAUDE.md §5 Stage 12 spec

Scope note vs DPEPO-style parallel exploration
----------------------------------------------
This framework is **single-treatment causal A/B** (1 control vs 1
treatment arm at a time). It is NOT the parallel-exploration analogue
of DPEPO (arXiv 2026, `LePanda026/Code-for-DPEPO`), which runs N
parallel envs per rollout for training-time sample efficiency.

The closer Kaori analogue to DPEPO's parallel rollout is
`reasoning.cdfl.agent.CDFLAgent.score_actions()`, which evaluates all
candidate actions in parallel via `LookaheadPlanner.score_actions()`
each call. That is action-selection parallelism (planning), not
production-A/B promotion. Don't confuse the two.

Multi-armed bandit (N treatments, traffic-split, online winner pick)
is also out of scope here — Phase 2 if a customer needs it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from .baseline import BaselineSummary, BaselineTracker


MIN_LIFT = 0.05
TSTAT_THRESHOLD = 1.96
EXPERIMENT_DAYS = 90


class ExperimentArm(str, Enum):
    CONTROL   = "control"
    TREATMENT = "treatment"


@dataclass(frozen=True)
class ABTestResult:
    """One A/B test conclusion."""
    tenant_id:        UUID
    experiment_id:    str
    metric_name:      str
    control:          BaselineSummary
    treatment:        BaselineSummary
    relative_lift:    float
    t_statistic:      float
    conclusion:       str   # 'treatment_wins' | 'control_wins' | 'inconclusive'
    reason:           str   # human-readable diagnostic
    computed_at:      datetime


def _welch_t(c: BaselineSummary, t: BaselineSummary) -> float:
    """Welch's t-statistic for unequal-variance two-sample test.
    Returns 0 when either variance is zero (no spread) — degenerate
    case; the threshold-based decision falls back to lift only."""
    n_c, n_t = c.sample_size, t.sample_size
    if n_c < 2 or n_t < 2:
        return 0.0
    denom_sq = (c.variance / n_c) + (t.variance / n_t)
    if denom_sq <= 0:
        return 0.0
    return (t.mean - c.mean) / math.sqrt(denom_sq)


class ABTestFramework:
    """Compute A/B conclusions against a BaselineTracker."""

    def __init__(self, tracker: BaselineTracker):
        self.tracker = tracker

    def evaluate(
        self, *,
        tenant_id: UUID,
        experiment_id: str,
        metric_name: str,
        baseline_window_days: int = 60,
        experiment_window_days: int = EXPERIMENT_DAYS,
        min_lift: float = MIN_LIFT,
        tstat_threshold: float = TSTAT_THRESHOLD,
        now: Optional[datetime] = None,
    ) -> ABTestResult:
        if now is None:
            now = datetime.now(timezone.utc)

        # Control = baseline (no experiment_id filter — pure baseline window)
        control = self.tracker.summary(
            tenant_id, metric_name,
            window_days=baseline_window_days, experiment_id=None, arm=None, now=now,
        )
        # Treatment = the experiment's treatment arm in the experiment window
        treatment = self.tracker.summary(
            tenant_id, metric_name,
            window_days=experiment_window_days,
            experiment_id=experiment_id, arm=ExperimentArm.TREATMENT.value,
            now=now,
        )

        if not control.is_valid:
            return ABTestResult(
                tenant_id=tenant_id, experiment_id=experiment_id,
                metric_name=metric_name, control=control, treatment=treatment,
                relative_lift=0.0, t_statistic=0.0,
                conclusion="inconclusive",
                reason=f"baseline too small (n={control.sample_size}, need ≥30)",
                computed_at=now,
            )
        if not treatment.is_valid:
            return ABTestResult(
                tenant_id=tenant_id, experiment_id=experiment_id,
                metric_name=metric_name, control=control, treatment=treatment,
                relative_lift=0.0, t_statistic=0.0,
                conclusion="inconclusive",
                reason=f"treatment arm too small (n={treatment.sample_size}, need ≥30)",
                computed_at=now,
            )

        if control.mean == 0:
            # Avoid div-by-zero on relative lift; fall back to absolute diff
            lift = float("inf") if treatment.mean > 0 else 0.0
        else:
            lift = (treatment.mean - control.mean) / control.mean
        t_stat = _welch_t(control, treatment)

        # Decision rules
        if abs(t_stat) < tstat_threshold:
            conclusion = "inconclusive"
            reason = (
                f"|t|={abs(t_stat):.2f} < {tstat_threshold} (95% threshold); "
                f"lift={lift:.4f}, control_n={control.sample_size}, "
                f"treatment_n={treatment.sample_size}"
            )
        elif lift >= min_lift and t_stat > 0:
            conclusion = "treatment_wins"
            reason = f"lift={lift:.4f} ≥ {min_lift}, t={t_stat:.2f} > 0"
        elif lift <= -min_lift and t_stat < 0:
            conclusion = "control_wins"
            reason = f"lift={lift:.4f} ≤ -{min_lift}, t={t_stat:.2f} < 0"
        else:
            conclusion = "inconclusive"
            reason = f"lift={lift:.4f} below threshold {min_lift}"

        return ABTestResult(
            tenant_id=tenant_id, experiment_id=experiment_id,
            metric_name=metric_name, control=control, treatment=treatment,
            relative_lift=lift, t_statistic=t_stat,
            conclusion=conclusion, reason=reason, computed_at=now,
        )
