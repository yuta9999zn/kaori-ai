"""
F-038 Reports — HTTP surface.

Three endpoints under /api/v1/reports — matching the Phase 1 routing
convention while the backend stabilises. Phase 2's
/api/v2/enterprise/reports prefix lives in the BACKLOG spec but is a
separate API-versioning concern; the FE templates already point at
/api/v1/reports so the migration window stays small.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from ..reports import repository, service
from ..reports.service import (
    InvalidDistributionError,
    ReportNotFoundError,
    ReportNotReadyError,
    TemplateNotFoundError,
)
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Wire shapes ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    template_id: UUID = Field(
        ...,
        description="report_templates.template_id — built-in or per-tenant.",
    )
    title: str = Field(
        ...,
        min_length=3, max_length=200,
        description="User-facing title for the FE list view + email subject.",
    )
    owner_email: EmailStr = Field(
        ...,
        description="Where to send the report-ready notification.",
    )
    params: dict = Field(
        default_factory=dict,
        description="Opaque caller params forwarded to the template's "
                    "system prompt (period, dataset filter, etc.).",
    )


class ReportListItem(BaseModel):
    """Trimmed shape for the list view — content_json is omitted to
    keep the response under a few KB regardless of report size."""
    report_id:    UUID
    template_id:  UUID
    title:        str
    owner_email:  str
    status:       str
    narrative:    Optional[str] = None
    created_at:   datetime
    completed_at: Optional[datetime] = None
    last_error:   Optional[str] = None


class ReportDetail(ReportListItem):
    """Full shape including the validated content_json. Returned by the
    detail endpoint."""
    content_json: Optional[dict] = None


class GenerateResponse(BaseModel):
    report_id: UUID
    status:    str = Field(default="queued")


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    next_cursor: Optional[str] = Field(
        default=None,
        description="Pass back as ``cursor`` query param to fetch the "
                    "next page. Absent when no more rows.",
    )


# ─── Endpoints ───────────────────────────────────────────────────

@router.post(
    "/reports/generate",
    response_model=GenerateResponse,
    status_code=202,
)
async def generate(
    req: GenerateRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """Queue a report. Returns 202 + the new report_id immediately;
    the actual generation runs as a background asyncio task. Poll the
    GET endpoint until status='ready' or status='failed'."""
    try:
        report_id = await service.queue_report(
            enterprise_id=x_enterprise_id,
            template_id=req.template_id,
            title=req.title,
            owner_email=str(req.owner_email),
            params=req.params,
        )
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Fire the worker. asyncio.create_task is intentional here — the
    # whole point of returning 202 is that the user doesn't wait for
    # the LLM. The worker captures every exception internally so we
    # never lose a task to an unhandled raise.
    asyncio.create_task(
        service.run_report(enterprise_id=x_enterprise_id, report_id=report_id),
        name=f"reports-{report_id}",
    )

    return GenerateResponse(report_id=report_id, status="queued")


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    x_enterprise_id: Annotated[str, Header()],
    cursor: Annotated[Optional[str], Query(description="Opaque cursor from previous page.")] = None,
    limit:  Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Cursor-paginated list of reports for the calling tenant.
    Cursor format: ``<created_at_iso>|<report_id>`` so the next page
    can resume after the last row deterministically."""
    cursor_ts: Optional[datetime] = None
    cursor_id: Optional[UUID] = None
    if cursor:
        try:
            ts_part, id_part = cursor.split("|", 1)
            cursor_ts = datetime.fromisoformat(ts_part)
            cursor_id = UUID(id_part)
        except (ValueError, AttributeError) as exc:
            raise HTTPException(
                status_code=400,
                detail="invalid cursor (expected '<iso8601>|<uuid>')",
            ) from exc

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await repository.list_reports(
            conn,
            limit=limit + 1,  # +1 to know if there's a next page
            cursor_created_at=cursor_ts,
            cursor_report_id=cursor_id,
        )

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last['created_at'].isoformat()}|{last['report_id']}"

    return ReportListResponse(
        items=[ReportListItem(**r) for r in items],
        next_cursor=next_cursor,
    )


