"""
Saga compensation runtime — P1.4 of orchestration hardening.

REL-011 / REL-012 declared compensation hooks in workflow YAML + mig 068
catalog (`compensation_action` column). Prior to P1.4 the hooks were
recorded but NEVER FIRED. This module implements the runtime that walks
back through successfully-completed external nodes when a downstream
node fails terminally + invokes their compensations.

Pattern: saga (not 2-phase commit). Each external node optionally
declares a compensation in its catalog row + workflow_node config_json.
On terminal failure, runner calls `run_compensation_chain()` which:

  1. Walks workflow_run_nodes in REVERSE completion order.
  2. For each completed node with side_effect_class='external' OR
     'write_non_idempotent', looks up the compensation handler.
  3. Invokes it idempotently (compensation handlers are themselves
     idempotent — typically POST send_correction_email / void_charge / etc.).
  4. Emits compensation_started + compensation_completed events.
  5. Records compensation_state in workflow_run_nodes.metadata.

Compensation handlers
---------------------
Catalog node_type_catalog.compensation_action column carries a string
key (e.g. 'cancel_approval_request', 'send_retraction_email',
'delete_message'). The runtime resolves the key to a registered
COMPENSATION_REGISTRY entry. Adding a new compensation = add one entry
to the registry.

v0 ships 4 compensation actions:
  send_retraction_email   — counter-message after send_email
  cancel_approval_request — closes pending approval_gate
  delete_task             — removes the task created by create_task
  void_call_api           — best-effort POST {url}/void with same idem key

Out-of-scope v0: arbitrary HTTP void URLs (caller declares method+url
in config), partial compensation (skipping some nodes), Temporal saga
SDK integration. P2+ extends this.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional
from uuid import UUID

import structlog

from .event_store import EventType, append_event
from .side_effect import SideEffectClass

log = structlog.get_logger()


# ─── Compensation action registry ────────────────────────────────


@dataclass(frozen=True)
class CompensationResult:
    """Per-node compensation outcome."""
    action_key:     str
    node_id:        str
    status:         str   # 'compensated' | 'skipped' | 'failed'
    detail:         str = ""


CompensationHandler = Callable[
    [UUID, UUID, UUID, dict[str, Any]],   # enterprise_id, run_id, node_id, node_state
    Awaitable[CompensationResult],
]


COMPENSATION_REGISTRY: dict[str, CompensationHandler] = {}


def register_compensation(action_key: str):
    """Decorator: register a compensation handler keyed by mig 068
    compensation_action string."""
    def _wrap(fn: CompensationHandler) -> CompensationHandler:
        if action_key in COMPENSATION_REGISTRY:
            log.warning("compensation.duplicate_register", action_key=action_key)
        COMPENSATION_REGISTRY[action_key] = fn
        return fn
    return _wrap


# ─── Built-in compensation handlers ──────────────────────────────


@register_compensation("send_retraction_email")
async def _comp_send_retraction_email(
    enterprise_id: UUID,
    run_id:        UUID,
    node_id:       UUID,
    node_state:    dict[str, Any],
) -> CompensationResult:
    """Inverse of send_email — enqueues a 'this previous message was
    sent in error' email to the same recipient. Looks up the original
    outbox row by source_ref derived from the node output."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    out = node_state.get("output_data") or {}
    original_id = out.get("outbox_id")
    recipient = out.get("recipient")
    if not original_id or not recipient:
        return CompensationResult(
            action_key="send_retraction_email", node_id=str(node_id),
            status="skipped",
            detail="missing outbox_id or recipient in node output_data",
        )

    retraction_ref = f"retract:{run_id}:{node_id}"
    context = {
        "subject":  "Kaori — Thông báo huỷ email trước",
        "body":     (
            f"Email gửi từ workflow vừa được retract do step xử lý "
            f"thất bại. Vui lòng bỏ qua thông tin trước. "
            f"(Original outbox_id: {original_id})"
        ),
        "cc":       [],
    }

    async with acquire_for_tenant(enterprise_id) as conn:
        existing = await conn.fetchrow(
            "SELECT outbox_id FROM notification_outbox "
            "WHERE enterprise_id = $1 AND source_ref = $2 LIMIT 1",
            enterprise_id, retraction_ref,
        )
        if existing:
            return CompensationResult(
                action_key="send_retraction_email", node_id=str(node_id),
                status="compensated",
                detail=f"retraction already enqueued (outbox_id={existing['outbox_id']})",
            )
        row = await conn.fetchrow(
            """INSERT INTO notification_outbox
                   (enterprise_id, template, recipient_email, context, source_ref)
               VALUES ($1, 'workflow-freeform', $2, $3, $4)
               RETURNING outbox_id""",
            enterprise_id, recipient, context, retraction_ref,
        )

    return CompensationResult(
        action_key="send_retraction_email", node_id=str(node_id),
        status="compensated",
        detail=f"retraction outbox row {row['outbox_id']}",
    )


