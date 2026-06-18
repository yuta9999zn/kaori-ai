"""CR-0018 — grounding self-verify (number-overlap |OR|) unit tests."""
from ai_orchestrator.reasoning.grounding import (
    Grounding, collect_facts, disclaimer_for, extract_claims, ground_claims,
)


class TestExtractClaims:
    def test_integers_and_decimals(self):
        assert extract_claims("doanh thu 100 và tỷ lệ 3.5") == [100.0, 3.5]

    def test_vn_thousands_and_percent(self):
        c = extract_claims("tăng 85% lên 1.000.000")
        assert 85.0 in c and 1000000.0 in c

    def test_en_thousands_decimal(self):
        assert 1234.56 in extract_claims("total 1,234.56")

    def test_no_numbers(self):
        assert extract_claims("không có số nào ở đây") == []


class TestCollectFacts:
    def test_walks_nested_blocks(self):
        payload = {"blocks": [{"value": 100}, {"rows": [{"rev": 250.0}, "ghi chú 7"]}]}
        facts = collect_facts(payload)
        assert 100.0 in facts and 250.0 in facts and 7.0 in facts

    def test_ignores_booleans(self):
        assert collect_facts({"ok": True, "n": 5}) == [5.0]


class TestGroundClaims:
    def test_all_grounded_scores_one(self):
        g = ground_claims("doanh thu 100, lợi nhuận 20", [100.0, 20.0, 5.0])
        assert g.score == 1.0 and g.flagged == []

    def test_fabricated_number_flagged(self):
        g = ground_claims("tăng trưởng 500", [100.0, 20.0])
        assert 500.0 in g.flagged and g.score < 1.0

    def test_no_claims_scores_one(self):
        g = ground_claims("không nêu số cụ thể", [1.0, 2.0])
        assert g.score == 1.0 and g.n_claims == 0

    def test_percent_fraction_tolerance(self):
        # 85 (percent) should count as grounded against a 0.85 fact.
        g = ground_claims("tỷ lệ giữ chân 85", [0.85])
        assert g.flagged == []

    def test_partial_match(self):
        g = ground_claims("100 đúng nhưng 999 bịa", [100.0])
        assert g.n_claims == 2 and g.n_matched == 1 and 999.0 in g.flagged
        assert g.score == 0.5


class TestDisclaimer:
    def test_flagged_disclaimer_warns_and_lists(self):
        d = disclaimer_for(Grounding(score=0.5, n_claims=2, n_matched=1, flagged=[999.0]))
        assert "⚠" in d and "999" in d

    def test_clean_disclaimer_still_says_verify(self):
        d = disclaimer_for(Grounding(score=1.0, n_claims=1, n_matched=1, flagged=[]))
        assert "kiểm chứng" in d and "⚠" not in d
