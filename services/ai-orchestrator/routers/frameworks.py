"""
F-034 Frameworks — HTTP surface.

Three endpoints:

    POST /api/v1/frameworks/generate          202 + run_id (background)
    GET  /api/v1/frameworks                    cursor-paginated list
    GET  /api/v1/frameworks/{run_id}           single + content_json
    GET  /api/v1/frameworks/templates          static registry catalogue

Same routing convention as F-038 reports — flat /api/v1, JWT-trusted
``X-Enterprise-ID`` header for tenant scoping (K-12).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..frameworks import repository, service, templates
from ..frameworks.service import (
    InvalidFrameworkInputError,
    UnknownFrameworkError,
)
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Wire shapes ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    framework_code: str = Field(
        ...,
        description="Built-in framework code: swot / 6w / 2h / fishbone.",
    )
    question: str = Field(
        ...,
        min_length=3, max_length=2000,
        description="The question / hypothesis the framework should structure.",
    )
    source_ref: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional pointer into the data layer (gold feature id, "
                    "analysis_run id, dataset name) for the prompt to ground on.",
    )
    consent_external: bool = Field(
        default=False,
        description="K-4 — must be explicit per call. Default OFF (Qwen local).",
    )


class GenerateResponse(BaseModel):
    run_id: UUID
    status: str = Field(default="queued")


class FrameworkRunListItem(BaseModel):
    """List shape — content_json omitted to keep responses small."""
    run_id:           UUID
    framework_code:   str
    question:         str
    source_ref:       Optional[str] = None
    consent_external: bool
    status:           str
    narrative:        Optional[str] = None
    created_at:       datetime
    completed_at:     Optional[datetime] = None
    last_error:       Optional[str] = None


class FrameworkRunDetail(FrameworkRunListItem):
    content_json: Optional[dict] = None


class FrameworkRunListResponse(BaseModel):
    items: list[FrameworkRunListItem]
    next_cursor: Optional[str] = Field(
        default=None,
        description="Pass back as ``cursor`` query param to fetch the next page.",
    )


class TemplateCatalogueItem(BaseModel):
    code:        str
    name:        str
    description: str


class TemplateCatalogueResponse(BaseModel):
    items: list[TemplateCatalogueItem]


# ─── Endpoints ───────────────────────────────────────────────────

@router.get("/frameworks/templates", response_model=TemplateCatalogueResponse)
async def list_templates_endpoint():
    """Static catalogue of built-in frameworks. Used by the FE hub
    page (file 40-frameworks.tsx) to render the gallery without
    duplicating the registry on the client side."""
    return TemplateCatalogueResponse(items=[
        TemplateCatalogueItem(
            code=t["code"], name=t["name"], description=t["description"],
        )
        for t in templates.REGISTRY.values()
    ])


@router.post(
    "/frameworks/generate",
    response_model=GenerateResponse,
    status_code=202,
)
async def generate(
    req: GenerateRequest,
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[Optional[str], Header()] = None,
):
    """Queue a framework run. Returns 202 + ``run_id``; the actual
    LLM call runs in a background asyncio task. Poll the GET endpoint
    until status='ready' or 'failed'."""
    triggered_by: Optional[UUID] = None
    if x_user_id:
        try:
            triggered_by = UUID(x_user_id)
        except ValueError:
            log.warning("frameworks.generate.bad_x_user_id", value=x_user_id)

    try:
        run_id = await service.queue_framework(
            enterprise_id=x_enterprise_id,
            framework_code=req.framework_code,
            question=req.question,
            source_ref=req.source_ref,
            consent_external=req.consent_external,
            created_by_user=triggered_by,
        )
    except UnknownFrameworkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidFrameworkInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    asyncio.create_task(
        service.run_framework(enterprise_id=x_enterprise_id, run_id=run_id),
        name=f"frameworks-{run_id}",
    )

    return GenerateResponse(run_id=run_id, status="queued")


@router.get("/frameworks", response_model=FrameworkRunListResponse)
async def list_runs(
    x_enterprise_id: Annotated[str, Header()],
    cursor: Annotated[Optional[str], Query(description="Opaque cursor from previous page.")] = None,
    limit:  Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Cursor-paginated list of framework runs for the calling tenant.
    Cursor format: ``<created_at_iso>|<run_id>``."""
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
            cursor_created_at=cursor_ts,
            cursor_run_id=cursor_id,
        )

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last['created_at'].isoformat()}|{last['run_id']}"

    return FrameworkRunListResponse(
        items=[FrameworkRunListItem(**r) for r in items],
        next_cursor=next_cursor,
    )


@router.get("/frameworks/{run_id}", response_model=FrameworkRunDetail)
async def get_run(
    run_id: UUID,
    x_enterprise_id: Annotated[str, Header()],
):
    """Single framework run including content_json. RLS ensures
    cross-tenant requests get 404."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await repository.fetch_run(conn, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="framework run not found")
    return FrameworkRunDetail(**row)
