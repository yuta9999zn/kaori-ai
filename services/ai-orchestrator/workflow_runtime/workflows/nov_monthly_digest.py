"""
nov_monthly_digest workflow — P15-S9 D7 reference.

Runs once per month per tenant. Sequence:

  1. gather_nov_inputs           read_only
  2. compute_nov_for_month       pure
  3. persist_nov_digest          write_idempotent
  4. maybe_dispatch_negative_alert  external (NOV-CORE-016)

Scheduling
==========
The workflow is intended to be triggered by a Temporal Schedule
(temporal CLI: `temporal schedule create --cron "0 0 1 * *"
--workflow-id nov-monthly-{enterprise} --task-queue kaori-default
--type nov_monthly_digest`). Phase 1.5 D7 ships the workflow
definition; the schedule itself lands when D8 cluster verification
finishes (sched lives in Temporal cluster state, not in repo).

Per-class retry policies match the strategic doc Phần 33.1:
  pure / read_only       3 attempts
  write_idempotent       5 attempts
  external               1 attempt, fixed 5s delay
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ..activities.economics import (
        NOVDigestPayload,
        NOVInputs,
        compute_nov_for_month,
        gather_nov_inputs,
        maybe_dispatch_negative_alert,
        persist_nov_digest,
    )


_RETRY_POLICIES = {
    "pure":             dict(initial_interval=timedelta(seconds=1),
                             backoff_coefficient=2.0,
                             maximum_interval=timedelta(seconds=60),
                             maximum_attempts=3),
    "read_only":        dict(initial_interval=timedelta(seconds=1),
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


def _retry_policy_for(side_effect_class: str):
    """Build the SDK RetryPolicy lazily (matches analyze_pipeline pattern)."""
    from temporalio.common import RetryPolicy
    return RetryPolicy(**_RETRY_POLICIES[side_effect_class])


@workflow.defn(name="nov_monthly_digest", sandboxed=False)
class NovMonthlyDigestWorkflow:
    """Monthly NOV computation per (enterprise, month).

    sandboxed=False — same reason as AnalyzePipelineWorkflow (the
    synthetic ai_orchestrator package doesn't survive the workflow
    sandbox importer; flip back on after Phase B-3 service rename).
    """

    @workflow.run
    async def run(self, enterprise_id: str, month_start: str) -> dict:
        # 1 — read_only: pull upstream rows
        inputs: NOVInputs = await workflow.execute_activity(
            gather_nov_inputs,
            args=[enterprise_id, month_start],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_retry_policy_for("read_only"),
        )

        # 2 — pure: aggregate to a digest payload
        digest: NOVDigestPayload = await workflow.execute_activity(
            compute_nov_for_month,
            inputs,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_retry_policy_for("pure"),
        )

        # 3 — write_idempotent: UPSERT the digest row
        persisted = await workflow.execute_activity(
            persist_nov_digest,
            digest,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=_retry_policy_for("write_idempotent"),
        )

        # 4 — external: alert when NOV is negative (best-effort)
        alert = await workflow.execute_activity(
            maybe_dispatch_negative_alert,
            persisted,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=_retry_policy_for("external"),
        )

        return {
            "enterprise_id": enterprise_id,
            "month_start": month_start,
            "nov_vnd": digest.nov_vnd,
            "is_negative": persisted.get("is_negative", False),
            "revision": persisted.get("revision", 1),
            "alert": alert,
        }
