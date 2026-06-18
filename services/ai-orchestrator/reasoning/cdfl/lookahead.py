"""
LookaheadPlanner — H-step Monte Carlo rollout của CDFL v3.

Default hyperparams từ `scaling_50.py` luận văn:
    horizon       = 5
    num_rollouts  = 6
    uncertainty_w = 1.0
    ig_weight     = 0.5  (scaling test) — em pin 1.0 default cho generic

Ablation từ REPORT_V8.md:
- NoRollout (horizon=1): −1.8pp đơn lẻ
- NoRolloutNoIG: −3.8pp (gần count-based)

Multi-step lookahead tự một mình giá trị nhỏ, NHƯNG tie-breaking trong
large state space + combined với uncertainty → emergent advantage.

CDFL planner KHÁC count-based ở chỗ count-based chỉ greedy 1-step trên
novelty(s') hiện tại; CDFL rollout H bước qua learned transition model →
score trajectory aware (avoid dead-end khi novelty hiện tại ties).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .information_gain import IGScorer
from .transition_model import TransitionModel
from .types import Action, ActionScore, RolloutResult, State, Transition


@dataclass
class LookaheadPlanner:
    """Monte Carlo H-step planner.

    Args:
        horizon: H — số bước rollout. Mặc định 5.
        num_rollouts: số rollout per action. Mặc định 6.
        scorer: IGScorer instance.
        rng: optional `random.Random` để reproducible.

    Lưu ý: planner KHÔNG đột biến TransitionModel. Rollout chỉ sample,
    không observe — observe là việc của agent khi nhận transition thật.
    """

    horizon: int = 5
    num_rollouts: int = 6
    scorer: IGScorer = None  # type: ignore[assignment]  # default trong __post_init__
    rng: random.Random | None = None

    def __post_init__(self) -> None:
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")
        if self.num_rollouts < 1:
            raise ValueError("num_rollouts must be >= 1")
        if self.scorer is None:
            self.scorer = IGScorer()
        if self.rng is None:
            self.rng = random.Random()

    def rollout(
        self,
        model: TransitionModel,
        start: State,
        first_action: Action,
    ) -> RolloutResult:
        """Một rollout H bước, bắt đầu bằng `first_action`.

        Mô phỏng theo learned transition model — không thực thi action
        ngoài đời thực.
        """
        trajectory: list[Transition] = []
        total_ig = 0.0
        state = start
        action: Action = first_action
        for step in range(self.horizon):
            next_state = model.sample_next(state, action)
            ig = self.scorer.score(model, state, action, next_state=next_state)
            total_ig += ig
            trajectory.append(Transition(state=state, action=action, next_state=next_state))
            state = next_state
            # Pick next action cho rollout tiếp: theo policy "max IG greedy"
            # trong known action set (nếu rỗng → break).
            candidate_actions = self._candidate_actions(model, state)
            if not candidate_actions:
                break
            # Sample weighted-by-IG để tránh deterministic loop.
            weights = [self.scorer.score(model, state, a) for a in candidate_actions]
            action = self.rng.choices(candidate_actions, weights=weights, k=1)[0]
        return RolloutResult(trajectory=tuple(trajectory), total_information_gain=total_ig)

    def score_actions(
        self,
        model: TransitionModel,
        state: State,
        candidate_actions: Sequence[Action],
    ) -> list[ActionScore]:
        """Score MỖI action bằng `num_rollouts` rollout, trả `ActionScore` list."""
        if not candidate_actions:
            return []
        scores: list[ActionScore] = []
        for action in candidate_actions:
            rollouts = [
                self.rollout(model, start=state, first_action=action)
                for _ in range(self.num_rollouts)
            ]
            mean = sum(r.total_information_gain for r in rollouts) / len(rollouts)
            best = max(r.total_information_gain for r in rollouts)
            scores.append(
                ActionScore(
                    action=action,
                    mean_score=mean,
                    best_score=best,
                    visit_proxy=model.state_action_count(state, action),
                )
            )
        return scores

    def best_action(
        self,
        model: TransitionModel,
        state: State,
        candidate_actions: Sequence[Action],
    ) -> Action:
        """Convenience: trả action có mean_score lớn nhất.

        Tie-breaking: action có visit_proxy nhỏ nhất (chưa thử) thắng tie.
        """
        scored = self.score_actions(model, state, candidate_actions)
        if not scored:
            raise ValueError("candidate_actions must be non-empty")
        scored.sort(key=lambda s: (-s.mean_score, s.visit_proxy))
        return scored[0].action

    def _candidate_actions(self, model: TransitionModel, state: State) -> list[Action]:
        """Actions đã từng quan sát từ `state`.

        Cho rollout interior steps — nếu state chưa có outgoing action
        nào quan sát thì trả empty (rollout kết thúc sớm).
        """
        # Liệt kê tất cả action có count tại (state, *).
        # Đây không hiệu quả O(|states| × |actions|) nhưng tabular CDFL
        # state space nhỏ; nếu Phase 2 mở scale lớn, em sẽ index lại.
        seen: set[Action] = set()
        for (s, a) in model._counts:  # type: ignore[attr-defined]
            if s == state:
                seen.add(a)
        return list(seen)
