"""Tests for RAG Router + engines — P15-S10 D6 + D8."""
from __future__ import annotations

import asyncio

import pytest

from reasoning.rag.engines import (
    DocSageStubEngine,
    PageIndexEngine,
    PGVectorStubEngine,
    RAGAnswer,
    RAGCitation,
    RAGEngine,
    RAGEngineUnavailable,
    RAGQuery,
)
from reasoning.rag.engines.base import RAGEngine as RAGEngineBase
from reasoning.rag.pageindex.retriever import (
    PageIndexRetriever,
    StubPageIndexRetriever,
)
from reasoning.rag.router import (
    ALL_ENGINE_NAMES,
    RAGRouter,
    RoutingDecision,
)


# ---------------------------------------------------------------------------
# Routing decision (pure function — no engines)
# ---------------------------------------------------------------------------


def test_route_doc_citation_keyword_picks_pageindex():
    """Rule 1 — 'điều khoản' triggers pageindex regardless of length."""
    q = RAGQuery(tenant_id="t1", query_text="điều khoản phạt vi phạm trong hợp đồng X")
    d = RAGRouter.route(q)
    assert d.engine_name == "pageindex"


def test_route_short_insight_keyword_picks_pgvector():
    """Rule 2 — short query + 'tóm tắt' → pgvector."""
    q = RAGQuery(tenant_id="t1", query_text="tóm tắt churn tuần qua")
    d = RAGRouter.route(q)
    assert d.engine_name == "pgvector"


def test_route_long_multi_entity_picks_docsage():
    """Rule 3 — long query (≥20 words) + 'so sánh' → docsage."""
    q = RAGQuery(
        tenant_id="t1",
        query_text=(
            "so sánh doanh thu của top 10 customer trong quý vừa rồi với cùng kỳ "
            "năm trước trên tất cả các kênh phân phối quan trọng nhất"
        ),
    )
    d = RAGRouter.route(q)
    assert d.engine_name == "docsage"


def test_route_default_falls_through_to_pgvector():
    """Anything that doesn't match a rule → pgvector default."""
    q = RAGQuery(tenant_id="t1", query_text="hello world")
    d = RAGRouter.route(q)
    assert d.engine_name == "pgvector"
    assert "default" in d.reason


def test_route_whitelist_overrides_when_routed_engine_excluded():
    """Tenant whitelist excludes pageindex → router picks the first
    whitelisted engine + sets fallback_from."""
    q = RAGQuery(tenant_id="t1", query_text="điều khoản phạt trong hợp đồng X")
    d = RAGRouter.route(q, whitelist=["pgvector", "docsage"])
    assert d.engine_name == "pgvector"
    assert d.fallback_from == "pageindex"
    assert "whitelist override" in d.reason


def test_route_whitelist_passes_through_when_engine_allowed():
    """Whitelist contains the routed engine → no override."""
    q = RAGQuery(tenant_id="t1", query_text="điều khoản phạt trong hợp đồng X")
    d = RAGRouter.route(q, whitelist=["pgvector", "pageindex"])
    assert d.engine_name == "pageindex"
    assert d.fallback_from is None


def test_route_empty_whitelist_treated_as_no_restriction():
    """Empty list = same as None — don't lock the tenant out of all engines."""
    q = RAGQuery(tenant_id="t1", query_text="điều khoản phạt trong hợp đồng X")
    d = RAGRouter.route(q, whitelist=[])
    assert d.engine_name == "pageindex"


def test_all_engine_names_constant_matches_router_dict():
    """Catch typos: ALL_ENGINE_NAMES module-level constant must include
    every engine the router instantiates. Note `trace_recall` (P2-S21)
    is opt-in via constructor arg — it's listed in ALL_ENGINE_NAMES but
    NOT in default RAGRouter().engines. The default router must be a
    SUBSET of ALL_ENGINE_NAMES."""
    router = RAGRouter()
    assert set(router.engines.keys()).issubset(set(ALL_ENGINE_NAMES))
    # Required-always engines (default bundle): pgvector + pageindex + docsage
    assert {"pgvector", "pageindex", "docsage"}.issubset(set(router.engines.keys()))
    # trace_recall must appear in the constant for whitelist validation
    assert "trace_recall" in ALL_ENGINE_NAMES


# ---------------------------------------------------------------------------
# Engine dispatch — async; uses default stub bundle
# ---------------------------------------------------------------------------


def test_pgvector_stub_returns_marked_answer():
    engine = PGVectorStubEngine()
    answer = asyncio.run(engine.answer(RAGQuery(tenant_id="t1", query_text="anything")))
    assert answer.engine_name == "pgvector"
    assert "[STUB pgvector]" in answer.answer
    assert len(answer.citations) == 1
    assert answer.citations[0].engine_name == "pgvector"


def test_docsage_stub_raises_not_implemented():
    engine = DocSageStubEngine()
    with pytest.raises(NotImplementedError):
        asyncio.run(engine.answer(RAGQuery(tenant_id="t1", query_text="anything")))


