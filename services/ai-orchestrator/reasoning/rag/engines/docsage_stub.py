"""
DocSage engine — STUB for P15-S10 D6 (full impl ships P15-S11 per
RAG_ADDENDUM_2026_05.md §6).

Per ADR-0019, DocSage is the structured-SQL reasoning engine for
multi-entity cross-doc QA. The full 3-module pipeline (Schema +
Extraction + SQL Reasoning) is a P15-S11 deliverable; this stub
exists so the router (D6) can:
  1. Recognise the docsage engine in its routing table.
  2. Fall back gracefully when a query routes to docsage but the real
     impl isn't shipped — the router catches NotImplementedError and
     re-routes to pgvector_stub per RAG_ADDENDUM §3 fallback rule.
"""
from __future__ import annotations

from .base import RAGAnswer, RAGEngine, RAGQuery


class DocSageStubEngine(RAGEngine):
    engine_name = "docsage"

    async def answer(self, query: RAGQuery) -> RAGAnswer:
        raise NotImplementedError(
            "DocSage engine is a P15-S11 deliverable per ADR-0019 + "
            "docs/strategic/RAG_ADDENDUM_2026_05.md §6. The router catches "
            "this and falls back to pgvector_stub so D6 can ship D8 + D7 "
            "ahead of the DocSage full impl."
        )
