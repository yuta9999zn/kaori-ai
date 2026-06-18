"""Temporal activity + workflow tests for Stage 7 Memory + Stage 12 Loop.

Uses temporalio.testing.ActivityEnvironment to invoke activities
directly without spinning a worker. Workflows themselves are exercised
via temporalio.testing.WorkflowEnvironment when available, OR by
asserting their composition (workflow class + activity registration).

Pure Python, no Temporal cluster.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from temporalio.testing import ActivityEnvironment

from ai_orchestrator.workflow_runtime.activities.memory_loop import (
    LoopEvaluateTask,
    SIDE_EFFECT_CLASS,
    TenantTask,
    loop_evaluate_for_tenant,
    memory_consolidate_for_tenant,
    memory_embed_pending_for_tenant,
    memory_forget_sweep_for_tenant,
    memory_promote_for_tenant,
    memory_promote_kb_for_tenant,
)


T1 = "11111111-1111-1111-1111-111111111111"


# ─── K-17 side_effect_class declarations ────────────────────────────


class TestSideEffectClassDeclarations:
    """K-17: every new activity carries a side_effect_class for the
    retry-policy picker. Test locks the table so a future activity
    addition that forgets the entry breaks CI."""

    def test_all_activities_declared(self):
        assert set(SIDE_EFFECT_CLASS.keys()) == {
            "memory_consolidate_for_tenant",
            "memory_promote_for_tenant",
            "memory_promote_kb_for_tenant",
            "memory_forget_sweep_for_tenant",
            "memory_embed_pending_for_tenant",
            "loop_evaluate_for_tenant",
        }

    def test_classes_in_known_vocab(self):
        allowed = {"pure", "read_only", "write_idempotent",
                    "write_non_idempotent", "external"}
        assert all(v in allowed for v in SIDE_EFFECT_CLASS.values())

    def test_embedding_activity_is_external(self):
        """embed_pending hits llm-gateway over HTTP — class MUST be
        external so the 1-attempt-only retry policy fires."""
        assert SIDE_EFFECT_CLASS["memory_embed_pending_for_tenant"] == "external"

    def test_eval_activity_is_read_only(self):
        """The evaluate activity SELECTs only — no writes. Class read_only."""
        assert SIDE_EFFECT_CLASS["loop_evaluate_for_tenant"] == "read_only"


# ─── consolidate activity ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_consolidate_activity_calls_memory_service():
    """The activity composes _build_memory_service + invokes
    .consolidate(); we patch the factory and assert the call."""
    env = ActivityEnvironment()
    svc = MagicMock()
    svc.consolidate = AsyncMock(return_value=7)
    with patch("ai_orchestrator.workflow_runtime.activities.memory_loop._build_memory_service",
                return_value=svc):
        result = await env.run(memory_consolidate_for_tenant, TenantTask(tenant_id=T1))
    assert result.activity == "memory_consolidate_for_tenant"
    assert result.tenant_id == T1
    assert result.count == 7
    svc.consolidate.assert_awaited_once_with(UUID(T1))


@pytest.mark.asyncio
async def test_promote_activity_calls_memory_service():
    env = ActivityEnvironment()
    svc = MagicMock()
    svc.promote = AsyncMock(return_value=3)
    with patch("ai_orchestrator.workflow_runtime.activities.memory_loop._build_memory_service",
                return_value=svc):
        result = await env.run(memory_promote_for_tenant, TenantTask(tenant_id=T1))
    assert result.count == 3
    svc.promote.assert_awaited_once_with(UUID(T1))


@pytest.mark.asyncio
async def test_promote_kb_activity_calls_service_with_knowledge_store():
    """ADR-0036 — the cron activity composes _build_memory_service +
    _build_knowledge_store and invokes promote_to_knowledge with that store."""
    env = ActivityEnvironment()
    svc = MagicMock()
    svc.promote_to_knowledge = AsyncMock(return_value=2)
    kb = MagicMock()
    with patch("ai_orchestrator.workflow_runtime.activities.memory_loop._build_memory_service",
                return_value=svc), \
         patch("ai_orchestrator.workflow_runtime.activities.memory_loop._build_knowledge_store",
                return_value=kb):
        result = await env.run(memory_promote_kb_for_tenant, TenantTask(tenant_id=T1))
    assert result.activity == "memory_promote_kb_for_tenant"
    assert result.count == 2
    svc.promote_to_knowledge.assert_awaited_once_with(UUID(T1), knowledge_store=kb)


@pytest.mark.asyncio
async def test_forget_sweep_activity_calls_memory_service():
    env = ActivityEnvironment()
    svc = MagicMock()
    svc.forget = AsyncMock(return_value=12)
    with patch("ai_orchestrator.workflow_runtime.activities.memory_loop._build_memory_service",
                return_value=svc):
        result = await env.run(memory_forget_sweep_for_tenant, TenantTask(tenant_id=T1))
    assert result.count == 12


# ─── embed activity ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_pending_activity_calls_worker():
    """The activity composes PostgresTierStore + calls
    embed_pending_for_tenant. Patch at the SOURCE module (the
    activity imports inline at call time)."""
    env = ActivityEnvironment()
    with patch("ai_orchestrator.reasoning.memory.embedding_worker"
                ".embed_pending_for_tenant",
                new=AsyncMock(return_value=5)) as mock_worker, \
         patch("ai_orchestrator.reasoning.memory.postgres_l3"
                ".PostgresTierStore") as mock_store_cls, \
         patch("ai_orchestrator.shared.db.acquire_for_tenant",
                new=AsyncMock()):
        mock_store_cls.return_value = MagicMock()
        result = await env.run(memory_embed_pending_for_tenant, TenantTask(tenant_id=T1))
    assert result.count == 5
    mock_worker.assert_awaited_once()


# ─── loop evaluate activity ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_loop_evaluate_activity_runs_framework_and_engine():
    env = ActivityEnvironment()
    tracker = MagicMock()
    from datetime import datetime, timezone
    from ai_orchestrator.org_intel.loop.ab_test import ABTestResult
    from ai_orchestrator.org_intel.loop.baseline import BaselineSummary
    summary = BaselineSummary(
        tenant_id=UUID(T1), metric_name="m",
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        sample_size=40, mean=0.1, variance=0.01, stddev=0.1,
    )
    fake_result = ABTestResult(
        tenant_id=UUID(T1), experiment_id="exp-1", metric_name="m",
        control=summary, treatment=summary,
        relative_lift=0.0, t_statistic=0.0,
        conclusion="inconclusive", reason="x",
        computed_at=datetime.now(timezone.utc),
    )

    with patch("ai_orchestrator.workflow_runtime.activities.memory_loop"
                "._build_baseline_tracker", return_value=tracker), \
         patch("ai_orchestrator.org_intel.loop.ABTestFramework") as mock_fw_cls:
        mock_fw_cls.return_value.evaluate = MagicMock(return_value=fake_result)
        out = await env.run(loop_evaluate_for_tenant, LoopEvaluateTask(
            tenant_id=T1, experiment_id="exp-1", metric_name="m",
        ))
    assert out.conclusion == "inconclusive"
    assert out.experiment_id == "exp-1"
    # decision_id is a UUID string
    UUID(out.decision_id)


# ─── Workflow registration ──────────────────────────────────────────


class TestWorkflowRegistration:
    """Each new workflow must show up in ALL_WORKFLOWS so the worker
    actually registers it."""

    def test_memory_maintenance_in_all_workflows(self):
        from ai_orchestrator.workflow_runtime.workflows import (
            ALL_WORKFLOWS,
            MemoryMaintenanceWorkflow,
        )
        assert MemoryMaintenanceWorkflow in ALL_WORKFLOWS

    def test_loop_ab_evaluate_in_all_workflows(self):
        from ai_orchestrator.workflow_runtime.workflows import (
            ALL_WORKFLOWS,
            LoopABEvaluateWorkflow,
        )
        assert LoopABEvaluateWorkflow in ALL_WORKFLOWS

    def test_forget_sweep_in_all_workflows(self):
        from ai_orchestrator.workflow_runtime.workflows import (
            ALL_WORKFLOWS,
            MemoryForgetSweepWorkflow,
        )
        assert MemoryForgetSweepWorkflow in ALL_WORKFLOWS

    def test_all_activities_in_all_activities(self):
        from ai_orchestrator.workflow_runtime.activities import (
            ALL_ACTIVITIES,
            loop_evaluate_for_tenant,
            memory_consolidate_for_tenant,
            memory_embed_pending_for_tenant,
            memory_forget_sweep_for_tenant,
            memory_promote_for_tenant,
            memory_promote_kb_for_tenant,
        )
        assert memory_consolidate_for_tenant in ALL_ACTIVITIES
        assert memory_promote_for_tenant in ALL_ACTIVITIES
        assert memory_promote_kb_for_tenant in ALL_ACTIVITIES
        assert memory_forget_sweep_for_tenant in ALL_ACTIVITIES
        assert memory_embed_pending_for_tenant in ALL_ACTIVITIES
        assert loop_evaluate_for_tenant in ALL_ACTIVITIES
