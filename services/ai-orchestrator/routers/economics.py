"""
ROI dashboard router — P15-S9 D7.

Reads from ``nov_monthly_digests`` (migration 043). The digest itself
is written by the nov_monthly_digest Temporal workflow — this router
is read-only.

Endpoints::

    GET /api/v1/economics/nov/current   latest digest + classification
    GET /api/v1/economics/nov/trend     last N months for the trend tile
                                        (?months=N, default 6, max 24)

Auth + tenant scoping via ``X-Enterprise-Id`` header (gateway-trusted)
+ ``acquire_for_tenant`` so RLS on the digest table enforces isolation
(K-1 / ADR-0013) at the database layer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..org_intel.economics.cfo_digest import (
    build_quarterly_digest,
    quarter_bounds,
    quarter_label,
)
from ..org_intel.economics.cost import (
    AmortizedCost,
    amortize_setup_cost,
)
from ..org_intel.economics.persistence import (
    fetch_current_digest,
    fetch_quarter_window,
    fetch_trend,
)
from ..org_intel.economics.revenue import (
    RevenueEstimate,
    VarianceAnalysis,
    estimate_revenue_ab_attribution,
    estimate_revenue_industry_benchmark,
    estimate_revenue_pre_post,
    estimate_revenue_variance,
)
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Wire shapes — kept Decimal-as-str on the way out so JSON consumers
# don't lose precision (browsers parse numbers as float64 → 4-decimal
# VND becomes lossy at large amounts). Frontend converts back to BigInt
# / Decimal-like for display.
# ---------------------------------------------------------------------------


class NOVMonthEntry(BaseModel):
    """One month's NOV digest, formatted for the dashboard tile."""

    month_start: str  # ISO date 'YYYY-MM-01'
    revenue_vnd: str
    cost_vnd: str
    nov_vnd: str
    revenue_method: str
    revenue_confidence: str
    people_cost_vnd: str
    ai_cost_vnd: str
    infra_cost_vnd: str
    integration_cost_vnd: str
    is_negative: bool
    revision: int


class NOVCurrentResponse(BaseModel):
    """GET /economics/nov/current envelope.

    Returns null `current` (HTTP 200, not 404) when no digest exists
    yet — a brand-new tenant + workflow hasn't run; the dashboard
    renders an empty state rather than an error tile.
    """
    current: NOVMonthEntry | None
    classification: str = Field(
        ...,
        description="positive / negative / no_data — drives tile colour",
    )


class NOVTrendResponse(BaseModel):
    """GET /economics/nov/trend envelope. Months are oldest → newest."""

    months: list[NOVMonthEntry]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/economics/nov/current", response_model=NOVCurrentResponse)
async def get_current_nov(
    x_enterprise_id: Annotated[str, Header()],
):
    """Latest digest for the tenant + classification hint.

    Tenant scoping: the gateway-supplied ``X-Enterprise-Id`` header
    populates the RLS GUC via ``acquire_for_tenant``. K-12 — header
    extracted from JWT claims at the gateway, never trusted from the
    body / query string.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await fetch_current_digest(conn, enterprise_id=enterprise_id)
    if row is None:
        return NOVCurrentResponse(current=None, classification="no_data")
    classification = "negative" if row.is_negative() else "positive"
    return NOVCurrentResponse(
        current=_to_month_entry(row),
        classification=classification,
    )


@router.get("/economics/nov/trend", response_model=NOVTrendResponse)
async def get_nov_trend(
    x_enterprise_id: Annotated[str, Header()],
    months: int = Query(default=6, ge=1, le=24,
                        description="How many months of history to return."),
):
    """Last N months of digests, oldest → newest. Front-end plots
    left-to-right; the persistence layer reverses order before return."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await fetch_trend(conn, enterprise_id=enterprise_id, months=months)
    return NOVTrendResponse(months=[_to_month_entry(r) for r in rows])


# ---------------------------------------------------------------------------
# P15-S10 D5 — revenue estimate dispatcher
# ---------------------------------------------------------------------------


class _PrePostInputs(BaseModel):
    revenue_30d_before_vnd: str
    revenue_30d_after_vnd: str


