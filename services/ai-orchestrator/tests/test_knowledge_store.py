"""Unit tests for KnowledgeStore (CR-0017) — SQL params + row mapping.

Mocks acquire_for_tenant (same pattern as test_chaos_memory_l3.py) so no live
DB is needed. Asserts the vector encoding, K-20 model pin, and the global+own
visibility query shape.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_orchestrator.reasoning.knowledge.store import (
    KnowledgeDocument, KnowledgeStore, _vec_to_pg,
    kb_confidence_ceiling, kb_reinforced_confidence,
)


def _mock_acquire(*, fetchrow=None, fetch=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])

    @asynccontextmanager
    async def _factory(_tenant_id):
        yield conn

    return _factory, conn


def _search_row(**over):
    base = {
        "document_id": uuid4(), "tenant_id": None, "tier": 2,
        "category": "churn", "title": "Churn benchmark",
        "content": "Khách >90 ngày không mua = nguy cơ rời bỏ.",
        "source": "churn_benchmarks.md", "source_url": None, "lang": "vi",
        "status": "active", "tags": ["churn"], "created_at": None,
        "distance": 0.12,
    }
    base.update(over)
    return base


def test_vec_to_pg_format():
    assert _vec_to_pg([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"
    assert _vec_to_pg([1, 2]) == "[1.0,2.0]"


@pytest.mark.asyncio
async def test_put_binds_vector_model_tier_and_tags():
    doc_id = uuid4()
    tenant = uuid4()
    acquire, conn = _mock_acquire(fetchrow={"document_id": doc_id})
    store = KnowledgeStore(acquire_for_tenant=acquire)

    doc = KnowledgeDocument(
        title="SOP win-back", content="Gọi VIP rời bỏ trong 7 ngày.",
        tier=4, tenant_id=tenant, category="retention", tags=["vip", "win-back"],
    )
    out = await store.put(doc, embedding=[0.1, 0.2, 0.3], scope_tenant_id=tenant)

    assert out == doc_id
    args = conn.fetchrow.call_args.args
    assert "[0.1,0.2,0.3]" in args           # K-20 vector encoded
    assert "bge-m3" in args                   # embedding_model default pinned
    assert 4 in args                          # tier
    assert tenant in args                     # tenant_id bound
    assert '["vip", "win-back"]' in args      # tags json bound


@pytest.mark.asyncio
async def test_put_without_embedding_leaves_model_null():
    acquire, conn = _mock_acquire(fetchrow={"document_id": uuid4()})
    store = KnowledgeStore(acquire_for_tenant=acquire)
    doc = KnowledgeDocument(title="t", content="c", tier=2, tenant_id=None)
    await store.put(doc, scope_tenant_id=None)
    args = conn.fetchrow.call_args.args
    # embedding param + model param are both None when no vector supplied
    assert None in args


@pytest.mark.asyncio
async def test_semantic_search_filters_model_and_maps_distance():
    acquire, conn = _mock_acquire(fetch=[_search_row(), _search_row(distance=0.4)])
    store = KnowledgeStore(acquire_for_tenant=acquire)

    docs = await store.semantic_search(uuid4(), [0.1, 0.2, 0.3], top_k=3)

    assert len(docs) == 2
    assert docs[0].distance == 0.12
    assert docs[0].tier == 2
    assert docs[0].tenant_id is None          # global row
    args = conn.fetch.call_args.args
    assert "[0.1,0.2,0.3]" in args            # query vector encoded
    assert "bge-m3" in args                   # K-20 model filter


@pytest.mark.asyncio
async def test_list_documents_maps_rows_without_distance():
    row = _search_row()
    del row["distance"]
    acquire, conn = _mock_acquire(fetch=[row])
    store = KnowledgeStore(acquire_for_tenant=acquire)
    docs = await store.list_documents(uuid4(), category="churn")
    assert len(docs) == 1
    assert docs[0].distance is None
    assert docs[0].category == "churn"


@pytest.mark.asyncio
async def test_set_embedding_returns_true_when_row_updated():
    acquire, conn = _mock_acquire(fetchrow={"document_id": uuid4()})
    store = KnowledgeStore(acquire_for_tenant=acquire)
    ok = await store.set_embedding(None, uuid4(), [0.1, 0.2, 0.3])
    assert ok is True
    args = conn.fetchrow.call_args.args
    assert "[0.1,0.2,0.3]" in args


# ─── ADR-0033: aging (maturation curve) ──────────────────────────────────────

def test_kb_confidence_ceiling_tiers():
    # regulatory > curated > market >= tenant; unknown tier → default
    assert kb_confidence_ceiling(1) > kb_confidence_ceiling(2) > kb_confidence_ceiling(3)
    assert kb_confidence_ceiling(3) >= kb_confidence_ceiling(4)
    assert kb_confidence_ceiling(99) == 0.80


def test_kb_reinforced_confidence_curve_diminishes():
    c1 = kb_reinforced_confidence(2, 0.5)
    c2 = kb_reinforced_confidence(2, c1)
    assert 0.5 < c1 < c2 <= kb_confidence_ceiling(2)
    assert (c1 - 0.5) > (c2 - c1)            # each citation adds less


def test_kb_reinforced_never_exceeds_ceiling():
    c = 0.5
    for _ in range(200):
        c = kb_reinforced_confidence(3, c)
    assert c <= kb_confidence_ceiling(3)


@pytest.mark.asyncio
async def test_reinforce_issues_update_and_returns_true():
    acquire, conn = _mock_acquire(fetchrow={"document_id": uuid4()})
    store = KnowledgeStore(acquire_for_tenant=acquire)
    ok = await store.reinforce(None, uuid4())
    assert ok is True
    sql = conn.fetchrow.call_args.args[0]
    assert "confidence" in sql and "use_count" in sql and "last_reinforced_at" in sql


# ─── ADR-0033: version history (supersede + walk) ────────────────────────────

@pytest.mark.asyncio
async def test_supersede_lands_new_and_archives_old():
    new_id, old_id = uuid4(), uuid4()
    acquire, conn = _mock_acquire(fetchrow={"document_id": new_id})
    store = KnowledgeStore(acquire_for_tenant=acquire)
    new_doc = KnowledgeDocument(title="churn 90d", content="...", tier=3, category="churn")
    out = await store.supersede(None, old_id, new_doc, change_reason="2026 benchmark refresh")
    assert out == new_id
    assert new_doc.supersedes == old_id and new_doc.status == "active"
    assert new_doc.change_reason == "2026 benchmark refresh"
    exec_sql = conn.execute.call_args.args[0]
    assert "archived" in exec_sql and "superseded_by" in exec_sql
    assert old_id in conn.execute.call_args.args and new_id in conn.execute.call_args.args


@pytest.mark.asyncio
async def test_version_history_walks_chain_newest_to_oldest():
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock as _AM
    v1_id, v2_id = uuid4(), uuid4()
    v2 = _search_row(document_id=v2_id, content="churn 90d", supersedes=v1_id, superseded_by=None)
    del v2["distance"]
    v1 = _search_row(document_id=v1_id, content="churn 120d", supersedes=None,
                     superseded_by=v2_id, change_reason="initial benchmark")
    del v1["distance"]
    conn = _AM()
    conn.fetchrow = _AM(side_effect=[v2, v1])

    @asynccontextmanager
    async def acquire(_t):
        yield conn

    store = KnowledgeStore(acquire_for_tenant=acquire)
    chain = await store.version_history(None, v2_id)
    assert [d.document_id for d in chain] == [v2_id, v1_id]      # newest → oldest
    assert chain[0].content == "churn 90d" and chain[1].content == "churn 120d"
    assert chain[1].change_reason == "initial benchmark"


# ─── ADR-0033: global-foundational maturation (admin context) ────────────────

@pytest.mark.asyncio
async def test_reinforce_global_scopes_to_global_rows():
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock as _AM
    conn = _AM()
    conn.fetch = _AM(return_value=[{"document_id": uuid4()}, {"document_id": uuid4()}])

    @asynccontextmanager
    async def admin_acquire():            # no enterprise_id arg — cross-tenant
        yield conn

    store = KnowledgeStore(acquire_for_tenant=lambda *a: None, acquire_admin=admin_acquire)
    n = await store.reinforce_global([uuid4(), uuid4()])
    assert n == 2
    sql = conn.fetch.call_args.args[0]
    assert "tenant_id IS NULL" in sql          # NEVER touches tenant data
    assert "use_count" in sql and "confidence" in sql


@pytest.mark.asyncio
async def test_reinforce_global_empty_is_noop():
    store = KnowledgeStore(acquire_for_tenant=lambda *a: None)
    assert await store.reinforce_global([]) == 0


def test_ceiling_case_sql_single_source_from_dict():
    # Hardcode audit: SQL ceilings are GENERATED from _KB_CONF_CEILING, not a
    # duplicated literal — change the dict and the SQL follows.
    from ai_orchestrator.reasoning.knowledge.store import _ceiling_case_sql, _KB_CONF_CEILING
    sql = _ceiling_case_sql("tier")
    assert sql.startswith("CASE tier ") and "ELSE" in sql
    for t, c in _KB_CONF_CEILING.items():
        assert f"WHEN {t} THEN {c}" in sql
