"""
Tool-calling loop. One ``run_tool_loop`` invocation handles a single
user turn end-to-end and yields SSE events the router serialises into
``data:`` lines.

Loop:
    1. Build messages = [system, ...history, user]
    2. POST gateway with tools=registry.openai_tools_for_scope(scope)
    3. If finish_reason='tool_calls' → dispatch each call via the
       registry, append tool result messages, recurse (max 3 hops).
       Else → emit ``message`` event with the assistant text and stop.

Hard caps:
    * MAX_HOPS = 3 — the agent may invoke at most three rounds of
      tools per turn. After that we stop and surface whatever text
      the model produced (or a generic fallback if it produced none).
    * MAX_TOOL_CALLS_PER_HOP = 4 — guards against a model that asks
      for the same tool 20× in a single hop. After truncation we feed
      the dropped calls back as a tool error so the model knows.

The agent is the ONLY place that constructs the OpenAI-style message
list. Tools never see the raw conversation; the registry strips
forbidden args before dispatch.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import structlog

import os

from ..engine.llm_router import llm_router
from .registry import ToolRegistry, ToolDispatchError, get_default_registry
from .schemas import SSEEvent
from .tool_necessity import (
    HIGH_CONFIDENCE,
    ToolCall,
    args_fingerprint,
    assess_tool_call_loop,
    log_loop_guardrail,
    log_necessity_decision,
    needs_tool_heuristic,
)
from .tools.base import ToolContext

log = structlog.get_logger()

MAX_HOPS = 3
MAX_TOOL_CALLS_PER_HOP = 4

# System prompts: scope-specific so the model knows which mental model
# to use. Kept short — long system prompts blow Qwen's context budget.
_ENTERPRISE_SYSTEM = (
    "Bạn là Kaori — trợ lý AI cho doanh nghiệp đang dùng nền tảng Kaori. "
    "Trả lời ngắn gọn bằng tiếng Việt. Khi cần dữ liệu cụ thể (quyết "
    "định gần đây, khách hàng rủi ro, hạn mức), gọi tool tương ứng "
    "thay vì đoán. Tool nào không có thì nói rõ là chưa hỗ trợ. "
    "Tuyệt đối không tự bịa số liệu."
)

_PLATFORM_SYSTEM = (
    "Bạn là Kaori Ops — trợ lý nội bộ cho admin platform Kaori. "
    "Người dùng là nhân viên Kaori (SUPER_ADMIN/ADMIN/SUPPORT) đang "
    "vận hành đa-tenant. Trả lời ngắn gọn bằng tiếng Việt. Gọi tool "
    "khi cần số liệu thật. Mọi tool call sẽ được audit — chỉ gọi khi "
    "thật sự cần."
)


async def run_tool_loop(
    *,
    user_message: str,
    history: list[dict],
    ctx: ToolContext,
    registry: ToolRegistry | None = None,
) -> AsyncIterator[SSEEvent]:
    """Drive one chat turn. Yields SSE events in order.

    The caller (``chat/router.py``) is responsible for serialising the
    yielded events to ``data: <json>\\n\\n`` lines and closing the
    stream after the final ``done`` event.
    """
    reg = registry or get_default_registry()

    yield SSEEvent(type="thinking")

    # K-24 EU AI Act Art 50 — the user must know they're talking to an AI.
    yield SSEEvent(
        type="disclosure",
        disclosure={
            "generated_by_ai": True,
            "notice_vi": "Bạn đang trò chuyện với trợ lý AI của Kaori (không phải người).",
            "notice_en": "You are chatting with Kaori's AI assistant (not a human).",
        },
    )

    system_prompt = (
        _PLATFORM_SYSTEM if ctx.scope == "platform" else _ENTERPRISE_SYSTEM
    )
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for turn in history:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    tools = reg.openai_tools_for_scope(ctx.scope)

    # Knowing-doing gap mitigation (ADR-0023, paper arXiv 2605.14038).
    # Heuristic on hop 0 only: if user message strongly indicates a
    # tool is needed, force tool_choice="required" so the LLM cannot
    # silently drop the tool call. Subsequent hops use 'auto' so the
    # model can choose to stop the loop with a plain-text answer.
    assessment = needs_tool_heuristic(user_message, scope=ctx.scope)
    log_necessity_decision(
        user_message=user_message,
        assessment=assessment,
        tenant_id=ctx.enterprise_id,
    )
    forced_tool_choice = (
        "required" if assessment.confidence >= HIGH_CONFIDENCE else "auto"
    )

    # Loop guardrail history — accumulates across hops within this turn.
    # See `tool_necessity.assess_tool_call_loop` (DPEPO depth/width pattern).
    tool_call_history: list[ToolCall] = []

    final_text = ""
    for hop in range(MAX_HOPS):
        # Only force on hop 0; subsequent hops should be free to answer.
        tool_choice_for_hop = forced_tool_choice if hop == 0 else "auto"
        try:
            payload = await llm_router.chat(
                messages=messages,
                task=f"chat.{ctx.scope}",
                tools=tools,
                tool_choice=tool_choice_for_hop,
                # K-4: chat default Qwen local. Plan §10 Q4 chốt cứng.
                consent_external=False,
                enterprise_id=ctx.enterprise_id or "",
                max_tokens=1500,
            )
        except Exception as exc:
            log.exception("chat.gateway_failed", error=str(exc))
            yield SSEEvent(
                type="error",
                title="LLM Gateway lỗi",
                detail="Không gọi được model. Vui lòng thử lại.",
            )
            yield SSEEvent(type="done")
            return

        completion = (payload.get("completion") or "").strip()
        tool_calls = payload.get("tool_calls") or []
        finish_reason = payload.get("finish_reason") or "stop"

        if finish_reason != "tool_calls" or not tool_calls:
            final_text = completion
            break

        # Truncate runaway tool-call lists. Models occasionally ask for
        # the same tool 10× in one hop; cap so a runaway turn can't
        # explode the audit log or the gateway round-trip count.
        truncated_extras: list[dict] = []
        if len(tool_calls) > MAX_TOOL_CALLS_PER_HOP:
            truncated_extras = tool_calls[MAX_TOOL_CALLS_PER_HOP:]
            tool_calls = tool_calls[:MAX_TOOL_CALLS_PER_HOP]

        # Append the assistant's tool-call turn back into the message
        # list so the provider can match tool results to their request
        # ids on the next hop.
        messages.append({
            "role": "assistant",
            "content": completion,  # may be empty when finish='tool_calls'
            "tool_calls": tool_calls,
        })

        for call in tool_calls:
            tool_name = call.get("name") or ""
            tool_args = call.get("arguments") or {}
            tool_id = call.get("id") or ""

            yield SSEEvent(type="tool_call", tool=tool_name, args=tool_args)

            # Loop guardrail: refuse dispatch if depth/width penalty trips.
            # Surface a structured tool-error back to the model so it can
            # change strategy on the next hop instead of looping.
            loop_assessment = assess_tool_call_loop(
                tool_name=tool_name,
                args=tool_args if isinstance(tool_args, dict) else {},
                history=tool_call_history,
            )
            log_loop_guardrail(
                tool_name=tool_name,
                assessment=loop_assessment,
                tenant_id=ctx.enterprise_id,
                hop=hop,
            )
            if loop_assessment.should_abort:
                yield SSEEvent(
                    type="tool_result",
                    tool=tool_name,
                    ok=False,
                    preview=(
                        f"[guardrail] {tool_name} đã được gọi lặp quá nhiều. "
                        "Đổi cách tiếp cận hoặc trả lời từ context đã có."
                    ),
                )
                messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": json.dumps(
                        {
                            "ok": False,
                            "error": "loop_guardrail_tripped",
                            "depth_count": loop_assessment.depth_count,
                            "width_count": loop_assessment.width_count,
                            "reason": loop_assessment.reason,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                })
                continue

            try:
                ok, result = await reg.dispatch(
                    name=tool_name,
                    args=tool_args,
                    ctx=ctx,
                )
            except ToolDispatchError as exc:
                ok, result = False, str(exc)

            tool_call_history.append(ToolCall(
                tool_name=tool_name,
                args_fingerprint=args_fingerprint(
                    tool_args if isinstance(tool_args, dict) else {},
                ),
                hop=hop,
            ))

            preview = _make_preview(result)
            yield SSEEvent(
                type="tool_result",
                tool=tool_name,
                ok=ok,
                preview=preview,
            )

            messages.append({
                "role": "tool",
                "name": tool_name,
                "tool_call_id": tool_id,
                "content": json.dumps(
                    {"ok": ok, "result": result},
                    ensure_ascii=False,
                    default=str,
                ),
            })

        # Tell the model about anything we dropped so it doesn't
        # silently miss data it asked for.
        for dropped in truncated_extras:
            messages.append({
                "role": "tool",
                "name": dropped.get("name") or "",
                "tool_call_id": dropped.get("id") or "",
                "content": json.dumps({
                    "ok": False,
                    "error": (
                        f"Đã bỏ qua: vượt quá giới hạn {MAX_TOOL_CALLS_PER_HOP} "
                        "tool calls / lượt."
                    ),
                }, ensure_ascii=False),
            })
    else:
        # Loop fell through MAX_HOPS without a plain-text answer. Emit
        # a friendly note rather than nothing — surprising-but-correct
        # behaviour beats an empty bubble.
        final_text = (
            "Đã chạy đến giới hạn vòng lặp tool. Kết quả tool có ở "
            "trên — bạn có thể hỏi thêm cụ thể hơn để mình tóm tắt."
        )

    if not final_text:
        final_text = "Mình chưa có câu trả lời dứt khoát cho câu hỏi này."

    yield SSEEvent(type="message", text=final_text)

    # ─── End-of-turn fact extraction (mem0 port — ADR-0024) ──────────
    # Opportunistic write to SEMANTIC L4 memory. Fire-and-forget per
    # turn; failures swallowed to never affect chat hot path.
    # Gated by CHAT_FACT_EXTRACTION_ENABLED env (default false) — em
    # ship the wiring but keep disabled until anh opts in per tenant.
    if _fact_extraction_enabled() and ctx.enterprise_id:
        try:
            await _seed_facts_from_turn(
                user_message=user_message,
                assistant_response=final_text,
                ctx=ctx,
            )
        except Exception:  # noqa: BLE001 — never crash chat over memory
            log.exception("chat.fact_extraction.failed",
                          tenant_id=ctx.enterprise_id)

    yield SSEEvent(type="done")


def _fact_extraction_enabled() -> bool:
    return os.getenv("CHAT_FACT_EXTRACTION_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


async def _seed_facts_from_turn(
    *,
    user_message: str,
    assistant_response: str,
    ctx: ToolContext,
) -> None:
    """Extract 0-5 facts from the user-assistant exchange and persist
    each as MemoryType.SEMANTIC record in L4 (ADR-0024 follow-up wire).

    Uses TCubeTransformer.extract_and_store_facts with the LLM gateway
    client. Stub-friendly: caller can override LLM via env stub if needed.
    """
    from uuid import UUID

    from ..reasoning.memory.service import MemoryService
    from ..reasoning.trace_distiller.runner import _build_llm_client
    from ..reasoning.trace_distiller.transformer import TCubeTransformer

    # Build combined turn text — caller-side context separates user from
    # assistant. Per-turn budget caps at ~4K chars to stay within
    # extract_facts truncation guard.
    combined = (
        f"USER: {user_message[:1500]}\n\n"
        f"ASSISTANT: {assistant_response[:2500]}"
    )
    # ToolContext doesn't carry session_id today; tag with user_id +
    # scope so retrieve() can still differentiate per-user threads.
    context = f"chat turn (scope={ctx.scope}, user={ctx.user_id or '-'})"

    transformer = TCubeTransformer(_build_llm_client())
    memsvc = MemoryService()  # InMemory default per Phase 1.5
    tenant_uuid = UUID(ctx.enterprise_id) if ctx.enterprise_id else None
    if tenant_uuid is None:
        return
    await transformer.extract_and_store_facts(
        combined,
        tenant_id=tenant_uuid,
        memory_service=memsvc,
        context=context,
        source_ref=f"chat:user:{ctx.user_id or 'adhoc'}",
    )


def _make_preview(value, limit: int = 200) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"
