"""
Type aliases và dataclass cho CDFL.

CDFL nguyên bản trong luận văn dùng tabular state (int) cho gridworld.
Port của Kaori dùng `Hashable` để có thể dùng cùng agent cho:
- Process Mining: state = event_type (str), action = next_event_type (str)
- RAG re-ranking: state = current_doc_chunk_id (str), action = candidate_chunk_id (str)
- Pure benchmark reproduction: state = int, action = int
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, TypeAlias

State: TypeAlias = Hashable
Action: TypeAlias = Hashable


@dataclass(frozen=True)
class Transition:
    """Một quan sát (s, a, s') — input cho TransitionModel.observe()."""
    state: State
    action: Action
    next_state: State


@dataclass(frozen=True)
class ActionScore:
    """Output của LookaheadPlanner.score_actions() — 1 row cho mỗi action.

    Fields:
      action            — candidate action
      mean_score        — average IG over num_rollouts rollouts
      best_score        — max IG over rollouts (cho diagnostic)
      visit_proxy       — số lần (s,a) đã quan sát (uncertainty proxy)
    """
    action: Action
    mean_score: float
    best_score: float
    visit_proxy: int


@dataclass(frozen=True)
class RolloutResult:
    """Output của 1 rollout — trajectory + accumulated IG.

    Trajectory bao gồm (state, action, next_state) tuples theo thứ tự.
    """
    trajectory: tuple[Transition, ...] = field(default_factory=tuple)
    total_information_gain: float = 0.0
