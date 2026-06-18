"""
Zalo OA bot adapter — STUB (P15-S10 D4 / blocker carries from P15-S9 D4c).

Real Zalo OA wiring requires:
  1. Customer-side Zalo OA account (each tenant brings their own).
  2. Tax registration with Zalo (compliance burden documented in
     ADR-0018 — why we shipped Telegram first).
  3. Per-tenant API credentials stored in
     `secret/tenant/{tenant_id}/zalo_oa` (Vault path per ADR-0013).

This stub exists so:
  * P15-S10 D4 intervention_engine.resolve_intervention_plan() can
    name "zalo" as a channel decision without the dispatch activity
    blowing up at NotImplementedError-ed-import-time.
  * The Vietnamese-context resolver tests can assert ZALO routing
    without waiting on customer OA setup.
  * When the real Zalo path lands, swap the implementation here +
    the resolver/workflow consumers don't change.

The stub raises BotSendError("zalo not configured") on send_message so
a misconfig surfaces in workflow logs immediately rather than being
silently dropped.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog

from .base import BotAdapter, BotSendError, WorkflowApprovalMarkup

log = structlog.get_logger()


@dataclass(frozen=True)
class ZaloBotConfig:
    """Per-tenant Zalo OA credentials. Resolved from Vault path
    `secret/tenant/{tenant_id}/zalo_oa` in production; env override
    only for local dev / tests.
    """
    oa_id: str
    oa_secret: str
    api_base: str = "https://openapi.zalo.me"
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "ZaloBotConfig":
        return cls(
            oa_id=os.getenv("KAORI_ZALO_OA_ID", ""),
            oa_secret=os.getenv("KAORI_ZALO_OA_SECRET", ""),
            api_base=os.getenv("KAORI_ZALO_API_BASE", "https://openapi.zalo.me"),
            timeout_seconds=float(os.getenv("KAORI_ZALO_TIMEOUT_SECONDS", "10")),
        )


class ZaloBotAdapter(BotAdapter):
    """Stub adapter — every send raises until the real impl lands.

    is_configured() returns False when oa_id is empty so the
    intervention_engine resolver's `zalo_oa_configured` boolean has
    a single source of truth.
    """

    provider = "zalo"

    def __init__(self, config: ZaloBotConfig | None = None) -> None:
        self.config = config or ZaloBotConfig.from_env()

    def is_configured(self) -> bool:
        return bool(self.config.oa_id.strip()) and bool(self.config.oa_secret.strip())

    async def send_message(
        self,
        *,
        chat_id: str | int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        raise BotSendError(
            "Zalo OA adapter not implemented yet — P15-S10 D4 ships the stub. "
            "Real wiring blocks on customer Zalo OA account + tax registration "
            "(ADR-0018). Until then, the intervention_engine should resolve to "
            "Telegram or Email; if you see this error the resolver was bypassed.",
            provider=self.provider,
        )

    def format_workflow_approval(
        self, markup: WorkflowApprovalMarkup,
    ) -> dict[str, Any]:
        """Zalo's button shape is different from Telegram's. Until the
        real adapter ships, return an empty placeholder — the resolver
        should never route MANAGER_APPROVAL to Zalo (only Telegram
        supports REL-011 in Phase 1.5)."""
        return {}
