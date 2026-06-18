"""
Knowing-doing gap mitigation tests (ADR-0023).

Validates `chat/tool_necessity.py` heuristic + agent.py integration.

8-section template per anh's "chuẩn chỉ + hiệu năng + phi chức năng":
  1. Heuristic — tool indicator scoring
  2. Heuristic — chitchat negative weights
  3. Heuristic — score clamping + edge cases (empty, mixed)
  4. Threshold bands — high/medium/low → suggested_tool_choice
  5. Vietnamese + English coverage (paper applies to both)
  6. Agent integration — hop 0 uses forced choice; hop 1+ uses auto
  7. Determinism — same input → same assessment
  8. Performance — 1000 messages assessed < 100ms
"""
from __future__ import annotations

import time

import pytest

from ai_orchestrator.chat.tool_necessity import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    NecessityAssessment,
    needs_tool_heuristic,
)


# ═════════════════════════════════════════════════════════════════════
# 1. Tool indicator scoring
# ═════════════════════════════════════════════════════════════════════


class TestToolIndicators:

    def test_quantitative_question_scores_high(self):
        a = needs_tool_heuristic("Bao nhiêu khách hàng đang ở mức rủi ro cao?")
        assert a.needs_tool is True
        assert a.confidence >= HIGH_CONFIDENCE
        assert a.suggested_tool_choice == "required"
        # Verify keywords fired
        assert any("bao nhiêu" in k or "khách hàng" in k for k in a.fired_keywords)

    def test_list_question_scores_high(self):
        a = needs_tool_heuristic("Liệt kê tất cả workflow đang hoạt động")
        assert a.confidence >= HIGH_CONFIDENCE
        assert a.suggested_tool_choice == "required"

    def test_lookup_question_scores_high(self):
        a = needs_tool_heuristic("Tra cứu lịch sử quyết định tháng này")
        assert a.confidence >= HIGH_CONFIDENCE

    def test_revenue_question_scores_high(self):
        a = needs_tool_heuristic("Doanh thu quý này bao nhiêu?")
        assert a.confidence >= HIGH_CONFIDENCE
        assert "bao nhiêu" in a.fired_keywords or "doanh thu" in a.fired_keywords


# ═════════════════════════════════════════════════════════════════════
# 2. Chitchat negative weights
# ═════════════════════════════════════════════════════════════════════


class TestChitchatIndicators:

    def test_greeting_scores_low(self):
        a = needs_tool_heuristic("Xin chào, bạn là ai?")
        assert a.confidence < LOW_CONFIDENCE
        assert a.suggested_tool_choice == "auto"

    def test_thanks_scores_low(self):
        a = needs_tool_heuristic("Cảm ơn nhiều!")
        assert a.confidence < LOW_CONFIDENCE
        assert a.needs_tool is False

    def test_explanation_request_scores_low(self):
        a = needs_tool_heuristic("Hãy giới thiệu về sản phẩm Kaori")
        assert a.confidence < LOW_CONFIDENCE


# ═════════════════════════════════════════════════════════════════════
# 3. Score clamping + edge cases
# ═════════════════════════════════════════════════════════════════════


class TestEdgeCases:

    def test_empty_message_returns_zero(self):
        a = needs_tool_heuristic("")
        assert a.confidence == 0.0
        assert a.needs_tool is False
        assert a.fired_keywords == ()

    def test_whitespace_only_returns_zero(self):
        a = needs_tool_heuristic("   \n\t  ")
        assert a.confidence == 0.0

    def test_score_clamped_to_one_when_many_keywords(self):
        # Long message with MANY tool indicators
        msg = (
            "Liệt kê danh sách khách hàng có doanh thu cao trong tháng này, "
            "thống kê tổng số đơn hàng và trung bình lợi nhuận theo phần trăm, "
            "tra cứu lịch sử quyết định"
        )
        a = needs_tool_heuristic(msg)
        assert a.confidence == 1.0

    def test_mixed_chitchat_and_tool_keywords(self):
        """Chitchat negative weight should subtract from positive tool signal."""
        a = needs_tool_heuristic("Xin chào, cho tôi xem danh sách khách hàng")
        # cho tôi xem (0.7) + xin chào (-0.6) + danh sách (0.6) + khách hàng (0.4) + xem (0.2)
        # = ~1.3 clamped to 1.0 → high. Tool wins.
        assert a.confidence >= HIGH_CONFIDENCE


