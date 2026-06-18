"""
adoption_hourly_aggregator workflow — Temporal cron.

Runs every hour. Fans out one activity per active tenant to compute
health snapshot + persist + maybe trigger intervention.

Schedule (set via Temporal CLI after worker boots):
    temporal schedule create \\
        --schedule-id adoption-hourly \\
        --cron "0 * * * *" \\
        --workflow-id adoption-hourly-aggregator \\
        --task-queue kaori-default \\
        --type adoption_hourly_aggregator

Per-class retry policies match strategic doc Phần 33.1.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ..activities.adoption import (
        HealthSnapshotResult,
        TenantHealthTask,
        compute_tenant_health_snapshot,
        list_active_tenants_for_adoption,
        persist_health_snapshot,
        trigger_intervention_if_needed,
    )


_RETRY = {
    "read_only":        dict(initial_interval=timedelta(seconds=1),
                              backoff_coefficient=2.0,
                              maximum_interval=timedelta(seconds=60),
                              maximum_attempts=3),
    "pure":             dict(initial_interval=timedelta(seconds=1),
                              backoff_coefficient=2.0,
                              maximum_interval=timedelta(seconds=60),
                              maximum_attempts=3),
    "write_idempotent": dict(initial_interval=timedelta(seconds=2),
                              backoff_coefficient=2.0,
                              maximum_interval=timedelta(seconds=120),
                              maximum_attempts=5),
    "external":         dict(initial_interval=timedelta(seconds=5),
                              backoff_coefficient=1.0,
                              maximum_interval=timedelta(seconds=5),
                              maximum_attempts=1),
}


@workflow.defn(name="adoption_hourly_aggregator")
class AdoptionHourlyAggregatorWorkflow:
    """Fan-out per-tenant adoption snapshot computation."""

    @workflow.run
    async def run(self) -> dict[str, int]:
        # 1) Pull tenants that need a snapshot
        tasks: list[TenantHealthTask] = await workflow.execute_activity(
            list_active_tenants_for_adoption,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=workflow.RetryPolicy(**_RETRY["read_only"]),
        )

        snapshots_taken = 0
        interventions_triggered = 0
        failures = 0

        for task in tasks:
            try:
                result: HealthSnapshotResult = await workflow.execute_activity(
                    compute_tenant_health_snapshot,
                    task,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=workflow.RetryPolicy(**_RETRY["pure"]),
                )
                result = await workflow.execute_activity(
                    persist_health_snapshot,
                    result,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=workflow.RetryPolicy(**_RETRY["write_idempotent"]),
                )
                result = await workflow.execute_activity(
                    trigger_intervention_if_needed,
                    result,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=workflow.RetryPolicy(**_RETRY["external"]),
                )
                if result.error:
                    failures += 1
                else:
                    snapshots_taken += 1
                    if result.intervention_triggered:
                        interventions_triggered += 1
            except Exception:  # noqa: BLE001
                # One bad tenant must not abort the fan-out — record + continue.
                failures += 1

        return {
            "tenants_processed":          len(tasks),
            "snapshots_taken":            snapshots_taken,
            "interventions_triggered":    interventions_triggered,
            "failures":                   failures,
        }
