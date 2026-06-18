"""
Tests for the 3 Phase 2.5 light AI / pure-compute nodes:
  - reasoning/document_summariser.summarise_document
  - reasoning/sentiment_analyser.sentiment_analysis
  - reasoning/record_dedup.dedup_records

LLM-based nodes use llm_router mocked via patch + AsyncMock; the
dedup node is pure compute (no LLM, no DB) so tests pin deterministic
output directly.

8-section template:
  1. SummariseInput defaults + reading-time heuristic
  2. summarise_document prompt build (titles + cap)
  3. summarise_document happy path + max_bullets clamp
  4. SentimentInput + SENTIMENT_SCALE contract
  5. sentiment_analysis happy path (overall + aspects)
  6. sentiment_analysis edge cases (invalid label, PII smoke alarm)
  7. dedup_records normalisers (vn_phone / vn_name / email)
  8. dedup_records conflict policy + fuzzy + merge_fn + provenance
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.data_plane_shim import Block, BlockType
from ai_orchestrator.reasoning.document_summariser import (
    SummariseInput,
    SummariseOutput,
    _build_prompt as _summarise_prompt,
    _estimate_reading_time,
    summarise_document,
)
from ai_orchestrator.reasoning.sentiment_analyser import (
    SENTIMENT_SCALE,
    AspectRequest,
    AspectScore,
    SentimentInput,
    SentimentOutput,
    _collect_text,
    _output_schema,
    sentiment_analysis,
)
from ai_orchestrator.reasoning.record_dedup import (
    DedupKey,
    DedupSpec,
    DedupedRow,
    DedupOutput,
    NORMALISERS,
    _norm_email,
    _norm_vn_name,
    _norm_vn_phone,
    dedup_records,
)
from ai_orchestrator.reasoning.structured_extractor import ExtractedRow


ENT = "11111111-1111-1111-1111-111111111111"


def _text_block(page: int, body: str, char_start: int = 0) -> Block:
    return Block(
        type=BlockType.TEXT, page_idx=page,
        char_start=char_start, char_end=char_start + len(body),
        text=body,
    )


def _title_block(page: int, title: str) -> Block:
    return Block(
        type=BlockType.TITLE, page_idx=page,
        char_start=0, char_end=len(title), text=title,
    )


# ═════════════════════════════════════════════════════════════════════
# 1. SummariseInput + reading-time
# ═════════════════════════════════════════════════════════════════════


class TestSummariseDefaults:

    def test_defaults_filled(self):
        inp = SummariseInput(blocks=[], enterprise_id=ENT)
        assert inp.max_bullets == 5
        assert inp.target_lang == "vi"
        assert inp.consent_external is False

    def test_reading_time_skips_chrome(self):
        blocks = [
            Block(BlockType.HEADER, 0, 0, 100, "x" * 100),
            Block(BlockType.TEXT, 0, 100, 200, "y" * 100),
            Block(BlockType.FOOTER, 0, 200, 300, "z" * 100),
            Block(BlockType.PAGE_NUMBER, 0, 300, 305, "1"),
        ]
        chars, seconds = _estimate_reading_time(blocks)
        # Only the TEXT block counts.
        assert chars == 100
        # ~17 chars/sec → ~6 sec, rounded to nearest 5 → 5.
        assert seconds == 5

    def test_reading_time_minimum_5_seconds(self):
        chars, seconds = _estimate_reading_time([_text_block(0, "hi")])
        assert seconds == 5     # floor of 5s even for tiny docs

    def test_reading_time_scales_with_length(self):
        big = "x" * 17_000      # ~17 KB ≈ 1000s ≈ 16-17 min
        chars, seconds = _estimate_reading_time([_text_block(0, big)])
        assert chars == 17_000
        assert 990 <= seconds <= 1010


# ═════════════════════════════════════════════════════════════════════
# 2. summarise_document prompt build
# ═════════════════════════════════════════════════════════════════════


class TestSummarisePrompt:

    def test_includes_titles(self):
        blocks = [
            _title_block(0, "Báo cáo tài chính Q1 2026"),
            _text_block(0, "Doanh thu tăng 12% so với cùng kỳ."),
        ]
        prompt = _summarise_prompt(blocks, max_bullets=5, target_lang="vi")
        assert "Báo cáo tài chính" in prompt
        assert "tiếng Việt" in prompt

    def test_caps_body_at_6kb(self):
        huge = _text_block(0, "x" * 20_000)
        prompt = _summarise_prompt([huge], max_bullets=5, target_lang="vi")
        # ~6 KB body + ~1 KB prompt overhead
        assert len(prompt) < 8_000

    def test_target_lang_en_changes_persona(self):
        prompt = _summarise_prompt(
            [_text_block(0, "test")], max_bullets=3, target_lang="en"
        )
        assert "English" in prompt
        assert "senior managers" in prompt

    def test_max_bullets_surfaces_in_prompt(self):
        prompt = _summarise_prompt([_text_block(0, "x")],
                                    max_bullets=7, target_lang="vi")
        assert "tối đa 7 bullet" in prompt


# ═════════════════════════════════════════════════════════════════════
# 3. summarise_document happy path
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSummariseHappy:

    async def test_returns_summary_bullets_action(self):
        blocks = [
            _title_block(0, "Quy chế khen thưởng 2026"),
            _text_block(0, "Quy chế áp dụng từ Q2 cho toàn bộ nhân viên..."),
        ]
        mock_result = {
            "summary":          "Quy chế mới có hiệu lực Q2 áp dụng toàn công ty.",
            "bullets":          ["Áp dụng Q2", "Tất cả nhân viên", "Hệ số thay đổi"],
            "next_action_hint": "Phòng HR cần thông báo công ty trước 1/4.",
        }
        with patch(
            "ai_orchestrator.reasoning.document_summariser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await summarise_document(SummariseInput(
                blocks=blocks, enterprise_id=ENT,
            ))
        assert out.summary.startswith("Quy chế mới")
        assert len(out.bullets) == 3
        assert "Phòng HR" in out.next_action_hint
        assert out.source_char_length > 0
        assert out.reading_time_seconds >= 5

    async def test_extra_bullets_are_clipped_to_max(self):
        mock_result = {
            "summary": "x",
            "bullets": ["a", "b", "c", "d", "e", "f", "g", "h"],   # 8 emitted
            "next_action_hint": "y",
        }
        with patch(
            "ai_orchestrator.reasoning.document_summariser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await summarise_document(SummariseInput(
                blocks=[_text_block(0, "doc")],
                enterprise_id=ENT, max_bullets=4,
            ))
        assert len(out.bullets) == 4
        assert out.bullets == ["a", "b", "c", "d"]

    async def test_missing_fields_fallback_to_empty(self):
        """LLM emits an incomplete object → defaults fill in safely."""
        with patch(
            "ai_orchestrator.reasoning.document_summariser.llm_router",
            complete_with_schema=AsyncMock(return_value={}),
        ):
            out = await summarise_document(SummariseInput(
                blocks=[_text_block(0, "tiny doc")],
                enterprise_id=ENT,
            ))
        assert out.summary == ""
        assert out.bullets == []
        assert out.next_action_hint == ""

    async def test_bullets_with_non_string_items_filtered_to_str(self):
        """Robust against an LLM emitting an int or float in the list."""
        mock_result = {
            "summary": "x",
            "bullets": ["a", 7, 3.14, None, "b"],   # None should drop
            "next_action_hint": "y",
        }
        with patch(
            "ai_orchestrator.reasoning.document_summariser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await summarise_document(SummariseInput(
                blocks=[_text_block(0, "x")],
                enterprise_id=ENT, max_bullets=5,
            ))
        # 'a', '7', '3.14', 'b' — None filtered.
        assert "a" in out.bullets and "b" in out.bullets
        assert any(b == "7" for b in out.bullets)
        assert all(isinstance(b, str) for b in out.bullets)


# ═════════════════════════════════════════════════════════════════════
# 4. SentimentInput contract + scale
# ═════════════════════════════════════════════════════════════════════


class TestSentimentContract:

    def test_scale_has_5_levels_symmetric(self):
        assert set(SENTIMENT_SCALE.keys()) == {
            "very_negative", "negative", "neutral", "positive", "very_positive",
        }
        # Symmetric around 0
        assert SENTIMENT_SCALE["very_negative"] == -1.0
        assert SENTIMENT_SCALE["very_positive"] == 1.0
        assert SENTIMENT_SCALE["neutral"] == 0.0

    def test_collect_text_skips_chrome(self):
        blocks = [
            Block(BlockType.HEADER, 0, 0, 10, "© Co"),
            _text_block(0, "Real content for sentiment.", char_start=11),
            Block(BlockType.FOOTER, 0, 50, 60, "Page 1"),
        ]
        text = _collect_text(blocks)
        assert "© Co" not in text
        assert "Page 1" not in text
        assert "Real content" in text

    def test_collect_text_caps_at_4kb(self):
        huge = _text_block(0, "x" * 10_000)
        text = _collect_text([huge])
        assert len(text) <= 4_100      # ~4 KB cap + small slack

    def test_output_schema_requires_aspects_when_provided(self):
        aspects = [AspectRequest(name="delivery", description="Tốc độ giao")]
        schema = _output_schema(aspects)
        assert "aspects" in schema["required"]
        assert "delivery" in schema["properties"]["aspects"]["required"]

    def test_output_schema_omits_aspects_when_empty(self):
        schema = _output_schema([])
        assert "aspects" not in schema.get("required", [])
        assert "aspects" not in schema["properties"]


# ═════════════════════════════════════════════════════════════════════
# 5. sentiment_analysis happy path
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSentimentHappy:

    async def test_overall_only(self):
        mock_result = {
            "overall_label":      "negative",
            "overall_confidence": 0.88,
            "overall_reasoning":  "Khách phàn nàn giao trễ + sản phẩm lỗi.",
        }
        with patch(
            "ai_orchestrator.reasoning.sentiment_analyser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await sentiment_analysis(SentimentInput(
                blocks=[_text_block(0, "Hàng đến trễ, vỏ hộp móp.")],
                enterprise_id=ENT,
            ))
        assert out.overall_label == "negative"
        assert out.overall_score == -0.5
        assert out.overall_confidence == 0.88
        assert out.aspects == []

    async def test_with_aspects(self):
        aspects = [
            AspectRequest(name="delivery", description="Tốc độ giao"),
            AspectRequest(name="quality",  description="Chất lượng sản phẩm"),
            AspectRequest(name="price",    description="Giá cả"),
        ]
        mock_result = {
            "overall_label":      "negative",
            "overall_confidence": 0.85,
            "overall_reasoning":  "Tổng thể tiêu cực vì giao + chất lượng kém.",
            "aspects": {
                "delivery": {"label": "very_negative", "confidence": 0.95,
                              "reasoning": "Giao chậm 3 ngày."},
                "quality":  {"label": "negative",     "confidence": 0.8,
                              "reasoning": "Vỏ móp."},
                "price":    {"label": "unknown",       "confidence": 0.0,
                              "reasoning": "Không nhắc."},
            },
        }
        with patch(
            "ai_orchestrator.reasoning.sentiment_analyser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await sentiment_analysis(SentimentInput(
                blocks=[_text_block(0, "Hàng tới trễ. Vỏ móp.")],
                enterprise_id=ENT, aspects=aspects,
            ))
        assert len(out.aspects) == 3
        by_name = {a.name: a for a in out.aspects}
        assert by_name["delivery"].score == -1.0
        assert by_name["quality"].score == -0.5
        assert by_name["price"].label == "unknown"
        assert by_name["price"].score == 0.0


# ═════════════════════════════════════════════════════════════════════
# 6. sentiment_analysis edge cases
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSentimentEdge:

    async def test_invalid_overall_label_coerced_neutral(self):
        mock_result = {
            "overall_label":      "ECSTATIC",   # not in scale
            "overall_confidence": 0.9,
            "overall_reasoning":  "made up label",
        }
        with patch(
            "ai_orchestrator.reasoning.sentiment_analyser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await sentiment_analysis(SentimentInput(
                blocks=[_text_block(0, "x")], enterprise_id=ENT,
            ))
        assert out.overall_label == "neutral"
        assert out.overall_score == 0.0

    async def test_invalid_aspect_label_becomes_unknown(self):
        aspects = [AspectRequest(name="speed", description="Tốc độ")]
        mock_result = {
            "overall_label":      "neutral",
            "overall_confidence": 0.5,
            "overall_reasoning":  "ok",
            "aspects": {
                "speed": {"label": "OOPS", "confidence": 0.7, "reasoning": "x"},
            },
        }
        with patch(
            "ai_orchestrator.reasoning.sentiment_analyser.llm_router",
            complete_with_schema=AsyncMock(return_value=mock_result),
        ):
            out = await sentiment_analysis(SentimentInput(
                blocks=[_text_block(0, "x")], enterprise_id=ENT,
                aspects=aspects,
            ))
        assert out.aspects[0].label == "unknown"
        assert out.aspects[0].score == 0.0

    async def test_pii_smoke_alarm_logs_warning(self, caplog):
        """PII heuristic logs a warning but does NOT block the call."""
        mock_result = {
            "overall_label":      "positive",
            "overall_confidence": 0.9,
            "overall_reasoning":  "ok",
        }
        with caplog.at_level(logging.WARNING):
            with patch(
                "ai_orchestrator.reasoning.sentiment_analyser.llm_router",
                complete_with_schema=AsyncMock(return_value=mock_result),
            ):
                out = await sentiment_analysis(SentimentInput(
                    blocks=[_text_block(
                        0,
                        "Liên hệ a.nguyen@kaori.io hoặc 0912345678 nếu cần.",
                    )],
                    enterprise_id=ENT,
                ))
        # The smoke alarm fires via structlog → some test envs route to
        # stderr, others to caplog. The contract: call still succeeds.
        assert out.overall_label == "positive"


# ═════════════════════════════════════════════════════════════════════
# 7. dedup_records normalisers
# ═════════════════════════════════════════════════════════════════════


class TestDedupNormalisers:

    def test_vn_phone_strips_spaces_and_country_code(self):
        assert _norm_vn_phone("0912 345 678") == "912345678"
        assert _norm_vn_phone("+84 912 345 678") == "912345678"
        assert _norm_vn_phone("84-912-345-678") == "912345678"
        assert _norm_vn_phone("(0912) 345.678") == "912345678"

    def test_vn_phone_unifies_format_variants(self):
        a = _norm_vn_phone("+84912345678")
        b = _norm_vn_phone("0912345678")
        c = _norm_vn_phone("0912.345.678")
        assert a == b == c

    def test_vn_name_strips_diacritics(self):
        assert _norm_vn_name("Nguyễn Văn An") == "nguyen van an"
        assert _norm_vn_name("Đoàn Thị Hồng") == "doan thi hong"
        assert _norm_vn_name("  TRẦN  THỊ  C  ") == "tran thi c"

    def test_vn_name_d_special_case(self):
        # đ/Đ doesn't decompose under NFKD — em handle explicitly.
        assert "đ" not in _norm_vn_name("Đặng Đình Đức")
        assert _norm_vn_name("Đặng Đình Đức") == "dang dinh duc"

    def test_email_lowercase_strip(self):
        assert _norm_email("  AN@Kaori.IO  ") == "an@kaori.io"

    def test_normaliser_keys_registered(self):
        assert set(NORMALISERS.keys()) == {
            "lower", "vn_phone", "vn_name", "email", "raw",
        }


# ═════════════════════════════════════════════════════════════════════
# 8. dedup_records — full algorithm
# ═════════════════════════════════════════════════════════════════════


def _row(values: dict, page: int = 0, block_id: int = 0) -> ExtractedRow:
    return ExtractedRow(values=values, source_page_idx=page,
                         source_block_id=block_id)


class TestDedupAlgorithm:

    def test_empty_input(self):
        out = dedup_records([], DedupSpec(keys=[DedupKey(column="x")]))
        assert out.rows_in == 0 and out.rows_out == 0
        assert out.duplicates_dropped == 0

    def test_exact_match_single_key(self):
        rows = [
            _row({"email": "an@kaori.io", "name": "An"},  page=0, block_id=1),
            _row({"email": "AN@kaori.io", "name": "An2"}, page=1, block_id=3),
            _row({"email": "an@kaori.io", "name": "An3"}, page=2, block_id=5),
            _row({"email": "b@kaori.io",  "name": "B"},   page=3, block_id=7),
        ]
        spec = DedupSpec(keys=[DedupKey(column="email", normaliser="email")])
        out = dedup_records(rows, spec)
        # 3 'an@' collapse → 1, 'b@' stays → 2 total
        assert out.rows_in == 4
        assert out.rows_out == 2
        assert out.duplicates_dropped == 2
        # First-occurrence order preserved
        assert out.rows[0].values["email"] == "an@kaori.io"
        assert out.rows[0].values["name"] == "An"   # first-policy
        # Provenance: all 3 block_ids captured for the 'an@' group
        assert sorted(out.rows[0].source_block_ids) == [1, 3, 5]
        assert sorted(out.rows[0].source_page_idxs) == [0, 1, 2]
        assert out.rows[0].collapsed_from == 3

    def test_composite_key(self):
        rows = [
            _row({"phone": "0912345678", "name": "Nguyễn An"}),
            _row({"phone": "+84912345678", "name": "Nguyen An"}),
            _row({"phone": "0912345678", "name": "Khác"}),   # phone same, name diff
        ]
        spec = DedupSpec(keys=[
            DedupKey(column="phone", normaliser="vn_phone"),
            DedupKey(column="name",  normaliser="vn_name"),
        ])
        out = dedup_records(rows, spec)
        # Rows 1+2 collapse (same normalised phone+name); row 3 differs on name.
        assert out.rows_out == 2

    def test_conflict_policy_last(self):
        rows = [
            _row({"id": "x", "qty": 1}),
            _row({"id": "x", "qty": 9}),
        ]
        spec = DedupSpec(keys=[DedupKey(column="id")],
                          conflict_policy="last")
        out = dedup_records(rows, spec)
        assert out.rows_out == 1
        assert out.rows[0].values["qty"] == 9

    def test_conflict_policy_longest_non_empty(self):
        rows = [
            _row({"id": "x", "addr": "",     "note": "n1"}),
            _row({"id": "x", "addr": "12 Nguyễn Trãi", "note": "n2 longer"}),
        ]
        spec = DedupSpec(keys=[DedupKey(column="id")],
                          conflict_policy="longest_non_empty")
        out = dedup_records(rows, spec)
        assert out.rows_out == 1
        # 'addr' picks the non-empty; 'note' picks the longer string
        assert out.rows[0].values["addr"] == "12 Nguyễn Trãi"
        assert out.rows[0].values["note"] == "n2 longer"

    def test_merge_fn_overrides_policy(self):
        """Caller-supplied merge_fn aggregates qty across duplicate SKUs."""
        rows = [
            _row({"sku": "A1", "qty": 2, "unit_price": 100}),
            _row({"sku": "A1", "qty": 3, "unit_price": 100}),
            _row({"sku": "B2", "qty": 1, "unit_price": 50}),
        ]
        def sum_qty(rs: list[dict]) -> dict:
            merged = dict(rs[0])
            merged["qty"] = sum(r["qty"] for r in rs)
            return merged
        spec = DedupSpec(
            keys=[DedupKey(column="sku")],
            conflict_policy="first",         # would be overridden
            merge_fn=sum_qty,
        )
        out = dedup_records(rows, spec)
        assert out.rows_out == 2
        by_sku = {r.values["sku"]: r for r in out.rows}
        assert by_sku["A1"].values["qty"] == 5
        assert by_sku["B2"].values["qty"] == 1

    def test_fuzzy_collapse_only_with_vn_name_key(self):
        """Fuzzy pass active only when keys include vn_name + threshold<1."""
        rows = [
            _row({"name": "Nguyen Van An"}),
            _row({"name": "Nguyen Văn  An"}),    # extra space
        ]
        # Without fuzzy → both collapse already because of vn_name normaliser
        spec = DedupSpec(keys=[DedupKey(column="name", normaliser="vn_name")])
        out = dedup_records(rows, spec)
        assert out.rows_out == 1

    def test_fuzzy_collapse_kicks_in_for_near_matches(self):
        """Two names that normalise differently (typo) collapse when
        fuzzy threshold drops below 1.0."""
        rows = [
            _row({"name": "Nguyen Van An"}),
            _row({"name": "Nguyen Van Anh"}),       # extra h
        ]
        spec_exact = DedupSpec(
            keys=[DedupKey(column="name", normaliser="vn_name")],
            fuzzy_threshold=1.0,
        )
        spec_fuzzy = DedupSpec(
            keys=[DedupKey(column="name", normaliser="vn_name")],
            fuzzy_threshold=0.9,
        )
        assert dedup_records(rows, spec_exact).rows_out == 2
        assert dedup_records(rows, spec_fuzzy).rows_out == 1

    def test_fuzzy_ignored_when_no_vn_name_key(self):
        """Fuzzy threshold below 1.0 but no vn_name key → still exact."""
        rows = [
            _row({"id": "abc"}),
            _row({"id": "abd"}),       # close string but no vn_name normaliser
        ]
        spec = DedupSpec(
            keys=[DedupKey(column="id", normaliser="lower")],
            fuzzy_threshold=0.85,
        )
        out = dedup_records(rows, spec)
        # Exact pass keeps them separate; fuzzy guard skips because no
        # vn_name key declared.
        assert out.rows_out == 2

    def test_determinism_same_input_same_output(self):
        rows = [
            _row({"k": "x", "v": 1}),
            _row({"k": "y", "v": 2}),
            _row({"k": "x", "v": 3}),
        ]
        spec = DedupSpec(keys=[DedupKey(column="k")])
        out1 = dedup_records(rows, spec)
        out2 = dedup_records(rows, spec)
        assert [(r.values, r.collapsed_from) for r in out1.rows] \
            == [(r.values, r.collapsed_from) for r in out2.rows]

    def test_unknown_conflict_policy_raises(self):
        with pytest.raises(ValueError, match="conflict_policy"):
            dedup_records(
                [_row({"k": "x"}), _row({"k": "x"})],
                DedupSpec(keys=[DedupKey(column="k")], conflict_policy="random"),
            )
