"""
P2-S21 D7 — NOV-RPT-024 Net Operational Value simulation (what-if).

Given a baseline NOV row + a scenario change (revenue uplift % +
cost reduction % + user count delta), project the resulting NOV with
a confidence interval.

Pure computation — no I/O. Caller (routers/economics.py) loads the
baseline from `monthly_digests` then passes the dataclass in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class BaselineDigest:
    """Compact NOV baseline for simulation input. Mirrors the relevant
    fields from MonthlyDigestRow."""
    enterprise_id:       UUID
    period_label:        str             # 'YYYY-MM' or 'YYYY-Qn'
    revenue_vnd:         Decimal
    people_cost_vnd:     Decimal
    ai_cost_vnd:         Decimal
    infra_cost_vnd:      Decimal
    integration_cost_vnd: Decimal
    setup_amortized_vnd: Decimal = Decimal("0")
    user_count:          int = 1


@dataclass(frozen=True)
class ScenarioChange:
    """What-if scenario. All deltas relative to baseline. NEGATIVE
    reductions allowed (downward scenarios)."""
    revenue_uplift_pct:      Decimal = Decimal("0")     # +10 = +10% revenue
    cost_reduction_pct:      Decimal = Decimal("0")     # +10 = -10% cost
    people_cost_change_pct:  Decimal = Decimal("0")     # +5 = +5% people cost only
    ai_cost_change_pct:      Decimal = Decimal("0")
    user_count_change:       int = 0
    notes:                   Optional[str] = None


@dataclass(frozen=True)
class SimulationResult:
    """Projection output. Confidence interval = 95% under additive uncertainty."""
    baseline_nov_vnd:        Decimal
    projected_nov_vnd:       Decimal
    delta_vnd:               Decimal
    delta_pct:               Decimal
    confidence_low_vnd:      Decimal
    confidence_high_vnd:     Decimal
    assumptions:             tuple[str, ...]


# Uncertainty multiplier: ±10% of projected NOV at 95% CI.
# Phase 1.5 is a heuristic; Phase 2 swap to bootstrapped CI from historical variance.
_UNCERTAINTY_PCT = Decimal("0.10")
_QUANTUM = Decimal("0.0001")    # 4 decimals for NUMERIC(14,4)


def _round(v: Decimal) -> Decimal:
    """Round to 4 decimal places (NUMERIC(14,4) per K-9)."""
    return v.quantize(_QUANTUM, rounding=ROUND_HALF_UP)


def _baseline_total_cost(b: BaselineDigest) -> Decimal:
    return (
        b.people_cost_vnd + b.ai_cost_vnd + b.infra_cost_vnd
        + b.integration_cost_vnd + b.setup_amortized_vnd
    )


def _baseline_nov(b: BaselineDigest) -> Decimal:
    return b.revenue_vnd - _baseline_total_cost(b)


def simulate_nov(
    baseline: BaselineDigest,
    scenario: ScenarioChange,
) -> SimulationResult:
    """Project NOV under the scenario. Pure function.

    Mechanics:
      1. Apply revenue_uplift_pct + user_count_change (linear scaling)
         to revenue.
      2. Apply cost_reduction_pct as a flat % reduction across all cost
         buckets, then layer per-bucket changes (people_change, ai_change)
         on top.
      3. Compute NOV = projected_revenue - projected_total_cost.
      4. CI: projected_nov × (1 ± _UNCERTAINTY_PCT).
    """
    assumptions: list[str] = []

    # 1. Revenue
    revenue_mult = Decimal("1") + scenario.revenue_uplift_pct / Decimal("100")
    if scenario.user_count_change != 0 and baseline.user_count > 0:
        user_mult = (
            Decimal(baseline.user_count + scenario.user_count_change)
            / Decimal(baseline.user_count)
        )
        revenue_mult *= user_mult
        assumptions.append(
            f"User count {baseline.user_count} → "
            f"{baseline.user_count + scenario.user_count_change}, "
            f"revenue scales linearly."
        )
    projected_revenue = _round(baseline.revenue_vnd * revenue_mult)

    if scenario.revenue_uplift_pct != Decimal("0"):
        assumptions.append(
            f"Revenue uplift {scenario.revenue_uplift_pct}% assumes "
            f"customer mix + product unchanged."
        )

    # 2. Costs — flat reduction then per-bucket layered
    flat_mult = Decimal("1") - scenario.cost_reduction_pct / Decimal("100")
    people_mult = flat_mult * (
        Decimal("1") + scenario.people_cost_change_pct / Decimal("100")
    )
    ai_mult = flat_mult * (
        Decimal("1") + scenario.ai_cost_change_pct / Decimal("100")
    )
    projected_people = _round(baseline.people_cost_vnd * people_mult)
    projected_ai     = _round(baseline.ai_cost_vnd * ai_mult)
    projected_infra  = _round(baseline.infra_cost_vnd * flat_mult)
    projected_integ  = _round(baseline.integration_cost_vnd * flat_mult)
    projected_setup  = baseline.setup_amortized_vnd  # one-off doesn't scale

    if scenario.cost_reduction_pct != Decimal("0"):
        assumptions.append(
            f"Cost reduction {scenario.cost_reduction_pct}% applied flat "
            f"across people/ai/infra/integration; setup amortization unchanged."
        )

    projected_total_cost = (
        projected_people + projected_ai + projected_infra
        + projected_integ + projected_setup
    )

    # 3. NOV
    projected_nov = projected_revenue - projected_total_cost
    baseline_nov = _baseline_nov(baseline)
    delta = projected_nov - baseline_nov

    if baseline_nov == Decimal("0"):
        delta_pct = Decimal("0")
        assumptions.append("Baseline NOV is 0; relative delta undefined → 0.")
    else:
        delta_pct = _round((delta / abs(baseline_nov)) * Decimal("100"))

    # 4. CI: ±10% of |projected_nov|
    abs_proj = abs(projected_nov)
    halfwidth = _round(abs_proj * _UNCERTAINTY_PCT)
    ci_low = _round(projected_nov - halfwidth)
    ci_high = _round(projected_nov + halfwidth)

    assumptions.append(
        f"Confidence interval ±{_UNCERTAINTY_PCT * Decimal('100')}% — "
        f"Phase 1.5 heuristic; Phase 2 will bootstrap from historical variance."
    )

    return SimulationResult(
        baseline_nov_vnd=_round(baseline_nov),
        projected_nov_vnd=_round(projected_nov),
        delta_vnd=_round(delta),
        delta_pct=delta_pct,
        confidence_low_vnd=ci_low,
        confidence_high_vnd=ci_high,
        assumptions=tuple(assumptions),
    )