def test_pageindex_engine_uses_stub_builder_and_retriever_by_default():
    engine = PageIndexEngine()
    answer = asyncio.run(
        engine.answer(RAGQuery(tenant_id="t1", query_text="anything"))
    )
    assert answer.engine_name == "pageindex"
    # Stub builder embeds [STUB] markers in node titles/summaries —
    # retriever propagates those through (production-presentable text
    # format, no tenant_id leak; per P15-S10_REVIEW.md P3 fix).
    assert "[STUB]" in answer.answer
    # tenant_id never appears in user-visible answer text (P3 fix).
    assert "t1" not in answer.answer
    assert len(answer.citations) == 1
    assert answer.citations[0].node_path is not None


def test_router_falls_back_to_pgvector_on_not_implemented():
    """When a query routes to docsage (long multi-entity) the docsage
    stub raises; router catches + answers from pgvector_stub."""
    router = RAGRouter()
    q = RAGQuery(
        tenant_id="t1",
        query_text=(
            "so sánh doanh thu của top 10 customer trong quý vừa rồi với cùng kỳ "
            "năm trước trên tất cả các kênh phân phối quan trọng nhất"
        ),
    )
    answer = asyncio.run(router.answer(q))
    # Routed to docsage, but answer comes from pgvector via fallback
    assert answer.engine_name == "pgvector"


def test_router_fallback_respects_tenant_whitelist():
    """R1 self-review fix — when the routed engine raises and the tenant
    whitelist EXCLUDES pgvector, the router must NOT fall back to pgvector.
    Instead it tries the next allowed engine and ultimately raises if none
    can answer."""
    router = RAGRouter()
    q = RAGQuery(
        tenant_id="t1",
        query_text=(
            "so sánh doanh thu của top 10 customer trong quý vừa rồi với cùng kỳ "
            "năm trước trên tất cả các kênh phân phối quan trọng nhất"
        ),
    )
    # docsage is the natural route + the only whitelisted engine. docsage
    # stub raises NotImplementedError → no other allowed engine → router
    # must raise RAGEngineUnavailable rather than silently using pgvector.
    with pytest.raises(RAGEngineUnavailable):
        asyncio.run(router.answer(q, whitelist=["docsage"]))


def test_router_fallback_picks_next_whitelisted_engine():
    """R1 self-review fix — when the routed engine raises but another
    whitelisted engine is available, the router uses that one (not pgvector
    unconditionally)."""
    router = RAGRouter()
    q = RAGQuery(
        tenant_id="t1",
        query_text=(
            "so sánh doanh thu của top 10 customer trong quý vừa rồi với cùng kỳ "
            "năm trước trên tất cả các kênh phân phối quan trọng nhất"
        ),
    )
    # Whitelist = [docsage, pageindex]. docsage routed → raises → fallback
    # must pick pageindex (next allowed), NOT pgvector (excluded).
    answer = asyncio.run(router.answer(q, whitelist=["docsage", "pageindex"]))
    assert answer.engine_name == "pageindex"


def test_router_dispatches_pgvector_path_end_to_end():
    router = RAGRouter()
    q = RAGQuery(tenant_id="t1", query_text="hello world")
    answer = asyncio.run(router.answer(q))
    assert answer.engine_name == "pgvector"


def test_router_dispatches_pageindex_path_end_to_end():
    router = RAGRouter()
    q = RAGQuery(tenant_id="t1", query_text="điều khoản phạt trong hợp đồng X")
    answer = asyncio.run(router.answer(q))
    assert answer.engine_name == "pageindex"


# ---------------------------------------------------------------------------
# D8 retriever stub — assert tree-walk produces a citation with breadcrumb
# ---------------------------------------------------------------------------


def test_stub_retriever_returns_first_leaf_with_breadcrumb():
    """Retriever takes any tree + returns a citation with node_path
    breadcrumb — enables consumer rendering of "Section A > Section A.1
    > Page 5" without traversing the tree itself."""
    from reasoning.rag.pageindex import StubPageIndexTreeBuilder

    builder = StubPageIndexTreeBuilder()
    tree = asyncio.run(
        builder.build(tenant_id="t1", doc_sha256="h", doc_text="x", doc_kind="pdf")
    )
    retriever = StubPageIndexRetriever()
    answer = asyncio.run(
        retriever.retrieve(query=RAGQuery(tenant_id="t1", query_text="x"), tree=tree)
    )
    assert answer.engine_name == "pageindex"
    assert len(answer.citations) == 1
    cite = answer.citations[0]
    # Breadcrumb is at least 1 element (root → leaf is depth-1 stub tree)
    assert cite.node_path is not None
    assert len(cite.node_path) >= 1
    assert cite.page_range is not None  # stub leaves have page_start/end


def test_pageindex_retriever_is_abstract():
    with pytest.raises(TypeError):
        PageIndexRetriever()  # type: ignore[abstract]


def test_rag_engine_is_abstract():
    """Every engine must subclass RAGEngine; can't instantiate base."""
    with pytest.raises(TypeError):
        RAGEngineBase()  # type: ignore[abstract]
