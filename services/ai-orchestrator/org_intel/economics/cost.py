"""
NOV cost calculators — 6 components Phase 1.5.

  NOV-CST-007  People cost (time saved × hourly rate)            P1-S7
  NOV-CST-008  Infrastructure cost (per-tenant compute + storage) P1-S7
  NOV-CST-009  AI call cost (token-based)                         P1-S7
  NOV-CST-010  Integration cost (3rd-party API calls)             P1-S7
  NOV-CST-012  Setup cost amortization over N months              P15-S11
  + monthly_run_rate helper for the CFO quarterly digest

All money returned as Decimal in VND (K-9). Never float.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def estimate_people_cost(
    *,
    hours_required: Decimal,
    hourly_rate_vnd: Decimal,
) -> Decimal:
    """NOV-CST-007 — time × rate.

    Used for both:
      * Cost SAVED by automation (positive = savings = lower cost)
      * Cost ADDED by manual oversight (manager intervention time)

    Caller decides the sign by passing positive or negative hours.
    """
    if hours_required < 0:
        return Decimal("0")
    return (hours_required * hourly_rate_vnd).quantize(Decimal("0.0001"))


def estimate_ai_token_cost(
    *,
    tokens_input: int,
    tokens_output: int,
    cost_per_1k_input_vnd: Decimal,
    cost_per_1k_output_vnd: Decimal,
) -> Decimal:
    """NOV-CST-009 — vendor token cost in VND.

    Vendor APIs price per 1K tokens. Phase 1 char-count-as-token-proxy
    is recorded in OBS-008 metrics; Phase 1.5+ swaps to provider-side
    billing API for accurate token counts.
    """
    in_cost = (Decimal(tokens_input) / Decimal("1000")) * cost_per_1k_input_vnd
    out_cost = (Decimal(tokens_output) / Decimal("1000")) * cost_per_1k_output_vnd
    return (in_cost + out_cost).quantize(Decimal("0.0001"))


def estimate_infrastructure_cost(
    *,
    compute_hours: Decimal,
    storage_gb_month: Decimal,
    cost_per_compute_hour_vnd: Decimal = Decimal("100"),
    cost_per_gb_month_vnd: Decimal = Decimal("1000"),
) -> Decimal:
    """NOV-CST-008 — per-tenant compute + storage allocation.

    Phase 1 defaults are placeholders; Phase 1.5+ pulls real per-tenant
    metering from Kubernetes resource accounting.
    """
    compute = compute_hours * cost_per_compute_hour_vnd
    storage = storage_gb_month * cost_per_gb_month_vnd
    return (compute + storage).quantize(Decimal("0.0001"))


def estimate_integration_cost(
    *,
    api_calls: int,
    cost_per_call_vnd: Decimal,
) -> Decimal:
    """NOV-CST-010 — 3rd-party API charges (SendGrid emails, Twilio SMS,
    Stripe charges, Zalo OA quotas, etc.).

    Caller batches per provider and sums externally. This helper just
    multiplies — keeps the unit conversion explicit at the call site
    so a future audit can grep "estimate_integration_cost" and find
    every cost source.
    """
    if api_calls <= 0:
        return Decimal("0")
    return (Decimal(api_calls) * cost_per_call_vnd).quantize(Decimal("0.0001"))


# ─── NOV-CST-012 — Setup cost amortization ─────────────────────────


@dataclass(frozen=True)
class AmortizedCost:
    """One-time setup cost amortized over `term_months` for CFO reporting.

    For accounting purposes the setup expense lands in month 1; for NOV
    "monthly cost" we want it spread out so a single setup spike doesn't
    crush a month's NOV calculation. Straight-line amortization is the
    simplest defensible method; non-linear methods (DDB, sum-of-years)
    are Phase 2.
    """
    total_setup_vnd:        Decimal
    term_months:            int
    monthly_amortized_vnd:  Decimal
    months_elapsed:         int
    months_remaining:       int
    cumulative_amortized_vnd: Decimal
    remaining_to_amortize_vnd: Decimal
    fully_amortized:        bool


def amortize_setup_cost(
    *,
    total_setup_vnd: Decimal,
    term_months: int = 12,
    months_elapsed: int = 1,
) -> AmortizedCost:
    """NOV-CST-012 — straight-line amortization of one-time setup cost.

    Args:
      total_setup_vnd:  one-time spend (onboarding, training, custom
                         integrations) — paid in month 0
      term_months:      amortization window. 12 default = "absorb over
                         year 1". Caller can set 24/36 for longer
                         contracts.
      months_elapsed:   how many full months have passed since setup.
                         month_elapsed=1 means the FIRST monthly
                         allocation lands (i.e. report period is the
                         end of month 1).

    Returns AmortizedCost with monthly allocation + cumulative + remaining.
    NOV monthly cost subtracts `monthly_amortized_vnd` (not the lump sum).
    """
    if total_setup_vnd < 0:
        raise ValueError(f"total_setup_vnd must be ≥ 0; got {total_setup_vnd}")
    if term_months <= 0:
        raise ValueError(f"term_months must be > 0; got {term_months}")
    if months_elapsed < 0:
        raise ValueError(f"months_elapsed must be ≥ 0; got {months_elapsed}")

    # Quantize to 4dp (VND has no fractional unit but we keep precision
    # for sum-up roll-up math).
    monthly = (total_setup_vnd / Decimal(term_months)).quantize(Decimal("0.0001"))

    capped_elapsed = min(months_elapsed, term_months)
    cumulative = (monthly * Decimal(capped_elapsed)).quantize(Decimal("0.0001"))
    remaining = (total_setup_vnd - cumulative).quantize(Decimal("0.0001"))
    if remaining < 0:
        remaining = Decimal("0")

    return AmortizedCost(
        total_setup_vnd=total_setup_vnd.quantize(Decimal("0.0001")),
        term_months=term_months,
        monthly_amortized_vnd=monthly,
        months_elapsed=months_elapsed,
        months_remaining=max(0, term_months - months_elapsed),
        cumulative_amortized_vnd=cumulative,
        remaining_to_amortize_vnd=remaining,
        fully_amortized=months_elapsed >= term_months,
    )


def monthly_run_rate(
    *,
    monthly_total_costs: list[Decimal],
) -> Decimal:
    """Compute the simple monthly run-rate (mean monthly cost) for the
    CFO quarterly digest (NOV-RPT-020). Empty list → 0."""
    if not monthly_total_costs:
        return Decimal("0")
    total = sum(monthly_total_costs, Decimal("0"))
    return (total / Decimal(len(monthly_total_costs))).quantize(Decimal("0.0001"))


# ─── NOV-CST-011 — Opportunity cost modeling (P2-S22 ship 2026-05-17) ─


@dataclass(frozen=True)
class OpportunityCost:
    """Difference between the chosen path's cost+value vs. the best
    alternative path's cost+value, expressed in VND.

    Sign convention: positive opportunity_cost_vnd means the chosen
    path is COSTLIER in net (we lost value vs. alt). Negative means
    chosen path was actually a win (rare — usually means baseline was
    wrong)."""
    chosen_total_cost_vnd:      Decimal
    chosen_realized_value_vnd:  Decimal
    alt_total_cost_vnd:         Decimal
    alt_projected_value_vnd:    Decimal
    opportunity_cost_vnd:       Decimal
    confidence:                 Decimal   # 0..1
    method:                     str       # historical_baseline | industry_benchmark | manual_estimate


def estimate_opportunity_cost(
    *,
    chosen_total_cost_vnd: Decimal,
    chosen_realized_value_vnd: Decimal,
    alt_total_cost_vnd: Decimal,
    alt_projected_value_vnd: Decimal,
    confidence: Decimal = Decimal("0.7"),
    method: str = "manual_estimate",
) -> OpportunityCost:
    """NOV-CST-011 — opportunity cost of chosen path vs. alt.

    opportunity_cost = alt_net - chosen_net
        where net = (realized_or_projected_value - total_cost).

    Positive → alt would have been better → opportunity cost paid.
    Negative → chosen was the right call.

    Confidence guards over-claiming on speculative alternatives.
    """
    if not (Decimal("0") <= confidence <= Decimal("1")):
        raise ValueError("confidence must be in [0, 1]")
    if method not in ("historical_baseline", "industry_benchmark", "manual_estimate"):
        raise ValueError(f"unsupported method {method!r}")

    chosen_net = chosen_realized_value_vnd - chosen_total_cost_vnd
    alt_net    = alt_projected_value_vnd - alt_total_cost_vnd
    opp_cost   = (alt_net - chosen_net).quantize(Decimal("0.0001"))

    return OpportunityCost(
        chosen_total_cost_vnd=chosen_total_cost_vnd.quantize(Decimal("0.0001")),
        chosen_realized_value_vnd=chosen_realized_value_vnd.quantize(Decimal("0.0001")),
        alt_total_cost_vnd=alt_total_cost_vnd.quantize(Decimal("0.0001")),
        alt_projected_value_vnd=alt_projected_value_vnd.quantize(Decimal("0.0001")),
        opportunity_cost_vnd=opp_cost,
        confidence=confidence,
        method=method,
    )
