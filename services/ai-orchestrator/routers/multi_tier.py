"""
F-033 Multi-tier Analysis — HTTP surface (PR A + PR B).

Endpoints (default /api/v1 prefix per PHASE2_PLAN §1 decision #2):

    GET  /api/v1/analysis/sources?layer=silver,gold       picker catalogue
    GET  /api/v1/analysis/cross-workspaces                 user's reachable workspaces
    GET  /api/v1/analysis/quota/external-ai                external-LLM month-to-date count
    POST /api/v1/analysis/runs                              start a tier run
    POST /api/v1/analysis/runs/{run_id}/approve            MANAGER approves a pending advanced run
    GET  /api/v1/analysis/runs                              cursor list
    GET  /api/v1/analysis/runs/{run_id}                     full detail

Same JWT-trusted X-Enterprise-ID header pattern as F-034 frameworks
(K-12 — never accept tenant via query string). The /approve endpoint
also enforces X-Role=MANAGER as a defence-in-depth check on top of the
gateway-side filter.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..multi_tier import repository, service
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Wire shapes ─────────────────────────────────────────────────


class SourceItem(BaseModel):
    id:        str
    label:     str
    layer:     str = Field(..., pattern="^(silver|gold)$")
    row_count: int = 0


class SourcesResponse(BaseModel):
    items: list[SourceItem]
    # Degraded-envelope (tenet 13): layers that failed to list are named
    # here instead of 500-ing the whole picker. Additive — FE may ignore.
    warnings: list[str] = []


class WorkspaceItem(BaseModel):
    id:           str
    name:         str
    can_include:  bool
    member_role:  str


class WorkspacesResponse(BaseModel):
    items: list[WorkspaceItem]


class ExternalQuotaResponse(BaseModel):
    external_calls_used:  int
    external_calls_limit: int
    period:               str = Field(..., description="Billing period this quota covers, e.g. '2026-05'.")


class SourceRef(BaseModel):
    """One entry in `source_ids` for intermediate tier."""
    layer: str = Field(..., pattern="^(silver|gold)$")
    id:    str = Field(..., min_length=1, max_length=200)
    label: Optional[str] = Field(default=None, max_length=200)


class RunCreateRequest(BaseModel):
    """Tier-aware union shape — service layer validates per tier."""
    tier:      str = Field(..., pattern="^(basic|intermediate|advanced)$")
    question:  Optional[str] = Field(default=None, max_length=2000)
    consent_external: bool = False

    # Basic-only fields
    pipeline_run_id: Optional[UUID] = None
    templates:       Optional[list[str]] = None
    config:          Optional[dict] = None

    # Intermediate + advanced fields
    framework:    Optional[str] = Field(default=None, pattern="^(swot|6w|2h|fishbone)$")
    source_ids:   Optional[list[SourceRef]] = None

    # Advanced-only — list of workspace UUIDs the cohort should span.
    # PR B "lite" only honours the calling workspace; PR D (when multi-
    # workspace memberships ship) reads this list for real.
    workspace_ids: Optional[list[UUID]] = None


class RunCreateResponse(BaseModel):
    run_id: UUID
    tier:   str
    status: str = "queued"


class RunListItem(BaseModel):
    id:               UUID
    pipeline_run_id:  Optional[UUID] = None
    tier:             str
    scope:            str
    framework:        Optional[str] = None
    question:         Optional[str] = None
    source_ids:       Optional[list[dict]] = None
    consent_external: bool
    status:           str
    narrative:        Optional[str] = None
    started_at:       Optional[datetime] = None
    completed_at:     Optional[datetime] = None
    created_by_user:  Optional[UUID] = None
    created_at:       datetime


class RunDetail(RunListItem):
    templates:       list[str] = []
    config:          dict = {}
    workspace_ids:   list[UUID] = []
    requires_approval: bool = False
    approved_by:     Optional[UUID] = None
    approved_at:     Optional[datetime] = None
    overview:        Optional[dict] = None
    output_schema_repaired: Optional[bool] = None


class RunListResponse(BaseModel):
    items:       list[RunListItem]
    next_cursor: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/analysis/sources", response_model=SourcesResponse)
async def list_sources(
    x_enterprise_id: Annotated[str, Header()],
    layer: Annotated[
        str,
        Query(description="Comma-separated layers — silver, gold, or both. Default: silver,gold."),
    ] = "silver,gold",
):
    """Picker catalogue for the intermediate tier left pane. Layer
    filter is FE-driven so users can scope to silver or gold only."""
    layers = {part.strip() for part in layer.split(",") if part.strip()}
    if not layers <= {"silver", "gold"}:
        raise HTTPException(status_code=400, detail="layer must be 'silver', 'gold', or both")

    items: list[dict] = []
    warnings: list[str] = []
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Per-layer degrade (tenet 13): one layer's schema drift must not
        # blank the whole picker (incident 2026-07-10 — pilot's wide
        # gold_features 500'd the endpoint while silver was fine).
        if "silver" in layers:
            try:
                items.extend(await repository.list_silver_sources(conn))
            except Exception as exc:  # noqa: BLE001
                log.error("analysis.sources.layer_failed", layer="silver", error=str(exc))
                warnings.append("silver layer unavailable")
        if "gold" in layers:
            try:
                items.extend(await repository.list_gold_sources(conn))
            except Exception as exc:  # noqa: BLE001
                log.error("analysis.sources.layer_failed", layer="gold", error=str(exc))
                warnings.append("gold layer unavailable")

    return SourcesResponse(items=[SourceItem(**i) for i in items], warnings=warnings)


@router.get("/analysis/cross-workspaces", response_model=WorkspacesResponse)
async def list_cross_workspaces(
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[Optional[str], Header()] = None,
    x_role:    Annotated[Optional[str], Header()] = None,
):
    """Workspaces the calling user can include in a cross-cohort.

    PR B "lite" honours the Phase 1 model — one user belongs to exactly
    one enterprise — so this returns a single-item list with the user's
    real role from the JWT claims. When `user_workspace_memberships`
    lands (PR D), this query expands to walk every membership the user
    has ANALYST+ on.
    """
    role = (x_role or "VIEWER").upper()
    return WorkspacesResponse(items=[
        WorkspaceItem(
            id=x_enterprise_id,
            name="(workspace hiện tại)",
            can_include=role in {"MANAGER", "ANALYST"},
            member_role=role,
        ),
    ])


@router.get("/analysis/quota/external-ai", response_model=ExternalQuotaResponse)
async def get_external_quota(
    x_enterprise_id: Annotated[str, Header()],
):
    """Real external-AI call quota for the current month — counts
    every ``decision_audit_log`` row tagged ``llm_provider != qwen-internal``
    since the first of the month. Limit is hardcoded to 100 in PR B
    (Phase 1 plans table doesn't carry the field yet — F-067 wires it).
    """
    today = datetime.utcnow()
    period_start = datetime(today.year, today.month, 1)
    period = f"{today.year:04d}-{today.month:02d}"

    async with acquire_for_tenant(x_enterprise_id) as conn:
        used = await repository.fetch_external_ai_usage(
            conn,
            enterprise_id=UUID(x_enterprise_id),
            period_start=period_start,
        )

    return ExternalQuotaResponse(
        external_calls_used=used,
        external_calls_limit=100,
        period=period,
    )


@router.post(
    "/analysis/runs/{run_id}/approve",
    response_model=RunDetail,
)
async def approve_run_endpoint(
    run_id: UUID,
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[str, Header()],
    x_role:    Annotated[Optional[str], Header()] = None,
):
    """Approve a pending advanced-tier run. MANAGER role required —
    the JWT enforcement at the gateway already restricts the path,
    but we double-check here so a misconfigured filter can't slip
    a non-MANAGER through to a privacy-sensitive dispatch."""
    if (x_role or "").upper() != "MANAGER":
        raise HTTPException(
            status_code=403,
            detail="Only MANAGER can approve advanced runs",
        )

    try:
        approver = UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-User-Id") from exc

    flipped = await service.approve(
        enterprise_id=x_enterprise_id,
        run_id=run_id,
        approver_user_id=approver,
    )
    if not flipped:
        # Either the row doesn't exist for this tenant (RLS prunes it)
        # OR it's not in pending-approval state. We can't tell from the
        # caller's POV — the security-correct answer is 404 in both
        # cases (don't leak existence of out-of-state rows).
        raise HTTPException(status_code=404, detail="Run not found or already actioned")

    # Spawn dispatcher — approval flipped the gate.
    asyncio.create_task(
        service.run_advanced(enterprise_id=x_enterprise_id, run_id=run_id),
        name=f"multi-tier-advanced-approved-{run_id}",
    )

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await repository.fetch_run(conn, run_id)
    if row is None:
        # Should never happen — we just approved it.
        raise HTTPException(status_code=500, detail="Run vanished after approval")
    return RunDetail(**row)


@router.post(
    "/analysis/runs",
    response_model=RunCreateResponse,
    status_code=202,
)
async def create_run(
    req: RunCreateRequest,
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[Optional[str], Header()] = None,
):
    """Queue a tier run + spawn the background dispatcher. Returns 202
    + run_id; the FE polls the GET endpoint until status='done' or
    'error'."""
    triggered_by: Optional[UUID] = None
    if x_user_id:
        try:
            triggered_by = UUID(x_user_id)
        except ValueError:
            log.warning("multi_tier.create.bad_x_user_id", value=x_user_id)

    try:
        if req.tier == "advanced":
            if not req.framework:
                raise HTTPException(
                    status_code=400,
                    detail="framework is required for tier='advanced'",
                )
            if not req.question:
                raise HTTPException(
                    status_code=400,
                    detail="question is required for tier='advanced'",
                )
            if not req.source_ids or len(req.source_ids) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="source_ids must contain at least 2 sources for tier='advanced'",
                )
            if not req.consent_external:
                raise HTTPException(
                    status_code=400,
                    detail="tier='advanced' requires consent_external=true (K-4)",
                )
            queue_result = await service.queue_advanced(
                enterprise_id=x_enterprise_id,
                framework=req.framework,
                question=req.question,
                source_ids=[s.model_dump() for s in req.source_ids],
                workspace_ids=[str(w) for w in (req.workspace_ids or [])],
                consent_external=req.consent_external,
                created_by_user=triggered_by,
            )
            run_id = queue_result["run_id"]
            requires_approval = queue_result["requires_approval"]

            # When approval is required, the dispatcher would short-
            # circuit anyway — but kicking the task is cheap and lets
            # the caller see a `running` flip if approval comes in
            # while the task is still pending.
            if not requires_approval:
                asyncio.create_task(
                    service.run_advanced(enterprise_id=x_enterprise_id, run_id=run_id),
                    name=f"multi-tier-advanced-{run_id}",
                )
            return RunCreateResponse(
                run_id=run_id,
                tier="advanced",
                status="awaiting_approval" if requires_approval else "queued",
            )

        if req.tier == "basic":
            if req.pipeline_run_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="pipeline_run_id is required for tier='basic'",
                )
            if not req.templates:
                raise HTTPException(
                    status_code=400,
                    detail="templates is required for tier='basic'",
                )
            run_id = await service.queue_basic(
                enterprise_id=x_enterprise_id,
                pipeline_run_id=req.pipeline_run_id,
                templates_=req.templates,
                question=req.question,
                config=req.config,
                consent_external=req.consent_external,
                created_by_user=triggered_by,
            )
            asyncio.create_task(
                service.run_basic(enterprise_id=x_enterprise_id, run_id=run_id),
                name=f"multi-tier-basic-{run_id}",
            )
            return RunCreateResponse(run_id=run_id, tier="basic")

        # intermediate
        if not req.framework:
            raise HTTPException(
                status_code=400,
                detail="framework is required for tier='intermediate'",
            )
        if not req.question:
            raise HTTPException(
                status_code=400,
                detail="question is required for tier='intermediate'",
            )
        if not req.source_ids or len(req.source_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="source_ids must contain at least 2 sources for tier='intermediate'",
            )
        run_id = await service.queue_intermediate(
            enterprise_id=x_enterprise_id,
            framework=req.framework,
            question=req.question,
            source_ids=[s.model_dump() for s in req.source_ids],
            consent_external=req.consent_external,
            created_by_user=triggered_by,
        )
        asyncio.create_task(
            service.run_intermediate(enterprise_id=x_enterprise_id, run_id=run_id),
            name=f"multi-tier-intermediate-{run_id}",
        )
        return RunCreateResponse(run_id=run_id, tier="intermediate")

    except service.InvalidRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/analysis/runs", response_model=RunListResponse)
async def list_runs(
    x_enterprise_id: Annotated[str, Header()],
    tier: Annotated[
        Optional[str],
        Query(pattern="^(basic|intermediate|advanced)$"),
    ] = None,
    cursor: Annotated[Optional[str], Query(description="Opaque cursor from previous page.")] = None,
    limit:  Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Cursor-paginated list. Cursor format: ``<created_at_iso>|<run_id>``."""
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
        rows = await repository.list_runs(
            conn,
            limit=limit + 1,
            tier=tier,
            cursor_created_at=cursor_ts,
            cursor_run_id=cursor_id,
        )

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last['created_at'].isoformat()}|{last['id']}"

    return RunListResponse(
        items=[RunListItem(**r) for r in items],
        next_cursor=next_cursor,
    )


@router.get("/analysis/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: UUID,
    x_enterprise_id: Annotated[str, Header()],
):
    """Single tier run including overview / templates / config. RLS
    ensures cross-tenant requests get 404."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await repository.fetch_run(conn, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return RunDetail(**row)
