"""
LogContextMiddleware — bind gateway-trusted X-* headers into
structlog contextvars so every log line in a request scope carries
``tenant_id`` / ``user_id`` / ``role`` / ``session_id`` /
``request_id``.

P1-S1 (OBS-012 / K-19) — Loki labels these fields for per-tenant log
search; Jaeger spans carry tenant_id as attribute via OTel
auto-instrumentation. The two are independent — Loki only sees what
this middleware binds, OTel only sees what FastAPIInstrumentor reads
from the request.

How it interacts with structlog:
  * On request start, ``bind_contextvars(**ctx)`` writes keys into a
    ``contextvars.ContextVar``-backed dict scoped to the asyncio task.
  * The structlog pipeline's ``merge_contextvars`` processor (registered
    by :func:`shared.tracing.configure_structlog_with_trace`) reads that
    dict and merges keys into every event_dict.
  * On response (or exception), ``unbind_contextvars`` deletes the keys
    so the next request on the same worker doesn't inherit stale
    tenant_id (K-12 spirit — never leak tenant identity across
    requests).

Only the gateway-trusted headers are read. The Spring Cloud Gateway
JwtAuthFilter strips client-supplied ``X-*`` headers and re-injects
them from JWT claims, so by the time a request reaches a Python
service, ``X-Enterprise-ID`` is authoritative (K-7). Reading them
here is safe; reading from the request body or query string would
not be (K-12).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Header → contextvar key mapping. Headers are lower-cased by ASGI
# before reaching the middleware, so match in lower form.
_HEADER_BINDINGS: tuple[tuple[str, str], ...] = (
    ("x-enterprise-id", "tenant_id"),  # K-7 forwarded; K-1 RLS source
    ("x-user-id", "user_id"),
    ("x-user-role", "role"),
    ("x-session-id", "session_id"),    # Phase 3 admin session tracking
    ("x-request-id", "request_id"),    # RFC trace correlation; falls back to OTel trace_id
)


class LogContextMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware — bind tenant identity into structlog scope.

    Mount via ``app.add_middleware(LogContextMiddleware)`` in main.py.
    Order matters: register AFTER FastAPIInstrumentor so OTel spans are
    already created when this middleware runs (so trace_id is available
    when the first log line fires).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        bindings: dict[str, Any] = {}
        for header_name, ctx_key in _HEADER_BINDINGS:
            value = request.headers.get(header_name)
            if value:
                bindings[ctx_key] = value

        # bind_contextvars returns the previous values for restoration;
        # we don't need them — unbind by key on the way out.
        if bindings:
            structlog.contextvars.bind_contextvars(**bindings)
        try:
            return await call_next(request)
        finally:
            if bindings:
                structlog.contextvars.unbind_contextvars(*bindings.keys())


def bind_log_context(**kwargs: Any) -> None:
    """Bind arbitrary keys into the current structlog scope.

    Used by background workers (Kafka consumers, outbox pollers) where
    there's no HTTP request to drive the middleware. Caller is
    responsible for matching ``unbind_log_context`` in a finally block.

    Example::

        from ai_orchestrator.shared.log_context import bind_log_context, unbind_log_context

        async def handle_message(msg):
            bind_log_context(
                tenant_id=msg.tenant_id,
                workflow_id=msg.workflow_id,
            )
            try:
                ... # log lines now carry tenant_id + workflow_id
            finally:
                unbind_log_context("tenant_id", "workflow_id")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_log_context(*keys: str) -> None:
    """Pair with :func:`bind_log_context`. Pass keys to unbind."""
    if keys:
        structlog.contextvars.unbind_contextvars(*keys)


def clear_log_context() -> None:
    """Wipe all contextvars from current scope. Use sparingly — prefer
    targeted unbind. Useful for worker loops that want a clean slate
    between message handlings (defence-in-depth against forgotten
    unbinds).
    """
    structlog.contextvars.clear_contextvars()
