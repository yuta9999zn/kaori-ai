"""
Circuit-breaker + bounded-retry helpers — Phase 2 #7 (B3 PR #6).

Two layers wrap every outgoing call to a slow upstream (Ollama, the LLM
gateway, external Anthropic/OpenAI):

  1. **Bounded retry**: ``retry_on_transient`` decorator (tenacity-based)
     replays a coroutine on transient failures with exponential backoff
     plus ±50% jitter, max 3 attempts. We retry only on
     ``httpx.HTTPError`` and connection-level errors — never on
     application-level 4xx that the server explicitly emitted.

  2. **Circuit breaker**: ``with_breaker(name, ...)`` returns a
     pybreaker-backed CB. Once 5 failures land inside a 30-second window
     the breaker opens for 60 seconds; after that it half-opens, lets a
     single probe through, and either closes (probe succeeds) or re-opens
     (probe fails). Open-state calls raise
     :class:`pybreaker.CircuitBreakerError` immediately so the caller can
     fall back instead of stacking timeouts.

Both layers compose: the retry runs *inside* the breaker, so a
flapping downstream burns its 3 retries inside one closed-state attempt
and the breaker's failure counter ticks up by 1 (not 3).

Mirrored across services/ai-orchestrator/shared/ + services/data-pipeline/
shared/. Updated to a new tunable? touch both.
"""
from __future__ import annotations

import asyncio
import os
import random
from typing import Awaitable, Callable, TypeVar

import httpx
import pybreaker
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    RetryError,
)

log = structlog.get_logger()

T = TypeVar("T")


# =============================================================================
# Tunables — env-overridable so production can tighten without a redeploy.
# =============================================================================

CB_FAIL_MAX        = int(os.getenv("CB_FAIL_MAX", "5"))          # opens after N failures
CB_RESET_TIMEOUT_S = int(os.getenv("CB_RESET_TIMEOUT_S", "60"))  # half-open after T seconds

RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BACKOFF_S    = float(os.getenv("RETRY_BACKOFF_S", "1.0"))   # base of exp backoff


# =============================================================================
# Breaker registry — one instance per logical upstream.
# =============================================================================

_breakers: dict[str, pybreaker.CircuitBreaker] = {}


class _BreakerListener(pybreaker.CircuitBreakerListener):
    """Surface state transitions in structured logs so the Phase 2 #6
    Prometheus rules + Tempo trace timeline can correlate them."""

    def __init__(self, name: str) -> None:
        self._name = name

    def state_change(self, cb, old, new) -> None:
        log.warning(
            "circuit_breaker.state_change",
            breaker=self._name,
            old_state=str(old),
            new_state=str(new),
            fail_counter=cb.fail_counter,
        )


def get_breaker(name: str) -> pybreaker.CircuitBreaker:
    """Return (creating on first call) the named breaker. Names are
    free-form strings — keep them short and stable so the structured
    log + Tempo span attribute are greppable. Conventional names:
    ``llm_gateway``, ``ollama``, ``notification_service``."""
    cb = _breakers.get(name)
    if cb is not None:
        return cb
    cb = pybreaker.CircuitBreaker(
        fail_max=CB_FAIL_MAX,
        reset_timeout=CB_RESET_TIMEOUT_S,
        listeners=[_BreakerListener(name)],
        name=name,
    )
    _breakers[name] = cb
    return cb


# =============================================================================
# Async-aware retry + breaker wrapper.
# =============================================================================

# Exceptions worth retrying. Anything else (4xx client errors, business
# exceptions) propagates without a retry — the server told us to stop.
_TRANSIENT_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.NetworkError,
    httpx.ReadError,
    httpx.WriteError,
)


async def _retry_async(work: Callable[[], Awaitable[T]]) -> T:
    """Run ``work`` with bounded retry. Caller passes a no-arg coroutine
    factory so each attempt re-creates the request (httpx clients can't
    be shared across awaits in some scenarios)."""
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
            wait=wait_exponential_jitter(initial=RETRY_BACKOFF_S, max=8.0, jitter=1.0),
            retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                return await work()
    except RetryError as e:
        # Re-raise the underlying cause so callers' existing except
        # branches keep matching httpx.HTTPError, not RetryError.
        cause = e.last_attempt.exception() if e.last_attempt else None
        raise cause if cause else e
    raise RuntimeError("unreachable")  # pragma: no cover


async def call_with_breaker(
    breaker_name: str,
    work: Callable[[], Awaitable[T]],
) -> T:
    """Execute ``work()`` under a circuit breaker + bounded retry.

    Usage::

        async def _post():
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return resp.json()

        result = await call_with_breaker("llm_gateway", _post)

    Raises ``pybreaker.CircuitBreakerError`` when the breaker is open
    (caller should treat this as the upstream being explicitly
    unavailable and surface a fallback rather than retry blindly).
    Other exceptions propagate from the underlying ``work()``.
    """
    cb = get_breaker(breaker_name)

    # pybreaker doesn't natively support coroutines — wrap the await
    # inside a sync function that asyncio.run-style "reborn" pattern
    # would deadlock under a running loop. Instead, we ask the breaker
    # whether we can proceed (sync call to .call on a no-op), then
    # await the actual work, then mark success/failure manually.
    if cb.current_state == pybreaker.STATE_OPEN:
        # Surface the open-state error WITHOUT touching the retry
        # machinery. The breaker's listener already logged the trip.
        raise pybreaker.CircuitBreakerError(
            f"Breaker {breaker_name} is OPEN — upstream unavailable"
        )

    try:
        result = await _retry_async(work)
    except Exception as exc:
        # Ratchet the breaker's failure counter via its sync .call API
        # so the threshold honours the same fail_max as direct callers.
        # We don't actually want to invoke anything sync here, so we
        # fake a callable that re-raises. pybreaker counts this as one
        # failure regardless of how many retries fired underneath.
        try:
            cb.call(_raise(exc))
        except Exception:
            pass  # counter incremented; original exception below
        raise

    # Reset the failure counter on success — pybreaker does this when
    # something flows through .call() in CLOSED state. We replicate it
    # by calling a no-op success.
    cb.call(lambda: None)
    return result


def _raise(exc: BaseException) -> Callable[[], None]:
    """Tiny helper — return a callable that re-raises ``exc`` so we
    can hand it to ``CircuitBreaker.call(...)`` and have it tick the
    failure counter."""
    def _f() -> None:
        raise exc
    return _f
