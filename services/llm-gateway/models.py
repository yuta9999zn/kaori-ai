"""
Wire schemas for POST /v1/infer.

Kept minimal on purpose — Phase 1 P-1 is the scaffolding; the real
routing logic, semantic cache, and per-tenant token budget come in
follow-up work. The shape is forward-compatible: adding ``cache_hit``,
``tokens``, etc. now means callers (ai-orchestrator's llm_router
shim, eventually) don't have to change when those features land.

Sprint 8 additions:
  - ``messages`` + ``tools`` + ``tool_choice`` on InferRequest, for
    the chat tool-calling path. Old single-prompt callers keep working
    untouched (``prompt`` stays the only required text field).
  - ``tool_calls`` on InferResponse, populated when the LLM decides
    to invoke a tool instead of answering directly.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One turn in a multi-message conversation. Mirrors the OpenAI /
    Anthropic chat format so providers can pass it through with minimal
    rewriting.
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    name: Optional[str] = Field(
        default=None,
        description="When role='tool', the tool name this message is "
                    "answering for. Required by OpenAI; ignored by "
                    "providers that don't need it.",
        max_length=100,
    )
    tool_call_id: Optional[str] = Field(
        default=None,
        description="Provider-issued id linking a tool result back to "
                    "the assistant turn that requested it.",
        max_length=200,
    )
    tool_calls: Optional[list[dict]] = Field(
        default=None,
        description="When role='assistant' and the model invoked tools, "
                    "the raw tool_calls list as the provider returned it. "
                    "Re-sent to the provider unchanged so the next turn "
                    "can match tool results to their requests.",
    )


class InferRequest(BaseModel):
    task: str = Field(
        ...,
        description="Logical task name — used to look up a routing rule "
                    "in llm_task_routing. Examples: 'schema_mapping', "
                    "'analysis_summary', 'cleaning_rule'.",
        min_length=1,
        max_length=100,
    )
    prompt: str = Field(
        default="",
        description="Single-shot prompt text. Either this OR ``messages`` "
                    "must be non-empty. Kept for back-compat with the "
                    "Phase-1 callers (analytics/runner, dashboard).",
    )
    messages: Optional[list[ChatMessage]] = Field(
        default=None,
        description="Multi-turn chat history. When set, takes priority "
                    "over ``prompt``. Used by the Sprint 8 chat tool "
                    "loop in ai-orchestrator/chat/.",
    )
    enterprise_id: UUID = Field(
        ...,
        description="Tenant id. Required for per-tenant token budget "
                    "enforcement (not yet wired) and audit trail.",
    )
    consent_external: bool = Field(
        default=False,
        description="K-4: external providers only run when the caller "
                    "explicitly opts in.",
    )
    max_tokens: int = Field(default=2000, ge=1, le=32000)
    run_id: Optional[UUID] = Field(
        default=None,
        description="Optional pipeline_runs id for cross-service tracing "
                    "and decision_audit_log linking.",
    )
    model_hint: Optional[str] = Field(
        default=None,
        description="Optional override for the model_id selected by "
                    "task routing — pass through to a specific model.",
        max_length=100,
    )
    pinned_model: Optional[str] = Field(
        default=None,
        description="K-20 (P1-LLM-004) — workflow-pinned model id, e.g. "
                    "'qwen2.5:14b' or 'claude-sonnet-4-6'. When set, the "
                    "router uses EXACTLY this model and ignores task "
                    "routing rules. Together with ``pinned_version`` this "
                    "is the workflow-as-code LLM stability contract: "
                    "vendor publishes a new version, but the workflow "
                    "stays on the previously-tested one until anh bumps "
                    "it explicitly. Audit row records both pinned values.",
        max_length=100,
    )
    pinned_version: Optional[str] = Field(
        default=None,
        description="K-20 (P1-LLM-004) — vendor-side version stamp tied "
                    "to ``pinned_model``. Free-form string (vendor "
                    "convention varies: ISO date '2026-01-01', semver "
                    "'4.6.2', commit-ish 'q4_K_M'). Required when "
                    "``pinned_model`` is set; either both or neither.",
        max_length=64,
    )
    tools: Optional[list[dict]] = Field(
        default=None,
        description="OpenAI-format tools array (each item is "
                    "{type:'function', function:{...}}). Forwarded to "
                    "providers that support native tool calling "
                    "(Ollama /api/chat for Qwen 2.5; Anthropic; OpenAI).",
    )
    tool_choice: Optional[str] = Field(
        default=None,
        description="'auto' (default) | 'none' | tool name. Same "
                    "semantics as OpenAI. None means provider default.",
        max_length=100,
    )
    output_schema: Optional[dict] = Field(
        default=None,
        description="Issue #3 — JSONSchema (Draft 2020-12) for the "
                    "expected response shape. When set, the gateway "
                    "extracts JSON from the completion, validates "
                    "against the schema, and on failure RE-PROMPTS the "
                    "model ONCE with an augmented prompt that includes "
                    "the schema + the validation error. If the second "
                    "attempt also fails, the gateway returns 502 with "
                    "code LLM.OUTPUT_VALIDATION_FAILED so the caller "
                    "decides whether to fall back or surface the error. "
                    "Callers without output_schema get the legacy raw-"
                    "string completion path unchanged.",
    )


class OutputValidation(BaseModel):
    """Metadata surfaced to the caller when the gateway validated the
    completion against ``output_schema``. Absent on the legacy raw-
    string path."""

    was_repaired: bool = Field(
        ...,
        description="True when the first attempt failed validation and "
                    "the second attempt succeeded. Useful for caller-"
                    "side metrics ('how often does Qwen need a repair "
                    "round on schema mapping?').",
    )
    attempts: int = Field(
        ...,
        ge=1,
        le=2,
        description="How many provider calls the gateway made. 1 = "
                    "first attempt validated; 2 = repair round used.",
    )
    parsed_json: dict = Field(
        ...,
        description="The validated JSON object. Returning the parsed "
                    "dict (not a string) saves the caller a json.loads "
                    "and guarantees the content matches the schema.",
    )


class TokenUsage(BaseModel):
    prompt_chars: int
    completion_chars: int


class AiDisclosure(BaseModel):
    """EU AI Act Art 50 (K-24) — machine-readable AI-generated disclosure
    attached to every completion at the gateway chokepoint (K-3)."""
    generated_by_ai: bool = True
    model:           str
    method:          str   # 'internal' (on-prem) | 'external' (vendor)
    notice_vi:       str
    notice_en:       str


_DISCLOSURE_NOTICE_VI = (
    "Nội dung này do AI tạo ra. Vui lòng kiểm chứng trước khi dùng cho "
    "quyết định quan trọng."
)
_DISCLOSURE_NOTICE_EN = (
    "This content was generated by AI. Please verify before relying on it "
    "for important decisions."
)


def build_disclosure(model_used: str, method: str) -> AiDisclosure:
    """Pure builder — total, never raises. Surfaces the concrete model +
    dispatch method so the consumer (FE badge, audit) can show provenance."""
    return AiDisclosure(
        generated_by_ai=True,
        model=model_used,
        method=method,
        notice_vi=_DISCLOSURE_NOTICE_VI,
        notice_en=_DISCLOSURE_NOTICE_EN,
    )


class InferResponse(BaseModel):
    completion: str
    model_used: str = Field(
        ...,
        description="Concrete model_id the request was dispatched to "
                    "(may differ from request when routing kicks in).",
    )
    method: str = Field(
        ...,
        description="'internal' (Ollama / on-prem) or 'external' "
                    "(third-party API). Mirrors llm_router.",
    )
    cache_hit: bool = Field(
        default=False,
        description="True when the response came from the semantic "
                    "cache. Always False until cache is wired.",
    )
    tokens: TokenUsage
    latency_ms: int
    tool_calls: Optional[list[dict]] = Field(
        default=None,
        description="When the model invoked tools instead of answering "
                    "directly, the parsed tool_calls list. Each entry: "
                    "{id?, name, arguments(dict)}. Empty/None means a "
                    "plain text answer in ``completion``.",
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="'stop' | 'tool_calls' | 'length' | 'error'. "
                    "Helps the chat agent decide whether to loop on "
                    "another tool round or surface the answer.",
        max_length=50,
    )
    output_validation: Optional[OutputValidation] = Field(
        default=None,
        description="Issue #3 — present iff the request supplied "
                    "``output_schema`` AND the gateway validated the "
                    "completion against it. ``parsed_json`` saves the "
                    "caller a json.loads; ``was_repaired`` + "
                    "``attempts`` are forensic signal for caller-side "
                    "metrics. Absent when no output_schema was set.",
    )
    disclosure: AiDisclosure = Field(
        ...,
        description="EU AI Act Art 50 / K-24 — machine-readable AI-generated "
                    "disclosure. Always present: every completion that leaves "
                    "the gateway self-declares as AI output.",
    )


# ─── P15-S11 — Embedding endpoint (pgvector real impl) ──────────────


class EmbedRequest(BaseModel):
    text: str = Field(
        ..., max_length=8000,
        description="Text to embed. Capped at 8000 chars — longer inputs "
                    "should be chunked by the caller. K-4 invariant: "
                    "embedding ALWAYS runs locally (Ollama BGE-M3); "
                    "consent_external has no effect here.",
    )
    enterprise_id: str = Field(
        ..., max_length=64,
        description="K-1 tenant context for the audit row. Required.",
    )


class EmbedResponse(BaseModel):
    vector:     list[float] = Field(
        ...,
        description="Embedding vector. BGE-M3 default dim = 1024. Empty "
                    "list when input text was empty.",
    )
    dim:        int    = Field(..., description="len(vector) — for caller sanity check.")
    model_used: str    = Field(..., description="Model id Ollama answered with.")
    latency_ms: int    = Field(..., description="Round-trip ms.")


# Phase 2.5 — OCR / vision (Qwen2.5-VL via Ollama, local-only K-4)
class OcrRequest(BaseModel):
    image_b64: str = Field(
        ..., min_length=4, max_length=15_000_000,
        description="Base64-encoded image (PNG / JPG / WebP). Max 15 MB "
                    "encoded ≈ 11 MB raw — fits one A4-resolution page "
                    "or a typical CCCD / receipt photo. Multi-page PDFs "
                    "must be rasterized + OCR'd page-by-page by the "
                    "caller (data-pipeline handles this for scanned PDFs).",
    )
    enterprise_id: str = Field(
        ..., max_length=64,
        description="K-1 tenant context for audit row. Required.",
    )
    prompt: str = Field(
        default="", max_length=2000,
        description="Override the default Vietnamese-first OCR prompt. "
                    "Leave empty for plain reading-order extraction; set "
                    "to a structured-extraction prompt for targeted "
                    "fields (e.g. 'Chỉ trích xuất mã số thuế').",
    )
    max_tokens: int = Field(
        default=2000, ge=100, le=8000,
        description="Output cap. Default 2000 fits ~3-4 KB of OCR text — "
                    "enough for a CCCD or receipt; bump for full A4 pages "
                    "of text (manuals, contracts).",
    )


class OcrResponse(BaseModel):
    text:       str    = Field(
        ...,
        description="OCR'd text in natural reading order. Empty string "
                    "when the input was empty / blank image.",
    )
    char_count: int    = Field(..., description="len(text) for sanity check.")
    model_used: str    = Field(..., description="Vision model that answered.")
    latency_ms: int    = Field(..., description="Round-trip ms.")
