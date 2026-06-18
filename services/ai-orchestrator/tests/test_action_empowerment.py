"""Empowerment advice wired into agent action results (PR3, 12-axiom).

The v0 action tools record reviewable artifacts (AI never auto-sends) → they are
option-PRESERVING for the human's OR. Each result now carries a `protection`
advisory (BR-9 advisory-only; the K-23 gate stays the hard control).
"""
from __future__ import annotations

import asyncio

from ai_orchestrator.agents.tools.actions import (
    DraftFollowupEmailTool,
    MarkCustomerForReviewTool,
)
from ai_orchestrator.chat.tools.base import ToolContext
from ai_orchestrator.reasoning.cdfl.empowerment import advise_for_result


def test_action_tools_declare_preserving():
    assert DraftFollowupEmailTool.option_impact == "preserving"
    assert MarkCustomerForReviewTool.option_impact == "preserving"


def test_advise_preserving():
    a = advise_for_result("preserving")
    assert a["preserves_options"] is True
    assert a["needs_consent"] is False
    assert "note" in a


def test_advise_shrinking_needs_consent():
    a = advise_for_result("shrinking")
    assert a["preserves_options"] is False
    assert a["needs_consent"] is True


def test_draft_dryrun_result_carries_protection():
    tool = DraftFollowupEmailTool()
    ctx = ToolContext(enterprise_id="00000000-0000-0000-0000-000000000001",
                      user_id=None, scope="enterprise", dry_run=True)
    res = asyncio.run(tool.execute(
        {"customer_external_id": "C1", "subject": "s", "body": "b"}, ctx))
    assert res["side_effect_fired"] is False
    assert res["protection"]["preserves_options"] is True
    assert res["protection"]["needs_consent"] is False


def test_mark_dryrun_result_carries_protection():
    tool = MarkCustomerForReviewTool()
    ctx = ToolContext(enterprise_id="00000000-0000-0000-0000-000000000001",
                      user_id=None, scope="enterprise", dry_run=True)
    res = asyncio.run(tool.execute(
        {"customer_external_id": "C1", "reason": "r"}, ctx))
    assert res["side_effect_fired"] is False
    assert res["protection"]["preserves_options"] is True
