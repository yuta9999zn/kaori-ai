"""Tests for kpi_engine.benchmark — pure interpolation logic.

The DB-bound `lookup_percentile` needs an asyncpg connection so we
skip end-to-end here; instead we test the pure helpers directly.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from reasoning.kpi_engine.benchmark import (
    _interpolate_percentile,
    _ordered_points,
    _to_decimal,
)


def _ordered(p25=None, p50=None, p75=None, p90=None) -> list:
    """Helper — fake a row dict."""
    row = {"p25": p25, "p50": p50, "p75": p75, "p90": p90}
    return _ordered_points(row)


def test_ordered_points_drops_nulls():
    pts = _ordered(p25=None, p50=Decimal("100"), p75=Decimal("200"), p90=None)
    assert len(pts) == 2
    assert pts == [(50, Decimal("100")), (75, Decimal("200"))]


def test_ordered_points_sorts_ascending_by_value():
    """When ALL 4 published, points should sort ascending by value."""
    pts = _ordered(
        p25=Decimal("1200000"),  # CAC distribution: lower P25 is "worse" rank,
        p50=Decimal("850000"),    # but the table just sorts by value here.
        p75=Decimal("600000"),
        p90=Decimal("400000"),
    )
    values = [v for _, v in pts]
    assert values == sorted(values), "must sort ascending by value"


def test_interpolate_clamp_low_to_first_percentile():
    """Value below the lowest published point → lowest percentile."""
    pts = [(25, Decimal("400000")), (50, Decimal("850000"))]
    pct = _interpolate_percentile(Decimal("100000"), pts)
    assert pct == 25.0


def test_interpolate_clamp_high_to_last_percentile():
    pts = [(25, Decimal("400000")), (50, Decimal("850000"))]
    pct = _interpolate_percentile(Decimal("2000000"), pts)
    assert pct == 50.0


def test_interpolate_exact_match_returns_known_percentile():
    pts = [(25, Decimal("400000")), (50, Decimal("850000")), (75, Decimal("1200000"))]
    assert _interpolate_percentile(Decimal("400000"), pts) == 25.0
    assert _interpolate_percentile(Decimal("850000"), pts) == 50.0
    assert _interpolate_percentile(Decimal("1200000"), pts) == 75.0


def test_interpolate_midway_between_published_points():
    """Halfway between P25 (400k) and P50 (800k) → P37.5."""
    pts = [(25, Decimal("400000")), (50, Decimal("800000"))]
    pct = _interpolate_percentile(Decimal("600000"), pts)
    assert pct == pytest.approx(37.5)


def test_interpolate_returns_none_with_one_point():
    """A single percentile point can't bracket → returns None."""
    pts = [(50, Decimal("500000"))]
    assert _interpolate_percentile(Decimal("400000"), pts) is None


def test_interpolate_returns_none_with_zero_points():
    assert _interpolate_percentile(Decimal("100000"), []) is None


def test_to_decimal_handles_int():
    assert _to_decimal(100) == Decimal("100")


def test_to_decimal_handles_float():
    # Decimal(str(0.1)) avoids float-binary surprises.
    assert _to_decimal(0.1) == Decimal("0.1")


def test_to_decimal_passthrough_decimal():
    d = Decimal("1.2345")
    assert _to_decimal(d) is d