class _ABInputs(BaseModel):
    control_revenue_vnd: str
    treatment_revenue_vnd: str
    control_group_size: int = Field(ge=0)
    treatment_group_size: int = Field(ge=0)
    total_population: int | None = Field(default=None, ge=0)


class _BenchmarkInputs(BaseModel):
    industry: str = Field(min_length=1, max_length=64)
    annual_revenue_vnd: str


class _VarianceInputs(BaseModel):
    """NOV-REV-006 — predicted vs actual variance check."""
    predicted_vnd:         str
    actual_vnd:            str
    predicted_confidence:  str = "0.7"


class RevenueEstimateRequest(BaseModel):
    """POST /economics/revenue/estimate body. Method discriminates which
    inputs are read; the others are ignored. Decimal-as-str on the way
    in (precision-safe — see _to_month_entry rationale)."""

    method: str = Field(
        ...,
        description="'pre_post' | 'a_b' | 'industry_benchmark' | 'variance'",
    )
    pre_post: _PrePostInputs | None = None
    a_b: _ABInputs | None = None
    industry_benchmark: _BenchmarkInputs | None = None
    variance: _VarianceInputs | None = None


class RevenueEstimateResponse(BaseModel):
    revenue_vnd: str
    confidence: str
    method: str
    note: str | None = None
    # NOV-REV-006 — populated ONLY when method='variance'
    variance: dict | None = None


