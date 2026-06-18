"""
Telegram webhook receiver — REL-011 approval gate inbound path.

The bot adapter pushes outbound messages with inline_keyboard buttons;
when a manager taps Approve / Reject, Telegram POSTs an Update to the
URL we registered with setWebhook. This module:

  1. Verifies the X-Telegram-Bot-Api-Secret-Token header matches the
     pre-shared secret (stops a random caller from forging approvals).
  2. Parses callback_query → workflow_id, run_id, node_id, decision.
  3. INSERTs into bot_approval_callbacks with ON CONFLICT DO NOTHING so a
     Telegram retry (same callback_query.id) is a no-op (REL-011 +
     Phần 6.2 — approval_gate is write_idempotent).
  4. Calls answerCallbackQuery so the manager sees an immediate ack.

The handler intentionally does NOT resume the matching workflow here —
that's the ai-orchestrator workflow_runtime worker's job. Splitting
keeps webhook latency under Telegram's 10s SLA + lets us redeploy the
two services independently.

Callback data encoding
======================
We use a compact `wa1:{decision}:{workflow_id}:{run_id}:{node_id}`
format (Bot API caps callback_data at 64 bytes UTF-8). When any
field would push us over 64 bytes the workflow author shortens the
node_id; the encoder validates length so a regression fails at send
time instead of silently truncating.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from .base import BotSendError

log = structlog.get_logger()


_CALLBACK_PREFIX = "wa1"  # version 1 — bump when payload format changes
_CALLBACK_FIELD_SEPARATOR = ":"


# ---------------------------------------------------------------------------
# Callback-data encoding — used by both the workflow node (when building the
# inline_keyboard) and the webhook handler (when decoding the tap).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalCallback:
    """Decoded callback_data payload."""
    decision: str          # 'approve' | 'reject'
    workflow_id: str
    run_id: str
    node_id: str


def encode_approval_callback(
    decision: str,
    workflow_id: str,
    run_id: str,
    node_id: str,
) -> str:
    """Build the callback_data string for an approval button.

    Format: ``wa1:{decision}:{workflow_id}:{run_id}:{node_id}``

    Telegram caps callback_data at 64 bytes UTF-8. We validate here +
    raise so a malformed callback never reaches the chat (silent
    truncation by Telegram would yield an undecodable payload).

    Decision values are restricted to 'approve' / 'reject' — the
    receiver pins the same allow-list on the way back.
    """
    if decision not in {"approve", "reject"}:
        raise ValueError(f"decision must be 'approve' or 'reject', got {decision!r}")
    for label, value in (
        ("workflow_id", workflow_id), ("run_id", run_id), ("node_id", node_id),
    ):
        if not value or _CALLBACK_FIELD_SEPARATOR in value:
            raise ValueError(
                f"approval callback {label} must be non-empty + must not contain "
                f"{_CALLBACK_FIELD_SEPARATOR!r}; got {value!r}"
            )
    payload = _CALLBACK_FIELD_SEPARATOR.join(
        [_CALLBACK_PREFIX, decision, workflow_id, run_id, node_id]
    )
    if len(payload.encode("utf-8")) > 64:
        raise ValueError(
            f"approval callback would exceed 64 bytes ({len(payload.encode('utf-8'))} bytes): "
            f"shorten node_id or run_id. Built: {payload!r}"
        )
    return payload


def decode_approval_callback(raw: str) -> ApprovalCallback:
    """Inverse of encode_approval_callback. Raises ValueError on garbage.

    Defensive against a stale callback (bot was redeployed with a new
    schema but a manager just tapped a button from yesterday's message)
    by version-prefix check; old-prefix payloads can be migrated by
    extending the prefix allow-list later.
    """
    parts = raw.split(_CALLBACK_FIELD_SEPARATOR)
    if len(parts) != 5 or parts[0] != _CALLBACK_PREFIX:
        raise ValueError(
            f"approval callback unrecognised: prefix or arity wrong: {raw!r}"
        )
    _, decision, workflow_id, run_id, node_id = parts
    if decision not in {"approve", "reject"}:
        raise ValueError(f"approval callback decision invalid: {decision!r}")
    return ApprovalCallback(
        decision=decision, workflow_id=workflow_id, run_id=run_id, node_id=node_id,
    )


# ---------------------------------------------------------------------------
# Handler — parse the Bot API Update payload + persist the decision.
# Pool + adapter are passed in so unit tests can supply mocks without
# globals (matches the OutboxPoller / SmtpClient injection pattern).
# ---------------------------------------------------------------------------


@dataclass
class WebhookContext:
    """Per-request dependencies. Bundled so the FastAPI route handler
    has one parameter to wire in main.py and tests have one fixture
    to compose."""
    pool: Any                         # asyncpg.Pool, kept Any to skip the import in tests
    adapter: Any                      # TelegramBotAdapter (or stub)
    expected_secret: str              # shared with Telegram via setWebhook(secret_token=)
    enterprise_resolver: Any          # callable: callback → enterprise_id (UUID)


@dataclass(frozen=True)
class HandledApproval:
    """Return shape for handle_callback_query so the route can build a
    minimal response without the handler knowing about HTTP at all.
    Tests can assert on it without reaching into mocks."""
    inserted: bool
    callback_query_id: str
    decision: str
    workflow_id: str
    run_id: str
    node_id: str


class WebhookSecretMismatch(RuntimeError):
    """Raised when the X-Telegram-Bot-Api-Secret-Token header doesn't
    match the configured secret. The route maps this to HTTP 401."""


async def handle_telegram_update(
    update: dict[str, Any],
    secret_header: str | None,
    ctx: WebhookContext,
) -> HandledApproval | None:
    """Top-level entry — verify secret, route on update type, persist.

    Returns ``None`` if the update is something we don't handle (a plain
    text message, a my_chat_member update, etc.). Returns a
    HandledApproval when a callback_query was decoded + the row attempted.
    """
    _verify_secret(secret_header, ctx.expected_secret)

    callback_query = update.get("callback_query")
    if not callback_query:
        # Not an approval — could be a text message, a join event, etc.
        # We log + ignore so we don't block on Telegram's other update types.
        log.info("telegram.webhook.update_ignored",
                 update_keys=sorted(update.keys()))
        return None

    return await _handle_callback_query(callback_query, ctx)


def _verify_secret(provided: str | None, expected: str) -> None:
    """Constant-time comparison of the secret header.

    When `expected` is empty we treat verification as disabled — useful
    for local dev / tests that don't set up a real bot. Production wires
    a non-empty secret; the secret check fails closed (mismatch raises)
    rather than open (silently passes) when expected is set.
    """
    if not expected:
        return
    # secrets.compare_digest avoids timing leaks; Telegram echoes our
    # secret_token verbatim so direct equality would also work, but
    # constant-time is the safe default.
    import secrets
    if not provided or not secrets.compare_digest(provided, expected):
        raise WebhookSecretMismatch(
            "X-Telegram-Bot-Api-Secret-Token mismatch"
        )


async def _handle_callback_query(
    callback_query: dict[str, Any],
    ctx: WebhookContext,
) -> HandledApproval:
    """Decode + persist a single callback_query update.

    Three Telegram-side calls might fail:
      1. answerCallbackQuery — best-effort; log + continue. The decision
         is already recorded so retrying the same Update lands on a
         no-op insert; the manager just sees the spinner for 10s before
         Telegram clears it on its own.
      2. The DB insert — uses ON CONFLICT DO NOTHING so a Telegram retry
         is idempotent.
      3. The callback decode — raises ValueError; route maps to 400.
    """
    callback_query_id = str(callback_query.get("id") or "")
    if not callback_query_id:
        raise ValueError("callback_query missing id")

    raw_data = callback_query.get("data") or ""
    decoded = decode_approval_callback(raw_data)

    # enterprise_resolver is a small callable (DI in main.py) that maps
    # the decoded callback to the enterprise_id. Phase 1.5 looks up via
    # workflow_runs(workflow_id, run_id) → enterprise_id; tests inject
    # a lambda returning a fixed UUID.
    enterprise_id: UUID = await ctx.enterprise_resolver(decoded)

    from_user = callback_query.get("from") or {}
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}

    inserted = await _insert_approval(
        ctx.pool,
        callback_query_id=callback_query_id,
        decoded=decoded,
        enterprise_id=enterprise_id,
        chat_id=chat.get("id"),
        user_id_external=from_user.get("id"),
        user_display_name=_display_name_for(from_user),
        raw_callback_data=raw_data,
        raw_payload=callback_query,
    )

    # Acknowledge so the manager's spinner clears immediately. Failures
    # are non-fatal — the decision is already recorded; the spinner
    # just persists for ~10s.
    try:
        await ctx.adapter.answer_callback_query(
            callback_query_id=callback_query_id,
            text="Đã ghi nhận lựa chọn ✅" if decoded.decision == "approve"
                 else "Đã từ chối ❌",
        )
    except BotSendError as exc:
        log.warning("telegram.webhook.ack_failed",
                    callback_query_id=callback_query_id,
                    error=str(exc))

    log.info(
        "telegram.webhook.decision_recorded",
        decision=decoded.decision,
        workflow_id=decoded.workflow_id,
        run_id=decoded.run_id,
        node_id=decoded.node_id,
        callback_query_id=callback_query_id,
        inserted=inserted,
    )
    return HandledApproval(
        inserted=inserted,
        callback_query_id=callback_query_id,
        decision=decoded.decision,
        workflow_id=decoded.workflow_id,
        run_id=decoded.run_id,
        node_id=decoded.node_id,
    )


def _display_name_for(from_user: dict[str, Any]) -> str:
    """Best-effort display name. Bot API supplies first_name + last_name +
    username; we concat what's there + fall back to '<unknown>' so the
    audit log never carries NULL where a hint would help an operator."""
    parts = [from_user.get("first_name") or "", from_user.get("last_name") or ""]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    if from_user.get("username"):
        return f"@{from_user['username']}"
    return "<unknown>"


async def _insert_approval(
    pool: Any,
    *,
    callback_query_id: str,
    decoded: ApprovalCallback,
    enterprise_id: UUID,
    chat_id: int | None,
    user_id_external: int | None,
    user_display_name: str,
    raw_callback_data: str,
    raw_payload: dict[str, Any],
) -> bool:
    """INSERT … ON CONFLICT DO NOTHING. Returns True if the row was
    inserted (first decision) or False if it was a duplicate retry.

    Both outcomes are success from the webhook's perspective — the
    boolean lets metrics distinguish first-time vs retry traffic without
    a separate counter.
    """
    import json
    # We cannot rely on RLS GUC here (the webhook runs without a tenant
    # session); migration policy uses WITH CHECK on enterprise_id, so we
    # set the GUC for the connection's lifetime.
    async with pool.acquire() as conn:
        await conn.execute(
            "SELECT set_config('app.current_enterprise_id', $1, true)",
            str(enterprise_id),
        )
        result = await conn.fetchrow(
            """
            INSERT INTO bot_approval_callbacks (
                workflow_id, run_id, node_id, decision,
                provider, callback_query_id, chat_id,
                user_id_external, user_display_name,
                enterprise_id, raw_callback_data, raw_payload
            ) VALUES (
                $1, $2, $3, $4, 'telegram', $5, $6, $7, $8, $9, $10, $11
            )
            ON CONFLICT (provider, callback_query_id) DO NOTHING
            RETURNING id
            """,
            decoded.workflow_id, decoded.run_id, decoded.node_id, decoded.decision,
            callback_query_id,
            str(chat_id) if chat_id is not None else None,
            str(user_id_external) if user_id_external is not None else None,
            user_display_name,
            enterprise_id,
            raw_callback_data,
            json.dumps(raw_payload),
        )
    return result is not None
