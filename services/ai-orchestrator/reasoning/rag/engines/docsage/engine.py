"""DocSage engine assembly — D6 endgame.

`DocSageEngine` is the `RAGEngine` implementation the router dispatches
to. It orchestrates the 3 modules (Schema Discovery → Structured
Extraction → SQL Reasoning) and returns the standard `RAGAnswer`
envelope so the router doesn't need to know it's DocSage talking.

Corpus selection (Phase 1.5 heuristic):
  * Pull up to 20 most-recent docs from `bronze_files` where the D2
    `metadata.docsage_status` is 'ok' or 'partial' for the tenant.
  * Higher-recall corpus selection (intent-driven, keyword pre-filter)
    is Phase 2 work.

Compliance: same K-3/4/5/19/20 as the 3 sub-modules. K-6 audit row is
written by the LLM router on every LLM hop (Schema + per-doc Extraction +
SQL compose + SQL format).
"""
from __future__ import annotations

import json
import time
from typing import Optional
from uuid import UUID

import structlog

from ..base import RAGAnswer, RAGCitation, RAGEngine, RAGQuery
from .extraction import StructuredExtraction
from .schema_discovery import SchemaDiscovery
from .sql_reasoning import SQLReasoning
from .types import Row

log = structlog.get_logger()


# Hard cap on corpus size to keep DocSage cost bounded per query —
# beyond this, the cost guard in plan §6 risk #1 says abort with a
# friendly error rather than burn the tenant's token budget.
MAX_CORPUS_DOCS = 20