@router.post(
    "/economics/revenue/estimate",
    response_model=RevenueEstimateResponse,
    tags=["Operational Economics"],
)
async def estimate_revenue(
    body: RevenueEstimateRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """Dispatch to one of 3 revenue estimators (NOV-REV-001/002/003).

    Pure function — no DB access. Tenant header is still parsed for
    audit logging + future per-tenant override hooks (vendor cap, etc.).
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    method = body.method.lower().strip()

    if method == "pre_post":
        if not body.pre_post:
            raise _missing_inputs("pre_post")
        est = estimate_revenue_pre_post(
            revenue_30d_before_vnd=Decimal(body.pre_post.revenue_30d_before_vnd),
            revenue_30d_after_vnd=Decimal(body.pre_post.revenue_30d_after_vnd),
        )
    elif method == "a_b":
        if not body.a_b:
            raise _missing_inputs("a_b")
        est = estimate_revenue_ab_attribution(
            control_revenue_vnd=Decimal(body.a_b.control_revenue_vnd),
            treatment_revenue_vnd=Decimal(body.a_b.treatment_revenue_vnd),
            control_group_size=body.a_b.control_group_size,
            treatment_group_size=body.a_b.treatment_group_size,
            total_population=body.a_b.total_population,
        )
    elif method == "industry_benchmark":
        if not body.industry_benchmark:
            raise _missing_inputs("industry_benchmark")
        est = estimate_revenue_industry_benchmark(
            industry=body.industry_benchmark.industry,
            annual_revenue_vnd=Decimal(body.industry_benchmark.annual_revenue_vnd),
        )
    elif method == "variance":
        # NOV-REV-006 — variance analysis. Returns the actual_vnd as
        # `revenue_vnd` for envelope compatibility; the variance fields
        # live under .variance.
        if not body.variance:
            raise _missing_inputs("variance")
        v = estimate_revenue_variance(
            predicted_vnd=Decimal(body.variance.predicted_vnd),
            actual_vnd=Decimal(body.variance.actual_vnd),
            predicted_confidence=Decimal(body.variance.predicted_confidence),
        )
        log.info(
            "economics.revenue.variance_computed",
            tenant_id=str(enterprise_id),
            verdict=v.verdict,
            relative_variance=str(v.relative_variance),
        )
        return RevenueEstimateResponse(
            revenue_vnd=_dec_str(v.actual_vnd),
            confidence=_dec_str(v.confidence),
            method="variance",
            note=v.note,
            variance={
                "predicted_vnd":     _dec_str(v.predicted_vnd),
                "actual_vnd":        _dec_str(v.actual_vnd),
                "variance_vnd":      _dec_str(v.variance_vnd),
                "relative_variance": _dec_str(v.relative_variance),
                "verdict":           v.verdict,
            },
        )
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://kaori.ai/errors/bad-revenue-method",
                "title": "Unknown revenue estimation method",
                "detail": f"got method={method!r}; expected one of "
                          "['pre_post', 'a_b', 'industry_benchmark', 'variance']",
                "errcode": "USR-ERR4",
            },
        )

    log.info(
        "economics.revenue.estimated",
        tenant_id=str(enterprise_id),
        method=est.method,
        confidence=str(est.confidence),
    )
    return RevenueEstimateResponse(
        revenue_vnd=_dec_str(est.revenue_vnd),
        confidence=_dec_str(est.confidence),
        method=est.method,
        note=est.note,
    )


# ─── NOV-CST-012 — Cost amortization endpoint ──────────────────────


class CostAmortizeRequest(BaseModel):
    total_setup_vnd: str
    term_months:     int = Field(default=12, ge=1, le=120)
    months_elapsed:  int = Field(default=1, ge=0, le=120)


class CostAmortizeResponse(BaseModel):
    total_setup_vnd:           str
    term_months:               int
    monthly_amortized_vnd:     str
    months_elapsed:            int
    months_remaining:          int
    cumulative_amortized_vnd:  str
    remaining_to_amortize_vnd: str
    fully_amortized:           bool


@router.post(
    "/economics/cost/compute",
    response_model=CostAmortizeResponse,
    tags=["Operational Economics"],
)
async def compute_cost(
    body: CostAmortizeRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """NOV-CST-012 — straight-line amortization of one-time setup cost.

    Body returns the full schedule (monthly allocation + cumulative +
    remaining) so the CFO digest can render the table without a second
    call. Pure function — no DB access; tenant header parsed for audit.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    try:
        result = amortize_setup_cost(
            total_setup_vnd=Decimal(body.total_setup_vnd),
            term_months=body.term_months,
            months_elapsed=body.months_elapsed,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "type":   "https://kaori.ai/errors/bad-amortize-inputs",
                "title":  "Cost amortization inputs invalid",
                "detail": str(e),
                "errcode": "USR-ERR3",
            },
        )
    log.info(
        "economics.cost.amortized",
        tenant_id=str(enterprise_id),
        term_months=body.term_months,
        months_elapsed=body.months_elapsed,
        monthly=str(result.monthly_amortized_vnd),
    )
    return CostAmortizeResponse(
        total_setup_vnd=_dec_str(result.total_setup_vnd),
        term_months=result.term_months,
        monthly_amortized_vnd=_dec_str(result.monthly_amortized_vnd),
        months_elapsed=result.months_elapsed,
        months_remaining=result.months_remaining,
        cumulative_amortized_vnd=_dec_str(result.cumulative_amortized_vnd),
        remaining_to_amortize_vnd=_dec_str(result.remaining_to_amortize_vnd),
        fully_amortized=result.fully_amortized,
    )


# ─── NOV-RPT-020 — CFO quarterly digest ────────────────────────────


class _PeriodComparisonOut(BaseModel):
    this_period_vnd:  str
    other_period_vnd: str
    absolute_delta:   str
    relative_delta:   str
    verdict:          str


class _CostBreakdownOut(BaseModel):
    people_vnd:      str
    ai_vnd:          str
    infra_vnd:       str
    integration_vnd: str
    total_vnd:       str


class CFODigestResponse(BaseModel):
    enterprise_id:        str
    quarter:              str
    quarter_start:        str
    quarter_end:          str
    month_count:          int
    revenue_total_vnd:    str
    cost_total_vnd:       str
    nov_total_vnd:        str
    cost_breakdown:       _CostBreakdownOut
    monthly_run_rate_vnd: str
    qoq:                  _PeriodComparisonOut | None
    yoy:                  _PeriodComparisonOut | None
    amortized_setup_vnd:  str
    notes:                list[str]


