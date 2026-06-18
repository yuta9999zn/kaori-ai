"""
CDFLAgent — integration của TransitionModel + IGScorer + LookaheadPlanner.

API tương thích interface `CDFLv3` từ benchmark suite của luận văn
(xem `_cdfl_extract/v8/ablation_study.py`):

    agent = CDFLAgent(action_space=..., horizon=5, num_rollouts=6,
                     uncertainty_weight=1.0, information_gain_weight=1.0)
    for episode:
        state = env.reset()
        for step:
            action = agent.step(state)
            next_state, _, _ = env.step(action)
            agent.observe_transition(state, action, next_state, reward=0)
            state = next_state

Khác với gridworld benchmark: agent này nhận `action_space` tổng quát
(Sequence[Action]) thay vì int — để dùng cho Process Mining (action =
event_type) lẫn RAG (action = candidate_chunk_id).

Hành vi chính khi `step(state)`:
1. Liệt kê candidate actions từ action_space.
2. Dùng LookaheadPlanner.score_actions() trên TransitionModel hiện tại.
3. Greedy chọn best_action với Boltzmann noise (nếu `temperature > 0`).
4. Ablation NoTransitionModel = init agent với TransitionModel cố định
   không observe (set `freeze_model=True`).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from .information_gain import IGScorer
from .lookahead import LookaheadPlanner
from .transition_model import TransitionModel
from .types import Action, ActionScore, State


@dataclass
class CDFLAgent:
    """Convergent Dual-Field Learning agent — port của CDFLv3.

    Args:
        action_space: list của actions agent có thể chọn. Cố định khi init.
        horizon: H bước lookahead. Mặc định 5.
        num_rollouts: rollouts per candidate. Mặc định 6.
        uncertainty_weight: λ trong IG. Mặc định 1.0.
        information_gain_weight: scale tổng IG. Mặc định 1.0.
        temperature: Boltzmann noise. 0 = greedy, > 0 = soft. Mặc định 0.1.
        freeze_model: nếu True, agent không học (cho ablation NoTransitionModel).
        seed: int seed để reproducible.
    """

    action_space: Sequence[Action]
    horizon: int = 5
    num_rollouts: int = 6
    uncertainty_weight: float = 1.0
    information_gain_weight: float = 1.0
    temperature: float = 0.1
    freeze_model: bool = False
    seed: int | None = None

    # Internal
    _model: TransitionModel = field(init=False)
    _planner: LookaheadPlanner = field(init=False)
    _scorer: IGScorer = field(init=False)
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        if not self.action_space:
            raise ValueError("action_space must be non-empty")
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")
        if self.num_rollouts < 1:
            raise ValueError("num_rollouts must be >= 1")
        if self.temperature < 0:
            raise ValueError("temperature must be >= 0")

        self._rng = random.Random(self.seed)
        self._model = TransitionModel(rng=self._rng)
        self._scorer = IGScorer(
            uncertainty_weight=self.uncertainty_weight,
            information_gain_weight=self.information_gain_weight,
        )
        self._planner = LookaheadPlanner(
            horizon=self.horizon,
            num_rollouts=self.num_rollouts,
            scorer=self._scorer,
            rng=self._rng,
        )

    # ----- API tương thích benchmark suite -----

    def step(self, state: State) -> Action:
        """Trả action cho state — pick max IG với Boltzmann noise."""
        scored = self._planner.score_actions(
            model=self._model,
            state=state,
            candidate_actions=list(self.action_space),
        )
        return self._pick_with_temperature(scored)

    def observe_transition(
        self,
        state: State,
        action: Action,
        next_state: State,
        reward: float = 0.0,
    ) -> None:
        """Update model. `reward` nhận để API-compat — CDFL ignore."""
        del reward  # CDFL không dùng reward (max |OR|, not max R).
        if self.freeze_model:
            return
        self._model.observe(state, action, next_state)

    # ----- Diagnostic / introspection -----

    @property
    def transition_counts(self) -> int:
        """Số transitions đã quan sát — proxy cho memory footprint."""
        return self._model.num_transitions_seen

    @property
    def model(self) -> TransitionModel:
        """Expose để benchmarking + adapter (e.g. seed từ Process Mining)."""
        return self._model

    @property
    def planner(self) -> LookaheadPlanner:
        return self._planner

    def score_actions(self, state: State) -> list[ActionScore]:
        """Public ranking — dùng cho Workflow planner endpoint trả top-K."""
        return self._planner.score_actions(
            model=self._model,
            state=state,
            candidate_actions=list(self.action_space),
        )

    # ----- internal -----

    def _pick_with_temperature(self, scored: list[ActionScore]) -> Action:
        if not scored:
            return self._rng.choice(list(self.action_space))
        if self.temperature <= 0:
            scored.sort(key=lambda s: (-s.mean_score, s.visit_proxy))
            return scored[0].action
        # Boltzmann: P(a) ∝ exp(score(a) / T). Normalize relative to max
        # để tránh overflow nếu mean_score lớn.
        max_score = max(s.mean_score for s in scored)
        logits = [(s.mean_score - max_score) / self.temperature for s in scored]
        weights = [math.exp(x) for x in logits]
        return self._rng.choices([s.action for s in scored], weights=weights, k=1)[0]


# ----- factory tiện dụng: seed từ Process Mining -----

def cdfl_agent_from_mined_workflow(
    direct_follows: dict[tuple[State, State], int],
    *,
    horizon: int = 5,
    num_rollouts: int = 6,
    uncertainty_weight: float = 1.0,
    information_gain_weight: float = 1.0,
    temperature: float = 0.1,
    seed: int | None = None,
) -> CDFLAgent:
    """Build CDFLAgent từ output của `HeuristicMiner.mine().direct_follows`.

    action_space được derive từ tất cả `to_type` xuất hiện. Sau khi build,
    agent đã có TransitionModel pre-seeded — không cần rerun observe.
    """
    if not direct_follows:
        raise ValueError("direct_follows must be non-empty to derive action_space")
    actions = sorted({to_type for (_from, to_type) in direct_follows.keys()},
                     key=lambda x: str(x))
    agent = CDFLAgent(
        action_space=actions,
        horizon=horizon,
        num_rollouts=num_rollouts,
        uncertainty_weight=uncertainty_weight,
        information_gain_weight=information_gain_weight,
        temperature=temperature,
        seed=seed,
    )
    # Pre-seed model — bypass freeze flag (factory intentional seed).
    for (from_type, to_type), count in direct_follows.items():
        for _ in range(int(count)):
            agent.model.observe(from_type, to_type, to_type)
    return agent
