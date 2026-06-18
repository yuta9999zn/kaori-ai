"""
Tests for the NOV monthly digest workflow + activities.

Coverage:
  * compute_nov_for_month — pure unit test (no Temporal env needed).
  * persist_nov_digest stub returns expected shape.
  * maybe_dispatch_negative_alert dispatches only when nov_vnd < 0.
  * NovMonthlyDigestWorkflow end-to-end via WorkflowEnvironment.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

pytest.importorskip("temporalio")

from temporalio.client import Client  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from ai_orchestrator.workflow_runtime.activities import ALL_ACTIVITIES  # noqa: E402
from ai_orchestrator.workflow_runtime.activities.economics import (  # noqa: E402
    NOVInputs,
    compute_nov_for_month,
    maybe_dispatch_negative_alert,
    persist_nov_digest,
)
from ai_orchestrator.workflow_runtime.workflows import NovMonthlyDigestWorkflow  # noqa: E402


_TASK_QUEUE = "test-nov-monthly"


# ─── Activity unit tests (no Temporal env needed) ────────────────────


@pytest.mark.asyncio
async def test_compute_nov_for_month_aggregates_4_costs():
    """Sum of 4 cost components + revenue → NOV. Verifies the activity
    delegates to the right estimators with the right kwargs (catches a
    signature drift like the one we hit during D7 implementation)."""
    inputs = NOVInputs(
        enterprise_id="ent-1",
        month_start="2026-04-01",
        revenue_30d_before_vnd="100000000",   # 100M baseline
        revenue_30d_after_vnd="120000000",    # 120M post = 20M delta
        people_hours_required="40",
        people_hourly_rate_vnd="200000",       # 40 * 200K = 8M VND
        ai_tokens_input=400_000,
        ai_tokens_output=100_000,
        ai_cost_per_1k_input_vnd="40",         # 400 * 40 = 16K
        ai_cost_per_1k_output_vnd="80",        # 100 * 80 = 8K → 24K total AI
        infra_compute_hours="720",             # 720 * 100 = 72K
        infra_storage_gb_month="50",           # 50 * 1000 = 50K → 122K total infra
        integration_api_calls=10_000,
        integration_cost_per_call_vnd="10",    # 10K * 10 = 100K
    )
    payload = await compute_nov_for_month(inputs)

    # Revenue from pre/post: post - before = 20M VND
    assert Decimal(payload.revenue_vnd) == Decimal("20000000.0000")

    # Costs: 8M people + 24K AI + 122K infra + 100K integration
    expected_cost = Decimal("8000000") + Decimal("24000") + \
                    Decimal("122000") + Decimal("100000")
    assert Decimal(payload.cost_vnd) == expected_cost.quantize(Decimal("0.0001"))

    # NOV = revenue - cost
    assert Decimal(payload.nov_vnd) == \
           Decimal("20000000") - expected_cost
    assert payload.revenue_method == "pre_post"


@pytest.mark.asyncio
async def test_persist_nov_digest_stub_returns_expected_shape():
    """Stub persist activity must return {row_id, is_negative, revision}
    so the downstream alert activity can branch on is_negative without
    knowing whether the persist was real or stubbed."""
    payload = await compute_nov_for_month(
        NOVInputs(
            enterprise_id="ent-x",
            month_start="2026-04-01",
            revenue_30d_before_vnd="0",  # zero baseline → revenue=0
            revenue_30d_after_vnd="0",
            people_hours_required="100",
            people_hourly_rate_vnd="500000",   # 50M cost
            ai_tokens_input=0, ai_tokens_output=0,
            ai_cost_per_1k_input_vnd="0", ai_cost_per_1k_output_vnd="0",
            infra_compute_hours="0", infra_storage_gb_month="0",
            integration_api_calls=0, integration_cost_per_call_vnd="0",
        )
    )
    result = await persist_nov_digest(payload)
    # Negative because revenue=0 and cost=50M
    assert result["is_negative"] is True
    assert result["enterprise_id"] == "ent-x"
    assert result["month_start"] == "2026-04-01"
    assert result["revision"] == 1
    assert "digest-ent-x" in result["row_id"]


@pytest.mark.asyncio
async def test_maybe_dispatch_alert_skips_positive_nov():
    """Positive / zero NOV → alert NOT dispatched. The stub returns
    {dispatched: False, reason} so the workflow can include the no-op
    in its result."""
    result = await maybe_dispatch_negative_alert(
        {"enterprise_id": "ent-1", "month_start": "2026-04-01",
         "nov_vnd": "5000000", "is_negative": False}
    )
    assert result["dispatched"] is False
    assert "positive" in result["reason"]


@pytest.mark.asyncio
async def test_maybe_dispatch_alert_fires_on_negative_nov():
    """Negative NOV → alert dispatched (stub returns synthetic ack)."""
    result = await maybe_dispatch_negative_alert(
        {"enterprise_id": "ent-2", "month_start": "2026-04-01",
         "nov_vnd": "-3000000", "is_negative": True}
    )
    assert result["dispatched"] is True
    assert result["channel"] == "stub"
    assert "alert-ent-2-2026-04-01" in result["ref"]


# ─── End-to-end workflow via WorkflowEnvironment ─────────────────────


@pytest.mark.asyncio
async def test_nov_monthly_digest_workflow_happy_path():
    """All 4 activities chain successfully + workflow returns the
    composite. Validates the K-17 declarations and the per-class retry
    policies wire correctly to Temporal's scheduling."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        client: Client = env.client
        async with Worker(
            client,
            task_queue=_TASK_QUEUE,
            workflows=[NovMonthlyDigestWorkflow],
            activities=list(ALL_ACTIVITIES),
        ):
            result = await client.execute_workflow(
                NovMonthlyDigestWorkflow.run,
                args=["ent-test", "2026-04-01"],
                id="test-nov-wf-happy",
                task_queue=_TASK_QUEUE,
            )

    assert result["enterprise_id"] == "ent-test"
    assert result["month_start"] == "2026-04-01"
    # The stub gather_nov_inputs returns positive-margin numbers →
    # positive NOV → no alert dispatched.
    assert result["is_negative"] is False
    assert result["alert"]["dispatched"] is False
    # NOV must be present + parseable as Decimal
    assert Decimal(result["nov_vnd"])