def _previous_quarter(q: str) -> str:
    """'2026-Q2' → '2026-Q1'; '2026-Q1' → '2025-Q4'."""
    y, n = q.split("-Q")
    y, n = int(y), int(n)
    if n == 1:
        return f"{y - 1}-Q4"
    return f"{y}-Q{n - 1}"


def _same_quarter_last_year(q: str) -> str:
    y, n = q.split("-Q")
    return f"{int(y) - 1}-Q{n}"


@router.get(
    "/economics/reports/manager-digest",
    response_model=CFODigestResponse,
    tags=["Operational Economics"],
)
async def manager_digest(
    x_enterprise_id: Annotated[str, Header()],
    period: str = Query("quarterly", description="'quarterly' only Phase 1.5"),
    quarter: str | None = Query(
        None,
        description="ISO-ish 'YYYY-Qn' label. Defaults to the quarter "
                    "containing today.",
    ),
    setup_monthly_vnd: str = Query(
        "0",
        description="Monthly-amortized setup cost to fold into the digest "
                    "(decimal-as-str). Caller computes via "
                    "/economics/cost/compute then passes the result here.",
    ),
):
    """NOV-RPT-020 — CFO-style quarterly digest.

    Aggregates 3 monthly digests + QoQ + YoY comparisons. Phase 1.5 only
    supports period='quarterly'; monthly/annual variants land Phase 2.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)

    if period != "quarterly":
        raise HTTPException(
            status_code=400,
            detail=f"period={period!r} not supported (Phase 1.5 = 'quarterly' only)",
        )

    from datetime import date as _date
    q_label = quarter or quarter_label(_date.today())
    try:
        q_start, q_end = quarter_bounds(q_label)
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail=f"quarter={q_label!r} must be 'YYYY-Qn' where n ∈ 1..4",
        )

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await fetch_quarter_window(
            conn, enterprise_id=enterprise_id,
            quarter_start=q_start, quarter_end=q_end,
        )
        # QoQ + YoY pull
        prev_q = _previous_quarter(q_label)
        prev_start, prev_end = quarter_bounds(prev_q)
        prev_rows = await fetch_quarter_window(
            conn, enterprise_id=enterprise_id,
            quarter_start=prev_start, quarter_end=prev_end,
        )
        yoy_q = _same_quarter_last_year(q_label)
        yoy_start, yoy_end = quarter_bounds(yoy_q)
        yoy_rows = await fetch_quarter_window(
            conn, enterprise_id=enterprise_id,
            quarter_start=yoy_start, quarter_end=yoy_end,
        )

    digest = build_quarterly_digest(
        enterprise_id=str(enterprise_id),
        quarter=q_label,
        monthly_rows=rows,
        prev_quarter_rows=prev_rows or None,
        same_quarter_last_year_rows=yoy_rows or None,
        amortized_setup_monthly_vnd=Decimal(setup_monthly_vnd),
    )

    log.info(
        "economics.cfo_digest.served",
        tenant_id=str(enterprise_id), quarter=q_label,
        month_count=digest.month_count,
        nov_total=str(digest.nov_total_vnd),
    )

    def _cmp_out(c):
        if c is None:
            return None
        return _PeriodComparisonOut(
            this_period_vnd=_dec_str(c.this_period_vnd),
            other_period_vnd=_dec_str(c.other_period_vnd),
            absolute_delta=_dec_str(c.absolute_delta),
            relative_delta=_dec_str(c.relative_delta),
            verdict=c.verdict,
        )

    return CFODigestResponse(
        enterprise_id=digest.enterprise_id,
        quarter=digest.quarter,
        quarter_start=digest.quarter_start.isoformat(),
        quarter_end=digest.quarter_end.isoformat(),
        month_count=digest.month_count,
        revenue_total_vnd=_dec_str(digest.revenue_total_vnd),
        cost_total_vnd=_dec_str(digest.cost_total_vnd),
        nov_total_vnd=_dec_str(digest.nov_total_vnd),
        cost_breakdown=_CostBreakdownOut(
            people_vnd=_dec_str(digest.cost_breakdown.people_vnd),
            ai_vnd=_dec_str(digest.cost_breakdown.ai_vnd),
            infra_vnd=_dec_str(digest.cost_breakdown.infra_vnd),
            integration_vnd=_dec_str(digest.cost_breakdown.integration_vnd),
            total_vnd=_dec_str(digest.cost_breakdown.total_vnd),
        ),
        monthly_run_rate_vnd=_dec_str(digest.monthly_run_rate_vnd),
        qoq=_cmp_out(digest.qoq),
        yoy=_cmp_out(digest.yoy),
        amortized_setup_vnd=_dec_str(digest.amortized_setup_vnd),
        notes=digest.notes,
    )


def _missing_inputs(method: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "type": "https://kaori.ai/errors/missing-method-inputs",
            "title": f"method={method!r} requires the matching inputs object",
            "detail": f"please populate body.{method}",
            "errcode": "USR-ERR3",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_enterprise_id(header_value: str) -> UUID:
    """Parse + validate the X-Enterprise-Id header. K-14 — return RFC
    7807 problem on bad UUID rather than 422 with pydantic-style detail
    so the front-end's error renderer has one shape to handle."""
    try:
        return UUID(header_value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://kaori.ai/errors/bad-enterprise-id",
                "title": "X-Enterprise-Id must be a UUID",
                "detail": f"got {header_value!r}",
            },
        )


