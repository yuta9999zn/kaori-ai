"""
Sprint 8 chat endpoints — POST /chat/{scope}/stream (SSE).

Two endpoints, one per portal scope. Why path-based scope rather than
a body field: we want a hard URL boundary so a leaked token from a
P2 user can never reach the platform tools, even if the body says
``scope='platform'``. The gateway's existing PUBLIC_PATHS list +
role-aware proxy filter handles the JWT side.

Both endpoints share the same body shape (``ChatRequest``) and the
same SSE envelope (see schemas.SSEEvent). The only difference is the
scope string passed into the agent + the role gate enforced on the
platform path.

Headers expected (set by the API gateway from the JWT):
    X-Enterprise-ID  enterprise scope only — UUID
    X-User-ID        both scopes — UUID (str ok in v0)
    X-Role           both scopes — RBAC role string

Wire format:
    Each SSE event is one ``data: <json>\\n\\n`` block. ``id:`` and
    ``event:`` lines are intentionally NOT used — the FE just decodes
    the payload and dispatches on ``type``. Keeps mocks simple.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional

import structlog
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from .agent import run_tool_loop
from .registry import PLATFORM_ROLES_ALLOWED
from .schemas import ChatRequest, SSEEvent
from .tools.base import ToolContext

log = structlog.get_logger()

router = APIRouter()


# =========================================================================
# POST /chat/enterprise/stream
# =========================================================================

@router.post("/enterprise/stream")
async def chat_enterprise(
    body: ChatRequest,
    x_enterprise_id: str        = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[str] = Header(None, alias="X-User-ID"),
    x_role:          Optional[str] = Header(None, alias="X-User-Role"),
):
    """Enterprise-scoped chat. Tools see ``ctx.enterprise_id`` from the
    gateway-trusted header and run RLS-scoped queries against the
    caller's tenant only."""

    ctx = ToolContext(
        scope="enterprise",
        enterprise_id=x_enterprise_id,
        user_id=x_user_id,
        role=x_role,
    )
    return _sse_response(body, ctx)


# =========================================================================
# POST /chat/platform/stream
# =========================================================================

@router.post("/platform/stream")
async def chat_platform(
    body: ChatRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_role:    Optional[str] = Header(None, alias="X-User-Role"),
):
    """Platform-scoped chat. Cross-tenant queries — gated to platform
    admin roles. The role check happens here AND in the registry, so
    a future endpoint refactor can't accidentally bypass it."""

    if not x_role or x_role not in PLATFORM_ROLES_ALLOWED:
        raise HTTPException(
            status_code=403,
            detail=f"role '{x_role}' is not allowed on /chat/platform/stream",
        )

    ctx = ToolContext(
        scope="platform",
        enterprise_id=None,  # cross-tenant
        user_id=x_user_id,
        role=x_role,
    )
    return _sse_response(body, ctx)


# =========================================================================
# Shared SSE wiring
# =========================================================================

def _sse_response(body: ChatRequest, ctx: ToolContext) -> StreamingResponse:
    """Wrap the agent's event generator in an SSE StreamingResponse.

    Headers force-disable proxy buffering so the FE gets each tool_call
    event the moment it fires (otherwise nginx / cloudflare can hold
    the whole stream until done).
    """
    async def _generate() -> AsyncIterator[bytes]:
        try:
            history = [t.model_dump() for t in body.history]
            async for event in run_tool_loop(
                user_message=body.message,
                history=history,
                ctx=ctx,
            ):
                yield _format_sse(event)
        except asyncio.CancelledError:
            # Client disconnected — stop quietly. Do NOT log as error;
            # users abandoning a chat turn is normal.
            log.info("chat.stream.client_disconnected",
                     scope=ctx.scope, user=ctx.user_id)
            raise
        except Exception as exc:
            # Unexpected failure mid-stream. Emit an error event then
            # close the stream cleanly so the FE can show a banner.
            log.exception("chat.stream.unhandled", error=str(exc))
            yield _format_sse(SSEEvent(
                type="error",
                title="Lỗi không xác định",
                detail="Đã ghi log. Vui lòng thử lại.",
            ))
            yield _format_sse(SSEEvent(type="done"))

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",   # disable nginx response buffering
            "Connection":        "keep-alive",
        },
    )


def _format_sse(event: SSEEvent) -> bytes:
    """One SSE event line. ``data: <json>\\n\\n`` — no ``event:`` /
    ``id:`` per the wire format note in the module docstring."""
    payload = event.model_dump(exclude_none=True)
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
