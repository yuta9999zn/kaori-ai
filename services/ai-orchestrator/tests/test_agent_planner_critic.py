"""
F-061 — planner + critic LLM call shape tests.

llm_router.complete_structured is mocked. Verifies:

  * planner returns Plan when the gateway returns a valid parsed dict
  * planner raises when the LLM picks a tool not in the workflow's
    allowed_tools (defence in depth)
  * critic returns CriticVerdict with the right action enum
  * Plan validator catches consecutive duplicate steps
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.agents.critic import review_session
from ai_orchestrator.agents.planner import plan_workflow
from ai_orchestrator.agents.registry_setup import (
    _reset_agent_registry_for_tests,
    get_agent_registry,
)
from ai_orchestrator.agents.schemas import Plan, PlanStep, TranscriptEntry
from ai_orchestrator.agents.workflows import get_workflow

_EID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _reset_registry():
    """Each test gets a fresh registry to keep test order independent."""
    _reset_agent_registry_for_tests()
    yield
    _reset_agent_registry_for_tests()


# =========================================================================
# Plan schema
# =========================================================================


def test_plan_validator_rejects_consecutive_duplicates():
    """Two identical steps in a row = planner artefact. Catch early."""
    with pytest.raises(ValueError) as exc:
        Plan.model_validate({
            "steps": [
                {"tool_name": "get_top_at_risk_customers", "args": {"limit": 5}, "rationale": "fetch"},
                {"tool_name": "get_top_at_risk_customers", "args": {"limit": 5}, "rationale": "again"},
            ],
            "rationale": "broken",
        })
    assert "duplicates" in str(exc.value).lower()


def test_plan_step_minimum():
    with pytest.raises(ValueError):
        Plan.model_validate({"steps": [], "rationale": ""})


def test_plan_step_maximum():
    """10-step cap. 11 must reject."""
    with pytest.raises(ValueError):
        Plan.model_validate({
            "steps": [
                {"tool_name": f"t{i}", "args": {}, "rationale": ""}
                for i in range(11)
            ],
            "rationale": "",
        })


# =========================================================================
# Planner
# =========================================================================


@pytest.mark.asyncio
async def test_planner_returns_plan_on_valid_gateway_response():
    """Happy path: gateway returns a parsed dict that matches the
    workflow's allowlist → planner gives back a Plan."""
    workflow = get_workflow("insight-to-action")
    registry = get_agent_registry()

    fake_parsed = {
        "steps": [
            {
                "tool_name": "get_top_at_risk_customers",
                "args": {"limit": 5},
                "rationale": "Lấy danh sách KH at-risk hàng đầu",
            },
            {
                "tool_name": "draft_followup_email",
                "args": {
                    "customer_external_id": "cust-1",
                    "subject": "Hỏi thăm",
                    "body": "Body here",
                },
                "rationale": "Soạn nháp email",
            },
        ],
        "rationale": "Đầu tiên đọc, sau đó draft.",
    }

    with patch(
        "ai_orchestrator.agents.planner.llm_router.complete_structured",
        new=AsyncMock(return_value=fake_parsed),
    ):
        plan, tokens = await plan_workflow(
            workflow=workflow,
            input={"insight_id": "abc-123"},
            registry=registry,
            enterprise_id=_EID,
        )

    assert isinstance(plan, Plan)
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "get_top_at_risk_customers"
    assert tokens == 0


@pytest.mark.asyncio
async def test_planner_rejects_tool_outside_workflow_allowlist():
    """Defence in depth: even if the LLM returns a valid Plan shape,
    a tool name outside the workflow's allowed_tools must error.
    Catches a planner that hallucinates a tool name from the chat
    catalog the workflow doesn't permit (e.g. get_billing_quota_status)."""
    workflow = get_workflow("insight-to-action")
    registry = get_agent_registry()

    fake_parsed = {
        "steps": [
            {
                "tool_name": "get_billing_quota_status",   # NOT in allowed_tools
                "args": {},
                "rationale": "should be rejected",
            },
        ],
        "rationale": "Bad pick.",
    }

    with patch(
        "ai_orchestrator.agents.planner.llm_router.complete_structured",
        new=AsyncMock(return_value=fake_parsed),
    ):
        with pytest.raises(ValueError) as exc:
            await plan_workflow(
                workflow=workflow,
                input={"insight_id": "abc"},
                registry=registry,
                enterprise_id=_EID,
            )

    assert "get_billing_quota_status" in str(exc.value)
    assert "allowed_tools" in str(exc.value)


# =========================================================================
# Critic
# =========================================================================


@pytest.mark.asyncio
async def test_critic_accept_verdict():
    workflow = get_workflow("insight-to-action")
    plan = Plan(
        steps=[PlanStep(tool_name="get_top_at_risk_customers", args={"limit": 5}, rationale="x")],
        rationale="ok",
    )
    transcripts = [
        TranscriptEntry(step_index=0, role="planner", reasoning="ok"),
        TranscriptEntry(step_index=1, role="executor", tool_name="get_top_at_risk_customers", tool_ok=True, reasoning="dispatched"),
    ]

    fake_verdict = {
        "action": "accept",
        "reason": "Plan đã chạy đúng yêu cầu workflow.",
        "issues": [],
    }

    with patch(
        "ai_orchestrator.agents.critic.llm_router.complete_structured",
        new=AsyncMock(return_value=fake_verdict),
    ):
        verdict = await review_session(
            workflow=workflow,
            input={"insight_id": "abc"},
            plan=plan,
            transcripts=transcripts,
            enterprise_id=_EID,
        )

    assert verdict.action == "accept"
    assert verdict.issues == []


@pytest.mark.asyncio
async def test_critic_replan_verdict():
    workflow = get_workflow("insight-to-action")
    plan = Plan(
        steps=[PlanStep(tool_name="get_top_at_risk_customers", args={}, rationale="x")],
        rationale="ok",
    )
    fake_verdict = {
        "action": "replan",
        "reason": "Thiếu bước draft email, cần re-plan.",
        "issues": ["chưa có draft_followup_email"],
    }
    with patch(
        "ai_orchestrator.agents.critic.llm_router.complete_structured",
        new=AsyncMock(return_value=fake_verdict),
    ):
        verdict = await review_session(
            workflow=workflow,
            input={"insight_id": "abc"},
            plan=plan,
            transcripts=[],
            enterprise_id=_EID,
        )
    assert verdict.action == "replan"
    assert "draft_followup_email" in verdict.issues[0]


@pytest.mark.asyncio
async def test_critic_escalate_verdict():
    workflow = get_workflow("insight-to-action")
    plan = Plan(
        steps=[PlanStep(tool_name="draft_followup_email", args={}, rationale="x")],
        rationale="ok",
    )
    fake_verdict = {
        "action": "escalate",
        "reason": "Phát hiện PII trong body — cần con người duyệt.",
        "issues": ["PII detected"],
    }
    with patch(
        "ai_orchestrator.agents.critic.llm_router.complete_structured",
        new=AsyncMock(return_value=fake_verdict),
    ):
        verdict = await review_session(
            workflow=workflow,
            input={"insight_id": "abc"},
            plan=plan,
            transcripts=[],
            enterprise_id=_EID,
        )
    assert verdict.action == "escalate"
