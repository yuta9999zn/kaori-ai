import pytest
from ai_orchestrator.reasoning import compliance_controls as cc


def test_valid_tiers_set():
    assert cc.RISK_TIERS == ("prohibited", "high", "limited", "minimal")


def test_is_prohibited():
    assert cc.is_prohibited("prohibited") is True
    assert cc.is_prohibited("high") is False


def test_high_tier_controls():
    controls = cc.controls_for_tier("high")
    assert "K-23_HUMAN_OVERSIGHT" in controls
    assert "K-25_MODEL_CARD" in controls
    assert "K-26_MONITORING" in controls
    assert "K-6_AUDIT_LOG" in controls


def test_limited_tier_controls():
    controls = cc.controls_for_tier("limited")
    assert "K-24_TRANSPARENCY" in controls
    assert "K-6_AUDIT_LOG" in controls
    assert "K-23_HUMAN_OVERSIGHT" not in controls


def test_minimal_and_prohibited_have_no_runtime_controls():
    assert cc.controls_for_tier("minimal") == []
    assert cc.controls_for_tier("prohibited") == []


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        cc.controls_for_tier("banana")


def test_validate_tier_normalises_case():
    assert cc.validate_tier(" HIGH ") == "high"
    with pytest.raises(ValueError):
        cc.validate_tier("nope")
