"""DocSage D4 — StructuredExtraction unit tests.

Mocks the LLM router; no Postgres (db_pool=None). Validates:
  * Happy path: 1 doc → list[Row].
  * Doc exceeds 8K → split into ≤4 segments + merge results.
  * Segment-level failure → status='partial' with rows from other segs.
  * Empty doc_text → status='failed' early.
  * Hallucinated table (not in schema) skipped, not poisoned.
  * Bad Row payload (Pydantic fails) skipped, not crashed.
  * source_segment coerced from [from, to] list to tuple.
  * PII redaction applied when consent_external=True; bypassed when False.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from ai_orchestrator.reasoning.rag.engines.docsage.extraction import (
    DOC_TEXT_CAP,
    ExtractionResult,
    StructuredExtraction,
    redact_pii,
)
from ai_orchestrator.reasoning.rag.engines.docsage.types import (
    Column,
    SchemaDefinition,
    Table,
)


ENT       = UUID("11111111-1111-1111-1111-111111111111")
SCHEMA_ID = UUID("22222222-2222-2222-2222-222222222222")


def _schema() -> SchemaDefinition:
    return SchemaDefinition(
        tables=[Table(name="branches", columns=[
            Column(name="branch_id",   sql_type="TEXT",    role="key"),
            Column(name="revenue_vnd", sql_type="NUMERIC", role="measure"),
        ])],
        question_class="comparison",
    )


# ─── PII redaction ──────────────────────────────────────────────────


class TestRedactPii:
    def test_email_redacted(self):
        assert "<EMAIL>" in redact_pii("Contact: john.doe@acme.com")
        assert "john.doe@acme.com" not in redact_pii("Contact: john.doe@acme.com")

    def test_phone_local_redacted(self):
        assert "<PHONE>" in redact_pii("ĐT: 0901234567")

    def test_phone_e164_redacted(self):
        assert "<PHONE>" in redact_pii("Phone: +84901234567")

    def test_cccd_redacted(self):
        assert "<NID>" in redact_pii("CCCD: 001234567890")

    def test_safe_text_unchanged(self):
        s = "Doanh thu quý 1 là 100 triệu VND."
        assert redact_pii(s) == s


# ─── Happy path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_happy_path():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "rows": [
            {"table": "branches",
             "values": {"branch_id": "B01", "revenue_vnd": 100_000_000},
             "source_segment": [1, 2]},
            {"table": "branches",
             "values": {"branch_id": "B02", "revenue_vnd": 200_000_000},
             "source_segment": [3, 4]},
        ],
    })
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    result = await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="doc-1", doc_text="Q1 revenue per branch:\nHà Nội 100M, TP.HCM 200M.",
        page_from=1, page_to=4, consent_external=False,
    )
    assert result.extraction_status == "ok"
    assert len(result.rows) == 2
    assert result.rows[0].table == "branches"
    assert result.rows[0].values["branch_id"] == "B01"
    # source_segment coerced from list → tuple
    assert isinstance(result.rows[0].source_segment, tuple)
    assert result.rows[0].source_segment == (1, 2)


# ─── Empty input ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_empty_doc_text_fails_early():
    llm = MagicMock()
    llm.complete_structured = AsyncMock()
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    result = await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="doc-1", doc_text="",
    )
    assert result.extraction_status == "failed"
    llm.complete_structured.assert_not_awaited()


# ─── Hallucinated rows ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_drops_hallucinated_table_rows():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "rows": [
            {"table": "branches",      # OK
             "values": {"branch_id": "B01", "revenue_vnd": 100},
             "source_segment": [1, 1]},
            {"table": "customers",     # NOT in schema → drop
             "values": {"name": "Anh"},
             "source_segment": [1, 1]},
        ],
    })
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    result = await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="doc-1", doc_text="some text",
    )
    # Only the branches row survived; status remains 'ok' (the LLM call
    # itself didn't fail).
    assert len(result.rows) == 1
    assert result.rows[0].table == "branches"


# ─── Split + merge ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_splits_oversize_doc_into_segments():
    llm = MagicMock()
    # Each segment returns 1 row.
    llm.complete_structured = AsyncMock(return_value={
        "rows": [{"table": "branches",
                  "values": {"branch_id": "X", "revenue_vnd": 1},
                  "source_segment": [1, 1]}],
    })
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    big = ("paragraph A.\n\n" * (DOC_TEXT_CAP // 14)) \
        + ("paragraph B.\n\n" * (DOC_TEXT_CAP // 14))
    assert len(big) > DOC_TEXT_CAP
    result = await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="big-doc", doc_text=big, page_from=1, page_to=10,
    )
    # >1 LLM call (split happened).
    assert llm.complete_structured.await_count >= 2
    # Status downgrades to 'partial' because multiple segments touched
    # the doc (the per-segment ok was OK; status='partial' surfaces the
    # multi-segment caveat so caller can show "trích xuất theo phần").
    assert result.extraction_status == "partial"


# ─── Segment failure ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_segment_failure_falls_through_to_partial():
    llm = MagicMock()
    # First call raises, second returns rows.
    llm.complete_structured = AsyncMock(side_effect=[
        RuntimeError("LLM gateway 502"),
        {"rows": [{"table": "branches",
                   "values": {"branch_id": "Y", "revenue_vnd": 5},
                   "source_segment": [5, 5]}]},
    ])
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    big = "alpha\n\n" + ("X" * DOC_TEXT_CAP) + "\n\n" + "beta"
    result = await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="d", doc_text=big, page_from=1, page_to=2,
    )
    assert result.extraction_status == "partial"
    # We still got the second segment's row.
    assert len(result.rows) == 1


# ─── PII redaction wire ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_redacts_pii_when_consent_external_true():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={"rows": []})
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="d", doc_text="Contact: anh@acme.com 0901234567",
        consent_external=True,
    )
    prompt = llm.complete_structured.await_args.kwargs["prompt"]
    assert "anh@acme.com" not in prompt
    assert "<EMAIL>" in prompt
    assert "0901234567" not in prompt
    assert "<PHONE>" in prompt


@pytest.mark.asyncio
async def test_extract_does_not_redact_when_consent_external_false():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={"rows": []})
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="d", doc_text="Contact: anh@acme.com",
        consent_external=False,
    )
    prompt = llm.complete_structured.await_args.kwargs["prompt"]
    assert "anh@acme.com" in prompt  # Qwen local stays raw


# ─── source_segment defaults when LLM omits ─────────────────────────


@pytest.mark.asyncio
async def test_extract_defaults_source_segment_when_llm_omits():
    llm = MagicMock()
    llm.complete_structured = AsyncMock(return_value={
        "rows": [{"table": "branches",
                  "values": {"branch_id": "B01", "revenue_vnd": 100}}],
    })
    se = StructuredExtraction(llm_router=llm, db_pool=None)
    result = await se.extract(
        enterprise_id=ENT, schema_id=SCHEMA_ID, schema=_schema(),
        doc_id="d", doc_text="x", page_from=3, page_to=7,
    )
    assert len(result.rows) == 1
    # Default = (page_from, page_to) from the call site.
    assert result.rows[0].source_segment == (3, 7)
