"""
Tests for bot/ — pluggable chatbot adapter (Phase 1 v4 P1-S8 scaffold).

Two layers:
  * Adapter contract — BotAdapter abstract surface, factory dispatch,
    BotSendError shape, WorkflowApprovalMarkup validation.
  * Telegram impl — TelegramBotAdapter is_configured, send_message
    sentinel, format_workflow_approval, MarkdownV2 escaping.

When a second adapter ships (Zalo / Line / Slack), add a test_bot_<provider>.py
mirroring the Telegram-impl section.
"""
from __future__ import annotations

import os

import pytest

from bot import (
    ApprovalButton,
    BotAdapter,
    BotSendError,
    TelegramBotAdapter,
    TelegramBotConfig,
    WorkflowApprovalMarkup,
    available_providers,
    get_bot_adapter,
)


# ─── Factory + adapter contract ─────────────────────────────────────


def test_available_providers_includes_telegram():
    """Telegram is the Phase 1 provider (ADR-0018)."""
    assert "telegram" in available_providers()


def test_get_bot_adapter_default_returns_telegram():
    """No env, no arg → Telegram (current Phase 1 default)."""
    os.environ.pop("KAORI_BOT_PROVIDER", None)
    adapter = get_bot_adapter()
    assert isinstance(adapter, TelegramBotAdapter)
    assert adapter.provider == "telegram"


def test_get_bot_adapter_explicit_arg_overrides_env():
    """Explicit ``provider`` arg wins over env so test fixtures + caller
    code that pin a specific adapter don't depend on test isolation."""
    os.environ["KAORI_BOT_PROVIDER"] = "telegram"
    try:
        adapter = get_bot_adapter(provider="telegram")
        assert adapter.provider == "telegram"
    finally:
        del os.environ["KAORI_BOT_PROVIDER"]


def test_get_bot_adapter_unknown_provider_raises():
    """Typo / future provider not yet shipped → fail loud at startup
    rather than silently default to Telegram."""
    with pytest.raises(ValueError, match="Unknown bot provider"):
        get_bot_adapter(provider="discord")


def test_get_bot_adapter_provider_match_is_case_insensitive():
    """env vars from CI / .env files come in mixed case sometimes;
    factory normalises."""
    os.environ["KAORI_BOT_PROVIDER"] = "TELEGRAM"
    try:
        adapter = get_bot_adapter()
        assert adapter.provider == "telegram"
    finally:
        del os.environ["KAORI_BOT_PROVIDER"]


# ─── BotAdapter base contract ───────────────────────────────────────


def test_bot_adapter_is_abstract():
    """BotAdapter cannot be instantiated directly — caller must pick
    a concrete adapter."""
    with pytest.raises(TypeError):
        BotAdapter()  # type: ignore[abstract]


def test_workflow_approval_markup_rejects_empty_workflow_name():
    """Empty inputs would render a misleading prompt at the manager's
    chat — fail at construction."""
    with pytest.raises(ValueError, match="workflow_name"):
        WorkflowApprovalMarkup(
            workflow_name="", run_id="run-1",
            approve=ApprovalButton(text="OK", url="https://x/a"),
            reject=ApprovalButton(text="No", url="https://x/r"),
        )


def test_workflow_approval_markup_rejects_empty_run_id():
    with pytest.raises(ValueError, match="run_id"):
        WorkflowApprovalMarkup(
            workflow_name="wf", run_id="",
            approve=ApprovalButton(text="OK", url="https://x/a"),
            reject=ApprovalButton(text="No", url="https://x/r"),
        )


def test_bot_send_error_carries_provider_metadata():
    """Provider + provider_code populate so audit logs can identify
    the source of failure."""
    err = BotSendError("rate limited", provider="telegram", provider_code=429)
    assert err.provider == "telegram"
    assert err.provider_code == 429
    assert "rate limited" in str(err)


# ─── TelegramBotConfig + TelegramBotAdapter ─────────────────────────


def test_telegram_config_from_env_reads_token():
    os.environ["KAORI_TELEGRAM_BOT_TOKEN"] = "123:ABC"
    try:
        cfg = TelegramBotConfig.from_env()
        assert cfg.bot_token == "123:ABC"
    finally:
        del os.environ["KAORI_TELEGRAM_BOT_TOKEN"]


