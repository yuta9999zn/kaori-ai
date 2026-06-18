"""DocSage D5 — SQLReasoning unit tests + SQL whitelist parser.

The SQL whitelist is the security boundary that lets us trust LLM-emitted
SQL inside the DocSage pipeline. Tests are aggressive on adversarial inputs.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from ai_orchestrator.reasoning.rag.engines.docsage.sql_reasoning import (
    SQLReasoning,
    build_insert_statements,
    build_temp_table_ddl,
    is_sql_safe,
)
from ai_orchestrator.reasoning.rag.engines.docsage.types import (
    Column,
    Row,
    SchemaDefinition,
    Table,
)


ENT = UUID("11111111-1111-1111-1111-111111111111")


def _schema() -> SchemaDefinition:
    return SchemaDefinition(
        tables=[Table(name="branches", columns=[
            Column(name="branch_id",   sql_type="TEXT",    role="key"),
            Column(name="revenue_vnd", sql_type="NUMERIC", role="measure"),
        ])],
        question_class="comparison",
    )


# ─── is_sql_safe — whitelist parser ─────────────────────────────────


class TestIsSqlSafe:
    ALLOWED = {"branches", "orders"}

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM branches",
        "SELECT branch_id, revenue_vnd FROM branches WHERE revenue_vnd > 0",
        "SELECT b.branch_id FROM branches b JOIN orders o ON b.branch_id = o.branch_id",
        "  SELECT 1 FROM branches  ",   # leading/trailing space OK
    ])
    def test_accepts_safe_selects(self, sql):
        ok, reason = is_sql_safe(sql, allowed_tables=self.ALLOWED)
        assert ok, reason

    @pytest.mark.parametrize("sql,expected_substr", [
        ("",                                              "empty"),
        ("   ",                                           "empty"),
        ("INSERT INTO branches VALUES ('x', 1)",          "not a SELECT"),
        ("UPDATE branches SET revenue_vnd = 0",           "not a SELECT"),
        ("DROP TABLE branches",                            "not a SELECT"),
        ("CREATE TABLE evil (x int)",                     "not a SELECT"),
        # Multi-statement with embedded DML hits the DML check first (also
        # a hard reject; both rejection paths are valid security-wise).
        ("SELECT * FROM branches; DROP TABLE branches",   "DML/DDL keyword"),
        # Pure multi-statement without DML: still rejected.
        ("SELECT * FROM branches; SELECT 1",              "multi-statement"),
        ("SELECT * FROM users",                            "outside schema"),
        ("SELECT * FROM enterprise_users",                 "outside schema"),
        ("SELECT * FROM branches -- malicious",            "comments not allowed"),
        ("SELECT * FROM branches /* injection */",         "comments not allowed"),
        ("WITH x AS (DELETE FROM branches RETURNING *) SELECT * FROM x", "not a SELECT"),
    ])
    def test_rejects_unsafe(self, sql, expected_substr):
        ok, reason = is_sql_safe(sql, allowed_tables=self.ALLOWED)
        assert not ok
        assert expected_substr in reason

    def test_trailing_semicolon_allowed(self):
        ok, _ = is_sql_safe("SELECT * FROM branches;", allowed_tables=self.ALLOWED)
        assert ok


# ─── build_temp_table_ddl ───────────────────────────────────────────


class TestBuildTempTableDdl:
    def test_emits_create_temporary(self):
        ddls = build_temp_table_ddl(_schema())
        assert len(ddls) == 1
        ddl = ddls[0]
        assert ddl.startswith("CREATE TEMPORARY TABLE branches")
        assert "branch_id TEXT" in ddl
        assert "revenue_vnd NUMERIC" in ddl

    def test_not_null_constraint(self):
        s = SchemaDefinition(
            tables=[Table(name="t", columns=[
                Column(name="id", sql_type="TEXT", role="key", nullable=False),
                Column(name="name", sql_type="TEXT", role="attribute", nullable=True),
            ])],
            question_class="comparison",
        )
        ddl = build_temp_table_ddl(s)[0]
        assert "id TEXT NOT NULL" in ddl
        assert "name TEXT" in ddl and "name TEXT NOT NULL" not in ddl


# ─── build_insert_statements ────────────────────────────────────────


class TestBuildInsertStatements:
    def test_emits_parameter_binding(self):
        rows = [
            Row(table="branches", values={"branch_id": "B01", "revenue_vnd": 100}),
            Row(table="branches", values={"branch_id": "B02", "revenue_vnd": 200}),
        ]
        out = build_insert_statements(_schema(), rows)
        assert len(out) == 2
        sql, params = out[0]
        # parameterised: $1, $2 — no string interpolation of values
        assert "$1" in sql and "$2" in sql
        assert "B01" in params and 100 in params

    def test_drops_rows_for_tables_not_in_schema(self):
        rows = [
            Row(table="branches", values={"branch_id": "B01", "revenue_vnd": 100}),
            Row(table="ghost_table", values={"x": 1}),
        ]
        out = build_insert_statements(_schema(), rows)
        assert len(out) == 1
        assert "branches" in out[0][0]

    def test_missing_column_in_values_becomes_None(self):
        rows = [Row(table="branches", values={"branch_id": "B01"})]  # no revenue_vnd
        out = build_insert_statements(_schema(), rows)
        _, params = out[0]
        assert params == ["B01", None]


# ─── SQLReasoning.query() end-to-end (mocked) ───────────────────────


@pytest.mark.asyncio
async def test_query_happy_path():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "sql": "SELECT branch_id, revenue_vnd FROM branches ORDER BY revenue_vnd DESC",
        "explanation_vi": "Sắp xếp doanh thu giảm dần",
    })
    llm.complete = AsyncMock(return_value=
        "Chi nhánh dẫn đầu là B02 với 200 triệu VNĐ [trang 3-4]."
    )
    rows_by_doc = {
        "doc-1": [Row(table="branches",
                       values={"branch_id": "B01", "revenue_vnd": 100},
                       source_segment=(1, 2)),
                   Row(table="branches",
                       values={"branch_id": "B02", "revenue_vnd": 200},
                       source_segment=(3, 4))],
    }
    executor = AsyncMock(return_value=[
        {"branch_id": "B02", "revenue_vnd": 200},
        {"branch_id": "B01", "revenue_vnd": 100},
    ])
    sr = SQLReasoning(llm_router=llm, sql_executor=executor)
    ans = await sr.query(
        enterprise_id=ENT, schema=_schema(),
        rows_by_doc=rows_by_doc, question="Chi nhánh nào doanh thu cao nhất?",
    )
    assert ans.error is None
    assert ans.sql_query.upper().startswith("SELECT")
    assert len(ans.rowset) == 2
    assert "B02" in ans.text
    assert len(ans.citations) == 2
    assert ans.citations[0].engine == "docsage"
    executor.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_rejects_unsafe_sql_from_llm():
    """LLM tries to escape with `; DROP TABLE`. Whitelist parser blocks
    + the executor is never called."""
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "sql": "SELECT * FROM branches; DROP TABLE branches",
        "explanation_vi": "...",
    })
    executor = AsyncMock()
    sr = SQLReasoning(llm_router=llm, sql_executor=executor)
    ans = await sr.query(
        enterprise_id=ENT, schema=_schema(),
        rows_by_doc={"doc-1": [Row(table="branches",
                                     values={"branch_id": "X", "revenue_vnd": 1},
                                     source_segment=(1, 1))]},
        question="Q",
    )
    assert "rejected" in (ans.error or "")
    executor.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_rejects_sql_referencing_unknown_table():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "sql": "SELECT * FROM enterprise_users",
        "explanation_vi": "...",
    })
    executor = AsyncMock()
    sr = SQLReasoning(llm_router=llm, sql_executor=executor)
    ans = await sr.query(
        enterprise_id=ENT, schema=_schema(),
        rows_by_doc={"doc-1": [Row(table="branches",
                                     values={"branch_id": "X", "revenue_vnd": 1},
                                     source_segment=(1, 1))]},
        question="Q",
    )
    assert "rejected" in (ans.error or "")
    executor.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_empty_rowset_short_circuits():
    llm = MagicMock()
    llm.complete_structured = AsyncMock()
    sr = SQLReasoning(llm_router=llm, sql_executor=AsyncMock())
    ans = await sr.query(
        enterprise_id=ENT, schema=_schema(),
        rows_by_doc={},
        question="Q",
    )
    assert "Không có dữ liệu" in ans.text
    llm.complete_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_executor_failure_returns_clean_error():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "sql": "SELECT branch_id FROM branches",
        "explanation_vi": "...",
    })
    executor = AsyncMock(side_effect=RuntimeError("DB connection lost"))
    sr = SQLReasoning(llm_router=llm, sql_executor=executor)
    ans = await sr.query(
        enterprise_id=ENT, schema=_schema(),
        rows_by_doc={"d": [Row(table="branches",
                                 values={"branch_id": "X", "revenue_vnd": 1},
                                 source_segment=(1, 1))]},
        question="Q",
    )
    assert "execution error" in (ans.error or "")
    assert "thử lại" in ans.text


@pytest.mark.asyncio
async def test_query_no_executor_returns_descriptive_error():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "sql": "SELECT * FROM branches", "explanation_vi": "x"})
    sr = SQLReasoning(llm_router=llm, sql_executor=None)
    ans = await sr.query(
        enterprise_id=ENT, schema=_schema(),
        rows_by_doc={"d": [Row(table="branches",
                                 values={"branch_id": "X", "revenue_vnd": 1},
                                 source_segment=(1, 1))]},
        question="Q",
    )
    assert ans.error == "no executor"


# ─── DocSageEngine integration (mocked at every boundary) ───────────


class TestDocSageEngineIntegration:
    """The engine glues 3 modules. We mock the LLM router + sql_executor
    so the test runs purely in-memory."""

    @pytest.mark.asyncio
    async def test_engine_pipeline_returns_rag_answer(self):
        from ai_orchestrator.reasoning.rag.engines.base import RAGQuery
        from ai_orchestrator.reasoning.rag.engines.docsage import DocSageEngine

        llm = MagicMock()
        # 4 LLM calls in order: schema_discovery / extraction (per doc) /
        # sql_compose / sql_format. We give each what it needs.
        llm.complete_structured = AsyncMock(side_effect=[
            # 1. Schema Discovery
            {"tables": [{"name": "branches", "columns": [
                {"name": "branch_id",   "sql_type": "TEXT",    "role": "key",
                 "nullable": False, "fk_target": None},
                {"name": "revenue_vnd", "sql_type": "NUMERIC", "role": "measure",
                 "nullable": True,  "fk_target": None},
            ]}], "join_keys": [], "question_class": "comparison"},
            # 2. Extraction (1 doc only in this test)
            {"rows": [
                {"table": "branches",
                 "values": {"branch_id": "B01", "revenue_vnd": 100},
                 "source_segment": [1, 2]},
            ]},
            # 3. SQL compose
            {"sql": "SELECT branch_id FROM branches", "explanation_vi": "x"},
        ])
        llm.complete = AsyncMock(return_value="Chi nhánh B01 [trang 1-2].")

        executor = AsyncMock(return_value=[{"branch_id": "B01"}])

        # Avoid touching shared.db — we override _load_corpus + _resolve_schema_id
        eng = DocSageEngine(llm_router=llm, db_pool=None, sql_executor=executor)
        eng._load_corpus = AsyncMock(return_value=(
            [("doc-1", "Q1 revenue per branch: B01 100 triệu")],
            {"doc-1": {"text": "Q1 revenue per branch: B01 100 triệu",
                        "page_count": 2}},
        ))
        from uuid import uuid4
        eng._resolve_schema_id = AsyncMock(return_value=uuid4())

        query = RAGQuery(
            tenant_id=str(ENT),
            query_text="So sánh doanh thu chi nhánh Q1",
            max_citations=5,
        )
        ans = await eng.answer(query)
        assert ans.engine_name == "docsage"
        assert "B01" in ans.answer
        assert ans.latency_ms is not None
        # 3 structured + 1 plain = 4 LLM calls
        assert llm.complete_structured.await_count == 3
        assert llm.complete.await_count == 1
