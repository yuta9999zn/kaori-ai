"""
SH-M59 ROI-Hybrid billing endpoints.

Endpoints
---------
Opt-in lifecycle:
    POST   /economics/roi/opt-in           opt the calling tenant into ENT ROI
    POST   /economics/roi/opt-out          opt the tenant back out
    GET    /economics/roi/subscription     current opt-in state

Compute + read:
    POST   /economics/roi/cron/compute     cron-triggered monthly run
                                            (body: { billing_month })
    POST   /economics/roi/preview          preview current/future month
                                            (no persist; body: { billing_month })
    GET    /economics/roi/billing-lines    paginated history
    GET    /economics/roi/billing-lines/{billing_month}  single-month read

K-1 / K-12: X-Enterprise-ID JWT header drives tenant scoping everywhere.
Cron endpoint also requires X-Enterprise-ID — Phase 2 internal cron runs
one tenant at a time; a future platform-admin /platform/billing/roi/cron/all
endpoint may iterate across tenants.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..org_intel.economics.roi_billing import (
    DEFAULT_CAP_VND,
    DEFAULT_RATE,
    MIN_MONTHS_OF_DATA,
    compute_monthly_run,
    fetch_actioned_revenue_at_risk,
    fetch_months_of_data,
    is_opted_in,
)
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────


class OptInOut(BaseModel):
    enterprise_id:           UUID
    opted_in_at:             datetime
    eligibility_confirmed_at: Optional[datetime]
    months_of_data:          int
    eligibility_met:         bool


class OptOutOut(BaseModel):
    enterprise_id: UUID
    opted_out_at:  datetime


class SubscriptionOut(BaseModel):
    enterprise_id:           UUID
    opted_in:                bool
    opted_in_at:             Optional[datetime]
    opted_out_at:            Optional[datetime]
    eligibility_confirmed_at: Optional[datetime]
    months_of_data:          int
    eligibility_met:         bool
    notes:                   Optional[str]


class ComputeRequest(BaseModel):
    billing_month: date = Field(..., description="First day of the month to bill.")


class ComputationOut(BaseModel):
    actioned_revenue_at_risk_vnd: str
    rate:                          str
    cap_threshold_vnd:             str
    raw_roi_addon_vnd:             str
    capped_roi_addon_vnd:          str
    cap_applied:                   bool
    months_of_data:                int
    eligibility_met:               bool


class CronOutcomeOut(BaseModel):
    enterprise_id: UUID
    status:        str
    computation:   Optional[ComputationOut]


class CronRunOut(BaseModel):
    billing_month:    date
    run_id:           UUID
    run_kind:         str
    started_at:       datetime
    finished_at:      Optional[datetime]
    total_computed:   int
    total_skipped:    int
    total_addon_vnd:  str
    outcomes:         list[CronOutcomeOut]


class BillingLineOut(BaseModel):
    line_id:                      UUID
    enterprise_id:                UUID
    billing_month:                date
    actioned_revenue_at_risk_vnd: str
    rate:                          str
    cap_threshold_vnd:             str
    raw_roi_addon_vnd:             str
    capped_roi_addon_vnd:          str
    cap_applied:                   bool
    months_of_data:                int
    eligibility_met:               bool
    computed_at:                   datetime
    computed_by_run_id:            Optional[UUID]
    notes:                         Optional[str]


def _comp_to_out(c) -> ComputationOut:
    return ComputationOut(
        actioned_revenue_at_risk_vnd=str(c.actioned_revenue_at_risk_vnd),
        rate=str(c.rate),
        cap_threshold_vnd=str(c.cap_threshold_vnd),
        raw_roi_addon_vnd=str(c.raw_roi_addon_vnd),
        capped_roi_addon_vnd=str(c.capped_roi_addon_vnd),
        cap_applied=c.cap_applied,
        months_of_data=c.months_of_data,
        eligibility_met=c.eligibility_met,
    )


# ─── Opt-in / opt-out lifecycle ──────────────────────────────────────


@router.post("/economics/roi/opt-in", response_model=OptInOut, status_code=201)
async def opt_in_roi(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """SH-M59-004 — opt the calling tenant into ENT ROI tier. Eligibility
    (≥3 months of data, SH-M59-005) is reported but not blocking — the
    monthly cron will skip charging until it confirms."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            """INSERT INTO enterprise_roi_subscriptions
                   (enterprise_id, opted_in_at)
               VALUES ($1, NOW())
               ON CONFLICT (enterprise_id) DO UPDATE SET
                   opted_in_at  = NOW(),
                   opted_out_at = NULL""",
            x_enterprise_id,
        )
        row = await conn.fetchrow(
            """SELECT opted_in_at, eligibility_confirmed_at
               FROM enterprise_roi_subscriptions
               WHERE enterprise_id = $1""",
            x_enterprise_id,
        )
        today = date.today().replace(day=1)
        months = await fetch_months_of_data(conn, x_enterprise_id, upto_month=today)

    log.info("roi_billing.opted_in",
             tenant_id=str(x_enterprise_id), months_of_data=months)
    return OptInOut(
        enterprise_id=x_enterprise_id,
        opted_in_at=row["opted_in_at"],
        eligibility_confirmed_at=row["eligibility_confirmed_at"],
        months_of_data=months,
        eligibility_met=months >= MIN_MONTHS_OF_DATA,
    )


@router.post("/economics/roi/opt-out", response_model=OptOutOut)
async def opt_out_roi(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Opt back out. Existing billing lines stay untouched (K-2)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE enterprise_roi_subscriptions
               SET opted_out_at = NOW()
               WHERE enterprise_id = $1 AND opted_out_at IS NULL
               RETURNING opted_out_at""",
            x_enterprise_id,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Tenant is not currently opted into ROI billing",
        )
    log.info("roi_billing.opted_out", tenant_id=str(x_enterprise_id))
    return OptOutOut(
        enterprise_id=x_enterprise_id,
        opted_out_at=row["opted_out_at"],
    )


