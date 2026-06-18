"""
TelegramBotAdapter — Phase 1.5 P15-S9 D5 — real httpx wire.

Phase 1 v4 P1-S8 shipped scaffolding (NotImplementedError sentinel);
this module replaces the stub with actual Bot API calls so the
notification outbox + workflow approval gate (REL-011) can dispatch.

ADR-0018 — Telegram chosen over Zalo OA (tax registration burden 2025).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from .base import ApprovalButton, BotAdapter, BotSendError, WorkflowApprovalMarkup

log = structlog.get_logger()


@dataclass(frozen=True)
class TelegramBotConfig:
    """Telegram bot credentials + endpoint config.

    Phase 1.5+ swaps env-var resolution for Vault path
    `secret/platform/telegram/bot_token` (K-18 invariant). The config
    dataclass stays sync; the lifespan in main.py is responsible for
    awaiting kaori_vault.get_or_env() before constructing the adapter
    in production profiles.

    `webhook_secret`: when set, the /webhook/telegram receiver verifies
    the ``X-Telegram-Bot-Api-Secret-Token`` header against this value.
    Telegram echoes whatever string was passed to setWebhook(secret_token=);
    that string never appears in messages, so it acts as a shared HMAC.
    """
    bot_token: str
    api_base: str = "https://api.telegram.org"
    timeout_seconds: float = 10.0
    webhook_secret: str = ""

    @classmethod
    def from_env(cls) -> "TelegramBotConfig":
        return cls(
            bot_token=os.getenv("KAORI_TELEGRAM_BOT_TOKEN", ""),
            api_base=os.getenv("KAORI_TELEGRAM_API_BASE", "https://api.telegram.org"),
            timeout_seconds=float(os.getenv("KAORI_TELEGRAM_TIMEOUT_SECONDS", "10")),
            webhook_secret=os.getenv("KAORI_TELEGRAM_WEBHOOK_SECRET", ""),
        )


class TelegramBotAdapter(BotAdapter):
    """Telegram Bot API adapter — real httpx implementation."""

    provider = "telegram"

    def __init__(self, config: TelegramBotConfig | None = None) -> None:
        self.config = config or TelegramBotConfig.from_env()

    def is_configured(self) -> bool:
        """True when bot_token is set + non-whitespace."""
        return bool(self.config.bot_token.strip())

    # ------------------------------------------------------------------
    # Outbound — sendMessage
    # ------------------------------------------------------------------

    async def send_message(
        self,
        *,
        chat_id: str | int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        """POST /bot{token}/sendMessage and return the parsed result dict.

        Bot API contract reference:
        https://core.telegram.org/bots/api#sendmessage

        Bot API responses always have shape::

            {"ok": <bool>, "result": <obj>}              on success
            {"ok": false, "description": <str>,          on error
             "error_code": <int>, "parameters": {...}}

        We unwrap the ``result`` dict on success + raise BotSendError on
        any non-OK shape. Network / timeout failures map to BotSendError
        with provider_code=None so the caller doesn't need to know the
        difference between "Telegram said no" and "we couldn't reach
        Telegram" — both are dispatch failures.
        """
        if not self.is_configured():
            raise BotSendError(
                "TelegramBotConfig.bot_token not set — refusing to send.",
                provider=self.provider,
            )

        url = f"{self.config.api_base}/bot{self.config.bot_token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        if disable_notification:
            payload["disable_notification"] = True

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            # Connection refused, DNS, timeout, TLS — everything network
            # surfaces here. Wrap so caller's BotSendError catch handles it.
            raise BotSendError(
                f"Telegram network error sending to chat_id={chat_id}: {exc}",
                provider=self.provider,
            ) from exc

        return self._parse_response(resp, chat_id=chat_id, op="sendMessage")

    # ------------------------------------------------------------------
    # Outbound — answerCallbackQuery (acknowledge button taps)
    # ------------------------------------------------------------------

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """Acknowledge a callback_query so Telegram clears the spinner.

        Telegram requires every callback_query be answered within 10s
        or the user sees a "loading…" indicator forever. The webhook
        receiver calls this immediately after recording the approval —
        before any heavyweight workflow resume — so the UX stays snappy
        even if downstream processing is slow.

        text/show_alert are optional: when non-empty they pop up a small
        toast (or full alert if show_alert=True) on the user's chat.
        Phase 1.5 we use the toast to confirm "Approval recorded".
        """
        if not self.is_configured():
            raise BotSendError(
                "TelegramBotConfig.bot_token not set — refusing to answer.",
                provider=self.provider,
            )

        url = f"{self.config.api_base}/bot{self.config.bot_token}/answerCallbackQuery"
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise BotSendError(
                f"Telegram network error on answerCallbackQuery({callback_query_id}): {exc}",
                provider=self.provider,
            ) from exc

        return self._parse_response(
            resp, chat_id=None, op="answerCallbackQuery", ref=callback_query_id
        )

    # ------------------------------------------------------------------
    # Markup helpers
    # ------------------------------------------------------------------

    def format_workflow_approval(
        self, markup: WorkflowApprovalMarkup,
    ) -> dict[str, Any]:
        """Build Telegram inline_keyboard JSON from the abstract markup.

        Each ApprovalButton in the markup is either a URL button or a
        callback_data button (mutually exclusive — base.py validates).
        The wire shape per Telegram Bot API:

            URL button:           {"text": "...", "url": "..."}
            callback button:      {"text": "...", "callback_data": "..."}

        Mixed rows are allowed; Telegram renders them side-by-side. We
        always emit a single row of two buttons (Approve / Reject).
        """
        return {
            "inline_keyboard": [
                [
                    self._button_json(markup.approve),
                    self._button_json(markup.reject),
                ]
            ]
        }

    @staticmethod
    def _button_json(btn: ApprovalButton) -> dict[str, Any]:
        """Pure helper — translate one ApprovalButton to its wire dict.

        base.py guarantees exactly one of url/callback_data is set; this
        function trusts that invariant + emits the matching key. Putting
        this as a method (not module-level) keeps the Telegram-specific
        JSON shape encapsulated in the adapter — Zalo / Line adapters
        will have their own _button_json with their own key names.
        """
        if btn.callback_data is not None:
            return {"text": btn.text, "callback_data": btn.callback_data}
        return {"text": btn.text, "url": btn.url}

    # Telegram MarkdownV2 escape characters per
    # https://core.telegram.org/bots/api#markdownv2-style
    _MARKDOWN_V2_ESCAPE = set("_*[]()~`>#+-=|{}.!\\")

    def escape_markdown(self, text: str) -> str:
        """Escape MarkdownV2 special characters per Telegram spec.

        Caller passes the result through send_message with parse_mode
        'MarkdownV2'. Failing to escape leads to silent message rejection
        by Telegram → use this helper for any user-supplied content.
        """
        out_chars = []
        for ch in text:
            if ch in self._MARKDOWN_V2_ESCAPE:
                out_chars.append("\\")
            out_chars.append(ch)
        return "".join(out_chars)

    # ------------------------------------------------------------------
    # Internal — response parsing shared by sendMessage + answerCallbackQuery
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        resp: httpx.Response,
        *,
        chat_id: str | int | None,
        op: str,
        ref: str | None = None,
    ) -> dict[str, Any]:
        """Map a Bot API response into either a result dict or a
        BotSendError. Centralised so every Bot API call gets the same
        error handling — one place to update if Telegram changes the
        envelope shape.
        """
        # Telegram returns 200 even for some errors (with ok=false) and
        # 4xx for others (rate limit, bad token, blocked). Try JSON first
        # so we surface the most specific error message available.
        try:
            body = resp.json()
        except ValueError:
            raise BotSendError(
                f"Telegram {op} returned non-JSON status={resp.status_code}: "
                f"{resp.text[:200]!r}",
                provider=self.provider,
                provider_code=resp.status_code,
            )

        if not isinstance(body, dict) or "ok" not in body:
            raise BotSendError(
                f"Telegram {op} returned unexpected envelope: {body!r}",
                provider=self.provider,
                provider_code=resp.status_code,
            )

        if body.get("ok") is True:
            log.info(
                "telegram.api.ok",
                op=op,
                chat_id=chat_id,
                ref=ref,
                status=resp.status_code,
            )
            return body.get("result") if isinstance(body.get("result"), dict) else body

        # ok=false — error_code + description give the operator the
        # diagnostic. parameters.retry_after is set on rate limits.
        log.warning(
            "telegram.api.err",
            op=op,
            chat_id=chat_id,
            ref=ref,
            status=resp.status_code,
            error_code=body.get("error_code"),
            description=body.get("description"),
        )
        raise BotSendError(
            f"Telegram {op} failed: {body.get('description', 'unknown')}",
            provider=self.provider,
            provider_code=body.get("error_code") or resp.status_code,
        )
