"""
RAG answer router — P15-S10 D6 (RAG-ROUTER-001 HTTP surface).

Wraps `reasoning.rag.router.RAGRouter` so the 3-engine dispatch
(pgvector / pageindex / docsage) is callable over HTTP for FE consumption.

Endpoint::

    POST /api/v1/rag/answer        natural-language query → answer + citations

Auth + tenant scoping via ``X-Enterprise-Id`` header (K-12 / K-16: never
trust a tenant id from body / query). The gateway extracts this from the
JWT before forwarding to ai-orchestrator.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..reasoning.rag.cdfl_reranker import CDFLRagReranker, rerank_to_answer
from ..reasoning.rag.engines import RAGEngineUnavailable, RAGQuery
from ..reasoning.rag.pageindex import StubPageIndexTreeBuilder
from ..reasoning.rag.router import RAGRouter

log = structlog.get_logger()

router = APIRouter()


_ROUTER_SINGLETON: Optional[RAGRouter] = None
_RERANKER_SINGLETON: Optional[CDFLRagReranker] = None
_TREE_BUILDER_SINGLETON: Optional[StubPageIndexTreeBuilder] = None


def _get_router() -> RAGRouter:
    """Lazily-built singleton — stubs construct quickly but a future
    real PageIndex builder opens a Postgres pool + LLM client, both of
    which we want to share.

    P2-S21 follow-up: when env `RAG_TRACE_RECALL_ENABLED=true`, register
    the TraceRecallEngine (P2-S21 D2 / ADR-0021) so reasoning-task
    queries route to it per RAGRouter Rule 4. Otherwise the default
    3-engine bundle (pgvector + pageindex + docsage) is kept.
    """
    global _ROUTER_SINGLETON
    if _ROUTER_SINGLETON is None:
        import os
        trace_recall_engine = None
        if os.getenv("RAG_TRACE_RECALL_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }:
            try:
                from ..reasoning.memory.service import MemoryService
                from ..reasoning.rag.engines.trace_recall import TraceRecallEngine
                trace_recall_engine = TraceRecallEngine(MemoryService())
                log.info("rag.trace_recall.registered")
            except Exception:
                log.exception("rag.trace_recall.register_failed")
        # Wire the REAL pgvector engine (bronze docsage corpus + curated KB via
        # stored bge-m3 embeddings). The router defaulted to the stub before, so
        # /rag/answer had been shipping placeholder answers on the default route.
        try:
            from ..reasoning.rag.engines.pgvector_real import PgVectorRealEngine
            from ..shared.db import get_pool
            pgvector_engine = PgVectorRealEngine(db_pool=get_pool())
        except Exception:
            log.exception("rag.pgvector_real.register_failed")
            pgvector_engine = None
        _ROUTER_SINGLETON = RAGRouter(pgvector=pgvector_engine, trace_recall=trace_recall_engine)
    return _ROUTER_SINGLETON


def _get_reranker() -> CDFLRagReranker:
    """Singleton CDFL reranker — preserves per-tenant model state across
    calls so IG signal accumulates over a session. Phase 1.5 in-memory."""
    global _RERANKER_SINGLETON
    if _RERANKER_SINGLETON is None:
        _RERANKER_SINGLETON = CDFLRagReranker()
    return _RERANKER_SINGLETON


def _get_tree_builder() -> StubPageIndexTreeBuilder:
    """Singleton PageIndex tree builder for the cdfl_ig path. Phase 1.5
    uses the stub; FixturePageIndexTreeBuilder swap-in is a one-line
    constructor change when a tenant has a pre-built fixture."""
    global _TREE_BUILDER_SINGLETON
    if _TREE_BUILDER_SINGLETON is None:
        _TREE_BUILDER_SINGLETON = StubPageIndexTreeBuilder()
    return _TREE_BUILDER_SINGLETON


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class RAGCitationOut(BaseModel):
    """One citation. Per-engine fields are optional so FE renders only
    the populated ones."""

    engine_name: str
    source_id: str
    snippet: Optional[str] = None
    similarity: Optional[float] = None
    node_path: Optional[list[str]] = None
    page_range: Optional[str] = None
    sql_query: Optional[str] = None
    rows_returned: Optional[int] = None


class RAGAnswerRequest(BaseModel):
    """POST /rag/answer body. tenant_id is NEVER read from here — K-12.
    The router extracts it from the X-Enterprise-Id header."""

    query_text: str = Field(min_length=1, max_length=2000)
    locale: str = Field(default="vi", description="'vi' or 'en'")
    max_citations: int = Field(default=5, ge=1, le=20)
    engines_whitelist: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional per-call whitelist. Tenant-level whitelist in "
            "tenant_settings.rag_engines takes precedence; this is a "
            "narrowing override (intersection)."
        ),
    )


class RAGAnswerResponse(BaseModel):
    """Engine response envelope. FE renders `answer` as the chat reply
    and `citations` as the source trail."""

    engine_name: str
    answer: str
    citations: list[RAGCitationOut]
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/rag/answer", response_model=RAGAnswerResponse, tags=["RAG"])
async def answer_query(
    body: RAGAnswerRequest,
    x_enterprise_id: Annotated[str, Header()],
    ranking: Annotated[
        Literal["default", "cdfl_ig"],
        Query(description="default = heuristic engine dispatch; cdfl_ig = "
              "PageIndex tree leaves re-ranked by CDFL information gain "
              "(novelty + uncertainty per NNL-NTHT, in-memory per-tenant "
              "session model)."),
    ] = "default",
):
    """Route + dispatch a RAG query.

    Default heuristic dispatch per RAG_ADDENDUM_2026_05.md:
      - doc-citation pattern → pageindex
      - short insight query → pgvector
      - long multi-entity question → docsage
      - default → pgvector

    Tenant whitelist (tenant_settings.rag_engines) restricts which engines
    can answer. If every whitelisted engine raises NotImplementedError
    (DocSage stub today), responds 503 rather than silently bypassing
    the policy (R1 self-review fix).

    ranking=cdfl_ig: bypass heuristic dispatch + force PageIndex path,
    then re-rank leaves via CDFLRagReranker. Subsequent calls for the
    same tenant accumulate session state — leaves visited many times
    lose IG; unexplored leaves get an uncertainty bonus. Phase 1.5
    in-memory only.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)

    query = RAGQuery(
        tenant_id=str(enterprise_id),
        query_text=body.query_text,
        locale=body.locale,
        max_citations=body.max_citations,
    )

    if ranking == "cdfl_ig":
        return await _answer_via_cdfl_ig(query, body, enterprise_id)

    rag_router = _get_router()
    try:
        result = await rag_router.answer(query, whitelist=body.engines_whitelist)
    except RAGEngineUnavailable as exc:
        log.warning(
            "rag.answer.no_engine_available",
            tenant_id=str(enterprise_id),
            whitelist=body.engines_whitelist,
            error=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://kaori.ai/errors/rag-engine-unavailable",
                "title": "No RAG engine available for tenant",
                "detail": str(exc),
                "errcode": "BIZ-ERR1",
            },
        )

    return RAGAnswerResponse(
        engine_name=result.engine_name,
        answer=result.answer,
        citations=[_citation_to_wire(c) for c in result.citations],
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
    )


