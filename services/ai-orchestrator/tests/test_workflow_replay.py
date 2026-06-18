"""
Tests for P0.4 replay harness — deterministic projection from event log.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from workflow_runtime.event_store import (
    EventType,
    NodeProjection,
    RunProjection,
    WorkflowEvent,
)
from workflow_runtime.replay import (
    CachedSnapshot,
    ReplayHarness,
    ReplayResult,
    assert_projection_matches_cached,
    diff_projection_vs_snapshot,
)


def _ev(run_id, seq, et, *, node_id=None, payload=None):
    return WorkflowEvent(
        event_id=uuid4(),
        enterprise_id=uuid4(),
        run_id=run_id,
        node_id=node_id,
        sequence_no=seq,
        event_type=et,
        payload=payload or {},
        actor_user_id=None,
        occurred_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )


# ─── Pure replay (no DB) ────────────────────────────────────────


class TestReplayFromEvents:
    def test_simple_happy_path_replay(self):
        run = uuid4()
        n1 = uuid4()
        n2 = uuid4()
        events = [
            _ev(run, 1, EventType.WORKFLOW_CREATED),
            _ev(run, 2, EventType.WORKFLOW_STARTED),
            _ev(run, 3, EventType.NODE_STARTED, node_id=n1),
            _ev(run, 4, EventType.NODE_COMPLETED, node_id=n1,
                payload={"output_data": {"branch": "true"}}),
            _ev(run, 5, EventType.NODE_STARTED, node_id=n2),
            _ev(run, 6, EventType.NODE_COMPLETED, node_id=n2,
                payload={"output_data": {"sent": True}}),
            _ev(run, 7, EventType.WORKFLOW_COMPLETED,
                payload={"nodes_executed": 2,
                          "output_data": {str(n1): {"branch": "true"},
                                            str(n2): {"sent": True}}}),
        ]
        proj = ReplayHarness().replay_from_events(events)
        assert proj.status == "completed"
        assert proj.nodes[str(n1)].status == "completed"
        assert proj.nodes[str(n2)].status == "completed"
        assert proj.event_count == 7

    def test_deterministic_same_events_same_state(self):
        """Replay twice on identical event lists produces identical
        RunProjection. This is THE invariant."""
        run = uuid4()
        n1 = uuid4()
        events = [
            _ev(run, 1, EventType.WORKFLOW_CREATED),
            _ev(run, 2, EventType.WORKFLOW_STARTED),
            _ev(run, 3, EventType.NODE_STARTED, node_id=n1),
            _ev(run, 4, EventType.NODE_COMPLETED, node_id=n1,
                payload={"output_data": {"v": 42}}),
        ]
        p1 = ReplayHarness().replay_from_events(events)
        p2 = ReplayHarness().replay_from_events(events)
        assert p1.status == p2.status
        assert p1.nodes[str(n1)].status == p2.nodes[str(n1)].status
        assert p1.nodes[str(n1)].output_data == p2.nodes[str(n1)].output_data
        assert p1.event_count == p2.event_count
        assert p1.last_sequence == p2.last_sequence

    def test_pause_resume_replay(self):
        run = uuid4()
        gate = uuid4()
        events = [
            _ev(run, 1, EventType.WORKFLOW_CREATED),
            _ev(run, 2, EventType.WORKFLOW_STARTED),
            _ev(run, 3, EventType.NODE_STARTED, node_id=gate),
            _ev(run, 4, EventType.NODE_PAUSED, node_id=gate),
            _ev(run, 5, EventType.WORKFLOW_PAUSED),
            # Later: approval comes in + resume
            _ev(run, 6, EventType.APPROVAL_RESOLVED, node_id=gate,
                payload={"decision": "approved"}),
            _ev(run, 7, EventType.WORKFLOW_RESUMED),
            _ev(run, 8, EventType.NODE_COMPLETED, node_id=gate,
                payload={"output_data": {"approved": True}}),
            _ev(run, 9, EventType.WORKFLOW_COMPLETED,
                payload={"nodes_executed": 1}),
        ]
        proj = ReplayHarness().replay_from_events(events)
        assert proj.status == "completed"
        assert proj.nodes[str(gate)].status == "completed"
        approval_decision = proj.nodes[str(gate)].output_data.get("approval_decision")
        assert approval_decision == "approved"

    def test_failed_terminal_with_error_propagates(self):
        run = uuid4()
        n1 = uuid4()
        events = [
            _ev(run, 1, EventType.WORKFLOW_CREATED),
            _ev(run, 2, EventType.WORKFLOW_STARTED),
            _ev(run, 3, EventType.NODE_STARTED, node_id=n1),
            _ev(run, 4, EventType.NODE_FAILED, node_id=n1,
                payload={"error": "exec exploded"}),
            _ev(run, 5, EventType.WORKFLOW_FAILED,
                payload={"error": "exec exploded",
                          "stalled_node": str(n1)}),
        ]
        proj = ReplayHarness().replay_from_events(events)
        assert proj.status == "failed"
        assert proj.error_summary == "exec exploded"
        assert proj.nodes[str(n1)].status == "failed"
        assert proj.nodes[str(n1)].error_message == "exec exploded"

    def test_partial_event_stream_returns_in_progress(self):
        """If the run crashed mid-execution, replay returns the partial
        state — last seen status (running or awaiting_approval)."""
        run = uuid4()
        n1 = uuid4()
        events = [
            _ev(run, 1, EventType.WORKFLOW_CREATED),
            _ev(run, 2, EventType.WORKFLOW_STARTED),
            _ev(run, 3, EventType.NODE_STARTED, node_id=n1),
            # No completion event — crash mid-flight.
        ]
        proj = ReplayHarness().replay_from_events(events)
        assert proj.status == "running"
        # The node is in 'running' (started but not yet completed)
        assert proj.nodes[str(n1)].status == "running"
        assert proj.nodes[str(n1)].ended_at is None


# ─── diff helpers ────────────────────────────────────────────────


class TestDiffProjectionVsSnapshot:
    def test_identical_returns_empty(self):
        proj = RunProjection(run_id="r1", status="completed")
        proj.nodes["n1"] = NodeProjection(
            node_id="n1", status="completed",
            output_data={"x": 1},
        )
        snap = CachedSnapshot(
            status="completed",
            nodes_by_id={"n1": {"status": "completed",
                                  "output_data": {"x": 1},
                                  "error_message": None,
                                  "retry_count": 0}},
        )
        assert diff_projection_vs_snapshot(proj, snap) == []

    def test_status_mismatch_reported(self):
        proj = RunProjection(run_id="r1", status="completed")
        snap = CachedSnapshot(status="failed")
        diffs = diff_projection_vs_snapshot(proj, snap)
        assert len(diffs) == 1
        assert "run.status" in diffs[0]

    def test_node_only_in_projection(self):
        proj = RunProjection(run_id="r1", status="completed")
        proj.nodes["n1"] = NodeProjection(node_id="n1", status="completed")
        snap = CachedSnapshot(status="completed")
        diffs = diff_projection_vs_snapshot(proj, snap)
        assert any("only in projection" in d for d in diffs)

    def test_node_output_data_diff_detected(self):
        proj = RunProjection(run_id="r1", status="completed")
        proj.nodes["n1"] = NodeProjection(
            node_id="n1", status="completed",
            output_data={"x": 1, "y": 2},
        )
        snap = CachedSnapshot(
            status="completed",
            nodes_by_id={"n1": {"status": "completed",
                                  "output_data": {"x": 1},
                                  "error_message": None,
                                  "retry_count": 0}},
        )
        diffs = diff_projection_vs_snapshot(proj, snap)
        assert any("output_data diff" in d for d in diffs)

    def test_null_vs_empty_error_summary_equivalent(self):
        """None and "" both mean 'no error' — should NOT diff."""
        proj = RunProjection(run_id="r1", status="completed", error_summary=None)
        snap = CachedSnapshot(status="completed", error_summary="")
        diffs = diff_projection_vs_snapshot(proj, snap)
        assert not any("error_summary" in d for d in diffs)


# ─── assert_projection_matches_cached helper ────────────────────


class TestAssertHelper:
    def test_passes_when_matches(self):
        result = ReplayResult(
            run_id="r1", event_count=4, matches=True, diffs=[],
        )
        # Should not raise
        assert_projection_matches_cached(result)

    def test_raises_when_diffs(self):
        result = ReplayResult(
            run_id="r1", event_count=4, matches=False,
            diffs=["run.status: projection=running vs cached=completed"],
        )
        with pytest.raises(AssertionError) as exc:
            assert_projection_matches_cached(result)
        assert "r1" in str(exc.value)
        assert "run.status" in str(exc.value)


# ─── DB-integrated replay (mocked conn) ─────────────────────────


@pytest.mark.asyncio
class TestReplayHarnessDB:
    async def test_load_cached_snapshot_missing_run(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None
            async def fetch(self, *a, **k): return []

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        from workflow_runtime.replay import load_cached_snapshot
        snap = await load_cached_snapshot(enterprise_id=uuid4(), run_id=uuid4())
        assert snap is None

    async def test_full_replay_run_no_drift(self, monkeypatch):
        """Happy-path: events agree with cached row → matches=True."""
        run_id = uuid4()
        enterprise_id = uuid4()
        n1 = uuid4()

        from workflow_runtime import event_store as _es
        from workflow_runtime import replay as _replay

        cached = {
            "status": "completed",
            "error_summary": None,
            "output_data": {str(n1): {"x": 1}},
        }
        cached_nodes = [
            {"node_id": n1, "status": "completed",
              "output_data": {"x": 1},
              "error_message": None, "retry_count": 0,
              "started_at": None, "ended_at": None},
        ]

        events_in_db = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.NODE_STARTED, node_id=n1),
            _ev(run_id, 4, EventType.NODE_COMPLETED, node_id=n1,
                payload={"output_data": {"x": 1}}),
            _ev(run_id, 5, EventType.WORKFLOW_COMPLETED,
                payload={"nodes_executed": 1,
                          "output_data": {str(n1): {"x": 1}}}),
        ]

        async def fake_load(*, enterprise_id, run_id):
            return events_in_db

        class _Conn:
            async def fetchrow(self, sql, *a):
                if "SELECT status, error_summary" in sql:
                    return {"status": cached["status"],
                              "error_summary": cached["error_summary"],
                              "output_data": cached["output_data"]}
                return None
            async def fetch(self, sql, *a):
                return cached_nodes

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())
        monkeypatch.setattr(_es, "load_event_stream", fake_load)
        monkeypatch.setattr(_replay, "load_event_stream", fake_load)

        result = await ReplayHarness().run(
            enterprise_id=enterprise_id, run_id=run_id,
        )
        assert result.matches is True
        assert result.event_count == 5
        assert result.diffs == []

    async def test_replay_detects_drift(self, monkeypatch):
        """Cached says completed but events say failed → diff reported."""
        run_id = uuid4()
        n1 = uuid4()

        from workflow_runtime import event_store as _es
        from workflow_runtime import replay as _replay

        events_in_db = [
            _ev(run_id, 1, EventType.WORKFLOW_CREATED),
            _ev(run_id, 2, EventType.WORKFLOW_STARTED),
            _ev(run_id, 3, EventType.NODE_STARTED, node_id=n1),
            _ev(run_id, 4, EventType.NODE_FAILED, node_id=n1,
                payload={"error": "bad"}),
            _ev(run_id, 5, EventType.WORKFLOW_FAILED,
                payload={"error": "bad"}),
        ]

        async def fake_load(*, enterprise_id, run_id):
            return events_in_db

        # Cached row says completed — DRIFT
        class _Conn:
            async def fetchrow(self, sql, *a):
                if "SELECT status, error_summary" in sql:
                    return {"status": "completed",
                              "error_summary": None,
                              "output_data": {}}
                return None
            async def fetch(self, *a, **k):
                return [{"node_id": n1, "status": "completed",
                          "output_data": {},
                          "error_message": None, "retry_count": 0,
                          "started_at": None, "ended_at": None}]

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())
        monkeypatch.setattr(_es, "load_event_stream", fake_load)
        monkeypatch.setattr(_replay, "load_event_stream", fake_load)

        result = await ReplayHarness().run(
            enterprise_id=uuid4(), run_id=run_id,
        )
        assert result.matches is False
        assert any("run.status" in d for d in result.diffs)
        # Also detects node-level diff
        assert any("status" in d for d in result.diffs if "node" in d.lower())
