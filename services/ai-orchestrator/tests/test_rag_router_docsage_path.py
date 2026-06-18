"""Tests for D6 — RAG router DocSage routing path.

Companion to tests/test_rag_router.py — these specifically exercise the
broader VN keyword set landed in commit `…` (D6 expansion) and the
DocSageEngine swap (real engine replaces stub when LLM router provided).

Coverage:
  * Each new VN keyword routes to DocSage.
  * Existing routing rules (PageIndex / pgvector / default) NOT broken.
  * Real DocSageEngine dispatchable through router.answer().
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_orchestrator.reasoning.rag.engines import (
    DocSageEngine,
    PageIndexEngine,
    PGVectorStubEngine,
    RAGAnswer,
    RAGEngine,
    RAGQuery,
)
from ai_orchestrator.reasoning.rag.router import RAGRouter


def _q(text: str) -> RAGQuery:
    return RAGQuery(tenant_id="11111111-1111-1111-1111-111111111111",
                     query_text=text, max_citations=5)


# ─── New keyword coverage ───────────────────────────────────────────


class TestNewMultiEntityKeywords:
    """Each of these queries SHOULD route to DocSage. All are ≥20 words
    so they pass the length filter."""

    BASE = "Chi nhánh nào "   # primes a 4-word seed; we pad to 20+ below

    @pytest.mark.parametrize("phrase", [
        "tổng doanh thu",
        "trung bình lợi nhuận",
        "ít nhất 3 đơn",
        "nhiều nhất khách hàng",
        "cao nhất chi phí",
        "thấp nhất tồn kho",
        "xếp hạng theo doanh số",
        "đứng đầu thị phần",
        "vendor nào trả chậm",
        "phòng ban nào năng suất",
    ])
    def test_keyword_routes_to_docsage(self, phrase):
        # Pad query to ≥20 words so the length gate passes.
        padding = " ".join(["a"] * 25)
        query_text = f"{phrase} {padding}"
        decision = RAGRouter.route(_q(query_text))
        assert decision.engine_name == "docsage", \
            f"{phrase!r}: routed to {decision.engine_name} ({decision.reason})"


# ─── Existing routes still work (regression safety) ─────────────────


class TestExistingRoutesNotBroken:

    def test_doc_citation_still_pageindex(self):
        # ≥20 words to trip the length gate AND contain a docsage
        # keyword if the doc-citation rule didn't take precedence first.
        q = ("Vui lòng cho biết điều khoản phạt vi phạm trong hợp đồng "
             "số HD-2026-001 — so sánh chi tiết với hợp đồng cũ.")
        decision = RAGRouter.route(_q(q))
        assert decision.engine_name == "pageindex"

    def test_short_summary_still_pgvector(self):
        decision = RAGRouter.route(_q("tóm tắt 5 khách hàng"))
        assert decision.engine_name == "pgvector"

    def test_default_still_pgvector(self):
        decision = RAGRouter.route(_q("Hello"))
        assert decision.engine_name == "pgvector"


# ─── Router dispatches real DocSageEngine ───────────────────────────


class TestRouterUsesRealDocSageEngine:

    @pytest.mark.asyncio
    async def test_router_dispatches_real_docsage(self):
        """When a real DocSageEngine is injected, router.answer() goes
        through it (not the stub)."""
        # Construct a real DocSageEngine with a mock LLM router. We
        # override the corpus loader so no Postgres is touched.
        llm = MagicMock()
        llm.complete_structured = AsyncMock(return_value={
            "tables": [{"name": "branches", "columns": [
                {"name": "branch_id", "sql_type": "TEXT", "role": "key",
                 "nullable": False, "fk_target": None},
            ]}],
            "join_keys": [],
            "question_class": "comparison",
        })
        llm.complete = AsyncMock(return_value="Câu trả lời mẫu.")

        eng = DocSageEngine(llm_router=llm, db_pool=None,
                             sql_executor=AsyncMock(return_value=[{"branch_id": "B01"}]))
        # No Postgres — provide our own corpus + schema_id resolver.
        eng._load_corpus = AsyncMock(return_value=(
            [("doc-1", "excerpt")],
            {"doc-1": {"text": "Branch B01 revenue 100", "page_count": 1}},
        ))
        from uuid import uuid4
        eng._resolve_schema_id = AsyncMock(return_value=uuid4())
        # Second LLM call returns extraction rows; third returns SQL.
        llm.complete_structured.side_effect = [
            # 1. schema discovery
            {"tables": [{"name": "branches", "columns": [
                {"name": "branch_id", "sql_type": "TEXT", "role": "key",
                 "nullable": False, "fk_target": None}]}],
             "join_keys": [], "question_class": "comparison"},
            # 2. extraction
            {"rows": [{"table": "branches", "values": {"branch_id": "B01"},
                       "source_segment": [1, 1]}]},
            # 3. SQL compose
            {"sql": "SELECT branch_id FROM branches", "explanation_vi": "x"},
        ]

        router = RAGRouter(
            pgvector=PGVectorStubEngine(),
            pageindex=PageIndexEngine(),
            docsage=eng,
        )
        # Long multi-entity query → DocSage route.
        q = _q("So sánh doanh thu chi nhánh nào cao nhất Q1 — "
                + " ".join(["x"] * 20))
        answer = await router.answer(q)
        assert answer.engine_name == "docsage"
        assert "Câu trả lời" in answer.answer
        # 3 structured + 1 plain = 4 LLM calls
        assert llm.complete_structured.await_count == 3
        assert llm.complete.await_count == 1
