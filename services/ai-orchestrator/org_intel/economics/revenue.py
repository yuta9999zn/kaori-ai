"""
NOV revenue estimators — Phase 1.5 ships 6/6 methods.

Methods:
  NOV-REV-001 ✅ Pre/Post comparison (P1-S7)
  NOV-REV-002 ✅ A/B attribution (P15-S10 D5)
  NOV-REV-003 ✅ Industry benchmark fallback (P1-S7)
  NOV-REV-004 ✅ KPI-to-revenue mapper (per industry — INDUSTRY_BENCHMARKS)
  NOV-REV-005 ✅ Confidence scoring on revenue estimates
  NOV-REV-006 ✅ Variance analysis (predicted vs actual) — P15-S11

All money returned as Decimal in VND (K-9). Never float.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RevenueEstimate:
    """NOV-REV-005 — revenue estimate + confidence + method label."""
    revenue_vnd: Decimal
    confidence: Decimal       # NUMERIC(5,4) range [0, 1]
    method: str               # 'pre_post' / 'industry_benchmark' / 'a_b'
    note: str | None = None


# NOV-REV-004 — KPI-to-revenue mapper. Industry-keyed.
# These are conservative defaults from Vietnam SME baseline data
# (Phase 1 hand-tuned; Phase 1.5+ replace with continuous baselining).
INDUSTRY_BENCHMARKS: dict[str, Decimal] = {
    "RETAIL":       Decimal("0.05"),   # 5% revenue uplift from churn intervention
    "F&B":          Decimal("0.04"),
    "FMCG":         Decimal("0.03"),
    "FINANCE":      Decimal("0.06"),
    "LOGISTICS":    Decimal("0.04"),
    "EDUCATION":    Decimal("0.03"),
    "HEALTHCARE":   Decimal("0.05"),
    "MANUFACTURING": Decimal("0.04"),
    "REAL_ESTATE":  Decimal("0.04"),
    "ECOMMERCE":    Decimal("0.06"),
    "BEAUTY":       Decimal("0.05"),
    "FASHION":      Decimal("0.04"),
}


def estimate_revenue_pre_post(
    *,
    revenue_30d_before_vnd: Decimal,
    revenue_30d_after_vnd: Decimal,
) -> RevenueEstimate:
    """NOV-REV-001 — compare 30 days before workflow deploy vs after.

    Confidence is high (0.7) for this method when both windows have
    data. The attribution risk (other factors changed in the window)
    is the main reason this isn't 1.0.
    """
    if revenue_30d_before_vnd <= 0:
        return RevenueEstimate(
            revenue_vnd=Decimal("0"),
            confidence=Decimal("0"),
            method="pre_post",
            note="pre-period revenue is zero or missing — falling back required",
        )
    delta = revenue_30d_after_vnd - revenue_30d_before_vnd
    return RevenueEstimate(
        revenue_vnd=delta if delta > 0 else Decimal("0"),
        confidence=Decimal("0.7"),
        method="pre_post",
        note=f"Δrevenue = {delta} VND ({revenue_30d_after_vnd} - {revenue_30d_before_vnd})",
    )


def estimate_revenue_ab_attribution(
    *,
    control_revenue_vnd: Decimal,
    treatment_revenue_vnd: Decimal,
    control_group_size: int,
    treatment_group_size: int,
    total_population: int | None = None,
) -> RevenueEstimate:
    """NOV-REV-002 — revenue uplift attributed via explicit A/B test.

    Compute per-user revenue in each group, take the treatment-vs-control
    delta, scale up to the full population (or sum of both groups when
    total_population not supplied). The result is the marginal monthly
    revenue attributable to the workflow being tested.

    Confidence rises with sample size (statistical power):
      both groups ≥ 1000 users → 0.9   (high confidence)
      both groups ≥ 100  users → 0.8   (good confidence)
      both groups ≥ 30   users → 0.5   (acceptable, narrow margin)
      either  group < 30 users → 0.2   (sample too small, advisory only)

    The 30-threshold is the rule-of-thumb for the central limit theorem;
    below it the per-user means aren't normally distributed enough to
    trust a simple difference. Phase 2 may add bootstrap CI / t-test
    for tighter confidence; Phase 1.5 keeps it heuristic.

    Args:
        control_revenue_vnd:    total VND revenue across the control group
                                during the experiment window
        treatment_revenue_vnd:  same for the treatment group
        control_group_size:     # of unique customers in control
        treatment_group_size:   # of unique customers in treatment
        total_population:       # of customers the workflow would reach
                                if rolled out 100%. When None, defaults to
                                control_group_size + treatment_group_size
                                (i.e. attribute to the experiment cohort
                                only — conservative).

    Returns:
        RevenueEstimate with method='a_b' and revenue_vnd = positive
        delta-per-user × total_population (clipped to 0 when treatment
        underperforms — A/B losses don't credit to the workflow).
    """
    if control_group_size <= 0 or treatment_group_size <= 0:
        return RevenueEstimate(
            revenue_vnd=Decimal("0"),
            confidence=Decimal("0"),
            method="a_b",
            note=(
                f"a_b attribution requires both groups >0 customers; "
                f"got control={control_group_size}, treatment={treatment_group_size}"
            ),
        )

    control_per_user = control_revenue_vnd / Decimal(control_group_size)
    treatment_per_user = treatment_revenue_vnd / Decimal(treatment_group_size)
    delta_per_user = treatment_per_user - control_per_user

    # Treatment underperformed → no positive uplift to attribute. We still
    # return the (negative) delta in note so reviewers see the experiment
    # signal even though revenue_vnd is clipped at 0.
    if delta_per_user <= 0:
        return RevenueEstimate(
            revenue_vnd=Decimal("0"),
            confidence=_ab_confidence(control_group_size, treatment_group_size),
            method="a_b",
            note=(
                f"treatment did not beat control: "
                f"Δ/user = {delta_per_user} VND "
                f"(treatment {treatment_per_user} - control {control_per_user})"
            ),
        )

    population = total_population if total_population is not None else (
        control_group_size + treatment_group_size
    )
    revenue = (delta_per_user * Decimal(population)).quantize(Decimal("0.0001"))

    return RevenueEstimate(
        revenue_vnd=revenue,
        confidence=_ab_confidence(control_group_size, treatment_group_size),
        method="a_b",
        note=(
            f"Δ/user = {delta_per_user} VND × population {population} "
            f"= {revenue} VND (control n={control_group_size}, "
            f"treatment n={treatment_group_size})"
        ),
    )


def _ab_confidence(control_n: int, treatment_n: int) -> Decimal:
    """Sample-size-driven confidence per docstring of estimate_revenue_ab_attribution.

    Internal helper so the threshold table is one-place-to-update; revenue.py
    keeps the public surface to the three estimators + confidence scoring
    NOV-REV-005 logic.
    """
    smaller = min(control_n, treatment_n)
    if smaller < 30:
        return Decimal("0.2")
    if smaller < 100:
        return Decimal("0.5")
    if smaller < 1000:
        return Decimal("0.8")
    return Decimal("0.9")


def estimate_revenue_industry_benchmark(
    *,
    industry: str,
    annual_revenue_vnd: Decimal,
) -> RevenueEstimate:
    """NOV-REV-003 — when no baseline exists, scale annual revenue by
    the industry benchmark uplift rate.

    Confidence is medium (0.4) — we're guessing based on industry
    averages. Better than nothing for new tenants who haven't been on
    Kaori long enough for pre/post.
    """
    industry_key = industry.upper().strip()
    rate = INDUSTRY_BENCHMARKS.get(industry_key)
    if rate is None:
        return RevenueEstimate(
            revenue_vnd=Decimal("0"),
            confidence=Decimal("0"),
            method="industry_benchmark",
            note=f"unknown industry={industry!r}; no benchmark available",
        )
    monthly = (annual_revenue_vnd * rate) / Decimal("12")
    return RevenueEstimate(
        revenue_vnd=monthly.quantize(Decimal("0.0001")),
        confidence=Decimal("0.4"),
        method="industry_benchmark",
        note=f"{industry_key} benchmark = {rate * 100}% annual revenue; "
             f"monthly = {monthly} VND",
    )


# ─── NOV-REV-006 — Variance analysis (predicted vs actual) ─────────


@dataclass(frozen=True)
class VarianceAnalysis:
    """Variance between a predicted revenue estimate (from any of the 3
    methods above) and the actual measured revenue afterwards.

    A negative variance means we OVER-estimated; positive means we
    UNDER-estimated. The verdict label is what the FE renders for the
    CFO digest:
      |relative_variance| ≤ 0.10  → 'on_target'
      0.10 < |relative| ≤ 0.30   → 'modest_drift'
      0.30 < |relative| ≤ 0.50   → 'significant_drift'
      |relative| > 0.50           → 'estimate_unreliable'

    Confidence is taken from the predicted side — variance can't be
    more confident than the source estimate.
    """
    predicted_vnd:      Decimal
    actual_vnd:         Decimal
    variance_vnd:       Decimal     # actual - predicted
    relative_variance:  Decimal     # variance / predicted (signed; 0 when predicted=0)
    verdict:            str         # on_target / modest_drift / significant_drift / estimate_unreliable
    confidence:         Decimal
    note:               str | None = None


def estimate_revenue_variance(
    *,
    predicted_vnd: Decimal,
    actual_vnd: Decimal,
    predicted_confidence: Decimal = Decimal("0.7"),
) -> VarianceAnalysis:
    """NOV-REV-006 — variance between a prior prediction and observed
    actual. Used by the CFO digest (NOV-RPT-020) to show "we predicted
    X, actual was Y; verdict = on_target".

    Args:
      predicted_vnd: the original RevenueEstimate.revenue_vnd
      actual_vnd:    measured revenue uplift in the same window
      predicted_confidence: confidence of the original estimate (cap)
    """
    variance = actual_vnd - predicted_vnd
    if predicted_vnd == 0:
        relative = Decimal("0") if actual_vnd == 0 else Decimal("1")
        verdict = "on_target" if actual_vnd == 0 else "estimate_unreliable"
        return VarianceAnalysis(
            predicted_vnd=predicted_vnd, actual_vnd=actual_vnd,
            variance_vnd=variance, relative_variance=relative,
            verdict=verdict, confidence=predicted_confidence,
            note="predicted=0; variance ratio undefined — verdict from actual only",
        )

    relative = (variance / predicted_vnd).quantize(Decimal("0.0001"))
    abs_rel = abs(relative)
    if abs_rel <= Decimal("0.10"):
        verdict = "on_target"
    elif abs_rel <= Decimal("0.30"):
        verdict = "modest_drift"
    elif abs_rel <= Decimal("0.50"):
        verdict = "significant_drift"
    else:
        verdict = "estimate_unreliable"

    return VarianceAnalysis(
        predicted_vnd=predicted_vnd,
        actual_vnd=actual_vnd,
        variance_vnd=variance,
        relative_variance=relative,
        verdict=verdict,
        confidence=predicted_confidence,
        note=(
            f"actual = {actual_vnd} VND; predicted = {predicted_vnd} VND; "
            f"Δ = {variance} ({relative * 100:.2f}%)"
        ),
    )
