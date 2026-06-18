"""
Phase 2.5 — `summarise_document` AI node.

Takes a list[Block] from Stage 6 docsage_extract output and returns an
executive summary + 3-7 key bullets + the document's "what-to-do-next"
hint. One LLM call per document.

Use cases (per WORKFLOW_USE_CASES.md):
- Long regulation / circular landing in compliance inbox — manager
  needs the gist + impact bullets before deciding to forward.
- Meeting minutes (.docx) → bullet list of action items.
- Vendor proposal (PDF) → executive summary + asks + price ballpark.
- CFO digest companion: per-quarter report → 1-paragraph summary that
  feeds NOV-RPT-020.

Design choices
--------------
1. **One LLM call, bounded prompt** — body capped near 6 KB (bigger
   envelope than classify_document because summarisation needs more
   context). TITLE blocks still surfaced first.
2. **Strict JSON output** — caller renders into the FE summary card
   without parsing free text. Bullets returned as `list[str]`, max 7.
3. **Reading time hint** — em compute a rough reading_time_seconds
   from char_length so the FE can show "Tóm tắt — đọc nhanh trong 30s"
   labels. Pure-Python, no extra LLM cost.
4. **Vietnamese-first** — prompt + bullets emit in Vietnamese unless
   the caller flags `target_lang='en'` (Phase 3 hook).

K-rules
-------
K-3: LLM dispatch via llm_router only.
K-4: Qwen local default. consent_external opt-in path for richer
     summarisation on long English documents.
K-17: side_effect_class = read_only — caller persists.
K-20: model pinning via task='summarise_document' in llm_router
     routing config.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import structlog

from ..data_plane_shim import Block, BlockType
from ..engine.llm_router import llm_router

log = structlog.get_logger()


# Reading speed heuristic. Average adult Vietnamese reads ~200 wpm;
# em assume ~5 chars per word → 1000 chars per minute → 16.67 chars/sec.
# This is a UI hint, not a contract — round to nearest 5 seconds.
_CHARS_PER_SECOND = 17.0


@dataclass
class SummariseInput:
    blocks:           list[Block]
    enterprise_id:    str
    consent_external: bool = False
    run_id:           Optional[str] = None
    # How many bullets the caller wants. LLM may emit fewer if the
    # document is short; never more than max_bullets.
    max_bullets:      int = 5
    # Target language for the summary. 'vi' (default) or 'en'.
    target_lang:      str = "vi"


@dataclass(frozen=True)
class SummariseOutput:
    summary:               str              # 2-4 sentence executive summary
    bullets:               list[str]        # key points
    next_action_hint:      str              # "what should the reader do next"
    source_char_length:    int              # how many chars summarised
    reading_time_seconds:  int              # rough estimate of original


_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "bullets", "next_action_hint"],
    "properties": {
        "summary":          {"type": "string", "maxLength": 1500},
        "bullets":          {
            "type": "array",
            "items": {"type": "string", "maxLength": 400},
            "maxItems": 7,
        },
        "next_action_hint": {"type": "string", "maxLength": 300},
    },
}


def _build_prompt(
    blocks:      list[Block],
    max_bullets: int,
    target_lang: str,
) -> str:
    """Compose the summarisation prompt. Bigger envelope than
    classify_document (6 KB) because summarisation needs more context
    to surface the right bullets."""
    titles = [b.text for b in blocks if b.type == BlockType.TITLE]
    body_chars = 0
    body_bits: list[str] = []
    for b in blocks:
        if b.type in (BlockType.HEADER, BlockType.FOOTER, BlockType.PAGE_NUMBER):
            continue
        snippet = b.text[:1500]
        if body_chars + len(snippet) > 6000:
            break
        body_bits.append(snippet)
        body_chars += len(snippet)

    lang_clause = "tiếng Việt" if target_lang == "vi" else "English"
    persona = (
        "Bạn là trợ lý tóm tắt tài liệu kinh doanh."
        if target_lang == "vi" else
        "You summarise business documents for senior managers."
    )

    parts = [
        persona,
        "",
        f"Trả về JSON với 3 trường, viết bằng {lang_clause}:",
        f"  summary           — 2-4 câu tóm tắt cốt lõi",
        f"  bullets           — tối đa {max_bullets} bullet, mỗi bullet 1-2 câu",
        f"  next_action_hint  — 1 câu gợi ý người đọc nên làm gì tiếp theo",
        "",
    ]
    if titles:
        parts.append("Tiêu đề tài liệu: " + " / ".join(titles[:3]))
    parts.append("")
    parts.append("Nội dung tài liệu:")
    parts.append("\n".join(body_bits))
    parts.append("")
    parts.append("Không thêm trường khác. Không thêm văn bản ngoài JSON.")
    return "\n".join(parts)


def _estimate_reading_time(blocks: list[Block]) -> tuple[int, int]:
    """Return (char_length, reading_time_seconds). Pure Python."""
    total = sum(
        b.char_length for b in blocks
        if b.type not in (BlockType.HEADER, BlockType.FOOTER, BlockType.PAGE_NUMBER)
    )
    seconds = round(total / _CHARS_PER_SECOND / 5) * 5
    return total, max(seconds, 5)


async def summarise_document(inp: SummariseInput) -> SummariseOutput:
    """Summarise the document into 2-4 sentences + N bullets + a
    next-action hint. Caller decides whether to surface the summary in
    the FE, attach to an email digest, or feed into NOV-RPT-020."""
    char_length, reading_time = _estimate_reading_time(inp.blocks)
    prompt = _build_prompt(inp.blocks, inp.max_bullets, inp.target_lang)

    try:
        result = await llm_router.complete_with_schema(
            prompt=prompt,
            task="summarise_document",
            output_schema=_OUTPUT_SCHEMA,
            consent_external=inp.consent_external,
            enterprise_id=inp.enterprise_id,
            run_id=inp.run_id,
            max_tokens=900,
        )
    except AttributeError:
        text = await llm_router.complete(
            prompt=prompt,
            task="summarise_document",
            consent_external=inp.consent_external,
            enterprise_id=inp.enterprise_id,
            run_id=inp.run_id,
            max_tokens=900,
        )
        from .document_classifier import _parse_json_fallback
        result = _parse_json_fallback(text)

    summary = str(result.get("summary", ""))[:1500]
    bullets_raw = result.get("bullets", []) or []
    bullets = [str(b)[:400] for b in bullets_raw if isinstance(b, (str, int, float))]
    bullets = bullets[: inp.max_bullets]
    next_action = str(result.get("next_action_hint", ""))[:300]

    log.info("summarise_document.done",
             bullets=len(bullets),
             reading_time_seconds=reading_time,
             enterprise_id=inp.enterprise_id)

    return SummariseOutput(
        summary=summary,
        bullets=bullets,
        next_action_hint=next_action,
        source_char_length=char_length,
        reading_time_seconds=reading_time,
    )