def test_telegram_adapter_is_configured_requires_non_whitespace_token():
    assert not TelegramBotAdapter(TelegramBotConfig(bot_token="")).is_configured()
    assert not TelegramBotAdapter(TelegramBotConfig(bot_token="   ")).is_configured()
    assert TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC")).is_configured()


@pytest.mark.asyncio
async def test_telegram_send_message_unconfigured_raises_bot_send_error():
    """No token = fail loud rather than silently swallow. Caller code
    must guard with is_configured() before calling."""
    adapter = TelegramBotAdapter(TelegramBotConfig(bot_token=""))
    with pytest.raises(BotSendError, match="bot_token not set"):
        await adapter.send_message(chat_id=42, text="hi")


# ─── send_message httpx wire — Phase 1.5 P15-S9 D5 ──────────────────


def _mock_async_client(handler):
    """Build a mock for ``httpx.AsyncClient`` so the adapter's `async
    with httpx.AsyncClient(...) as c: await c.post(...)` round-trips
    through the supplied handler.

    Returns a context manager suitable for ``patch("httpx.AsyncClient",
    return_value=cm)``. Same shape as test_kaori_vault.py uses for
    Vault's GET — keeps the mocking pattern uniform across services.
    """
    from unittest.mock import AsyncMock, MagicMock
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock(post=handler))
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _resp(status: int, body):
    """Build a minimal httpx.Response double — enough for `_parse_response`
    to read status_code + .json() + .text on. Avoids spinning up a real
    httpx.MockTransport fixture for every assertion."""
    from unittest.mock import MagicMock
    import httpx
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json = MagicMock(return_value=body)
    r.text = repr(body)
    return r


@pytest.mark.asyncio
async def test_telegram_send_message_happy_path_round_trip():
    """ok=true response + 'result' dict → caller sees the result dict.
    Verifies URL composition, payload shape, and result unwrap."""
    from unittest.mock import AsyncMock, patch

    captured = {}

    async def _post(url, json):
        captured["url"] = url
        captured["json"] = json
        return _resp(200, {"ok": True, "result": {"message_id": 7, "chat": {"id": 42}}})

    with patch("httpx.AsyncClient", return_value=_mock_async_client(_post)):
        adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC"))
        result = await adapter.send_message(
            chat_id=42, text="hello", parse_mode="MarkdownV2",
        )

    assert captured["url"].endswith("/bot123:ABC/sendMessage")
    assert captured["json"]["chat_id"] == 42
    assert captured["json"]["text"] == "hello"
    assert captured["json"]["parse_mode"] == "MarkdownV2"
    assert "reply_markup" not in captured["json"]  # not set when None
    assert result["message_id"] == 7


@pytest.mark.asyncio
async def test_telegram_send_message_ok_false_maps_to_bot_send_error():
    """Bot API can return 200 with ok=false (bad chat id, blocked user).
    The adapter must surface the error_code so audit logs identify the
    cause without parsing the description string."""
    from unittest.mock import patch

    async def _post(url, json):
        return _resp(200, {
            "ok": False, "error_code": 403,
            "description": "Forbidden: bot was blocked by the user",
        })

    with patch("httpx.AsyncClient", return_value=_mock_async_client(_post)):
        adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC"))
        with pytest.raises(BotSendError) as excinfo:
            await adapter.send_message(chat_id=42, text="hi")

    assert excinfo.value.provider == "telegram"
    assert excinfo.value.provider_code == 403
    assert "blocked by the user" in str(excinfo.value)


@pytest.mark.asyncio
async def test_telegram_send_message_network_error_maps_to_bot_send_error():
    """httpx.HTTPError (timeout, connect refused, DNS) becomes BotSendError
    with provider_code=None — caller catches one type for any dispatch
    failure."""
    from unittest.mock import patch
    import httpx

    async def _post(url, json):
        raise httpx.ConnectTimeout("connect timeout")

    with patch("httpx.AsyncClient", return_value=_mock_async_client(_post)):
        adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC"))
        with pytest.raises(BotSendError, match="network error") as excinfo:
            await adapter.send_message(chat_id=42, text="hi")

    assert excinfo.value.provider_code is None


