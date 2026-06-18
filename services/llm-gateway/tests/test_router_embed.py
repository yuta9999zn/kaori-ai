"""Tests for POST /v1/embed (P15-S11 pgvector real impl).

Mocks providers.embed_text; no Ollama running. Validates:
  * happy path returns vector + dim + model_used + latency_ms
  * provider failure → 502
  * empty text → empty vector + dim=0 (preserves K-4 short-circuit)
  * K-4 invariant: endpoint has no consent_external param at all
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import router as v1_router


@pytest.fixture(autouse=True)
def _stub_pool_and_governance():
    """Phase 2.7 P3: /v1/embed now writes ai_decision_audit via the
    pool — these tests have no live pool, so stub both the pool
    accessor and the gov writer for every test in this module."""
    from unittest.mock import MagicMock
    with patch("llm_gateway.router.get_pool", return_value=MagicMock()), \
         patch("llm_gateway.router.ai_governance.record_ai_call",
                new=AsyncMock(return_value=None)):
        yield


@pytest.fixture
def client():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
    return TestClient(app)


def _body(text: str = "Doanh thu quý 1") -> dict:
    return {"text": text, "enterprise_id": str(uuid4())}


# ─── Happy path ─────────────────────────────────────────────────────


def test_embed_happy_path(client):
    fake_vec = [0.1, 0.2, 0.3, 0.4]
    with patch("llm_gateway.providers.embed_text",
                new=AsyncMock(return_value=fake_vec)):
        r = client.post("/v1/embed", json=_body())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vector"] == fake_vec
    assert body["dim"] == 4
    assert "model_used" in body
    assert body["latency_ms"] >= 0


def test_embed_empty_text_returns_empty_vector(client):
    """Provider short-circuits empty text to []. Endpoint preserves
    that — dim=0 signals the caller to skip / use a sentinel."""
    with patch("llm_gateway.providers.embed_text",
                new=AsyncMock(return_value=[])):
        r = client.post("/v1/embed", json={"text": "", "enterprise_id": str(uuid4())})
    assert r.status_code == 200
    body = r.json()
    assert body["vector"] == []
    assert body["dim"] == 0


# ─── Failure path ───────────────────────────────────────────────────


def test_embed_provider_failure_returns_502(client):
    with patch("llm_gateway.providers.embed_text",
                new=AsyncMock(side_effect=RuntimeError("Ollama 500"))):
        r = client.post("/v1/embed", json=_body())
    assert r.status_code == 502
    # RFC 7807 — Content-Type problem+json or JSON
    assert "embedding" in r.text.lower() or "upstream" in r.text.lower()


# ─── Validation ─────────────────────────────────────────────────────


def test_embed_missing_enterprise_id_rejects(client):
    r = client.post("/v1/embed", json={"text": "x"})
    assert r.status_code == 422


def test_embed_text_too_long_rejects(client):
    """Cap at 8000 chars (BGE-M3 context-friendly)."""
    r = client.post("/v1/embed", json={"text": "x" * 9000,
                                          "enterprise_id": str(uuid4())})
    assert r.status_code == 422


# ─── K-4 invariant ──────────────────────────────────────────────────


def test_embed_request_has_no_consent_external_field():
    """Embedding endpoint MUST not accept consent_external — the K-4
    invariant for this path is enforced by the schema itself, not by
    runtime checks. A future contributor who adds the field will fail
    this test before the regression lands."""
    from llm_gateway.models import EmbedRequest
    fields = set(EmbedRequest.model_fields.keys())
    assert "consent_external" not in fields, \
        "EmbedRequest must not accept consent_external — embeddings are always local (K-4)."
    assert "prefer_external" not in fields
