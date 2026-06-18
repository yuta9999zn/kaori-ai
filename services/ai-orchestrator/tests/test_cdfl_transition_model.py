"""Tests for CDFL TransitionModel — P15-S11 CDFL port."""
from __future__ import annotations

import random

import pytest

from reasoning.cdfl import TransitionModel
from reasoning.cdfl.types import Transition


def test_probability_zero_when_unobserved():
    m = TransitionModel()
    assert m.probability("A", "x", "B") == 0.0


def test_probability_normalises_to_one_after_observations():
    m = TransitionModel()
    m.observe("A", "go", "B")
    m.observe("A", "go", "B")
    m.observe("A", "go", "C")
    # 2/3 vs 1/3
    assert m.probability("A", "go", "B") == pytest.approx(2 / 3)
    assert m.probability("A", "go", "C") == pytest.approx(1 / 3)
    # Other states are 0.
    assert m.probability("A", "go", "Z") == 0.0


def test_state_visit_count_tracks_both_sides_of_transition():
    m = TransitionModel()
    m.observe("A", "go", "B")
    assert m.state_visit_count("A") == 1
    assert m.state_visit_count("B") == 1
    m.observe("B", "go", "A")
    assert m.state_visit_count("A") == 2
    assert m.state_visit_count("B") == 2


def test_sample_next_respects_observed_distribution():
    rng = random.Random(42)
    m = TransitionModel(rng=rng)
    # Heavy bias B.
    for _ in range(900):
        m.observe("A", "go", "B")
    for _ in range(100):
        m.observe("A", "go", "C")
    samples = [m.sample_next("A", "go") for _ in range(5000)]
    b_rate = samples.count("B") / len(samples)
    # 90% with sampling noise ±3%.
    assert 0.87 < b_rate < 0.93


def test_sample_next_falls_back_to_known_state_when_novel():
    rng = random.Random(7)
    m = TransitionModel(rng=rng)
    m.observe("A", "go", "B")
    m.observe("B", "go", "C")
    # (A, "stay") chưa quan sát — fallback choose 1 known state
    result = m.sample_next("A", "stay")
    assert result in {"A", "B", "C"}


def test_sample_next_self_loop_when_no_known_state():
    m = TransitionModel(rng=random.Random(0))
    # Brand new model: no known states yet.
    assert m.sample_next("X", "y") == "X"


def test_observe_many_bulk():
    m = TransitionModel()
    m.observe_many([
        Transition("A", "go", "B"),
        Transition("B", "go", "C"),
        Transition("A", "go", "B"),
    ])
    assert m.state_action_count("A", "go") == 2
    assert m.state_action_count("B", "go") == 1


def test_known_states_preserves_insertion_order():
    m = TransitionModel()
    m.observe("A", "go", "B")
    m.observe("C", "go", "D")
    assert m.known_states == ("A", "B", "C", "D")


def test_num_transitions_seen():
    m = TransitionModel()
    assert m.num_transitions_seen == 0
    m.observe("A", "go", "B")
    # Counts both A and B as visited → 2.
    assert m.num_transitions_seen == 2


def test_from_direct_follows_seeds_counts():
    # Mimic HeuristicMiner output.
    df = {("login", "browse"): 50, ("browse", "checkout"): 20, ("login", "logout"): 5}
    m = TransitionModel.from_direct_follows(df)
    assert m.state_action_count("login", "browse") == 50
    assert m.state_action_count("login", "logout") == 5
    assert m.probability("login", "browse", "browse") == 1.0
    assert m.probability("browse", "checkout", "checkout") == 1.0
