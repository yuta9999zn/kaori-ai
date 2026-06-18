"""
DLQ recovery console — P1 of Phase 2.7 (anh's review §2D + §2 runtime
"DLQ orchestration").

Pre-2.7 dead/failed items were scattered across multiple tables:
  - notification_outbox.status='dead'
  - workflow_chat_outbox.status='dead'
  - workflow_runs.status='failed'
  - workflow_email_intake.status='rejected'
  - workflow_webhook_intake.status='rejected'

Ops had no single place to see what's stuck + no API to retry / skip /
replay. This router exposes admin endpoints that unify the view:

  GET    /admin/dlq                                      — counts per source
  GET    /admin/dlq/{source}                             — list dead rows
  POST   /admin/dlq/notification/{outbox_id}/retry       — flip dead→pending
  POST   /admin/dlq/chat/{outbox_id}/retry               — same for chat
  POST   /admin/dlq/run/{run_id}/replay                  — re-fire workflow run
  POST   /admin/dlq/intake/{kind}/{id}/requeue           — flip rejected→pending

K-1 / K-12: every read scoped by enterprise_id from JWT header. Admin
authz gated by X-User-Role in {SUPER_ADMIN, ADMIN}.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path, Query
from pydantic import BaseModel

from ai_orchestrator.shared.db import acquire_for_tenant

log = structlog.get_logger()
router = APIRouter()


# ─── Shared shapes ───────────────────────────────────────────────


class DlqSummaryOut(BaseModel):
    source:        str
    dead_count:    int
    sample_row:    Optional[dict[str, Any]] = None


class DlqOverviewOut(BaseModel):
    sources:    list[DlqSummaryOut]
    total:      int


class DlqItemOut(BaseModel):
    source:        str
    id:            str
    created_at:    str
    error_summary: Optional[str] = None
    payload:       dict[str, Any]


def _require_admin(role: Optional[str]) -> None:
    if role not in ("SUPER_ADMIN", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail=f"DLQ console requires SUPER_ADMIN or ADMIN role; got {role!r}",
        )


# K-13 helpers — Phase 2.9 closeout. Wire Idempotency-Key header on
# all 5 ops endpoints (retry/replay/requeue/discard) so a double-click
# from the ops dashboard doesn't re-fire the underlying side effect.
# Cached responses live 24h in workflow_idempotency_records (mig 095).
async def _idempotency_short_circuit(
    enterprise_id: UUID,
    idempotency_key: Optional[str],
    side_effect_class: str = "external",
) -> Optional[dict[str, Any]]:
    """Return cached response_payload dict if duplicate Idempotency-Key,
    else None (caller proceeds + records outcome at end).

    Guard: when caller invokes the handler directly (not via FastAPI
    HTTP route), the parameter receives the Header() default object
    instead of None — isinstance check rules that out.
    """
    if not isinstance(idempotency_key, str) or not idempotency_key:
        return None
    from ..workflow_runtime.idempotency_store import get_or_set
    hit = await get_or_set(
        enterprise_id=enterprise_id, key=idempotency_key,
        side_effect_class=side_effect_class, ttl_seconds=86_400,
    )
    return hit.response_payload if hit.cached else None


async def _record_idempotency_outcome(
    enterprise_id: UUID,
    idempotency_key: Optional[str],
    response: dict[str, Any],
) -> None:
    """Persist response_payload after side effect completes. No-op when
    no Idempotency-Key provided (legacy callers stay unchanged)."""
    if not isinstance(idempotency_key, str) or not idempotency_key:
        return
    from ..workflow_runtime.idempotency_store import record_outcome
    await record_outcome(
        enterprise_id=enterprise_id, key=idempotency_key,
        response_payload=response,
    )


# ─── Overview ────────────────────────────────────────────────────


@router.get("/admin/dlq", response_model=DlqOverviewOut)
async def dlq_overview(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
):
    """Per-source dead/failed counts. Op uses this as a dashboard."""
    _require_admin(x_user_role)

    summaries: list[DlqSummaryOut] = []
    async with acquire_for_tenant(x_enterprise_id) as conn:
        for source, sql in (
            ("notification_outbox",
             "SELECT COUNT(*) AS n FROM notification_outbox WHERE status = 'dead'"),
            ("workflow_chat_outbox",
             "SELECT COUNT(*) AS n FROM workflow_chat_outbox WHERE status = 'dead'"),
            ("workflow_runs",
             "SELECT COUNT(*) AS n FROM workflow_runs WHERE status = 'failed'"),
            ("workflow_email_intake",
             "SELECT COUNT(*) AS n FROM workflow_email_intake WHERE status = 'rejected'"),
            ("workflow_webhook_intake",
             "SELECT COUNT(*) AS n FROM workflow_webhook_intake WHERE status = 'rejected'"),
        ):
            row = await conn.fetchrow(sql)
            count = row["n"] if row else 0
            summaries.append(DlqSummaryOut(source=source, dead_count=count))

    total = sum(s.dead_count for s in summaries)
    return DlqOverviewOut(sources=summaries, total=total)


# ─── Per-source listings ─────────────────────────────────────────


@router.get("/admin/dlq/{source}", response_model=list[DlqItemOut])
async def list_dlq_items(
    source:          str = Path(..., max_length=64),
    limit:           int = Query(default=50, ge=1, le=500),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
):
    _require_admin(x_user_role)

    if source not in ("notification_outbox", "workflow_chat_outbox",
                       "workflow_runs", "workflow_email_intake",
                       "workflow_webhook_intake"):
        raise HTTPException(status_code=404,
                              detail=f"Unknown DLQ source {source!r}")

    items: list[DlqItemOut] = []
    async with acquire_for_tenant(x_enterprise_id) as conn:
        if source == "notification_outbox":
            rows = await conn.fetch(
                "SELECT outbox_id, created_at, last_error, recipient_email, "
                "       template, attempts FROM notification_outbox "
                "WHERE status = 'dead' ORDER BY created_at DESC LIMIT $1",
                limit,
            )
            for r in rows:
                items.append(DlqItemOut(
                    source=source, id=str(r["outbox_id"]),
                    created_at=r["created_at"].isoformat(),
                    error_summary=r["last_error"],
                    payload={"recipient": r["recipient_email"],
                              "template": r["template"],
                              "attempts": r["attempts"]},
                ))
        elif source == "workflow_chat_outbox":
            rows = await conn.fetch(
                "SELECT outbox_id, created_at, last_error, channel, target, attempts "
                "FROM workflow_chat_outbox WHERE status = 'dead' "
                "ORDER BY created_at DESC LIMIT $1",
                limit,
            )
            for r in rows:
                items.append(DlqItemOut(
                    source=source, id=str(r["outbox_id"]),
                    created_at=r["created_at"].isoformat(),
                    error_summary=r["last_error"],
                    payload={"channel": r["channel"],
                              "target": r["target"],
                              "attempts": r["attempts"]},
                ))
        elif source == "workflow_runs":
            rows = await conn.fetch(
                "SELECT run_id, started_at, ended_at, error_summary, "
                "       workflow_id, trigger_source "
                "FROM workflow_runs WHERE status = 'failed' "
                "ORDER BY started_at DESC LIMIT $1",
                limit,
            )
            for r in rows:
                items.append(DlqItemOut(
                    source=source, id=str(r["run_id"]),
                    created_at=r["started_at"].isoformat(),
                    error_summary=r["error_summary"],
                    payload={"workflow_id": str(r["workflow_id"]),
                              "trigger_source": r["trigger_source"],
                              "ended_at": (r["ended_at"].isoformat()
                                           if r["ended_at"] else None)},
                ))
        elif source == "workflow_email_intake":
            rows = await conn.fetch(
                "SELECT email_id, received_at, queue_key, sender, subject "
                "FROM workflow_email_intake WHERE status = 'rejected' "
                "ORDER BY received_at DESC LIMIT $1",
                limit,
            )
            for r in rows:
                items.append(DlqItemOut(
                    source=source, id=str(r["email_id"]),
                    created_at=r["received_at"].isoformat(),
                    payload={"queue_key": r["queue_key"],
                              "sender": r["sender"],
                              "subject": r["subject"]},
                ))
        else:  # workflow_webhook_intake
            rows = await conn.fetch(
                "SELECT webhook_id, received_at, queue_key, source, external_event_id "
                "FROM workflow_webhook_intake WHERE status = 'rejected' "
                "ORDER BY received_at DESC LIMIT $1",
                limit,
            )
            for r in rows:
                items.append(DlqItemOut(
                    source=source, id=str(r["webhook_id"]),
                    created_at=r["received_at"].isoformat(),
                    payload={"queue_key": r["queue_key"],
                              "source": r["source"],
                              "external_event_id": r["external_event_id"]},
                ))

    log.info("dlq.listed", source=source, count=len(items),
              enterprise_id=str(x_enterprise_id))
    return items


# ─── Retry / requeue / replay actions ────────────────────────────


class DlqActionOut(BaseModel):
    action:    str
    source:    str
    target_id: str
    success:   bool
    detail:    str


@router.post("/admin/dlq/notification/{outbox_id}/retry",
              response_model=DlqActionOut)
async def retry_notification(
    outbox_id:       UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Flip dead → pending so the poller picks it back up.

    K-13: pass Idempotency-Key header; double-click from ops dashboard
    returns the original response instead of re-flipping a row that
    has since changed status.
    """
    _require_admin(x_user_role)

    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key)
    if cached is not None:
        return DlqActionOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "UPDATE notification_outbox "
            "SET status = 'pending', attempts = 0, last_error = NULL "
            "WHERE outbox_id = $1 AND status = 'dead'",
            outbox_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    if rows == 0:
        raise HTTPException(status_code=404,
                              detail="No dead row matched outbox_id")
    log.info("dlq.notification.retried",
              outbox_id=str(outbox_id), enterprise_id=str(x_enterprise_id))
    out = DlqActionOut(action="retry", source="notification_outbox",
                          target_id=str(outbox_id), success=True,
                          detail=f"reset {rows} row(s) to pending")
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.post("/admin/dlq/chat/{outbox_id}/retry",
              response_model=DlqActionOut)
