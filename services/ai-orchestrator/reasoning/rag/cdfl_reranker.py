"""
CDFLRagReranker — P15-S11 Tuần 6 Build Week.

Re-rank PageIndex tree leaves by CDFL information gain instead of
raw first-leaf / similarity. Plugs into `/rag/answer?ranking=cdfl_ig`
to give the agent a "novelty-seeking" reading policy: leaves the
tenant has visited many times in this session lose IG; leaves the
tenant hasn't touched get an exploration bonus.

How it maps to CDFL theory:
- state    = current query token-set fingerprint (string id)
- action   = candidate leaf node (string id, derived from node_path)
- transition (state, action, next_state):
    on each rerank call we observe (query_fp, chosen_leaf_id,
    chosen_leaf_id) — leaf is both action and next_state because in
    a single-step retrieval the agent commits to the leaf it reads.

The same `TransitionModel` from `reasoning/cdfl/` is used directly —
this module is pure plumbing on top, so the CDFL math stays in one
place (transition_model.py + information_gain.py).

Phase 1.5 (Build Week): in-memory per-tenant model, reset on process
restart. No DB persistence. The honest position is that the IG signal
emerges across consecutive queries within a single session; longer-
term learning (cross-session, cross-tenant) is a Phase 2 follow-up
that needs `rag_session_state` Postgres table + replay-from-log.

K-1 tenant isolation: the model is keyed strictly by `tenant_id`. Two
tenants never share state — verified by a unit test that records a
transition for tenant A and asserts tenant B's model is untouched.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Hashable, Iterable

from ..cdfl import IGScorer, TransitionModel
from .engines.base import RAGAnswer, RAGCitation, RAGQuery
from .pageindex.tree_builder import PageIndexNode, PageIndexTree


# ---------------------------------------------------------------------------
# Leaf collection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _LeafRef:
    """Captured information about one leaf for re-ranking.

    `leaf_id` is the canonical identifier we use in the TransitionModel
    (string, deterministic from the title path). The actual node + path
    are kept alongside for citation rendering.
    """

    leaf_id: str
    node: PageIndexNode
    path: tuple[PageIndexNode, ...]


def _collect_leaves(
    node: PageIndexNode, ancestors: tuple[PageIndexNode, ...] = ()
) -> list[_LeafRef]:
    """Depth-first leaf enumeration. A node with no children is a leaf."""
    here = ancestors + (node,)
    if not node.children:
        leaf_id = "|".join(p.title for p in here)
        return [_LeafRef(leaf_id=leaf_id, node=node, path=here)]
    out: list[_LeafRef] = []
    for child in node.children:
        out.extend(_collect_leaves(child, here))
    return out


def _query_fingerprint(query_text: str) -> str:
    """Stable id for a query text — used as the CDFL state.

    SHA-1 prefix of normalised text. Different queries → different
    states (correctly); two phrasings of the same question collide
    only when they normalise identically. Good enough for Phase 1.5.
    """
    normalised = " ".join(query_text.lower().strip().split())
    return "q_" + hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------


@dataclass
class CDFLRagReranker:
    """Stateful re-ranker. One instance keeps a per-tenant
    TransitionModel in memory.

    Usage from the RAG router:

        reranker = CDFLRagReranker()
        ranked = reranker.rerank(tree, query)        # list[ActionScore]
        top = ranked[0]                              # pick the best
        reranker.observe(query, leaf_id=top.leaf_id) # record for next call

    Args:
        uncertainty_weight: forwarded to IGScorer (λ in IG formula).
        max_candidates: cap how many leaves the rerank considers per call
            (defensive — a 10k-leaf tree shouldn't OOM us).
    """

    uncertainty_weight: float = 1.0
    max_candidates: int = 200

    # Per-tenant in-memory state. Key = tenant_id (str).
    _models: dict[str, TransitionModel] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")

    def _get_or_create_model(self, tenant_id: str) -> TransitionModel:
        m = self._models.get(tenant_id)
        if m is None:
            m = TransitionModel()
            self._models[tenant_id] = m
        return m

    def rerank(
        self,
        tree: PageIndexTree,
        query: RAGQuery,
    ) -> list[tuple[_LeafRef, float]]:
        """Return all leaves (capped at max_candidates) ranked descending
        by IG score. Pure read — does NOT mutate the model. Call
        `observe()` after picking a winner to record the transition."""
        leaves = _collect_leaves(tree.root)
        if not leaves:
            return []
        leaves = leaves[: self.max_candidates]
        model = self._models.get(tree.tenant_id)
        scorer = IGScorer(uncertainty_weight=self.uncertainty_weight)
        q_state = _query_fingerprint(query.query_text)

        if model is None:
            # No history yet — every leaf has equal IG (1.0 + 1.0 = 2.0
            # with λ=1). Tie-break stably on insertion order so the
            # result is reproducible.
            return [(leaf, 2.0 * self.uncertainty_weight + 1.0) for leaf in leaves]

        scored: list[tuple[_LeafRef, float]] = []
        for leaf in leaves:
            score = scorer.score(model, q_state, leaf.leaf_id, next_state=leaf.leaf_id)
            scored.append((leaf, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored

    def observe(self, query: RAGQuery, leaf_id: str, tenant_id: str | None = None) -> None:
        """Record (query_fp, leaf_id) → leaf_id transition.

        Subsequent reranks for the same tenant will see lower IG for
        that leaf (uncertainty term drops). For cross-tenant safety we
        require tenant_id explicitly — caller usually passes
        `tree.tenant_id` after picking the top leaf.
        """
        tid = tenant_id if tenant_id is not None else query.tenant_id
        if not tid:
            raise ValueError("tenant_id required for observe()")
        model = self._get_or_create_model(tid)
        q_state = _query_fingerprint(query.query_text)
        model.observe(q_state, leaf_id, leaf_id)

    def reset_tenant(self, tenant_id: str) -> None:
        """Drop any accumulated state for a tenant. Useful for tests +
        future "clear session" UI affordance."""
        self._models.pop(tenant_id, None)

    def tenants_with_state(self) -> set[str]:
        """Read-only view for debug / metrics — which tenants have
        accumulated history."""
        return set(self._models.keys())


# ---------------------------------------------------------------------------
# Convenience: rerank → RAGAnswer with the top leaf as citation
# ---------------------------------------------------------------------------


def rerank_to_answer(
    reranker: CDFLRagReranker,
    tree: PageIndexTree,
    query: RAGQuery,
    *,
    record_observation: bool = True,
) -> RAGAnswer:
    """Wrap rerank() output as a RAGAnswer matching the PageIndex shape.

    The router calls this when `ranking=cdfl_ig` so the response wire
    shape is identical to the default PageIndex retriever — only the
    chosen leaf differs.
    """
    ranked = reranker.rerank(tree, query)
    if not ranked:
        return RAGAnswer(
            engine_name="pageindex",
            answer="(no leaves available to rank)",
            citations=(),
        )
    top_leaf, _top_score = ranked[0]
    if record_observation:
        reranker.observe(query, leaf_id=top_leaf.leaf_id, tenant_id=tree.tenant_id)

    page_range = top_leaf.node.page_range()
    if page_range:
        answer_text = f"{top_leaf.node.summary} (xem {page_range})"
    else:
        answer_text = top_leaf.node.summary
    return RAGAnswer(
        engine_name="pageindex",
        answer=answer_text,
        citations=(
            RAGCitation(
                engine_name="pageindex",
                source_id=tree.doc_sha256,
                node_path=tuple(p.title for p in top_leaf.path),
                page_range=page_range or None,
            ),
        ),
    )
