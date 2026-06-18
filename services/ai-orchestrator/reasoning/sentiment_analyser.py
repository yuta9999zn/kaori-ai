"""
Phase 2.5 — `sentiment_analysis` AI node.

Takes a list[Block] (or shorter free-text snippet via a single TEXT
block) and returns overall sentiment + optional per-aspect sentiment
breakdown.

Use cases (per WORKFLOW_USE_CASES.md):
- Support ticket triage — Negative + 'high' urgency → route to L2 queue.
- Product review feedback — score VOC pipeline aspect-by-aspect
  (delivery, quality, price, support).
- Sales call transcript → seller can flag deals with deteriorating
  customer tone before churn lands.
- Internal NPS comments → cluster Negative themes for the next sprint
  retro.

Design choices
--------------
1. **Overall + aspects** — caller passes optional `aspects=[...]`. If
   empty, em return overall only (fast path). If non-empty, em ask the
   LLM to score each aspect on the same 5-point scale.
2. **5-point scale** — VeryNegative / Negative / Neutral / Positive /
   VeryPositive. The numeric mapping (-1.0..1.0) is em's contract;
   prompt uses Vietnamese labels.
3. **Confidence per aspect** — LLM may be confident overall but
   uncertain on an aspect ("price not mentioned"). Em surface that
   via `confidence` on each aspect; caller filters.
4. **PII redaction reminder** — sentiment prompt may carry customer
   names / phones if caller didn't redact. Em DON'T redact inside this
   node — that's the caller's job before invoking (K-5). Em just log
   a warning if the prompt looks like raw PII slipped through.

K-rules
-------
K-3: LLM via llm_router. K-4: Qwen default; consent_external opt-in
     for English-heavy text where Claude/GPT does noticeably better.
K-17: side_effect_class = read_only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import structlog

from ..data_plane_shim import Block, BlockType
from ..engine.llm_router import llm_router

log = structlog.get_logger()


# 5-point sentiment scale. The string is what the prompt asks the LLM
# to emit; the float is what the caller may use for aggregation /
# trend dashboards.
SENTIMENT_SCALE: dict[str, float] = {
    "very_negative": -1.0,
    "negative":      -0.5,
    "neutral":        0.0,
    "positive":       0.5,
    "very_positive":  1.0,
}


# Cheap PII heuristic for the "did the caller forget to redact?" log
# warning. Not a real PII detector — just a smoke alarm. Real redaction
# is the caller's K-5 responsibility.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_VN_PHONE_RE = re.compile(r"\b0\d{9}\b")


@dataclass
class AspectRequest:
    """Optional aspect the caller wants scored separately."""
    name:        str    # snake_case key, vd "delivery_speed"
    description: str    # 1-line hint for the LLM


@dataclass
class SentimentInput:
    blocks:           list[Block]
    enterprise_id:    str
    consent_external: bool = False
    run_id:           Optional[str] = None
    # If empty, only overall sentiment returned.
    aspects:          Optional[list[AspectRequest]] = None
    # Confidence floor for accepting per-aspect scores. Below this the
    # caller sees the score but should treat it as "unknown".
    min_aspect_confidence: float = 0.5


@dataclass(frozen=True)
class AspectScore:
    name:       str
    label:      str       # one of SENTIMENT_SCALE keys, or "unknown"
    score:      float     # -1.0..1.0; 0.0 if label="unknown"
    confidence: float     # 0.0..1.0
    reasoning:  str       # short Vietnamese explanation


@dataclass(frozen=True)
class SentimentOutput:
    overall_label:      str            # one of SENTIMENT_SCALE keys
    overall_score:      float          # -1.0..1.0
    overall_confidence: float          # 0.0..1.0
    overall_reasoning:  str
    aspects:            list[AspectScore]


def _aspect_props_schema(aspects: list[AspectRequest]) -> dict[str, Any]:
    """Build a JSON Schema requiring an entry per requested aspect."""
    props: dict[str, Any] = {}
    for a in aspects:
        props[a.name] = {
            "type": "object",
            "required": ["label", "confidence", "reasoning"],
            "properties": {
                "label":      {"type": "string",
                                "enum": list(SENTIMENT_SCALE.keys()) + ["unknown"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning":  {"type": "string", "maxLength": 300},
            },
        }
    return props


def _output_schema(aspects: list[AspectRequest]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "object",
        "required": ["overall_label", "overall_confidence", "overall_reasoning"],
        "properties": {
            "overall_label":      {"type": "string",
                                    "enum": list(SENTIMENT_SCALE.keys())},
            "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "overall_reasoning":  {"type": "string", "maxLength": 500},
        },
    }
    if aspects:
        base["properties"]["aspects"] = {
            "type":       "object",
            "required":   [a.name for a in aspects],
            "properties": _aspect_props_schema(aspects),
        }
        base["required"].append("aspects")
    return base


def _collect_text(blocks: list[Block]) -> str:
    """Pull body text excluding chrome. Cap near 4 KB — sentiment
    rarely needs more than the first few paragraphs."""
    bits: list[str] = []
    total = 0
    for b in blocks:
        if b.type in (BlockType.HEADER, BlockType.FOOTER, BlockType.PAGE_NUMBER):
            continue
        chunk = b.text[:1500]
        if total + len(chunk) > 4000:
            break
        bits.append(chunk)
        total += len(chunk)
    return "\n".join(bits)


def _warn_if_pii(text: str, enterprise_id: str) -> None:
    """Log a warning (NOT a raise) if the caller forgot to redact.
    Real K-5 enforcement is at the caller's layer."""
    has_email = bool(_EMAIL_RE.search(text))
    has_phone = bool(_VN_PHONE_RE.search(text))
    if has_email or has_phone:
        log.warning("sentiment_analysis.pii_smoke_alarm",
                    has_email=has_email,
                    has_phone=has_phone,
                    enterprise_id=enterprise_id,
                    hint="Caller should redact before invoking (K-5).")


