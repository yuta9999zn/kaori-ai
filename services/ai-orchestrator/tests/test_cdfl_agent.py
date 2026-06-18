"""Tests for CDFL Agent integration — P15-S11 CDFL port."""
from __future__ import annotations

import pytest

from reasoning.cdfl import CDFLAgent
from reasoning.cdfl.agent import cdfl_agent_from_mined_workflow


def test_init_validates_args():
    with pytest.raises(ValueError):
        CDFLAgent(action_space=[])
    with pytest.raises(ValueError):
        CDFLAgent(action_space=["a"], horizon=0)
    with pytest.raises(ValueError):
        CDFLAgent(action_space=["a"], num_rollouts=0)
    with pytest.raises(ValueError):
        CDFLAgent(action_space=["a"], temperature=-0.1)


def test_step_returns_valid_action_from_space():
    agent = CDFLAgent(action_space=["a", "b", "c"], seed=42)
    action = agent.step("start")
    assert action in {"a", "b", "c"}


def test_observe_transition_updates_model_unless_frozen():
    agent = CDFLAgent(action_space=["a", "b"], seed=42)
    assert agent.transition_counts == 0
    agent.observe_transition("s0", "a", "s1")
    assert agent.transition_counts == 2  # both s0 and s1 visited

    frozen = CDFLAgent(action_space=["a", "b"], freeze_model=True, seed=42)
    frozen.observe_transition("s0", "a", "s1")
    assert frozen.transition_counts == 0  # NoTransitionModel ablation


def test_greedy_temperature_zero_is_deterministic():
    """temperature=0 → cùng input → cùng action (modulo planner rng).

    Em fix seed cho planner rng để greedy thực sự deterministic.
    """
    a1 = CDFLAgent(action_space=["a", "b", "c"], temperature=0, seed=42)
    a2 = CDFLAgent(action_space=["a", "b", "c"], temperature=0, seed=42)
    # Seed cùng + state cùng + transition model cùng (rỗng) → cùng score → cùng action.
    assert a1.step("s0") == a2.step("s0")


def test_seed_makes_run_reproducible():
    def run(seed: int) -> list:
        agent = CDFLAgent(action_space=["a", "b", "c"], seed=seed)
        out = []
        state = "s0"
        for i in range(5):
            action = agent.step(state)
            next_state = f"s{i + 1}"
            agent.observe_transition(state, action, next_state)
            out.append((state, action, next_state))
            state = next_state
        return out

    r1 = run(42)
    r2 = run(42)
    assert r1 == r2
    r3 = run(7)
    # Khác seed → đa số sẽ khác (rất unlikely identical với 5 step + 3 action).
    assert r1 != r3


def test_score_actions_returns_ranked_when_called():
    agent = CDFLAgent(action_space=["a", "b", "c"], seed=42)
    # Pre-seed model: action "a" đã được taken nhiều.
    for _ in range(20):
        agent.observe_transition("s0", "a", "s1")
    scored = agent.score_actions("s0")
    assert len(scored) == 3
    # "a" có visit_proxy lớn nhất → uncertainty thấp → score thấp nhất
    # (giả định novelty s1 cũng đã giảm).
    a_score = next(s for s in scored if s.action == "a")
    b_score = next(s for s in scored if s.action == "b")
    assert b_score.mean_score >= a_score.mean_score


def test_factory_from_mined_workflow_pre_seeds_model():
    df = {
        ("login", "browse"): 100,
        ("browse", "checkout"): 40,
        ("checkout", "logout"): 30,
        ("login", "logout"): 5,
    }
    agent = cdfl_agent_from_mined_workflow(df, seed=42)
    # Action space derived from to_types.
    assert set(agent.action_space) == {"browse", "checkout", "logout"}
    # Counts seeded.
    assert agent.model.state_action_count("login", "browse") == 100
    assert agent.model.state_action_count("login", "logout") == 5
    # Model knows direct-follow probabilities.
    assert agent.model.probability("login", "browse", "browse") == 1.0


def test_factory_raises_on_empty_input():
    with pytest.raises(ValueError):
        cdfl_agent_from_mined_workflow({})


def test_factory_step_chooses_high_ig_action():
    """Với direct_follows skewed, agent prefer action ít quan sát."""
    df = {
        ("S", "common"): 1000,   # heavily trodden
        ("S", "rare"): 1,         # high uncertainty
    }
    agent = cdfl_agent_from_mined_workflow(df, temperature=0, seed=42)
    # Greedy + uncertainty → "rare" được pick.
    assert agent.step("S") == "rare"


def test_no_transition_model_ablation_signature():
    """freeze_model agent vẫn run được — chỉ là không học. Verify ablation."""
    agent = CDFLAgent(action_space=["a", "b"], freeze_model=True, seed=42)
    for _ in range(10):
        a = agent.step("s")
        agent.observe_transition("s", a, "s_next")
    assert agent.transition_counts == 0  # learned nothing
    # Nhưng step vẫn trả action hợp lệ — degraded mode, not crash.
    assert agent.step("s") in {"a", "b"}