@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: UUID,
    x_enterprise_id: Annotated[str, Header()],
):
    """Single report including content_json. RLS ensures cross-tenant
    requests return 404 (the row simply isn't visible)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await repository.fetch_report(conn, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")
    return ReportDetail(**row)


# ─── Distribution (F-038 follow-up — migration 029) ──────────────

class DistributeRequest(BaseModel):
    recipients: list[EmailStr] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Email addresses to send this report to. De-duped + "
                    "trimmed server-side; max 50 per call.",
    )
    custom_message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional sender-supplied message rendered above the "
                    "default copy in the email body.",
    )


class DistributionItem(BaseModel):
    recipient:       str
    distribution_id: Optional[UUID] = None
    outbox_id:       Optional[UUID] = None
    status:          str


class DistributeResponse(BaseModel):
    report_id:       UUID
    recipient_count: int
    success_count:   int
    failure_count:   int
    distributions:   list[DistributionItem]


class DistributionRow(BaseModel):
    distribution_id:    UUID
    report_id:          UUID
    recipient_email:    str
    channel:            str
    outbox_id:          Optional[UUID] = None
    dispatch_status:    str
    custom_message:     Optional[str] = None
    triggered_by_user:  Optional[UUID] = None
    dispatch_error:     Optional[str] = None
    created_at:         datetime
    # Joined from notification_outbox — None when outbox row is gone
    # (shouldn't happen in normal ops; here for forensic completeness).
    outbox_status:      Optional[str] = None
    outbox_attempts:    Optional[int] = None
    outbox_error:       Optional[str] = None
    outbox_sent_at:     Optional[datetime] = None


class DistributionListResponse(BaseModel):
    items: list[DistributionRow]


@router.post(
    "/reports/{report_id}/distribute",
    response_model=DistributeResponse,
    status_code=202,
)
async def distribute(
    report_id: UUID,
    req: DistributeRequest,
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[Optional[str], Header()] = None,
):
    """Manually distribute a ready report to additional recipients.
    Returns 202 + a per-recipient summary. Each recipient gets one
    notification_outbox row (poller handles SMTP retries) and one
    report_distributions audit row.

    Status codes:
      * 404 — report not found / not visible to tenant
      * 409 — report exists but status != 'ready'
      * 400 — empty / over-cap recipients
    """
    triggered_by: Optional[UUID] = None
    if x_user_id:
        try:
            triggered_by = UUID(x_user_id)
        except ValueError:
            # Header is forwarded by the gateway from JWT; an invalid
            # value is a config bug, not user input. Log + drop.
            log.warning("reports.distribute.bad_x_user_id", value=x_user_id)

    try:
        summary = await service.distribute_report(
            enterprise_id=x_enterprise_id,
            report_id=report_id,
            recipients=[str(r) for r in req.recipients],
            custom_message=req.custom_message,
            triggered_by_user=triggered_by,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReportNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidDistributionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DistributeResponse(
        report_id=summary["report_id"],
        recipient_count=summary["recipient_count"],
        success_count=summary["success_count"],
        failure_count=summary["failure_count"],
        distributions=[DistributionItem(**d) for d in summary["distributions"]],
    )


@router.get(
    "/reports/{report_id}/distributions",
    response_model=DistributionListResponse,
)
async def list_distributions(
    report_id: UUID,
    x_enterprise_id: Annotated[str, Header()],
):
    """List manual distributions for a report, joined with the live
    notification_outbox state (status / attempts / sent_at). Used by
    the FE distribution audit drawer."""
    try:
        rows = await service.list_distributions(
            enterprise_id=x_enterprise_id,
            report_id=report_id,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DistributionListResponse(
        items=[DistributionRow(**r) for r in rows],
    )
