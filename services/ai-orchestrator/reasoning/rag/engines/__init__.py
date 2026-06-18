"""
RAG engines — pluggable abstract base + 3 implementations per ADR-0019.

Each engine answers a query + returns RAGAnswer with engine-specific
citation shape (text snippet for pgvector, page-range for pageindex,
SQL+rows for docsage). The router (rag.router) picks per query
characteristics + tenant_settings.rag_engines whitelist.

Phase 1.5 P15-S10 + S11:
  pgvector_stub    — stub until pgvector real impl lands (P15-S11 in-progress)
  pageindex_engine — wraps reasoning.rag.pageindex (D7 ships StubBuilder)
  docsage          — REAL 3-module pipeline (P15-S11 D1-D5, 2026-05-17)
  docsage_stub     — fallback used when no LLM router is provided to the
                     router (e.g. unit tests of the heuristic only)
"""
from __future__ import annotations

from .base import RAGAnswer, RAGCitation, RAGEngine, RAGEngineUnavailable, RAGQuery
from .docsage import DocSageEngine
from .docsage_stub import DocSageStubEngine
from .pageindex_engine import PageIndexEngine
from .pgvector_real import PgVectorRealEngine
from .pgvector_stub import PGVectorStubEngine
from .trace_recall import TraceRecallEngine

__all__ = [
    "RAGAnswer",
    "RAGCitation",
    "RAGEngine",
    "RAGEngineUnavailable",
    "RAGQuery",
    "DocSageEngine",
    "DocSageStubEngine",
    "PageIndexEngine",
    "PGVectorStubEngine",
    "PgVectorRealEngine",
    "TraceRecallEngine",
]
