"""
RAG engine abstract base + wire shapes — RAG-ROUTER-001 (P15-S10 D6).

Engines accept a RAGQuery + return a RAGAnswer with engine-tagged
citations. The router uses the engine_name field on the answer so the
caller can render different citation types (snippet, page-range,
SQL+rows) without dispatching by class.

Citation shape is intentionally permissive (Optional fields) — pgvector
returns text snippets, pageindex returns page ranges, docsage returns
SQL + table rows. Consumers render the field that's set; missing
fields render empty.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class RAGEngineUnavailable(RuntimeError):
    """Raised by the router when no available engine can answer.

    Reached when every engine in the tenant's whitelist either raises
    NotImplementedError (stub) or isn't registered. The router maps
    this to RFC 7807 503 at the API boundary — tenant configuration
    is intact (the whitelist isn't bypassed) and operator gets paged
    on the failure rather than the policy being silently violated.
    """


@dataclass(frozen=True)
class RAGQuery:
    """Inbound query envelope. Same shape across engines so the router
    can dispatch without each engine reading different headers."""

    tenant_id: str
    query_text: str
    user_id: Optional[str] = None             # for audit; not for filtering
    locale: str = "vi"                         # 'vi' default; 'en' for international
    max_citations: int = 5
    # When False, an engine returns the retrieved CITATIONS without the
    # (slow) LLM answer synthesis — for grounding tools that need evidence,
    # not a written answer. Engines that don't synthesise ignore it.
    synthesize: bool = True


@dataclass(frozen=True)
class RAGCitation:
    """One citation. Engine-specific fields are optional; consumers
    render the populated ones."""

    # Common — every engine sets these
    engine_name: str                          # 'pgvector' | 'pageindex' | 'docsage'
    source_id: str                            # doc_sha256 (pgvector/pageindex) or table_name (docsage)

    # pgvector-specific
    snippet: Optional[str] = None
    similarity: Optional[float] = None

    # pageindex-specific
    node_path: Optional[tuple[str, ...]] = None
    page_range: Optional[str] = None

    # docsage-specific
    sql_query: Optional[str] = None
    rows_returned: Optional[int] = None


@dataclass(frozen=True)
class RAGAnswer:
    """Engine response envelope. answer is the natural-language reply;
    citations is the trail consumers render alongside."""

    engine_name: str                          # picked engine, surfaces in audit
    answer: str
    citations: tuple[RAGCitation, ...] = field(default_factory=tuple)
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None          # external LLM cost; None for local Qwen


class RAGEngine(ABC):
    """Pluggable RAG engine. Implementations live in sibling modules."""

    engine_name: str = ""

    @abstractmethod
    async def answer(self, query: RAGQuery) -> RAGAnswer:
        """Answer the query + return citations. MUST set
        RAGAnswer.engine_name == self.engine_name so the router's audit
        log can attribute correctly."""
        ...
