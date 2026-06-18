"""
RAG Router — RAG-ROUTER-001 (P15-S10 D6).

3-engine pluggable dispatch (pgvector / pageindex / docsage) per query
characteristics + tenant_settings.rag_engines whitelist. Phase 1.5 uses
a heuristic; Phase 2 swaps to a small classifier LLM per
RAG_ADDENDUM_2026_05.md §7 question 4.

Routing heuristic (P15-S10):

  Rule 1 — query has doc-citation pattern keyword
           ("trong hợp đồng", "section X", "điều khoản",
            "khoản phạt", "điều ", "chương ", "mục ")
           → pageindex
  Rule 2 — query is short (< 8 words) AND keyword
           ("insight", "summary", "tóm tắt", "trends", "xu hướng")
           → pgvector (cheap insight panel)
  Rule 3 — query is long (≥ 20 words) AND multi-entity pattern
           ("so sánh", "compare", "top ", "ranking", "across all")
           → docsage (manager BI question)
  Default → pgvector

Tenant whitelist:
  tenant_settings.rag_engines is an optional list of engine names. If
  set + non-empty, the router restricts to that whitelist; if the
  routed engine isn't in the whitelist, the router falls back to the
  first whitelisted engine (defensive — don't 503 a query because the
  tenant excluded one engine).

Engine fallback:
  If the routed engine raises NotImplementedError (DocSage stub does
  this until S11), the router falls back to pgvector_stub. Logged at
  WARNING so the operator sees the fallback path firing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from .engines import (
    DocSageStubEngine,
    PageIndexEngine,
    PGVectorStubEngine,
    RAGAnswer,
    RAGEngine,
    RAGEngineUnavailable,
    RAGQuery,
    TraceRecallEngine,
)

log = structlog.get_logger()


# Heuristic keyword sets — kept module-level + frozenset so tests can
# import + assert on them (catches typos when adding Vietnamese terms).
_DOC_CITATION_KEYWORDS = frozenset({
    "trong hợp đồng", "hợp đồng", "section ", "điều khoản",
    "khoản phạt", "điều ", "chương ", "mục ", "appendix",
})
_SHORT_INSIGHT_KEYWORDS = frozenset({
    "insight", "summary", "tóm tắt", "trends", "xu hướng",
})
_MULTI_ENTITY_KEYWORDS = frozenset({
    # Comparison
    "so sánh", "compare",
    # Ranking
    "top ", "ranking", "xếp hạng", "thứ hạng", "đứng đầu", "đứng cuối",
    # Aggregation
    "tổng ", "tổng cộng", "trung bình", "trung vị", "average",
    "ít nhất", "nhiều nhất", "lớn nhất", "nhỏ nhất", "cao nhất", "thấp nhất",
    # Relationship / cross-doc
    "across all", "all customers", "tất cả khách", "tất cả chi nhánh",
    "5 customer", "10 customer", "khách nào", "chi nhánh nào",
    "vendor nào", "phòng ban nào", "đơn nào",
})

# P2-S21: reasoning-task keywords trigger trace_recall (4th engine).
# Distinct from doc-citation + insight-summary + multi-entity buckets —
# these are PROCEDURAL queries ("how do I", "what should I", "tối ưu",
# "kế hoạch") where prior thinking traces are most valuable.
_REASONING_TASK_KEYWORDS = frozenset({
    # Vietnamese reasoning verbs
    "tính toán", "lập luận", "phân tích", "tối ưu", "đề xuất",
    "khuyến nghị", "kế hoạch", "chiến lược", "quy trình", "cách",
    "làm sao", "nên làm gì", "phương án",
    # English reasoning verbs
    "what should", "how do i", "how should", "strategy", "plan ",
    "optimize", "approach", "recommend", "advise",
})

ALL_ENGINE_NAMES = ("pgvector", "pageindex", "docsage", "trace_recall")


@dataclass(frozen=True)
class RoutingDecision:
    """Captured for audit + tests. The router emits one per call."""

    engine_name: str
    reason: str                    # human-readable rule that fired
    fallback_from: Optional[str] = None  # set if NotImplementedError fallback


class RAGRouter:
    """Pluggable router. Engines passed in for testability — defaults
    are the stub bundle so the router is usable end-to-end on day one."""

    def __init__(
        self,
        *,
        pgvector: Optional[RAGEngine] = None,
        pageindex: Optional[RAGEngine] = None,
        docsage: Optional[RAGEngine] = None,
        trace_recall: Optional[RAGEngine] = None,
    ) -> None:
        self.engines: dict[str, RAGEngine] = {
            "pgvector": pgvector or PGVectorStubEngine(),
            "pageindex": pageindex or PageIndexEngine(),
            "docsage": docsage or DocSageStubEngine(),
        }
        # trace_recall is opt-in: requires a MemoryService at construction
        # time. If caller didn't pass one, the engine isn't registered and
        # routing to "trace_recall" falls back to pgvector.
        if trace_recall is not None:
            self.engines["trace_recall"] = trace_recall

    # ------------------------------------------------------------------
    # Routing — pure function, returns the engine name + reason
    # ------------------------------------------------------------------

    @staticmethod
    def route(
        query: RAGQuery,
        whitelist: Optional[list[str]] = None,
    ) -> RoutingDecision:
        """Pure routing decision — no I/O. Tests call this directly to
        assert routing behaviour without instantiating engines."""
        text_lower = query.query_text.lower()
        word_count = len(query.query_text.split())

        # Rule 1 — doc citation pattern wins regardless of length
        for kw in _DOC_CITATION_KEYWORDS:
            if kw in text_lower:
                decision = RoutingDecision(
                    engine_name="pageindex",
                    reason=f"doc-citation keyword {kw!r} matched",
                )
                return _apply_whitelist(decision, whitelist)

        # P2-S21 Rule 4 — reasoning task triggers trace_recall.
        # Placed AFTER doc-citation so contractual questions still pageindex,
        # BEFORE length-based short/long rules because reasoning queries
        # span both short (procedural how-to) and long (multi-step plan).
        if word_count >= 8:
            for kw in _REASONING_TASK_KEYWORDS:
                if kw in text_lower:
                    decision = RoutingDecision(
                        engine_name="trace_recall",
                        reason=f"reasoning-task keyword {kw!r} matched ({word_count} words)",
                    )
                    return _apply_whitelist(decision, whitelist)

        # Rule 2 — short insight queries → pgvector
        if word_count < 8:
            for kw in _SHORT_INSIGHT_KEYWORDS:
                if kw in text_lower:
                    decision = RoutingDecision(
                        engine_name="pgvector",
                        reason=f"short insight keyword {kw!r} matched ({word_count} words)",
                    )
                    return _apply_whitelist(decision, whitelist)

        # Rule 3 — long multi-entity → docsage
        if word_count >= 20:
            for kw in _MULTI_ENTITY_KEYWORDS:
                if kw in text_lower:
                    decision = RoutingDecision(
                        engine_name="docsage",
                        reason=f"long multi-entity keyword {kw!r} matched ({word_count} words)",
                    )
                    return _apply_whitelist(decision, whitelist)

        # Default — pgvector covers most insight panel + chat queries
        decision = RoutingDecision(
            engine_name="pgvector",
            reason="default — no specific pattern matched",
        )
        return _apply_whitelist(decision, whitelist)

    # ------------------------------------------------------------------
    # Dispatch — async, includes NotImplementedError fallback
    # ------------------------------------------------------------------

    async def answer(
        self,
        query: RAGQuery,
        whitelist: Optional[list[str]] = None,
    ) -> RAGAnswer:
        """Route + dispatch.

        On NotImplementedError from the routed engine, fall back to the
        next available engine — but always within the tenant's whitelist
        if one is set. If every whitelisted engine is unavailable, raise
        RAGEngineUnavailable so the tenant policy isn't silently bypassed
        (R1 self-review fix; the previous behaviour unconditionally fell
        back to pgvector even when the tenant whitelist excluded it).
        """
        decision = self.route(query, whitelist=whitelist)
        log.info(
            "rag.router.decision",
            tenant_id=query.tenant_id,
            engine=decision.engine_name,
            reason=decision.reason,
            whitelist=whitelist,
        )

        # Build the fallback chain: routed engine first, then any others
        # the tenant allows. No whitelist → all engines are allowed; the
        # routed engine is still tried first so successful routes don't
        # change behaviour.
        if whitelist:
            allowed = [name for name in whitelist if name in self.engines]
        else:
            allowed = list(self.engines.keys())

        attempt_order = [decision.engine_name] + [
            n for n in allowed if n != decision.engine_name
        ]

        last_error: Optional[NotImplementedError] = None
        for engine_name in attempt_order:
            if engine_name not in self.engines:
                continue  # routed engine excluded by whitelist
            try:
                return await self.engines[engine_name].answer(query)
            except NotImplementedError as exc:
                last_error = exc
                log.warning(
                    "rag.router.engine_not_implemented",
                    tenant_id=query.tenant_id,
                    attempted_engine=engine_name,
                    error=str(exc),
                )

        raise RAGEngineUnavailable(
            f"no available RAG engine in allowed set {attempt_order!r} "
            f"could answer for tenant {query.tenant_id!r}: "
            f"last error = {last_error!r}"
        )


def _apply_whitelist(
    decision: RoutingDecision, whitelist: Optional[list[str]],
) -> RoutingDecision:
    """Restrict the decision to the tenant's whitelisted engines.

    If the picked engine is NOT in the whitelist, fall back to the first
    whitelisted engine (defensive: don't 503 a query because the tenant
    excluded the routed engine — answer with what they allow).
    """
    if not whitelist:
        return decision
    if decision.engine_name in whitelist:
        return decision
    if not whitelist:
        return decision
    fallback = whitelist[0]
    return RoutingDecision(
        engine_name=fallback,
        reason=f"{decision.reason}; whitelist override → {fallback}",
        fallback_from=decision.engine_name,
    )