def _build_prompt(text: str, aspects: list[AspectRequest]) -> str:
    parts = [
        "Bạn phân tích cảm xúc văn bản tiếng Việt (review, ticket, NPS...).",
        "",
        "Trả về JSON gồm:",
        "  overall_label       — một trong: very_negative, negative, neutral, positive, very_positive",
        "  overall_confidence  — 0..1",
        "  overall_reasoning   — 1-2 câu giải thích",
    ]
    if aspects:
        parts.append("  aspects             — object có các khoá:")
        for a in aspects:
            parts.append(f"      {a.name} → {{label, confidence, reasoning}} — {a.description}")
        parts.append(
            "      Nếu khía cạnh không được nhắc trong văn bản, "
            "đặt label='unknown', confidence=0."
        )
    parts.extend([
        "",
        "Văn bản:",
        text,
        "",
        "Không thêm trường khác. Không thêm văn bản ngoài JSON.",
    ])
    return "\n".join(parts)


async def sentiment_analysis(inp: SentimentInput) -> SentimentOutput:
    """Score overall sentiment (+ optional per-aspect). Returns a
    SentimentOutput the caller can persist into a `voc_signals` table
    or feed into the support-ticket router."""
    aspects = inp.aspects or []
    text = _collect_text(inp.blocks)
    _warn_if_pii(text, inp.enterprise_id)

    prompt = _build_prompt(text, aspects)
    schema = _output_schema(aspects)

    try:
        result = await llm_router.complete_with_schema(
            prompt=prompt,
            task="sentiment_analysis",
            output_schema=schema,
            consent_external=inp.consent_external,
            enterprise_id=inp.enterprise_id,
            run_id=inp.run_id,
            max_tokens=600,
        )
    except AttributeError:
        text_out = await llm_router.complete(
            prompt=prompt,
            task="sentiment_analysis",
            consent_external=inp.consent_external,
            enterprise_id=inp.enterprise_id,
            run_id=inp.run_id,
            max_tokens=600,
        )
        from .document_classifier import _parse_json_fallback
        result = _parse_json_fallback(text_out)

    overall_label = str(result.get("overall_label", "neutral")).lower()
    if overall_label not in SENTIMENT_SCALE:
        log.warning("sentiment_analysis.invalid_overall_label",
                    label=overall_label, enterprise_id=inp.enterprise_id)
        overall_label = "neutral"
    overall_conf = float(result.get("overall_confidence", 0.0))
    overall_reason = str(result.get("overall_reasoning", ""))[:500]

    aspect_scores: list[AspectScore] = []
    aspects_raw = result.get("aspects", {}) or {}
    for a in aspects:
        entry = aspects_raw.get(a.name) or {}
        raw_label = str(entry.get("label", "unknown")).lower()
        if raw_label not in SENTIMENT_SCALE and raw_label != "unknown":
            raw_label = "unknown"
        conf = float(entry.get("confidence", 0.0))
        reasoning = str(entry.get("reasoning", ""))[:300]
        score = SENTIMENT_SCALE.get(raw_label, 0.0) if raw_label != "unknown" else 0.0
        aspect_scores.append(AspectScore(
            name=a.name,
            label=raw_label,
            score=score,
            confidence=conf,
            reasoning=reasoning,
        ))

    log.info("sentiment_analysis.done",
             overall_label=overall_label,
             overall_confidence=overall_conf,
             aspect_count=len(aspect_scores),
             enterprise_id=inp.enterprise_id)

    return SentimentOutput(
        overall_label=overall_label,
        overall_score=SENTIMENT_SCALE[overall_label],
        overall_confidence=overall_conf,
        overall_reasoning=overall_reason,
        aspects=aspect_scores,
    )
