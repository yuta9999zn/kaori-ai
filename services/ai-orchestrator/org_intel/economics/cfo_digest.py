"""
NOV-RPT-020 — CFO quarterly digest.

Aggregates 3 monthly NOV digests into a CFO-style quarterly report:
  * Period totals (revenue, cost, NOV)
  * Cost breakdown (people / ai / infra / integration)
  * QoQ comparison (this quarter vs previous)
  * YoY comparison (this quarter vs same quarter last year)
  * Monthly run-rate + amortized setup allocation

Pure computation. Persistence I/O lives in persistence.py +
routers/economics.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from .persistence import MonthlyDigestRow


@dataclass(frozen=True)
class CostBreakdown:
    """Quarterly cost aggregation."""
    people_vnd:      Decimal
    ai_vnd:          Decimal
    infra_vnd:       Decimal
    integration_vnd: Decimal
    total_vnd:       Decimal


@dataclass(frozen=True)
class PeriodComparison:
    """One window vs another (QoQ or YoY).

    `relative_delta` is signed: positive = this period higher.
    `verdict` mirrors NOV-REV-006 bands:
      |relative| ≤ 5%  → flat
      ≤ 15%             → modest
      ≤ 30%             → significant
      > 30%             → major
    """
    this_period_vnd:  Decimal
    other_period_vnd: Decimal
    absolute_delta:   Decimal
    relative_delta:   Decimal     # signed
    verdict:          str


@dataclass(frozen=True)
class CFOQuarterlyDigest:
    """The CFO-facing payload for one quarter."""
    enterprise_id:    str
    quarter:          str            # 'YYYY-Qn' (e.g. '2026-Q1')
    quarter_start:    date
    quarter_end:      date
    month_count:      int            # 1-3 (incomplete quarters allowed)

    # Totals
    revenue_total_vnd: Decimal
    cost_total_vnd:    Decimal
    nov_total_vnd:     Decimal

    # Breakdowns
    cost_breakdown:    CostBreakdown
    monthly_run_rate_vnd: Decimal     # avg of the 3 months

    # Comparisons (None when no comparable window exists)
    qoq: Optional[PeriodComparison]
    yoy: Optional[PeriodComparison]

    # Setup amortization allocation (if any)
    amortized_setup_vnd: Decimal      # monthly amortization × month_count

    notes: list[str]                  # human-readable bullets for the CFO


def quarter_label(d: date) -> str:
    """date(2026, 5, 1) → '2026-Q2'."""
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def quarter_bounds(quarter: str) -> tuple[date, date]:
    """'2026-Q1' → (date(2026,1,1), date(2026,3,31))."""
    year_s, q_s = quarter.split("-Q")
    year, q = int(year_s), int(q_s)
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    last_day = 31 if end_month in (3, 12) else 30 if end_month in (6, 9) else 28
    return date(year, start_month, 1), date(year, end_month, last_day)


def _classify_delta(relative: Decimal) -> str:
    abs_rel = abs(relative)
    if abs_rel <= Decimal("0.05"):
        return "flat"
    if abs_rel <= Decimal("0.15"):
        return "modest"
    if abs_rel <= Decimal("0.30"):
        return "significant"
    return "major"


def _compare_periods(this_vnd: Decimal, other_vnd: Decimal) -> PeriodComparison:
    delta = this_vnd - other_vnd
    if other_vnd == 0:
        relative = Decimal("0") if delta == 0 else Decimal("1")
        return PeriodComparison(
            this_period_vnd=this_vnd, other_period_vnd=other_vnd,
            absolute_delta=delta, relative_delta=relative,
            verdict="flat" if delta == 0 else "major",
        )
    relative = (delta / other_vnd).quantize(Decimal("0.0001"))
    return PeriodComparison(
        this_period_vnd=this_vnd, other_period_vnd=other_vnd,
        absolute_delta=delta, relative_delta=relative,
        verdict=_classify_delta(relative),
    )


def build_quarterly_digest(
    *,
    enterprise_id: str,
    quarter: str,                                  # 'YYYY-Qn'
    monthly_rows: list[MonthlyDigestRow],
    prev_quarter_rows: Optional[list[MonthlyDigestRow]] = None,
    same_quarter_last_year_rows: Optional[list[MonthlyDigestRow]] = None,
    amortized_setup_monthly_vnd: Decimal = Decimal("0"),
) -> CFOQuarterlyDigest:
    """Build the CFO digest. Caller fetches the rows; this is pure."""
    q_start, q_end = quarter_bounds(quarter)

    # Filter just-in-case the caller passed extra months.
    rows = sorted(
        [r for r in monthly_rows if q_start <= r.month_start <= q_end],
        key=lambda r: r.month_start,
    )

    revenue_total = sum((r.revenue_vnd for r in rows), Decimal("0"))
    cost_total    = sum((r.cost_vnd    for r in rows), Decimal("0"))
    nov_total     = sum((r.nov_vnd     for r in rows), Decimal("0"))

    cb = CostBreakdown(
        people_vnd=sum((r.people_cost_vnd      for r in rows), Decimal("0")),
        ai_vnd=    sum((r.ai_cost_vnd          for r in rows), Decimal("0")),
        infra_vnd= sum((r.infra_cost_vnd       for r in rows), Decimal("0")),
        integration_vnd=sum((r.integration_cost_vnd for r in rows), Decimal("0")),
        total_vnd=cost_total,
    )

    run_rate = (
        (cost_total / Decimal(len(rows))).quantize(Decimal("0.0001"))
        if rows else Decimal("0")
    )

    # QoQ
    qoq = None
    if prev_quarter_rows:
        prev_cost = sum((r.cost_vnd for r in prev_quarter_rows), Decimal("0"))
        qoq = _compare_periods(cost_total, prev_cost)

    # YoY
    yoy = None
    if same_quarter_last_year_rows:
        yoy_cost = sum((r.cost_vnd for r in same_quarter_last_year_rows),
                        Decimal("0"))
        yoy = _compare_periods(cost_total, yoy_cost)

    amortized_total = (amortized_setup_monthly_vnd * Decimal(len(rows))).quantize(
        Decimal("0.0001"),
    )

    # Build human-readable notes the CFO can paste into a 1-pager
    notes: list[str] = []
    notes.append(f"Quý {quarter} có {len(rows)} tháng dữ liệu NOV.")
    if rows:
        notes.append(
            f"Tổng doanh thu attributable: {_vnd_fmt(revenue_total)}. "
            f"Tổng chi phí: {_vnd_fmt(cost_total)}. "
            f"NOV: {_vnd_fmt(nov_total)} "
            f"({'âm' if nov_total < 0 else 'dương'})."
        )
        notes.append(
            f"Chi phí trung bình theo tháng: {_vnd_fmt(run_rate)}/tháng."
        )
    if qoq:
        direction = "tăng" if qoq.relative_delta > 0 else "giảm" if qoq.relative_delta < 0 else "đi ngang"
        notes.append(
            f"Chi phí QoQ {direction} {abs(qoq.relative_delta * 100):.1f}% "
            f"so với quý trước (verdict: {qoq.verdict})."
        )
    if yoy:
        direction = "tăng" if yoy.relative_delta > 0 else "giảm" if yoy.relative_delta < 0 else "đi ngang"
        notes.append(
            f"Chi phí YoY {direction} {abs(yoy.relative_delta * 100):.1f}% "
            f"so với cùng kỳ năm trước (verdict: {yoy.verdict})."
        )
    if amortized_setup_monthly_vnd > 0:
        notes.append(
            f"Phân bổ chi phí setup: {_vnd_fmt(amortized_setup_monthly_vnd)}/tháng "
            f"(× {len(rows)} tháng = {_vnd_fmt(amortized_total)} trong quý)."
        )

    return CFOQuarterlyDigest(
        enterprise_id=enterprise_id, quarter=quarter,
        quarter_start=q_start, quarter_end=q_end,
        month_count=len(rows),
        revenue_total_vnd=revenue_total,
        cost_total_vnd=cost_total,
        nov_total_vnd=nov_total,
        cost_breakdown=cb,
        monthly_run_rate_vnd=run_rate,
        qoq=qoq, yoy=yoy,
        amortized_setup_vnd=amortized_total,
        notes=notes,
    )


def _vnd_fmt(amount: Decimal) -> str:
    """Vietnamese number format: '1.000.000₫'. CFO-friendly."""
    n = int(amount)
    s = f"{abs(n):,}".replace(",", ".")
    return ("-" if n < 0 else "") + s + "₫"
