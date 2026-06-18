"""
Sprint 8 — llm_router.chat() shim tests.

Verify the body shipped to the gateway carries the chat-specific
fields that didn't exist before this PR (``messages``, ``tools``,
``tool_choice``) and that K-4 is enforced on the chat path too — a
non-consenting tenant cannot reach an external chat model even if
the chat agent forgot to set ``consent_external=False``.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from ai_orchestrator.engine import llm_router as shim
from ai_orchestrator.engine.llm_router import ConsentDeniedError


def _ok_chat_response():
    return httpx.Response(
        200,
        request=httpx.Request("POST", "http://gw/v1/infer"),
        json={
            "completion":      "ok",
            "model_used":      "qwen2.5:14b",
            "method":          "internal",
            "cache_hit":       False,
            "tokens":          {"prompt_chars": 5, "completion_chars": 2},
            "latency_ms":      10,
            "tool_calls":      None,
            "finish_reason":   "stop",
        },
    )


@pytest.fixture(autouse=True)
def _clear_consent_cache():
    shim._invalidate_consent_cache()
    yield
    shim._invalidate_consent_cache()


@pytest.mark.asyncio
async def test_chat_forwards_messages_and_tools_to_gateway():
    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["json"] = json
        return _ok_chat_response()

    messages = [
        {"role": "system", "content": "you are kaori"},
        {"role": "user",   "content": "hi"},
    ]
    tools = [{
        "type": "function",
        "function": {
            "name": "get_billing_quota_status",
            "description": "test",
            "parameters": {"type": "object", "properties": {}},
        },
    }]

    with patch("httpx.AsyncClient.post", _fake_post):
        out = await shim.llm_router.chat(
            messages=messages,
            task="chat.enterprise",
            tools=tools,
            tool_choice="auto",
            enterprise_id=str(uuid4()),
        )

    assert out["completion"] == "ok"
    body = captured["json"]
    assert body["messages"] == messages
    assert body["tools"] == tools
    assert body["tool_choice"] == "auto"
    assert body["consent_external"] is False  # chat default Qwen local


@pytest.mark.asyncio
async def test_chat_external_without_tenant_consent_refuses():
    """Even on the chat path, K-4 still gates external calls."""
    @asynccontextmanager
    async def fake_acquire(enterprise_id):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"consent_external_ai": False})
        yield conn

    with patch.object(shim, "acquire_for_tenant", fake_acquire):
        with pytest.raises(ConsentDeniedError):
            await shim.llm_router.chat(
                messages=[{"role": "user", "content": "x"}],
                task="chat.enterprise",
                consent_external=True,
                enterprise_id=str(uuid4()),
            )


@pytest.mark.asyncio
async def test_chat_omits_tools_when_none():
    """When the caller has no tools, the body should not carry an
    empty list — keeps the gateway's logging cleaner."""
    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["json"] = json
        return _ok_chat_response()

    with patch("httpx.AsyncClient.post", _fake_post):
        await shim.llm_router.chat(
            messages=[{"role": "user", "content": "x"}],
            task="chat.enterprise",
            tools=None,
            enterprise_id=str(uuid4()),
        )

    assert "tools" not in captured["json"]
    assert "tool_choice" not in captured["json"]
