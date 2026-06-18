"""
Replay-driven reconciler — F3 of chaos-matrix.md follow-up.

Closes the long-tail of Gap 1: when state_store.upsert_run_node
exhausts retries (DbWriteExhausted), the runner logs + continues. The
workflow_events stream STILL captured the NODE_STARTED + NODE_COMPLETED
events (events are best-effort _emit but those have their own
defense). The workflow_run_nodes row is missing.

This module re-INSERTs missing rows from the event log. Two entry
points:

  reconcile_run(enterprise_id, run_id)
      Walks events for one run + INSERTs any missing workflow_run_nodes
      rows. Returns ReconcileResult with counts.

  reconcile_recent(enterprise_id, hours)
      Sweep mode: finds all runs with events in the last N hours
      whose status is terminal (completed/failed) AND have at least
      one node mentioned in events but missing from workflow_run_nodes.
      Calls reconcile_run for each.

Manual invocation today via the routers in routers/admin_reconcile.py.
Future: schedule reconcile_recent as a Temporal cron (workflow ready
to wire when worker activates).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from .event_store import (
    EventType,
    load_event_stream,
    project_state,
)

log = structlog.get_logger()


@dataclass
class ReconcileResult:
    """Outcome of reconcile_run. Counts surface in the admin endpoint
    response so ops can see how big the gap was."""
    run_id:                str
    events_walked:         int = 0
    nodes_in_projection:   int = 0
    nodes_already_present: int = 0
    nodes_inserted:        int = 0
    insert_errors:         int = 0
    inserted_node_ids:     list[str] = field(default_factory=list)


@dataclass
class SweepResult:
    """Outcome of reconcile_recent. Aggregates per-run counts."""
    runs_scanned:          int = 0
    runs_reconciled:       int = 0
    total_nodes_inserted:  int = 0
    total_insert_errors:   int = 0
    per_run:               list[ReconcileResult] = field(default_factory=list)


async def reconcile_run(
    enterprise_id: UUID,
    run_id:        UUID,
) -> ReconcileResult:
    """Walk events for the run + INSERT any missing workflow_run_nodes
    rows. Idempotent — uses INSERT ... ON CONFLICT DO NOTHING so
    re-running the same reconcile produces the same state."""
    result = ReconcileResult(run_id=str(run_id))

    events = await load_event_stream(enterprise_id=enterprise_id, run_id=run_id)
    result.events_walked = len(events)
    if not events:
        return result

    projection = project_state(events)
    result.nodes_in_projection = len(projection.nodes)

    if not projection.nodes:
        return result

    # Look up which workflow_run_nodes rows already exist.
    from ai_orchestrator.shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        existing_rows = await conn.fetch(
            "SELECT node_id FROM workflow_run_nodes WHERE run_id = $1",
            run_id,
        )
        existing_ids = {str(r["node_id"]) for r in existing_rows}
        result.nodes_already_present = len(existing_ids)

        # Determine which node_type_catalog_key + side_effect_class
        # to use for inserts. Read from workflow_nodes table.
        wf_run = await conn.fetchrow(
            "SELECT workflow_id FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
        if wf_run is None:
            log.warning("reconciler.run_not_found", run_id=str(run_id))
            return result

        node_meta_rows = await conn.fetch(
            """SELECT node_id, node_type_catalog_key, sequence_order
               FROM workflow_nodes WHERE workflow_id = $1""",
            wf_run["workflow_id"],
        )
        node_meta = {
            str(r["node_id"]): r for r in node_meta_rows
        }

        # Insert missing rows. For side_effect_class, default to
        # 'pure' if we can't infer it — the audit gap is recoverable;
        # the K-17 class is a hint, not a constraint here.
        for projected_node_id, node_proj in projection.nodes.items():
            if projected_node_id in existing_ids:
                continue

            meta = node_meta.get(projected_node_id)
            if meta is None:
                # Event referenced a node that's not in workflow_nodes
                # (workflow edited after run started?). Log + skip.
                log.warning(
                    "reconciler.node_meta_missing",
                    run_id=str(run_id),
                    node_id=projected_node_id,
                )
                result.insert_errors += 1
                continue

            try:
                await conn.execute(
                    """INSERT INTO workflow_run_nodes
                           (run_id, node_id, enterprise_id, node_type_key,
                            side_effect_class, sequence_order, status,
                            input_data, output_data, error_message,
                            started_at, ended_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                       ON CONFLICT (run_id, node_id) DO NOTHING""",
                    run_id, UUID(projected_node_id), enterprise_id,
                    meta["node_type_catalog_key"],
                    "pure",  # K-17 hint — reconciler can't know the
                              # real class, audit downstream if needed
                    meta["sequence_order"] or 0,
                    node_proj.status,
                    json.dumps({}),
                    json.dumps(node_proj.output_data) if node_proj.output_data else None,
                    node_proj.error_message,
                    node_proj.started_at,
                    node_proj.ended_at,
                )
                result.nodes_inserted += 1
                result.inserted_node_ids.append(projected_node_id)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "reconciler.node_insert_failed",
                    run_id=str(run_id),
                    node_id=projected_node_id,
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                )
                result.insert_errors += 1

    log.info(
        "reconciler.run_complete",
        run_id=str(run_id),
        events=result.events_walked,
        projected_nodes=result.nodes_in_projection,
        already_present=result.nodes_already_present,
        inserted=result.nodes_inserted,
        errors=result.insert_errors,
    )
    return result


async def reconcile_recent(
    enterprise_id: UUID,
    *,
    hours: int = 24,
    limit: int = 100,
) -> SweepResult:
    """Find recent terminal runs + reconcile each. Bounds:
      hours  — look back N hours via workflow_events.occurred_at
      limit  — max runs to reconcile in one sweep
    """
    if hours < 1 or hours > 24 * 14:
        raise ValueError("hours must be between 1 and 336 (2 weeks)")
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")

    sweep = SweepResult()

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    from ai_orchestrator.shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        # Find runs with events in the window that are in terminal
        # state (completed/failed/cancelled). Skip running/pending —
        # those might still get their write through.
        rows = await conn.fetch(
            """SELECT DISTINCT run_id
               FROM workflow_events
               WHERE occurred_at >= $1
                 AND event_type IN ('workflow_completed', 'workflow_failed', 'workflow_cancelled')
               ORDER BY run_id
               LIMIT $2""",
            since, limit,
        )
    run_ids = [r["run_id"] for r in rows]
    sweep.runs_scanned = len(run_ids)

    for run_id in run_ids:
        rr = await reconcile_run(enterprise_id, run_id)
        sweep.per_run.append(rr)
        if rr.nodes_inserted > 0:
            sweep.runs_reconciled += 1
        sweep.total_nodes_inserted += rr.nodes_inserted
        sweep.total_insert_errors += rr.insert_errors

    log.info(
        "reconciler.sweep_complete",
        enterprise_id=str(enterprise_id),
        hours=hours,
        scanned=sweep.runs_scanned,
        reconciled=sweep.runs_reconciled,
        inserted=sweep.total_nodes_inserted,
    )
    return sweep
