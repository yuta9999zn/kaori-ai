"""Tests for PageIndex tree builder contract — P15-S10 D7."""
from __future__ import annotations

import asyncio

import pytest

from reasoning.rag.pageindex import (
    PageIndexNode,
    PageIndexTree,
    PageIndexTreeBuilder,
    StubPageIndexTreeBuilder,
)


# ---------------------------------------------------------------------------
# Wire shape contracts
# ---------------------------------------------------------------------------


def test_pageindex_node_page_range_single_page():
    """page_start == page_end → 'p.N' single-page citation."""
    node = PageIndexNode(title="t", summary="s", page_start=5, page_end=5)
    assert node.page_range() == "p.5"


def test_pageindex_node_page_range_multi_page():
    """Different start/end → 'p.A-B' range citation."""
    node = PageIndexNode(title="t", summary="s", page_start=10, page_end=22)
    assert node.page_range() == "p.10-22"


def test_pageindex_node_page_range_no_pages():
    """Markdown source (no page numbers) → empty citation string;
    caller falls back to doc_offset_* for citation."""
    node = PageIndexNode(title="t", summary="s")
    assert node.page_range() == ""


def test_pageindex_tree_cache_key_deterministic():
    """Same (tenant, doc_sha256, schema_version) → same cache_key.
    REL-005 idempotency requires this so a retry hits the same row."""
    root = PageIndexNode(title="r", summary="s")
    t1 = PageIndexTree(tenant_id="t1", doc_sha256="abc", schema_version=1, root=root)
    t2 = PageIndexTree(tenant_id="t1", doc_sha256="abc", schema_version=1, root=root)
    assert t1.cache_key() == t2.cache_key()


def test_pageindex_tree_cache_key_changes_with_tenant():
    """Cross-tenant trees MUST get distinct cache keys (K-1 + K-13)."""
    root = PageIndexNode(title="r", summary="s")
    t1 = PageIndexTree(tenant_id="tenant-a", doc_sha256="abc", schema_version=1, root=root)
    t2 = PageIndexTree(tenant_id="tenant-b", doc_sha256="abc", schema_version=1, root=root)
    assert t1.cache_key() != t2.cache_key()


def test_pageindex_tree_cache_key_changes_with_schema_version():
    """Bumping schema_version invalidates the old cache so consumers
    rebuild against the new shape."""
    root = PageIndexNode(title="r", summary="s")
    t1 = PageIndexTree(tenant_id="t1", doc_sha256="abc", schema_version=1, root=root)
    t2 = PageIndexTree(tenant_id="t1", doc_sha256="abc", schema_version=2, root=root)
    assert t1.cache_key() != t2.cache_key()


# ---------------------------------------------------------------------------
# Stub builder behaviour
# ---------------------------------------------------------------------------


def test_stub_builder_returns_two_child_synthetic_tree():
    """Stub always returns the same 2-child shape so consumers can
    verify they handle the contract without an LLM call."""
    builder = StubPageIndexTreeBuilder()
    tree = asyncio.run(
        builder.build(
            tenant_id="t1",
            doc_sha256="hash1",
            doc_text="hello world",
            doc_kind="pdf",
        )
    )
    assert isinstance(tree, PageIndexTree)
    assert tree.tenant_id == "t1"
    assert tree.doc_sha256 == "hash1"
    assert tree.schema_version == 1
    assert len(tree.root.children) == 2
    assert tree.root.children[0].page_start == 1
    assert tree.root.children[0].page_end == 50
    assert tree.root.children[1].page_start == 51
    assert tree.root.children[1].page_end == 100


def test_stub_builder_marks_synthetic_in_summary():
    """[STUB] marker visible in every node so an operator who sees a
    PageIndex citation containing [STUB] knows the upstream wrap
    hasn't been wired for that tenant yet."""
    builder = StubPageIndexTreeBuilder()
    tree = asyncio.run(
        builder.build(
            tenant_id="t1",
            doc_sha256="h",
            doc_text="x",
            doc_kind="markdown",
        )
    )
    assert "[STUB]" in tree.root.title
    assert "[STUB]" in tree.root.summary
    for child in tree.root.children:
        assert "[STUB]" in child.title


def test_stub_builder_deterministic_for_same_inputs():
    """Same inputs → same tree (cache_key invariant under retry)."""
    builder = StubPageIndexTreeBuilder()
    tree1 = asyncio.run(
        builder.build(tenant_id="t1", doc_sha256="h", doc_text="x", doc_kind="pdf")
    )
    tree2 = asyncio.run(
        builder.build(tenant_id="t1", doc_sha256="h", doc_text="x", doc_kind="pdf")
    )
    assert tree1.cache_key() == tree2.cache_key()


def test_pageindex_tree_builder_is_abstract():
    """ABC contract: PageIndexTreeBuilder cannot be instantiated
    directly; consumers must use Stub or future Upstream impl."""
    with pytest.raises(TypeError):
        PageIndexTreeBuilder()  # type: ignore[abstract]
