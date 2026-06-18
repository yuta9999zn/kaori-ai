"""
Provider dispatch — Ollama (internal) and Anthropic / OpenAI (external).

Ports the HTTP-call logic that previously lived in
``services/ai-orchestrator/engine/llm_router.py``. The gateway is now
the only place that talks to an LLM; ai-orchestrator's llm_router has
been reduced to an HTTP shim against this service.

Two dispatch modes:

  * ``invoke``    — single-prompt text completion. Phase-1 callers
                    (schema mapping, cleaning rules, analysis summary)
                    use this path and never need tools.
  * ``invoke_chat`` — multi-message chat with optional tool calling.
                    Sprint 8 chat agent uses this. Returns
                    ``(content, model_used, tool_calls, finish_reason)``.

Dispatch table (both modes):
  method='internal'  → Ollama (qwen2.5:14b by default)
  method='external'  → Anthropic if ANTHROPIC_API_KEY is set, else
                        OpenAI if OPENAI_API_KEY is set, else fall
                        back to Ollama with method='internal'.

Caller is responsible for K-5 PII redaction before invoking external
methods — see router.py.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

EXTERNAL_AI_ENABLED = os.getenv("EXTERNAL_AI_ENABLED", "false").lower() == "true"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# ===========================================================================
# Single-prompt completion (Phase 1 callers, unchanged)
# ===========================================================================

def _resolve_local_model(model_id: str) -> str:
    """Concrete Ollama model to call for a LOCAL (internal) request.

    The deployment's ``OLLAMA_MODEL`` env is the single source of truth for which
    model is actually pulled — the pilot runs ``qwen2.5:7b`` while the routing
    table logically names ``qwen2.5:14b``. Honouring the env here keeps the
    routing model-tag-agnostic and avoids a 404 (→ 502) when the routed tag isn't
    the one deployed. Falls back to the requested model_id when the env is unset
    (production parity / tests). No model name is hardcoded.
    """
    return os.getenv("OLLAMA_MODEL") or model_id


async def invoke(
    *,
    model_id: str,
    method: str,
    prompt: str,
    max_tokens: int,
) -> tuple[str, str]:
    """Dispatch to the appropriate backend.

    Returns ``(completion, model_used)`` — model_used can differ from
    the requested model_id when a fallback kicks in (e.g. external
    requested but no API key configured → falls back to Ollama).
    """
    if method == "external" and EXTERNAL_AI_ENABLED:
        if model_id.startswith("claude") and ANTHROPIC_API_KEY:
            return await _call_anthropic(model_id, prompt, max_tokens), model_id
        if model_id.startswith("gpt") and OPENAI_API_KEY:
            return await _call_openai(model_id, prompt, max_tokens), model_id
        # External requested but no usable key — quietly fall back to
        # local. Better to serve a reduced-quality answer than 500.
        log.warning(
            "llm_gateway.provider.external_fallback_to_internal",
            requested=model_id,
            anthropic_key_set=bool(ANTHROPIC_API_KEY),
            openai_key_set=bool(OPENAI_API_KEY),
        )
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        return await _call_ollama(ollama_model, prompt, max_tokens), ollama_model

    # Default path: internal Ollama. The deployment's OLLAMA_MODEL governs the
    # concrete model (pilot 7b vs routing's logical 14b) — see _resolve_local_model.
    concrete = _resolve_local_model(model_id)
    return await _call_ollama(concrete, prompt, max_tokens), concrete


async def _call_ollama(model: str, prompt: str, max_tokens: int) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.1},
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


async def _call_anthropic(model: str, prompt: str, max_tokens: int) -> str:
    """Caller must have already redacted PII (K-5)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


