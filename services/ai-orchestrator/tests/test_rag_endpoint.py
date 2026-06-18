"""
P15-S10 D6 — HTTP-surface tests for /rag/answer.

Pure TestClient — RAGRouter defaults to stub engines so no LLM / DB
required. Confirms request→response wire shape + tenant header parsing
+ R1 whitelist behaviour at the HTTP boundary.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-Id": ENTERPRISE}


@pytest.fixture
def client():
    """Mount the router on a fresh app — singleton router cache is
    cleared between tests so engine substitutions don't leak."""
    import ai_orchestrator.routers.rag as rag_module
    rag_module._ROUTER_SINGLETON = None  # type: ignore[attr-defined]
    test_app = FastAPI()
    test_app.include_router(rag_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def test_pgvector_default_path_short_query(client):
    """Default routing → pgvector stub returns a synthetic answer."""
    resp = client.post(
        "/rag/answer",
        headers=HEADERS,
        json={"query_text": "tóm tắt insight tháng này"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["engine_name"] == "pgvector"
    assert isinstance(body["answer"], str) and len(body["answer"]) > 0
    assert isinstance(body["citations"], list)


def test_doc_citation_query_routes_to_pageindex(client):
    """'điều khoản' keyword → pageindex engine (R1 fix path)."""
    resp = client.post(
        "/rag/answer",
        headers=HEADERS,
        json={"query_text": "điều khoản phạt trong hợp đồng?"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["engine_name"] == "pageindex"


def test_tenant_whitelist_excludes_unavailable_engine_503(client):
    """Whitelist = ['docsage'] only; DocSage is stub → 503 instead of
    silently falling back to pgvector (R1 fix at HTTP level)."""
    resp = client.post(
        "/rag/answer",
        headers=HEADERS,
        json={
            "query_text": "tóm tắt",
            "engines_whitelist": ["docsage"],
        },
    )
    assert resp.status_code == 503
    body = resp.json()
    # FastAPI envelopes the dict detail under "detail"
    detail = body.get("detail", body)
    assert detail.get("errcode") == "BIZ-ERR1"


def test_missing_tenant_header_422(client):
    """X-Enterprise-Id is required — FastAPI returns 422 when missing."""
    resp = client.post(
        "/rag/answer",
        json={"query_text": "tóm tắt"},
    )
    assert resp.status_code == 422


def test_bad_uuid_tenant_header_400(client):
    """Malformed UUID → RFC 7807 400 with USR-ERR4 errcode."""
    resp = client.post(
        "/rag/answer",
        headers={"X-Enterprise-Id": "not-a-uuid"},
        json={"query_text": "tóm tắt"},
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", {})
    assert detail.get("errcode") == "USR-ERR4"


def test_empty_query_text_422(client):
    """Validation: query_text min_length=1."""
    resp = client.post(
        "/rag/answer",
        headers=HEADERS,
        json={"query_text": ""},
    )
    assert resp.status_code == 422
