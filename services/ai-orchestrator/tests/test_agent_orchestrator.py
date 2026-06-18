"""
F-061 orchestrator end-to-end with all I/O mocked.

Verifies the full planner → executor → critic loop:

  * happy path (accept) → status='completed', transcripts inlined
  * planner failure → status='failed' with error_message
  * critic escalate → status='escalated'
  * critic replan + MAX_REPLAN exceeded → status='escalated'
  * dry_run=True is propagated into ToolContext for action tools
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.agents.orchestrator import MAX_REPLAN, run_session
from ai_orchestrator.agents.registry_setup import _reset_agent_registry_for_tests
from ai_orchestrator.agents.schemas import SessionResponse

_EID = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"

# Each test patches the four side-effect surfaces:
#   * llm_router.complete_structured (planner + critic)
#   * registry.dispatch (executor — bypass real tool execution)
#   * orchestrator's DB writes (4 helpers)
# That keeps the orchestrator tests pure — no Postgres, no LLM gateway.

_PERSIST_PATCHES = (
    "ai_orchestrator.agents.orchestrator._insert_session",
    "ai_orchestrator.agents.orchestrator._set_status",
    "ai_orchestrator.agents.orchestrator._persist_plan",
    "ai_orchestrator.agents.orchestrator._persist_verdict",
    "ai_orchestrator.agents.orchestrator._bump_replan",
    "ai_orchestrator.agents.orchestrator._finalise_session",
    "ai_orchestrator.agents.orchestrator._insert_transcript",
)

# Single patch target for ``complete_structured``. Both planner and
# critic import the SAME ``llm_router`` singleton instance from
# ``engine.llm_router`` — patching it on the class means both calls
# come through the same mock, and side_effect=iter([...]) lets the
# test return a DIFFERENT response per call (planner first, critic
# second, planner-on-replan third, ...).
_LLM_PATCH_TARGET = "ai_orchestrator.engine.llm_router.LLMRouter.complete_structured"


@pytest.fixture(autouse=True)
def _reset_registry():
    _reset_agent_registry_for_tests()
    yield
    _reset_agent_registry_for_tests()


def _stub_persistence(stack):
    """Patch all DB write helpers to async no-ops. Returns a list of
    the AsyncMock instances so tests can assert call counts."""
    mocks = []
    for target in _PERSIST_PATCHES:
        m = stack.enter_context(patch(target, new=AsyncMock()))
        mocks.append(m)
    return mocks


def _patch_llm(stack, returns: list):
    """Install a single mock on LLMRouter.complete_structured that
    returns each item in ``returns`` on successive calls. Tests pass
    ``[plan_dict, verdict_dict]`` for a one-pass run."""
    return stack.enter_context(patch(
        _LLM_PATCH_TARGET,
        new=AsyncMock(side_effect=list(returns)),
    ))


# =========================================================================
# Happy path
# =========================================================================


@pytest.mark.asyncio
async def test_orchestrator_happy_path_completed():
    """Planner → 1 executor step (mocked dispatch) → Critic accept →
    status='completed'."""
    plan_dict = {
        "steps": [
            {
                "tool_name": "get_top_at_risk_customers",
                "args": {"limit": 5},
                "rationale": "Lấy danh sách KH at-risk",
            },
        ],
        "rationale": "Một bước để lấy dữ liệu.",
    }
    verdict_dict = {
        "action": "accept",
        "reason": "Đủ dữ liệu, accept.",
        "issues": [],
    }

    from contextlib import ExitStack
    with ExitStack() as stack:
        _stub_persistence(stack)
        _patch_llm(stack, [plan_dict, verdict_dict])
        # Mock the executor's dispatch — return ok without touching tools.
        stack.enter_context(patch(
            "ai_orchestrator.agents.executor.ToolRegistry.dispatch",
            new=AsyncMock(return_value=(True, {"customers": [{"id": "cust-1"}]})),
        ))

        result = await run_session(
            workflow_id="insight-to-action",
            input={"insight_id": "11111111-1111-1111-1111-111111111111"},
            dry_run=True,
            enterprise_id=_EID,
            actor_user_id=_USER,
        )

    assert isinstance(result, SessionResponse)
    assert result.status == "completed"
    assert result.replan_count == 0
    assert result.error_message is None
    assert result.dry_run is True
    assert result.plan is not None
    assert len(result.plan.steps) == 1
    assert result.critic_verdict is not None
    assert result.critic_verdict.action == "accept"
    # Transcript: 1 planner row + 1 executor row + 1 critic row
    assert len(result.transcripts) == 3
    assert result.transcripts[0].role == "planner"
    assert result.transcripts[1].role == "executor"
    assert result.transcripts[2].role == "critic"


# =========================================================================
# Failure paths
# =========================================================================


@pytest.mark.asyncio
async def test_orchestrator_planner_failure_marks_failed():
    """Planner gateway raise → status='failed' with error_message."""
    from contextlib import ExitStack
    with ExitStack() as stack:
        _stub_persistence(stack)
        stack.enter_context(patch(
            _LLM_PATCH_TARGET,
            new=AsyncMock(side_effect=RuntimeError("gateway 502")),
        ))

        result = await run_session(
            workflow_id="insight-to-action",
            input={"insight_id": "11111111-1111-1111-1111-111111111111"},
            dry_run=True,
            enterprise_id=_EID,
            actor_user_id=_USER,
        )

    assert result.status == "failed"
    assert "planner_failed" in (result.error_message or "")
    # Critic never called — no critic transcript row.
    assert all(t.role != "critic" for t in result.transcripts)


@pytest.mark.asyncio
async def test_orchestrator_critic_escalate_marks_escalated():
    plan_dict = {
        "steps": [
            {"tool_name": "get_top_at_risk_customers", "args": {}, "rationale": "x"},
        ],
        "rationale": "ok",
    }
    verdict_dict = {
        "action": "escalate",
        "reason": "PII detected.",
        "issues": ["PII in draft body"],
    }

    from contextlib import ExitStack
    with ExitStack() as stack:
        _stub_persistence(stack)
        _patch_llm(stack, [plan_dict, verdict_dict])
        stack.enter_context(patch(
            "ai_orchestrator.agents.executor.ToolRegistry.dispatch",
            new=AsyncMock(return_value=(True, {})),
        ))

        result = await run_session(
            workflow_id="insight-to-action",
            input={"insight_id": "11111111-1111-1111-1111-111111111111"},
            dry_run=True,
            enterprise_id=_EID,
            actor_user_id=_USER,
        )

    assert result.status == "escalated"
    assert result.critic_verdict is not None
    assert result.critic_verdict.action == "escalate"


@pytest.mark.asyncio
async def test_orchestrator_max_replan_forces_escalation():
    """If critic asks replan more than MAX_REPLAN times, force-escalate.
    Cap is hit on the (MAX_REPLAN + 1)th replan request."""
    plan_dict = {
        "steps": [
            {"tool_name": "get_top_at_risk_customers", "args": {}, "rationale": "x"},
        ],
        "rationale": "ok",
    }
    replan_verdict = {
        "action": "replan",
        "reason": "Thiếu bước action.",
        "issues": ["missing action step"],
    }

    from contextlib import ExitStack
    with ExitStack() as stack:
        _stub_persistence(stack)
        # Loop runs MAX_REPLAN+1 times. Each iteration = 1 planner + 1
        # critic call. Pre-build the side_effect list with that many
        # alternating (plan, replan_verdict) pairs.
        sequence: list = []
        for _ in range(MAX_REPLAN + 1):
            sequence.append(plan_dict)
            sequence.append(replan_verdict)
        _patch_llm(stack, sequence)
        stack.enter_context(patch(
            "ai_orchestrator.agents.executor.ToolRegistry.dispatch",
            new=AsyncMock(return_value=(True, {})),
        ))

        result = await run_session(
            workflow_id="insight-to-action",
            input={"insight_id": "11111111-1111-1111-1111-111111111111"},
            dry_run=True,
            enterprise_id=_EID,
            actor_user_id=_USER,
        )

    assert result.status == "escalated"
    assert "max_replan_reached" in (result.error_message or "")
    # Replan count incremented to MAX_REPLAN+1 before the loop bailed.
    assert result.replan_count == MAX_REPLAN + 1


# =========================================================================
# Dry-run propagation
# =========================================================================


@pytest.mark.asyncio
async def test_orchestrator_dry_run_propagates_to_executor_ctx():
    """The ctx the executor receives MUST carry dry_run=True when the
    session was started with dry_run=True. This is the contract the
    action tools rely on."""
    plan_dict = {
        "steps": [
            {
                "tool_name": "draft_followup_email",
                "args": {"customer_external_id": "c1", "subject": "ok", "body": "hi"},
                "rationale": "draft",
            },
        ],
        "rationale": "ok",
    }
    verdict_dict = {"action": "accept", "reason": "ok", "issues": []}

    seen_ctx = {}

    async def _capturing_dispatch(*, name, args, ctx):
        seen_ctx["dry_run"] = ctx.dry_run
        return True, {"side_effect_fired": False}

    from contextlib import ExitStack
    with ExitStack() as stack:
        _stub_persistence(stack)
        _patch_llm(stack, [plan_dict, verdict_dict])
        stack.enter_context(patch(
            "ai_orchestrator.agents.executor.ToolRegistry.dispatch",
            new=AsyncMock(side_effect=_capturing_dispatch),
        ))

        await run_session(
            workflow_id="insight-to-action",
            input={"insight_id": "11111111-1111-1111-1111-111111111111"},
            dry_run=True,
            enterprise_id=_EID,
            actor_user_id=_USER,
        )

    assert seen_ctx["dry_run"] is True
