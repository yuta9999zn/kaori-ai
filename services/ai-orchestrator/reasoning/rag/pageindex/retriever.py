"""
PageIndex retriever — RAG-PAGEINDEX-002 (P15-S10 D8) contract surface.

Phase 1.5 P15-S10. The real implementation traverses the hierarchical
tree via LLM (asks the model "which child best matches the query",
descends to a leaf, returns the leaf's content + page range). This
module ships:

  * Abstract `PageIndexRetriever` base — extracts contract for the
    PageIndex engine wrapper (engines/pageindex_engine.py D6).
  * `StubPageIndexRetriever` — deterministic synthetic retrieval that
    returns the first leaf as a citation. Lets the RAG router (D6)
    test the end-to-end path without an LLM call.

Real upstream traversal lands when the tree builder upstream wrap
lands (D7 follow-up); this module's contract is stable so the swap
is a one-line constructor change in PageIndexEngine.

P15-S11 fix (P3 review item from P15-S10_REVIEW.md):
Stub answer text no longer leaks tenant_id UUID into user-visible
output. tenant_id stays in structured log only. Answer text now
mirrors what a real retriever would produce (leaf summary + page
range citation), so operator inspecting the response sees the
[STUB] markers from StubPageIndexTreeBuilder's node titles/summaries
rather than a "[STUB pageindex]" prefix on the answer itself.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..engines.base import RAGAnswer, RAGCitation, RAGQuery
from .tree_builder import PageIndexNode, PageIndexTree

log = logging.getLogger(__name__)


class PageIndexRetriever(ABC):
    @abstractmethod
    async def retrieve(self, *, query: RAGQuery, tree: PageIndexTree) -> RAGAnswer:
        """Traverse `tree` to answer `query`. MUST set
        RAGAnswer.engine_name='pageindex' so the router's audit log
        attributes correctly."""
        ...


class StubPageIndexRetriever(PageIndexRetriever):
    """Synthetic retriever — returns the first leaf as a citation.

    Answer text mirrors production retriever shape (summary + page
    range). The [STUB] marker is preserved when the tree comes from
    StubPageIndexTreeBuilder (whose node summaries embed [STUB]); when
    FixturePageIndexTreeBuilder is used the answer is fully production-
    presentable.
    """

    async def retrieve(self, *, query: RAGQuery, tree: PageIndexTree) -> RAGAnswer:
        leaf = _first_leaf(tree.root)
        path = _path_to_leaf(tree.root, leaf, [])
        log.debug(
            "stub_pageindex_retrieve",
            extra={
                "tenant_id": tree.tenant_id,
                "doc_sha256": tree.doc_sha256,
                "node_count": _count_nodes(tree.root),
                "leaf_title": leaf.title,
            },
        )
        page_range = leaf.page_range()
        # Production-presentable answer: leaf summary + page-range
        # citation. Tenant identity stays in the structured log above,
        # never in the user-visible text (per P15-S10_REVIEW.md P3).
        if page_range:
            answer_text = f"{leaf.summary} (xem {page_range})"
        else:
            answer_text = leaf.summary
        return RAGAnswer(
            engine_name="pageindex",
            answer=answer_text,
            citations=(
                RAGCitation(
                    engine_name="pageindex",
                    source_id=tree.doc_sha256,
                    node_path=tuple(p.title for p in path) if path else (leaf.title,),
                    page_range=page_range or None,
                ),
            ),
        )


def _first_leaf(node: PageIndexNode) -> PageIndexNode:
    """Depth-first first-leaf — used by the stub retriever to pick a
    deterministic citation target without traversal heuristics."""
    if not node.children:
        return node
    return _first_leaf(node.children[0])


def _path_to_leaf(
    current: PageIndexNode,
    target: PageIndexNode,
    acc: list[PageIndexNode],
) -> list[PageIndexNode]:
    """Build the breadcrumb from root to target leaf for citation
    rendering. Returns an empty list if target not in tree (defensive;
    shouldn't happen given _first_leaf provenance)."""
    if current is target:
        return acc + [current]
    for child in current.children:
        path = _path_to_leaf(child, target, acc + [current])
        if path:
            return path
    return []


def _count_nodes(node: PageIndexNode) -> int:
    """Helper for stub answer text — total node count for context."""
    return 1 + sum(_count_nodes(c) for c in node.children)
