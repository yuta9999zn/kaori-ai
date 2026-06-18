"""
PageIndex — vectorless tree retrieval (P15-S10 D7-D8 + RAG-PAGEINDEX-001/002).

Per ADR-0019 + docs/strategic/RAG_ADDENDUM_2026_05.md, PageIndex is one
of three RAG engines (alongside pgvector and DocSage). Its sweet spot:
deep-dive document QA where the answer is in a specific section + page
range (contracts, policies, technical manuals).

Two deliverables, shipped in order:
  RAG-PAGEINDEX-001 — Tree builder. Given a PDF/Markdown, build a
                       hierarchical Table-of-Contents tree. Cached per
                       (tenant_id, doc_sha256) in pageindex_trees table.
  RAG-PAGEINDEX-002 — Retrieval. Given a query + tree, LLM-traverse to
                       the matching node + return RAGAnswer with
                       page-range citations.

P15-S10 D7 (this commit) ships the contract surface + a deterministic
stub tree_builder.build() so the RAG router (D6) and tests can wire
end-to-end without an LLM call. The real PageIndex wrap (PyPI v0.2.8 —
verified available 2026-05-10) lands when:
  1. LLM credentials are reachable from the test fixture (today the
     llm-gateway path is mocked in unit tests).
  2. A sample PDF/Markdown corpus is available for acceptance.
  3. Migration 045_pageindex_trees lands.

Until then this package returns a synthetic 2-level tree so consumers
can build against the contract.
"""
from __future__ import annotations

from .tree_builder import (
    FixtureNotFoundError,
    FixturePageIndexTreeBuilder,
    PageIndexNode,
    PageIndexTree,
    PageIndexTreeBuilder,
    StubPageIndexTreeBuilder,
    UpstreamPageIndexTreeBuilder,
    UpstreamPageIndexUnavailable,
    node_to_dict,
)

__all__ = [
    "FixtureNotFoundError",
    "FixturePageIndexTreeBuilder",
    "PageIndexNode",
    "PageIndexTree",
    "PageIndexTreeBuilder",
    "StubPageIndexTreeBuilder",
    "UpstreamPageIndexTreeBuilder",
    "UpstreamPageIndexUnavailable",
    "node_to_dict",
]
