"""
IGScorer — Information Gain component của CDFL.

Theo REPORT_V8.md §6 formalisation:

    novelty(s)         = 1 / sqrt(N(s) + 1)
    uncertainty(s, a)  = 1 / sqrt(n(s, a) + 1)
    IG(s, a)           = novelty(s) + λ · uncertainty(s, a)

trong đó:
- N(s)  = số lần state s đã được visit (Σ qua mọi trajectory)
- n(s,a) = số lần (s, a) đã được taken

λ (`uncertainty_weight`) mặc định 1.0 theo ablation_study.py.

Ablation cho thấy: novelty và uncertainty individually contribute <2pp,
nhưng combined trong context lookahead → ~+4pp. Đây là cốt lõi của "IF
expanding into MF": novelty đo distance to known core, uncertainty đo
confidence của model về (s,a) edge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .transition_model import TransitionModel
from .types import Action, State


@dataclass(frozen=True)
class IGScorer:
    """Score actions theo information gain.

    Args:
        uncertainty_weight: λ trong công thức. Mặc định 1.0 (luận văn CDFL v3).
        information_gain_weight: weight thêm để scale tổng IG khi combine
            với reward (Phase 2 hybrid). Mặc định 1.0 → pure CDFL.

    Stateless — đọc counts từ TransitionModel injection.
    """

    uncertainty_weight: float = 1.0
    information_gain_weight: float = 1.0

    def novelty(self, model: TransitionModel, state: State) -> float:
        """1 / sqrt(N(s) + 1) — luôn ∈ (0, 1]."""
        n = model.state_visit_count(state)
        return 1.0 / math.sqrt(n + 1)

    def uncertainty(self, model: TransitionModel, state: State, action: Action) -> float:
        """1 / sqrt(n(s,a) + 1) — luôn ∈ (0, 1]."""
        n = model.state_action_count(state, action)
        return 1.0 / math.sqrt(n + 1)

    def score(
        self,
        model: TransitionModel,
        state: State,
        action: Action,
        next_state: State | None = None,
    ) -> float:
        """IG(s, a) = novelty(s') + λ·uncertainty(s, a), scaled bởi weight.

        Khi `next_state` được provided: dùng novelty(next_state) — đây là
        spec luận văn (rollout score dựa trên TRẠNG THÁI ĐÍCH của action,
        không phải state hiện tại). Khi `next_state=None`: fallback dùng
        novelty(state) — chỉ cho stateless re-ranking RAG candidate.
        """
        target = next_state if next_state is not None else state
        nov = self.novelty(model, target)
        unc = self.uncertainty(model, state, action)
        raw = nov + self.uncertainty_weight * unc
        return self.information_gain_weight * raw
