"""
F-032 — Gold layer aggregator.

Reads strictly canonical Silver fields (per docs/specs/MEDALLION_CONTRACT.md):
  - ``customer_external_id``  — unique customer key (K-11 billing unit too)
  - ``date``                  — purchase / interaction timestamp
  - ``revenue`` OR ``amount`` — monetary value (revenue takes precedence)

Computes ``revenue_at_risk`` per customer using a deliberately simple
heuristic so the maths is auditable and the metric is testable:

    if (today - last_purchase_at) <= 90 days  →  revenue_at_risk = 0
    else                                      →  revenue_at_risk =
        min(avg_purchase_value, sum(purchases in last 12 months))

The `min()` cap prevents a long-dormant customer with one ancient
high-value transaction from inflating the at-risk number — Phase 1
ships an honest, if conservative, rollup. Phase 2 F-024 / F-060 will
replace this with a churn-ML model + the `is_actioned` workflow.

Layer separation (per the medallion-separation memory): this module
NEVER falls back to a non-canonical column. If a tenant's silver rows
don't expose ``customer_external_id``, the aggregator logs and skips
that tenant. Fixing the source is Silver / column-mapper work, not
Gold's.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

import structlog

from ...shared.db import acquire_for_tenant

log = structlog.get_logger()

# 90-day churn cutoff per CLAUDE.md North Star prose; keep wired here so
# the service test pins the boundary. Long-term this should move into a
# tenant_settings column for per-tenant tuning (Phase 2).
CHURN_DAYS_DEFAULT = 90

# 12-month look-back ceiling on revenue_at_risk — see docstring.
REVENUE_CEILING_DAYS = 365


@dataclass
class AggregateResult:
    enterprise_id:           UUID
    customers_processed:     int
    customers_skipped:       int          # rows missing canonical fields
    at_risk_customer_count:  int
    total_revenue_at_risk:   Decimal
    skipped_reason:          Optional[str] = None  # None on success


async def aggregate_for_tenant(
    enterprise_id: str | UUID,
    *,
    today: Optional[datetime] = None,
    churn_days: int = CHURN_DAYS_DEFAULT,
) -> AggregateResult:
    """Run the Gold aggregator for one tenant.

    Idempotent: re-running on the same data produces the same rows
    (gold_features upsert keyed on (enterprise_id, customer_external_id);
    gold_aggregates upsert keyed on (enterprise_id, metric_key)).

    Returns an :class:`AggregateResult` summary the consumer logs +
    exposes via structured telemetry.
    """
    eid_uuid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))
    today = today or datetime.now(timezone.utc)
    churn_cutoff   = today - timedelta(days=churn_days)
    ceiling_cutoff = today - timedelta(days=REVENUE_CEILING_DAYS)

    rows = await _load_silver(eid_uuid)
    if not rows:
        log.info("gold.aggregate.skip.no_silver", enterprise_id=str(eid_uuid))
        return AggregateResult(eid_uuid, 0, 0, 0, Decimal("0"), "no_silver_rows")

    by_customer, skipped = _group_by_customer(rows)
    if not by_customer:
        log.warning("gold.aggregate.skip.no_customer_id",
                    enterprise_id=str(eid_uuid),
                    silver_rows=len(rows),
                    skipped=skipped)
        return AggregateResult(eid_uuid, 0, skipped, 0, Decimal("0"),
                                "no_customer_external_id")

    features = []
    total_at_risk = Decimal("0")
    at_risk_count = 0
    for cust_id, purchases in by_customer.items():
        f = _compute_customer_features(
            cust_id, purchases,
            today=today, churn_cutoff=churn_cutoff, ceiling_cutoff=ceiling_cutoff,
        )
        features.append(f)
        if f["revenue_at_risk"] > 0:
            at_risk_count += 1
            total_at_risk += f["revenue_at_risk"]

    await _upsert_features(eid_uuid, features, computed_at=today)
    await _upsert_aggregates(eid_uuid,
                              total_at_risk=total_at_risk,
                              at_risk_count=at_risk_count,
                              computed_at=today)

    log.info("gold.aggregate.done",
             enterprise_id=str(eid_uuid),
             customers_processed=len(features),
             customers_skipped=skipped,
             at_risk_count=at_risk_count,
             total_revenue_at_risk=str(total_at_risk))

    return AggregateResult(eid_uuid, len(features), skipped,
                            at_risk_count, total_at_risk)


# =========================================================================
# Step 1 — load silver rows
# =========================================================================

async def _load_silver(enterprise_id: UUID) -> list[dict]:
    """Pull every silver row for the tenant.

    Phase 1 reads the whole tenant — fine because pilot tenants are small
    (low thousands of rows). Phase 2 should switch to incremental reads
    keyed off the silver.complete event's run_id once the volume justifies
    the complexity.
    """
    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT row_data FROM silver_rows WHERE enterprise_id = $1",
            enterprise_id,
        )
    # asyncpg returns JSONB as a str unless a codec is registered — parse so the
    # canonical-field checks see a dict, not a string (else every row is skipped
    # as "not a dict" → 0 features, masquerading as no_customer_external_id).
    out: list[dict] = []
    for r in rows:
        rd = r["row_data"]
        if isinstance(rd, str):
            try:
                rd = json.loads(rd)
            except (ValueError, TypeError):
                continue
        if isinstance(rd, dict):
            out.append(rd)
    return out


# =========================================================================
# Step 2 — group rows by customer (strict canonical, no fallback)
# =========================================================================

def _group_by_customer(rows: list[dict]) -> tuple[dict[str, list[dict]], int]:
    """Group rows by ``customer_external_id``.

    Rows that lack the canonical key are dropped + counted in the returned
    ``skipped`` value — Gold does NOT try fallback names. Fixing the source
    is Silver's job (per docs/specs/MEDALLION_CONTRACT.md)."""
    by_customer: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    for r in rows:
        if not isinstance(r, dict):
            skipped += 1
            continue
        cust = r.get("customer_external_id")
        if cust is None or str(cust).strip() == "":
            skipped += 1
            continue
        by_customer[str(cust).strip()].append(r)
    return by_customer, skipped


