"""
KPI value classifier — Good / Warning / Critical against thresholds.

Pure function over (KPIDefinition, raw_value). No I/O, no DB. Belongs
in its own module so test-driving the classification logic is trivial
and the rules are visible at one place.

Classification rules:
- direction='higher_better':
    value >= threshold_good       → 'good'
    value >= threshold_warning    → 'warning'
    value <  threshold_warning    → 'critical'
- direction='lower_better':
    value <= threshold_good       → 'good'
    value <= threshold_warning    → 'warning'
    value >  threshold_warning    → 'critical'
- direction='target_midpoint':
    |value - target_value| / target_value <= 0.20 → 'good'  (within ±20%)
    |value - target_value| / target_value <= 0.50 → 'warning' (±50%)
    else → 'critical'
- When either threshold is NULL (or for the target_midpoint without
  target_value) → 'no_threshold' (caller may still render the value
  but should not claim a verdict).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Union

from .definitions import KPIDefinition

_TARGET_MIDPOINT_GOOD_BAND = Decimal("0.20")
_TARGET_MIDPOINT_WARNING_BAND = Decimal("0.50")


def classify_value(
    kpi_def: KPIDefinition,
    raw_value: Union[Decimal, float, int, None],
) -> str:
    """Return one of 'good' | 'warning' | 'critical' | 'no_threshold'.

    Raises ValueError if KPIDefinition.direction is unknown — that
    would be a seed-data error, not a runtime input error.
    """
    if raw_value is None:
        return "no_threshold"

    value = _to_decimal(raw_value)
    direction = kpi_def.direction

    if direction == "higher_better":
        if kpi_def.threshold_good is None or kpi_def.threshold_warning is None:
            return "no_threshold"
        if value >= kpi_def.threshold_good:
            return "good"
        if value >= kpi_def.threshold_warning:
            return "warning"
        return "critical"

    if direction == "lower_better":
        if kpi_def.threshold_good is None or kpi_def.threshold_warning is None:
            return "no_threshold"
        if value <= kpi_def.threshold_good:
            return "good"
        if value <= kpi_def.threshold_warning:
            return "warning"
        return "critical"

    if direction == "target_midpoint":
        if kpi_def.target_value is None or kpi_def.target_value == 0:
            return "no_threshold"
        deviation = abs(value - kpi_def.target_value) / kpi_def.target_value
        if deviation <= _TARGET_MIDPOINT_GOOD_BAND:
            return "good"
        if deviation <= _TARGET_MIDPOINT_WARNING_BAND:
            return "warning"
        return "critical"

    raise ValueError(
        f"Unknown KPI direction {direction!r} for kpi_code={kpi_def.kpi_code!r}. "
        "Seed data error — expected higher_better | lower_better | target_midpoint."
    )


def _to_decimal(value: Union[Decimal, float, int]) -> Decimal:
    """Coerce to Decimal preserving precision when possible."""
    if isinstance(value, Decimal):
        return value
    # str() round-trip avoids float-binary noise for nice round numbers
    return Decimal(str(value))
