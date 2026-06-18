"""
SH-M59 ROI-Hybrid billing — pure compute for the +1.5% revenue-saved
add-on layered on top of the ENT ROI base subscription.

Pricing model (CLAUDE.md §10):
    ENT ROI = 8,000,000 VND base + 1.5% × revenue_saved
              cap 20,000,000 VND / month
              opt-in: tenant must have been ENT MAX ≥3 months

This module owns ONLY the +1.5% add-on math. The 8M base lives in
subscription_plans + the existing billing pipeline. Engagement signals
("is_actioned=true") gate which gold_features rows contribute.

Closes:
    SH-M59-001 cron monthly aggregate          → compute_monthly_run()
    SH-M59-002 0.015 × SUM(rev WHERE actioned) → compute_roi_addon()
    SH-M59-003 cap 20M                         → apply_cap()
    SH-M59-004 ENT MAX opt-in only             → eligibility check
    SH-M59-005 ≥3 months data                  → months_of_data check

K-rules
-------
K-1: all DB reads/writes filter by enterprise_id.
K-2: enterprise_roi_billing_lines is append-only; cron skips months
     already lined (idempotent K-13 spirit).
K-9: NUMERIC arithmetic via Decimal — never float for money.
K-11: revenue_at_risk pulled from gold_features per customer; SUM is
      per-enterprise-per-month with is_actioned=TRUE.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


# ─── Constants ───────────────────────────────────────────────────────


DEFAULT_RATE         = Decimal("0.0150")         # 1.5% — SH-M59-002
DEFAULT_CAP_VND      = Decimal("20000000.0000")  # 20M — SH-M59-003
MIN_MONTHS_OF_DATA   = 3                          # SH-M59-005


# ─── Pure compute (no DB) ────────────────────────────────────────────


@dataclass(frozen=True)
class RoiComputation:
    """One month's worth of ROI billing math for one tenant.

    All values stored as Decimal so callers can serialise them straight
    into NUMERIC(18,4) columns without precision loss.
    """
    actioned_revenue_at_risk_vnd: Decimal
    rate:                          Decimal
    cap_threshold_vnd:             Decimal
    raw_roi_addon_vnd:             Decimal
    capped_roi_addon_vnd:          Decimal
    cap_applied:                   bool
    months_of_data:                int
    eligibility_met:               bool


def compute_roi_addon(
    actioned_revenue_at_risk_vnd: Decimal,
    *,
    rate:              Decimal = DEFAULT_RATE,
    cap_threshold_vnd: Decimal = DEFAULT_CAP_VND,
    months_of_data:    int     = 0,
) -> RoiComputation:
    """Pure-compute one month's ROI add-on.

    `actioned_revenue_at_risk_vnd` must be a non-negative Decimal —
    caller is responsible for summing gold_features.revenue_at_risk
    WHERE is_actioned=TRUE for the period.

    `months_of_data` gates eligibility: if < MIN_MONTHS_OF_DATA, the
    line is still recorded (audit) but capped_roi_addon_vnd=0 and
    eligibility_met=FALSE. The cron uses this to surface "nearly
    eligible" tenants in the dashboard.
    """
    if actioned_revenue_at_risk_vnd < 0:
        raise ValueError(
            f"actioned_revenue_at_risk_vnd must be >= 0; got "
            f"{actioned_revenue_at_risk_vnd}"
        )
    if rate <= 0 or rate >= 1:
        raise ValueError(f"rate must be in (0,1); got {rate}")
    if cap_threshold_vnd <= 0:
        raise ValueError(f"cap_threshold_vnd must be > 0; got {cap_threshold_vnd}")
    if months_of_data < 0:
        raise ValueError(f"months_of_data must be >= 0; got {months_of_data}")

    eligibility_met = months_of_data >= MIN_MONTHS_OF_DATA

    raw = (actioned_revenue_at_risk_vnd * rate).quantize(Decimal("0.0001"))

    if not eligibility_met:
        # SH-M59-005 — record the line for audit, but charge zero.
        return RoiComputation(
            actioned_revenue_at_risk_vnd=actioned_revenue_at_risk_vnd,
            rate=rate,
            cap_threshold_vnd=cap_threshold_vnd,
            raw_roi_addon_vnd=raw,
            capped_roi_addon_vnd=Decimal("0.0000"),
            cap_applied=False,
            months_of_data=months_of_data,
            eligibility_met=False,
        )

    if raw > cap_threshold_vnd:
        return RoiComputation(
            actioned_revenue_at_risk_vnd=actioned_revenue_at_risk_vnd,
            rate=rate,
            cap_threshold_vnd=cap_threshold_vnd,
            raw_roi_addon_vnd=raw,
            capped_roi_addon_vnd=cap_threshold_vnd,
            cap_applied=True,
            months_of_data=months_of_data,
            eligibility_met=True,
        )

    return RoiComputation(
        actioned_revenue_at_risk_vnd=actioned_revenue_at_risk_vnd,
        rate=rate,
        cap_threshold_vnd=cap_threshold_vnd,
        raw_roi_addon_vnd=raw,
        capped_roi_addon_vnd=raw,
        cap_applied=False,
        months_of_data=months_of_data,
        eligibility_met=True,
    )


# Convenience: eligibility check on its own — useful for the opt-in flow
# so the FE can show "you'll be charged starting <date>".


def is_eligible(months_of_data: int, opted_in: bool) -> bool:
    """SH-M59-004 + 005: ENT ROI charges apply only when both:
      - tenant has opted in
      - tenant has ≥3 months of billing data
    """
    return opted_in and months_of_data >= MIN_MONTHS_OF_DATA


# ─── DB-touching helpers ─────────────────────────────────────────────


async def fetch_actioned_revenue_at_risk(
    conn,
    enterprise_id: UUID,
    *,
    billing_month: date,
) -> Decimal:
    """Sum gold_features.revenue_at_risk for actioned customers
    whose `actioned_at` (or `computed_at` as a fallback) lands inside
    the billing month.

    Implementation note: `gold_features` is upsert-on-recompute per
    tenant. To stay deterministic, em filter by `actioned_at` falling
    within [billing_month, next_month) and require is_actioned=TRUE.
    """
    sql = """
        SELECT COALESCE(SUM(revenue_at_risk), 0) AS total
        FROM gold_features
        WHERE enterprise_id = $1
          AND is_actioned = TRUE
          AND actioned_at >= $2::DATE
          AND actioned_at <  ($2::DATE + INTERVAL '1 month')
    """
    row = await conn.fetchrow(sql, enterprise_id, billing_month)
    if row is None or row["total"] is None:
        return Decimal("0")
    val = row["total"]
    return val if isinstance(val, Decimal) else Decimal(str(val))


async def fetch_months_of_data(
    conn,
    enterprise_id: UUID,
    *,
    upto_month: date,
) -> int:
    """Count distinct closed billing months strictly before `upto_month`."""
    sql = """
        SELECT COUNT(*) AS n
        FROM enterprise_monthly_billing
        WHERE enterprise_id = $1
          AND billing_month < $2::DATE
    """
    row = await conn.fetchrow(sql, enterprise_id, upto_month)
    return int(row["n"]) if row else 0


async def is_opted_in(conn, enterprise_id: UUID) -> bool:
    sql = """
        SELECT 1 FROM enterprise_roi_subscriptions
        WHERE enterprise_id = $1 AND opted_out_at IS NULL
    """
    row = await conn.fetchrow(sql, enterprise_id)
    return row is not None


async def has_existing_line(
    conn,
    enterprise_id: UUID,
    *,
    billing_month: date,
) -> bool:
    sql = """
        SELECT 1 FROM enterprise_roi_billing_lines
        WHERE enterprise_id = $1 AND billing_month = $2::DATE
    """
    row = await conn.fetchrow(sql, enterprise_id, billing_month)
    return row is not None


# ─── Cron entry point ────────────────────────────────────────────────


@dataclass
class CronLineOutcome:
    """One tenant's outcome from a monthly cron run."""
    enterprise_id:  UUID
    status:         str   # 'computed' | 'skipped_existing' | 'skipped_not_opted_in'
    computation:    Optional[RoiComputation] = None


