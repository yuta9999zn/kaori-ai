"""
Unit tests for framework_router.py — K-10 deterministic framework selection.
Run: pytest services/ai-orchestrator/tests/test_framework_router.py -v
"""
import pytest
from ai_orchestrator.agents.framework_router import route_framework, FRAMEWORK_PROMPTS


# ── route_framework: keyword matching ─────────────────────────────────────────

class TestRouteFramework:

    def test_5why_vietnamese(self):
        assert route_framework("Tại sao doanh thu giảm?") == "5why"

    def test_5why_english(self):
        assert route_framework("Why did sales drop in Q3?") == "5why"

    def test_5why_root_cause(self):
        assert route_framework("Tìm nguyên nhân gốc rễ của vấn đề này") == "5why"

    def test_fishbone_factors(self):
        assert route_framework("Những yếu tố nào ảnh hưởng đến chất lượng?") == "fishbone"

    def test_fishbone_causes(self):
        assert route_framework("Nguyên nhân nào gây ra tình trạng này?") == "fishbone"

    def test_swot_direct(self):
        assert route_framework("Phân tích SWOT cho chiến lược mới") == "swot"

    def test_swot_strength(self):
        assert route_framework("Điểm mạnh của sản phẩm so với đối thủ?") == "swot"

    def test_swot_english_keyword(self):
        assert route_framework("What are our strengths and weaknesses?") == "swot"

    def test_mom_compare_vietnamese(self):
        assert route_framework("So sánh doanh thu tháng này với tháng trước") == "mom_compare"

    def test_mom_compare_english(self):
        assert route_framework("MoM comparison for user acquisition") == "mom_compare"

    def test_5w1h_who(self):
        assert route_framework("Ai chịu trách nhiệm cho khu vực miền Nam?") == "5w1h"

    def test_5w1h_what(self):
        assert route_framework("Cái gì làm cho khách hàng hài lòng nhất?") == "5w1h"

    def test_default_no_keyword(self):
        assert route_framework("Hãy phân tích dữ liệu này cho tôi") == "5w1h"

    def test_default_empty(self):
        assert route_framework("") == "5w1h"

    def test_case_insensitive(self):
        assert route_framework("WHY is revenue declining?") == "5why"
        assert route_framework("SWOT analysis please") == "swot"

    # ── Priority order: 5why > fishbone > swot > mom_compare > 5w1h ────────────

    def test_priority_5why_over_fishbone(self):
        # Contains both "tại sao" (5why) and "vấn đề" (fishbone) — 5why wins
        assert route_framework("Tại sao vấn đề này xảy ra liên tục?") == "5why"

    def test_priority_fishbone_over_swot(self):
        # Contains "nguyên nhân nào" (fishbone) and "chiến lược" (swot) — fishbone wins
        assert route_framework("Nguyên nhân nào ảnh hưởng đến chiến lược?") == "fishbone"

    # ── Edge cases for the longest-match algorithm ──────────────────────────────

    def test_specific_keyword_beats_substring(self):
        """Edge: when a longer fishbone phrase fully contains a 5why phrase
        (e.g. 'nguyên nhân nào' contains 'nguyên nhân'), the more specific
        framework wins regardless of priority order."""
        assert route_framework("Nguyên nhân nào quan trọng nhất?") == "fishbone"

    def test_tie_resolves_to_higher_priority(self):
        """Edge: when two keywords have identical length, the framework
        listed earlier in the priority order wins (5why > fishbone)."""
        # Both "tại sao" (5why, 7) and "vấn đề" (fishbone, 7) match, equal length.
        assert route_framework("Tại sao vấn đề diễn ra?") == "5why"

    def test_multiple_long_keywords_pick_longest(self):
        """Edge: among several matches the absolute longest keyword wins,
        even if it is in a lower-priority framework."""
        # "tháng trước" (mom, 11) vs "swot" (4) vs "what" (4)
        assert route_framework("So sánh chiến lược tháng trước có gì đổi không?") == "mom_compare"

    def test_priority_swot_over_mom(self):
        # Contains "điểm mạnh" (swot) and "so sánh" (mom) — swot wins
        assert route_framework("So sánh điểm mạnh của hai phương án") == "swot"

    def test_priority_mom_over_5w1h(self):
        # Contains "tuần trước" (mom) — mom wins over default 5w1h
        assert route_framework("Dữ liệu tuần trước thay đổi thế nào?") == "mom_compare"


# ── FRAMEWORK_PROMPTS: template formatting ────────────────────────────────────

class TestFrameworkPrompts:

    def test_all_frameworks_have_prompts(self):
        for fw in ("5why", "fishbone", "swot", "5w1h", "mom_compare"):
            assert fw in FRAMEWORK_PROMPTS, f"Missing prompt for {fw}"

    def test_prompts_have_placeholders(self):
        for fw, prompt in FRAMEWORK_PROMPTS.items():
            assert "{question}" in prompt, f"{fw} missing {{question}} placeholder"
            assert "{data_context}" in prompt, f"{fw} missing {{data_context}} placeholder"

    def test_prompts_are_nonempty(self):
        for fw, prompt in FRAMEWORK_PROMPTS.items():
            assert len(prompt.strip()) > 50, f"{fw} prompt too short"

    def test_prompt_formatting(self):
        prompt = FRAMEWORK_PROMPTS["5why"].format(
            question="Tại sao doanh thu giảm?",
            data_context="Doanh thu tháng 3: 500M, tháng 4: 420M (-16%)",
        )
        assert "Tại sao doanh thu giảm?" in prompt
        assert "500M" in prompt

    @pytest.mark.parametrize("fw", ["5why", "fishbone", "swot", "5w1h", "mom_compare"])
    def test_each_prompt_formats_cleanly(self, fw):
        result = FRAMEWORK_PROMPTS[fw].format(
            question="test question",
            data_context="test context",
        )
        assert "test question" in result
        assert "test context" in result
