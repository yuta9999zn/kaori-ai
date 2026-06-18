"""Tests for ADR-0033 analyze injection (reasoning/knowledge/inject.py):
ground_analysis embeds → foundational search → rank → coverage gate → DB-sourced
preamble, fail-open and bounded; reinforce_cited bumps cited docs.
"""
from uuid import uuid4

import pytest

from ai_orchestrator.reasoning.knowledge import inject as inject_mod
from ai_orchestrator.reasoning.knowledge.inject import ground_analysis, reinforce_cited
from ai_orchestrator.reasoning.knowledge.store import KnowledgeDocument


def _doc(tier, distance, confidence=0.9, source=None, category="rfm"):
    return KnowledgeDocument(title=f"t{tier}", content="c", tier=tier, category=category,
                             source=source, distance=distance, confidence=confidence)


class _Store:
    def __init__(self, docs):
        self._docs = docs
        self.reinforced = []

    async def semantic_search(self, scope, vec, *, top_k=5, **_):
        return self._docs

    async def reinforce_global(self, document_ids):
        self.reinforced.extend(document_ids)
        return len(document_ids)


async def _embed(_text, *, enterprise_id):
    return [0.1, 0.2, 0.3]


# ── ground_analysis ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ground_builds_preamble_from_foundational_docs():
    docs = [_doc(tier=2, distance=0.1, source="rfm.md"), _doc(tier=3, distance=0.2)]
    store = _Store(docs)
    g = await ground_analysis("ent-1", "rfm churn vip", store=store, embed=_embed)
    assert "KIẾN THỨC NỀN" in g["preamble"]
    assert "[rfm.md]" in g["preamble"]          # source cited
    assert g["coverage"] > 0
    assert len(g["cited_ids"]) == 1             # only the foundational (tier 2) doc cited


@pytest.mark.asyncio
async def test_ground_empty_when_no_embedding():
    async def _no_vec(_t, *, enterprise_id):
        return []
    g = await ground_analysis("e", "x", store=_Store([]), embed=_no_vec)
    assert g["preamble"] == "" and g["cited_ids"] == []


@pytest.mark.asyncio
async def test_ground_fails_open_on_store_error():
    class _Boom:
        async def semantic_search(self, *a, **k):
            raise RuntimeError("db down")
    g = await ground_analysis("e", "x", store=_Boom(), embed=_embed)
    assert g == {"preamble": "", "coverage": 0.0, "can_generalize": True, "cited_ids": []}


@pytest.mark.asyncio
async def test_ground_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(inject_mod, "_ENABLED", False)
    g = await ground_analysis("e", "rfm", store=_Store([_doc(2, 0.1)]), embed=_embed)
    assert g["preamble"] == ""


@pytest.mark.asyncio
async def test_ground_empty_when_subject_blank():
    g = await ground_analysis("e", "   ", store=_Store([_doc(2, 0.1)]), embed=_embed)
    assert g["preamble"] == ""


# ── reinforce_cited ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reinforce_cited_counts_updates():
    store = _Store([])
    ids = [uuid4(), uuid4()]
    n = await reinforce_cited("ent-1", ids, store=store)
    assert n == 2 and store.reinforced == ids


@pytest.mark.asyncio
async def test_reinforce_cited_best_effort_on_error():
    class _Boom:
        async def reinforce_global(self, *a, **k):
            raise RuntimeError("admin acquire down")
    n = await reinforce_cited("e", [uuid4()], store=_Boom())
    assert n == 0                                # swallowed, no raise
