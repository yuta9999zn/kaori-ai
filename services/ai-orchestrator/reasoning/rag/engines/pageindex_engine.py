"""
PageIndex engine — wraps reasoning.rag.pageindex tree builder + retriever.

P15-S10 D6 wires the existing D7 StubPageIndexTreeBuilder + D8
StubPageIndexRetriever (this commit) into the RAG router contract.
The upstream PageIndex wrap (PyPI pageindex==0.2.8) lands in a
follow-up sprint; this engine swaps to it transparently when the
underlying tree builder + retriever swap.
"""
from __future__ import annotations

from typing import Optional

from ..pageindex import PageIndexTreeBuilder, StubPageIndexTreeBuilder
from ..pageindex.retriever import (
    PageIndexRetriever,
    StubPageIndexRetriever,
)
from .base import RAGAnswer, RAGEngine, RAGQuery


class PageIndexEngine(RAGEngine):
    """RAG engine using PageIndex hierarchical tree retrieval.

    Constructor accepts a builder + retriever so tests can swap in
    deterministic stubs and the future upstream wrap can land without
    touching this file. Defaults to StubPageIndexTreeBuilder +
    StubPageIndexRetriever so the engine is usable end-to-end on day one.
    """

    engine_name = "pageindex"

    def __init__(
        self,
        *,
        builder: Optional[PageIndexTreeBuilder] = None,
        retriever: Optional[PageIndexRetriever] = None,
    ) -> None:
        self.builder = builder or StubPageIndexTreeBuilder()
        self.retriever = retriever or StubPageIndexRetriever()

    async def answer(self, query: RAGQuery) -> RAGAnswer:
        """Build (or load cached) tree, then retrieve.

        Phase 1.5 stub path: builds a fresh tree per call against an
        empty source doc — fine for routing tests. Real impl loads the
        cached tree from `pageindex_trees` (migration 045) and only
        builds on cache miss.
        """
        tree = await self.builder.build(
            tenant_id=query.tenant_id,
            doc_sha256="[STUB]doc-pageindex-1",
            doc_text="",                       # placeholder; real path loads from MinIO
            doc_kind="pdf",
        )
        return await self.retriever.retrieve(query=query, tree=tree)