async def retry_chat(
    outbox_id:       UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    _require_admin(x_user_role)

    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key)
    if cached is not None:
        return DlqActionOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "UPDATE workflow_chat_outbox "
            "SET status = 'pending', attempts = 0, last_error = NULL "
            "WHERE outbox_id = $1 AND status = 'dead'",
            outbox_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    if rows == 0:
        raise HTTPException(status_code=404,
                              detail="No dead row matched outbox_id")
    out = DlqActionOut(action="retry", source="workflow_chat_outbox",
                          target_id=str(outbox_id), success=True,
                          detail=f"reset {rows} row(s) to pending")
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.post("/admin/dlq/run/{run_id}/replay",
              response_model=DlqActionOut)
async def replay_workflow_run(
    background_tasks: BackgroundTasks,
    run_id:          UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(default=None, alias="X-User-ID"),
    x_user_role:     Optional[str]  = Header(default=None, alias="X-User-Role"),
    idempotency_key: Optional[str]  = Header(default=None, alias="Idempotency-Key"),
):
    """Resume a failed run from where it stopped. The runner's resume-aware
    loop preloads completed node outputs + skips them; only failed/pending
    nodes re-execute. Idempotent — repeated calls are no-ops if run is
    already running or completed.

    K-13: Idempotency-Key header dedupes double-click; first call records
    409 outcome in ledger; subsequent calls within 24h return cached 409
    so background replay only schedules once per click.
    """
    _require_admin(x_user_role)

    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key)
    if cached is not None:
        return DlqActionOut(**cached)

    # Reset run status to running so the state machine accepts the resume
    from workflow_runtime.runner import run_in_background

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT status FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="run not found")
        if row["status"] != "failed":
            raise HTTPException(
                status_code=409,
                detail=f"run status={row['status']!r}, only 'failed' can be replayed",
            )
        # Manually transition failed → running (not in standard graph;
        # admin replay is the explicit recovery path the state machine
        # carves out).
        await conn.execute(
            "UPDATE workflow_runs SET status = 'running', "
            "    error_summary = NULL, ended_at = NULL "
            "WHERE run_id = $1",
            run_id,
        )

    background_tasks.add_task(
        run_in_background,
        run_id=run_id,
        enterprise_id=x_enterprise_id,
        user_id=x_user_id,
    )
    log.info("dlq.run.replayed",
              run_id=str(run_id),
              enterprise_id=str(x_enterprise_id),
              actor=str(x_user_id) if x_user_id else None)
    out = DlqActionOut(
        action="replay", source="workflow_runs",
        target_id=str(run_id), success=True,
        detail="run flipped to 'running'; resume scheduled in background",
    )
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.post("/admin/dlq/intake/{kind}/{intake_id}/requeue",
              response_model=DlqActionOut)
