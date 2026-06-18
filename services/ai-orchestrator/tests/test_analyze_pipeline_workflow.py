"""
End-to-end workflow test using temporalio.testing.WorkflowEnvironment.

The test environment runs an in-memory Temporal server + worker so the
full @workflow.defn / @activity.defn dance executes without docker.
Each test gets a fresh environment so workflows from one test never
bleed into another.
"""
from __future__ import annotations

import pytest

pytest.importorskip("temporalio")

from temporalio.client import Client  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from ai_orchestrator.workflow_runtime.activities import ALL_ACTIVITIES  # noqa: E402
from ai_orchestrator.workflow_runtime.workflows import AnalyzePipelineWorkflow  # noqa: E402


_TASK_QUEUE = "test-analyze-pipeline"


@pytest.mark.asyncio
async def test_analyze_pipeline_workflow_happy_path():
    """Happy path — all 5 activities execute in order, workflow returns
    the composite result. Validates K-17 contract end-to-end: every
    side_effect_class participates without breaking the orchestration."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        client: Client = env.client
        async with Worker(
            client,
            task_queue=_TASK_QUEUE,
            workflows=[AnalyzePipelineWorkflow],
            activities=list(ALL_ACTIVITIES),
        ):
            result = await client.execute_workflow(
                AnalyzePipelineWorkflow.run,
                {
                    "tenant_id": "tenant-test",
                    "run_id": "run-001",
                    "templates": ["churn_v1", "cohort_v1"],
                    "config": {"window_days": 90},
                },
                id="test-wf-happy-path",
                task_queue=_TASK_QUEUE,
            )

    assert result["run_id"] == "run-001"
    assert result["tenant_id"] == "tenant-test"
    assert result["final_status"] == "complete"
    assert result["running_state_recorded"] == "running"
    # write_non_idempotent activity returned a deterministic id keyed on
    # run + decision_type — exercises the audit-row reference contract.
    assert result["audit_id"] == "audit-run-001-analyze_started"
    # external activity stub returned a synthetic ack
    assert result["notification"]["delivered"] is True
    assert result["notification"]["channel"] == "stub"


@pytest.mark.asyncio
async def test_analyze_pipeline_workflow_invalid_payload_fails_fast():
    """parse_input is the pure first node — a malformed payload must
    surface the failure before any side effect fires. The workflow
    should NOT run upsert/insert/notify activities when input is bad."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        client: Client = env.client
        async with Worker(
            client,
            task_queue=_TASK_QUEUE,
            workflows=[AnalyzePipelineWorkflow],
            activities=list(ALL_ACTIVITIES),
        ):
            with pytest.raises(Exception) as excinfo:
                await client.execute_workflow(
                    AnalyzePipelineWorkflow.run,
                    {"tenant_id": "tenant-test"},  # missing run_id + templates
                    id="test-wf-bad-payload",
                    task_queue=_TASK_QUEUE,
                )

    # WorkflowFailureError wraps the activity's ApplicationError which
    # wraps the ValueError. Walk the chain to find the original message.
    chain_text = []
    cur: BaseException | None = excinfo.value
    while cur is not None:
        chain_text.append(repr(cur))
        chain_text.append(str(cur))
        cur = cur.__cause__ or cur.__context__
    joined = " | ".join(chain_text).lower()
    assert "missing keys" in joined or "run_id" in joined or "templates" in joined, (
        f"expected parse_input failure message in cause chain, got: {joined}"
    )
