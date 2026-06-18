import os
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI, Header, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator

from bot import TelegramBotAdapter, TelegramBotConfig
from bot.webhook import (
    ApprovalCallback,
    WebhookContext,
    WebhookSecretMismatch,
    handle_telegram_update,
)
from config import get_settings
from db import close_db_pool, get_pool, init_db_pool
from errors import register_problem_handlers
from log_context import LogContextMiddleware
from models import SendRequest, SendResponse
from outbox_poller import OutboxPoller
from smtp_client import SmtpClient
from tracing import configure_structlog_with_trace, setup_tracing

# Phase 2 #2/#5 — structlog with trace_id/span_id enrichment.
configure_structlog_with_trace("kaori-notification-service")

log = structlog.get_logger()
_client: SmtpClient | None = None
_poller: OutboxPoller | None = None


def _telegram_bot_configured() -> bool:
    """True when KAORI_TELEGRAM_BOT_TOKEN is non-empty.

    Lifted out of TelegramBotAdapter so the lifespan can decide whether
    to init the DB pool without instantiating the adapter. Reads env
    directly to match TelegramBotConfig.from_env() exactly.
    """
    return bool(os.getenv("KAORI_TELEGRAM_BOT_TOKEN", "").strip())


def _bot_webhook_secret_configured() -> bool:
    """True when KAORI_TELEGRAM_WEBHOOK_SECRET is non-empty."""
    return bool(os.getenv("KAORI_TELEGRAM_WEBHOOK_SECRET", "").strip())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client, _poller
    settings = get_settings()
    _client = SmtpClient(settings)

    # Issue #6 outbox — start the poller after the SMTP client + DB
    # pool are ready. Gated by ``OUTBOX_POLL_ENABLED`` so a one-off
    # debug deploy can keep the legacy direct-HTTP endpoint alive
    # without burning DB connections on a poll loop nothing reads.
    #
    # P15-S9 D5 follow-up: the /webhook/telegram receiver also reads
    # the pool (records approval decisions). Init the pool whenever
    # either consumer is configured so a poll-disabled deploy with
    # Telegram still works. Only the *poller* spawn is gated.
    needs_pool = settings.outbox_poll_enabled or _telegram_bot_configured()
    if needs_pool:
        await init_db_pool(settings)

    if settings.outbox_poll_enabled:
        _poller = OutboxPoller(settings, _client)
        _poller.start()
    else:
        log.info("outbox.poller.disabled_by_config")

    # K-18 spirit — if Telegram is wired but the webhook secret is
    # empty, we ship effectively unauthenticated. Loud warning at boot
    # so an ops misconfig surfaces in startup logs instead of being
    # discovered only after a forged callback POST.
    if _telegram_bot_configured() and not _bot_webhook_secret_configured():
        log.warning(
            "telegram.webhook.secret_not_set",
            detail=(
                "KAORI_TELEGRAM_WEBHOOK_SECRET is empty — /webhook/telegram "
                "will accept ANY POST that reaches the endpoint. Set the "
                "secret + register it via setWebhook(secret_token=...)."
            ),
        )

    log.info("notification_service.started", smtp_host=settings.smtp_host)
    yield

    if _poller is not None:
        await _poller.stop()
        await close_db_pool()
    log.info("notification_service.stopped")


app = FastAPI(
    title="Kaori Notification Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Phase 2 #2/#5 — OpenTelemetry to Tempo. notification-service has no
# Kafka dep (HTTP only), so we skip the aiokafka instrumentor.
setup_tracing("kaori-notification-service", app, instrument_kafka=False)

# P1-S1 (OBS-012 / K-19) — bind gateway-trusted X-* headers into structlog
# scope so every log line carries tenant_id / user_id / role / session_id.
# notification-service receives internal HTTP from auth-service with X-*
# forwarded by gateway, so middleware applies same way.
app.add_middleware(LogContextMiddleware)

Instrumentator().instrument(app).expose(app)

# K-14: RFC 7807 error envelope on every error path.
register_problem_handlers(app)


@app.post("/internal/notifications/send", response_model=SendResponse, status_code=200)
async def send_notification(req: SendRequest):
    if _client is None:
        raise HTTPException(status_code=503, detail="SMTP client not ready")
    try:
        msg_id = await _client.send(req.to, req.template.value, req.context)
        return SendResponse(success=True, message_id=msg_id)
    except Exception as exc:
        log.error("notification.send.failed", to=req.to, template=req.template, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": f"Failed to send notification: {exc}"},
        )


# ---------------------------------------------------------------------------
# REL-011 — Telegram webhook receiver. Telegram POSTs callback_query
# updates here when a manager taps an approval button. We verify the
# pre-shared secret, persist the decision, and answer the callback so
# the spinner clears in the chat.
# ---------------------------------------------------------------------------


async def _resolve_enterprise_for_callback(decoded: ApprovalCallback) -> UUID:
    """Map a decoded callback to the enterprise_id the workflow belongs to.

    Phase 1.5 first wire — looks up workflow_runs by run_id. Real impl
    queries `pipeline_runs` via the Postgres pool (RLS scoped). For
    P15-S9 D5 first ship this is a placeholder that prefers an explicit
    KAORI_TELEGRAM_DEFAULT_ENTERPRISE_ID env override (set by ops for
    pilot Olist) and otherwise raises so a misconfigured deploy doesn't
    silently write decisions to a nil tenant.
    """
    override = os.getenv("KAORI_TELEGRAM_DEFAULT_ENTERPRISE_ID")
    if override:
        return UUID(override)
    raise HTTPException(
        status_code=503,
        detail={
            "type": "https://kaori.ai/errors/webhook-no-tenant-resolver",
            "title": "Approval webhook unable to resolve enterprise_id",
            "detail": (
                "Phase 1.5 P15-S9 D5 ships a stub resolver. Set "
                "KAORI_TELEGRAM_DEFAULT_ENTERPRISE_ID for pilot, or wire "
                "the workflow_runs lookup."
            ),
        },
    )


@app.post("/webhook/telegram", status_code=200)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Telegram callback_query receiver — REL-011 approval gate inbound.

    The route is intentionally thin: it parses the JSON body, hands off
    to ``handle_telegram_update``, and translates the handler's
    exceptions into RFC 7807 problem responses (K-14).
    """
    # Lazy adapter — built once, cached. Notification-service runs a
    # single bot identity so process-globals are fine.
    global _bot_adapter  # noqa: PLW0603
    try:
        _bot_adapter
    except NameError:
        _bot_adapter = TelegramBotAdapter()

    payload = await request.json()
    ctx = WebhookContext(
        pool=get_pool(),
        adapter=_bot_adapter,
        expected_secret=_bot_adapter.config.webhook_secret,
        enterprise_resolver=_resolve_enterprise_for_callback,
    )
    try:
        result = await handle_telegram_update(
            payload, x_telegram_bot_api_secret_token, ctx,
        )
    except WebhookSecretMismatch:
        raise HTTPException(status_code=401, detail="secret token mismatch")
    except ValueError as exc:
        # Decode failure or malformed payload — caller (Telegram) sees
        # 400 + a description so the bug surfaces in the bot logs.
        raise HTTPException(status_code=400, detail=str(exc))

    if result is None:
        return {"status": "ignored"}
    return {
        "status": "ok",
        "inserted": result.inserted,
        "decision": result.decision,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification-service"}
