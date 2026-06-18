"""
Tests for the 2 Phase 2.5 AI nodes:
  - reasoning/document_classifier.classify_document
  - reasoning/structured_extractor.extract_structured_data

Both consume Block lists (from data-pipeline Stage 6 output) + call
llm_router via mock. No live LLM in tests.

8-section template:
  1. Default categories + ClassifyInput shape
  2. Prompt building — titles + body trimming
  3. Classification happy path (mocked LLM)
  4. Classification OOV category → 'uncertain'
  5. JSON fallback parser (code fences + wrapped JSON)
  6. ExtractInput + ColumnSpec + output_schema generation
  7. extract_structured_data — no tables / happy path / low confidence
  8. extract_structured_data — provenance + warnings + per-table failure
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.data_plane_shim import Block, BlockType
from ai_orchestrator.reasoning.document_classifier import (
    DEFAULT_CATEGORIES,
    ClassifyInput,
    ClassifyOutput,
    _build_prompt,
    _parse_json_fallback,
    classify_document,
)
from ai_orchestrator.reasoning.structured_extractor import (
    ColumnSpec,
    ExtractInput,
    ExtractOutput,
    ExtractedRow,
    _column_brief,
    _output_schema_for,
    extract_structured_data,
)


ENT = "11111111-1111-1111-1111-111111111111"


# ═════════════════════════════════════════════════════════════════════
# 1. ClassifyInput defaults
# ═════════════════════════════════════════════════════════════════════


class TestClassifyInputDefaults:

    def test_default_categories_filled(self):
        inp = ClassifyInput(blocks=[], enterprise_id=ENT)
        assert inp.candidates is not None
        assert "contract" in inp.candidates
        assert "invoice" in inp.candidates
        assert "other" in inp.candidates

    def test_explicit_candidates_preserved(self):
        custom = ["nda", "service_contract", "employment"]
        inp = ClassifyInput(blocks=[], enterprise_id=ENT, candidates=custom)
        assert inp.candidates == custom

    def test_default_categories_constant_has_main_types(self):
        for k in ("contract", "invoice", "report", "regulation", "resume"):
            assert k in DEFAULT_CATEGORIES


# ═════════════════════════════════════════════════════════════════════
# 2. Prompt building
# ═════════════════════════════════════════════════════════════════════


class TestBuildPrompt:

    def test_includes_candidates_list(self):
        blocks = [Block(BlockType.TEXT, 0, 0, 50, "body content")]
        prompt = _build_prompt(blocks, ["contract", "invoice"])
        assert "contract, invoice" in prompt

    def test_includes_titles(self):
        blocks = [
            Block(BlockType.TITLE, 0, 0, 30, "Hợp đồng dịch vụ"),
            Block(BlockType.TEXT, 0, 31, 100, "Bên A và Bên B đồng ý"),
        ]
        prompt = _build_prompt(blocks, ["contract"])
        assert "Hợp đồng dịch vụ" in prompt

    def test_skips_header_footer(self):
        blocks = [
            Block(BlockType.HEADER, 0, 0, 10, "© Kaori"),
            Block(BlockType.TEXT, 0, 11, 50, "Real content here"),
            Block(BlockType.FOOTER, 0, 51, 60, "Page 1"),
        ]
        prompt = _build_prompt(blocks, ["report"])
        assert "© Kaori" not in prompt
        assert "Page 1" not in prompt
        assert "Real content here" in prompt

    def test_body_capped_around_3kb(self):
        big_block = Block(BlockType.TEXT, 0, 0, 10000, "x" * 10000)
        prompt = _build_prompt([big_block], ["other"])
        # Em cap at ~3000 chars; prompt overhead ~500 chars
        assert len(prompt) < 5000


# ═════════════════════════════════════════════════════════════════════
# 3. Classify happy path
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestClassifyHappy:

    async def test_returns_category_with_confidence(self):
        blocks = [
            Block(BlockType.TITLE, 0, 0, 30, "Hợp đồng dịch vụ A-B"),
            Block(BlockType.TEXT, 0, 31, 100, "Bên A là công ty X..."),
        ]
        mock_result = {
            "category":   "contract",
            "confidence": 0.93,
            "reasoning":  "Có tiêu đề 'Hợp đồng' + nội dung Bên A/B điển hình hợp đồng.",
        }
        with patch(
            "ai_orchestrator.reasoning.document_classifier.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await classify_document(ClassifyInput(
                blocks=blocks, enterprise_id=ENT, min_confidence=0.7,
            ))
        assert out.category == "contract"
        assert out.confidence == 0.93
        assert out.meets_threshold is True
        assert "Hợp đồng" in out.reasoning

    async def test_low_confidence_does_not_meet_threshold(self):
        blocks = [Block(BlockType.TEXT, 0, 0, 50, "ambiguous text")]
        mock_result = {
            "category":   "report",
            "confidence": 0.40,
            "reasoning":  "Nội dung mơ hồ, không rõ là báo cáo hay đơn.",
        }
        with patch(
            "ai_orchestrator.reasoning.document_classifier.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await classify_document(ClassifyInput(
                blocks=blocks, enterprise_id=ENT, min_confidence=0.7,
            ))
        assert out.meets_threshold is False


# ═════════════════════════════════════════════════════════════════════
# 4. Classify OOV category
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestClassifyOov:

    async def test_unknown_category_becomes_uncertain(self):
        """LLM hallucinates a category outside candidates → coerced
        to 'uncertain' with confidence reset to 0."""
        blocks = [Block(BlockType.TEXT, 0, 0, 50, "text")]
        mock_result = {
            "category":   "completely_made_up_category",
            "confidence": 0.95,
            "reasoning":  "...",
        }
        with patch(
            "ai_orchestrator.reasoning.document_classifier.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await classify_document(ClassifyInput(
                blocks=blocks, enterprise_id=ENT,
                candidates=["contract", "invoice"],
            ))
        assert out.category == "uncertain"
        assert out.confidence == 0.0
        assert out.meets_threshold is False


# ═════════════════════════════════════════════════════════════════════
# 5. JSON fallback parser
# ═════════════════════════════════════════════════════════════════════


class TestJsonFallback:

    def test_clean_json(self):
        out = _parse_json_fallback('{"category": "report", "confidence": 0.8}')
        assert out == {"category": "report", "confidence": 0.8}

    def test_code_fence_json(self):
        text = '```json\n{"category": "invoice", "confidence": 0.7}\n```'
        out = _parse_json_fallback(text)
        assert out["category"] == "invoice"

    def test_wrapped_in_prose(self):
        text = (
            "Đây là kết quả phân loại:\n"
            '{"category": "contract", "confidence": 0.9}\n'
            "Hy vọng giúp ích."
        )
        out = _parse_json_fallback(text)
        assert out["category"] == "contract"

    def test_garbage_returns_empty(self):
        assert _parse_json_fallback("not json at all") == {}

    def test_empty_returns_empty(self):
        assert _parse_json_fallback("") == {}


# ═════════════════════════════════════════════════════════════════════
# 6. ExtractInput + output_schema
# ═════════════════════════════════════════════════════════════════════


class TestExtractSchemaGeneration:

    def test_output_schema_includes_all_required(self):
        cols = [
            ColumnSpec(name="customer_id", type="string",
                       description="Mã KH", required=True),
            ColumnSpec(name="amount", type="number",
                       description="Doanh thu", required=True),
            ColumnSpec(name="notes", type="string",
                       description="Ghi chú", required=False),
        ]
        schema = _output_schema_for(cols)
        rows_schema = schema["properties"]["rows"]["items"]
        assert "customer_id" in rows_schema["required"]
        assert "amount" in rows_schema["required"]
        assert "notes" not in rows_schema["required"]
        assert rows_schema["properties"]["amount"]["type"] == "number"

    def test_date_type_maps_to_string_with_format(self):
        cols = [ColumnSpec(name="signed_at", type="date",
                            description="Ngày ký")]
        schema = _output_schema_for(cols)
        prop = schema["properties"]["rows"]["items"]["properties"]["signed_at"]
        assert prop["type"] == "string"
        assert prop["format"] == "date"

    def test_enum_column(self):
        cols = [ColumnSpec(name="status", type="string",
                            description="Trạng thái",
                            enum=["draft", "approved", "rejected"])]
        schema = _output_schema_for(cols)
        prop = schema["properties"]["rows"]["items"]["properties"]["status"]
        assert prop["enum"] == ["draft", "approved", "rejected"]

    def test_column_brief_includes_required_marker(self):
        cols = [
            ColumnSpec(name="x", type="string", description="X col", required=True),
            ColumnSpec(name="y", type="number", description="Y col", required=False),
        ]
        brief = _column_brief(cols)
        assert "BẮT BUỘC" in brief
        assert "tuỳ chọn" in brief
        assert "X col" in brief and "Y col" in brief


# ═════════════════════════════════════════════════════════════════════
# 7. extract_structured_data — no tables / happy / low confidence
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestExtractStructured:

    @staticmethod
    def _table_block(page: int, md: str = "| Mã KH | Doanh thu |\n|---|---|\n| KH-001 | 1500000 |") -> Block:
        return Block(
            type=BlockType.TABLE, page_idx=page,
            char_start=0, char_end=len(md), text=md,
            metadata={"rows": [["Mã KH", "Doanh thu"], ["KH-001", "1500000"]],
                       "n_rows": 2, "n_cols": 2},
        )

    @staticmethod
    def _cols() -> list[ColumnSpec]:
        return [
            ColumnSpec(name="customer_id", type="string", description="Mã KH"),
            ColumnSpec(name="revenue", type="number", description="Doanh thu"),
        ]

    async def test_no_tables_returns_empty_with_warning(self):
        blocks = [Block(BlockType.TEXT, 0, 0, 50, "just prose")]
        out = await extract_structured_data(ExtractInput(
            blocks=blocks, target_schema=self._cols(),
            enterprise_id=ENT,
        ))
        assert out.rows == []
        assert out.tables_processed == 0
        assert "no_tables_in_input" in out.warnings

    async def test_happy_extracts_rows_with_provenance(self):
        blocks = [
            Block(BlockType.TEXT, 0, 0, 10, "intro"),
            self._table_block(2),
            self._table_block(4),
        ]
        mock_result = {
            "rows": [
                {"customer_id": "KH-001", "revenue": 1500000},
            ],
            "mapping_confidence": 0.95,
            "notes": "Cột bảng map 1-1 với schema.",
        }
        with patch(
            "ai_orchestrator.reasoning.structured_extractor.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await extract_structured_data(ExtractInput(
                blocks=blocks, target_schema=self._cols(),
                enterprise_id=ENT,
            ))
        # 2 tables × 1 row each
        assert out.tables_processed == 2
        assert out.rows_extracted == 2
        # Provenance: source_page_idx matches the block's page
        assert {r.source_page_idx for r in out.rows} == {2, 4}
        # Block id is the index INTO inp.blocks where the table sat
        assert {r.source_block_id for r in out.rows} == {1, 2}
        # Values populated
        assert out.rows[0].values["customer_id"] == "KH-001"

    async def test_low_confidence_adds_warning(self):
        blocks = [self._table_block(0)]
        mock_result = {
            "rows": [{"customer_id": "X", "revenue": 100}],
            "mapping_confidence": 0.4,    # below default 0.6
            "notes": "Phải đoán cột vì header thiếu.",
        }
        with patch(
            "ai_orchestrator.reasoning.structured_extractor.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await extract_structured_data(ExtractInput(
                blocks=blocks, target_schema=self._cols(),
                enterprise_id=ENT,
            ))
        assert out.rows_extracted == 1     # rows still emitted
        assert any("confidence" in w for w in out.warnings)


# ═════════════════════════════════════════════════════════════════════
# 8. extract — per-table failure isolation
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestExtractPerTableFailure:

    async def test_one_table_failure_doesnt_kill_others(self):
        from ai_orchestrator.reasoning.structured_extractor import (
            ColumnSpec, ExtractInput, extract_structured_data,
        )
        md_good = "| A | B |\n|---|---|\n| 1 | 2 |"
        md_bad = "| C | D |\n|---|---|\n| 3 | 4 |"
        blocks = [
            Block(BlockType.TABLE, 0, 0, len(md_good), md_good,
                  {"rows": [["A","B"], ["1","2"]], "n_rows": 2, "n_cols": 2}),
            Block(BlockType.TABLE, 1, 0, len(md_bad), md_bad,
                  {"rows": [["C","D"], ["3","4"]], "n_rows": 2, "n_cols": 2}),
        ]
        cols = [
            ColumnSpec(name="x", type="string", description="X"),
            ColumnSpec(name="y", type="number", description="Y"),
        ]

        # First call returns good rows; second call raises.
        call_count = {"n": 0}
        async def _mock_call(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {
                    "rows": [{"x": "1", "y": 2}],
                    "mapping_confidence": 0.9,
                    "notes": "ok",
                }
            raise RuntimeError("LLM timeout")

        with patch(
            "ai_orchestrator.reasoning.structured_extractor.llm_router",
            complete_with_schema=AsyncMock(side_effect=_mock_call),
        ):
            out = await extract_structured_data(ExtractInput(
                blocks=blocks, target_schema=cols, enterprise_id=ENT,
            ))
        # Page 0 succeeded, page 1 failed with warning
        assert out.rows_extracted == 1
        assert any("trang 2" in w.lower() for w in out.warnings)
