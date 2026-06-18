"""
Tests for P1 DLQ console — admin endpoints validation + auth gate.

Uses fastapi.testclient via existing main app fixture pattern. Where DB
calls are needed, mock acquire_for_tenant.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from ai_orchestrator.routers.dlq_console import (
    DlqActionOut,
    DlqItemOut,
    DlqOverviewOut,
    _require_admin,
)
from fastapi import HTTPException


# ─── Auth gate ───────────────────────────────────────────────────


class TestRequireAdmin:
    def test_super_admin_passes(self):
        _require_admin("SUPER_ADMIN")  # no raise

    def test_admin_passes(self):
        _require_admin("ADMIN")  # no raise

    def test_other_roles_blocked(self):
        for role in ("MANAGER", "OPERATOR", "ANALYST", "VIEWER",
                       "CSM", "SUPPORT"):
            with pytest.raises(HTTPException) as exc:
                _require_admin(role)
            assert exc.value.status_code == 403

    def test_none_role_blocked(self):
        with pytest.raises(HTTPException) as exc:
            _require_admin(None)
        assert exc.value.status_code == 403

    def test_empty_string_blocked(self):
        with pytest.raises(HTTPException):
            _require_admin("")


# ─── DTO shapes ──────────────────────────────────────────────────


class TestDtoShapes:
    def test_overview_aggregates_total(self):
        from ai_orchestrator.routers.dlq_console import DlqSummaryOut
        out = DlqOverviewOut(
            sources=[
                DlqSummaryOut(source="notification_outbox", dead_count=5),
                DlqSummaryOut(source="workflow_runs", dead_count=3),
            ],
            total=8,
        )
        assert out.total == sum(s.dead_count for s in out.sources)

    def test_dlq_item_serialisable(self):
        item = DlqItemOut(
            source="notification_outbox",
            id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            error_summary="SMTP timeout",
            payload={"recipient": "x@y.com", "attempts": 5},
        )
        d = item.model_dump()
        assert d["source"] == "notification_outbox"
        assert "x@y.com" in d["payload"]["recipient"]

    def test_action_out_required_fields(self):
        action = DlqActionOut(
            action="retry", source="notification_outbox",
            target_id="abc-123", success=True, detail="reset 1 row",
        )
        assert action.success is True


# ─── Endpoint: dlq_overview (mocked DB) ──────────────────────────


@pytest.mark.asyncio
class TestDlqOverview:
    async def test_aggregates_across_sources(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import dlq_overview

        counts = {
            "notification_outbox": 7,
            "workflow_chat_outbox": 2,
            "workflow_runs": 4,
            "workflow_email_intake": 1,
            "workflow_webhook_intake": 0,
        }

        class _Conn:
            def __init__(self):
                self.call_i = 0
                # Order matches the SQL list in dlq_overview
                self.order = [
                    "notification_outbox", "workflow_chat_outbox",
                    "workflow_runs", "workflow_email_intake",
                    "workflow_webhook_intake",
                ]
            async def fetchrow(self, sql):
                source = self.order[self.call_i]
                self.call_i += 1
                return {"n": counts[source]}

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await dlq_overview(
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert result.total == sum(counts.values())
        assert len(result.sources) == 5
        assert {s.source for s in result.sources} == set(counts.keys())

    async def test_blocks_non_admin(self):
        from ai_orchestrator.routers.dlq_console import dlq_overview
        with pytest.raises(HTTPException) as exc:
            await dlq_overview(
                x_enterprise_id=uuid4(),
                x_user_role="VIEWER",
            )
        assert exc.value.status_code == 403


# ─── Endpoint: list_dlq_items ────────────────────────────────────


@pytest.mark.asyncio
class TestListDlqItems:
    async def test_unknown_source_404(self):
        from ai_orchestrator.routers.dlq_console import list_dlq_items
        with pytest.raises(HTTPException) as exc:
            await list_dlq_items(
                source="something_random",
                x_enterprise_id=uuid4(),
                x_user_role="ADMIN",
            )
        assert exc.value.status_code == 404

    async def test_lists_notification_outbox(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import list_dlq_items

        class _Conn:
            async def fetch(self, sql, limit):
                return [{
                    "outbox_id": uuid4(),
                    "created_at": datetime.now(timezone.utc),
                    "last_error": "SMTP refused",
                    "recipient_email": "ops@kaori.vn",
                    "template": "workflow-freeform",
                    "attempts": 5,
                }]

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await list_dlq_items(
            source="notification_outbox",
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert len(result) == 1
        assert result[0].source == "notification_outbox"
        assert result[0].error_summary == "SMTP refused"
        assert result[0].payload["attempts"] == 5


# ─── Action: retry_notification ──────────────────────────────────


@pytest.mark.asyncio
class TestRetryNotification:
    async def test_retries_dead_row(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import retry_notification

        class _Conn:
            async def execute(self, sql, *a):
                assert "UPDATE notification_outbox" in sql
                assert "status = 'pending'" in sql
                return "UPDATE 1"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await retry_notification(
            outbox_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert result.success is True
        assert "reset 1 row" in result.detail

    async def test_404_when_not_dead(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import retry_notification

        class _Conn:
            async def execute(self, *a, **k): return "UPDATE 0"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(HTTPException) as exc:
            await retry_notification(
                outbox_id=uuid4(),
                x_enterprise_id=uuid4(),
                x_user_role="ADMIN",
            )
        assert exc.value.status_code == 404


# ─── Action: replay_workflow_run ─────────────────────────────────


@pytest.mark.asyncio
class TestReplayWorkflowRun:
    async def test_404_when_run_missing(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import replay_workflow_run
        from fastapi import BackgroundTasks

        class _Conn:
            async def fetchrow(self, *a, **k): return None
            async def execute(self, *a, **k): return "UPDATE 0"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(HTTPException) as exc:
            await replay_workflow_run(
                background_tasks=BackgroundTasks(),
                run_id=uuid4(),
                x_enterprise_id=uuid4(),
                x_user_role="ADMIN",
            )
        assert exc.value.status_code == 404

    async def test_409_when_run_not_failed(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import replay_workflow_run
        from fastapi import BackgroundTasks

        class _Conn:
            async def fetchrow(self, *a, **k):
                return {"status": "completed"}  # already done
            async def execute(self, *a, **k): return "UPDATE 0"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(HTTPException) as exc:
            await replay_workflow_run(
                background_tasks=BackgroundTasks(),
                run_id=uuid4(),
                x_enterprise_id=uuid4(),
                x_user_role="ADMIN",
            )
        assert exc.value.status_code == 409

    async def test_replays_failed_run(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import replay_workflow_run
        from fastapi import BackgroundTasks

        execute_called = {"n": 0}

        class _Conn:
            async def fetchrow(self, *a, **k):
                return {"status": "failed"}
            async def execute(self, sql, *a, **k):
                execute_called["n"] += 1
                assert "UPDATE workflow_runs" in sql
                return "UPDATE 1"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        bg = BackgroundTasks()
        result = await replay_workflow_run(
            background_tasks=bg,
            run_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert result.success is True
        assert execute_called["n"] == 1
        # background task scheduled
        assert len(bg.tasks) == 1


# ─── Action: requeue_intake ──────────────────────────────────────


@pytest.mark.asyncio
class TestRequeueIntake:
    async def test_unknown_kind_404(self):
        from ai_orchestrator.routers.dlq_console import requeue_intake
        with pytest.raises(HTTPException) as exc:
            await requeue_intake(
                kind="wrong",
                intake_id=uuid4(),
                x_enterprise_id=uuid4(),
                x_user_role="ADMIN",
            )
        assert exc.value.status_code == 404

    async def test_email_kind_works(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import requeue_intake

        class _Conn:
            async def execute(self, sql, *a):
                assert "workflow_email_intake" in sql
                return "UPDATE 1"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await requeue_intake(
            kind="email",
            intake_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert result.success is True

    async def test_webhook_kind_works(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import requeue_intake

        class _Conn:
            async def execute(self, sql, *a):
                assert "workflow_webhook_intake" in sql
                return "UPDATE 1"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await requeue_intake(
            kind="webhook",
            intake_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert result.success is True


# ─── Discard ─────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestDiscardNotification:
    async def test_discards_dead_row(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import discard_notification

        class _Conn:
            async def execute(self, sql, *a):
                assert "DELETE FROM notification_outbox" in sql
                return "DELETE 1"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await discard_notification(
            outbox_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
        )
        assert result.success is True
        assert "deleted 1" in result.detail

    async def test_404_when_no_dead(self, monkeypatch):
        from ai_orchestrator.routers.dlq_console import discard_notification

        class _Conn:
            async def execute(self, *a, **k): return "DELETE 0"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(HTTPException) as exc:
            await discard_notification(
                outbox_id=uuid4(),
                x_enterprise_id=uuid4(),
                x_user_role="ADMIN",
            )
        assert exc.value.status_code == 404


# ─── Phase 2.9 K-13 — Idempotency-Key coverage ────────────────────


@pytest.mark.asyncio
class TestIdempotencyKeyDlq:
    """K-13 coverage Phase 2.9: 5 DLQ ops endpoints accept
    Idempotency-Key header; duplicate Idempotency-Key returns cached
    response without re-firing the side effect."""

    async def test_short_circuit_returns_cached_when_duplicate(self, monkeypatch):
        """Second call with same Idempotency-Key returns cached payload
        without touching DB."""
        from ai_orchestrator.routers.dlq_console import retry_notification

        # Stub idempotency_store to simulate cache hit
        cached_payload = {
            "action": "retry",
            "source": "notification_outbox",
            "target_id": "00000000-0000-0000-0000-000000000001",
            "success": True,
            "detail": "reset 1 row(s) to pending (cached)",
        }

        class _Hit:
            cached = True
            response_payload = cached_payload

        async def _fake_get_or_set(**kwargs):
            return _Hit()

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)

        # acquire_for_tenant should NOT be called — short-circuit before DB
        call_count = {"db": 0}

        class _CM:
            async def __aenter__(self):
                call_count["db"] += 1
                raise AssertionError("DB should not be touched on cache hit")
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await retry_notification(
            outbox_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
            idempotency_key="TEST-IDEMPOTENCY-DUPLICATE",
        )
        assert result.success is True
        assert "cached" in result.detail
        assert call_count["db"] == 0

    async def test_records_outcome_when_first_call(self, monkeypatch):
        """First call: handler executes + records outcome via
        record_outcome() so future replays return the cached response."""
        from ai_orchestrator.routers.dlq_console import retry_notification

        class _Miss:
            cached = False
            response_payload = {}

        async def _fake_get_or_set(**kwargs):
            return _Miss()

        recorded = {}

        async def _fake_record(**kwargs):
            recorded.update(kwargs)

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)
        monkeypatch.setattr(_idem, "record_outcome", _fake_record)

        class _Conn:
            async def execute(self, *a, **k): return "UPDATE 1"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        tenant = uuid4()
        result = await retry_notification(
            outbox_id=uuid4(),
            x_enterprise_id=tenant,
            x_user_role="ADMIN",
            idempotency_key="TEST-IDEMPOTENCY-FIRSTCALL",
        )
        assert result.success is True
        # Verify record_outcome was called with our key
        assert recorded.get("key") == "TEST-IDEMPOTENCY-FIRSTCALL"
        assert recorded.get("enterprise_id") == tenant
        assert recorded.get("response_payload", {}).get("action") == "retry"

    async def test_no_idempotency_key_skips_helper(self, monkeypatch):
        """Backwards compat: missing Idempotency-Key header means caller
        opts out of K-13 ledger — handler executes normally without
        touching idempotency_store."""
        from ai_orchestrator.routers.dlq_console import retry_notification

        idem_calls = {"get_or_set": 0, "record_outcome": 0}

        async def _fail_get_or_set(**kwargs):
            idem_calls["get_or_set"] += 1
            raise AssertionError("should not call when no header")

        async def _fail_record(**kwargs):
            idem_calls["record_outcome"] += 1
            raise AssertionError("should not call when no header")

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fail_get_or_set)
        monkeypatch.setattr(_idem, "record_outcome", _fail_record)

        class _Conn:
            async def execute(self, *a, **k): return "UPDATE 1"
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.dlq_console as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        result = await retry_notification(
            outbox_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_role="ADMIN",
            idempotency_key=None,
        )
        assert result.success is True
        assert idem_calls["get_or_set"] == 0
        assert idem_calls["record_outcome"] == 0
