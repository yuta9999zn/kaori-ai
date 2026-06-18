"""F-032 — Gold layer (per-customer features + per-tenant rollups)."""

from .aggregator import (
    AggregateResult,
    CHURN_DAYS_DEFAULT,
    aggregate_for_tenant,
)

__all__ = [
    "AggregateResult",
    "CHURN_DAYS_DEFAULT",
    "aggregate_for_tenant",
]
