"""
Tests for bot/webhook.py — Telegram callback_query receiver.

Covers:
  * encode/decode round-trip + 64-byte cap + bad input rejection
  * secret-token verification (positive, negative, empty=disabled)
  * happy-path handler: persists row, calls answerCallbackQuery, returns
    HandledApproval with inserted=True
  * idempotent retry: same callback_query_id second time → inserted=False
  * non-callback_query update (text message) → returns None, no DB write
  * answerCallbackQuery failure: webhook still records the decision

DB pool + bot adapter are mocked — no live Telegram, no Postgres.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from bot.base import BotSendError
from bot.webhook import (
    ApprovalCallback,
    HandledApproval,
    WebhookContext,
    WebhookSecretMismatch,
    decode_approval_callback,
    encode_approval_callback,
    handle_telegram_update,
)


_TEST_ENTERPRISE = UUID("11111111-1111-1111-1111-111111111111")


# ─── Callback-data encoder/decoder ──────────────────────────────────


def test_encode_decode_round_trip():
    raw = encode_approval_callback("approve", "churn-detect", "run-7", "gate")
    decoded = decode_approval_callback(raw)
    assert decoded == ApprovalCallback(
        decision="approve", workflow_id="churn-detect", run_id="run-7", node_id="gate",
    )


def test_encode_rejects_bad_decision():
    with pytest.raises(ValueError, match="must be 'approve' or 'reject'"):
        encode_approval_callback("yes", "wf", "run", "node")


def test_encode_rejects_separator_in_field():
    """Embedded ':' would unbalance the decode; reject at encode time."""
    with pytest.raises(ValueError, match="must not contain"):
        encode_approval_callback("approve", "wf:bad", "run", "node")


def test_encode_enforces_64_byte_cap():
    """Telegram silently drops callback_data > 64 bytes UTF-8."""
    with pytest.raises(ValueError, match="exceed 64 bytes"):
        encode_approval_callback("approve", "x" * 30, "y" * 30, "z")


def test_decode_rejects_unknown_prefix():
    """A stale message from a previous schema version → fail loud."""
    with pytest.raises(ValueError, match="unrecognised"):
        decode_approval_callback("v9:approve:wf:run:node")


def test_decode_rejects_wrong_arity():
    """Missing field → fail loud rather than IndexError on the unpack."""
    with pytest.raises(ValueError, match="unrecognised"):
        decode_approval_callback("wa1:approve:wf:run")  # only 4 parts


# ─── Secret-token verification ──────────────────────────────────────


def _make_ctx(
    *,
    pool=None,
    adapter=None,
    secret: str = "",
    enterprise: UUID = _TEST_ENTERPRISE,
):
    if pool is None:
        pool = _make_pool_mock()
    if adapter is None:
        adapter = MagicMock()
        adapter.answer_callback_query = AsyncMock(return_value={})

    async def _resolver(decoded):  # noqa: ARG001 - test fixture
        return enterprise

    return WebhookContext(
        pool=pool,
        adapter=adapter,
        expected_secret=secret,
        enterprise_resolver=_resolver,
    )


def _make_pool_mock(*, conflict: bool = False):
    """asyncpg pool double — supports `async with pool.acquire() as conn`.

    When ``conflict=True`` the INSERT returns None (mimicking ON CONFLICT
    DO NOTHING dropping the duplicate).
    """
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None if conflict else {"id": "row-1"})

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


@pytest.mark.asyncio
async def test_secret_mismatch_raises():
    """Production path — header missing or wrong → reject."""
    ctx = _make_ctx(secret="real-secret")
    with pytest.raises(WebhookSecretMismatch):
        await handle_telegram_update(_callback_update(), "wrong-secret", ctx)


@pytest.mark.asyncio
async def test_secret_empty_disables_verification():
    """Dev / test environments without a configured secret — accept all
    requests so the loop works on a laptop without Telegram setWebhook."""
    ctx = _make_ctx(secret="")  # empty = disabled
    result = await handle_telegram_update(_callback_update(), None, ctx)
    assert result is not None
    assert result.inserted is True


@pytest.mark.asyncio
async def test_secret_correct_passes():
    ctx = _make_ctx(secret="t0k3n")
    result = await handle_telegram_update(_callback_update(), "t0k3n", ctx)
    assert result is not None


# ─── Update routing ─────────────────────────────────────────────────


def _callback_update(
    *,
    callback_query_id: str = "cb-101",
    callback_data: str = "wa1:approve:churn-detect:run-7:gate",
) -> dict[str, Any]:
    """Build a minimal Bot API Update with a callback_query."""
    return {
        "update_id": 100,
        "callback_query": {
            "id": callback_query_id,
            "data": callback_data,
            "from": {"id": 5550001, "first_name": "Yuta", "username": "yuta_test"},
            "message": {
                "message_id": 42,
                "chat": {"id": -1002000000000, "type": "supergroup"},
                "text": "Approve this workflow run?",
            },
        },
    }


@pytest.mark.asyncio
async def test_text_message_update_returns_none():
    """Plain text message → not an approval; ignore + return None.
    No DB write, no answerCallbackQuery call."""
    ctx = _make_ctx()
    result = await handle_telegram_update(
        {"update_id": 1, "message": {"text": "hi"}},
        secret_header=None, ctx=ctx,
    )
    assert result is None
    ctx.pool.acquire.assert_not_called()
    ctx.adapter.answer_callback_query.assert_not_called()


# ─── Happy path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_query_inserts_and_answers():
    """First-time callback → row inserted, ack sent, return inserted=True."""
    ctx = _make_ctx()
    result = await handle_telegram_update(_callback_update(), None, ctx)

    assert isinstance(result, HandledApproval)
    assert result.inserted is True
    assert result.decision == "approve"
    assert result.workflow_id == "churn-detect"
    assert result.run_id == "run-7"
    assert result.node_id == "gate"

    # answerCallbackQuery called exactly once with the matching id
    ctx.adapter.answer_callback_query.assert_awaited_once()
    kwargs = ctx.adapter.answer_callback_query.await_args.kwargs
    assert kwargs["callback_query_id"] == "cb-101"
    assert kwargs["text"]  # non-empty toast


# ─── Idempotency — Telegram retries the same callback_query_id ──────


@pytest.mark.asyncio
async def test_duplicate_callback_query_id_second_call_returns_inserted_false():
    """Second delivery hits the unique index → INSERT returns NULL →
    handler returns inserted=False. The decision is still acknowledged
    so the manager's spinner clears even on retry."""
    pool = _make_pool_mock(conflict=True)  # simulates ON CONFLICT DO NOTHING dropping
    ctx = _make_ctx(pool=pool)

    result = await handle_telegram_update(_callback_update(), None, ctx)

    assert result is not None
    assert result.inserted is False
    # Ack still sent so the user UX stays consistent across retries
    ctx.adapter.answer_callback_query.assert_awaited_once()


# ─── Resilience — answerCallbackQuery failure must not lose the row ─


@pytest.mark.asyncio
async def test_answer_callback_query_failure_does_not_lose_decision():
    """If Telegram is having a bad day and answerCallbackQuery fails,
    the decision is already in Postgres. Handler returns the result
    instead of bubbling the BotSendError — losing the row would be
    worse than a stuck spinner for 10s."""
    adapter = MagicMock()
    adapter.answer_callback_query = AsyncMock(
        side_effect=BotSendError("timeout", provider="telegram")
    )
    ctx = _make_ctx(adapter=adapter)

    result = await handle_telegram_update(_callback_update(), None, ctx)
    assert result is not None
    assert result.inserted is True


# ─── Bad callback_data ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bad_callback_data_raises_value_error():
    """Garbage callback_data → handler raises ValueError so the route
    can map to HTTP 400 + Telegram bot logs surface the bug."""
    ctx = _make_ctx()
    bad_update = _callback_update(callback_data="not-a-valid-payload")
    with pytest.raises(ValueError):
        await handle_telegram_update(bad_update, None, ctx)
    # Defensive: nothing got persisted on the failure path
    ctx.pool.acquire.assert_not_called()
