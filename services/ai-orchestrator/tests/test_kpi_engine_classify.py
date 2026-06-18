"""Tests for kpi_engine.classify — P15-S11 Tuần 7 SQL-first backbone."""
from __future__ import annotations

from decimal import Decimal

import pytest

from reasoning.kpi_engine import classify_value
from reasoning.kpi_engine.definitions import KPIDefinition


def _def(direction: str, good: float, warning: float,
         target: float | None = None) -> KPIDefinition:
    """Minimal KPIDefinition for testing classify only."""
    return KPIDefinition(
        kpi_id="test-id",
        kpi_code="test_kpi",
        dept_type="marketing",
        display_name_vi="Test",
        display_name_en="Test",
        description_vi=None,
        formula_sql="",
        target_gold_view="gold.test",
        unit="pct",
        decimal_places=2,
        direction=direction,
        target_value=Decimal(str(target)) if target is not None else None,
        threshold_good=Decimal(str(good)) if good is not None else None,
        threshold_warning=Decimal(str(warning)) if warning is not None else None,
        threshold_source=None,
        is_active=True,
    )


def test_higher_better_good_at_threshold():
    d = _def("higher_better", good=3.0, warning=1.5)
    assert classify_value(d, 3.0) == "good"
    assert classify_value(d, 5.0) == "good"


def test_higher_better_warning_band():
    d = _def("higher_better", good=3.0, warning=1.5)
    assert classify_value(d, 1.5) == "warning"
    assert classify_value(d, 2.5) == "warning"


def test_higher_better_critical_below_warning():
    d = _def("higher_better", good=3.0, warning=1.5)
    assert classify_value(d, 1.0) == "critical"
    assert classify_value(d, 0.5) == "critical"


def test_lower_better_good_at_threshold():
    d = _def("lower_better", good=500_000, warning=1_000_000)
    assert classify_value(d, 500_000) == "good"
    assert classify_value(d, 300_000) == "good"


def test_lower_better_warning_band():
    d = _def("lower_better", good=500_000, warning=1_000_000)
    assert classify_value(d, 1_000_000) == "warning"
    assert classify_value(d, 800_000) == "warning"


def test_lower_better_critical():
    d = _def("lower_better", good=500_000, warning=1_000_000)
    assert classify_value(d, 1_500_000) == "critical"


def test_none_value_returns_no_threshold():
    d = _def("higher_better", good=3.0, warning=1.5)
    assert classify_value(d, None) == "no_threshold"


def test_missing_threshold_returns_no_threshold():
    """A KPI without both thresholds populated should not classify."""
    d = _def("higher_better", good=None, warning=1.5)  # type: ignore[arg-type]
    assert classify_value(d, 2.0) == "no_threshold"


def test_target_midpoint_inside_20pct_band_is_good():
    """Working capital ratio target=2.0, ±20% = [1.6, 2.4]."""
    d = _def("target_midpoint", good=None, warning=None, target=2.0)  # type: ignore[arg-type]
    assert classify_value(d, 2.0) == "good"     # exact
    assert classify_value(d, 1.6) == "good"     # lower edge of band
    assert classify_value(d, 2.4) == "good"     # upper edge


def test_target_midpoint_warning_band_20_to_50pct():
    d = _def("target_midpoint", good=None, warning=None, target=2.0)  # type: ignore[arg-type]
    assert classify_value(d, 1.5) == "warning"  # 25% below
    assert classify_value(d, 2.8) == "warning"  # 40% above
    assert classify_value(d, 1.0) == "warning"  # 50% below


def test_target_midpoint_critical_outside_50pct():
    d = _def("target_midpoint", good=None, warning=None, target=2.0)  # type: ignore[arg-type]
    assert classify_value(d, 0.5) == "critical"  # 75% below
    assert classify_value(d, 3.5) == "critical"  # 75% above


def test_target_midpoint_no_target_returns_no_threshold():
    d = _def("target_midpoint", good=None, warning=None, target=None)  # type: ignore[arg-type]
    assert classify_value(d, 2.0) == "no_threshold"


def test_unknown_direction_raises():
    d = _def("invalid_dir", good=1.0, warning=0.5)
    with pytest.raises(ValueError, match="Unknown KPI direction"):
        classify_value(d, 1.0)


def test_decimal_input_preserved():
    """Decimal input should compare exactly, not float-coerced."""
    d = _def("higher_better", good=3.0, warning=1.5)
    assert classify_value(d, Decimal("3.0")) == "good"
    assert classify_value(d, Decimal("1.4999")) == "critical"


def test_int_input_coerced():
    d = _def("higher_better", good=3.0, warning=1.5)
    assert classify_value(d, 5) == "good"
    assert classify_value(d, 1) == "critical"
