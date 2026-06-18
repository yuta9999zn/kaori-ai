"""
BotAdapter — pluggable chatbot dispatch contract.

Phase 1 v4 P1-S8 ships the abstract surface so caller code (outbox
dispatcher, workflow approval node, NOV digest cron) writes against
the interface only. Concrete adapters live in sibling modules
(telegram.py shipped Phase 1; zalo.py / line.py / slack.py future).

The contract surface stays minimal Phase 1 — just enough for the
3 use cases anh has in mind for P15-S9:
  1. Workflow approval (inline keyboard with Approve/Reject)
  2. Quota alert push (text + optional URL button)
  3. Monthly NOV digest (text + optional formatting)

Future use cases (multi-step conversation, file attachments, etc.)
extend this interface; adapters opt in by overriding.

Why dataclasses for markup instead of dict[str, Any]:
  * Unit tests assert on .approve_url, not on dict[str].
  * Future adapters (Zalo, Line) translate the abstract dataclass to
    their provider-specific JSON shape inside their adapter — caller
    code never sees the wire format.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


class BotSendError(RuntimeError):
    """Raised on any bot dispatch failure (network, rate limit, blocked,
    invalid token). Carries provider-side error code + description so
    ops + audit log can identify the cause."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        provider_code: str | int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.provider_code = provider_code


@dataclass(frozen=True)
class ApprovalButton:
    """One button in a workflow-approval markup.

    Exactly one of ``url`` and ``callback_data`` must be set. URL buttons
    open a browser tab on tap (Phase 1 default — useful when the
    approval page lives in the Kaori web app). callback_data buttons
    POST a callback_query to the bot's webhook (Phase 1.5+ pattern —
    allows the manager to approve from inside the chat without leaving
    Telegram, used for fast-path approval gates).

    Mutual exclusivity is checked at construction so a half-built markup
    can't sneak past + render a non-functional button.
    """
    text: str
    url: str | None = None
    callback_data: str | None = None

    def __post_init__(self) -> None:
        if (self.url is None) == (self.callback_data is None):
            raise ValueError(
                "ApprovalButton requires exactly one of url / callback_data "
                f"(got url={self.url!r}, callback_data={self.callback_data!r})"
            )
        # Telegram caps callback_data at 64 bytes UTF-8 per Bot API.
        # Fail loud at construction so a 65-byte payload doesn't silently
        # truncate at send time.
        if self.callback_data is not None:
            byte_len = len(self.callback_data.encode("utf-8"))
            if byte_len > 64:
                raise ValueError(
                    f"callback_data must be <=64 bytes UTF-8 per Telegram Bot API "
                    f"(got {byte_len} bytes)"
                )


@dataclass(frozen=True)
class WorkflowApprovalMarkup:
    """Adapter-agnostic representation of a 2-button approval prompt.

    TelegramBotAdapter.format_workflow_approval() converts this to
    Telegram's inline_keyboard JSON; ZaloBotAdapter would convert the
    same dataclass to Zalo OA's button format.
    """
    workflow_name: str
    run_id: str
    approve: ApprovalButton
    reject: ApprovalButton

    def __post_init__(self) -> None:
        if not self.workflow_name or not self.run_id:
            raise ValueError(
                "workflow_name + run_id required for WorkflowApprovalMarkup"
            )


class BotAdapter(abc.ABC):
    """Abstract chatbot adapter. Subclass per provider.

    Subclasses implement:
      * provider — class-level identifier ('telegram', 'zalo', ...)
      * is_configured() — True when credentials available + ready to send
      * send_message(chat_id, text, reply_markup=None) — async dispatch
      * format_workflow_approval(markup) — provider-specific markup JSON

    Optional helpers:
      * escape_markdown(text) — provider-specific escaping (Telegram
        MarkdownV2 has its own escape rules; Zalo uses plain text)
    """

    #: Lower-case provider identifier — must match the registration
    #: key in bot/__init__.py get_bot_adapter().
    provider: str = ""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True when the adapter has credentials + can attempt send_message.

        Caller pattern::

            adapter = get_bot_adapter()
            if not adapter.is_configured():
                log.info("bot.not_configured", provider=adapter.provider)
                return  # skip gracefully
            await adapter.send_message(...)
        """

    @abc.abstractmethod
    async def send_message(
        self,
        *,
        chat_id: str | int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message via the configured provider.

        Args:
            chat_id: provider-specific identifier (Telegram int, Zalo str).
                     Caller resolves from per-tenant allow-list.
            text:    message body. Caller pre-escapes per the provider's
                     formatting rules (see ``escape_markdown`` helper).
            reply_markup: provider-specific markup JSON (e.g. result of
                          ``format_workflow_approval`` or quota-alert button).

        Returns:
            Provider response dict (parsed JSON). On failure raises
            BotSendError.
        """

    @abc.abstractmethod
    def format_workflow_approval(
        self, markup: WorkflowApprovalMarkup,
    ) -> dict[str, Any]:
        """Translate the abstract approval markup to the provider's
        button format. Pure function — no I/O — so tests can assert on
        the wire shape without a live bot.
        """

    def escape_markdown(self, text: str) -> str:
        """Optional provider-specific escaping. Default: identity (caller
        sends pre-escaped text). Telegram overrides with MarkdownV2
        escape spec.
        """
        return text