async def _call_openai(model: str, prompt: str, max_tokens: int) -> str:
    """Caller must have already redacted PII (K-5)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ===========================================================================
# Multi-message chat with tool calling (Sprint 8 chat agent)
# ===========================================================================
#
# Three return values for every call:
#   content        — assistant text. Empty string when finish_reason='tool_calls'.
#   model_used     — see invoke().
#   tool_calls     — list of {id?, name, arguments} when the model invoked
#                    tools, else None.
#   finish_reason  — 'stop' | 'tool_calls' | 'length'. Used by the agent loop
#                    to decide whether to recurse on another tool round.

async def invoke_chat(
    *,
    model_id: str,
    method: str,
    messages: list[dict],
    tools: list[dict] | None,
    tool_choice: str | None,
    max_tokens: int,
) -> tuple[str, str, list[dict] | None, str]:
    if method == "external" and EXTERNAL_AI_ENABLED:
        if model_id.startswith("claude") and ANTHROPIC_API_KEY:
            return await _chat_anthropic(model_id, messages, tools, max_tokens)
        if model_id.startswith("gpt") and OPENAI_API_KEY:
            return await _chat_openai(model_id, messages, tools, tool_choice, max_tokens)
        log.warning(
            "llm_gateway.chat.external_fallback_to_internal",
            requested=model_id,
        )
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        return await _chat_ollama(ollama_model, messages, tools, max_tokens)

    return await _chat_ollama(_resolve_local_model(model_id), messages, tools, max_tokens)


async def _chat_ollama(
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    max_tokens: int,
) -> tuple[str, str, list[dict] | None, str]:
    """Ollama /api/chat endpoint. Qwen 2.5 supports native tool calling
    here when ``tools`` is non-empty. Returns the unified shape so
    callers don't need to know which provider answered.
    """
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.1},
    }
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=body)
        resp.raise_for_status()
        data = resp.json()

    msg = data.get("message", {}) or {}
    content = msg.get("content", "") or ""
    raw_calls = msg.get("tool_calls") or []

    # Ollama returns ``[{function: {name, arguments}}]``. Normalise to
    # ``[{id, name, arguments}]`` — id is a stable hash so the tool
    # result can reference the request even though Ollama doesn't
    # mint one. (OpenAI/Anthropic do; we keep the same shape.)
    tool_calls = None
    if raw_calls:
        tool_calls = []
        for i, c in enumerate(raw_calls):
            fn = c.get("function") or {}
            tool_calls.append({
                "id":        c.get("id") or f"ollama_{i}",
                "name":      fn.get("name", ""),
                "arguments": fn.get("arguments") or {},
            })

    finish_reason = "tool_calls" if tool_calls else "stop"
    return content, model, tool_calls, finish_reason


async def _chat_anthropic(
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    max_tokens: int,
) -> tuple[str, str, list[dict] | None, str]:
    """Caller must have already redacted PII (K-5)."""
    # Anthropic system prompt is a top-level field, not a message role.
    system_parts = [m["content"] for m in messages
                    if m.get("role") == "system" and m.get("content")]
    chat_msgs = [
        {"role": m["role"], "content": m.get("content") or ""}
        for m in messages if m.get("role") in {"user", "assistant"}
    ]
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": chat_msgs,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    if tools:
        # OpenAI tool shape ⇒ Anthropic tool shape: pull the inner
        # ``function`` dict and rename ``parameters`` → ``input_schema``.
        body["tools"] = [
            {
                "name":         t["function"]["name"],
                "description":  t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {}),
            }
            for t in tools
        ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    blocks = data.get("content", []) or []
    text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

    tool_calls = None
    if tool_blocks:
        tool_calls = [
            {
                "id":        b.get("id", ""),
                "name":      b.get("name", ""),
                "arguments": b.get("input") or {},
            }
            for b in tool_blocks
        ]

    finish_reason = data.get("stop_reason") or ("tool_calls" if tool_calls else "stop")
    if finish_reason == "tool_use":
        finish_reason = "tool_calls"
    return "".join(text_parts), model, tool_calls, finish_reason


async def _chat_openai(
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    tool_choice: str | None,
    max_tokens: int,
) -> tuple[str, str, list[dict] | None, str]:
    """Caller must have already redacted PII (K-5)."""
    import json as _json

    body: dict[str, Any] = {
        "model":      model,
        "messages":   messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message", {}) or {}
    content = msg.get("content") or ""
    raw_calls = msg.get("tool_calls") or []

    tool_calls = None
    if raw_calls:
        tool_calls = []
        for c in raw_calls:
            fn = c.get("function") or {}
            args = fn.get("arguments") or {}
            # OpenAI returns arguments as a JSON string — decode so the
            # downstream agent doesn't have to know which provider answered.
            if isinstance(args, str):
                try:
                    args = _json.loads(args)
                except _json.JSONDecodeError:
                    args = {}
            tool_calls.append({
                "id":        c.get("id", ""),
                "name":      fn.get("name", ""),
                "arguments": args,
            })

    finish_reason = choice.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
    return content, model, tool_calls, finish_reason


# ===========================================================================
# Embeddings — P15-S11 (pgvector real impl, Phase 1.5)
# ===========================================================================
#
# Single provider — Ollama (BGE-M3 by default per ADR-0015 + CLAUDE.md K-4).
# Embeddings are ALWAYS local; consent_external is not even an input here
# because document text NEVER leaves the tenant for embedding work. If a
# tenant needs a managed vector service Phase 2+, that lands as a sibling
# adapter (e.g. Pinecone) but NOT as an external API for embedding the
# raw document text.

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")


# ===========================================================================
# OCR / vision (Phase 2.5 — Qwen2.5-VL via Ollama, local-only per K-4)
# ===========================================================================
#
# OCR_MODEL must be a vision-capable Ollama model. Qwen2.5-VL 7B is the
# default — small enough to coexist with qwen2.5:14b on a 16 GB box;
# good Vietnamese receipt + form OCR per the model card. Alternative:
# llama3.2-vision:11b for English-heavy workloads.
#
# K-4 INVARIANT — em do NOT expose a consent_external path for OCR in
# Phase 2.5. Image bytes routinely carry PII (CCCD, hợp đồng scan,
# receipts) that PII redaction can't strip at the byte level — sending
# to Anthropic/OpenAI Vision would be a privacy escape hatch K-4 was
# designed to prevent. Vendor vision adapters are explicitly Phase 3
# (separate ADR required).

OCR_MODEL = os.getenv("OCR_MODEL", "qwen2.5vl:7b")

DEFAULT_OCR_PROMPT = (
    "Trích xuất TOÀN BỘ văn bản trong ảnh, giữ thứ tự đọc tự nhiên "
    "(trái-phải, trên-dưới). Bảng giữ định dạng cột tách nhau bằng "
    "dấu '|'. Số tiền giữ định dạng gốc (1.000.000 hoặc 1,000,000). "
    "Không thêm bình luận, không giải thích — chỉ văn bản trích xuất."
)


async def ocr_image(
    *,
    image_b64: str,
    prompt: str = "",
    max_tokens: int = 2000,
) -> str:
    """Run OCR on a base64-encoded image via the local vision model.

    K-4 invariant: ALWAYS local (no consent_external opt-in path).
    Image bytes never leave the Kaori boundary; vendor vision providers
    are Phase 3 + require a separate ADR before any wire-in.

    Returns the extracted text, in natural reading order per the
    default Vietnamese-first prompt. Caller can override `prompt` for
    structured extraction (e.g. "Trích xuất chỉ mã số thuế từ hóa đơn").
    """
    if not image_b64:
        return ""
    payload = {
        "model": OCR_MODEL,
        "prompt": prompt or DEFAULT_OCR_PROMPT,
        "stream": False,
        "images": [image_b64],
        "options": {"num_predict": max_tokens, "temperature": 0.0},
    }
    # OCR is heavier than chat completion — give it a longer timeout
    # (180s) for a large multi-page invoice scan.
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")


async def embed_text(text: str) -> list[float]:
    """Return the embedding vector for `text` from the local BGE-M3 model.

    BGE-M3 dimension = 1024 by default (varies if a different model is
    set via EMBEDDING_MODEL env var). Caller can assert dimension on the
    first vector + cache the expected dim for sanity checks.
    """
    if not text:
        # An empty string would 400 from Ollama; short-circuit with the
        # zero vector so the caller's "no content" handling stays uniform.
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        payload = resp.json()
    vec = payload.get("embedding") or []
    if not isinstance(vec, list):
        raise RuntimeError(
            f"Ollama /api/embeddings returned non-list embedding: {type(vec).__name__}"
        )
    return [float(x) for x in vec]
