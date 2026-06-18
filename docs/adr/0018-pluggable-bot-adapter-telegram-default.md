# ADR-0018 — Pluggable bot adapter (Telegram default Phase 1)

> **Status:** accepted
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0010 (modular monolith) · BACKLOG_V4 P1-S8 · `docs/strategic/WORKFLOW_SYSTEM.md` PART V (Action Nodes — external side-effect class)

## Context

BACKLOG_V4 P1-S8 originally specified **Zalo Bot** for the Kaori-side outbound chat layer — workflow approval messages, quota alerts, monthly NOV digest. The choice fit Vietnamese SME context (Zalo is the dominant ops chat in VN).

Two facts surfaced mid-Sprint P1-S8:

1. **Zalo Official Account (OA) needs tax registration in 2025.** Operating a Zalo OA as a Vietnamese SaaS = file business tax, register with relevant tax authority, ongoing compliance burden. Acceptable for an established VN business; heavy for a Phase 1 SaaS pilot with single-digit customers.
2. **Anh wants the architecture to be provider-pluggable** — "muốn để có thể thay thế các loại chatbot, và bây giờ dùng telegram nhé". A future customer might require Zalo (and accept the tax cost as part of the engagement); or Singapore expansion (Phase 2 P2-S23) might demand Line; or international (Phase 3) may want Slack. A hardcoded Telegram client would lock the codebase into one provider's wire format.

Two forces in tension:

- **Phase 1 simplicity** — one provider is easier to ship; abstraction overhead is real.
- **Future swap cost** — every caller (outbox dispatcher, workflow approval node, NOV digest cron) writing against a `TelegramBotClient` directly = painful refactor when Zalo arrives.

## Decision

We ship **`services/notification-service/bot/`** as a pluggable adapter package and pick **Telegram as the Phase 1 default provider**:

```
bot/
├── __init__.py     ← factory get_bot_adapter(provider=...) — env-driven dispatch
├── base.py         ← BotAdapter ABC + WorkflowApprovalMarkup +
│                     ApprovalButton + BotSendError dataclasses
└── telegram.py     ← TelegramBotAdapter (Phase 1 impl) + TelegramBotConfig
```

Caller code imports the abstract API:

```python
from bot import get_bot_adapter, WorkflowApprovalMarkup, ApprovalButton

adapter = get_bot_adapter()  # honors KAORI_BOT_PROVIDER env
if not adapter.is_configured():
    return  # graceful skip
markup = adapter.format_workflow_approval(WorkflowApprovalMarkup(...))
await adapter.send_message(chat_id=..., text=..., reply_markup=markup)
```

Switching providers Phase 2+ = `KAORI_BOT_PROVIDER=zalo` env var + ship `bot/zalo.py` extending `BotAdapter` — no caller refactor. Each adapter handles its own wire format (Telegram inline_keyboard JSON; Zalo OA button format; Line FlexMessage; Slack blocks).

Phase 1 v4 P1-S8 ships:
- `BotAdapter` abstract base + 4 dataclasses
- `TelegramBotAdapter` impl with `send_message` raising NotImplementedError until P15-S9 wires the actual httpx call (alongside Vault credential storage + K8s deploy)
- `format_workflow_approval` + `escape_markdown(MarkdownV2)` already functional Phase 1 (pure-function helpers, no I/O)
- 16 unit tests covering factory dispatch, abstract base, dataclass validation, and Telegram-specific behaviour

PM-EVT-003 Zalo Metadata connector (services/data-pipeline/ingestion/connectors/zalo_metadata/) is **unrelated to this decision**. That connector reads metadata from a customer's existing Zalo OA for Process Mining — read-only, customer-side OA, customer's tax filing. Different concern from the Kaori-side outbound bot.

## Consequences

### Positive

- One env var to swap providers; caller code stays stable across provider changes.
- Telegram free + open API + BotFather setup ~1 minute → Phase 1 can ship without Vietnamese tax registration burden.
- Adapter pattern surfaces the interface contract in `base.py` — any caller misuse (forgetting to escape MarkdownV2, missing reply_markup) shows up as type errors / failed unit tests, not silent message rejections at the provider side.
- Future adapters are isolated: a Zalo adapter bug can't accidentally break Telegram dispatch.
- Telegram is approve-flow-friendly: inline keyboard with Approve/Reject buttons is built-in (Zalo OA also supports buttons, format differs).

### Negative / accepted trade-offs

- One more layer of abstraction. Caller code goes through `BotAdapter` instead of `TelegramBotClient` directly — small cost in code reading. Worth it for the swap insurance.
- Telegram has lower SME penetration than Zalo in Vietnam. Acceptance: Telegram is the *Kaori-side outbound* (notifications + approvals). Customers can keep using Zalo for their internal ops; Process Mining still reads Zalo metadata via PM-EVT-003 (customer-side). The "manager won't see notifications because they don't have Telegram" risk is mitigated by Phase 1.5 P15-S9 also wiring `notification_outbox` rows to email — bot is supplementary, email is mandatory.
- Two providers to maintain Phase 2+ if a customer demands Zalo. Acceptance: revisit when first customer asks; tax burden may shift by then.

### Neutral / follow-ups

- Phase 1.5 P15-S9 wires `TelegramBotAdapter.send_message` to the real httpx call + Vault token + per-tenant chat allow-list.
- Phase 1.5 also wires `KaoriBot` BotFather setup + tenant chat opt-in flow (`/register` command in Kaori `/p2/settings/notifications`).
- Phase 2 evaluate Zalo adapter when first customer requests + accepts the tax registration trade-off.
- Phase 3 evaluate Line / Slack adapters per international expansion needs.

## Alternatives considered

- **Zalo OA only (original BACKLOG_V4 plan).** Rejected: tax registration burden too heavy Phase 1.
- **Telegram only, no abstraction.** Rejected: caller refactor cost when next provider lands. Adapter pattern is cheap to write upfront.
- **Email only (skip bot Phase 1).** Rejected: workflow approval inline buttons are a meaningful UX win; email reply parsing is fragile.
- **Slack as default (international from day 1).** Rejected: SME pilot is Vietnamese; Slack penetration in VN SMEs is near zero.

## References

- BACKLOG_V4 P1-S8 (Zalo Bot row supersedes to Telegram via adapter)
- `docs/sprint/P1-S8_ACCEPTANCE.md`
- `services/notification-service/bot/README.md`
- `services/notification-service/bot/base.py` (BotAdapter ABC)
- `services/notification-service/bot/telegram.py` (TelegramBotAdapter)
- Telegram Bot API: https://core.telegram.org/bots/api
- Memory `feedback_vnd_currency_format.md` — context for VN-specific UX choices