@pytest.mark.asyncio
async def test_telegram_answer_callback_query_round_trip():
    """answerCallbackQuery is a separate Bot API method; verify URL
    + payload shape + happy path. The webhook handler depends on this
    to clear the manager's spinner inside the 10s SLA."""
    from unittest.mock import patch

    captured = {}

    async def _post(url, json):
        captured["url"] = url
        captured["json"] = json
        return _resp(200, {"ok": True, "result": True})

    with patch("httpx.AsyncClient", return_value=_mock_async_client(_post)):
        adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC"))
        await adapter.answer_callback_query(
            callback_query_id="cb-1", text="ok", show_alert=False,
        )

    assert captured["url"].endswith("/bot123:ABC/answerCallbackQuery")
    assert captured["json"]["callback_query_id"] == "cb-1"
    assert captured["json"]["text"] == "ok"
    assert "show_alert" not in captured["json"]  # only set when True


# ─── Markup wire shape ───────────────────────────────────────────────


def test_telegram_format_workflow_approval_emits_inline_keyboard_url():
    """URL buttons (Phase 1 default) → {text, url} shape."""
    adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC"))
    markup = WorkflowApprovalMarkup(
        workflow_name="churn-detect",
        run_id="run-7",
        approve=ApprovalButton(text="✅ Approve", url="https://kaori.ai/wf/run-7/approve"),
        reject=ApprovalButton(text="❌ Reject", url="https://kaori.ai/wf/run-7/reject"),
    )
    out = adapter.format_workflow_approval(markup)
    buttons = out["inline_keyboard"][0]
    assert buttons[0] == {"text": "✅ Approve", "url": "https://kaori.ai/wf/run-7/approve"}
    assert buttons[1] == {"text": "❌ Reject",  "url": "https://kaori.ai/wf/run-7/reject"}


def test_telegram_format_workflow_approval_emits_inline_keyboard_callback():
    """callback_data buttons (Phase 1.5+ approval gate path) → {text,
    callback_data} shape; the URL key must NOT be present."""
    adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="123:ABC"))
    markup = WorkflowApprovalMarkup(
        workflow_name="churn-detect",
        run_id="r7",
        approve=ApprovalButton(text="OK", callback_data="wa1:approve:churn:r7:gate"),
        reject=ApprovalButton(text="No", callback_data="wa1:reject:churn:r7:gate"),
    )
    out = adapter.format_workflow_approval(markup)
    buttons = out["inline_keyboard"][0]
    assert buttons[0] == {"text": "OK", "callback_data": "wa1:approve:churn:r7:gate"}
    assert "url" not in buttons[0]
    assert buttons[1] == {"text": "No", "callback_data": "wa1:reject:churn:r7:gate"}


def test_approval_button_requires_exactly_one_of_url_or_callback():
    """XOR — neither set + both set are equally bad; both render a
    half-built button that Telegram silently truncates."""
    with pytest.raises(ValueError, match="exactly one"):
        ApprovalButton(text="X")  # neither
    with pytest.raises(ValueError, match="exactly one"):
        ApprovalButton(text="X", url="https://x", callback_data="cb")


def test_approval_button_callback_data_64_byte_cap():
    """Telegram silently drops callback_data > 64 bytes UTF-8. Catch at
    construction so the failure is local + obvious."""
    long_cb = "wa1:approve:" + ("x" * 60)  # > 64 bytes
    with pytest.raises(ValueError, match="64 bytes"):
        ApprovalButton(text="X", callback_data=long_cb)


def test_telegram_escape_markdown_handles_special_chars():
    """MarkdownV2 spec — escape these chars or Telegram silently drops
    the message: _*[]()~`>#+-=|{}.!\\"""
    adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="x"))
    plain = "Hello (world)! It's *amazing*."
    escaped = adapter.escape_markdown(plain)
    assert "\\(" in escaped
    assert "\\)" in escaped
    assert "\\!" in escaped
    assert "\\*" in escaped
    assert "\\." in escaped


def test_telegram_escape_markdown_idempotent_for_safe_chars():
    """Plain alphanumeric + spaces should pass through unchanged."""
    adapter = TelegramBotAdapter(TelegramBotConfig(bot_token="x"))
    assert adapter.escape_markdown("simple text 123") == "simple text 123"
