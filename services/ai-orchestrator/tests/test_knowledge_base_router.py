"""HTTP-surface tests for the Knowledge Base router (CR-0017).

Monkeypatches the router-module-level acquire_for_tenant + embed_text so no
live DB or llm-gateway is needed (mirrors test_rag_endpoint.py + the
acquire-mock pattern from test_chaos_memory_l3.py).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ai_orchestrator.routers.knowledge_base as kb

EID = "11111111-1111-1111-1111-111111111111"


def _wire(monkeypatch, *, fetchrow=None, fetch=None, embed=(0.1, 0.2, 0.3), embed_exc=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])

    @asynccontextmanager
    async def _acquire(_tenant_id):
        yield conn

    async def _embed(text, *, enterprise_id):
        if embed_exc is not None:
            raise embed_exc
        return list(embed) if embed is not None else []

    monkeypatch.setattr(kb, "acquire_for_tenant", _acquire)
    monkeypatch.setattr(kb, "embed_text", _embed)

    app = FastAPI()
    app.include_router(kb.router)
    return TestClient(app, raise_server_exceptions=True), conn


def _search_row(**over):
    base = {
        "document_id": uuid4(), "tenant_id": None, "tier": 2, "category": "churn",
        "title": "Churn benchmark", "content": "Khách >90 ngày = nguy cơ rời bỏ.",
        "source": "churn_benchmarks.md", "source_url": None, "lang": "vi",
        "status": "active", "tags": ["churn"], "created_at": None, "distance": 0.1,
    }
    base.update(over)
    return base


def test_ingest_forces_tier4_and_tenant_scope(monkeypatch):
    doc_id = uuid4()
    client, conn = _wire(monkeypatch, fetchrow={"document_id": doc_id})
    r = client.post(
        "/knowledge-base/documents",
        headers={"X-Enterprise-ID": EID},
        json={"title": "SOP win-back", "content": "Gọi VIP trong 7 ngày", "category": "retention"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["document_id"] == str(doc_id)
    assert body["status"] == "active"
    # INSERT bound: tier forced to 4, tenant_id = caller enterprise.
    args = conn.fetchrow.call_args.args
    assert 4 in args
    assert str([a for a in args if str(a) == EID][0]) == EID


def test_search_returns_results_with_similarity_and_scope(monkeypatch):
    client, conn = _wire(monkeypatch, fetch=[_search_row(), _search_row(distance=0.3)])
    r = client.post(
        "/knowledge-base/search",
        headers={"X-Enterprise-ID": EID},
        json={"query": "dấu hiệu churn", "top_k": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "dấu hiệu churn"
    assert len(body["results"]) == 2
    top = body["results"][0]
    assert top["scope"] == "global"          # tenant_id None
    assert top["tier"] == 2
    assert top["similarity"] == pytest.approx(0.9, abs=1e-6)   # 1 - 0.1
    assert top["snippet"] and top["snippet"].startswith("Khách >90 ngày")  # content surfaced


def test_list_documents_ok(monkeypatch):
    row = _search_row()
    del row["distance"]
    client, _ = _wire(monkeypatch, fetch=[row])
    r = client.get("/knowledge-base/documents", headers={"X-Enterprise-ID": EID})
    assert r.status_code == 200
    docs = r.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["similarity"] is None     # list has no distance


def test_bad_enterprise_id_returns_400(monkeypatch):
    client, _ = _wire(monkeypatch, fetch=[])
    r = client.post(
        "/knowledge-base/search",
        headers={"X-Enterprise-ID": "not-a-uuid"},
        json={"query": "x"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["errcode"] == "USR-ERR4"


def test_embed_outage_returns_503(monkeypatch):
    client, _ = _wire(monkeypatch, fetch=[], embed_exc=RuntimeError("gateway down"))
    r = client.post(
        "/knowledge-base/search",
        headers={"X-Enterprise-ID": EID},
        json={"query": "x"},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["errcode"] == "SVC-ERR3"


def test_empty_vector_returns_503(monkeypatch):
    client, _ = _wire(monkeypatch, fetchrow={"document_id": uuid4()}, embed=[])
    r = client.post(
        "/knowledge-base/documents",
        headers={"X-Enterprise-ID": EID},
        json={"title": "t", "content": "c"},
    )
    assert r.status_code == 503