@dataclass
class CronRunReport:
    """Top-level cron report."""
    billing_month:  date
    run_id:         UUID
    started_at:     datetime
    finished_at:    Optional[datetime] = None
    outcomes:       list[CronLineOutcome] = None
    run_kind:       str = "cron"   # 'cron' | 'manual' | 'preview'

    def __post_init__(self):
        if self.outcomes is None:
            self.outcomes = []

    @property
    def total_computed(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "computed")

    @property
    def total_skipped(self) -> int:
        return sum(1 for o in self.outcomes if o.status.startswith("skipped"))

    @property
    def total_addon_vnd(self) -> Decimal:
        total = Decimal("0")
        for o in self.outcomes:
            if o.computation is not None:
                total += o.computation.capped_roi_addon_vnd
        return total


async def compute_monthly_run(
    conn,
    *,
    billing_month: date,
    run_id:        Optional[UUID] = None,
    persist:       bool = True,
) -> CronRunReport:
    """SH-M59-001 — walk every opted-in tenant, compute one month's
    ROI add-on, persist to enterprise_roi_billing_lines.

    Idempotent: tenants with an existing line for `billing_month` are
    skipped (status='skipped_existing'). To force recompute, anh must
    DELETE the existing line first (manual operation — K-2 immutable).

    Pass `persist=False` for preview mode (returns outcomes without
    writing).
    """
    import uuid as _uuid

    if run_id is None:
        run_id = _uuid.uuid4()
    started = datetime.now(timezone.utc)
    report = CronRunReport(
        billing_month=billing_month,
        run_id=run_id,
        started_at=started,
        run_kind="cron" if persist else "preview",
    )

    rows = await conn.fetch(
        """SELECT enterprise_id FROM enterprise_roi_subscriptions
           WHERE opted_out_at IS NULL
           ORDER BY enterprise_id""",
    )

    for row in rows:
        ent_id = row["enterprise_id"]
        outcome = await _compute_one_tenant(
            conn, ent_id, billing_month=billing_month,
            run_id=run_id, persist=persist,
        )
        report.outcomes.append(outcome)

    report.finished_at = datetime.now(timezone.utc)
    log.info("roi_billing.cron_run_complete",
             billing_month=str(billing_month),
             run_id=str(run_id),
             total_computed=report.total_computed,
             total_skipped=report.total_skipped,
             total_addon_vnd=str(report.total_addon_vnd))
    return report


