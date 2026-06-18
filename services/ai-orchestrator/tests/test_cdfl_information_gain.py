"""Tests for CDFL IGScorer — P15-S11 CDFL port."""
from __future__ import annotations

import math

import pytest

from reasoning.cdfl import IGScorer, TransitionModel


def test_novelty_decreases_with_visits():
    m = TransitionModel()
    scorer = IGScorer()
    n0 = scorer.novelty(m, "A")
    m.observe("A", "go", "B")  # visits A once
    n1 = scorer.novelty(m, "A")
    m.observe("A", "go", "B")  # visits A twice
    n2 = scorer.novelty(m, "A")
    assert n0 > n1 > n2


def test_novelty_bounds():
    m = TransitionModel()
    scorer = IGScorer()
    # Never visited → N=0 → 1/√1 = 1.0
    assert scorer.novelty(m, "A") == pytest.approx(1.0)
    # 3 visits → 1/√4 = 0.5
    for _ in range(3):
        m.observe("A", "go", "B")
    # A's visit count = 3 (observed 3x as src)
    assert scorer.novelty(m, "A") == pytest.approx(1 / math.sqrt(4))


def test_uncertainty_decreases_with_state_action_count():
    m = TransitionModel()
    scorer = IGScorer()
    u0 = scorer.uncertainty(m, "A", "go")
    m.observe("A", "go", "B")
    u1 = scorer.uncertainty(m, "A", "go")
    assert u0 > u1


def test_score_uses_next_state_novelty_when_provided():
    m = TransitionModel()
    scorer = IGScorer(uncertainty_weight=1.0)
    # Make B much more visited than C.
    for _ in range(10):
        m.observe("A", "go", "B")
    # score(A, go, next=B): novelty(B) small + uncertainty(A,go) small
    # score(A, go, next=C): novelty(C) = 1.0 (never visited) + uncertainty same
    score_b = scorer.score(m, "A", "go", next_state="B")
    score_c = scorer.score(m, "A", "go", next_state="C")
    assert score_c > score_b


def test_score_falls_back_to_state_novelty_when_no_next():
    m = TransitionModel()
    scorer = IGScorer()
    # Stateless re-ranking mode.
    s = scorer.score(m, "A", "x", next_state=None)
    # Both novelty(A) and uncertainty(A,x) = 1.0 → 1+1 = 2.0
    assert s == pytest.approx(2.0)


def test_uncertainty_weight_scales_contribution():
    m = TransitionModel()
    for _ in range(5):
        m.observe("A", "go", "B")
    s_lam0 = IGScorer(uncertainty_weight=0.0).score(m, "A", "go", next_state="B")
    s_lam1 = IGScorer(uncertainty_weight=1.0).score(m, "A", "go", next_state="B")
    s_lam2 = IGScorer(uncertainty_weight=2.0).score(m, "A", "go", next_state="B")
    # λ=0 → only novelty(B); λ>0 adds uncertainty term monotonically.
    assert s_lam0 < s_lam1 < s_lam2


def test_information_gain_weight_scales_whole_score():
    m = TransitionModel()
    s1 = IGScorer(information_gain_weight=1.0).score(m, "A", "go", next_state="B")
    s2 = IGScorer(information_gain_weight=2.0).score(m, "A", "go", next_state="B")
    assert s2 == pytest.approx(2 * s1)