async def _answer_via_cdfl_ig(
    query: RAGQuery,
    body: RAGAnswerRequest,
    enterprise_id: UUID,
) -> RAGAnswerResponse:
    """ranking=cdfl_ig branch — force PageIndex + CDFL rerank path.

    Whitelist still honoured: if the tenant has a non-empty whitelist
    that excludes pageindex, we 503 rather than silently bypassing.
    """
    if body.engines_whitelist and "pageindex" not in body.engines_whitelist:
        log.warning(
            "rag.answer.cdfl_ig_not_in_whitelist",
            tenant_id=str(enterprise_id),
            whitelist=body.engines_whitelist,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "type": "https://kaori.ai/errors/rag-engine-unavailable",
                "title": "cdfl_ig requires pageindex engine; not in whitelist",
                "detail": (
                    "tenant whitelist excludes pageindex — CDFL re-ranking "
                    "cannot run on a non-PageIndex engine."
                ),
                "errcode": "BIZ-ERR1",
            },
        )

    builder = _get_tree_builder()
    reranker = _get_reranker()

    tree = await builder.build(
        tenant_id=query.tenant_id,
        doc_sha256="[STUB]doc-pageindex-1",
        doc_text="",
        doc_kind="pdf",
    )
    result = rerank_to_answer(reranker, tree, query)

    log.info(
        "rag.answer.cdfl_ig",
        tenant_id=str(enterprise_id),
        candidates=len(_collect_leaves_count(tree)),
        tenants_with_state=len(reranker.tenants_with_state()),
    )

    return RAGAnswerResponse(
        engine_name=result.engine_name,
        answer=result.answer,
        citations=[_citation_to_wire(c) for c in result.citations],
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
    )


def _collect_leaves_count(tree) -> list:
    """Cheap shim for logging — collect_leaves is private to reranker."""
    from ..reasoning.rag.cdfl_reranker import _collect_leaves

    return _collect_leaves(tree.root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_enterprise_id(header_value: str) -> UUID:
    """K-14 RFC 7807 envelope on bad UUID rather than 422."""
    try:
        return UUID(header_value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://kaori.ai/errors/bad-enterprise-id",
                "title": "X-Enterprise-Id must be a UUID",
                "detail": f"got {header_value!r}",
                "errcode": "USR-ERR4",
            },
        )


def _citation_to_wire(c) -> RAGCitationOut:
    return RAGCitationOut(
        engine_name=c.engine_name,
        source_id=c.source_id,
        snippet=c.snippet,
        similarity=c.similarity,
        node_path=list(c.node_path) if c.node_path else None,
        page_range=c.page_range,
        sql_query=c.sql_query,
        rows_returned=c.rows_returned,
    )