@router.get("/economics/roi/subscription", response_model=SubscriptionOut)
async def get_subscription(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT opted_in_at, opted_out_at, eligibility_confirmed_at, notes
               FROM enterprise_roi_subscriptions
               WHERE enterprise_id = $1""",
            x_enterprise_id,
        )
        today = date.today().replace(day=1)
        months = await fetch_months_of_data(conn, x_enterprise_id, upto_month=today)

    if row is None:
        return SubscriptionOut(
            enterprise_id=x_enterprise_id,
            opted_in=False,
            opted_in_at=None,
            opted_out_at=None,
            eligibility_confirmed_at=None,
            months_of_data=months,
            eligibility_met=months >= MIN_MONTHS_OF_DATA,
            notes=None,
        )
    return SubscriptionOut(
        enterprise_id=x_enterprise_id,
        opted_in=row["opted_out_at"] is None,
        opted_in_at=row["opted_in_at"],
        opted_out_at=row["opted_out_at"],
        eligibility_confirmed_at=row["eligibility_confirmed_at"],
        months_of_data=months,
        eligibility_met=months >= MIN_MONTHS_OF_DATA,
        notes=row["notes"],
    )


# ─── Compute + read ──────────────────────────────────────────────────


@router.post("/economics/roi/cron/compute", response_model=CronRunOut)
async def cron_compute_one(
    body: ComputeRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """SH-M59-001 — synchronously compute + persist the billing line
    for the calling tenant for the given month. Idempotent: re-running
    skips an existing line for the same (enterprise_id, billing_month).

    Phase 2.5+ moves this onto a platform-admin endpoint that iterates
    all opted-in tenants in one run.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Only run for the calling tenant — guard against tenant_id leakage
        if not await is_opted_in(conn, x_enterprise_id):
            raise HTTPException(
                status_code=400,
                detail="Tenant is not opted into ROI billing",
            )
        # compute_monthly_run iterates "all opted-in" but K-1 RLS means
        # this connection only sees the calling tenant's subscription row.
        report = await compute_monthly_run(
            conn, billing_month=body.billing_month, persist=True,
        )

    return _report_to_out(report)


@router.post("/economics/roi/preview", response_model=CronRunOut)
async def preview_month(
    body: ComputeRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Compute without persisting. Useful for FE "how much would I
    have been charged?" widgets."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        if not await is_opted_in(conn, x_enterprise_id):
            # Allow preview even when not opted-in — surface eligibility
            # state so FE can show what the cost WOULD be after opt-in.
            revenue = await fetch_actioned_revenue_at_risk(
                conn, x_enterprise_id, billing_month=body.billing_month,
            )
            months = await fetch_months_of_data(
                conn, x_enterprise_id, upto_month=body.billing_month,
            )
            from ..org_intel.economics.roi_billing import compute_roi_addon
            comp = compute_roi_addon(revenue, months_of_data=months)
            from datetime import datetime as _dt, timezone as _tz
            import uuid as _uuid
            return CronRunOut(
                billing_month=body.billing_month,
                run_id=_uuid.uuid4(),
                run_kind="preview",
                started_at=_dt.now(_tz.utc),
                finished_at=_dt.now(_tz.utc),
                total_computed=1,
                total_skipped=0,
                total_addon_vnd=str(comp.capped_roi_addon_vnd),
                outcomes=[CronOutcomeOut(
                    enterprise_id=x_enterprise_id,
                    status="computed",
                    computation=_comp_to_out(comp),
                )],
            )
        report = await compute_monthly_run(
            conn, billing_month=body.billing_month, persist=False,
        )
    return _report_to_out(report)


def _report_to_out(report) -> CronRunOut:
    return CronRunOut(
        billing_month=report.billing_month,
        run_id=report.run_id,
        run_kind=report.run_kind,
        started_at=report.started_at,
        finished_at=report.finished_at,
        total_computed=report.total_computed,
        total_skipped=report.total_skipped,
        total_addon_vnd=str(report.total_addon_vnd),
        outcomes=[
            CronOutcomeOut(
                enterprise_id=o.enterprise_id,
                status=o.status,
                computation=_comp_to_out(o.computation) if o.computation else None,
            )
            for o in report.outcomes
        ],
    )


@router.get(
    "/economics/roi/billing-lines",
    response_model=list[BillingLineOut],
)
async def list_billing_lines(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    limit: int = Query(default=24, ge=1, le=120),
    from_month: Optional[date] = Query(default=None, alias="from"),
    to_month:   Optional[date] = Query(default=None, alias="to"),
):
    where = ["enterprise_id = $1"]
    params: list = [x_enterprise_id]
    if from_month is not None:
        where.append(f"billing_month >= ${len(params) + 1}::DATE")
        params.append(from_month)
    if to_month is not None:
        where.append(f"billing_month <= ${len(params) + 1}::DATE")
        params.append(to_month)
    sql = f"""
        SELECT line_id, enterprise_id, billing_month,
               actioned_revenue_at_risk_vnd, rate, cap_threshold_vnd,
               raw_roi_addon_vnd, capped_roi_addon_vnd, cap_applied,
               months_of_data, eligibility_met,
               computed_at, computed_by_run_id, notes
        FROM enterprise_roi_billing_lines
        WHERE {' AND '.join(where)}
        ORDER BY billing_month DESC
        LIMIT {limit}
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)
    return [
        BillingLineOut(
            line_id=r["line_id"],
            enterprise_id=r["enterprise_id"],
            billing_month=r["billing_month"],
            actioned_revenue_at_risk_vnd=str(r["actioned_revenue_at_risk_vnd"]),
            rate=str(r["rate"]),
            cap_threshold_vnd=str(r["cap_threshold_vnd"]),
            raw_roi_addon_vnd=str(r["raw_roi_addon_vnd"]),
            capped_roi_addon_vnd=str(r["capped_roi_addon_vnd"]),
            cap_applied=r["cap_applied"],
            months_of_data=r["months_of_data"],
            eligibility_met=r["eligibility_met"],
            computed_at=r["computed_at"],
            computed_by_run_id=r["computed_by_run_id"],
            notes=r["notes"],
        )
        for r in rows
    ]


@router.get(
    "/economics/roi/billing-lines/{billing_month}",
    response_model=BillingLineOut,
)
async def get_billing_line(
    billing_month: date,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        r = await conn.fetchrow(
            """SELECT line_id, enterprise_id, billing_month,
                      actioned_revenue_at_risk_vnd, rate, cap_threshold_vnd,
                      raw_roi_addon_vnd, capped_roi_addon_vnd, cap_applied,
                      months_of_data, eligibility_met,
                      computed_at, computed_by_run_id, notes
               FROM enterprise_roi_billing_lines
               WHERE enterprise_id = $1 AND billing_month = $2::DATE""",
            x_enterprise_id, billing_month,
        )
    if r is None:
        raise HTTPException(
            status_code=404,
            detail=f"No ROI billing line for {billing_month}",
        )
    return BillingLineOut(
        line_id=r["line_id"],
        enterprise_id=r["enterprise_id"],
        billing_month=r["billing_month"],
        actioned_revenue_at_risk_vnd=str(r["actioned_revenue_at_risk_vnd"]),
        rate=str(r["rate"]),
        cap_threshold_vnd=str(r["cap_threshold_vnd"]),
        raw_roi_addon_vnd=str(r["raw_roi_addon_vnd"]),
        capped_roi_addon_vnd=str(r["capped_roi_addon_vnd"]),
        cap_applied=r["cap_applied"],
        months_of_data=r["months_of_data"],
        eligibility_met=r["eligibility_met"],
        computed_at=r["computed_at"],
        computed_by_run_id=r["computed_by_run_id"],
        notes=r["notes"],
    )
