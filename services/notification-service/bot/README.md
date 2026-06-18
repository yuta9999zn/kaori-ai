# `bot/` — Pluggable chatbot adapter (Phase 1 v4 P1-S8 scaffold)

> **Status:** scaffold (P1-S8). Telegram adapter contract surface; full impl P15-S9.
> **Decision:** ADR-0018 — Telegram over Zalo (tax registration burden); pluggable adapter pattern so swap to Zalo / Line / Slack later is config-only.

## Why adapter pattern (anh chốt 2026-05-08)

> "muốn để có thể thay thế các loại chatbot, và bây giờ dùng telegram nhé"

Caller code (outbox dispatcher, workflow approval node, NOV digest cron) writes against the abstract `BotAdapter` interface only. Switching providers later = change one env var (`KAORI_BOT_PROVIDER=zalo`) + ship the new adapter — no caller refactor.

## Why Telegram first (not Zalo OA)

Anh confirmed Zalo Official Account (OA) trong 2025 yêu cầu **đăng ký thuế chính thức** — compliance burden lớn cho Kaori. Telegram Bot:

- Free + open API (BotFather setup ~1 phút)
- No Vietnamese tax filing required for Telegram bot operation
- Inline keyboard for workflow approval (Approve/Reject buttons)
- Webhook receiver for callback handling
- Group + channel support — manager routes notifications to a team channel

**Trade-off:** Telegram has lower SME penetration than Zalo in Vietnam. Acceptance: Telegram is the **Kaori-side outbound** (notifications + approvals); customers can keep using Zalo for internal ops, and Process Mining still reads Zalo metadata via PM-EVT-003 connector (read-only, customer's OA, customer's tax filing).

## Architecture

```
bot/
├── __init__.py          ← factory get_bot_adapter() — env-driven dispatch
├── base.py              ← BotAdapter ABC + WorkflowApprovalMarkup +
│                          ApprovalButton + BotSendError dataclasses
├── telegram.py          ← TelegramBotAdapter (Phase 1 impl) + TelegramBotConfig
├── (zalo.py)            ← Phase 2+ if customer demands
├── (line.py)            ← Phase 3 SE Asia expansion
├── (slack.py)           ← Phase 3 international option
└── README.md            ← this file
```

Caller code:

```python
from bot import (
    ApprovalButton, BotSendError, WorkflowApprovalMarkup, get_bot_adapter,
)

adapter = get_bot_adapter()  # honors KAORI_BOT_PROVIDER env (default 'telegram')
if not adapter.is_configured():
    log.info("bot.not_configured", provider=adapter.provider)
    return

markup_dataclass = WorkflowApprovalMarkup(
    workflow_name="Churn Detection",
    run_id="run-7",
    approve=ApprovalButton(text="✅ Approve", url="https://kaori.ai/wf/run-7/approve"),
    reject=ApprovalButton(text="❌ Reject", url="https://kaori.ai/wf/run-7/reject"),
)
provider_markup = adapter.format_workflow_approval(markup_dataclass)
await adapter.send_message(chat_id=chat_id, text="...", reply_markup=provider_markup)
```

## Adding a new provider (future)

1. Create `bot/<provider>.py` with `<Provider>BotAdapter` extending `BotAdapter`.
2. Implement: `is_configured()`, `send_message()`, `format_workflow_approval()`. Optionally override `escape_markdown()` for provider-specific text formatting.
3. Add `<provider>` to `available_providers()` tuple in `bot/__init__.py` + dispatch case in `get_bot_adapter()`.
4. Add unit tests mirroring `tests/test_bot.py`.
5. Update this README's Architecture section.

## Phase 1 v4 P1-S8 scope

- `bot/base.py` — abstract surface
- `bot/telegram.py` — Telegram adapter (`send_message` raises NotImplementedError until P15-S9)
- `bot/__init__.py` — factory + provider registry
- ~13 unit tests in `tests/test_bot.py` covering config, adapter dispatch, format_workflow_approval, MarkdownV2 escaping

## Phase 1.5 P15-S9 scope

- httpx POST to `https://api.telegram.org/bot{TOKEN}/sendMessage`
- Webhook receiver for callback button taps (FastAPI route)
- Vault-backed token + per-tenant chat allow-list (`tenant/{tenant_id}/telegram/chat_id`)
- Retry policy per REL-008 + circuit breaker per REL-018
- Outbox integration: `outbox_poller` reads `notification_outbox` rows with `channel='bot:telegram'` and dispatches via the adapter

## Use cases (Phase 1.5+)

1. **Workflow approval** — workflow node `external` triggers a manager bot message with inline Approve/Reject. Webhook records verdict; Temporal signal moves the workflow.
2. **Quota alert push** — `quota-alert` outbox row publishes to bot in addition to email (F-037).
3. **Monthly NOV digest** — `org_intel/economics/nov.compute_monthly_nov` results posted to manager's chat (NOV-RPT-019).
4. **Adoption alert** — when AI-HSC composite drops below STRUGGLING, CSM gets a bot ping (AI-INT-018).

## Operational notes (Telegram-specific)

- **Bot creation:** `@BotFather` → `/newbot` → save token → set `KAORI_TELEGRAM_BOT_TOKEN` env (Phase 1) or write to `secret/platform/telegram/bot_token` Vault path (P15-S9).
- **Chat opt-in:** customer adds `@KaoriBot` to their Telegram group; admin posts `/register` command; bot replies with verification code; admin enters code in Kaori `/p2/settings/notifications` to bind chat_id to tenant.
- **MarkdownV2 escaping:** use `adapter.escape_markdown(text)` for any user-supplied content. Failing to escape silently rejects the message at Telegram side.

## References

- ADR-0018 (`docs/adr/0018-telegram-over-zalo-for-bot.md`)
- BACKLOG_V4 P1-S8 (Zalo Bot row supersedes to Telegram via adapter pattern)
- `docs/strategic/WORKFLOW_SYSTEM.md` PART V (Action Nodes — external side-effect class)
- Telegram Bot API: https://core.telegram.org/bots/api
