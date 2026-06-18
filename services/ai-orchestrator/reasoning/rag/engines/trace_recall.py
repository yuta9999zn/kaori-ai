"""
trace_recall — 4th RAG engine (P2-S21 D2).

Retrieves thinking-trace memories (Memory L4 PROCEDURAL tier produced by
T-Cube transformer) for reasoning-flavoured queries. Inspired by arXiv
2605.03344 — instead of retrieving doc chunks, we retrieve compressed
reasoning experiences that previously solved similar problems.

Routing rule (added to rag.router as Rule 4):

  Rule 4 — query indicates reasoning task (keyword set
           {"tính toán", "lập luận", "quy trình", "phân tích",
            "tối ưu", "đề xuất", "khuyến nghị", "what should",
            "how do I", "strategy", "kế hoạch"})
           AND length >= 8 words
           → trace_recall

The engine queries L4 with form="semantic" first (the embedding-ready
form), reranks by problem-context similarity, then includes the matching
"reflect" form as a "watch out for" hint in the answer.

K-rules:
  - K-1 / K-12: tenant_id filter on every read (RLS enforced via memory store)
  - K-3: no direct LLM call — engine is retrieval-only; augmentation is
         the caller's responsibility (see reasoning.augment)
"""
from __future__ import annotations

import time
from typing import Optional
from uuid import UUID

import structlog

from ...memory.service import MemoryService
from ...memory.types import MemoryTier, MemoryType
from .base import RAGAnswer, RAGCitation, RAGEngine, RAGQuery

log = structlog.get_logger()


class TraceRecallEngine(RAGEngine):
    """Retrieve top-k semantic-form thinking traces and assemble an
    answer that surfaces (a) procedural steps from the matching trace,
    (b) reflect-form pitfalls as warning.

    The engine does NOT call an LLM — it returns retrieved content so
    the caller can decide to augment a fresh LLM prompt (see
    reasoning.augment.augment_prompt_with_traces).
    """

    engine_name = "trace_recall"

    def __init__(self, memory_service: MemoryService, *, top_k: int = 3):
        self._memory = memory_service
        self._top_k = top_k

    async def answer(self, query: RAGQuery) -> RAGAnswer:
        t0 = time.perf_counter()
        tenant = UUID(query.tenant_id)
        # MemoryService.retrieve walks tiers using cheap_text_match; we
        # restrict to L4_LONG (where PROCEDURAL records live by default),
        # then filter Python-side by memory_type + tcube_form metadata.
        # Over-fetch (top_k * 4) so that after filtering we still have
        # top_k candidates if the L4 slice mixes other memory types.
        raw = await self._memory.retrieve(
            tenant_id=tenant,
            query=query.query_text,
            top_k=self._top_k * 4,
            tier=MemoryTier.L4_LONG.value,
        )
        semantic_hits = [
            r for r in raw
            if r.memory_type == MemoryType.PROCEDURAL
            and r.metadata.get("tcube_form") == "semantic"
        ][: self._top_k]

        if not semantic_hits:
            elapsed = int((time.perf_counter() - t0) * 1000)
            log.info("trace_recall.empty",
                     tenant_id=str(tenant),
                     query=query.query_text[:80])
            return RAGAnswer(
                engine_name=self.engine_name,
                answer=(
                    "Không tìm thấy kinh nghiệm tương tự trong Memory L4 "
                    "Procedural. Hệ thống chưa từng giải bài toán cùng "
                    "dạng — sẽ giải từ đầu."
                ),
                citations=(),
                latency_ms=elapsed,
            )

        # Build answer: concatenate semantic insights + reflect warnings.
        # Each semantic hit may have a sibling reflect record produced by
        # the same source_decision_id — we look those up.
        answer_parts: list[str] = []
        citations: list[RAGCitation] = []
        seen_sources: set[str] = set()

        for rec in semantic_hits:
            src = rec.metadata.get("source_decision_id", "")
            if src in seen_sources:
                continue
            seen_sources.add(src)
            answer_parts.append(f"• Insight: {rec.content}")
            citations.append(RAGCitation(
                engine_name=self.engine_name,
                source_id=src,
                snippet=rec.content[:300],
                similarity=None,  # MemoryService doesn't expose score yet
            ))
            # Find sibling reflect record (same source_decision_id)
            sibling = await self._fetch_reflect_sibling(tenant, src)
            if sibling is not None:
                answer_parts.append(f"  Cảnh báo: {sibling}")

        elapsed = int((time.perf_counter() - t0) * 1000)
        log.info("trace_recall.hit",
                 tenant_id=str(tenant),
                 query=query.query_text[:80],
                 traces_returned=len(citations))

        return RAGAnswer(
            engine_name=self.engine_name,
            answer="\n".join(answer_parts),
            citations=tuple(citations),
            latency_ms=elapsed,
            cost_usd=None,  # retrieval-only — no LLM call
        )

    async def _fetch_reflect_sibling(
        self,
        tenant_id: UUID,
        source_decision_id: str,
    ) -> Optional[str]:
        """Look up reflect-form record that shares source_decision_id.

        MemoryService.retrieve scores by `cheap_text_match` on content
        text — the source_decision_id only lives in metadata, so a
        retrieve-by-text won't find the sibling reliably. We use the
        L4 tier store's `list_all` directly and filter by metadata
        Python-side. L4 stays small per tenant (PROCEDURAL is curated)
        so the scan is bounded.
        """
        records = await self._memory.l4.list_all(tenant_id)
        for rec in records:
            if (rec.memory_type == MemoryType.PROCEDURAL
                    and rec.metadata.get("source_decision_id") == source_decision_id
                    and rec.metadata.get("tcube_form") == "reflect"):
                return rec.content
        return None
