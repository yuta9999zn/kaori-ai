"""Tests for CDFL LookaheadPlanner — P15-S11 CDFL port."""
from __future__ import annotations

import random

import pytest

from reasoning.cdfl import IGScorer, LookaheadPlanner, TransitionModel


def _seeded_model(seed: int = 0) -> TransitionModel:
    rng = random.Random(seed)
    m = TransitionModel(rng=rng)
    # Build small chain A→B→C→D with one branch A→Z.
    for _ in range(10):
        m.observe("A", "to_b", "B")
    for _ in range(10):
        m.observe("B", "to_c", "C")
    for _ in range(10):
        m.observe("C", "to_d", "D")
    # Only 1 observation of branch — uncertainty high.
    m.observe("A", "to_z", "Z")
    return m


def test_rollout_trajectory_length_at_most_horizon():
    m = _seeded_model()
    planner = LookaheadPlanner(horizon=5, num_rollouts=1, rng=random.Random(0))
    result = planner.rollout(m, start="A", first_action="to_b")
    assert len(result.trajectory) <= 5
    # First transition starts at A with first_action.
    assert result.trajectory[0].state == "A"
    assert result.trajectory[0].action == "to_b"


def test_rollout_terminates_early_on_dead_end():
    """Khi không có action nào quan sát từ state, rollout dừng."""
    m = TransitionModel(rng=random.Random(0))
    m.observe("A", "go", "B")   # B chưa có outgoing → planner break sau step 1.
    planner = LookaheadPlanner(horizon=5, num_rollouts=1, rng=random.Random(0))
    result = planner.rollout(m, start="A", first_action="go")
    assert len(result.trajectory) == 1


def test_rollout_does_not_mutate_model():
    m = _seeded_model()
    before = m.num_transitions_seen
    planner = LookaheadPlanner(rng=random.Random(0))
    planner.rollout(m, start="A", first_action="to_b")
    assert m.num_transitions_seen == before


def test_score_actions_returns_one_per_candidate():
    m = _seeded_model()
    planner = LookaheadPlanner(num_rollouts=4, rng=random.Random(0))
    scored = planner.score_actions(m, "A", ["to_b", "to_z", "to_x"])
    assert len(scored) == 3
    actions = {s.action for s in scored}
    assert actions == {"to_b", "to_z", "to_x"}


def test_best_action_h1_prefers_novel_branch():
    """Với horizon=1, novelty + uncertainty ưu tiên branch chưa khám phá nhiều."""
    m = _seeded_model()
    planner = LookaheadPlanner(horizon=1, num_rollouts=8, rng=random.Random(123))
    # to_z: uncertainty cao (count=1), Z novel (visit count=1).
    # to_b: trodden 10x, B visit count=10.
    best = planner.best_action(m, "A", ["to_b", "to_z"])
    assert best == "to_z"


def test_lookahead_h5_prefers_extendable_chain_over_dead_end():
    """REPORT_V8.md §6: multi-step lookahead avoids dead-ends by accumulating IG.

    Trong fixture, `to_b` mở chain A→B→C→D (3-step extendable trajectory) còn
    `to_z` chỉ dẫn vào Z (dead-end). H=3 → `to_b` accumulate IG cao hơn.
    Đây CHÍNH LÀ niche CDFL: planner trajectory-aware bypass dead-ends.
    """
    m = _seeded_model()
    planner = LookaheadPlanner(horizon=3, num_rollouts=8, rng=random.Random(123))
    best = planner.best_action(m, "A", ["to_b", "to_z"])
    assert best == "to_b"


def test_best_action_tie_break_on_visit_proxy():
    m = TransitionModel(rng=random.Random(0))
    m.observe("S", "a1", "X")  # 1 visit
    m.observe("S", "a2", "X")  # 1 visit (same count → mean_score ties)
    planner = LookaheadPlanner(horizon=1, num_rollouts=2, rng=random.Random(0))
    # Inject 1 extra visit cho a1 để a2 có lower visit_proxy.
    m.observe("S", "a1", "X")
    best = planner.best_action(m, "S", ["a1", "a2"])
    # a2 chỉ thử 1 lần, a1 thử 2 lần → tie-break ưu tiên a2.
    assert best == "a2"


def test_horizon_1_equivalent_to_no_rollout_ablation():
    """REPORT_V8.md NoRollout = horizon=1 (still uses transition model)."""
    m = _seeded_model()
    p1 = LookaheadPlanner(horizon=1, num_rollouts=4, rng=random.Random(0))
    p5 = LookaheadPlanner(horizon=5, num_rollouts=4, rng=random.Random(0))
    s1 = p1.score_actions(m, "A", ["to_b"])
    s5 = p5.score_actions(m, "A", ["to_b"])
    # H=5 score accumulates more IG since trajectory longer.
    assert s5[0].mean_score >= s1[0].mean_score


def test_best_action_raises_on_empty_candidates():
    m = _seeded_model()
    planner = LookaheadPlanner()
    with pytest.raises(ValueError):
        planner.best_action(m, "A", [])


def test_planner_validates_init_args():
    with pytest.raises(ValueError):
        LookaheadPlanner(horizon=0)
    with pytest.raises(ValueError):
        LookaheadPlanner(num_rollouts=0)
