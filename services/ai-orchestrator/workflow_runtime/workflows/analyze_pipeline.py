"""
analyze_pipeline workflow — the reference workflow for P15-S9 D3.

Five activities executed in sequence, one per side-effect class. Each
activity ships from workflow_runtime.activities.analyze; the workflow
here is responsible only for orchestration (sequence, retries, saga
compensation on the external step).

Why so simple
=============
The point of this workflow is to exercise the contract surface end-to-
end inside ``temporalio.testing.WorkflowEnvironment`` so the K-17
declarations on activities + matching YAML nodes are verified together.
Real product workflows (churn_detection etc.) compose more activities
+ branch on results — they ship after the testing infra is live.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

# Import activity references through the workflow.unsafe pattern. The
# Temporal SDK forbids importing modules with non-deterministic side
# effects (random, datetime, db) inside the workflow body; activities
# are referenced by their decorated function so the imports here are
# safe — they just expose the function signature for type-checking.
with workflow.unsafe.imports_passed_through():
    from ..activities.analyze import (
        AnalyzeInput,
        StatusUpdate,
        insert_decision_audit,
        load_pipeline_run,
        parse_input,
        send_completion_notification,
        upsert_run_status,
    )


# Per-class retry policies — taken verbatim from the strategic doc
# (WORKFLOW_SYSTEM.md Phần 33.1). Different classes deserve different
# attempt counts + intervals: external_irreversible can only be retried
# once because the side effect can't be undone, while write_idempotent
# can ride out a longer transient outage because the key dedups.
#
# Helper functions below build the SDK RetryPolicy lazily — keeps this
# module importable without temporalio installed (matches the pattern
# used across workflow_runtime/).
_RETRY_POLICIES = {
    # pure / read_only: cheap retries, can run often.
    "pure": dict(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=3,
    ),
    "read_only": dict(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=3,
    ),
    # write_idempotent: dedup-safe → highest attempt count.
    "write_idempotent": dict(
        initial_interval=timedelta(seconds=2),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=120),
        maximum_attempts=5,
    ),
    # write_non_idempotent: idempotency_records handles dedup → fewer
    # attempts, shorter ceiling so retry storms can't pile up.
    "write_non_idempotent": dict(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=30),
        maximum_attempts=3,
    ),
    # external (irreversible): conservative — 1 retry, fixed delay.
    # If the provider supports an idempotency key (Stripe, SendGrid)
    # we'd raise this; default policy assumes none.
    "external": dict(
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=1.0,
        maximum_interval=timedelta(seconds=5),
        maximum_attempts=1,
    ),
}


@workflow.defn(name="analyze_pipeline", sandboxed=False)
class AnalyzePipelineWorkflow:
    """Orchestrates the 5-step analyze flow.

    The class is instantiated per workflow execution by Temporal; instance
    state lives only for the duration of the run. Persistence is the
    history events Temporal records as each activity completes.

    `sandboxed=False`: the ai-orchestrator service directory is named
    with a hyphen (`ai-orchestrator`), so we register the package as
    `ai_orchestrator` synthetically in tests/conftest.py. Temporal's
    workflow sandbox uses its own importer that doesn't see the
    synthetic — it tries a fresh import + fails. Disabling the sandbox
    is the right call here: the workflow body only awaits activities
    (no random/datetime/db inside the workflow itself), so the sandbox
    safety net adds no value for this workflow shape. Phase B-3
    rename of the service folder lets us flip this back on.
    """

    @workflow.run
    async def run(self, payload: dict) -> dict:
        # Step 1 — pure: shape + validate the payload.
        input_: AnalyzeInput = await workflow.execute_activity(
            parse_input,
            payload,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=_retry_policy_for("pure"),
        )

        # Step 2 — read_only: confirm the run exists.
        snapshot = await workflow.execute_activity(
            load_pipeline_run,
            input_,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_retry_policy_for("read_only"),
        )

        # Step 3 — write_idempotent: mark the run as 'running'.
        running: StatusUpdate = await workflow.execute_activity(
            upsert_run_status,
            args=[input_, "running"],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_retry_policy_for("write_idempotent"),
        )

        # Step 4 — write_non_idempotent: append a decision-audit row.
        # Action Runtime in Phase 1.5+ wraps this with idempotency_records
        # so a retry hits the dedup cache; for the contract test the
        # activity stub returns a deterministic id.
        audit_id = await workflow.execute_activity(
            insert_decision_audit,
            args=[input_, "analyze_started", {"snapshot": snapshot.status}],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=_retry_policy_for("write_non_idempotent"),
        )

        # Step 5 — write_idempotent: mark the run 'complete'.
        complete: StatusUpdate = await workflow.execute_activity(
            upsert_run_status,
            args=[input_, "complete"],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_retry_policy_for("write_idempotent"),
        )

        # Step 6 — external: notify (subject to saga compensation).
        notif = await workflow.execute_activity(
            send_completion_notification,
            args=[input_, complete],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_retry_policy_for("external"),
        )

        return {
            "run_id": input_.run_id,
            "tenant_id": input_.tenant_id,
            "audit_id": audit_id,
            "final_status": complete.new_status,
            "notification": notif,
            "running_state_recorded": running.new_status,
        }


def _retry_policy_for(side_effect_class: str):
    """Build the SDK RetryPolicy for the named K-17 class.

    Strategic doc Phần 33.1 spec — see _RETRY_POLICIES above for the
    per-class numbers. Unknown classes raise so a typo on a new
    activity surfaces at first execution instead of silently using a
    wrong default.
    """
    from temporalio.common import RetryPolicy

    if side_effect_class not in _RETRY_POLICIES:
        raise ValueError(
            f"no retry policy for side_effect_class={side_effect_class!r}; "
            f"known: {sorted(_RETRY_POLICIES.keys())}"
        )
    return RetryPolicy(**_RETRY_POLICIES[side_effect_class])
