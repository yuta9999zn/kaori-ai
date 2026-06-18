# Telegram Bridge — Remote Work Assignment

> **Status:** Phase 1 local-only utility. Not for production.
> **Owner:** anh (single-user)
> **Replaces:** Claude phone app + Remote Control (em recommended originally;
> anh chốt Telegram 2026-05-08).

## What it does

Listener script `scripts/telegram_listener.py` long-polls Telegram bot updates
and writes anh's messages to `.claude/telegram_inbox.md`. Em (Claude) reads
that file at session start and processes pending items. Em writes replies to
`.claude/telegram_outbox.md`; listener tails outbox + sends them back to
anh's Telegram.

## One-time setup

### 1. Create a bot via @BotFather

In Telegram, search **@BotFather** and:

```
/newbot
Bot name: Kaori Assistant
Bot username: kaori_yuta_bot   # any *_bot, must be unique
```

@BotFather sends back a token like `123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`.

### 2. Find your chat_id

1. Search the new bot in Telegram, send `/start`.
2. Open a browser, paste:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":<NUMBER>, ...}` — `<NUMBER>` is your `chat_id`.

### 3. Add to .env (gitignored)

```
KAORI_TELEGRAM_BOT_TOKEN=123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
KAORI_TELEGRAM_CHAT_ID_WHITELIST=123456789
```

Multiple chat_ids comma-separated. Only listed ids can issue commands.

## Daily usage

### Start listener (only while Claude Code CLI active per ADR)

In a **second terminal** (so it doesn't block CLI):

```bash
cd "D:\Kaori System"
python scripts/telegram_listener.py --foreground
```

Or background (no log spam):

```bash
start /b python scripts\telegram_listener.py
```

### Send work from phone

Open Telegram, chat with bot:

> Em check failing CI on PR 200 nhé

Listener appends to `.claude/telegram_inbox.md` + auto-acks anh.

### Em pickup (Claude session)

Anh start CLI session → say "check telegram" → em reads inbox → process →
write reply to outbox. Listener picks up + sends to phone.

Em can also run `cat .claude/telegram_inbox.md` proactively at session
start.

### Em respond

Em append to `.claude/telegram_outbox.md`:

```
Done. CI fix pushed in commit abc1234. Next?
---
Plus em đã update CLAUDE.md §14.
```

The `---` on its own line splits multiple messages. Listener sends each
chunk as one Telegram message. Caps at 4096 chars per chunk (Telegram limit).

### Stop listener

Ctrl-C in foreground, or `taskkill /F /IM python.exe` (be careful — kills
all Python).

## Files

| Path | Purpose |
|---|---|
| `scripts/telegram_listener.py` | The bridge daemon |
| `.claude/telegram_inbox.md` | Inbound messages from anh (Claude reads) |
| `.claude/telegram_outbox.md` | Outbound replies (Claude writes) |
| `.claude/telegram_state.json` | Last-update-id + outbox byte-offset |
| `.env` | Bot token + whitelist (gitignored — DO NOT COMMIT) |

All `.claude/telegram_*` files are gitignored (parent `.claude/` is in `.gitignore`).

## Security

- **Whitelist enforced** — non-whitelisted chat_ids get a polite "private bot"
  refusal. Bot URL leak doesn't grant access.
- **Token in .env only** — never logged, never committed. `git status`
  before commit; `gitleaks` workflow scans for accidental token leaks.
- **No code execution from message text** — Claude reads inbox as plain
  text instructions, applies same judgement + invariants as in-CLI work.
  Anh CANNOT make Claude bypass K-1..K-20 via Telegram.

## Troubleshooting

**Listener exits with config error.** Check `.env` has both KAORI_TELEGRAM_BOT_TOKEN
+ KAORI_TELEGRAM_CHAT_ID_WHITELIST set. Token format `<digits>:<base64-ish>`.

**No messages reaching inbox.** Check bot is unblocked in Telegram (you sent
`/start`). Test direct API call:
```bash
curl https://api.telegram.org/bot<TOKEN>/getMe
```
Should return `{"ok":true, "result":{...}}`.

**Listener idle forever.** Long-poll timeout is 25s by default; expected.

**Reply doesn't arrive.** Check `.claude/telegram_outbox.md` has content;
listener log (foreground mode) shows send attempts.

**Multiple messages get joined.** Use `\n---\n` separator in outbox.

## Phase 2 considerations (deferred per anh)

- Webhook mode (no polling) — needs public HTTPS endpoint.
- Inline keyboard buttons for workflow approval — bot adapter at
  `services/notification-service/bot/telegram.py` already has the format.
- 24/7 background daemon — Windows Task Scheduler or nssm.

## See also

- ADR-0018 (`docs/adr/0018-pluggable-bot-adapter-telegram-default.md`) — pluggable bot adapter (outbound notifications, separate from this inbound bridge)
- `services/notification-service/bot/telegram.py` — outbound Telegram for workflow notifications
- Memory `project_v4_phase_a_landed.md` — anh chốt Telegram for remote work 2026-05-08