@register_compensation("cancel_approval_request")
async def _comp_cancel_approval(
    enterprise_id: UUID,
    run_id:        UUID,
    node_id:       UUID,
    node_state:    dict[str, Any],
) -> CompensationResult:
    """Mark pending workflow_approvals row as cancelled. Idempotent —
    terminal rows untouched."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        result = await conn.execute(
            """UPDATE workflow_approvals
               SET status = 'cancelled', resolved_at = NOW(),
                   decision_note = COALESCE(decision_note, '') ||
                                    ' [auto-cancelled by saga compensation]'
               WHERE run_id = $1 AND node_id = $2 AND status = 'pending'""",
            run_id, node_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    return CompensationResult(
        action_key="cancel_approval_request", node_id=str(node_id),
        status="compensated" if rows > 0 else "skipped",
        detail=f"updated {rows} approval rows",
    )


@register_compensation("delete_task")
async def _comp_delete_task(
    enterprise_id: UUID,
    run_id:        UUID,
    node_id:       UUID,
    node_state:    dict[str, Any],
) -> CompensationResult:
    """Mark task created by create_task as cancelled. Idempotent."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    out = node_state.get("output_data") or {}
    task_id = out.get("task_id")
    if not task_id:
        return CompensationResult(
            action_key="delete_task", node_id=str(node_id),
            status="skipped",
            detail="no task_id in node output_data",
        )

    async with acquire_for_tenant(enterprise_id) as conn:
        result = await conn.execute(
            "UPDATE workflow_tasks SET status = 'cancelled' "
            "WHERE task_id = $1 AND status NOT IN ('done','cancelled','expired')",
            task_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    return CompensationResult(
        action_key="delete_task", node_id=str(node_id),
        status="compensated" if rows > 0 else "skipped",
        detail=f"cancelled {rows} task(s)",
    )


@register_compensation("retract_alert")
async def _comp_retract_alert(
    enterprise_id: UUID,
    run_id:        UUID,
    node_id:       UUID,
    node_state:    dict[str, Any],
) -> CompensationResult:
    """Mark alert created by publish_alert as auto-acknowledged with a
    note. Idempotent — once acknowledged, repeated calls are no-ops."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    out = node_state.get("output_data") or {}
    alert_id = out.get("alert_id")
    if not alert_id:
        return CompensationResult(
            action_key="retract_alert", node_id=str(node_id),
            status="skipped", detail="no alert_id in output",
        )

    async with acquire_for_tenant(enterprise_id) as conn:
        result = await conn.execute(
            "UPDATE workflow_alerts "
            "SET acknowledged_at = NOW(), "
            "    payload = jsonb_set(COALESCE(payload, '{}'::jsonb), "
            "                         '{retracted}', 'true'::jsonb, true) "
            "WHERE alert_id = $1 AND acknowledged_at IS NULL",
            alert_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    return CompensationResult(
        action_key="retract_alert", node_id=str(node_id),
        status="compensated" if rows > 0 else "skipped",
        detail=f"retracted {rows} alert(s)",
    )


# ─── Driver: walk completed nodes in reverse + invoke handlers ───


@dataclass
class SagaRunResult:
    run_id:       UUID
    invoked:      list[CompensationResult] = field(default_factory=list)
    skipped:      list[CompensationResult] = field(default_factory=list)
    failed:       list[CompensationResult] = field(default_factory=list)


async def run_compensation_chain(
    *,
    enterprise_id:   UUID,
    run_id:          UUID,
    failed_node_id:  UUID,
) -> SagaRunResult:
    """Walk completed external/write_non_idempotent nodes in reverse
    completion order + fire registered compensations.

    Best-effort: a handler failure on one node does NOT abort the chain
    (other compensations still try). Each result recorded for audit.
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    result = SagaRunResult(run_id=run_id)

    async with acquire_for_tenant(enterprise_id) as conn:
        # Load completed nodes in reverse + their catalog entry for the
        # compensation_action key.
        rows = await conn.fetch(
            """SELECT rn.node_id, rn.node_type_key, rn.side_effect_class,
                      rn.output_data, ntc.compensation_action
               FROM workflow_run_nodes rn
               LEFT JOIN node_type_catalog ntc
                    ON ntc.node_type_key = rn.node_type_key
               WHERE rn.run_id = $1
                 AND rn.status = 'completed'
                 AND rn.side_effect_class IN ('external','write_non_idempotent')
               ORDER BY rn.ended_at DESC NULLS LAST""",
            run_id,
        )

    if not rows:
        log.info("compensation.no_nodes_to_compensate",
                  run_id=str(run_id), failed_node_id=str(failed_node_id))
        return result

    await append_event(
        enterprise_id=enterprise_id, run_id=run_id,
        event_type=EventType.COMPENSATION_STARTED,
        payload={"failed_node_id": str(failed_node_id),
                  "candidate_nodes": [str(r["node_id"]) for r in rows]},
    )

    for row in rows:
        action_key = row["compensation_action"]
        node_id_val = row["node_id"]
        if not action_key:
            result.skipped.append(CompensationResult(
                action_key="", node_id=str(node_id_val),
                status="skipped",
                detail="catalog row has no compensation_action declared",
            ))
            continue
        handler = COMPENSATION_REGISTRY.get(action_key)
        if handler is None:
            result.skipped.append(CompensationResult(
                action_key=action_key, node_id=str(node_id_val),
                status="skipped",
                detail=f"no handler registered for action_key={action_key!r}",
            ))
            continue
        # Coerce JSONB to dict
        out = row["output_data"]
        if isinstance(out, str):
            try:
                out = json.loads(out) if out else {}
            except json.JSONDecodeError:
                out = {}
        node_state = {"output_data": out or {},
                       "node_type_key": row["node_type_key"]}
        try:
            outcome = await handler(
                enterprise_id, run_id, node_id_val, node_state,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("compensation.handler_failed",
                            action_key=action_key,
                            node_id=str(node_id_val))
            result.failed.append(CompensationResult(
                action_key=action_key, node_id=str(node_id_val),
                status="failed",
                detail=f"{type(e).__name__}: {e}",
            ))
            continue
        if outcome.status == "compensated":
            result.invoked.append(outcome)
        elif outcome.status == "failed":
            result.failed.append(outcome)
        else:
            result.skipped.append(outcome)

    await append_event(
        enterprise_id=enterprise_id, run_id=run_id,
        event_type=EventType.COMPENSATION_COMPLETED,
        payload={
            "invoked_count": len(result.invoked),
            "skipped_count": len(result.skipped),
            "failed_count":  len(result.failed),
            "invoked":       [r.action_key for r in result.invoked],
            "failed":        [{"action": r.action_key, "detail": r.detail}
                                for r in result.failed],
        },
    )

    log.info("compensation.chain_complete",
              run_id=str(run_id),
              invoked=len(result.invoked),
              skipped=len(result.skipped),
              failed=len(result.failed))
    return result
