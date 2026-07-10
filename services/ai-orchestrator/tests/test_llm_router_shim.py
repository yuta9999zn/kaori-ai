"""
Tests for the post-cutover llm_router HTTP shim.

The shim's only job is to translate the legacy in-process
``llm_router.complete(prompt, task=..., enterprise_id=..., ...)``
call into a POST against the gateway and return the ``completion``
field. Behavior under failure (gateway down) and signature
preservation (so existing callers don't break) are the contract.

K-4 enforcement (F-016) is exercised in test_llm_router_consent.py;
this file's only intersection is the consent_external=True path which
now requires a DB-backed consent flag — see the helper below.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from ai_orchestrator.engine import llm_router as shim


@pytest.fixture(autouse=True)
def _clear_consent_cache():
    shim._invalidate_consent_cache()
    yield
    shim._invalidate_consent_cache()


def _consent_true_acquire():
    """Async-CM that yields a fake conn whose tenant_settings row says
    consent_external_ai=TRUE. Use when a test needs the K-4 check to
    pass through to the gateway forwarding path."""
    @asynccontextmanager
    async def fake(enterprise_id):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"consent_external_ai": True})
        yield conn
    return fake


@pytest.mark.asyncio
async def test_complete_posts_request_body_to_gateway_v1_infer():
    _req = httpx.Request("POST", "http://gw/v1/infer")
    fake_resp = httpx.Response(
        200,
        request=_req,
        json={
            "completion": "hello",
            "model_used": "qwen2.5:14b",
            "method": "internal",
            "cache_hit": False,
            "tokens": {"prompt_chars": 5, "completion_chars": 5},
            "latency_ms": 10,
        },
    )

    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["url"] = url
        captured["json"] = json
        return fake_resp

    eid = str(uuid4())
    with patch("httpx.AsyncClient.post", _fake_post):
        out = await shim.llm_router.complete(
            "the prompt",
            task="schema_mapping",
            enterprise_id=eid,
            run_id=str(uuid4()),
            max_tokens=500,
        )

    assert out == "hello"
    assert captured["url"].endswith("/v1/infer")
    assert captured["json"]["task"] == "schema_mapping"
    assert captured["json"]["prompt"] == "the prompt"
    assert captured["json"]["enterprise_id"] == eid
    assert captured["json"]["max_tokens"] == 500
    assert captured["json"]["consent_external"] is False  # default


@pytest.mark.asyncio
async def test_complete_substitutes_dev_enterprise_id_when_caller_passes_empty_string():
    """Background callers without a tenant context (rare) historically
    passed enterprise_id=''. The gateway requires a UUID; the shim
    substitutes the well-known dev id so the call still succeeds and
    audit rows surface as system-level entries."""
    _req = httpx.Request("POST", "http://gw/v1/infer")
    fake_resp = httpx.Response(
        200,
        request=_req,
        json={
            "completion": "x",
            "model_used": "qwen2.5:14b",
            "method": "internal",
            "cache_hit": False,
            "tokens": {"prompt_chars": 1, "completion_chars": 1},
            "latency_ms": 1,
        },
    )

    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["json"] = json
        return fake_resp

    with patch("httpx.AsyncClient.post", _fake_post):
        await shim.llm_router.complete("p", task="t")

    assert captured["json"]["enterprise_id"] == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_complete_passes_consent_external_true_when_caller_opts_in():
    _req = httpx.Request("POST", "http://gw/v1/infer")
    fake_resp = httpx.Response(
        200,
        request=_req,
        json={
            "completion": "ok",
            "model_used": "claude-sonnet-4-6",
            "method": "external",
            "cache_hit": False,
            "tokens": {"prompt_chars": 1, "completion_chars": 2},
            "latency_ms": 5,
        },
    )

    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["json"] = json
        return fake_resp

    # consent_external=True now triggers a tenant_settings lookup (K-4).
    # Stub it to TRUE so the call forwards instead of being refused.
    with patch.object(shim, "acquire_for_tenant", _consent_true_acquire()), \
         patch("httpx.AsyncClient.post", _fake_post):
        await shim.llm_router.complete(
            "p", task="t", enterprise_id=str(uuid4()), consent_external=True
        )

    assert captured["json"]["consent_external"] is True


@pytest.mark.asyncio
async def test_complete_raises_on_gateway_error():
    """The shim does not silently swallow gateway failures. K-3
    invariant: every LLM call goes through us; if the call fails the
    caller must hear about it (callers currently treat raised
    exceptions as soft-failures via try/except)."""
    async def _fake_post(self, url, json=None, **kw):
        raise httpx.ConnectError("connection refused")

    with patch("httpx.AsyncClient.post", _fake_post):
        with pytest.raises(httpx.HTTPError):
            await shim.llm_router.complete("p", task="t", enterprise_id=str(uuid4()))


@pytest.mark.asyncio
async def test_complete_returns_empty_string_when_response_lacks_completion_field():
    """Defensive: if the gateway response shape ever drifts, the shim
    falls back to '' instead of raising — existing callers handle
    empty completions by treating them as 'no answer.'"""
    fake_resp = httpx.Response(200, request=httpx.Request("POST", "http://gw/v1/infer"), json={"unexpected": "shape"})

    async def _fake_post(self, url, json=None, **kw):
        return fake_resp

    with patch("httpx.AsyncClient.post", _fake_post):
        out = await shim.llm_router.complete(
            "p", task="t", enterprise_id=str(uuid4())
        )
    assert out == ""


def test_OLLAMA_HOST_constant_still_exported_for_backward_compat():
    """Earlier code imported OLLAMA_HOST directly from this module
    (e.g. routers/health.py). Constant stays exported even though the
    shim doesn't itself talk to Ollama anymore."""
    assert hasattr(shim, "OLLAMA_HOST")
    assert isinstance(shim.OLLAMA_HOST, str)


