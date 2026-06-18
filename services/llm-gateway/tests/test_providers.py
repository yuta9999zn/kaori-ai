"""
Tests for provider dispatch (services/llm-gateway/providers.py).

Two responsibilities checked here:

  1. **External-fallback** — when ``method='external'`` is requested
     but the env is misconfigured (EXTERNAL_AI_ENABLED off, or no API
     key set for the requested provider), the provider quietly
     downgrades to local Ollama and returns the substituted model id.
     This is the "fail open with reduced quality" contract documented
     at the top of providers.py.

  2. **tool_call normalisation** — Ollama, Anthropic, and OpenAI each
     surface tool calls in slightly different shapes. ``invoke_chat``
     is the only place callers see them, so the unified
     ``[{id, name, arguments(dict)}]`` shape must hold across all
     three providers.

httpx.AsyncClient is patched per-test so nothing real is ever sent.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_gateway import providers


def _httpx_response(payload: dict, status: int = 200):
    """Build a fake httpx.Response.json() returning ``payload``.

    Wrapping in MagicMock is enough — providers.py calls
    ``resp.raise_for_status()`` then ``resp.json()`` and never inspects
    the underlying request object.
    """
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=payload)
    return resp


def _patch_httpx_post(handler):
    """Patch httpx.AsyncClient so the body of every POST goes through
    ``handler(url, json) -> response_payload_dict``. Returns the
    AsyncMock for assertions."""
    captured = []

    async def _post(self, url, json=None, headers=None, **kw):
        captured.append({"url": url, "json": json, "headers": headers})
        payload = handler(url, json)
        return _httpx_response(payload)

    return patch("httpx.AsyncClient.post", _post), captured


# ─── invoke (single-prompt) — external fallback paths ────────────────

@pytest.mark.asyncio
async def test_invoke_external_with_disabled_flag_routes_through_ollama_with_original_model_id(monkeypatch):
    """EXTERNAL_AI_ENABLED=False is the production-default safety
    switch. method='external' MUST NOT reach the public internet — it
    routes to local Ollama. Quirk: this branch keeps the original
    ``model_id`` (e.g. 'claude-sonnet-4-6') in ``model_used`` rather
    than substituting OLLAMA_MODEL, which is what the no-API-key
    branch does. Two different fallback shapes for two different
    misconfigurations — pin the current behaviour so a future cleanup
    is an intentional diff. See follow-up note in providers.py."""
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", False)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "anthropic-key")  # set but ignored

    def handler(url, body):
        # Whatever model_id was passed gets sent to Ollama as-is.
        assert "11434" in url
        return {"response": "from local model"}

    patcher, captured = _patch_httpx_post(handler)
    with patcher:
        completion, model_used = await providers.invoke(
            model_id="claude-sonnet-4-6",
            method="external",
            prompt="hello",
            max_tokens=100,
        )

    assert completion == "from local model"
    # Original model_id flows through — NOT substituted to qwen2.5:14b.
    assert model_used == "claude-sonnet-4-6"
    # And we hit the Ollama URL, not Anthropic's.
    assert "anthropic.com" not in captured[0]["url"]


@pytest.mark.asyncio
async def test_invoke_external_with_no_api_key_falls_back_to_ollama(monkeypatch):
    """EXTERNAL_AI_ENABLED=True but no Anthropic/OpenAI key configured →
    same fallback behaviour."""
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(providers, "OPENAI_API_KEY", "")

    patcher, captured = _patch_httpx_post(lambda url, body: {"response": "from local"})
    with patcher:
        completion, model_used = await providers.invoke(
            model_id="claude-sonnet-4-6",
            method="external",
            prompt="hello",
            max_tokens=100,
        )

    assert "anthropic" not in captured[0]["url"]
    assert "openai" not in captured[0]["url"]
    assert model_used.startswith("qwen")


@pytest.mark.asyncio
async def test_invoke_external_claude_with_key_calls_anthropic(monkeypatch):
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "ant-key")

    def handler(url, body):
        assert "anthropic.com" in url
        return {"content": [{"type": "text", "text": "claude says hi"}]}

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        completion, model_used = await providers.invoke(
            model_id="claude-sonnet-4-6",
            method="external",
            prompt="hello",
            max_tokens=100,
        )

    assert completion == "claude says hi"
    assert model_used == "claude-sonnet-4-6"  # not substituted


@pytest.mark.asyncio
async def test_invoke_external_gpt_with_key_calls_openai(monkeypatch):
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(providers, "OPENAI_API_KEY", "oai-key")

    def handler(url, body):
        assert "openai.com" in url
        return {"choices": [{"message": {"content": "gpt says hi"}}]}

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        completion, model_used = await providers.invoke(
            model_id="gpt-4o",
            method="external",
            prompt="hello",
            max_tokens=100,
        )

    assert completion == "gpt says hi"
    assert model_used == "gpt-4o"


@pytest.mark.asyncio
async def test_invoke_internal_calls_ollama_passthrough():
    def handler(url, body):
        assert "11434" in url
        assert body["model"] == "qwen2.5:7b"
        return {"response": "ok"}

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        completion, model_used = await providers.invoke(
            model_id="qwen2.5:7b",
            method="internal",
            prompt="hello",
            max_tokens=100,
        )

    assert completion == "ok"
    assert model_used == "qwen2.5:7b"


# ─── invoke_chat — tool_call normalisation ───────────────────────────

@pytest.mark.asyncio
async def test_chat_ollama_normalises_tool_calls_to_unified_shape():
    """Ollama returns ``[{function: {name, arguments}}]`` and no id.
    The gateway must surface ``[{id, name, arguments}]`` so the chat
    agent doesn't need to know which provider answered."""
    def handler(url, body):
        return {
            "message": {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "list_pipeline_runs",
                                  "arguments": {"limit": 5}}},
                ],
            }
        }

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        content, model, tool_calls, finish = await providers.invoke_chat(
            model_id="qwen2.5:7b",
            method="internal",
            messages=[{"role": "user", "content": "list runs"}],
            tools=[{"type": "function", "function": {"name": "list_pipeline_runs"}}],
            tool_choice=None,
            max_tokens=2000,
        )

    assert content == ""
    assert finish == "tool_calls"
    assert tool_calls is not None and len(tool_calls) == 1
    call = tool_calls[0]
    assert call["name"] == "list_pipeline_runs"
    assert call["arguments"] == {"limit": 5}
    assert call["id"].startswith("ollama_")  # synthesised stable id


