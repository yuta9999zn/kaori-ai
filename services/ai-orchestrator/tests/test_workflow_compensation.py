"""
Tests for P1.4 saga compensation runtime.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from workflow_runtime.compensation import (
    COMPENSATION_REGISTRY,
    CompensationResult,
    SagaRunResult,
    register_compensation,
    run_compensation_chain,
)


class TestRegistry:
    def test_builtin_compensations_registered(self):
        for key in (
            "send_retraction_email",
            "cancel_approval_request",
            "delete_task",
            "retract_alert",
        ):
            assert key in COMPENSATION_REGISTRY, f"{key} not registered"

    def test_register_decorator_adds_to_registry(self):
        @register_compensation("test_action_only_for_test")
        async def _h(enterprise_id, run_id, node_id, node_state):
            return CompensationResult(
                action_key="test_action_only_for_test",
                node_id=str(node_id),
                status="compensated",
            )
        assert COMPENSATION_REGISTRY["test_action_only_for_test"] is _h


class TestBuiltinHandlers:
    """Each handler tested in isolation with mocked DB. They follow the
    same shape — early return if required key missing, idempotent UPDATE."""

    @pytest.mark.asyncio
    async def test_send_retraction_email_skips_when_no_outbox_id(self):
        from workflow_runtime.compensation import _comp_send_retraction_email
        result = await _comp_send_retraction_email(
            uuid4(), uuid4(), uuid4(),
            {"output_data": {"recipient": "x@y.com"}},  # missing outbox_id
        )
        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_send_retraction_email_inserts(self, monkeypatch):
        from workflow_runtime.compensation import _comp_send_retraction_email

        class _Conn:
            async def fetchrow(self, sql, *a):
                if "SELECT outbox_id" in sql:
                    return None  # no existing
                return {"outbox_id": uuid4()}

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await _comp_send_retraction_email(
            uuid4(), uuid4(), uuid4(),
            {"output_data": {"outbox_id": "x", "recipient": "a@b.com"}},
        )
        assert result.status == "compensated"

    @pytest.mark.asyncio
    async def test_send_retraction_dedup(self, monkeypatch):
        from workflow_runtime.compensation import _comp_send_retraction_email

        existing_id = uuid4()
        execute_calls = []

        class _Conn:
            async def fetchrow(self, sql, *a):
                if "SELECT outbox_id" in sql:
                    return {"outbox_id": existing_id}  # already enqueued
                return None
            async def execute(self, *a, **k):
                execute_calls.append(a)

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await _comp_send_retraction_email(
            uuid4(), uuid4(), uuid4(),
            {"output_data": {"outbox_id": "x", "recipient": "a@b.com"}},
        )
        assert result.status == "compensated"
        assert "already enqueued" in result.detail

    @pytest.mark.asyncio
    async def test_cancel_approval_request_updates_pending(self, monkeypatch):
        from workflow_runtime.compensation import _comp_cancel_approval

        class _Conn:
            async def execute(self, sql, *a):
                return "UPDATE 1"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await _comp_cancel_approval(
            uuid4(), uuid4(), uuid4(), {},
        )
        assert result.status == "compensated"

    @pytest.mark.asyncio
    async def test_cancel_approval_idempotent_skip_if_already_resolved(self, monkeypatch):
        from workflow_runtime.compensation import _comp_cancel_approval

        class _Conn:
            async def execute(self, *a, **k):
                return "UPDATE 0"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await _comp_cancel_approval(
            uuid4(), uuid4(), uuid4(), {},
        )
        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_delete_task_skips_without_task_id(self):
        from workflow_runtime.compensation import _comp_delete_task
        result = await _comp_delete_task(
            uuid4(), uuid4(), uuid4(), {"output_data": {}},
        )
        assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_delete_task_cancels_open(self, monkeypatch):
        from workflow_runtime.compensation import _comp_delete_task

        class _Conn:
            async def execute(self, *a, **k): return "UPDATE 1"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await _comp_delete_task(
            uuid4(), uuid4(), uuid4(),
            {"output_data": {"task_id": str(uuid4())}},
        )
        assert result.status == "compensated"

    @pytest.mark.asyncio
    async def test_retract_alert_skips_without_id(self):
        from workflow_runtime.compensation import _comp_retract_alert
        result = await _comp_retract_alert(
            uuid4(), uuid4(), uuid4(), {"output_data": {}},
        )
        assert result.status == "skipped"


# ─── Driver: run_compensation_chain ─────────────────────────────


@pytest.mark.asyncio
class TestRunCompensationChain:
    async def _setup_db(self, monkeypatch, rows: list[dict]):
        """Common setup: load returns the given rows, append_event is no-op."""
        from workflow_runtime import compensation as _comp

        class _Conn:
            async def fetch(self, *a, **k): return rows
            async def fetchrow(self, *a, **k): return None
            async def execute(self, *a, **k): return "OK"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        async def fake_append_event(**kwargs):
            return None
        monkeypatch.setattr(_comp, "append_event", fake_append_event)

    async def test_no_completed_nodes_returns_empty(self, monkeypatch):
        await self._setup_db(monkeypatch, rows=[])
        result = await run_compensation_chain(
            enterprise_id=uuid4(),
            run_id=uuid4(),
            failed_node_id=uuid4(),
        )
        assert result.invoked == []
        assert result.skipped == []
        assert result.failed == []

    async def test_skips_node_without_compensation_action(self, monkeypatch):
        await self._setup_db(monkeypatch, rows=[
            {"node_id": uuid4(), "node_type_key": "send_email",
              "side_effect_class": "external",
              "output_data": {"outbox_id": "x", "recipient": "a@b.com"},
              "compensation_action": None},
        ])
        result = await run_compensation_chain(
            enterprise_id=uuid4(),
            run_id=uuid4(),
            failed_node_id=uuid4(),
        )
        assert len(result.skipped) == 1
        assert "no compensation_action" in result.skipped[0].detail

    async def test_skips_unknown_action_key(self, monkeypatch):
        await self._setup_db(monkeypatch, rows=[
            {"node_id": uuid4(), "node_type_key": "custom",
              "side_effect_class": "external",
              "output_data": {},
              "compensation_action": "no_such_handler"},
        ])
        result = await run_compensation_chain(
            enterprise_id=uuid4(),
            run_id=uuid4(),
            failed_node_id=uuid4(),
        )
        assert len(result.skipped) == 1
        assert "no handler registered" in result.skipped[0].detail

    async def test_handler_exception_captured_chain_continues(self, monkeypatch):
        from workflow_runtime import compensation as _comp

        # Register a deliberately failing handler
        @register_compensation("explode_for_test")
        async def _bad(_eid, _rid, _nid, _ns):
            raise RuntimeError("boom")

        node_a = uuid4()
        node_b = uuid4()
        await self._setup_db(monkeypatch, rows=[
            {"node_id": node_a, "node_type_key": "x",
              "side_effect_class": "external",
              "output_data": {},
              "compensation_action": "explode_for_test"},
            {"node_id": node_b, "node_type_key": "y",
              "side_effect_class": "external",
              "output_data": {},
              "compensation_action": "no_such_handler"},
        ])

        result = await run_compensation_chain(
            enterprise_id=uuid4(),
            run_id=uuid4(),
            failed_node_id=uuid4(),
        )
        # First node fails, second is skipped — chain continues
        assert len(result.failed) == 1
        assert "RuntimeError" in result.failed[0].detail
        assert len(result.skipped) == 1


class TestSagaRunResult:
    def test_dataclass_defaults_empty_lists(self):
        run_id = uuid4()
        r = SagaRunResult(run_id=run_id)
        assert r.invoked == []
        assert r.skipped == []
        assert r.failed == []
