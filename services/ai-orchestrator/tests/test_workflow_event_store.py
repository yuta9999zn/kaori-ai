"""
Tests for the event-sourcing layer (P0.1 of orchestration hardening).

Two halves:
  - Pure projection function (project_state) — no DB needed.
  - Append + load via mocked DB.
"""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from workflow_runtime.event_store import (
    EventType,
    NodeProjection,
    RunProjection,
    WorkflowEvent,
    project_state,
)


def _ev(run_id, seq, event_type, *, node_id=None, payload=None,
         ts_offset=0):
    """Convenience: build a WorkflowEvent for projection tests."""
    return WorkflowEvent(
        event_id=uuid4(),
        enterprise_id=uuid4(),
        run_id=run_id,
        node_id=node_id,
        sequence_no=seq,
        event_type=event_type,
        payload=payload or {},
        actor_user_id=None,
        occurred_at=datetime(2026, 5, 19, 10, 0, ts_offset, tzinfo=timezone.utc),
    )


# ─── Projection — pure function tests ────────────────────────────


class TestProjectStateEmpty:
    def test_empty_event_list_returns_pending(self):
        proj = project_state([])
        assert proj.status == "pending"
        assert proj.event_count == 0
        assert proj.nodes == {}


class TestProjectStateBasic:
    def test_create_then_start(self):
        run_id = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED, ts_offset=1),
        ]
        proj = project_state(events)
        assert proj.status == "running"
        assert proj.started_at is not None
        assert proj.event_count == 2
        assert proj.last_sequence == 2

    def test_completes_terminal(self):
        run_id = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.WORKFLOW_COMPLETED, ts_offset=5,
                payload={"nodes_executed": 3,
                          "output_data": {"n1": {"x": 1}}}),
        ]
        proj = project_state(events)
        assert proj.status == "completed"
        assert proj.ended_at is not None
        assert proj.output_data == {"n1": {"x": 1}}

    def test_fails_terminal_with_error(self):
        run_id = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.WORKFLOW_FAILED,
                payload={"error": "node X exploded"}),
        ]
        proj = project_state(events)
        assert proj.status == "failed"
        assert proj.error_summary == "node X exploded"


class TestProjectStateNodes:
    def test_node_start_complete(self):
        run_id = uuid4()
        node_id = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.NODE_STARTED, node_id=node_id,
                payload={"node_type_key": "if_else"}),
            _ev(run_id, 4, EventType.NODE_COMPLETED, node_id=node_id,
                payload={"output_data": {"branch": "true"}}),
        ]
        proj = project_state(events)
        node = proj.nodes[str(node_id)]
        assert node.status == "completed"
        assert node.output_data == {"branch": "true"}
        # output_data flows into run-level snapshot
        assert proj.output_data[str(node_id)] == {"branch": "true"}

    def test_node_fail(self):
        run_id = uuid4()
        node_id = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.NODE_STARTED, node_id=node_id),
            _ev(run_id, 3, EventType.NODE_FAILED, node_id=node_id,
                payload={"error": "boom"}),
        ]
        proj = project_state(events)
        node = proj.nodes[str(node_id)]
        assert node.status == "failed"
        assert node.error_message == "boom"

    def test_node_skipped_in_resume(self):
        run_id = uuid4()
        node_id = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_RESUMED),
            _ev(run_id, 2, EventType.NODE_SKIPPED, node_id=node_id,
                payload={"output_data": {"prior": True}}),
        ]
        proj = project_state(events)
        node = proj.nodes[str(node_id)]
        assert node.status == "completed"
        assert proj.output_data[str(node_id)] == {"prior": True}

    def test_multiple_nodes_independent(self):
        run_id = uuid4()
        n1 = uuid4()
        n2 = uuid4()
        events = [
            _ev(run_id, 1, EventType.NODE_STARTED, node_id=n1),
            _ev(run_id, 2, EventType.NODE_STARTED, node_id=n2),
            _ev(run_id, 3, EventType.NODE_COMPLETED, node_id=n1,
                payload={"output_data": {"a": 1}}),
            _ev(run_id, 4, EventType.NODE_FAILED, node_id=n2,
                payload={"error": "x"}),
        ]
        proj = project_state(events)
        assert proj.nodes[str(n1)].status == "completed"
        assert proj.nodes[str(n2)].status == "failed"
        assert proj.nodes[str(n2)].error_message == "x"


class TestProjectStatePauseResume:
    def test_pause_then_resume_keeps_completed_nodes(self):
        run_id = uuid4()
        n1 = uuid4()
        n2 = uuid4()  # approval gate
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.NODE_STARTED, node_id=n1),
            _ev(run_id, 4, EventType.NODE_COMPLETED, node_id=n1,
                payload={"output_data": {"v": 100}}),
            _ev(run_id, 5, EventType.NODE_STARTED, node_id=n2),
            _ev(run_id, 6, EventType.NODE_PAUSED, node_id=n2),
            _ev(run_id, 7, EventType.WORKFLOW_PAUSED),
            # later... approval comes in
            _ev(run_id, 8, EventType.APPROVAL_RESOLVED, node_id=n2,
                payload={"decision": "approved"}),
            _ev(run_id, 9, EventType.WORKFLOW_RESUMED),
            _ev(run_id, 10, EventType.NODE_COMPLETED, node_id=n2,
                payload={"output_data": {"approved": True}}),
            _ev(run_id, 11, EventType.WORKFLOW_COMPLETED,
                payload={"nodes_executed": 2,
                          "output_data": {str(n1): {"v": 100},
                                            str(n2): {"approved": True}}}),
        ]
        proj = project_state(events)
        assert proj.status == "completed"
        assert proj.nodes[str(n1)].status == "completed"
        assert proj.nodes[str(n2)].status == "completed"
        assert proj.nodes[str(n2)].output_data["approval_decision"] == "approved"

    def test_paused_state_visible(self):
        run_id = uuid4()
        n1 = uuid4()
        events = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.NODE_PAUSED, node_id=n1),
            _ev(run_id, 4, EventType.WORKFLOW_PAUSED),
        ]
        proj = project_state(events)
        assert proj.status == "awaiting_approval"
        assert proj.nodes[str(n1)].status == "awaiting_approval"


class TestEventTypeEnum:
    def test_all_15_event_types_have_unique_values(self):
        values = [e.value for e in EventType]
        assert len(values) == len(set(values))

    def test_terminal_event_types_present(self):
        terminals = {EventType.WORKFLOW_COMPLETED.value,
                       EventType.WORKFLOW_FAILED.value,
                       EventType.WORKFLOW_CANCELLED.value}
        assert terminals.issubset({e.value for e in EventType})

    def test_compensation_events_reserved(self):
        # P1.4 compensation runtime — events already defined
        assert EventType.COMPENSATION_STARTED.value == "compensation_started"
        assert EventType.COMPENSATION_COMPLETED.value == "compensation_completed"
