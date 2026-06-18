"""
Event store — append-only workflow_events writer + projector.

P0.1 of operational-correctness hardening (per anh's review 2026-05-19).

Two responsibilities:

  1. append(event)            — atomic INSERT with per-run sequence_no
  2. project(run_id)          — replay events to current state snapshot
                                (workflow + per-node + paused flag)

The runner (runner.py) emits events at every state change; the workflow_runs
+ workflow_run_nodes tables become CACHED PROJECTIONS rebuildable from
events. Replay tests (P0.4) rebuild state from a recorded event log and
assert equivalence with a fresh in-process run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


class EventType(str, Enum):
    WORKFLOW_CREATED        = "workflow_created"
    WORKFLOW_STARTED        = "workflow_started"
    NODE_STARTED            = "node_started"
    NODE_COMPLETED          = "node_completed"
    NODE_FAILED             = "node_failed"
    NODE_SKIPPED            = "node_skipped"
    NODE_PAUSED             = "node_paused"
    APPROVAL_RESOLVED       = "approval_resolved"
    WORKFLOW_PAUSED         = "workflow_paused"
    WORKFLOW_RESUMED        = "workflow_resumed"
    WORKFLOW_COMPLETED      = "workflow_completed"
    WORKFLOW_FAILED         = "workflow_failed"
    WORKFLOW_CANCELLED      = "workflow_cancelled"
    COMPENSATION_STARTED    = "compensation_started"
    COMPENSATION_COMPLETED  = "compensation_completed"


@dataclass(frozen=True)
class WorkflowEvent:
    """One immutable event in a run's history."""
    event_id:       UUID
    enterprise_id:  UUID
    run_id:         UUID
    node_id:        Optional[UUID]
    sequence_no:    int
    event_type:     EventType
    payload:        dict[str, Any]
    actor_user_id:  Optional[UUID]
    occurred_at:    datetime


@dataclass
class NodeProjection:
    node_id:        str
    status:         str
    started_at:     Optional[datetime] = None
    ended_at:       Optional[datetime] = None
    error_message:  Optional[str] = None
    retry_count:    int = 0
    output_data:    Optional[dict[str, Any]] = None


@dataclass
class RunProjection:
    """Derived state from event stream. Equivalent to what
    workflow_runs + workflow_run_nodes rows would say."""
    run_id:         str
    status:         str = "pending"
    started_at:     Optional[datetime] = None
    ended_at:       Optional[datetime] = None
    error_summary:  Optional[str] = None
    output_data:    dict[str, dict[str, Any]] = field(default_factory=dict)
    nodes:          dict[str, NodeProjection] = field(default_factory=dict)
    event_count:    int = 0
    last_sequence:  int = 0