@pytest.mark.asyncio
async def test_chat_ollama_no_tool_calls_returns_stop():
    def handler(url, body):
        return {"message": {"content": "plain answer", "tool_calls": []}}

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        content, _, tool_calls, finish = await providers.invoke_chat(
            model_id="qwen2.5:7b",
            method="internal",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            tool_choice=None,
            max_tokens=100,
        )

    assert content == "plain answer"
    assert tool_calls is None
    assert finish == "stop"


@pytest.mark.asyncio
async def test_chat_openai_decodes_json_string_arguments(monkeypatch):
    """OpenAI returns tool args as a JSON-encoded string. The unified
    shape must surface them as a Python dict so callers don't have to
    branch on provider."""
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(providers, "OPENAI_API_KEY", "oai-key")

    def handler(url, body):
        return {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_abc",
                        "function": {
                            "name": "get_decisions",
                            "arguments": json.dumps({"limit": 3}),
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }]
        }

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        _, _, tool_calls, finish = await providers.invoke_chat(
            model_id="gpt-4o",
            method="external",
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "get_decisions"}}],
            tool_choice="auto",
            max_tokens=200,
        )

    assert finish == "tool_calls"
    assert tool_calls[0]["id"] == "call_abc"
    assert tool_calls[0]["arguments"] == {"limit": 3}  # decoded, not a string


@pytest.mark.asyncio
async def test_chat_openai_malformed_json_arguments_fall_back_to_empty_dict(monkeypatch):
    """A malformed JSON arg string would crash downstream tool dispatch
    if it propagated as a string. providers.py guards with try/except —
    pin that behaviour."""
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(providers, "OPENAI_API_KEY", "oai-key")

    def handler(url, body):
        return {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_bad",
                        "function": {"name": "x", "arguments": "{not-json"},
                    }],
                },
                "finish_reason": "tool_calls",
            }]
        }

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        _, _, tool_calls, _ = await providers.invoke_chat(
            model_id="gpt-4o", method="external",
            messages=[{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "x"}}],
            tool_choice="auto", max_tokens=200,
        )

    assert tool_calls[0]["arguments"] == {}


@pytest.mark.asyncio
async def test_chat_anthropic_remaps_stop_reason_tool_use_to_tool_calls(monkeypatch):
    """Anthropic uses ``stop_reason='tool_use'``; the gateway maps it
    to ``finish_reason='tool_calls'`` so the chat agent's loop reads
    the same flag for every provider."""
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "ant-key")

    def handler(url, body):
        return {
            "content": [{
                "type": "tool_use",
                "id": "toolu_1",
                "name": "list_pipeline_runs",
                "input": {"limit": 5},
            }],
            "stop_reason": "tool_use",
        }

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        _, _, tool_calls, finish = await providers.invoke_chat(
            model_id="claude-sonnet-4-6",
            method="external",
            messages=[{"role": "user", "content": "list runs"}],
            tools=[{"type": "function",
                    "function": {"name": "list_pipeline_runs",
                                 "parameters": {"type": "object"}}}],
            tool_choice="auto",
            max_tokens=2000,
        )

    assert finish == "tool_calls"  # remapped from 'tool_use'
    assert tool_calls[0]["id"] == "toolu_1"
    assert tool_calls[0]["name"] == "list_pipeline_runs"
    assert tool_calls[0]["arguments"] == {"limit": 5}


@pytest.mark.asyncio
async def test_chat_anthropic_text_only_response_returns_stop(monkeypatch):
    monkeypatch.setattr(providers, "EXTERNAL_AI_ENABLED", True)
    monkeypatch.setattr(providers, "ANTHROPIC_API_KEY", "ant-key")

    def handler(url, body):
        return {
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
        }

    patcher, _ = _patch_httpx_post(handler)
    with patcher:
        content, _, tool_calls, finish = await providers.invoke_chat(
            model_id="claude-sonnet-4-6",
            method="external",
            messages=[{"role": "user", "content": "hi"}],
            tools=None, tool_choice=None, max_tokens=200,
        )

    assert content == "Hello!"
    assert tool_calls is None
    assert finish == "end_turn"
