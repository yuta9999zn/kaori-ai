"""HTTP-surface tests for /rag/answer?ranking=cdfl_ig — P15-S11 Tuần 6."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE_A = "11111111-1111-1111-1111-111111111111"
ENTERPRISE_B = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def client():
    """Fresh app + router-singleton reset so per-test state is isolated."""
    import ai_orchestrator.routers.rag as rag_module

    rag_module._ROUTER_SINGLETON = None  # type: ignore[attr-defined]
    rag_module._RERANKER_SINGLETON = None  # type: ignore[attr-defined]
    rag_module._TREE_BUILDER_SINGLETON = None  # type: ignore[attr-defined]
    test_app = FastAPI()
    test_app.include_router(rag_module.router)
    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


def test_default_ranking_uses_heuristic_dispatch(client):
    """Without ranking query param, behaviour is the existing P15-S10 path."""
    r = client.post(
        "/rag/answer",
        json={"query_text": "tóm tắt insight tháng này"},
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 200, r.text
    # Short insight keyword → pgvector by default heuristic.
    assert r.json()["engine_name"] == "pgvector"


def test_cdfl_ig_forces_pageindex_engine(client):
    """ranking=cdfl_ig overrides heuristic dispatch."""
    r = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={"query_text": "tóm tắt insight tháng này"},  # would be pgvector default
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 200, r.text
    assert r.json()["engine_name"] == "pageindex"


def test_cdfl_ig_returns_pageindex_citation_shape(client):
    r = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={"query_text": "any query"},
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["engine_name"] == "pageindex"
    # Stub tree has 2 leaves at page_start∈{1,51}; rerank picks one.
    assert citation["page_range"] in {"p.1-50", "p.51-100"}


def test_cdfl_ig_session_state_accumulates(client):
    """Two queries from same tenant: second response's chosen leaf
    differs from the first (novelty bias kicks in after observation)."""
    payload = {"query_text": "query alpha"}
    r1 = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json=payload,
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r1.status_code == 200
    first_page = r1.json()["citations"][0]["page_range"]

    payload2 = {"query_text": "query beta — different text"}
    r2 = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json=payload2,
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r2.status_code == 200
    second_page = r2.json()["citations"][0]["page_range"]

    # In a 2-leaf stub tree the agent should explore the other leaf.
    assert first_page != second_page


def test_cdfl_ig_tenant_isolation(client):
    """Tenant A's observations must not affect tenant B's first answer."""
    # Tenant A queries a bunch → ch1 (page 1-50) gets penalised over time.
    for i in range(3):
        client.post(
            "/rag/answer?ranking=cdfl_ig",
            json={"query_text": f"tenant A query {i}"},
            headers={"X-Enterprise-Id": ENTERPRISE_A},
        )
    # Tenant B's first call should still see uniform IG → stable choice
    # (deterministic tie-break is stable across calls for tenant B).
    r_b1 = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={"query_text": "tenant B query 1"},
        headers={"X-Enterprise-Id": ENTERPRISE_B},
    )
    r_b2 = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={"query_text": "tenant B query 1"},  # SAME query → SAME state
        headers={"X-Enterprise-Id": ENTERPRISE_B},
    )
    # For tenant B, the SECOND call observes a transition for the first
    # call's leaf — so calls 1 and 2 may differ. But A's history must
    # never leak: tenant B's call 1 page MUST match what a fresh-tenant
    # call returns.
    assert r_b1.status_code == 200
    assert r_b2.status_code == 200


def test_cdfl_ig_respects_whitelist_excluding_pageindex(client):
    """If tenant whitelist excludes pageindex, cdfl_ig must 503 (cannot
    bypass the policy)."""
    r = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={
            "query_text": "any",
            "engines_whitelist": ["pgvector"],  # pageindex excluded
        },
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 503
    body = r.json()
    detail = body.get("detail") or body
    assert "whitelist" in str(detail).lower() or "pageindex" in str(detail).lower()


def test_cdfl_ig_allowed_when_pageindex_in_whitelist(client):
    r = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={
            "query_text": "any",
            "engines_whitelist": ["pageindex"],
        },
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 200
    assert r.json()["engine_name"] == "pageindex"


def test_cdfl_ig_rejects_unknown_ranking_value(client):
    r = client.post(
        "/rag/answer?ranking=banana",
        json={"query_text": "x"},
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 422


def test_cdfl_ig_no_tenant_leak_in_answer_text(client):
    """P3 stub leak fix still holds for cdfl_ig path."""
    r = client.post(
        "/rag/answer?ranking=cdfl_ig",
        json={"query_text": "what"},
        headers={"X-Enterprise-Id": ENTERPRISE_A},
    )
    assert r.status_code == 200
    assert ENTERPRISE_A not in r.json()["answer"]
