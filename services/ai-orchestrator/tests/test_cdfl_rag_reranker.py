"""Tests for CDFLRagReranker — P15-S11 Tuần 6."""
from __future__ import annotations

import pytest

from reasoning.rag.cdfl_reranker import (
    CDFLRagReranker,
    _collect_leaves,
    _query_fingerprint,
    rerank_to_answer,
)
from reasoning.rag.engines.base import RAGQuery
from reasoning.rag.pageindex import PageIndexNode, PageIndexTree


def _make_tree(tenant_id: str = "t1") -> PageIndexTree:
    """Tree with 3 leaves under 1 root — small enough to reason about."""
    root = PageIndexNode(
        title="root",
        summary="root",
        page_start=1,
        page_end=100,
        children=(
            PageIndexNode(
                title="ch1", summary="ch1 summary", page_start=1, page_end=30
            ),
            PageIndexNode(
                title="ch2", summary="ch2 summary", page_start=31, page_end=60
            ),
            PageIndexNode(
                title="ch3", summary="ch3 summary", page_start=61, page_end=100
            ),
        ),
    )
    return PageIndexTree(
        tenant_id=tenant_id, doc_sha256="hash" + tenant_id, schema_version=1, root=root
    )


def _q(text: str = "what is chapter 2 about?", tenant: str = "t1") -> RAGQuery:
    return RAGQuery(tenant_id=tenant, query_text=text)


def test_collect_leaves_walks_depth_first():
    tree = _make_tree()
    leaves = _collect_leaves(tree.root)
    assert len(leaves) == 3
    assert [leaf.node.title for leaf in leaves] == ["ch1", "ch2", "ch3"]
    # leaf_id includes ancestors for cross-leaf uniqueness.
    assert all(leaf.leaf_id.startswith("root|") for leaf in leaves)


def test_query_fingerprint_normalises():
    fp1 = _query_fingerprint("Hello World")
    fp2 = _query_fingerprint("  hello   world  ")
    fp3 = _query_fingerprint("hello world!")
    assert fp1 == fp2
    assert fp1 != fp3  # punctuation differs (no stripping by design)


def test_rerank_empty_history_returns_uniform_score():
    """First call for a tenant — no history → all leaves equal IG."""
    reranker = CDFLRagReranker()
    tree = _make_tree()
    ranked = reranker.rerank(tree, _q())
    assert len(ranked) == 3
    scores = [s for _, s in ranked]
    # All equal → uniform tie.
    assert len(set(scores)) == 1


def test_observe_then_rerank_demotes_observed_leaf():
    """After observing a leaf, IG for that leaf drops → it ranks lower
    in the next rerank for a different query."""
    reranker = CDFLRagReranker()
    tree = _make_tree()
    q1 = _q("first question")
    ranked_before = reranker.rerank(tree, q1)
    chosen = ranked_before[0][0]
    reranker.observe(q1, leaf_id=chosen.leaf_id, tenant_id=tree.tenant_id)

    # Re-rank for a NEW query — the observed leaf should now have lower
    # IG than the un-observed leaves (uncertainty term shrinks).
    q2 = _q("different question")
    ranked_after = reranker.rerank(tree, q2)
    top_after = ranked_after[0][0]
    # The observed leaf should NOT be top (others have higher uncertainty
    # for the new state q2 as well — though the novelty term penalises
    # only the observed leaf at the next_state position).
    observed_score = next(
        s for leaf, s in ranked_after if leaf.leaf_id == chosen.leaf_id
    )
    unobserved_scores = [
        s for leaf, s in ranked_after if leaf.leaf_id != chosen.leaf_id
    ]
    assert all(u > observed_score for u in unobserved_scores)


