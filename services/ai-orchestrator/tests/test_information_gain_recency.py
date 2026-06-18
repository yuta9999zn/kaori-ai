"""D3 — T-face recency decay in CDFL novelty (NNL-NTHT 12-axiom, tiên đề 10/11).

Default OFF (recency_decay=1.0) → identical to the original integer counting.
With decay<1, `tick()` ages counts so novelty re-grows for stale (s,a) — the
Dark-Existence T-face (knowledge gets stale in a changing world).
Pure, no I/O.
"""
from __future__ import annotations

import math

from ai_orchestrator.reasoning.cdfl.information_gain import IGScorer
from ai_orchestrator.reasoning.cdfl.transition_model import TransitionModel

S0, S1, A = ("s0",), ("s1",), "look"


def test_decay_off_is_current_behaviour():
    m = TransitionModel()                      # default decay=1.0
    for _ in range(4):
        m.observe(S0, A, S1)
    assert m.state_visit_count(S1) == 4        # exact integer
    ig = IGScorer()
    assert abs(ig.novelty(m, S1) - 1.0 / math.sqrt(5)) < 1e-12  # 1/√(4+1)


def test_tick_is_noop_when_decay_off():
    m = TransitionModel()
    for _ in range(3):
        m.observe(S0, A, S1)
    before = m.state_visit_count(S1)
    for _ in range(10):
        m.tick()
    assert m.state_visit_count(S1) == before   # unchanged when decay=1.0


def test_recency_decay_regrows_novelty():
    m = TransitionModel(recency_decay=0.5)
    for _ in range(4):
        m.observe(S0, A, S1)
    ig = IGScorer()
    nov_fresh = ig.novelty(m, S1)
    base = m.state_visit_count(S1)
    for _ in range(20):                        # time passes, S1 not re-observed
        m.tick()
    assert m.state_visit_count(S1) < base      # count decayed (stale)
    assert ig.novelty(m, S1) > nov_fresh       # novelty re-grew → DE re-grows


def test_re_observing_refreshes():
    m = TransitionModel(recency_decay=0.5)
    m.observe(S0, A, S1)
    for _ in range(10):
        m.tick()
    stale = m.state_visit_count(S1)
    m.observe(S0, A, S1)                        # re-observe → +1 full mass
    assert m.state_visit_count(S1) > stale + 0.9


def test_invalid_decay_raises():
    import pytest
    with pytest.raises(ValueError):
        TransitionModel(recency_decay=0.0)
    with pytest.raises(ValueError):
        TransitionModel(recency_decay=1.5)
