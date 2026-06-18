"""
F-061 — action tool dry_run / side-effect paths.

Each tool runs through ``execute`` with a stubbed ``acquire_for_tenant``
so no real DB is touched. Two scenarios per tool:

  * dry_run=True  → returns preview, NO INSERT issued
  * dry_run=False → returns confirmation + audit_decision_id, ONE
                    INSERT into decision_audit_log captured
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.agents.tools.actions import (
    DraftFollowupEmailTool,
    MarkCustomerForReviewTool,
)
from ai_orchestrator.chat.tools.base import ToolContext

_EID = "11111111-1111-1111-1111-111111111111"
_USER = "22222222-2222-2222-2222-222222222222"


def _fake_acquire(captured: dict | None = None):
    """Build an async-context-manager whose conn captures every
    ``execute`` call. Tests assert against ``captured['inserts']``
    to verify whether a write actually happened."""

    @asynccontextmanager
    async def _ctx(enterprise_id):
        conn = AsyncMock()

        async def _execute(sql, *args):
            if captured is not None:
                captured.setdefault("inserts", []).append((sql, args))

        conn.execute = AsyncMock(side_effect=_execute)
        yield conn

    return _ctx


# =========================================================================
# draft_followup_email
# =========================================================================


@pytest.mark.asyncio
async def test_draft_followup_email_dry_run_skips_db():
    captured: dict = {}
    ctx = ToolContext(
        scope="enterprise",
        enterprise_id=_EID,
        user_id=_USER,
        dry_run=True,
    )

    with patch(
        "ai_orchestrator.agents.tools.actions.acquire_for_tenant",
        _fake_acquire(captured),
    ):
        result = await DraftFollowupEmailTool().execute(
            {
                "customer_external_id": "cust-9001",
                "subject": "Cảm ơn anh/chị đã quan tâm",
                "body": "Em là Kaori, viết bản nháp cho anh/chị xem trước.",
            },
            ctx,
        )

    # Dry-run: no INSERT expected.
    assert "inserts" not in captured, "dry_run=True must NOT touch the DB"
    assert result["side_effect_fired"] is False
    assert result["customer_external_id"] == "cust-9001"
    assert result["subject"] == "Cảm ơn anh/chị đã quan tâm"
    assert "audit_decision_id" not in result


@pytest.mark.asyncio
async def test_draft_followup_email_real_run_writes_audit():
    captured: dict = {}
    ctx = ToolContext(
        scope="enterprise",
        enterprise_id=_EID,
        user_id=_USER,
        dry_run=False,
    )

    with patch(
        "ai_orchestrator.agents.tools.actions.acquire_for_tenant",
        _fake_acquire(captured),
    ):
        result = await DraftFollowupEmailTool().execute(
            {
                "customer_external_id": "cust-9001",
                "subject": "Hỏi thăm tình hình",
                "body": "Body content here.",
            },
            ctx,
        )

    # Side-effect: exactly one INSERT into decision_audit_log.
    assert len(captured["inserts"]) == 1
    sql, _args = captured["inserts"][0]
    assert "INSERT INTO decision_audit_log" in sql
    assert result["side_effect_fired"] is True
    assert "audit_decision_id" in result


@pytest.mark.asyncio
async def test_draft_followup_email_rejects_oversize_body():
    ctx = ToolContext(scope="enterprise", enterprise_id=_EID, dry_run=True)
    with pytest.raises(ValueError) as exc:
        await DraftFollowupEmailTool().execute(
            {
                "customer_external_id": "cust-1",
                "subject": "ok",
                "body": "x" * 5000,  # > 4000 cap
            },
            ctx,
        )
    assert "body" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_draft_followup_email_rejects_missing_enterprise_in_ctx():
    ctx = ToolContext(scope="enterprise", enterprise_id=None, dry_run=False)
    with pytest.raises(ValueError) as exc:
        await DraftFollowupEmailTool().execute(
            {
                "customer_external_id": "cust-1",
                "subject": "ok",
                "body": "ok",
            },
            ctx,
        )
    assert "enterprise_id" in str(exc.value)


# =========================================================================
# mark_customer_for_review
# =========================================================================


@pytest.mark.asyncio
async def test_mark_customer_for_review_dry_run_skips_db():
    captured: dict = {}
    ctx = ToolContext(
        scope="enterprise",
        enterprise_id=_EID,
        user_id=_USER,
        dry_run=True,
    )

    with patch(
        "ai_orchestrator.agents.tools.actions.acquire_for_tenant",
        _fake_acquire(captured),
    ):
        result = await MarkCustomerForReviewTool().execute(
            {
                "customer_external_id": "cust-9001",
                "reason": "revenue_at_risk cao + chưa có liên lạc 30 ngày",
                "priority": "high",
            },
            ctx,
        )

    assert "inserts" not in captured
    assert result["side_effect_fired"] is False
    assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_mark_customer_for_review_real_run_writes_audit():
    captured: dict = {}
    ctx = ToolContext(
        scope="enterprise",
        enterprise_id=_EID,
        user_id=_USER,
        dry_run=False,
    )

    with patch(
        "ai_orchestrator.agents.tools.actions.acquire_for_tenant",
        _fake_acquire(captured),
    ):
        result = await MarkCustomerForReviewTool().execute(
            {
                "customer_external_id": "cust-9001",
                "reason": "needs review",
            },
            ctx,
        )

    assert len(captured["inserts"]) == 1
    sql, _args = captured["inserts"][0]
    assert "INSERT INTO decision_audit_log" in sql
    assert result["side_effect_fired"] is True
    assert result["priority"] == "normal"   # default


@pytest.mark.asyncio
async def test_mark_customer_for_review_rejects_invalid_priority():
    ctx = ToolContext(scope="enterprise", enterprise_id=_EID, dry_run=True)
    with pytest.raises(ValueError):
        await MarkCustomerForReviewTool().execute(
            {
                "customer_external_id": "cust-1",
                "reason": "x",
                "priority": "URGENT",   # not in enum
            },
            ctx,
        )
