"""
pgvector engine — STUB for P15-S10 D6.

The real pgvector retrieval (BGE-M3 embedding + cosine similarity over
the existing pgvector store + LLM synthesis) lands separately —
expected next sprint after S9 review settles. This stub returns a
sentinel citation so the router (rag.router) tests can assert routing
decisions without paying for embedding + LLM calls.

The [STUB] marker in the answer + source_id mirrors the PageIndex stub
pattern (D7 tree_builder) so an operator who sees a stub citation in
production knows immediately that the real engine isn't wired yet for
the calling tenant.
"""
from __future__ import annotations

from .base import RAGAnswer, RAGCitation, RAGEngine, RAGQuery


class PGVectorStubEngine(RAGEngine):
    engine_name = "pgvector"

    async def answer(self, query: RAGQuery) -> RAGAnswer:
        return RAGAnswer(
            engine_name=self.engine_name,
            answer=(
                f"[STUB pgvector] Would have embedded the {len(query.query_text)}-char "
                f"query for tenant={query.tenant_id} and returned the top-"
                f"{query.max_citations} similar vectors."
            ),
            citations=(
                RAGCitation(
                    engine_name=self.engine_name,
                    source_id="[STUB]doc-stub-1",
                    snippet="[STUB] pgvector stub citation snippet",
                    similarity=0.99,
                ),
            ),
        )
