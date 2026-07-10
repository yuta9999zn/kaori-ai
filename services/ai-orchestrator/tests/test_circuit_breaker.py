"""Tests for shared/circuit_breaker.py — Phase 2 #7 (B3 PR #6)."""
from __future__ import annotations

import asyncio

import httpx
import pybreaker
import pytest

from ai_orchestrator.shared import circuit_breaker as cb


@pytest.fixture(autouse=True)
def reset_breakers():
    """Each test gets a fresh registry — pybreaker keeps state across
    test invocations otherwise."""
    cb._breakers.clear()
    yield
    cb._breakers.clear()


@pytest.mark.asyncio
async def test_call_with_breaker_returns_value_on_success():
    async def _ok():
        return "happy"

    result = await cb.call_with_breaker("test_breaker", _ok)
    assert result == "happy"
    # No failures → breaker stays closed.
    assert cb.get_breaker("test_breaker").current_state == pybreaker.STATE_CLOSED


@pytest.mark.asyncio
async def test_call_with_breaker_propagates_business_exception():
    """A non-transient exception (ValueError, etc.) propagates to the
    caller AND ticks the breaker counter — same as if the upstream
    cleanly returned a 4xx."""

    async def _boom():
        raise ValueError("not retryable")

    with pytest.raises(ValueError, match="not retryable"):
        await cb.call_with_breaker("test_breaker", _boom)
    breaker = cb.get_breaker("test_breaker")
    assert breaker.fail_counter == 1


@pytest.mark.asyncio
async def test_breaker_opens_after_fail_max_failures(monkeypatch):
    """N consecutive failures (where N == CB_FAIL_MAX) flip the
    breaker to OPEN; further calls short-circuit with
    CircuitBreakerError without invoking the work."""
    monkeypatch.setattr(cb, "CB_FAIL_MAX", 3)
    monkeypatch.setattr(cb, "RETRY_MAX_ATTEMPTS", 1)  # don't retry inside

    invocations = 0

    async def _always_fail():
        nonlocal invocations
        invocations += 1
        raise httpx.ConnectError("upstream down")

    # We need a fresh breaker that picks up the patched CB_FAIL_MAX.
    cb._breakers.clear()

    for _ in range(3):
        with pytest.raises(httpx.ConnectError):
            await cb.call_with_breaker("test_breaker", _always_fail)

    breaker = cb.get_breaker("test_breaker")
    assert breaker.current_state == pybreaker.STATE_OPEN

    # Next call should short-circuit with CircuitBreakerError —
    # _always_fail must NOT run again.
    invocations_before = invocations
    with pytest.raises(pybreaker.CircuitBreakerError):
        await cb.call_with_breaker("test_breaker", _always_fail)
    assert invocations == invocations_before


@pytest.mark.asyncio
async def test_retry_replays_on_transient_failure(monkeypatch):
    """tenacity retries httpx.ConnectError up to RETRY_MAX_ATTEMPTS
    inside one closed-state attempt before bubbling up."""
    monkeypatch.setattr(cb, "RETRY_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(cb, "RETRY_BACKOFF_S", 0.01)  # speed up the test

    attempts = 0

    async def _flaky():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("transient")
        return "recovered"

    result = await cb.call_with_breaker("test_breaker", _flaky)
    assert result == "recovered"
    assert attempts == 3
    # Breaker closed because the final attempt succeeded — counter
    # actually goes to 0 because pybreaker resets on success.
    assert cb.get_breaker("test_breaker").current_state == pybreaker.STATE_CLOSED


@pytest.mark.asyncio
async def test_get_breaker_returns_same_instance():
    """Named breakers are cached — repeated lookups return the SAME
    pybreaker instance so state isn't lost between calls."""
    a = cb.get_breaker("foo")
    b = cb.get_breaker("foo")
    assert a is b


@pytest.mark.asyncio
async def test_call_with_breaker_max_attempts_overrides_global(monkeypatch):
    """Per-call max_attempts overrides RETRY_MAX_ATTEMPTS. Incident
    2026-07-10: an LLM node on pilot CPU inherited 3 × LLM_TIMEOUT_S
    (≈ 24 min of silent waiting) from the global default — LLM callers
    need to fail fast without loosening retry for every other upstream."""
    monkeypatch.setattr(cb, "RETRY_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(cb, "RETRY_BACKOFF_S", 0.01)

    attempts = 0

    async def _always_timeout():
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("slow upstream")

    with pytest.raises(httpx.TimeoutException):
        await cb.call_with_breaker("test_breaker", _always_timeout, max_attempts=1)
    assert attempts == 1


@pytest.mark.asyncio
async def test_call_with_breaker_max_attempts_none_keeps_global(monkeypatch):
    """max_attempts=None (the default) preserves existing behavior."""
    monkeypatch.setattr(cb, "RETRY_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(cb, "RETRY_BACKOFF_S", 0.01)

    attempts = 0

    async def _always_timeout():
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("slow upstream")

    with pytest.raises(httpx.TimeoutException):
        await cb.call_with_breaker("test_breaker", _always_timeout, max_attempts=None)
    assert attempts == 2