async def append_event(
    *,
    enterprise_id:  UUID,
    run_id:         UUID,
    event_type:     EventType,
    node_id:        Optional[UUID] = None,
    payload:        Optional[dict[str, Any]] = None,
    actor_user_id:  Optional[UUID] = None,
) -> WorkflowEvent:
    """Append an event with a per-run sequence_no allocated atomically.

    Raises asyncpg.RaiseError if RLS rejects (caller's enterprise_id
    mismatch). The trigger on workflow_events also blocks any UPDATE
    or DELETE — appends only.
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str)

    async with acquire_for_tenant(enterprise_id) as conn:
        async with conn.transaction():
            seq = await conn.fetchval(
                "SELECT workflow_events_next_seq($1, $2)",
                run_id, enterprise_id,
            )
            row = await conn.fetchrow(
                """INSERT INTO workflow_events
                       (enterprise_id, run_id, node_id, sequence_no,
                        event_type, payload, actor_user_id)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                   RETURNING event_id, occurred_at""",
                enterprise_id, run_id, node_id, seq,
                event_type.value, payload_json, actor_user_id,
            )

    event = WorkflowEvent(
        event_id=row["event_id"],
        enterprise_id=enterprise_id,
        run_id=run_id,
        node_id=node_id,
        sequence_no=seq,
        event_type=event_type,
        payload=payload or {},
        actor_user_id=actor_user_id,
        occurred_at=row["occurred_at"],
    )
    log.info("workflow_event.appended",
              run_id=str(run_id), sequence_no=seq,
              event_type=event_type.value, node_id=str(node_id) if node_id else None,
              enterprise_id=str(enterprise_id))
    return event


async def load_event_stream(
    *,
    enterprise_id: UUID,
    run_id:        UUID,
) -> list[WorkflowEvent]:
    """Read all events for a run ordered by sequence_no. Used by replay
    harness + admin debugging."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT event_id, enterprise_id, run_id, node_id, sequence_no,
                      event_type, payload, actor_user_id, occurred_at
               FROM workflow_events
               WHERE run_id = $1
               ORDER BY sequence_no""",
            run_id,
        )

    events: list[WorkflowEvent] = []
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                payload = {}
        events.append(WorkflowEvent(
            event_id=r["event_id"],
            enterprise_id=r["enterprise_id"],
            run_id=r["run_id"],
            node_id=r["node_id"],
            sequence_no=r["sequence_no"],
            event_type=EventType(r["event_type"]),
            payload=payload or {},
            actor_user_id=r["actor_user_id"],
            occurred_at=r["occurred_at"],
        ))
    return events


def project_state(events: list[WorkflowEvent]) -> RunProjection:
    """Pure function — fold events into the current state snapshot.

    Same logic that workflow_run_nodes + workflow_runs rows would carry
    if we trusted them. Tests use this to verify the projection matches
    the cached tables.
    """
    if not events:
        return RunProjection(run_id="")

    proj = RunProjection(run_id=str(events[0].run_id))
    for evt in events:
        proj.event_count += 1
        proj.last_sequence = evt.sequence_no

        if evt.event_type == EventType.WORKFLOW_CREATED:
            proj.status = "pending"
        elif evt.event_type == EventType.WORKFLOW_STARTED:
            proj.status = "running"
            proj.started_at = evt.occurred_at
        elif evt.event_type == EventType.WORKFLOW_PAUSED:
            proj.status = "awaiting_approval"
        elif evt.event_type == EventType.WORKFLOW_RESUMED:
            proj.status = "running"
        elif evt.event_type == EventType.WORKFLOW_COMPLETED:
            proj.status = "completed"
            proj.ended_at = evt.occurred_at
            if "output_data" in evt.payload and isinstance(evt.payload["output_data"], dict):
                proj.output_data = evt.payload["output_data"]
        elif evt.event_type == EventType.WORKFLOW_FAILED:
            proj.status = "failed"
            proj.ended_at = evt.occurred_at
            proj.error_summary = evt.payload.get("error")
        elif evt.event_type == EventType.WORKFLOW_CANCELLED:
            proj.status = "cancelled"
            proj.ended_at = evt.occurred_at
            proj.error_summary = evt.payload.get("reason")

        # Per-node projection
        if evt.node_id is not None:
            node_key = str(evt.node_id)
            node = proj.nodes.setdefault(node_key, NodeProjection(
                node_id=node_key, status="pending",
            ))
            if evt.event_type == EventType.NODE_STARTED:
                node.status = "running"
                node.started_at = evt.occurred_at
                node.retry_count += 1 if node.retry_count > 0 or node.started_at else 0
                if node.started_at is None:
                    node.started_at = evt.occurred_at
            elif evt.event_type == EventType.NODE_COMPLETED:
                node.status = "completed"
                node.ended_at = evt.occurred_at
                if "output_data" in evt.payload and isinstance(evt.payload["output_data"], dict):
                    # Preserve approval_decision if APPROVAL_RESOLVED stamped
                    # it before NODE_COMPLETED (approval gate flow).
                    preserved = (node.output_data or {}).get("approval_decision")
                    node.output_data = dict(evt.payload["output_data"])
                    if preserved is not None and "approval_decision" not in node.output_data:
                        node.output_data["approval_decision"] = preserved
                    proj.output_data[node_key] = node.output_data
            elif evt.event_type == EventType.NODE_FAILED:
                node.status = "failed"
                node.ended_at = evt.occurred_at
                node.error_message = evt.payload.get("error")
            elif evt.event_type == EventType.NODE_SKIPPED:
                node.status = "completed"
                if "output_data" in evt.payload and isinstance(evt.payload["output_data"], dict):
                    node.output_data = evt.payload["output_data"]
                    proj.output_data[node_key] = evt.payload["output_data"]
            elif evt.event_type == EventType.NODE_PAUSED:
                node.status = "awaiting_approval"
            elif evt.event_type == EventType.APPROVAL_RESOLVED:
                # node was awaiting_approval — emit subsequent node_completed
                # to clear it; for now stamp the approval payload on the node
                if "decision" in evt.payload:
                    node.output_data = dict(node.output_data or {})
                    node.output_data["approval_decision"] = evt.payload["decision"]

    return proj


# ─── Bulk-fetch enterprise events (admin / projector rebuild) ─────


async def find_runs_needing_projection_rebuild(
    enterprise_id: UUID,
    limit:         int = 100,
) -> list[UUID]:
    """List run_ids whose workflow_runs.status disagrees with the
    projection from workflow_events. Useful for cache invalidation +
    nightly reconciliation sweeps.
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT r.run_id
               FROM workflow_runs r
               WHERE r.enterprise_id = $1
                 AND EXISTS (
                   SELECT 1 FROM workflow_events e
                   WHERE e.run_id = r.run_id
                     AND e.event_type IN ('workflow_completed','workflow_failed',
                                           'workflow_cancelled')
                 )
                 AND r.status NOT IN ('completed','failed','cancelled')
               LIMIT $2""",
            enterprise_id, limit,
        )
    return [r["run_id"] for r in rows]