def test_tenant_isolation_observe_does_not_leak():
    """K-1: observation on tenant A must not affect tenant B's ranking."""
    reranker = CDFLRagReranker()
    tree_a = _make_tree(tenant_id="t_a")
    tree_b = _make_tree(tenant_id="t_b")

    qa = _q("question", tenant="t_a")
    ranked_a = reranker.rerank(tree_a, qa)
    reranker.observe(qa, leaf_id=ranked_a[0][0].leaf_id, tenant_id="t_a")

    # Tenant B has had no observations — still uniform.
    qb = _q("question", tenant="t_b")
    ranked_b = reranker.rerank(tree_b, qb)
    scores_b = [s for _, s in ranked_b]
    assert len(set(scores_b)) == 1, "tenant B should have uniform scores"


def test_reset_tenant_clears_history():
    reranker = CDFLRagReranker()
    tree = _make_tree()
    q = _q()
    reranker.observe(q, leaf_id=_collect_leaves(tree.root)[0].leaf_id,
                     tenant_id=tree.tenant_id)
    assert tree.tenant_id in reranker.tenants_with_state()
    reranker.reset_tenant(tree.tenant_id)
    assert tree.tenant_id not in reranker.tenants_with_state()


def test_max_candidates_caps_returned_size():
    """Big tree — only `max_candidates` leaves considered."""
    # Build wide tree with 50 children.
    children = tuple(
        PageIndexNode(title=f"ch{i}", summary=f"summary {i}",
                      page_start=i, page_end=i)
        for i in range(50)
    )
    root = PageIndexNode(title="big_root", summary="x", children=children)
    tree = PageIndexTree(tenant_id="t", doc_sha256="h", schema_version=1, root=root)

    reranker = CDFLRagReranker(max_candidates=10)
    ranked = reranker.rerank(tree, _q())
    assert len(ranked) == 10


def test_rerank_to_answer_returns_top_leaf_citation():
    reranker = CDFLRagReranker()
    tree = _make_tree()
    answer = rerank_to_answer(reranker, tree, _q())
    assert answer.engine_name == "pageindex"
    assert len(answer.citations) == 1
    citation = answer.citations[0]
    assert citation.engine_name == "pageindex"
    assert citation.source_id == tree.doc_sha256
    # Top leaf should be one of the three chapters.
    assert citation.page_range in {"p.1-30", "p.31-60", "p.61-100"}


def test_rerank_to_answer_records_observation_by_default():
    reranker = CDFLRagReranker()
    tree = _make_tree()
    q = _q()
    assert tree.tenant_id not in reranker.tenants_with_state()
    rerank_to_answer(reranker, tree, q)
    assert tree.tenant_id in reranker.tenants_with_state()


def test_rerank_to_answer_skips_observation_when_disabled():
    reranker = CDFLRagReranker()
    tree = _make_tree()
    q = _q()
    rerank_to_answer(reranker, tree, q, record_observation=False)
    assert tree.tenant_id not in reranker.tenants_with_state()


def test_observe_requires_tenant_id():
    reranker = CDFLRagReranker()
    # tenant_id default empty in RAGQuery — must explicitly pass.
    bad_q = RAGQuery(tenant_id="", query_text="x")
    with pytest.raises(ValueError, match="tenant_id required"):
        reranker.observe(bad_q, leaf_id="x")


def test_init_validates_max_candidates():
    with pytest.raises(ValueError, match="max_candidates"):
        CDFLRagReranker(max_candidates=0)


def test_session_convergence_top_leaf_changes_over_observations():
    """Demo niche behaviour: after the agent reads leaf X across multiple
    queries, subsequent queries should start favouring un-read leaves
    (novelty-seeking)."""
    reranker = CDFLRagReranker()
    tree = _make_tree()
    # Force the agent to read ch1 in queries 1+2+3.
    for i in range(3):
        q = _q(f"q{i}")
        reranker.observe(q, leaf_id=_collect_leaves(tree.root)[0].leaf_id,
                         tenant_id=tree.tenant_id)
    # New query — ch1 should NOT be top.
    q_new = _q("new question")
    ranked = reranker.rerank(tree, q_new)
    top = ranked[0][0]
    assert top.node.title != "ch1"
