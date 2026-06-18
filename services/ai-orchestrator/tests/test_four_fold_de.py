"""Tests for cdfl.four_fold_de — the four-face Dark-Existence dashboard."""
from __future__ import annotations

import pytest

from ai_orchestrator.reasoning.cdfl.four_fold_de import FourFoldDE, assemble_de


def test_all_known_zero_dark_full_or():
    de = assemble_de(data_coverage=1.0, knowledge_freshness=1.0,
                     knowledge_coverage=1.0, grounding_score=1.0)
    assert de.faces == {"x": 0.0, "t": 0.0, "if": 0.0, "mf": 0.0}
    assert de.manifest_or() == pytest.approx(1.0)
    assert de.max_dark() == pytest.approx(0.0)


def test_all_unknown_full_dark():
    de = assemble_de(data_coverage=0.0, knowledge_freshness=0.0,
                     knowledge_coverage=0.0, grounding_score=0.0)
    assert de.manifest_or() == pytest.approx(0.0)
    assert de.max_dark() == pytest.approx(1.0)


def test_faces_map_to_right_signal():
    # only grounding low → mf-face dark (đốm đen), others light
    de = assemble_de(data_coverage=1.0, knowledge_freshness=1.0,
                     knowledge_coverage=1.0, grounding_score=0.2)
    assert de.mf == pytest.approx(0.8)
    assert de.x == de.t == de.if_ == pytest.approx(0.0)
    assert de.max_dark() == pytest.approx(0.8)  # mf is the binding constraint


def test_clips_out_of_range_inputs():
    de = assemble_de(data_coverage=1.5, knowledge_freshness=-0.3,
                     knowledge_coverage=0.5, grounding_score=2.0)
    assert de.x == pytest.approx(0.0)   # clipped from 1.5
    assert de.t == pytest.approx(1.0)   # clipped from -0.3
    assert de.if_ == pytest.approx(0.5)
    assert de.mf == pytest.approx(0.0)  # clipped from 2.0
