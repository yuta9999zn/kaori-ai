"""
Phase 2.5 — `classify_document` AI node.

Takes a list[Block] from Stage 6 docsage_extract output and classifies
the whole document into one of a caller-supplied category set (or a
default business taxonomy).

Use cases (per WORKFLOW_USE_CASES.md pattern matrix — 8 use cases hit
this node): contract type detection, invoice vs receipt vs PO,
support ticket priority, contract category routing, legal letter
urgency, regulation impact triage, CV department match.

Design choices
--------------
1. **Pure compute + ONE LLM call** — no DB writes, no Kafka. Caller
   persists the result. K-17 side_effect_class = read_only.
2. **Categories are caller-supplied** — defaults provided but tenant
   workflow templates pass their own (e.g. mig 069 template's
   `expected_categories: ["nda", "service_contract", "employment", ...]`).
3. **Confidence + reasoning fields** — caller can gate on confidence
   threshold (default 0.7 per ADR-0023 knowing-doing-gap heuristic
   threshold). Reasoning surfaces in audit log so anh can debug
   misclassifications.
4. **JSON output strictly schema'd** — output_schema enforced by
   llm-gateway. One repair round; second fail raises.

K-rules
-------
K-3: LLM dispatch via llm_router → llm-gateway (no direct SDK).
K-4: consent_external=False by default — Qwen local. Caller can opt
     in but business doc classification rarely needs Claude/GPT.
K-20: model_version pinned via llm_router task='classify_document'
     (Phase 2.5 follow-up: add pinning config).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import structlog

from ..data_plane_shim import Block, BlockType
from ..engine.llm_router import llm_router
# NOTE: ai-orchestrator doesn't import directly from data-pipeline at
# runtime — em define a thin shim re-exporting Block/BlockType under
# ai-orchestrator's namespace so the two services compile + ship
# independently. The shim file lives one level up.

log = structlog.get_logger()


# Default category set when caller doesn't supply one. Covers ~80% of
# Vietnamese business docs per the 20-case analysis.
DEFAULT_CATEGORIES = [
    "contract",        # hợp đồng (NDA / service / employment / lease)
    "invoice",         # hóa đơn
    "receipt",         # biên lai
    "purchase_order",  # đơn đặt hàng
    "bank_statement",  # sao kê ngân hàng
    "report",          # báo cáo (doanh thu / tài chính / nhân sự)
    "regulation",      # thông tư / nghị định
    "legal_letter",    # văn bản pháp lý
    "resume",          # CV / sơ yếu lý lịch
    "form",            # đơn từ / biểu mẫu
    "policy",          # chính sách / quy trình
    "other",           # fallback
]


@dataclass
class ClassifyInput:
    blocks:        list[Block]
    enterprise_id: str
    candidates:    list[str] = None        # type: ignore[assignment]
    consent_external: bool = False
    run_id:        Optional[str] = None
    # Confidence threshold; below this caller should reject + ask for
    # human classification. Default 0.7 from ADR-0023.
    min_confidence: float = 0.7

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = list(DEFAULT_CATEGORIES)


@dataclass(frozen=True)
class ClassifyOutput:
    category:           str       # one of the candidates, or "uncertain"
    confidence:         float     # 0.0 .. 1.0
    reasoning:          str       # 1-2 sentence explanation
    meets_threshold:    bool      # confidence >= input.min_confidence
    candidates_evaluated: list[str]


_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["category", "confidence", "reasoning"],
    "properties": {
        "category":   {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning":  {"type": "string", "maxLength": 500},
    },
}


def _build_prompt(blocks: list[Block], candidates: list[str]) -> str:
    """Compose the classification prompt. Includes only first ~3 KB of
    text + every TITLE block (lead signal) — keeps token usage bounded
    on long documents without losing the dominant clue."""
    titles = [b.text for b in blocks if b.type == BlockType.TITLE]
    body_chars = 0
    body_bits: list[str] = []
    for b in blocks:
        if b.type in (BlockType.HEADER, BlockType.FOOTER, BlockType.PAGE_NUMBER):
            continue
        snippet = b.text[:500]
        if body_chars + len(snippet) > 3000:
            break
        body_bits.append(snippet)
        body_chars += len(snippet)

    parts = [
        "Bạn là phân loại tài liệu kinh doanh Việt Nam.",
        "Hãy chọn MỘT category phù hợp nhất từ danh sách:",
        "  " + ", ".join(candidates),
        "",
        "Tài liệu:",
    ]
    if titles:
        parts.append("Tiêu đề: " + " / ".join(titles[:3]))
    parts.append("\n".join(body_bits))
    parts.extend([
        "",
        "Trả về JSON đúng schema sau:",
        "  category    — đúng 1 chuỗi từ danh sách trên",
        "  confidence  — số từ 0 đến 1; bằng 1 nếu chắc chắn, 0.5 nếu ngờ",
        "  reasoning   — 1-2 câu giải thích bằng tiếng Việt",
        "Không thêm trường khác. Không thêm văn bản ngoài JSON.",
    ])
    return "\n".join(parts)


async def classify_document(inp: ClassifyInput) -> ClassifyOutput:
    """Classify the document into one of `inp.candidates`. Returns
    ClassifyOutput with meets_threshold flag the caller uses to decide
    whether to act on the classification or fall back to human review.

    Raises:
      - ConsentDeniedError if external requested but tenant didn't opt in
      - llm_router-level errors (network, repair-twice-fail)
    """
    prompt = _build_prompt(inp.blocks, inp.candidates)
    try:
        result = await llm_router.complete_with_schema(
            prompt=prompt,
            task="classify_document",
            output_schema=_OUTPUT_SCHEMA,
            consent_external=inp.consent_external,
            enterprise_id=inp.enterprise_id,
            run_id=inp.run_id,
            max_tokens=300,
        )
    except AttributeError:
        # Backwards compat: older llm_router doesn't have schema variant
        text = await llm_router.complete(
            prompt=prompt,
            task="classify_document",
            consent_external=inp.consent_external,
            enterprise_id=inp.enterprise_id,
            run_id=inp.run_id,
            max_tokens=300,
        )
        result = _parse_json_fallback(text)

    cat = str(result.get("category", "")).strip().lower()
    confidence = float(result.get("confidence", 0.0))
    reasoning = str(result.get("reasoning", ""))[:500]

    # Coerce out-of-vocabulary categories to "uncertain" so callers
    # always know to retry / escalate.
    candidates_lower = {c.lower() for c in inp.candidates}
    if cat not in candidates_lower:
        log.warning("classify_document.oov_category",
                    requested_category=cat,
                    valid_candidates=inp.candidates)
        cat = "uncertain"
        confidence = 0.0

    meets = confidence >= inp.min_confidence and cat != "uncertain"

    log.info("classify_document.done",
             category=cat,
             confidence=confidence,
             meets_threshold=meets,
             enterprise_id=inp.enterprise_id)

    return ClassifyOutput(
        category=cat,
        confidence=confidence,
        reasoning=reasoning,
        meets_threshold=meets,
        candidates_evaluated=list(inp.candidates),
    )


def _parse_json_fallback(text: str) -> dict:
    """Best-effort JSON extraction from free-text completion. Used only
    when llm_router doesn't expose a schema-enforced variant.

    Strategy: strip code fences if present, then json.loads. On failure
    returns empty dict so the caller sees confidence=0 + cat=uncertain."""
    if not text:
        return {}
    s = text.strip()
    # Strip ```json / ``` fences
    if s.startswith("```"):
        # Find the first newline (skip the language tag) + the final ```
        first_nl = s.find("\n")
        if first_nl > 0:
            s = s[first_nl + 1:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    # If still wrapped in some prose, find first { ... } range
    if not s.startswith("{"):
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            s = s[first:last + 1]
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:   # noqa: BLE001
        return {}
