"""Tests for cdfl.empowerment — option-preservation / agent protection (12-axiom).

Pure, no I/O. Mirrors the side_effect taxonomy and the K-23 gate classes.
"""
from __future__ import annotations

from ai_orchestrator.reasoning.cdfl.empowerment import (
    OPTION_SHRINKING_CLASSES,
    REVERSIBLE_CLASSES,
    option_preserving,
    protection_advice,
)


def test_taxonomy_matches_side_effect_classes():
    assert REVERSIBLE_CLASSES == ("pure", "read_only", "write_idempotent")
    assert OPTION_SHRINKING_CLASSES == ("write_non_idempotent", "external")


def test_reversible_classes_preserve_options():
    for sec in REVERSIBLE_CLASSES:
        assert option_preserving(sec) is True


def test_irreversible_classes_do_not_preserve():
    for sec in OPTION_SHRINKING_CLASSES:
        assert option_preserving(sec) is False


def test_advice_reversible_no_consent():
    a = protection_advice("read_only")
    assert a.preserves_options is True
    assert a.needs_consent is False
    assert a.prefer_reversible is False


def test_advice_irreversible_needs_consent():
    a = protection_advice("external")
    assert a.preserves_options is False
    assert a.needs_consent is True
    assert a.prefer_reversible is False
    assert "BẤT KHẢ HỒI" in a.rationale


def test_advice_prefers_reversible_alternative():
    a = protection_advice("write_non_idempotent", reversible_alternative_exists=True)
    assert a.preserves_options is False
    assert a.needs_consent is True
    assert a.prefer_reversible is True