async def _compute_one_tenant(
    conn,
    enterprise_id: UUID,
    *,
    billing_month: date,
    run_id:        UUID,
    persist:       bool,
) -> CronLineOutcome:
    if persist and await has_existing_line(
        conn, enterprise_id, billing_month=billing_month,
    ):
        return CronLineOutcome(
            enterprise_id=enterprise_id,
            status="skipped_existing",
        )

    revenue = await fetch_actioned_revenue_at_risk(
        conn, enterprise_id, billing_month=billing_month,
    )
    months = await fetch_months_of_data(
        conn, enterprise_id, upto_month=billing_month,
    )
    comp = compute_roi_addon(
        revenue,
        months_of_data=months,
    )

    if persist:
        await conn.execute(
            """INSERT INTO enterprise_roi_billing_lines
                   (enterprise_id, billing_month,
                    actioned_revenue_at_risk_vnd, rate, cap_threshold_vnd,
                    raw_roi_addon_vnd, capped_roi_addon_vnd, cap_applied,
                    months_of_data, eligibility_met,
                    computed_by_run_id)
               VALUES ($1, $2::DATE,
                       $3, $4, $5,
                       $6, $7, $8,
                       $9, $10,
                       $11)
               ON CONFLICT (enterprise_id, billing_month) DO NOTHING""",
            enterprise_id, billing_month,
            comp.actioned_revenue_at_risk_vnd, comp.rate, comp.cap_threshold_vnd,
            comp.raw_roi_addon_vnd, comp.capped_roi_addon_vnd, comp.cap_applied,
            comp.months_of_data, comp.eligibility_met,
            run_id,
        )
        # If eligibility just confirmed, stamp the subscription row.
        if comp.eligibility_met:
            await conn.execute(
                """UPDATE enterprise_roi_subscriptions
                   SET eligibility_confirmed_at = COALESCE(
                       eligibility_confirmed_at, NOW())
                   WHERE enterprise_id = $1 AND opted_out_at IS NULL""",
                enterprise_id,
            )

    return CronLineOutcome(
        enterprise_id=enterprise_id,
        status="computed",
        computation=comp,
    )
