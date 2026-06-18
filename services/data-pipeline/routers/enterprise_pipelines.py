"""
F-022 — Pipeline Run History (Phase 1 close-out, Sprint 1).

Cursor-paginated read over ``pipeline_runs``, scoped per tenant. Pairs
with F-NEW2 SSE (status stream) which is registered on the same router
prefix so the two ship in one PR — see ``status_stream`` below.

Endpoint shape::

    GET /pipelines?cursor=&limit=&status=&from=&to=
    GET /pipelines/{run_id}/events     (SSE — F-NEW2)

K-1 / K-12: tenant comes from the gateway-trusted ``X-Enterprise-ID``
header, never the query string. ``acquire_for_tenant`` (Sprint 0.5)
sets ``app.enterprise_id`` so that, the moment kaori_app drops
BYPASSRLS, the underlying SELECT is also filtered at the row level.

Cursor format (mirrors auth-service WorkspaceService keyset):

    base64url("{iso-8601-utc}|{run_id}")

Keyset on ``(created_at DESC, run_id DESC)`` — the existing index
``idx_pipeline_runs_enterprise (enterprise_id, created_at DESC)``
serves the first page; tie-breaks on run_id keep ordering stable
when several runs share a microsecond timestamp.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse

from ..shared.db import acquire_for_tenant
from ..shared.event_bus import event_bus

log = structlog.get_logger()

router = APIRouter()

DEFAULT_LIMIT = 50
MAX_LIMIT     = 500

# Pipeline lifecycle (002_pipeline.sql:16-20). Kept here so the validator
# can reject typos in ?status= queries without a DB round-trip.
ALLOWED_STATUSES = frozenset({
    "uploading", "bronze_complete", "schema_review",
    "silver_complete", "analyzing", "analysis_complete",
    "failed", "cancelled",
})


# =========================================================================
# Cursor encode / decode
# =========================================================================

def _encode_cursor(created_at: datetime, run_id: UUID) -> str:
    raw = f"{created_at.astimezone(timezone.utc).isoformat()}|{run_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    pad = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + pad).encode("ascii")).decode("utf-8")
        ts_str, run_id_str = decoded.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(run_id_str)
    except Exception as exc:  # malformed → 400
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}")


# =========================================================================
# GET /pipelines  (F-022)
# =========================================================================

@router.get("")
async def list_pipelines(
    request: Request,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor: Optional[str] = Query(None, description="Opaque cursor from prior meta.cursor"),
    limit:  int           = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    status: Optional[str] = Query(None, description="Comma-separated status filter"),
    from_:  Optional[datetime] = Query(None, alias="from", description="ISO-8601 lower bound on created_at"),
    to:     Optional[datetime] = Query(None,                description="ISO-8601 upper bound on created_at"),
):
    """List pipeline runs for the calling tenant, newest first."""

    # ---- validate filters ------------------------------------------------
    status_list: list[str] = []
    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        unknown = [s for s in status_list if s not in ALLOWED_STATUSES]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown status(es): {','.join(unknown)}",
            )

    if from_ and to and from_ > to:
        raise HTTPException(status_code=400, detail="from must be ≤ to")

    # ---- build WHERE + parameters ---------------------------------------
    where_parts = ["enterprise_id = $1"]
    params: list = [x_enterprise_id]

    if cursor:
        cursor_ts, cursor_run = _decode_cursor(cursor)
        # Tuple keyset: rows strictly older than the cursor row, breaking
        # ties on run_id. Indexed scan thanks to (enterprise_id, created_at).
        where_parts.append(
            f"(created_at, run_id) < (${len(params) + 1}, ${len(params) + 2})"
        )
        params.extend([cursor_ts, cursor_run])

    if status_list:
        where_parts.append(f"status = ANY(${len(params) + 1}::text[])")
        params.append(status_list)

    if from_:
        where_parts.append(f"created_at >= ${len(params) + 1}")
        params.append(from_)

    if to:
        where_parts.append(f"created_at <= ${len(params) + 1}")
        params.append(to)

    # Fetch limit+1 so we know whether a next page exists without a COUNT.
    sql = f"""
        SELECT run_id, status, filename, original_size_bytes, mime_type,
               detected_language, sheet_count, row_count_bronze,
               row_count_silver, quality_score, error_message,
               created_at, updated_at
          FROM pipeline_runs
         WHERE {' AND '.join(where_parts)}
         ORDER BY created_at DESC, run_id DESC
         LIMIT ${len(params) + 1}
    """
    params.append(limit + 1)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

    has_more = len(rows) > limit
    page_rows = rows[:limit]

    next_cursor: Optional[str] = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_cursor(last["created_at"], last["run_id"])

    items = [_serialise_row(r) for r in page_rows]

    return {
        "data": items,
        "meta": {
            "cursor":      next_cursor,
            "limit":       limit,
            "count":       len(items),
            "has_more":    has_more,
            "request_id":  _request_id(request),
            "trace_id":    request.headers.get("X-Trace-ID"),
            "server_time": datetime.now(timezone.utc).isoformat(),
        },
    }


# =========================================================================
# GET /pipelines/{run_id}/events  (F-NEW2 — SSE)
# =========================================================================

@router.get("/{run_id}/events")
async def status_stream(
    request: Request,
    run_id: UUID = Path(..., description="Pipeline run UUID"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """Server-Sent Events for a single pipeline run.

    Emits one event per ``pipeline_runs.status`` transition for the run.
    Heartbeats every 15 s as comment lines so reverse proxies (nginx,
    AWS ALB) don't close the idle TCP connection. Browsers reconnect
    automatically with ``Last-Event-ID`` — when present, we replay the
    current row state immediately so the client sees the latest known
    status without having to wait for the next transition.
    """

    # 404 the request before opening the stream if the run isn't ours.
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT run_id, status, updated_at FROM pipeline_runs "
            "WHERE run_id = $1 AND enterprise_id = $2",
            run_id, x_enterprise_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    initial_state = {
        "run_id":     str(row["run_id"]),
        "status":     row["status"],
        "updated_at": row["updated_at"].astimezone(timezone.utc).isoformat()
                       if row["updated_at"] else None,
        "replay":     last_event_id is not None,
    }

    async def _stream() -> AsyncIterator[bytes]:
        # 1) Replay current state so the client immediately knows where it
        #    stands. This covers both the "fresh subscriber" and "reconnect
        #    via Last-Event-ID" paths uniformly.
        yield _format_sse(_event_id(), "status", initial_state)

        # 2) Fan out new events until the client disconnects or the run
        #    enters a terminal state.
        async with event_bus.subscribe(run_id) as queue:
            heartbeat_at = time.monotonic() + 15.0
            while True:
                if await request.is_disconnected():
                    return

                timeout = max(0.1, heartbeat_at - time.monotonic())
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    yield b": heartbeat\n\n"
                    heartbeat_at = time.monotonic() + 15.0
                    continue

                yield _format_sse(_event_id(), "status", payload)
                heartbeat_at = time.monotonic() + 15.0

                # Once the run reaches a terminal state we close the stream
                # cleanly so the browser doesn't keep an idle connection.
                if payload.get("status") in {"analysis_complete", "failed", "cancelled"}:
                    return

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering when in front
            "Connection":     "keep-alive",
        },
    )


# =========================================================================
# Helpers
# =========================================================================

def _serialise_row(row) -> dict:
    return {
        "run_id":              str(row["run_id"]),
        "status":              row["status"],
        "filename":            row["filename"],
        "original_size_bytes": row["original_size_bytes"],
        "mime_type":           row["mime_type"],
        "detected_language":   row["detected_language"],
        "sheet_count":         row["sheet_count"],
        "row_count_bronze":    row["row_count_bronze"],
        "row_count_silver":    row["row_count_silver"],
        "quality_score":       float(row["quality_score"]) if row["quality_score"] is not None else None,
        "error_message":       row["error_message"],
        "created_at":          row["created_at"].astimezone(timezone.utc).isoformat() if row["created_at"] else None,
        "updated_at":          row["updated_at"].astimezone(timezone.utc).isoformat() if row["updated_at"] else None,
    }


def _request_id(request: Request) -> str:
    # Prefer a header set by the gateway; otherwise generate one so the
    # response is still tagged for log correlation.
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


def _event_id() -> str:
    """Per-event ID used in SSE so Last-Event-ID can target replay."""
    return str(uuid.uuid4())


def _format_sse(event_id: str, event: str, data: dict) -> bytes:
    return (
        f"id: {event_id}\n"
        f"event: {event}\n"
        f"data: {json.dumps(data, default=str)}\n\n"
    ).encode("utf-8")