# ---------------------------------------------------------------------------
# KAORI_LLM_RETRY_MAX_ATTEMPTS knob (incident 2026-07-10, run d3d2e493)
# ---------------------------------------------------------------------------
# The gateway hop inherits RETRY_MAX_ATTEMPTS=3 from the global retry
# wrapper; with LLM_TIMEOUT_S=480 on the pilot that is ~24 min of silent
# waiting per LLM node. The shim must forward an LLM-specific attempt
# budget (env KAORI_LLM_RETRY_MAX_ATTEMPTS, read per call) so ops can
# tighten LLM retries without touching other upstreams.


def _breaker_capture(captured: dict, payload: dict):
    async def _fake_breaker(name, work, *, max_attempts=None, **kw):
        captured["max_attempts"] = max_attempts
        return payload
    return _fake_breaker


@pytest.mark.asyncio
async def test_complete_forwards_llm_retry_attempts_from_env(monkeypatch):
    monkeypatch.setenv("KAORI_LLM_RETRY_MAX_ATTEMPTS", "1")
    captured: dict = {}
    with patch("ai_orchestrator.engine.llm_router.call_with_breaker",
               _breaker_capture(captured, {"completion": "ok"})):
        out = await shim.llm_router.complete(
            "p", task="t", enterprise_id=str(uuid4())
        )
    assert out == "ok"
    assert captured["max_attempts"] == 1


@pytest.mark.asyncio
async def test_complete_defaults_to_global_retry_when_env_unset(monkeypatch):
    monkeypatch.delenv("KAORI_LLM_RETRY_MAX_ATTEMPTS", raising=False)
    captured: dict = {}
    with patch("ai_orchestrator.engine.llm_router.call_with_breaker",
               _breaker_capture(captured, {"completion": "ok"})):
        await shim.llm_router.complete(
            "p", task="t", enterprise_id=str(uuid4())
        )
    assert captured["max_attempts"] is None


@pytest.mark.asyncio
async def test_complete_structured_forwards_llm_retry_attempts(monkeypatch):
    monkeypatch.setenv("KAORI_LLM_RETRY_MAX_ATTEMPTS", "2")
    captured: dict = {}
    payload = {"output_validation": {"parsed_json": {"entities": {}}}}
    with patch("ai_orchestrator.engine.llm_router.call_with_breaker",
               _breaker_capture(captured, payload)):
        out = await shim.llm_router.complete_structured(
            "p", task="t", output_schema={"type": "object"},
            enterprise_id=str(uuid4()),
        )
    assert out == {"entities": {}}
    assert captured["max_attempts"] == 2
