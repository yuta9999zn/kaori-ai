"""
Two Temporal workflows for Stage 7 Memory + Stage 12 Loop scheduling.

Workflows
---------
  MemoryMaintenanceWorkflow
    Daily cron per tenant. Composes consolidate (L2→L3) → promote
    (L3→L4) → embed-pending (bg vectoriser). TTL sweep runs as a
    weekly child schedule (separate workflow LoopForgetSweepWorkflow
    below).

  LoopABEvaluateWorkflow
    Daily cron per (tenant, experiment_id, metric_name). Returns
    a LoopEvaluateResult with the PromotionDecision summary.

Scheduling
----------
The workflows live in code; the schedules live in Temporal cluster
state (created via `temporal schedule create`). Phase 1.5 ships the
workflow definitions; the schedule itself lands when the cluster is
verified (per D8 plan).

Gated by TEMPORAL_ENABLE_WORKER (default false).
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ..activities.memory_loop import (
        LoopEvaluateResult,
        LoopEvaluateTask,
        TenantBatchResult,
        TenantTask,
        loop_evaluate_for_tenant,
        memory_consolidate_for_tenant,
        memory_embed_pending_for_tenant,
        memory_forget_sweep_for_tenant,
        memory_promote_for_tenant,
        memory_promote_kb_for_tenant,
    )


# Match the analyse / NOV workflows' policy bands (Phần 33.1).
_RETRY = {
    "read_only": dict(maximum_attempts=3,
                       initial_interval=timedelta(seconds=1),
                       backoff_coefficient=2.0,
                       maximum_interval=timedelta(seconds=60)),
    "write_idempotent": dict(maximum_attempts=5,
                               initial_interval=timedelta(seconds=2),
                               backoff_coefficient=2.0,
                               maximum_interval=timedelta(seconds=120)),
    "external": dict(maximum_attempts=1,
                      initial_interval=timedelta(seconds=5),
                      backoff_coefficient=1.0,
                      maximum_interval=timedelta(seconds=5)),
}


def _retry(side_effect_class: str):
    from temporalio.common import RetryPolicy
    return RetryPolicy(**_RETRY[side_effect_class])


@workflow.defn(name="memory_maintenance", sandboxed=False)
class MemoryMaintenanceWorkflow:
    """Daily per-tenant memory maintenance. consolidate → promote →
    embed. Each step has its own retry policy."""

    @workflow.run
    async def run(self, tenant_id: str) -> dict:
        task = TenantTask(tenant_id=tenant_id)

        consolidated: TenantBatchResult = await workflow.execute_activity(
            memory_consolidate_for_tenant, task,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_retry("write_idempotent"),
        )
        promoted: TenantBatchResult = await workflow.execute_activity(
            memory_promote_for_tenant, task,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_retry("write_idempotent"),
        )
        # ADR-0036 — feed mature, validated memory into the tenant KB so the
        # coverage gate ("học 1 hiểu 10") grows as the tenant accrues experience.
        promoted_kb: TenantBatchResult = await workflow.execute_activity(
            memory_promote_kb_for_tenant, task,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_retry("write_idempotent"),
        )
        embedded: TenantBatchResult = await workflow.execute_activity(
            memory_embed_pending_for_tenant, task,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=_retry("external"),
        )
        return {
            "tenant_id":   tenant_id,
            "consolidated": consolidated.count,
            "promoted":     promoted.count,
            "promoted_kb":  promoted_kb.count,
            "embedded":     embedded.count,
        }


@workflow.defn(name="memory_forget_sweep", sandboxed=False)
class MemoryForgetSweepWorkflow:
    """Weekly L3 TTL sweep — separate from daily maintenance so it
    can run on a different cadence + alert separately."""

    @workflow.run
    async def run(self, tenant_id: str) -> dict:
        task = TenantTask(tenant_id=tenant_id)
        result: TenantBatchResult = await workflow.execute_activity(
            memory_forget_sweep_for_tenant, task,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_retry("write_idempotent"),
        )
        return {
            "tenant_id": tenant_id,
            "wiped":     result.count,
        }


@workflow.defn(name="loop_ab_evaluate", sandboxed=False)
class LoopABEvaluateWorkflow:
    """Daily per (tenant, experiment_id, metric_name). Computes the
    A/B conclusion + promotion decision."""

    @workflow.run
    async def run(self, tenant_id: str, experiment_id: str,
                  metric_name: str) -> dict:
        task = LoopEvaluateTask(
            tenant_id=tenant_id,
            experiment_id=experiment_id,
            metric_name=metric_name,
        )
        result: LoopEvaluateResult = await workflow.execute_activity(
            loop_evaluate_for_tenant, task,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_retry("read_only"),
        )
        return {
            "tenant_id":     result.tenant_id,
            "experiment_id": result.experiment_id,
            "metric_name":   result.metric_name,
            "conclusion":    result.conclusion,
            "action":        result.action,
            "decision_id":   result.decision_id,
        }
