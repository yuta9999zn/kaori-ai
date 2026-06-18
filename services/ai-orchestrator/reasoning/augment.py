"""
P2-S21 D3 — reasoning-augmented prompt hook.

Helper function that AI node handlers (mig 068 catalog: call_insight_engine,
call_recommendation_engine, call_risk_detection, call_forecasting) call
BEFORE LLM dispatch to enrich the prompt with relevant prior thinking
traces from Memory L4 PROCEDURAL tier.

Pattern::

    augmented, source_ids = await augment_prompt_with_traces(
        base_prompt=user_prompt,
        tenant_id=tenant,
        query_text=user_query,
        memory_service=memsvc,
    )
    # send augmented prompt to llm-gateway, log source_ids for traceability

The function is a NO-OP when no traces found — caller's prompt passes
through unchanged so AI nodes still work in a cold-start environment.

K-rules:
  - K-1 / K-12: tenant_id from JWT (caller's responsibility); helper
    re-validates by passing tenant_id directly to MemoryService.
  - K-6: source_decision_ids returned for audit log linkage — the
    caller writes a `traces_used` field on its own decision_audit_log
    row so the lineage is queryable.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

import structlog

from .memory.service import MemoryService
from .rag.engines.base import RAGQuery
from .rag.engines.trace_recall import TraceRecallEngine

log = structlog.get_logger()


_TRACE_BLOCK_HEADER_VI = "Kinh nghiệm từ các bài toán tương tự đã giải:"
_TRACE_BLOCK_FOOTER_VI = (
    "\n--- Hết kinh nghiệm. Áp dụng nếu phù hợp; bỏ qua nếu khác bản chất. ---\n"
)


async def augment_prompt_with_traces(
    *,
    base_prompt: str,
    tenant_id: UUID,
    query_text: str,
    memory_service: MemoryService,
    top_k: int = 3,
    locale: str = "vi",
) -> tuple[str, list[str]]:
    """Prepend trace_recall hits to base_prompt.

    Returns the augmented prompt + list of source_decision_ids for
    audit log linkage. If no traces match, returns (base_prompt, []).

    Locale 'vi' uses Vietnamese block headers; 'en' falls back to
    "Prior solved cases:" / "End of cases." headers (P3 international).
    """
    engine = TraceRecallEngine(memory_service, top_k=top_k)
    rag_query = RAGQuery(
        tenant_id=str(tenant_id),
        query_text=query_text,
        locale=locale,
        max_citations=top_k,
    )
    answer = await engine.answer(rag_query)

    if not answer.citations:
        log.info("augment.no_traces",
                 tenant_id=str(tenant_id),
                 query=query_text[:80])
        return base_prompt, []

    header = (_TRACE_BLOCK_HEADER_VI if locale == "vi"
              else "Prior solved cases:")
    footer = (_TRACE_BLOCK_FOOTER_VI if locale == "vi"
              else "\n--- End of cases. Apply if relevant; skip otherwise. ---\n")
    trace_block = f"{header}\n{answer.answer}{footer}"
    source_ids = [c.source_id for c in answer.citations]
    log.info("augment.traces_added",
             tenant_id=str(tenant_id),
             query=query_text[:80],
             trace_count=len(source_ids))
    return trace_block + base_prompt, source_ids