def _to_month_entry(row) -> NOVMonthEntry:
    """Persistence row → wire entry. Decimal serialised as str so the
    JSON layer can't lose precision."""
    return NOVMonthEntry(
        month_start=row.month_start.isoformat(),
        revenue_vnd=_dec_str(row.revenue_vnd),
        cost_vnd=_dec_str(row.cost_vnd),
        nov_vnd=_dec_str(row.nov_vnd),
        revenue_method=row.revenue_method,
        revenue_confidence=_dec_str(row.revenue_confidence),
        people_cost_vnd=_dec_str(row.people_cost_vnd),
        ai_cost_vnd=_dec_str(row.ai_cost_vnd),
        infra_cost_vnd=_dec_str(row.infra_cost_vnd),
        integration_cost_vnd=_dec_str(row.integration_cost_vnd),
        is_negative=row.is_negative(),
        revision=row.revision,
    )


def _dec_str(value: Decimal | float | int | str) -> str:
    """Coerce to ``str`` without losing trailing zeros from NUMERIC.

    NUMERIC(14,4) returns Decimal('100.0000') — we keep that shape so
    a comparison test against a fixture is stable instead of
    sensitive to int/Decimal round-trips."""
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


# ═════════════════════════════════════════════════════════════════════
# P2-S21 D6 + D7 — NOV-RPT-023 recommendations + NOV-RPT-024 simulation
# ═════════════════════════════════════════════════════════════════════


from ..org_intel.economics.recommendations import (  # noqa: E402
    OKRRef,
    TemplateCandidate,
    WorkflowRecommendation,
    WorkflowRoiRow,
    recommend_workflow_fixes,
)
from ..org_intel.economics.simulation import (  # noqa: E402
    BaselineDigest,
    ScenarioChange,
    SimulationResult,
    simulate_nov,
)
from typing import Optional  # noqa: E402


# ─── D6 Recommendations endpoint ─────────────────────────────────────


class OKRRefOut(BaseModel):
    okr_id:              UUID
    objective_text:      str
    progress:            str
    contribution_weight: str


class TemplateCandidateOut(BaseModel):
    template_id:        UUID
    display_name:       str
    display_name_vi:    str
    department_type:    str
    industry_vertical:  Optional[str]
    category:           Optional[str]
    estimated_setup_minutes: int


class WorkflowRecommendationOut(BaseModel):
    workflow_id:       UUID
    workflow_name:     str
    department_type:   str
    current_roi:       str
    nov_vnd:           str
    severity:          str
    reason_vi:         str
    suggested_template: Optional[TemplateCandidateOut]
    blocked_okrs:      list[OKRRefOut]


