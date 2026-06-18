"""
Industry benchmark percentile lookup — reads industry_benchmarks table.

Given a (industry, kpi_code, region, period_year, raw_value), returns
the percentile rank of raw_value within the P25/P50/P75/P90 distribution
published by the source.

This is what powers "your CAC is at P40 of Vietnamese retail SMEs
(median 850K VND)" tooltips on the dashboard. The percentile is
interpolated linearly between known points; outside the [P25, P90]
window the function returns the band's outer percentile (capped).

NULL handling: when a benchmark row exists but partial percentiles are
missing (some sources publish only P50), the function uses whatever
ordered values are available and returns None for percentile when
fewer than 2 points exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Union

import asyncpg


@dataclass(frozen=True)
class BenchmarkLookup:
    """Result of a benchmark lookup. None percentile means the
    underlying benchmark row had insufficient data to interpolate."""

    industry: str
    kpi_code: str
    region: str
    period_year: int
    percentile: Optional[float]      # 0-100 or None
    p50_value: Optional[Decimal]     # median for tooltip "median = X"
    source: str                       # citation text
    sample_size: Optional[int]


_BENCHMARK_LOOKUP_SQL = """
SELECT
    industry, kpi_code, region, period_year,
    p25, p50, p75, p90,
    sample_size, source, source_url
FROM industry_benchmarks
WHERE industry    = $1
  AND kpi_code    = $2
  AND region      = $3
  AND period_year = $4
  AND is_active   = TRUE
"""


_BENCHMARK_LATEST_SQL = """
SELECT
    industry, kpi_code, region, period_year,
    p25, p50, p75, p90,
    sample_size, source, source_url
FROM industry_benchmarks
WHERE industry  = $1
  AND kpi_code  = $2
  AND region    = $3
  AND is_active = TRUE
ORDER BY period_year DESC
LIMIT 1
"""


async def lookup_percentile(
    conn: asyncpg.Connection,
    *,
    industry: str,
    kpi_code: str,
    raw_value: Union[Decimal, float, int],
    region: str = "VN",
    period_year: Optional[int] = None,
    higher_is_better: bool = True,
) -> Optional[BenchmarkLookup]:
    """Look up the percentile rank of `raw_value` for this benchmark.

    Args:
        conn: open asyncpg connection (benchmarks have no RLS — global ref).
        industry: 'retail' | 'ecommerce' | 'b2b_service' | ...
        kpi_code: matches kpi_definitions.kpi_code.
        raw_value: the value to rank against the distribution.
        region: 'VN' | 'APAC' | 'GLOBAL' (default 'VN').
        period_year: specific year, or None to use the latest available.
        higher_is_better: when True (CAC: lower_better → False, LTV:
            higher_better → True), the percentile reflects "your rank
            among peers" not "your value's percentile". A high value
            with higher_is_better=True gives a high percentile (good);
            same high value with higher_is_better=False (lower_better)
            gives a low percentile (bad).

    Returns:
        BenchmarkLookup, or None if no benchmark row exists for the
        combination.
    """
    if period_year is not None:
        row = await conn.fetchrow(
            _BENCHMARK_LOOKUP_SQL, industry, kpi_code, region, period_year
        )
    else:
        row = await conn.fetchrow(_BENCHMARK_LATEST_SQL, industry, kpi_code, region)
    if row is None:
        return None

    points = _ordered_points(row)
    value = _to_decimal(raw_value)
    pct = _interpolate_percentile(value, points)

    # Invert when lower-is-better: a low CAC value should show high
    # percentile (good rank), not low.
    if pct is not None and not higher_is_better:
        pct = 100.0 - pct

    return BenchmarkLookup(
        industry=row["industry"],
        kpi_code=row["kpi_code"],
        region=row["region"],
        period_year=int(row["period_year"]),
        percentile=pct,
        p50_value=row["p50"],
        source=row["source"],
        sample_size=row["sample_size"],
    )


def _ordered_points(row) -> list[tuple[int, Decimal]]:
    """Return non-NULL percentile points in ascending order of value
    if higher_better, else as published (caller flips later)."""
    pts: list[tuple[int, Decimal]] = []
    for pct_label, val in [(25, row["p25"]), (50, row["p50"]),
                            (75, row["p75"]), (90, row["p90"])]:
        if val is not None:
            pts.append((pct_label, val))
    # Ascending by published value so interpolation works regardless of
    # whether the distribution is increasing (higher_better KPIs) or
    # decreasing (lower_better KPIs).
    pts.sort(key=lambda pv: pv[1])
    return pts


def _interpolate_percentile(
    value: Decimal, points: list[tuple[int, Decimal]]
) -> Optional[float]:
    """Linear interpolation between known percentile points.

    Outside [first, last] window we clamp to the boundary percentile.
    Inside: linear between adjacent published points.
    Fewer than 2 points → None (can't interpolate).
    """
    if len(points) < 2:
        return None
    if value <= points[0][1]:
        return float(points[0][0])
    if value >= points[-1][1]:
        return float(points[-1][0])
    for i in range(len(points) - 1):
        lo_pct, lo_val = points[i]
        hi_pct, hi_val = points[i + 1]
        if lo_val <= value <= hi_val:
            if hi_val == lo_val:
                return float(lo_pct)
            frac = (value - lo_val) / (hi_val - lo_val)
            return float(lo_pct) + float(frac) * (hi_pct - lo_pct)
    return None  # unreachable given the clamping above; safety net.


def _to_decimal(v: Union[Decimal, float, int]) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))
