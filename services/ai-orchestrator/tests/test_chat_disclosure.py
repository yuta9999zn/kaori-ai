"""
EU AI Act Art 50 (K-24) — chat self-identifies as AI.

The chat must emit a machine-readable ``disclosure`` SSE event at stream
start so the FE can render an "Đây là AI" badge before the answer arrives.

Harness mirrors the real ``run_tool_loop`` async generator (see
``chat/agent.py``): we drive the loop end-to-end with an empty
``ToolRegistry`` (no tools for the scope) and mock the single
llm-gateway round-trip (``llm_router.chat``) to return a plain-text
completion with ``finish_reason="stop"``. This lets the loop reach the
``message`` emit without spinning up Ollama / the gateway HTTP call.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.chat.agent import run_tool_loop
from ai_orchestrator.chat.registry import ToolRegistry
from ai_orchestrator.chat.tools.base import ToolContext


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER = "22222222-2222-2222-2222-222222222222"


def _ctx(scope: str = "enterprise") -> ToolContext:
    return ToolContext(
        enterprise_id=ENTERPRISE,
        user_id=USER,
        role="ANALYST",
        scope=scope,
    )


async def _collect_events(registry):
    # Mock the gateway: plain-text answer, no tool calls → loop emits
    # `message` then `done` on the first hop.
    fake_chat = AsyncMock(return_value={
        "completion": "Xin chào! Tôi có thể giúp gì cho anh?",
        "tool_calls": [],
        "finish_reason": "stop",
    })
    with patch(
        "ai_orchestrator.chat.agent.llm_router.chat", fake_chat
    ):
        return [
            e
            async for e in run_tool_loop(
                user_message="xin chào",
                history=[],
                ctx=_ctx(),
                registry=registry,
            )
        ]


@pytest.mark.asyncio
async def test_chat_emits_disclosure_event_at_stream_start():
    registry = ToolRegistry()  # empty → openai_tools_for_scope returns []
    events = await _collect_events(registry)

    disc = [e for e in events if e.type == "disclosure"]
    assert len(disc) == 1, f"expected exactly one disclosure event, got {[e.type for e in events]}"

    payload = disc[0].disclosure
    assert payload is not None
    assert payload["generated_by_ai"] is True
    assert payload.get("notice_vi")  # non-empty Vietnamese notice


@pytest.mark.asyncio
async def test_disclosure_comes_before_the_answer():
    registry = ToolRegistry()
    events = await _collect_events(registry)
    types = [e.type for e in events]

    assert "disclosure" in types
    assert "message" in types
    # Art 50: the user must be told it's an AI *before* the answer text.
    assert types.index("disclosure") < types.index("message")
