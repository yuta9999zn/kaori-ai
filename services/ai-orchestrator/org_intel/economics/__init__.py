"""Operational Economics (NOV) — Net Operational Value computation in VND.

Phase 1 v4 P1-S7 ships:
  * Revenue estimators: pre/post comparison + industry benchmark fallback
  * Cost calculators: people time + AI tokens + infrastructure + integrations
  * Monthly NOV = revenue - cost (NOV-CORE-013)
  * Time-to-payback projection (NOV-CORE-014)
  * Per-tenant + per-department rollup (NOV-CORE-017/018)

Phase 1.5 P15-S10 ships NOV-REV-002 (A/B attribution method).

Phase 2 extract: services/economics/ (skeleton P15-S9 follow-up).
"""

from .revenue import (
    INDUSTRY_BENCHMARKS,
    VarianceAnalysis,
    estimate_revenue_ab_attribution,
    estimate_revenue_industry_benchmark,
    estimate_revenue_pre_post,
    estimate_revenue_variance,
)
from .cost import (
    AmortizedCost,
    OpportunityCost,
    amortize_setup_cost,
    estimate_ai_token_cost,
    estimate_infrastructure_cost,
    estimate_integration_cost,
    estimate_opportunity_cost,
    estimate_people_cost,
    monthly_run_rate,
)
from .nov import NOVResult, compute_monthly_nov, time_to_payback_months
from .persistence import (
    MonthlyDigestRow,
    fetch_current_digest,
    fetch_quarter_window,
    fetch_trend,
    upsert_monthly_digest,
)
from .cfo_digest import (
    CFOQuarterlyDigest,
    CostBreakdown,
    PeriodComparison,
    build_quarterly_digest,
    quarter_bounds,
    quarter_label,
)

__all__ = [
    "AmortizedCost",
    "OpportunityCost",
    "CFOQuarterlyDigest",
    "CostBreakdown",
    "INDUSTRY_BENCHMARKS",
    "MonthlyDigestRow",
    "NOVResult",
    "PeriodComparison",
    "VarianceAnalysis",
    "amortize_setup_cost",
    "build_quarterly_digest",
    "compute_monthly_nov",
    "estimate_ai_token_cost",
    "estimate_infrastructure_cost",
    "estimate_integration_cost",
    "estimate_opportunity_cost",
    "estimate_people_cost",
    "estimate_revenue_ab_attribution",
    "estimate_revenue_industry_benchmark",
    "estimate_revenue_pre_post",
    "estimate_revenue_variance",
    "fetch_current_digest",
    "fetch_quarter_window",
    "fetch_trend",
    "monthly_run_rate",
    "quarter_bounds",
    "quarter_label",
    "time_to_payback_months",
    "upsert_monthly_digest",
]
