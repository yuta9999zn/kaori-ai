"""CR-0016 closeout — _suggest_line_total recommendation logic.

The suggestion is derived from PRESENCE facts only (which canonicals the data
has), never a hard-coded threshold gate — the measured share is surfaced as
evidence, not used to flip the decision.
"""
from data_pipeline.routers.clean import _suggest_line_total


def test_suggests_when_unit_price_and_quantity_no_total():
    sig = {
        "has_unit_price": True, "has_quantity": True, "has_explicit_total": False,
        "unit_price_median": 10.0, "quantity_median": 2.0,
        "implied_line_total_median": 20.0,
    }
    suggested, rationale = _suggest_line_total(sig)
    assert suggested is True
    assert "nên nhân" in rationale
    assert "10.0" in rationale and "20.0" in rationale   # evidence surfaced


def test_not_suggested_when_explicit_total_present():
    sig = {
        "has_unit_price": True, "has_quantity": True, "has_explicit_total": True,
        "explicit_total_col": "amount", "total_matches_unit_times_qty": 1.0,
    }
    suggested, rationale = _suggest_line_total(sig)
    assert suggested is False
    assert "KHÔNG cần" in rationale
    assert "100%" in rationale                            # match share surfaced


def test_not_suggested_total_present_without_match_share():
    sig = {"has_unit_price": True, "has_quantity": True, "has_explicit_total": True,
           "explicit_total_col": "revenue"}
    suggested, rationale = _suggest_line_total(sig)
    assert suggested is False                             # total exists → derive no-ops


def test_ambiguous_when_no_quantity():
    sig = {"has_unit_price": True, "has_quantity": False, "has_explicit_total": False}
    suggested, rationale = _suggest_line_total(sig)
    assert suggested is None
    assert "tự quyết" in rationale
