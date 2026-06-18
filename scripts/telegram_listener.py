"""
Telegram bridge listener — local long-poll for remote work assignment.

Usage:
    # Start in background while CLI session is active
    python scripts/telegram_listener.py &

    # Or foreground (for debugging)
    python scripts/telegram_listener.py --foreground

Architecture (per anh chốt 2026-05-08):
  * Listener runs ONLY while Claude Code CLI session is active.
  * Inbox: appends `[<timestamp> from @<username>]\\n<message>\\n` to
    .claude/telegram_inbox.md. Claude reads this file at each session
    start (or when anh prompts "check telegram") and processes pending
    items.
  * Outbox: Claude appends reply text to .claude/telegram_outbox.md.
    Listener tails outbox, sends each new line as a Telegram message.
  * Auto-ack: anh's first message after listener start gets an instant
    "Em đã nhận, sẽ xử lý khi pickup" reply so anh isn't confused while
    Claude is busy on another task.
  * Whitelist: only chat_id in KAORI_TELEGRAM_CHAT_ID_WHITELIST env
    receives bot responses + can issue commands. Cross-tenant defense
    against bot URL leaks.

Env vars (read from .env via python-dotenv if present, or OS env):
  KAORI_TELEGRAM_BOT_TOKEN          Required — from @BotFather /newbot.
  KAORI_TELEGRAM_CHAT_ID_WHITELIST  Required — comma-separated chat ids
                                    allowed to send commands. Other
                                    chats get a polite refusal.
  KAORI_TELEGRAM_POLL_INTERVAL      Optional — long-poll timeout
                                    seconds (default 25).

Files (under .claude/):
  telegram_inbox.md    — INCOMING messages from anh (Claude reads).
  telegram_outbox.md   — OUTGOING replies (Claude writes, listener
                         tails + sends).
  telegram_state.json  — Persisted last-update-id so a restart doesn't
                         re-fetch already-processed messages.

Stop listener: Ctrl-C in foreground; or `taskkill /F /IM python.exe`
for background. Restart picks up where it left off via state file.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
INBOX_PATH = REPO_ROOT / ".claude" / "telegram_inbox.md"
OUTBOX_PATH = REPO_ROOT / ".claude" / "telegram_outbox.md"
STATE_PATH = REPO_ROOT / ".claude" / "telegram_state.json"

DEFAULT_POLL_INTERVAL = 25  # Telegram long-poll max
TELEGRAM_API = "https://api.telegram.org"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> None:
    """Tiny .env parser. python-dotenv would do this but adding a dep
    for a local-dev script is overkill."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _config() -> tuple[str, set[int], int]:
    """Read + validate env. Returns (bot_token, whitelist_ids, poll_interval)."""
    _load_env_file(REPO_ROOT / ".env")

    token = os.getenv("KAORI_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit(
            "KAORI_TELEGRAM_BOT_TOKEN not set. Get one from @BotFather "
            "and add to .env (KAORI_TELEGRAM_BOT_TOKEN=...)"
        )

    raw_ids = os.getenv("KAORI_TELEGRAM_CHAT_ID_WHITELIST", "").strip()
    if not raw_ids:
        sys.exit(
            "KAORI_TELEGRAM_CHAT_ID_WHITELIST not set. Find your chat_id "
            "via https://api.telegram.org/bot<TOKEN>/getUpdates after "
            "sending /start to your bot. Comma-separated for multiple."
        )
    try:
        whitelist = {int(x.strip()) for x in raw_ids.split(",") if x.strip()}
    except ValueError as exc:
        sys.exit(f"Invalid chat ids: {raw_ids!r} — must be integers. {exc}")

    poll_interval = int(os.getenv("KAORI_TELEGRAM_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
    return token, whitelist, poll_interval


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def _load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_update_id": 0, "outbox_offset": 0, "auto_ack_seen_chats": []}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Telegram API
# ---------------------------------------------------------------------------


def _get_updates(token: str, offset: int, timeout: int) -> list[dict[str, Any]]:
    """Long-poll Telegram getUpdates."""
    try:
        with httpx.Client(timeout=timeout + 5) as client:
            r = client.get(
                f"{TELEGRAM_API}/bot{token}/getUpdates",
                params={"offset": offset, "timeout": timeout, "allowed_updates": "message"},
            )
        r.raise_for_status()
        body = r.json()
        if not body.get("ok"):
            print(f"[telegram] getUpdates not OK: {body}", file=sys.stderr)
            return []
        return body.get("result", [])
    except httpx.HTTPError as exc:
        print(f"[telegram] getUpdates error: {exc}", file=sys.stderr)
        time.sleep(2)
        return []


def _send_message(token: str, chat_id: int, text: str) -> None:
    """Send a single message. Caps text at 4096 chars (Telegram limit)."""
    text = (text or "").strip()
    if not text:
        return
    if len(text) > 4096:
        text = text[:4090] + " […]"
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
        if r.status_code != 200:
            print(f"[telegram] sendMessage {r.status_code}: {r.text[:200]}", file=sys.stderr)
    except httpx.HTTPError as exc:
        print(f"[telegram] sendMessage error: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Inbox + outbox file handling
# ---------------------------------------------------------------------------


def _append_inbox(msg: dict[str, Any]) -> None:
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    user = msg.get("from", {})
    username = user.get("username") or user.get("first_name") or str(user.get("id", "?"))
    text = msg.get("text", "")
    entry = f"\n[{ts} from @{username}]\n{text}\n"
    with INBOX_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)


def _drain_outbox(token: str, chat_ids: set[int], state: dict[str, Any]) -> None:
    """Send any new lines in outbox. Tracks byte offset across restarts."""
    if not OUTBOX_PATH.exists():
        return
    size = OUTBOX_PATH.stat().st_size
    offset = state.get("outbox_offset", 0)
    if size <= offset:
        return
    with OUTBOX_PATH.open("r", encoding="utf-8") as f:
        f.seek(offset)
        new_text = f.read()
    if not new_text.strip():
        state["outbox_offset"] = size
        _save_state(state)
        return
    # Split by message separator "\n---\n" so Claude can write multi-line
    # replies as one logical message. Lone single-line replies just have
    # no separator.
    chunks = [c.strip() for c in new_text.split("\n---\n") if c.strip()]
    for chunk in chunks:
        for cid in chat_ids:
            _send_message(token, cid, chunk)
    state["outbox_offset"] = size
    _save_state(state)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


_running = True


def _stop(_sig, _frame):
    global _running
    _running = False
    print("[telegram] stop requested", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kaori Telegram bridge listener")
    parser.add_argument(
        "--foreground", action="store_true",
        help="Run with verbose stdout (debug). Default is quiet (background).",
    )
    args = parser.parse_args()

    token, whitelist, poll_interval = _config()
    state = _load_state()

    # Pre-create files so Claude finds them empty rather than missing
    INBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_PATH.touch(exist_ok=True)
    OUTBOX_PATH.touch(exist_ok=True)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if args.foreground:
        print(f"[telegram] listener started (whitelist={whitelist}, poll={poll_interval}s)")

    auto_ack_seen = set(state.get("auto_ack_seen_chats", []))

    while _running:
        # 1. Drain outbox first (Claude may have written replies between polls)
        _drain_outbox(token, whitelist, state)

        # 2. Long-poll Telegram for new messages
        updates = _get_updates(token, offset=state["last_update_id"] + 1, timeout=poll_interval)
        if not updates:
            continue

        for update in updates:
            update_id = update.get("update_id", 0)
            if update_id > state["last_update_id"]:
                state["last_update_id"] = update_id

            msg = update.get("message")
            if not msg:
                continue

            chat = msg.get("chat", {})
            chat_id = chat.get("id")
            if chat_id not in whitelist:
                # Polite refusal — don't leak that we have an allow-list.
                _send_message(
                    token, chat_id,
                    "Sorry, this bot is private. Contact owner for access.",
                )
                continue

            text = msg.get("text", "")
            if args.foreground:
                print(f"[telegram] inbox: chat={chat_id} text={text[:60]!r}")

            _append_inbox(msg)

            # First-message-per-chat-per-session ack
            if chat_id not in auto_ack_seen:
                _send_message(
                    token, chat_id,
                    "Em đã nhận. Em sẽ xử lý khi pickup queue (Claude Code session live).",
                )
                auto_ack_seen.add(chat_id)
                state["auto_ack_seen_chats"] = sorted(auto_ack_seen)

            _save_state(state)

    if args.foreground:
        print("[telegram] listener stopped")


if __name__ == "__main__":
    main()