class DocSageEngine(RAGEngine):
    """DocSage glue: dispatch SchemaDiscovery → StructuredExtraction →
    SQLReasoning, return RAGAnswer (router contract)."""

    engine_name = "docsage"

    def __init__(
        self,
        *,
        llm_router,
        db_pool,
        sql_executor=None,
    ):
        self.schema_discovery = SchemaDiscovery(llm_router=llm_router, db_pool=db_pool)
        self.extraction       = StructuredExtraction(llm_router=llm_router, db_pool=db_pool)
        self.sql_reasoning    = SQLReasoning(llm_router=llm_router,
                                              sql_executor=sql_executor)
        self.llm_router = llm_router
        self.db_pool    = db_pool

    async def answer(self, query: RAGQuery) -> RAGAnswer:
        t0 = time.monotonic()
        tenant_uuid = UUID(query.tenant_id)

        # 1 — pull corpus from bronze_files (per-tenant; RLS via acquire_for_tenant).  # tenant-filter-lint: allow
        # Reason: comment-only mention; actual SQL inside _load_corpus carries RLS GUC.
        corpus_excerpts, doc_meta = await self._load_corpus(tenant_uuid)
        if not corpus_excerpts:
            return RAGAnswer(
                engine_name=self.engine_name,
                answer=(
                    "Chưa có tài liệu DocSage trích xuất được — upload PDF/DOCX "
                    "vào workflow rồi thử lại."
                ),
                citations=(),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 2 — Schema Discovery.
        try:
            schema = await self.schema_discovery.discover(
                enterprise_id=tenant_uuid,
                question=query.query_text,
                corpus_excerpts=corpus_excerpts,
                consent_external=False,   # K-4 default; router elevates if tenant opted in
            )
        except Exception as e:
            log.warning("docsage.engine.schema_discovery_failed", error=str(e))
            return RAGAnswer(
                engine_name=self.engine_name,
                answer="Không hiểu được câu hỏi để xây schema. Vui lòng diễn đạt cụ thể hơn.",
                citations=(),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 3 — find or create the cached schema_id (so extractions cache).
        schema_id = await self._resolve_schema_id(
            tenant_uuid, corpus_excerpts, schema.question_class,
        )

        # 4 — per-doc Extraction.
        rows_by_doc: dict[str, list[Row]] = {}
        for doc_id, _excerpt in corpus_excerpts:
            full_text = doc_meta[doc_id]["text"]
            pages     = doc_meta[doc_id]["page_count"]
            res = await self.extraction.extract(
                enterprise_id=tenant_uuid, schema_id=schema_id, schema=schema,
                doc_id=doc_id, doc_text=full_text,
                page_from=1, page_to=max(pages, 1),
                consent_external=False,
            )
            if res.rows:
                rows_by_doc[doc_id] = res.rows

        if not rows_by_doc:
            return RAGAnswer(
                engine_name=self.engine_name,
                answer="Không trích xuất được dòng dữ liệu nào từ corpus.",
                citations=(),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        # 5 — SQL Reasoning.
        sql_ans = await self.sql_reasoning.query(
            enterprise_id=tenant_uuid, schema=schema,
            rows_by_doc=rows_by_doc, question=query.query_text,
            consent_external=False,
        )

        # 6 — translate citations to router shape.
        citations = tuple(
            RAGCitation(
                engine_name="docsage",
                source_id=c.doc_id,
                sql_query=sql_ans.sql_query or None,
                rows_returned=len(sql_ans.rowset),
                page_range=(f"{c.source_segment[0]}-{c.source_segment[1]}"
                             if c.source_segment else None),
            )
            for c in sql_ans.citations[: query.max_citations]
        )
        return RAGAnswer(
            engine_name=self.engine_name,
            answer=sql_ans.text,
            citations=citations,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    # ─── Internal ─────────────────────────────────────────────────

    async def _load_corpus(
        self, tenant_uuid: UUID,
    ) -> tuple[list[tuple[str, str]], dict[str, dict]]:
        """Return (corpus_excerpts, doc_meta) for the tenant.

        corpus_excerpts: list[(doc_id, short_excerpt)] for SchemaDiscovery
        doc_meta:        full text + page_count per doc_id for Extraction
        """
        if self.db_pool is None:
            return [], {}
        from ...shared.db import acquire_for_tenant  # noqa: E402
        async with acquire_for_tenant(tenant_uuid) as conn:
            rows = await conn.fetch(
                """SELECT file_id::text AS file_id, metadata
                   FROM bronze_files
                   WHERE enterprise_id = $1
                     AND metadata ? 'docsage_status'
                     AND metadata->>'docsage_status' IN ('ok', 'partial')
                   ORDER BY created_at DESC
                   LIMIT $2""",
                tenant_uuid, MAX_CORPUS_DOCS,
            )
        excerpts: list[tuple[str, str]] = []
        meta: dict[str, dict] = {}
        for r in rows:
            md = r["metadata"]
            if isinstance(md, str):
                md = json.loads(md)
            text = md.get("docsage_text") or ""
            pages = md.get("docsage_page_count") or 1
            if not text:
                continue
            excerpts.append((r["file_id"], text[:600]))
            meta[r["file_id"]] = {"text": text, "page_count": pages}
        return excerpts, meta

    async def _resolve_schema_id(
        self, tenant_uuid: UUID, corpus_excerpts: list[tuple[str, str]],
        question_class: str,
    ) -> UUID:
        """Look up the cached schema_id for (tenant, corpus_hash,
        question_class). The Discovery step wrote the row; this just
        reads it back as a UUID we can pass to Extraction's cache."""
        from .schema_discovery import corpus_hash_of
        from ...shared.db import acquire_for_tenant  # noqa: E402
        ch = corpus_hash_of([d for d, _ in corpus_excerpts])
        async with acquire_for_tenant(tenant_uuid) as conn:
            row = await conn.fetchrow(
                """SELECT schema_id FROM docsage_schemas
                   WHERE enterprise_id = $1 AND corpus_hash = $2
                     AND question_class = $3
                   ORDER BY created_at DESC LIMIT 1""",
                tenant_uuid, ch, question_class,
            )
        if row is None:
            # Race or db_pool=None test — synthesise a UUID; extractions
            # will not cache (FK orphan) but the answer still flows.
            from uuid import uuid4
            return uuid4()
        return row["schema_id"]
