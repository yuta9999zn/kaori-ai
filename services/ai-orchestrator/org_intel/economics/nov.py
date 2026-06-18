"""
NOV core computation — NOV-CORE-013..018 (P1-S7).

Net Operational Value (NOV) = revenue - cost. Tracked monthly per
workflow + rolled up per department + per tenant.

Phase 1 ships:
  NOV-CORE-013  Monthly NOV computation
  NOV-CORE-014  Time-to-payback projection
  NOV-CORE-015  Cumulative NOV tracking (caller manages the sum)
  NOV-CORE-016  Negative NOV alerts (caller decides escalation)
  NOV-CORE-017  Per-department rollup (caller groups + sums)
  NOV-CORE-018  Per-tenant total NOV (caller groups + sums)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class NOVResult:
    """One month's NOV computation result.

    Use the .is_negative() helper for NOV-CORE-016 alert decisions.
    """
    revenue_vnd: Decimal
    cost_vnd: Decimal
    nov_vnd: Decimal
    revenue_method: str
    revenue_confidence: Decimal

    def is_negative(self) -> bool:
        """NOV-CORE-016 — is NOV negative this month?"""
        return self.nov_vnd < 0


def compute_monthly_nov(
    *,
    revenue_vnd: Decimal,
    cost_vnd: Decimal,
    revenue_method: str = "pre_post",
    revenue_confidence: Decimal = Decimal("0.7"),
) -> NOVResult:
    """NOV-CORE-013 — monthly NOV = revenue - cost.

    Both inputs are pre-summed by caller (revenue from one of
    estimate_revenue_*; cost as sum of all 4 cost components).
    Decimal arithmetic — no float (K-9).
    """
    nov = revenue_vnd - cost_vnd
    return NOVResult(
        revenue_vnd=revenue_vnd.quantize(Decimal("0.0001")),
        cost_vnd=cost_vnd.quantize(Decimal("0.0001")),
        nov_vnd=nov.quantize(Decimal("0.0001")),
        revenue_method=revenue_method,
        revenue_confidence=revenue_confidence,
    )


def time_to_payback_months(
    *,
    upfront_cost_vnd: Decimal,
    monthly_net_savings_vnd: Decimal,
) -> int | None:
    """NOV-CORE-014 — months until cumulative NOV breaks even on
    upfront cost (one-time integration cost, training cost, etc.).

    Returns None when monthly savings ≤ 0 (workflow won't pay back at
    current rate — caller surfaces as 'never').
    """
    if monthly_net_savings_vnd <= 0:
        return None
    if upfront_cost_vnd <= 0:
        return 0
    months = upfront_cost_vnd / monthly_net_savings_vnd
    # Round up — partial month means breakeven happens during that month.
    # Decimal // doesn't floor toward -inf reliably across versions, so
    # use explicit "remainder?" check.
    whole = int(months)
    if months > Decimal(whole):
        return whole + 1
    return whole
