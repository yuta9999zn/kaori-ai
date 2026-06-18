"""Tests for the pgvector real engine + cosine helper.

Mocks httpx for both /v1/embed and /v1/infer calls. Overrides
`_load_corpus` to bypass Postgres.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest

from ai_orchestrator.reasoning.rag.engines import RAGQuery
from ai_orchestrator.reasoning.rag.engines.pgvector_real import (
    PgVectorRealEngine,
    _cosine,
)


# ─── Cosine ─────────────────────────────────────────────────────────


class TestCosine:

    def test_identical_vectors_returns_1(self):
        assert _cosine([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_returns_0(self):
        assert _cosine([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors_returns_minus_1(self):
        assert _cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_empty_returns_0(self):
        assert _cosine([], [1, 2, 3]) == 0.0
        assert _cosine([1, 2, 3], []) == 0.0

    def test_zero_vector_returns_0(self):
        assert _cosine([0, 0, 0], [1, 1, 1]) == 0.0


# ─── PgVectorRealEngine.answer() ────────────────────────────────────


ENT = "11111111-1111-1111-1111-111111111111"


def _embed_response(vec: list[float]):
    """Build a mock httpx response for /v1/embed."""
    resp = MagicMock()
    resp.json = MagicMock(return_value={"vector": vec, "dim": len(vec),
                                          "model_used": "bge-m3", "latency_ms": 5})
    resp.raise_for_status = MagicMock()
    return resp


def _infer_response(text: str):
    resp = MagicMock()
    resp.json = MagicMock(return_value={"completion": text, "model_used": "qwen2.5:14b",
                                          "method": "internal", "cache_hit": False,
                                          "tokens": {"prompt_chars": 0, "completion_chars": len(text)},
                                          "latency_ms": 10})
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_answer_happy_path():
    eng = PgVectorRealEngine(db_pool=None)
    # Override corpus loader to provide 3 docs.
    eng._load_corpus = AsyncMock(return_value=[
        ("doc-A", "Doanh thu quý 1 chi nhánh Hà Nội: 100 triệu."),
        ("doc-B", "Tổng kết quý: lợi nhuận sau thuế 20 triệu, EBITDA 25 triệu."),
        ("doc-C", "Chính sách nhân sự 2026 — quy trình tuyển dụng."),
    ])

    # Mock httpx — 1 query embed + 3 doc embeds + 1 synthesis call.
    call_log: list[str] = []

    async def _fake_post(url, json):
        call_log.append(url)
        if url.endswith("/v1/embed"):
            text = json.get("text") or ""
            # Make the relevant doc most similar to query: same vector.
            if "Doanh thu" in text or "doanh thu" in (json.get("text") or "").lower():
                return _embed_response([1.0, 0.0, 0.0])
            if "Tổng kết" in text:
                return _embed_response([0.0, 1.0, 0.0])
            if "Chính sách" in text:
                return _embed_response([0.0, 0.0, 1.0])
            # query text
            return _embed_response([1.0, 0.0, 0.0])
        if url.endswith("/v1/infer"):
            return _infer_response("Doanh thu quý 1 đạt 100 triệu [doc 1].")
        raise AssertionError(f"unexpected URL {url}")

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        ans = await eng.answer(RAGQuery(tenant_id=ENT,
                                         query_text="Doanh thu quý 1 ra sao?",
                                         max_citations=2))

    assert ans.engine_name == "pgvector"
    assert "Doanh thu" in ans.answer
    assert len(ans.citations) == 2
    # Top citation should be doc-A (perfect cosine match).
    assert ans.citations[0].source_id == "doc-A"
    assert ans.citations[0].similarity == pytest.approx(1.0, abs=1e-4)
    # 1 query embed + 3 doc embeds + 1 synth = 5 calls
    assert len(call_log) == 5


@pytest.mark.asyncio
async def test_empty_corpus_returns_friendly_message():
    eng = PgVectorRealEngine(db_pool=None)
    eng._load_corpus = AsyncMock(return_value=[])
    ans = await eng.answer(RAGQuery(tenant_id=ENT, query_text="x"))
    assert "Chưa có tài liệu" in ans.answer
    assert ans.citations == ()


@pytest.mark.asyncio
async def test_query_embed_failure_returns_friendly_message():
    eng = PgVectorRealEngine(db_pool=None)
    eng._load_corpus = AsyncMock(return_value=[("doc-A", "text")])

    client = AsyncMock()
    client.post = AsyncMock(side_effect=httpx.HTTPError("embed down"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        ans = await eng.answer(RAGQuery(tenant_id=ENT, query_text="x"))
    assert "Không embed" in ans.answer


@pytest.mark.asyncio
async def test_doc_embed_failures_dont_abort_batch():
    """If some doc embeds fail, the engine should still answer using the
    successful ones. Robust degradation > all-or-nothing."""
    eng = PgVectorRealEngine(db_pool=None)
    eng._load_corpus = AsyncMock(return_value=[
        ("doc-A", "text A"),
        ("doc-B", "text B"),
    ])

    call_count = {"n": 0}

    async def _fake_post(url, json):
        call_count["n"] += 1
        if url.endswith("/v1/embed"):
            # Calls: query (1), doc-A (2 → fail), doc-B (3 → ok)
            if call_count["n"] == 1:
                return _embed_response([1.0, 0.0])
            if call_count["n"] == 2:
                raise httpx.HTTPError("doc-A embed fail")
            return _embed_response([1.0, 0.0])
        if url.endswith("/v1/infer"):
            return _infer_response("Answer [doc 1].")
        raise AssertionError(url)

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        ans = await eng.answer(RAGQuery(tenant_id=ENT, query_text="q"))
    # Only doc-B survived; one citation.
    assert len(ans.citations) == 1
    assert ans.citations[0].source_id == "doc-B"


@pytest.mark.asyncio
async def test_synthesis_failure_falls_back_to_doc_id_listing():
    eng = PgVectorRealEngine(db_pool=None)
    eng._load_corpus = AsyncMock(return_value=[("doc-A", "text A")])

    async def _fake_post(url, json):
        if url.endswith("/v1/embed"):
            return _embed_response([1.0, 0.0])
        if url.endswith("/v1/infer"):
            raise httpx.HTTPError("Qwen busy")
        raise AssertionError(url)

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        ans = await eng.answer(RAGQuery(tenant_id=ENT, query_text="q"))
    # Fallback answer mentions the doc IDs so the manager can read them.
    assert "doc-A" in ans.answer
    assert len(ans.citations) == 1


@pytest.mark.asyncio
async def test_calls_use_consent_external_false():
    """K-4 invariant: synth call must default consent_external=False."""
    eng = PgVectorRealEngine(db_pool=None)
    eng._load_corpus = AsyncMock(return_value=[("doc-A", "text")])

    posted_bodies: list[dict] = []

    async def _fake_post(url, json):
        posted_bodies.append({"url": url, "body": json})
        if url.endswith("/v1/embed"):
            return _embed_response([1.0, 0.0])
        if url.endswith("/v1/infer"):
            return _infer_response("Answer.")
        raise AssertionError(url)

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        await eng.answer(RAGQuery(tenant_id=ENT, query_text="q"))

    infer_calls = [b for b in posted_bodies if b["url"].endswith("/v1/infer")]
    assert infer_calls, "no /v1/infer call observed"
    assert all(b["body"]["consent_external"] is False for b in infer_calls)


# ─── CR-0017: domain knowledge blended into RAG answer ──────────────


@pytest.mark.asyncio
async def test_knowledge_blends_into_citations():
    """A curated knowledge row competes with the doc corpus and, when more
    relevant, tops the citations (source_id prefixed kb:)."""
    eng = PgVectorRealEngine(db_pool=object())          # non-None → KB reachable
    eng._load_corpus = AsyncMock(return_value=[("doc-A", "nội dung không liên quan")])
    eng._load_knowledge = AsyncMock(return_value=[
        ("kb:k1", "[tri thức ngành · churn_benchmarks.md] Churn: >90 ngày = nguy cơ.", 0.99),
    ])

    async def _fake_post(url, json):
        if url.endswith("/v1/embed"):
            text = json.get("text") or ""
            # query = [1,0]; doc-A orthogonal [0,1] → cosine 0 < kb 0.99
            return _embed_response([1.0, 0.0] if "?" in text or "churn" in text.lower()
                                   else [0.0, 1.0])
        if url.endswith("/v1/infer"):
            return _infer_response("Khách >90 ngày là nguy cơ rời bỏ [doc 1].")
        raise AssertionError(url)

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        ans = await eng.answer(RAGQuery(tenant_id=ENT,
                                         query_text="dấu hiệu churn?", max_citations=2))

    ids = [c.source_id for c in ans.citations]
    assert "kb:k1" in ids
    assert ans.citations[0].source_id == "kb:k1"        # knowledge ranked top
    assert ans.citations[0].similarity == pytest.approx(0.99, abs=1e-4)


@pytest.mark.asyncio
async def test_knowledge_answers_even_with_empty_doc_corpus():
    """A tenant who uploaded nothing still gets a knowledge-grounded answer."""
    eng = PgVectorRealEngine(db_pool=object())
    eng._load_corpus = AsyncMock(return_value=[])        # no uploaded docs
    eng._load_knowledge = AsyncMock(return_value=[
        ("kb:k7", "[tri thức ngành · rfm_segmentation.md] RFM: ...", 0.88),
    ])

    async def _fake_post(url, json):
        if url.endswith("/v1/embed"):
            return _embed_response([1.0, 0.0, 0.0])
        if url.endswith("/v1/infer"):
            return _infer_response("Phân khúc RFM gồm Recency, Frequency, Monetary [doc 1].")
        raise AssertionError(url)

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        ans = await eng.answer(RAGQuery(tenant_id=ENT, query_text="RFM là gì?"))

    assert ans.engine_name == "pgvector"
    assert len(ans.citations) == 1
    assert ans.citations[0].source_id == "kb:k7"


@pytest.mark.asyncio
async def test_load_knowledge_empty_without_pool():
    eng = PgVectorRealEngine(db_pool=None)
    out = await eng._load_knowledge(UUID(ENT), [1.0, 0.0], top_k=5)
    assert out == []


@pytest.mark.asyncio
async def test_corpus_cap_read_from_config(monkeypatch):
    """CR-0019 — answer() reads rag_max_corpus_docs and passes it as the limit."""
    import ai_orchestrator.shared.ai_config as cfg
    async def fake_int(key, default):
        return 7 if key == "rag_max_corpus_docs" else default
    monkeypatch.setattr(cfg, "get_int", fake_int)

    eng = PgVectorRealEngine(db_pool=None)
    captured: dict = {}
    async def fake_load(tenant_uuid, *, limit=50):
        captured["limit"] = limit
        return [("doc-A", "text A")]
    eng._load_corpus = fake_load
    eng._load_knowledge = AsyncMock(return_value=[])

    async def _fake_post(url, json):
        if url.endswith("/v1/embed"):
            return _embed_response([1.0, 0.0])
        if url.endswith("/v1/infer"):
            return _infer_response("ok [doc 1].")
        raise AssertionError(url)

    client = AsyncMock()
    client.post = _fake_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("ai_orchestrator.reasoning.rag.engines.pgvector_real.httpx.AsyncClient",
                return_value=client):
        await eng.answer(RAGQuery(tenant_id=ENT, query_text="q"))

    assert captured["limit"] == 7
