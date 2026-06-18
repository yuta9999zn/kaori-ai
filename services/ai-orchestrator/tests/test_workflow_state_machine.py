"""
Tests for the formal state machine (P0.2 of orchestration hardening).
Pure validation tests — no DB needed for the validate_* functions.
DB-touching transition_*_status tested with monkeypatched conn.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from workflow_runtime.state_machine import (
    NodeRunState,
    StateTransitionDenied,
    WorkflowRunState,
    allowed_node_transitions,
    allowed_workflow_transitions,
    is_terminal_node,
    is_terminal_workflow,
    transition_node_status,
    transition_workflow_status,
    validate_node_transition,
    validate_workflow_transition,
)


# ─── Validation rules (pure) ─────────────────────────────────────


class TestWorkflowValidate:
    @pytest.mark.parametrize("from_state,to_state", [
        ("pending", "running"),
        ("pending", "cancelled"),
        ("running", "awaiting_approval"),
        ("running", "completed"),
        ("running", "failed"),
        ("running", "cancelled"),
        ("awaiting_approval", "running"),
        ("awaiting_approval", "failed"),
        ("awaiting_approval", "cancelled"),
        # Idempotent re-entry on running (resume flow uses this)
        ("running", "running"),
    ])
    def test_allowed_transitions_pass(self, from_state, to_state):
        validate_workflow_transition(from_state, to_state)  # no raise

    @pytest.mark.parametrize("from_state,to_state", [
        ("pending", "completed"),     # can't skip running
        ("pending", "failed"),        # same
        ("pending", "awaiting_approval"),
        ("completed", "running"),     # terminal — frozen
        ("completed", "failed"),
        ("failed", "running"),
        ("failed", "completed"),
        ("cancelled", "running"),
        ("cancelled", "pending"),
        ("running", "pending"),       # no backward
    ])
    def test_forbidden_transitions_raise(self, from_state, to_state):
        with pytest.raises(StateTransitionDenied) as exc_info:
            validate_workflow_transition(from_state, to_state)
        assert exc_info.value.from_state == from_state
        assert exc_info.value.to_state == to_state
        assert exc_info.value.entity == "workflow_run"

    def test_none_treated_as_pending(self):
        validate_workflow_transition(None, "running")  # no raise
        validate_workflow_transition("", "running")    # no raise
        with pytest.raises(StateTransitionDenied):
            validate_workflow_transition(None, "completed")  # pending→completed forbidden

    def test_invalid_to_state_value_raises(self):
        with pytest.raises(StateTransitionDenied):
            validate_workflow_transition("running", "fictional_status")


class TestNodeValidate:
    @pytest.mark.parametrize("from_state,to_state", [
        ("pending", "running"),
        ("pending", "skipped"),
        ("running", "awaiting_approval"),
        ("running", "completed"),
        ("running", "failed"),
        ("running", "skipped"),
        ("awaiting_approval", "running"),
        ("awaiting_approval", "completed"),
        ("awaiting_approval", "failed"),
        # Idempotent re-emits
        ("completed", "completed"),
        ("failed", "failed"),
        ("skipped", "skipped"),
    ])
    def test_allowed(self, from_state, to_state):
        validate_node_transition(from_state, to_state)

    @pytest.mark.parametrize("from_state,to_state", [
        ("completed", "running"),
        ("completed", "failed"),
        ("failed", "running"),
        ("skipped", "running"),
        ("pending", "completed"),  # must go through running first
        ("pending", "failed"),
    ])
    def test_forbidden(self, from_state, to_state):
        with pytest.raises(StateTransitionDenied):
            validate_node_transition(from_state, to_state)


class TestTerminalHelpers:
    def test_workflow_terminals(self):
        assert is_terminal_workflow("completed")
        assert is_terminal_workflow("failed")
        assert is_terminal_workflow("cancelled")
        assert not is_terminal_workflow("running")
        assert not is_terminal_workflow("awaiting_approval")
        assert not is_terminal_workflow("pending")

    def test_node_terminals(self):
        assert is_terminal_node("completed")
        assert is_terminal_node("failed")
        assert is_terminal_node("skipped")
        assert not is_terminal_node("running")
        assert not is_terminal_node("pending")
        assert not is_terminal_node("awaiting_approval")


class TestEnumConsistency:
    def test_workflow_enum_values_match_check_constraint(self):
        # CHECK in mig 088: ('pending','running','awaiting_approval',
        # 'completed','failed','cancelled')
        check_values = {"pending", "running", "awaiting_approval",
                          "completed", "failed", "cancelled"}
        enum_values = {s.value for s in WorkflowRunState}
        assert enum_values == check_values

    def test_node_enum_values_match_check_constraint(self):
        # CHECK in mig 088 workflow_run_nodes: ('pending','running',
        # 'awaiting_approval','completed','failed','skipped')
        check_values = {"pending", "running", "awaiting_approval",
                          "completed", "failed", "skipped"}
        enum_values = {s.value for s in NodeRunState}
        assert enum_values == check_values


# ─── DB transitions (mocked conn) ────────────────────────────────


@pytest.mark.asyncio
class TestTransitionWorkflowStatus:
    async def test_legal_transition_updates(self):
        captured = {"select_calls": [], "update_calls": []}

        class _Conn:
            async def fetchrow(self, sql, *args):
                captured["select_calls"].append((sql, args))
                return {"status": "running"}
            async def execute(self, sql, *args):
                captured["update_calls"].append((sql, args))

        outcome = await transition_workflow_status(
            _Conn(), run_id=uuid4(), new_status="completed",
        )
        assert outcome.applied is True
        assert outcome.from_state == "running"
        assert outcome.to_state == "completed"
        assert len(captured["update_calls"]) == 1

    async def test_idempotent_noop_skips_update(self):
        captured = {"updates": 0}

        class _Conn:
            async def fetchrow(self, *a, **k):
                return {"status": "running"}
            async def execute(self, *a, **k):
                captured["updates"] += 1

        outcome = await transition_workflow_status(
            _Conn(), run_id=uuid4(), new_status="running",
        )
        assert outcome.applied is False
        assert captured["updates"] == 0

    async def test_illegal_transition_raises(self):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return {"status": "completed"}
            async def execute(self, *a, **k):
                raise AssertionError("must not reach execute")

        with pytest.raises(StateTransitionDenied):
            await transition_workflow_status(
                _Conn(), run_id=uuid4(), new_status="running",
            )

    async def test_missing_run_raises(self):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return None
            async def execute(self, *a, **k): pass

        with pytest.raises(StateTransitionDenied):
            await transition_workflow_status(
                _Conn(), run_id=uuid4(), new_status="running",
            )


@pytest.mark.asyncio
class TestTransitionNodeStatus:
    async def test_first_record_treats_as_pending_origin(self):
        captured = {"execs": []}

        class _Conn:
            async def fetchrow(self, *a, **k):
                return None  # node row not yet inserted
            async def execute(self, *a, **k):
                captured["execs"].append(a)

        outcome = await transition_node_status(
            _Conn(),
            run_id=uuid4(), node_id=uuid4(),
            new_status="running",
        )
        assert outcome.applied is True
        assert outcome.from_state == "pending"

    async def test_legal_running_to_completed(self):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return {"status": "running"}
            async def execute(self, *a, **k): pass

        outcome = await transition_node_status(
            _Conn(),
            run_id=uuid4(), node_id=uuid4(),
            new_status="completed",
        )
        assert outcome.applied is True

    async def test_terminal_node_cannot_resurrect(self):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return {"status": "completed"}
            async def execute(self, *a, **k):
                raise AssertionError("forbidden")

        with pytest.raises(StateTransitionDenied):
            await transition_node_status(
                _Conn(),
                run_id=uuid4(), node_id=uuid4(),
                new_status="running",
            )


class TestPublicIntrospection:
    def test_workflow_transition_list_is_sorted(self):
        ts = allowed_workflow_transitions()
        assert ts == sorted(ts)
        # Includes at least the key edges
        assert ("pending", "running") in ts
        assert ("running", "completed") in ts

    def test_node_transition_list(self):
        ts = allowed_node_transitions()
        assert ("pending", "running") in ts
        assert ("running", "completed") in ts
        assert ("completed", "running") not in ts