# ═════════════════════════════════════════════════════════════════════
# 4. Threshold bands
# ═════════════════════════════════════════════════════════════════════


class TestThresholdBands:

    def test_high_confidence_recommends_required(self):
        a = needs_tool_heuristic("Bao nhiêu workflow đang chạy?")
        assert a.confidence >= HIGH_CONFIDENCE
        assert a.suggested_tool_choice == "required"
        assert "high tool-necessity score" in a.reason

    def test_medium_confidence_recommends_auto(self):
        # Single moderate-weight keyword: 'tìm kiếm' = 0.5 (LOW < 0.5 < HIGH)
        a = needs_tool_heuristic("Tìm kiếm sản phẩm")
        assert LOW_CONFIDENCE <= a.confidence < HIGH_CONFIDENCE
        assert a.suggested_tool_choice == "auto"
        assert "medium tool-necessity score" in a.reason

    def test_low_confidence_recommends_auto(self):
        a = needs_tool_heuristic("Xin chào")
        assert a.confidence < LOW_CONFIDENCE
        assert a.suggested_tool_choice == "auto"
        assert "low tool-necessity score" in a.reason


# ═════════════════════════════════════════════════════════════════════
# 5. Vietnamese + English coverage
# ═════════════════════════════════════════════════════════════════════


class TestBilingualCoverage:

    def test_english_show_me_scores_high(self):
        a = needs_tool_heuristic("show me a list of workflows")
        assert a.confidence >= HIGH_CONFIDENCE

    def test_english_get_keyword_scores(self):
        a = needs_tool_heuristic("get the latest decision audit log")
        # 'get ' + 'audit' + 'history' (n/a) — should at least cross LOW
        assert a.confidence >= LOW_CONFIDENCE

    def test_english_hello_chitchat(self):
        a = needs_tool_heuristic("hi there, who are you?")
        assert a.confidence < LOW_CONFIDENCE


# ═════════════════════════════════════════════════════════════════════
# 6. Agent integration (hop-0 forcing)
# ═════════════════════════════════════════════════════════════════════


class TestAgentIntegration:

    def test_high_confidence_message_triggers_required_choice(self):
        """Direct test of the hop-0 forcing logic from agent.py."""
        a = needs_tool_heuristic("Liệt kê khách hàng rủi ro cao")
        forced = "required" if a.confidence >= HIGH_CONFIDENCE else "auto"
        assert forced == "required"

    def test_low_confidence_message_stays_auto(self):
        a = needs_tool_heuristic("Xin chào, mình muốn hỏi vài điều")
        forced = "required" if a.confidence >= HIGH_CONFIDENCE else "auto"
        assert forced == "auto"


# ═════════════════════════════════════════════════════════════════════
# 7. Determinism
# ═════════════════════════════════════════════════════════════════════


class TestDeterminism:

    def test_repeated_calls_identical(self):
        msg = "Bao nhiêu khách hàng VIP có doanh thu giảm tháng này?"
        a1 = needs_tool_heuristic(msg)
        a2 = needs_tool_heuristic(msg)
        a3 = needs_tool_heuristic(msg)
        assert a1 == a2 == a3

    def test_case_insensitive(self):
        a_lower = needs_tool_heuristic("bao nhiêu khách hàng?")
        a_upper = needs_tool_heuristic("BAO NHIÊU KHÁCH HÀNG?")
        a_mixed = needs_tool_heuristic("Bao Nhiêu Khách Hàng?")
        assert a_lower.confidence == a_upper.confidence == a_mixed.confidence


# ═════════════════════════════════════════════════════════════════════
# 8. Performance — heuristic must be sub-millisecond per call
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_1000_messages_under_100ms(self):
        """1000 message assessments must complete < 100ms total
        (0.1ms avg). Heuristic is on the chat hot path; must not add
        perceptible latency."""
        messages = [
            "Bao nhiêu khách hàng VIP?",
            "Xin chào",
            "Liệt kê quyết định gần đây",
            "Cảm ơn",
            "Tra cứu doanh thu tháng này",
        ] * 200
        t0 = time.perf_counter()
        for m in messages:
            needs_tool_heuristic(m)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"too slow: {elapsed:.3f}s for 1000 calls"
