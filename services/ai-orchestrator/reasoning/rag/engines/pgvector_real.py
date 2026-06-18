"""
pgvector engine — REAL implementation (P15-S11 task #11).

Replaces the P15-S10 D6 stub (`pgvector_stub.py`). Wires the existing
docsage_text-bearing rows in `bronze_files` as the corpus, embeds query
+ doc text via the llm-gateway BGE-M3 endpoint, and returns the top-K
by cosine similarity.

Why this lands now
------------------
- The pgvector store was speced at P1-S5 but never wired to a live
  embedding endpoint — `/v1/embed` lands in the same P15-S11 batch.
- Stage 6 D2 (commit `xxx`) populated `bronze_files.metadata.docsage_text`
  for PDF/DOCX uploads, so a real corpus exists in every Kaori tenant
  the moment they upload a doc.
- Without this, the router falls back to the stub for ~80% of queries
  (default route is pgvector) — engineering-wise the router has been
  shipping placeholder answers.

Scope (P15-S11 stage)
---------------------
- In-memory cosine similarity over the docsage_text corpus.
- Embeddings are CACHED in `bronze_file_embeddings` (mig 133) — embed-once,
  write-through, keyed by the immutable file_id (K-2). The first query for a
  doc embeds + stores it; subsequent queries reuse the stored vector.
- LLM synthesis of the answer text: we call llm-gateway /v1/infer with
  the retrieved snippets concatenated as context, instructing Qwen to
  answer in Vietnamese with [doc N] citations.

K-3 / K-4 compliance
--------------------
- All HTTP calls go to llm-gateway (no direct Ollama or vendor SDK).
- Embedding endpoint enforces K-4 by design (always local; no consent
  parameter); the synthesis call default consent_external=False (Qwen).
- Per K-19 the gateway emits a span around its `/v1/infer` and
  `/v1/embed` handlers; this module inherits.

Cost guard rail
---------------
- MAX_CORPUS_DOCS = 50 (slightly larger than DocSage's 20 since
  pgvector synthesis is cheaper than DocSage's 4-LLM-call pipeline).
- Per-query LLM cost: 1 embedding call + N doc embedding calls +
  1 synthesis call. For N=20 on Qwen local ~ 10 sec total.
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Optional
from uuid import UUID

import httpx
import structlog

from .base import RAGAnswer, RAGCitation, RAGEngine, RAGQuery

log = structlog.get_logger()


LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")
MAX_CORPUS_DOCS = 50
EMBED_TIMEOUT_S = 30.0
INFER_TIMEOUT_S = 120.0


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Returns 0 when either vector is empty / zero-norm."""
    if not a or not b:
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class PgVectorRealEngine(RAGEngine):
    engine_name = "pgvector"

    def __init__(self, *, db_pool=None, gateway_url: Optional[str] = None):
        self.db_pool = db_pool
        self.gateway_url = gateway_url or LLM_GATEWAY_URL

    async def answer(self, query: RAGQuery) -> RAGAnswer:
        t0 = time.monotonic()
        tenant_uuid = UUID(query.tenant_id)

        # 1 — load the tenant's own document corpus (bronze docsage_text).
        # CR-0019 — corpus cap is a platform-admin knob (fall back to the const).
        from ai_orchestrator.shared import ai_config  # noqa: E402
        max_docs = await ai_config.get_int("rag_max_corpus_docs", MAX_CORPUS_DOCS)
        corpus = await self._load_corpus(tenant_uuid, limit=max_docs)
        # The knowledge base is only reachable with a live db_pool. When there
        # is neither a document corpus NOR a reachable KB, bail early before
        # spending an embed call.
        if not corpus and self.db_pool is None:
            return RAGAnswer(
                engine_name=self.engine_name,
                answer=(
                    "Chưa có tài liệu để tìm kiếm — upload file PDF/DOCX hoặc "
                    "đợi pipeline xử lý xong rồi thử lại."
                ),
                citations=(),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 2 — embed query (used for BOTH the doc corpus and the KB <=> search)
        try:
            query_vec = await self._embed(query.query_text, tenant_id=query.tenant_id)
        except Exception as e:
            log.warning("pgvector.embed.query_failed", error=str(e))
            return RAGAnswer(
                engine_name=self.engine_name,
                answer="Không embed được câu hỏi. Vui lòng thử lại.",
                citations=(),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 3 — score the document corpus. Embeddings are CACHED (mig 133
        # bronze_file_embeddings): embed-once, then reuse — no more re-embed
        # per query. Cache is keyed by file_id (immutable, K-2).
        cached = await self._load_cached_embeddings(
            tenant_uuid, [doc_id for doc_id, _ in corpus])
        scored: list[tuple[str, str, float]] = []  # (source_id, snippet, score)
        for doc_id, text in corpus:
            doc_vec = cached.get(doc_id)
            if doc_vec is None:
                try:
                    doc_vec = await self._embed(text[:2000], tenant_id=query.tenant_id)
                except Exception as e:
                    log.warning("pgvector.embed.doc_failed",
                                doc_id=doc_id, error=str(e))
                    continue
                await self._cache_embedding(tenant_uuid, doc_id, doc_vec)
            score = _cosine(query_vec, doc_vec)
            scored.append((doc_id, text[:500], score))

        # 3b — CR-0017: blend in curated DOMAIN KNOWLEDGE. Knowledge rows carry
        # STORED embeddings + an HNSW index, so this is one indexed <=> query
        # (no re-embed) and works even when the tenant uploaded nothing — the
        # AI still reasons from industry knowledge ("học 1 hiểu 10").
        try:
            scored.extend(await self._load_knowledge(
                tenant_uuid, query_vec, top_k=max(query.max_citations, 1)))
        except Exception as e:
            log.warning("pgvector.knowledge.failed", error=str(e))

        if not scored:
            return RAGAnswer(
                engine_name=self.engine_name,
                answer="Không tìm được tài liệu hay tri thức liên quan để trả lời.",
                citations=(),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 4 — top-K across both sources by similarity
        scored.sort(key=lambda x: x[2], reverse=True)
        top_k = scored[: max(query.max_citations, 1)]

        citations = tuple(
            RAGCitation(
                engine_name=self.engine_name,
                source_id=doc_id,
                snippet=snippet,
                similarity=float(round(score, 4)),
            )
            for doc_id, snippet, score in top_k
        )

        # Grounding tools want the evidence, not a written answer — skip the
        # ~50s Qwen synthesis. Return citations + a plain joined snippet.
        if not query.synthesize:
            return RAGAnswer(
                engine_name=self.engine_name,
                answer="\n\n".join(s for _, s, _ in top_k),
                citations=citations,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 5 — synthesise answer with Qwen
        context_block = "\n\n".join(
            f"[doc {i + 1}]\n{snippet}"
            for i, (_doc_id, snippet, _score) in enumerate(top_k)
        )
        synth_prompt = (
            "Bạn là trợ lý phân tích dữ liệu. Trả lời câu hỏi của manager bằng "
            "tiếng Việt 1-3 câu, có inline citation [doc N] cho mỗi số liệu hoặc "
            "khẳng định chính. KHÔNG markdown, KHÔNG bullet list, KHÔNG từ vô "
            "nghĩa ('nhìn chung', 'tóm lại').\n\n"
            f"Câu hỏi: {query.query_text}\n\n"
            f"Tài liệu (top-{len(top_k)}):\n{context_block}"
        )
        try:
            text = await self._infer(synth_prompt, tenant_id=query.tenant_id)
        except Exception as e:
            log.warning("pgvector.synthesise.failed", error=str(e))
            text = (
                "Tìm được tài liệu liên quan nhưng không tổng hợp được câu trả lời. "
                f"Top-{len(top_k)} doc IDs: "
                + ", ".join(d for d, _, _ in top_k)
            )

        return RAGAnswer(
            engine_name=self.engine_name,
            answer=text.strip(),
            citations=citations,      # built before the synth branch above
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    # ─── Internal ────────────────────────────────────────────────

    async def _load_corpus(
        self, tenant_uuid: UUID, *, limit: int = MAX_CORPUS_DOCS,
    ) -> list[tuple[str, str]]:
        """Pull (file_id, docsage_text) for the tenant from bronze_files
        where Stage 6 D2 left usable text. Caps at `limit` (rag_max_corpus_docs)."""
        if self.db_pool is None:
            return []
        from ai_orchestrator.shared.db import acquire_for_tenant  # noqa: E402
        async with acquire_for_tenant(tenant_uuid) as conn:
            rows = await conn.fetch(
                """SELECT file_id::text AS file_id, metadata
                   FROM bronze_files
                   WHERE enterprise_id = $1
                     AND metadata ? 'docsage_status'
                     AND metadata->>'docsage_status' IN ('ok', 'partial')
                   ORDER BY created_at DESC
                   LIMIT $2""",
                tenant_uuid, limit,
            )
        out: list[tuple[str, str]] = []
        for r in rows:
            md = r["metadata"]
            if isinstance(md, str):
                md = json.loads(md)
            text = md.get("docsage_text") or ""
            if text:
                out.append((r["file_id"], text))
        return out

    async def _load_knowledge(
        self, tenant_uuid: UUID, query_vec: list[float], *, top_k: int,
    ) -> list[tuple[str, str, float]]:
        """CR-0017 — retrieve curated domain knowledge by stored-embedding
        cosine (``<=>``), RLS-scoped to global (tier 1-3) + this tenant (tier 4).
        Returns (source_id, snippet, similarity) tuples that merge straight into
        the document corpus ranking. Empty when there is no db_pool or no
        embedded knowledge yet (seeded rows awaiting re-embed)."""
        if self.db_pool is None or not query_vec:
            return []
        from ai_orchestrator.reasoning.knowledge.store import EMBEDDING_MODEL, _vec_to_pg  # noqa: E402
        from ai_orchestrator.shared.db import acquire_for_tenant  # noqa: E402
        async with acquire_for_tenant(tenant_uuid) as conn:
            rows = await conn.fetch(
                """SELECT document_id::text AS id, tier, source, title, content,
                          embedding <=> $1 AS distance
                   FROM knowledge_documents
                   WHERE embedding IS NOT NULL
                     AND embedding_model = $2
                     AND status = 'active'
                   ORDER BY embedding <=> $1
                   LIMIT $3""",
                _vec_to_pg(query_vec), EMBEDDING_MODEL, top_k,
            )
        out: list[tuple[str, str, float]] = []
        for r in rows:
            label = r["source"] or f"tier {r['tier']}"
            snippet = f"[tri thức ngành · {label}] {r['title']}: {(r['content'] or '')[:400]}"
            out.append((f"kb:{r['id']}", snippet, 1.0 - float(r["distance"])))
        return out

    async def _load_cached_embeddings(
        self, tenant_uuid: UUID, file_ids: list[str],
    ) -> dict[str, list[float]]:
        """Read stored bge-m3 embeddings for these bronze files (mig 133)."""
        if self.db_pool is None or not file_ids:
            return {}
        from ai_orchestrator.shared.db import acquire_for_tenant  # noqa: E402
        from ai_orchestrator.reasoning.knowledge.store import EMBEDDING_MODEL  # noqa: E402
        try:
            async with acquire_for_tenant(tenant_uuid) as conn:
                rows = await conn.fetch(
                    """SELECT file_id::text AS fid, embedding::text AS vec
                       FROM bronze_file_embeddings
                       WHERE file_id = ANY($1::uuid[]) AND embedding_model = $2""",
                    [UUID(f) for f in file_ids], EMBEDDING_MODEL,
                )
        except Exception as e:  # pragma: no cover
            log.warning("pgvector.cache.read_failed", error=str(e))
            return {}
        out: dict[str, list[float]] = {}
        for r in rows:
            try:
                out[r["fid"]] = [float(x) for x in r["vec"].strip("[]").split(",")]
            except Exception:
                continue
        return out

    async def _cache_embedding(
        self, tenant_uuid: UUID, file_id: str, vec: list[float],
    ) -> None:
        """Write-through: store an embedding so the next query reuses it."""
        if self.db_pool is None or not vec:
            return
        from ai_orchestrator.shared.db import acquire_for_tenant  # noqa: E402
        from ai_orchestrator.reasoning.knowledge.store import EMBEDDING_MODEL, _vec_to_pg  # noqa: E402
        try:
            async with acquire_for_tenant(tenant_uuid) as conn:
                await conn.execute(
                    """INSERT INTO bronze_file_embeddings
                           (file_id, enterprise_id, embedding, embedding_model)
                       VALUES ($1, $2, $3::vector, $4)
                       ON CONFLICT (file_id) DO NOTHING""",
                    UUID(file_id), tenant_uuid, _vec_to_pg(vec), EMBEDDING_MODEL,
                )
        except Exception as e:  # pragma: no cover
            log.warning("pgvector.cache.write_failed", file_id=file_id, error=str(e))

    async def _embed(self, text: str, *, tenant_id: str) -> list[float]:
        async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_S) as client:
            resp = await client.post(
                f"{self.gateway_url}/v1/embed",
                json={"text": text, "enterprise_id": tenant_id},
            )
            resp.raise_for_status()
            return resp.json().get("vector") or []

    async def _infer(self, prompt: str, *, tenant_id: str) -> str:
        async with httpx.AsyncClient(timeout=INFER_TIMEOUT_S) as client:
            resp = await client.post(
                f"{self.gateway_url}/v1/infer",
                json={
                    "task":             "rag.pgvector_synthesis",
                    "prompt":           prompt,
                    "enterprise_id":    tenant_id,
                    "consent_external": False,
                    "max_tokens":       400,
                },
            )
            resp.raise_for_status()
            return resp.json().get("completion") or ""