async def requeue_intake(
    kind:            str = Path(..., max_length=16),
    intake_id:       UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Flip a rejected intake row back to pending for re-claim.

    K-13: Idempotency-Key dedupes double-click. Without it a second
    requeue could land while the row is mid-claim, racing the claimant.
    """
    _require_admin(x_user_role)

    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key)
    if cached is not None:
        return DlqActionOut(**cached)

    if kind == "email":
        table, id_col = "workflow_email_intake", "email_id"
    elif kind == "webhook":
        table, id_col = "workflow_webhook_intake", "webhook_id"
    else:
        raise HTTPException(status_code=404,
                              detail=f"Unknown intake kind {kind!r} (expected email|webhook)")

    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            f"UPDATE {table} SET status = 'pending', consumed_at = NULL, "
            f"    consumed_by_run_id = NULL "
            f"WHERE {id_col} = $1 AND status = 'rejected'",
            intake_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    if rows == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No rejected row matched {kind} intake {intake_id}",
        )
    out = DlqActionOut(action="requeue", source=table,
                          target_id=str(intake_id), success=True,
                          detail=f"reset {rows} row(s) to pending")
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.post("/admin/dlq/notification/{outbox_id}/discard",
              response_model=DlqActionOut)
async def discard_notification(
    outbox_id:       UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Permanently drop a dead notification — no retry. Caller's explicit
    decision (record in audit log).

    K-13: discard is destructive; Idempotency-Key prevents a double-click
    from deleting one row then 404-ing on the second call.
    """
    _require_admin(x_user_role)

    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key)
    if cached is not None:
        return DlqActionOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "DELETE FROM notification_outbox WHERE outbox_id = $1 AND status = 'dead'",
            outbox_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    if rows == 0:
        raise HTTPException(status_code=404, detail="No dead row matched")
    log.warning("dlq.notification.discarded",
                  outbox_id=str(outbox_id),
                  enterprise_id=str(x_enterprise_id))
    out = DlqActionOut(action="discard", source="notification_outbox",
                          target_id=str(outbox_id), success=True,
                          detail=f"deleted {rows} row(s) permanently")
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out
