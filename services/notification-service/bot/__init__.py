"""
Bot adapter package — pluggable chat-bot dispatch.

Anh chốt 2026-05-08: hệ thống cần **adapter pattern** cho chatbot —
swap được giữa Telegram / Zalo / Line / Slack / etc. Phase 1 ship
Telegram làm provider hiện tại (ADR-0018: Zalo OA cần đăng ký thuế
2025, Telegram free + open).

Architecture:

    bot/
    ├── base.py              ← BotAdapter ABC + WorkflowApprovalMarkup +
    │                           BotSendError + ApprovalButton dataclass
    ├── telegram.py          ← TelegramBotAdapter impl + TelegramConfig
    ├── (zalo.py)            ← Phase 2 if customer requires
    ├── (line.py)            ← Phase 3 SE Asia expansion
    └── __init__.py          ← factory `get_bot_adapter(provider=...)`

Caller code (notification-service outbox dispatcher, workflow approval
node) imports the abstract `BotAdapter` API only:

    from bot import get_bot_adapter
    bot = get_bot_adapter()  # picks provider from KAORI_BOT_PROVIDER env
    if bot.is_configured():
        await bot.send_message(chat_id="...", text="...", reply_markup=markup)

Switching providers Phase 2+ = set env var, no caller change.
"""
from __future__ import annotations

import os

from .base import (
    ApprovalButton,
    BotAdapter,
    BotSendError,
    WorkflowApprovalMarkup,
)
from .telegram import TelegramBotAdapter, TelegramBotConfig

__all__ = [
    "ApprovalButton",
    "BotAdapter",
    "BotSendError",
    "WorkflowApprovalMarkup",
    "TelegramBotAdapter",
    "TelegramBotConfig",
    "get_bot_adapter",
    "available_providers",
]


def available_providers() -> tuple[str, ...]:
    """Provider keys this build knows about. Add to the tuple when a
    new adapter lands; factory dispatches by case-insensitive match."""
    return ("telegram",)


def get_bot_adapter(provider: str | None = None) -> BotAdapter:
    """Return a configured BotAdapter for the named provider.

    Resolution order:
      1. Explicit ``provider`` arg (caller forces a specific adapter).
      2. ``KAORI_BOT_PROVIDER`` env var.
      3. Default 'telegram' (ADR-0018 — current Phase 1 choice).

    Raises ValueError when the provider isn't recognised. Returns the
    adapter instance even when not configured — caller's responsibility
    to check ``adapter.is_configured()`` before sending (graceful skip
    when a tenant hasn't opted in yet).
    """
    name = (provider or os.getenv("KAORI_BOT_PROVIDER") or "telegram").strip().lower()
    if name == "telegram":
        return TelegramBotAdapter()
    raise ValueError(
        f"Unknown bot provider {name!r}; available: {available_providers()}"
    )
