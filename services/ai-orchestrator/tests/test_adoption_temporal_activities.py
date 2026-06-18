"""
Tests for adoption_hourly_aggregator activities + workflow wiring.

The actual cron fires inside Temporal cluster (covered by e2e suite).
These tests pin the activity logic with monkeypatched DB + HTTP.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from ai_orchestrator.workflow_runtime.activities.adoption import (
    HealthSnapshotResult,
    TenantHealthTask,
    persist_health_snapshot,
    trigger_intervention_if_needed,
)


class TestPersistHealthSnapshot:
    @pytest.mark.asyncio
    async def test_error_short_circuits_persist(self, monkeypatch):
        """If compute produced an error, persist is a no-op."""
        bad = HealthSnapshotResult(
            enterprise_id=str(uuid4()),
            health_score=0.0,
            classification="unknown",
            intervention_triggered=False,
            error="compute failed",
        )

        called = {"count": 0}

        class _Conn:
            async def execute(self, *a, **k):
                called["count"] += 1

        class _CM:
            async def __aenter__(self):
                return _Conn()
            async def __aexit__(self, *a):
                return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        out = await persist_health_snapshot(bad)
        assert out.error == "compute failed"
        assert called["count"] == 0  # no DB write attempted

    @pytest.mark.asyncio
    async def test_success_calls_upsert(self, monkeypatch):
        good = HealthSnapshotResult(
            enterprise_id=str(uuid4()),
            health_score=0.42,
            classification="stretched",
            intervention_triggered=False,
        )
        called = {"count": 0}

        class _Conn:
            async def execute(self, sql, *args):
                called["count"] += 1
                assert "INSERT INTO adoption_health_snapshots" in sql
                assert args[1] == 0.42
                assert args[2] == "stretched"

        class _CM:
            async def __aenter__(self):
                return _Conn()
            async def __aexit__(self, *a):
                return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        out = await persist_health_snapshot(good)
        assert called["count"] == 1
        assert out.health_score == 0.42


class TestTriggerInterventionIfNeeded:
    @pytest.mark.asyncio
    async def test_healthy_skips(self):
        """classification != at_risk/churn_imminent → no HTTP call."""
        result = HealthSnapshotResult(
            enterprise_id=str(uuid4()),
            health_score=0.85,
            classification="healthy",
            intervention_triggered=False,
        )
        out = await trigger_intervention_if_needed(result)
        assert out.intervention_triggered is False
        assert out.error is None

    @pytest.mark.asyncio
    async def test_error_short_circuits(self):
        result = HealthSnapshotResult(
            enterprise_id=str(uuid4()),
            health_score=0.0,
            classification="at_risk",
            intervention_triggered=False,
            error="earlier failure",
        )
        out = await trigger_intervention_if_needed(result)
        assert out.intervention_triggered is False
        assert out.error == "earlier failure"

    @pytest.mark.asyncio
    async def test_at_risk_triggers_http_call(self, monkeypatch):
        captured = {"posted": False, "body": None, "headers": None}

        class _Resp:
            def raise_for_status(self):
                return None

        class _Client:
            def __init__(self, *a, **k):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def post(self, url, *, json, headers):
                captured["posted"] = True
                captured["body"] = json
                captured["headers"] = headers
                return _Resp()

        import ai_orchestrator.workflow_runtime.activities.adoption as _mod
        monkeypatch.setattr(_mod.httpx, "AsyncClient", _Client)

        result = HealthSnapshotResult(
            enterprise_id=str(uuid4()),
            health_score=0.18,
            classification="at_risk",
            intervention_triggered=False,
        )
        out = await trigger_intervention_if_needed(result)
        assert captured["posted"] is True
        assert captured["body"]["intervention_type"] == "auto_health_drop"
        assert captured["headers"]["X-Enterprise-Id"] == result.enterprise_id
        assert "Idempotency-Key" in captured["headers"]
        assert out.intervention_triggered is True

    @pytest.mark.asyncio
    async def test_http_failure_recorded(self, monkeypatch):
        class _Client:
            def __init__(self, *a, **k):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def post(self, *a, **k):
                raise ConnectionError("unreachable")

        import ai_orchestrator.workflow_runtime.activities.adoption as _mod
        monkeypatch.setattr(_mod.httpx, "AsyncClient", _Client)

        result = HealthSnapshotResult(
            enterprise_id=str(uuid4()),
            health_score=0.05,
            classification="churn_imminent",
            intervention_triggered=False,
        )
        out = await trigger_intervention_if_needed(result)
        assert out.intervention_triggered is False
        assert out.error is not None
        assert "ConnectionError" in out.error


class TestWorkflowRegistration:
    def test_adoption_hourly_in_all_workflows(self):
        from ai_orchestrator.workflow_runtime.workflows import ALL_WORKFLOWS
        names = [w.__name__ for w in ALL_WORKFLOWS]
        assert "AdoptionHourlyAggregatorWorkflow" in names

    def test_adoption_activities_in_all_activities(self):
        from ai_orchestrator.workflow_runtime.activities import ALL_ACTIVITIES
        # Activities are temporalio decorated functions — read their .name
        names = []
        for a in ALL_ACTIVITIES:
            # @activity.defn assigns __temporal_activity_definition__ with name
            tdef = getattr(a, "__temporal_activity_definition__", None)
            if tdef is not None:
                names.append(tdef.name)
            else:
                names.append(getattr(a, "__name__", str(a)))
        for needed in (
            "list_active_tenants_for_adoption",
            "compute_tenant_health_snapshot",
            "persist_health_snapshot",
            "trigger_intervention_if_needed",
        ):
            assert needed in names, f"{needed} missing from ALL_ACTIVITIES (got {names})"
