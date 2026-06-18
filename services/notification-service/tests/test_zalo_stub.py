"""Tests for Zalo OA stub adapter — P15-S10 D4 / blocker S9 D4c."""
from __future__ import annotations

import asyncio

import pytest

from bot.base import BotSendError
from bot.zalo import ZaloBotAdapter, ZaloBotConfig


def test_zalo_is_configured_false_when_creds_missing():
    """Empty creds → not configured. The intervention_engine resolver
    reads this boolean to decide whether to route ZALO vs fallback."""
    adapter = ZaloBotAdapter(ZaloBotConfig(oa_id="", oa_secret=""))
    assert adapter.is_configured() is False


def test_zalo_is_configured_true_when_both_set():
    adapter = ZaloBotAdapter(ZaloBotConfig(oa_id="oa-1", oa_secret="secret-1"))
    assert adapter.is_configured() is True


def test_zalo_is_configured_false_when_only_oa_id_set():
    adapter = ZaloBotAdapter(ZaloBotConfig(oa_id="oa-1", oa_secret=""))
    assert adapter.is_configured() is False


def test_zalo_send_message_raises_not_implemented_via_botsenderror():
    """Stub adapter raises BotSendError so misconfigured route surfaces
    in workflow logs immediately rather than silently dropped."""
    adapter = ZaloBotAdapter(ZaloBotConfig(oa_id="oa-1", oa_secret="s"))
    with pytest.raises(BotSendError) as exc_info:
        asyncio.run(
            adapter.send_message(chat_id="user-1", text="hello")
        )
    assert "not implemented" in str(exc_info.value).lower()
    assert exc_info.value.provider == "zalo"


def test_zalo_format_workflow_approval_returns_empty_placeholder():
    """Manager approval (REL-011) is Telegram-only Phase 1.5; the
    resolver shouldn't route MANAGER_APPROVAL to Zalo. If somehow it
    does, the empty markup makes the bug visible (no buttons to tap)
    rather than dispatching with a wrong shape."""
    adapter = ZaloBotAdapter(ZaloBotConfig(oa_id="oa-1", oa_secret="s"))
    # A markup arg isn't actually needed for this stub but sanity-check
    # the method exists with the right signature.
    result = adapter.format_workflow_approval(None)  # type: ignore[arg-type]
    assert result == {}
