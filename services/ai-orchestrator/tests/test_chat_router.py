"""
Sprint 8 — chat HTTP endpoint tests.

These run through FastAPI's TestClient against an in-memory app so
the SSE wire format is exercised end-to-end. The tool loop is
mocked at ``run_tool_loop`` because:
  * we already test the registry + tools individually
  * the loop calls the gateway over HTTP, which we don't want to
    spin up here (and Ollama isn't installed in CI)

Coverage:
  * SSE envelope shape (``data: <json>\\n\\n`` per event, type field)
  * X-Enterprise-ID required on /chat/enterprise/stream
  * Role gate on /chat/platform/stream — non-admin → 403
  * Body validation (empty message → 422)
"""
from __future__ import annotations

import json
from typing import AsyncIterator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.chat.router import router as chat_router
from ai_orchestrator.chat.schemas import SSEEvent
from ai_orchestrator.shared.errors import register_problem_handlers


@pytest.fixture
def app():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(chat_router, prefix="/chat")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _parse_sse(body: bytes) -> list[dict]:
    """Decode a finished SSE response body into a list of payload dicts."""
    events: list[dict] = []
    for chunk in body.decode("utf-8").split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


async def _three_event_loop(*, user_message, history, ctx) -> AsyncIterator[SSEEvent]:
    """Mock loop that fires the canonical thinking → message → done sequence."""
    yield SSEEvent(type="thinking")
    yield SSEEvent(type="message", text=f"echo: {user_message} (scope={ctx.scope})")
    yield SSEEvent(type="done")


async def _tool_then_message(*, user_message, history, ctx) -> AsyncIterator[SSEEvent]:
    """Mock loop that pretends one tool round happened."""
    yield SSEEvent(type="thinking")
    yield SSEEvent(type="tool_call", tool="get_billing_quota_status", args={})
    yield SSEEvent(type="tool_result", tool="get_billing_quota_status",
                   ok=True, preview='{"plan_code":"BUSINESS"}')
    yield SSEEvent(type="message", text="Bạn đang ở plan BUSINESS.")
    yield SSEEvent(type="done")


# =========================================================================
# /chat/enterprise/stream
# =========================================================================

def test_enterprise_stream_emits_thinking_message_done(client):
    with patch("ai_orchestrator.chat.router.run_tool_loop", _three_event_loop):
        resp = client.post(
            "/chat/enterprise/stream",
            headers={"X-Enterprise-ID": "11111111-1111-1111-1111-111111111111",
                     "X-User-ID":       "22222222-2222-2222-2222-222222222222",
                     "X-User-Role":     "MANAGER"},
            json={"message": "Hello"},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.content)
    types = [e["type"] for e in events]
    assert types == ["thinking", "message", "done"]
    assert "scope=enterprise" in events[1]["text"]


def test_enterprise_stream_renders_tool_call_and_result(client):
    """The ToolCallCard FE relies on tool_call + tool_result lines —
    make sure they survive the SSE serialiser intact."""
    with patch("ai_orchestrator.chat.router.run_tool_loop", _tool_then_message):
        resp = client.post(
            "/chat/enterprise/stream",
            headers={"X-Enterprise-ID": "11111111-1111-1111-1111-111111111111",
                     "X-User-Role":     "MANAGER"},
            json={"message": "Quota của tôi?"},
        )
    events = _parse_sse(resp.content)
    types = [e["type"] for e in events]
    assert types == ["thinking", "tool_call", "tool_result", "message", "done"]
    assert events[1]["tool"] == "get_billing_quota_status"
    assert events[2]["ok"] is True
    assert events[2]["preview"] == '{"plan_code":"BUSINESS"}'


def test_enterprise_stream_requires_X_Enterprise_ID_header(client):
    with patch("ai_orchestrator.chat.router.run_tool_loop", _three_event_loop):
        resp = client.post(
            "/chat/enterprise/stream",
            headers={"X-User-Role": "MANAGER"},
            json={"message": "Hello"},
        )
    assert resp.status_code == 422  # Header(...) missing


def test_enterprise_stream_rejects_empty_message(client):
    with patch("ai_orchestrator.chat.router.run_tool_loop", _three_event_loop):
        resp = client.post(
            "/chat/enterprise/stream",
            headers={"X-Enterprise-ID": "11111111-1111-1111-1111-111111111111",
                     "X-User-Role":     "MANAGER"},
            json={"message": ""},
        )
    assert resp.status_code == 422


# =========================================================================
# /chat/platform/stream
# =========================================================================

@pytest.mark.parametrize("role", ["SUPER_ADMIN", "ADMIN", "SUPPORT"])
def test_platform_stream_admin_roles_pass(client, role):
    with patch("ai_orchestrator.chat.router.run_tool_loop", _three_event_loop):
        resp = client.post(
            "/chat/platform/stream",
            headers={"X-User-Role": role,
                     "X-User-ID":   "u-1"},
            json={"message": "Hello"},
        )
    assert resp.status_code == 200
    events = _parse_sse(resp.content)
    assert "scope=platform" in events[1]["text"]


@pytest.mark.parametrize("role", ["MANAGER", "OPERATOR", "VIEWER", "ANALYST"])
def test_platform_stream_rejects_non_admin_roles(client, role):
    with patch("ai_orchestrator.chat.router.run_tool_loop", _three_event_loop):
        resp = client.post(
            "/chat/platform/stream",
            headers={"X-User-Role": role},
            json={"message": "Hello"},
        )
    assert resp.status_code == 403
    # K-14: error envelope must be RFC 7807
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_platform_stream_rejects_missing_role(client):
    with patch("ai_orchestrator.chat.router.run_tool_loop", _three_event_loop):
        resp = client.post(
            "/chat/platform/stream",
            json={"message": "Hello"},
        )
    assert resp.status_code == 403


# =========================================================================
# History pass-through
# =========================================================================

def test_history_is_forwarded_to_loop(client):
    captured: dict = {}

    async def _capturing_loop(*, user_message, history, ctx):
        captured["user_message"] = user_message
        captured["history"] = history
        captured["scope"] = ctx.scope
        yield SSEEvent(type="message", text="ok")
        yield SSEEvent(type="done")

    with patch("ai_orchestrator.chat.router.run_tool_loop", _capturing_loop):
        resp = client.post(
            "/chat/enterprise/stream",
            headers={"X-Enterprise-ID": "11111111-1111-1111-1111-111111111111",
                     "X-User-Role":     "MANAGER"},
            json={
                "message": "Câu mới",
                "history": [
                    {"role": "user",      "content": "Câu trước"},
                    {"role": "assistant", "content": "Trả lời trước"},
                ],
            },
        )
    assert resp.status_code == 200
    assert captured["user_message"] == "Câu mới"
    assert len(captured["history"]) == 2
    assert captured["history"][0]["role"] == "user"
    assert captured["scope"] == "enterprise"
