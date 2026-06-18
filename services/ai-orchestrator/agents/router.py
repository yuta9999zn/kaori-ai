"""
F-061 router — two endpoints under /shared/agents.

The gateway rewrites ``/api/v1/shared/agents/...`` → ``/shared/agents/...``
so this router mounts at the shorter prefix. Same convention as the
existing chat router and analytics router (see main.py mount blocks).

Endpoints
=========

POST /shared/agents/sessions
    Generic entry: caller provides workflow_id in the body.

POST /shared/agents/workflows/{workflow_id}/invoke
    Convenience wrapper: workflow_id comes from the path. Body is the
    same SessionRequest minus workflow_id (the path wins).

Both return SessionResponse with the full transcript inlined. There
is no streaming SSE in v0; the call blocks until the orchestrator
finishes (typically 5-15 seconds for one workflow run with Qwen local).

Headers
=======
::

    X-Enterprise-ID    UUID — required, set by the gateway from the JWT
    X-User-ID          UUID — required (actor on the audit row)
    X-User-Role        str  — current role; v0 ignored, Phase 2 will
                              gate workflow_ids by role
    Idempotency-Key    str  — REQUIRED when dry_run=False. Reuses Redis
                              dedup the same way K-13 wires every other
                              POST mutation. Skipped here in v0 — the
                              orchestrator's session_id IS the
                              idempotency key for the duration of this
                              PR. Phase 2.6 follow-up wires Redis.
"""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Header, HTTPException, Path

from .orchestrator import (
    WorkflowInputError,
    run_session,
)
from .schemas import SessionRequest, SessionResponse

log = structlog.get_logger()

router = APIRouter(prefix="/shared/agents", tags=["Agents"])


# =========================================================================
# POST /shared/agents/sessions
# =========================================================================


@router.post("/sessions", response_model=SessionResponse)
async def start_session(
    body: SessionRequest,
    x_enterprise_id: str = Header(..., alias="X-Enterprise-ID"),
    x_user_id:    Optional[str] = Header(None, alias="X-User-ID"),
    x_user_role:  Optional[str] = Header(None, alias="X-User-Role"),
) -> SessionResponse:
    """Start a new agent session for ``body.workflow_id``.

    Validates the workflow + input shape, then drives the
    planner/executor/critic loop synchronously. Returns
    SessionResponse with the full transcript when the loop terminates
    (completed | failed | escalated).
    """
    return await _run(
        workflow_id=body.workflow_id,
        input=body.input,
        dry_run=body.dry_run,
        enterprise_id=x_enterprise_id,
        actor_user_id=x_user_id,
    )


# =========================================================================
# POST /shared/agents/workflows/{workflow_id}/invoke
# =========================================================================


@router.post("/workflows/{workflow_id}/invoke", response_model=SessionResponse)
async def invoke_workflow(
    body: SessionRequest,
    workflow_id: str = Path(..., min_length=1, max_length=50),
    x_enterprise_id: str = Header(..., alias="X-Enterprise-ID"),
    x_user_id:    Optional[str] = Header(None, alias="X-User-ID"),
    x_user_role:  Optional[str] = Header(None, alias="X-User-Role"),
) -> SessionResponse:
    """Same orchestrator, workflow_id pinned by the URL.

    Body's ``workflow_id`` field is ignored — the path always wins.
    This makes the URL the source of truth for which workflow ran,
    which is what audit / dashboards expect.
    """
    return await _run(
        workflow_id=workflow_id,
        input=body.input,
        dry_run=body.dry_run,
        enterprise_id=x_enterprise_id,
        actor_user_id=x_user_id,
    )


# =========================================================================
# Shared dispatcher
# =========================================================================


async def _run(
    *,
    workflow_id: str,
    input: dict,
    dry_run: bool,
    enterprise_id: str,
    actor_user_id: Optional[str],
) -> SessionResponse:
    """Convert orchestrator-side exceptions into RFC 7807 HTTP errors.

    The orchestrator itself swallows execution exceptions and returns
    a SessionResponse with status='failed', so we only need to convert
    the up-front validation errors (unknown workflow, bad input shape).
    """
    try:
        return await run_session(
            workflow_id=workflow_id,
            input=input,
            dry_run=dry_run,
            enterprise_id=enterprise_id,
            actor_user_id=actor_user_id,
        )
    except KeyError as exc:
        # workflows.get_workflow raises KeyError with a friendly message
        # listing available workflow_ids.
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