@router.get(
    "/economics/reports/manager-digest/recommendations",
    response_model=list[WorkflowRecommendationOut],
    tags=["Operational Economics"],
)
async def manager_digest_recommendations(
    x_enterprise_id: Annotated[str, Header()],
    quarter: Optional[str] = Query(None, description="ISO 'YYYY-Qn' (defaults to current)"),
    top_k: int = Query(3, ge=1, le=10),
):
    """NOV-RPT-023 — top-K underperforming workflows + suggested
    replacement templates + blocked OKRs.

    Triggered when CFO digest shows negative NOV. Pure read endpoint —
    suggestions are advisory, not auto-applied.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    from datetime import date as _date
    q_label = quarter or quarter_label(_date.today())
    try:
        q_start, q_end = quarter_bounds(q_label)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400,
                            detail=f"quarter={q_label!r} must be 'YYYY-Qn' where n ∈ 1..4")

    async with acquire_for_tenant(enterprise_id) as conn:
        wf_rows = await conn.fetch(
            """SELECT
                  w.workflow_id, w.name AS workflow_name,
                  d.department_type,
                  COALESCE(SUM(m.revenue_vnd), 0) AS revenue_vnd,
                  COALESCE(SUM(m.people_cost_vnd + m.ai_cost_vnd
                              + m.infra_cost_vnd + m.integration_cost_vnd), 0) AS cost_vnd
               FROM workflows w
               LEFT JOIN departments d ON d.department_id = w.department_id
               LEFT JOIN nov_monthly_digests m
                  ON m.enterprise_id = w.enterprise_id
                  AND m.period_month >= $1 AND m.period_month <= $2
               WHERE w.enterprise_id = $3
               GROUP BY w.workflow_id, w.name, d.department_type""",
            q_start, q_end, enterprise_id,
        )
        workflows = []
        for r in wf_rows:
            revenue = Decimal(r["revenue_vnd"] or 0)
            cost = Decimal(r["cost_vnd"] or 0)
            nov = revenue - cost
            roi = (nov / cost) if cost > 0 else Decimal("0")
            workflows.append(WorkflowRoiRow(
                workflow_id=r["workflow_id"],
                workflow_name=r["workflow_name"] or "(unnamed)",
                department_type=r["department_type"] or "custom",
                revenue_vnd=revenue, cost_vnd=cost,
                nov_vnd=nov, roi=roi,
            ))

        # Templates pool — all active mig 069 templates
        tpl_rows = await conn.fetch(
            """SELECT template_id, display_name, display_name_vi,
                      department_type, industry_vertical, category,
                      estimated_setup_minutes
               FROM workflow_templates WHERE is_active = TRUE"""
        )
        templates = [
            TemplateCandidate(
                template_id=t["template_id"],
                display_name=t["display_name"],
                display_name_vi=t["display_name_vi"],
                department_type=t["department_type"],
                industry_vertical=t["industry_vertical"],
                category=t["category"],
                estimated_setup_minutes=t["estimated_setup_minutes"],
            )
            for t in tpl_rows
        ]

        # Linked OKRs per workflow — join workflow_okr_links → okrs
        link_rows = await conn.fetch(
            """SELECT l.workflow_id, l.contribution_weight,
                      o.okr_id, o.objective_text, o.progress
               FROM workflow_okr_links l
               JOIN okrs o ON o.okr_id = l.okr_id
               WHERE l.enterprise_id = $1 AND o.status IN ('DRAFT', 'ACTIVE')""",
            enterprise_id,
        )
        linked: dict[UUID, list[OKRRef]] = {}
        for r in link_rows:
            linked.setdefault(r["workflow_id"], []).append(OKRRef(
                okr_id=r["okr_id"],
                objective_text=r["objective_text"],
                progress=Decimal(r["progress"]),
                contribution_weight=Decimal(r["contribution_weight"]),
            ))

    recs = recommend_workflow_fixes(
        workflows=workflows,
        available_templates=templates,
        linked_okrs_by_workflow=linked,
        top_k=top_k,
    )
    return [_serialize_recommendation(r) for r in recs]


def _serialize_recommendation(r: WorkflowRecommendation) -> WorkflowRecommendationOut:
    return WorkflowRecommendationOut(
        workflow_id=r.workflow_id,
        workflow_name=r.workflow_name,
        department_type=r.department_type,
        current_roi=str(r.current_roi),
        nov_vnd=str(r.nov_vnd),
        severity=r.severity,
        reason_vi=r.reason_vi,
        suggested_template=(
            TemplateCandidateOut(**r.suggested_template.__dict__)
            if r.suggested_template else None
        ),
        blocked_okrs=[
            OKRRefOut(
                okr_id=o.okr_id,
                objective_text=o.objective_text,
                progress=str(o.progress),
                contribution_weight=str(o.contribution_weight),
            )
            for o in r.blocked_okrs
        ],
    )


# ─── D7 Simulation endpoint ──────────────────────────────────────────


class SimulateRequest(BaseModel):
    """What-if scenario request. period_label identifies the baseline
    digest row to load; all change fields default to 0 so the request
    is partial-friendly."""
    period_label:           str = Field(..., min_length=4, max_length=16,
                                         description="'YYYY-MM' baseline month")
    revenue_uplift_pct:     str = Field("0", description="Decimal-as-str")
    cost_reduction_pct:     str = Field("0", description="Decimal-as-str")
    people_cost_change_pct: str = Field("0", description="Decimal-as-str")
    ai_cost_change_pct:     str = Field("0", description="Decimal-as-str")
    user_count_change:      int = 0
    notes:                  Optional[str] = None


class SimulationResultOut(BaseModel):
    baseline_nov_vnd:    str
    projected_nov_vnd:   str
    delta_vnd:           str
    delta_pct:           str
    confidence_low_vnd:  str
    confidence_high_vnd: str
    assumptions:         list[str]


@router.post(
    "/economics/reports/manager-digest/simulate",
    response_model=SimulationResultOut,
    tags=["Operational Economics"],
)
async def manager_digest_simulate(
    body: SimulateRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """NOV-RPT-024 — what-if simulation of NOV under a scenario change.

    Loads the baseline monthly digest by period_label, applies the
    scenario, returns projected NOV + 95% CI + assumptions.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT enterprise_id, period_month, revenue_vnd,
                      people_cost_vnd, ai_cost_vnd, infra_cost_vnd,
                      integration_cost_vnd,
                      COALESCE(setup_amortized_vnd, 0) AS setup_amortized_vnd,
                      COALESCE(user_count, 1) AS user_count
               FROM nov_monthly_digests
               WHERE enterprise_id = $1 AND period_label = $2""",
            enterprise_id, body.period_label,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"no monthly digest for period_label={body.period_label!r}",
        )
    baseline = BaselineDigest(
        enterprise_id=row["enterprise_id"],
        period_label=body.period_label,
        revenue_vnd=Decimal(row["revenue_vnd"]),
        people_cost_vnd=Decimal(row["people_cost_vnd"]),
        ai_cost_vnd=Decimal(row["ai_cost_vnd"]),
        infra_cost_vnd=Decimal(row["infra_cost_vnd"]),
        integration_cost_vnd=Decimal(row["integration_cost_vnd"]),
        setup_amortized_vnd=Decimal(row["setup_amortized_vnd"]),
        user_count=int(row["user_count"]),
    )
    scenario = ScenarioChange(
        revenue_uplift_pct=Decimal(body.revenue_uplift_pct),
        cost_reduction_pct=Decimal(body.cost_reduction_pct),
        people_cost_change_pct=Decimal(body.people_cost_change_pct),
        ai_cost_change_pct=Decimal(body.ai_cost_change_pct),
        user_count_change=body.user_count_change,
        notes=body.notes,
    )
    result = simulate_nov(baseline, scenario)
    return SimulationResultOut(
        baseline_nov_vnd=str(result.baseline_nov_vnd),
        projected_nov_vnd=str(result.projected_nov_vnd),
        delta_vnd=str(result.delta_vnd),
        delta_pct=str(result.delta_pct),
        confidence_low_vnd=str(result.confidence_low_vnd),
        confidence_high_vnd=str(result.confidence_high_vnd),
        assumptions=list(result.assumptions),
    )