# =========================================================================
# Step 3 — per-customer feature computation
# =========================================================================

def _compute_customer_features(
    customer_id: str,
    purchases: list[dict],
    *,
    today: datetime,
    churn_cutoff: datetime,
    ceiling_cutoff: datetime,
) -> dict:
    """Compute the feature row for one customer.

    Pure function — given the same purchases + today, the output is
    bit-identical. Tested in test_gold_aggregator.py.
    """
    parsed = []
    for p in purchases:
        ts = _parse_date(p.get("date"))
        amt = _parse_amount(p.get("revenue") if p.get("revenue") is not None else p.get("amount"))
        parsed.append((ts, amt))

    valid_amounts = [a for _, a in parsed if a is not None]
    valid_dates   = [t for t, _ in parsed if t is not None]

    last_purchase_at = max(valid_dates) if valid_dates else None
    purchase_count   = len(valid_amounts)
    total_purchases  = sum(valid_amounts) if valid_amounts else Decimal("0")
    avg_purchase_value = (
        (total_purchases / purchase_count) if purchase_count else Decimal("0")
    )

    # 12-month look-back sum — drives the cap on revenue_at_risk so a
    # single ancient high-value purchase can't dominate the rollup.
    recent_total = sum(
        (a for t, a in parsed if t is not None and a is not None and t >= ceiling_cutoff),
        Decimal("0"),
    )

    # Active vs at-risk classifier
    is_active = last_purchase_at is not None and last_purchase_at >= churn_cutoff
    if is_active or avg_purchase_value <= 0 or recent_total <= 0:
        revenue_at_risk = Decimal("0")
    else:
        revenue_at_risk = min(avg_purchase_value, recent_total)

    return {
        "customer_external_id": customer_id,
        "revenue_at_risk":      _q4(revenue_at_risk),
        "last_purchase_at":     last_purchase_at,
        "total_purchases":      _q4(total_purchases),
        "purchase_count":       purchase_count,
        "avg_purchase_value":   _q4(avg_purchase_value) if purchase_count else None,
    }


# =========================================================================
# Step 4 — upsert into gold_features + gold_aggregates
# =========================================================================

_UPSERT_FEATURE_SQL = """
    INSERT INTO gold_features
        (enterprise_id, customer_external_id, revenue_at_risk,
         last_purchase_at, total_purchases, purchase_count,
         avg_purchase_value, computed_at)
    VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (enterprise_id, customer_external_id) DO UPDATE SET
        revenue_at_risk    = EXCLUDED.revenue_at_risk,
        last_purchase_at   = EXCLUDED.last_purchase_at,
        total_purchases    = EXCLUDED.total_purchases,
        purchase_count     = EXCLUDED.purchase_count,
        avg_purchase_value = EXCLUDED.avg_purchase_value,
        computed_at        = EXCLUDED.computed_at
        -- intentionally NOT updating is_actioned / actioned_at — those
        -- are owned by the Phase 2 F-060 user-facing flow.
"""

_UPSERT_AGGREGATE_SQL = """
    INSERT INTO gold_aggregates (enterprise_id, metric_key, metric_value, computed_at)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (enterprise_id, metric_key) DO UPDATE SET
        metric_value = EXCLUDED.metric_value,
        computed_at  = EXCLUDED.computed_at
"""


async def _upsert_features(enterprise_id: UUID, features: list[dict],
                            *, computed_at: datetime) -> None:
    if not features:
        return
    async with acquire_for_tenant(enterprise_id) as conn:
        for f in features:
            await conn.execute(
                _UPSERT_FEATURE_SQL,
                enterprise_id,
                f["customer_external_id"],
                f["revenue_at_risk"],
                f["last_purchase_at"],
                f["total_purchases"],
                f["purchase_count"],
                f["avg_purchase_value"],
                computed_at,
            )


async def _upsert_aggregates(enterprise_id: UUID,
                              *, total_at_risk: Decimal,
                              at_risk_count: int,
                              computed_at: datetime) -> None:
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(_UPSERT_AGGREGATE_SQL,
                           enterprise_id, "total_revenue_at_risk",
                           _q4(total_at_risk), computed_at)
        await conn.execute(_UPSERT_AGGREGATE_SQL,
                           enterprise_id, "at_risk_customer_count",
                           Decimal(at_risk_count), computed_at)


# =========================================================================
# Tiny parsing helpers
# =========================================================================

def _parse_date(v) -> Optional[datetime]:
    """Parse a date / datetime out of a JSONB value. Returns None on failure
    (cleaning is Silver's job; Gold tolerates dirty inputs by ignoring them)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # Try ISO-8601 first (Silver's canonical date shape after rule_catalog).
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        # Try date-only (YYYY-MM-DD) — Silver standardise_date rule output.
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _parse_amount(v) -> Optional[Decimal]:
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        try:
            d = Decimal(str(v))
        except InvalidOperation:
            return None
        return d if d >= 0 else None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s:
            return None
        try:
            d = Decimal(s)
        except InvalidOperation:
            return None
        return d if d >= 0 else None
    return None


def _q4(d: Decimal) -> Decimal:
    """Quantise to NUMERIC(14,4) precision per K-9."""
    return d.quantize(Decimal("0.0001"))
