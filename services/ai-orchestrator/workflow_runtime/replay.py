"""
Deterministic replay harness — P0.4 of orchestration hardening.

A replay harness rebuilds workflow state from the event_store stream
WITHOUT firing side effects. Two use cases:

  1. Verify state recovery: load events for a real run, project_state()
     → RunProjection, assert equivalence with workflow_runs +
     workflow_run_nodes rows. Detects projector drift early.

  2. Deterministic test: capture a run's event stream + replay against
     a fresh in-process state. Same input → same output. If a future
     refactor changes the projection, the test catches it.

API surface:
  ReplayHarness                     — class that drives replay
  ReplayResult                      — typed outcome with diffs
  load_run_for_replay()             — pull events + cached projections
  assert_projection_matches_cached() — comparison helper for tests
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import structlog

from .event_store import (
    EventType,
    RunProjection,
    WorkflowEvent,
    load_event_stream,
    project_state,
)

log = structlog.get_logger()


@dataclass
class ReplayResult:
    """Outcome of a replay run. `matches` is True only when the projected
    state from the event stream is byte-equivalent to the cached
    workflow_runs / workflow_run_nodes view."""
    run_id:         str
    event_count:    int
    matches:        bool
    diffs:          list[str] = field(default_factory=list)
    projection:     Optional[RunProjection] = None


@dataclass
class CachedSnapshot:
    """Cached view rebuilt from workflow_runs + workflow_run_nodes.
    For comparison with the projection from event stream."""
    status:         str
    nodes_by_id:    dict[str, dict[str, Any]] = field(default_factory=dict)
    error_summary:  Optional[str] = None
    output_data:    dict[str, dict[str, Any]] = field(default_factory=dict)


async def load_cached_snapshot(
    *,
    enterprise_id: UUID,
    run_id:        UUID,
) -> Optional[CachedSnapshot]:
    """Load workflow_runs row + per-node rows into a CachedSnapshot.
    Returns None if the run doesn't exist (or RLS hides it)."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        run_row = await conn.fetchrow(
            "SELECT status, error_summary, output_data "
            "FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
        if run_row is None:
            return None
        node_rows = await conn.fetch(
            "SELECT node_id, status, output_data, error_message, "
            "       retry_count, started_at, ended_at "
            "FROM workflow_run_nodes WHERE run_id = $1",
            run_id,
        )

    snap = CachedSnapshot(
        status=run_row["status"],
        error_summary=run_row["error_summary"],
    )
    output_data = run_row["output_data"]
    if isinstance(output_data, str):
        try:
            output_data = json.loads(output_data) if output_data else {}
        except json.JSONDecodeError:
            output_data = {}
    snap.output_data = output_data or {}

    for r in node_rows:
        node_out = r["output_data"]
        if isinstance(node_out, str):
            try:
                node_out = json.loads(node_out) if node_out else {}
            except json.JSONDecodeError:
                node_out = {}
        snap.nodes_by_id[str(r["node_id"])] = {
            "status":          r["status"],
            "output_data":     node_out or {},
            "error_message":   r["error_message"],
            "retry_count":     r["retry_count"],
        }
    return snap


def diff_projection_vs_snapshot(
    projection: RunProjection,
    snapshot:   CachedSnapshot,
) -> list[str]:
    """Pure comparison. Returns list of human-readable diffs. Empty list
    means the projection matches the cached snapshot byte-for-byte on
    the comparable fields (status, error, per-node status + output)."""
    diffs: list[str] = []

    if projection.status != snapshot.status:
        diffs.append(
            f"run.status: projection={projection.status!r} vs "
            f"cached={snapshot.status!r}"
        )

    if projection.error_summary != snapshot.error_summary:
        # Sentinel: both might be None — that's fine.
        if (projection.error_summary or "") != (snapshot.error_summary or ""):
            diffs.append(
                f"run.error_summary: projection={projection.error_summary!r} "
                f"vs cached={snapshot.error_summary!r}"
            )

    # Node-level diff
    proj_node_ids = set(projection.nodes.keys())
    cached_node_ids = set(snapshot.nodes_by_id.keys())

    only_in_projection = proj_node_ids - cached_node_ids
    only_in_cached = cached_node_ids - proj_node_ids
    if only_in_projection:
        diffs.append(f"nodes only in projection: {sorted(only_in_projection)}")
    if only_in_cached:
        diffs.append(f"nodes only in cached: {sorted(only_in_cached)}")

    for nid in proj_node_ids & cached_node_ids:
        proj_node = projection.nodes[nid]
        cached_node = snapshot.nodes_by_id[nid]
        if proj_node.status != cached_node["status"]:
            diffs.append(
                f"node {nid[:8]} status: projection={proj_node.status!r} "
                f"vs cached={cached_node['status']!r}"
            )
        proj_out = proj_node.output_data or {}
        cached_out = cached_node["output_data"] or {}
        if proj_out != cached_out:
            diffs.append(
                f"node {nid[:8]} output_data diff: "
                f"projection_keys={sorted(proj_out.keys())} "
                f"cached_keys={sorted(cached_out.keys())}"
            )

    return diffs


class ReplayHarness:
    """Driver class — loads events + projects + compares.

    Use case 1 (drift detection):
        result = await ReplayHarness().run(enterprise_id=eid, run_id=rid)
        if not result.matches:
            log.error("replay.drift_detected", diffs=result.diffs)

    Use case 2 (deterministic test): tests inject events via
    `replay_from_events()` and assert against a known RunProjection.
    """

    async def run(
        self,
        *,
        enterprise_id: UUID,
        run_id:        UUID,
    ) -> ReplayResult:
        """Load events + cached snapshot, project + diff."""
        events = await load_event_stream(
            enterprise_id=enterprise_id, run_id=run_id,
        )
        snapshot = await load_cached_snapshot(
            enterprise_id=enterprise_id, run_id=run_id,
        )
        projection = project_state(events)
        if snapshot is None:
            return ReplayResult(
                run_id=str(run_id),
                event_count=len(events),
                matches=False,
                diffs=["cached snapshot not found (run missing or RLS hidden)"],
                projection=projection,
            )
        diffs = diff_projection_vs_snapshot(projection, snapshot)
        return ReplayResult(
            run_id=str(run_id),
            event_count=len(events),
            matches=not diffs,
            diffs=diffs,
            projection=projection,
        )

    def replay_from_events(self, events: list[WorkflowEvent]) -> RunProjection:
        """Pure replay — no DB. For deterministic unit tests."""
        return project_state(events)


def assert_projection_matches_cached(result: ReplayResult) -> None:
    """Test helper — pytest-friendly assertion. Raises AssertionError
    with a readable diff list when mismatched."""
    if not result.matches:
        msg = (
            f"replay drift on run {result.run_id} "
            f"({result.event_count} events):\n  - "
            + "\n  - ".join(result.diffs)
        )
        raise AssertionError(msg)
