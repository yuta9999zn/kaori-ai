"""
Wire schemas for the chat endpoint and SSE event envelope.

The SSE stream emits one JSON event per ``data:`` line. Event types:

    {"type": "thinking"}
        Sent right after the request lands and before the first LLM call.
        FE uses it to show the typing indicator without waiting for the
        first token.

    {"type": "tool_call",   "tool": str, "args": dict}
        The agent decided to invoke a tool. FE renders a collapsible
        ToolCallCard so the user can audit what the assistant looked at.

    {"type": "tool_result", "tool": str, "ok": bool, "preview": str}
        The tool finished. ``preview`` is the first ~200 chars of the
        JSON-stringified result, used for the ToolCallCard summary.

    {"type": "message",     "text": str}
        Final assistant text. May arrive in chunks if streaming is
        wired in a follow-up — for v0 the gateway is non-streaming so
        this fires once at the end.

    {"type": "error",       "title": str, "detail": str}
        Terminal — user prompt rejected, tool budget exceeded, gateway
        5xx, etc. RFC 7807-shaped where possible.

    {"type": "done"}
        End-of-stream sentinel. FE can close the EventSource.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """A single user message. Stateless v0 — caller passes the visible
    history each turn so the BE doesn't need a `chat_messages` table.

    Conversation persistence is intentionally deferred to Phase 2
    (F-NEW4). The trade-off is documented in the Sprint 8 plan: cost
    of stateless = the FE has to keep a sessionStorage rolling buffer;
    benefit = no migration, no RLS surface, no PII retention question.
    """

    message: str = Field(..., min_length=1, max_length=4000)
    history: list["ChatTurn"] = Field(
        default_factory=list,
        description="Prior turns the FE wants the assistant to see. "
                    "Capped at 20 turns to keep prompt size bounded.",
        max_length=20,
    )


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


ChatRequest.model_rebuild()


class SSEEvent(BaseModel):
    """Discriminated-union shape for every line in the SSE response.

    Kept as a single open BaseModel rather than a Union[...] of typed
    variants because the FE is fine consuming a permissive shape, and
    the backward-compat story for the BE is easier when we add a new
    event type later.
    """

    type: Literal[
        "thinking",
        "tool_call",
        "tool_result",
        "message",
        "error",
        "done",
        "disclosure",
    ]
    tool: Optional[str] = None
    args: Optional[dict] = None
    ok: Optional[bool] = None
    preview: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    disclosure: Optional[dict] = None
