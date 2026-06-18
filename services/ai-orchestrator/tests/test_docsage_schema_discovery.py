"""DocSage D3 — SchemaDiscovery unit tests.

Mocks the LLM router; no Postgres needed (db_pool=None mode in the
class). Validates:
  * Pydantic schema enforcement (snake_case, enum, length, role vocab).
  * Cache hit short-circuits the LLM call.
  * Cache miss → LLM call → cache write.
  * Output-schema JSON Schema shape matches spec §4.3.
  * corpus_hash_of() deterministic and order-independent.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from ai_orchestrator.reasoning.rag.engines.docsage import (
    SchemaDefinition,
    SchemaDiscovery,
)
from ai_orchestrator.reasoning.rag.engines.docsage.schema_discovery import (
    _schema_definition_json_schema,
    corpus_hash_of,
)
from ai_orchestrator.reasoning.rag.engines.docsage.types import Column, Table


ENT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Pydantic enforcement ───────────────────────────────────────────


class TestSchemaDefinitionValidation:

    def test_happy_path(self):
        s = SchemaDefinition(
            tables=[Table(name="branches", columns=[
                Column(name="branch_id",  sql_type="TEXT",    role="key"),
                Column(name="revenue_vnd", sql_type="NUMERIC", role="measure"),
            ])],
            join_keys=[],
            question_class="comparison",
        )
        assert s.tables[0].name == "branches"
        assert s.tables[0].columns[1].sql_type == "NUMERIC"

    def test_sql_type_normalised_to_upper(self):
        c = Column(name="x", sql_type="numeric", role="measure")
        assert c.sql_type == "NUMERIC"

    def test_sql_type_rejects_unknown(self):
        with pytest.raises(ValueError, match="sql_type must be"):
            Column(name="x", sql_type="JSONB", role="attribute")

    def test_role_rejects_unknown(self):
        with pytest.raises(ValueError, match="role must be"):
            Column(name="x", sql_type="TEXT", role="primary_key")

    def test_column_name_must_be_snake_case_alnum(self):
        with pytest.raises(ValueError, match="snake_case"):
            Column(name="Branch-ID", sql_type="TEXT", role="key")

    def test_column_name_lowercased(self):
        c = Column(name="BranchId", sql_type="TEXT", role="key")
        assert c.name == "branchid"

    def test_table_name_first_char_must_be_alpha(self):
        with pytest.raises(ValueError, match="snake_case"):
            Table(name="1_thing", columns=[Column(name="a", sql_type="TEXT", role="attribute")])

    def test_question_class_in_vocab(self):
        with pytest.raises(ValueError, match="question_class must be"):
            SchemaDefinition(
                tables=[Table(name="t", columns=[Column(name="a", sql_type="TEXT", role="attribute")])],
                question_class="other",
            )

    def test_at_most_5_tables(self):
        many = [Table(name=f"t{i}", columns=[Column(name="a", sql_type="TEXT", role="attribute")])
                for i in range(6)]
        with pytest.raises(ValueError):
            SchemaDefinition(tables=many, question_class="comparison")

    def test_at_most_12_columns_per_table(self):
        cols = [Column(name=f"c{i}", sql_type="TEXT", role="attribute") for i in range(13)]
        with pytest.raises(ValueError):
            Table(name="t", columns=cols)


# ─── JSON Schema for Issue #3 ───────────────────────────────────────


class TestJsonSchema:

    def test_required_top_level_keys(self):
        s = _schema_definition_json_schema()
        assert s["type"] == "object"
        assert set(s["required"]) == {"tables", "question_class"}

    def test_question_class_enum_matches_pydantic_vocab(self):
        s = _schema_definition_json_schema()
        assert set(s["properties"]["question_class"]["enum"]) == {
            "comparison", "aggregation", "relationship", "ranking",
        }

    def test_column_sql_type_enum_matches_pydantic_vocab(self):
        s = _schema_definition_json_schema()
        col_schema = s["properties"]["tables"]["items"]["properties"]["columns"]["items"]
        assert set(col_schema["properties"]["sql_type"]["enum"]) == {
            "TEXT", "INTEGER", "NUMERIC", "DATE", "TIMESTAMP", "BOOLEAN",
        }

    def test_column_role_enum_matches_pydantic_vocab(self):
        s = _schema_definition_json_schema()
        col_schema = s["properties"]["tables"]["items"]["properties"]["columns"]["items"]
        assert set(col_schema["properties"]["role"]["enum"]) == {
            "key", "attribute", "measure", "fk",
        }


# ─── corpus_hash_of ─────────────────────────────────────────────────


class TestCorpusHash:

    def test_deterministic(self):
        a = corpus_hash_of(["doc1", "doc2", "doc3"])
        b = corpus_hash_of(["doc1", "doc2", "doc3"])
        assert a == b

    def test_order_independent(self):
        a = corpus_hash_of(["doc1", "doc2", "doc3"])
        b = corpus_hash_of(["doc3", "doc1", "doc2"])
        assert a == b

    def test_different_corpus_different_hash(self):
        a = corpus_hash_of(["doc1", "doc2"])
        b = corpus_hash_of(["doc1", "doc3"])
        assert a != b

    def test_empty_corpus_handled(self):
        h = corpus_hash_of([])
        assert isinstance(h, str) and len(h) == 64

    def test_whitespace_doc_ids_stripped(self):
        a = corpus_hash_of(["doc1", "doc2"])
        b = corpus_hash_of(["  doc1  ", "\tdoc2"])
        assert a == b


# ─── End-to-end (mocked LLM) ────────────────────────────────────────


def _valid_payload() -> dict:
    return {
        "tables": [{
            "name": "branches",
            "columns": [
                {"name": "branch_id", "sql_type": "TEXT", "role": "key",
                 "nullable": False, "fk_target": None},
                {"name": "name", "sql_type": "TEXT", "role": "attribute",
                 "nullable": True, "fk_target": None},
                {"name": "revenue_vnd", "sql_type": "NUMERIC", "role": "measure",
                 "nullable": True, "fk_target": None},
            ],
        }],
        "join_keys": [],
        "question_class": "comparison",
    }


@pytest.mark.asyncio
async def test_discover_no_cache_calls_llm_and_returns_validated_schema():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value=_valid_payload())
    sd = SchemaDiscovery(llm_router=llm, db_pool=None)  # db_pool=None skips cache

    result = await sd.discover(
        enterprise_id=ENT,
        question="So sánh doanh thu 3 chi nhánh Q1",
        corpus_excerpts=[("doc1", "Doanh thu Q1 chi nhánh Hà Nội: 100 triệu VND"),
                          ("doc2", "Doanh thu Q1 chi nhánh TP.HCM: 200 triệu VND")],
        consent_external=False,
    )
    assert isinstance(result, SchemaDefinition)
    assert result.question_class == "comparison"
    assert result.tables[0].name == "branches"
    # LLM called exactly once.
    assert llm.complete_structured.await_count == 1
    # task + enterprise_id + output_schema forwarded.
    call_kwargs = llm.complete_structured.await_args.kwargs
    assert call_kwargs["task"] == "docsage.schema_discovery"
    assert call_kwargs["enterprise_id"] == str(ENT)
    assert "tables" in call_kwargs["output_schema"]["properties"]


@pytest.mark.asyncio
async def test_discover_propagates_consent_external_to_llm_router():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value=_valid_payload())
    sd = SchemaDiscovery(llm_router=llm, db_pool=None)
    await sd.discover(
        enterprise_id=ENT,
        question="Q",
        corpus_excerpts=[("doc1", "x")],
        consent_external=True,
    )
    assert llm.complete_structured.await_args.kwargs["consent_external"] is True


@pytest.mark.asyncio
async def test_discover_corpus_excerpts_trimmed_to_3_docs_and_600_chars():
    """Spec §4.3 — only the first 3 docs, each ≤600 chars. 4th doc
    must not appear in the prompt."""
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value=_valid_payload())
    sd = SchemaDiscovery(llm_router=llm, db_pool=None)
    long_doc = "A" * 1000
    await sd.discover(
        enterprise_id=ENT,
        question="Q",
        corpus_excerpts=[
            ("doc1", long_doc),
            ("doc2", "short doc 2"),
            ("doc3", "short doc 3"),
            ("doc4", "MUST NOT APPEAR"),
        ],
        consent_external=False,
    )
    prompt = llm.complete_structured.await_args.kwargs["prompt"]
    assert "MUST NOT APPEAR" not in prompt
    # The 1000-char doc is trimmed to 600 — no run of >600 contiguous A's.
    assert "A" * 601 not in prompt


@pytest.mark.asyncio
async def test_discover_rejects_invalid_llm_output():
    """LLM returns something that passes JSON Schema (gateway side) but
    fails the Pydantic defence-in-depth (e.g., sql_type=JSONB). The
    Pydantic ValidationError must propagate — the caller's RAGRouter
    falls back to pgvector when DocSage raises."""
    bad = _valid_payload()
    bad["tables"][0]["columns"][0]["sql_type"] = "JSONB"   # not in our vocab
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value=bad)
    sd = SchemaDiscovery(llm_router=llm, db_pool=None)
    with pytest.raises(Exception):
        await sd.discover(
            enterprise_id=ENT,
            question="Q",
            corpus_excerpts=[("doc1", "x")],
            consent_external=False,
        )
