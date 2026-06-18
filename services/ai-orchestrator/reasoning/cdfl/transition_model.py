"""
TransitionModel — CRITICAL component của CDFL v3.

Ablation từ luận văn (REPORT_V8.md §1): gỡ transition model giảm coverage
**−31.6pp**. Các component khác (multi-step lookahead, uncertainty, IG) chỉ
contribute <2pp đơn lẻ. Transition model là cốt lõi empirical.

Model học P(s' | s, a) từ observed transitions:

    P(s' | s, a) = count(s, a, s') / sum_{s''} count(s, a, s'')

Khi (s, a) chưa từng quan sát: trả uniform-random sample qua mọi state đã
biết — đây là default exploration prior từ luận văn.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Hashable, Iterable

from .types import Action, State, Transition


class TransitionModel:
    """Tabular P(s'|s,a) learned from observed transitions.

    Args:
        rng: optional `random.Random` instance để reproducible
             (mặc định module-level random, theo seed nếu caller seed).

    State + action chỉ cần Hashable; không yêu cầu int.
    """

    def __init__(
        self, *, rng: random.Random | None = None, recency_decay: float = 1.0,
    ) -> None:
        # transition_counts[(s, a)][s'] = count
        self._counts: dict[tuple[State, Action], Counter[State]] = defaultdict(Counter)
        # state_visits[s] = số lần thấy s (cho novelty downstream)
        self._state_visits: Counter[State] = Counter()
        # known_states giữ thứ tự insertion để uniform-random predictable
        self._known_states: list[State] = []
        self._known_states_set: set[State] = set()
        self._rng = rng or random.Random()
        # T-face (NNL-NTHT 12-axiom, tiên đề 10/11): in a CHANGING world,
        # knowledge ages → novelty must re-grow for stale (s,a). `tick()`
        # multiplies all counts by `recency_decay` so unre-visited states decay
        # toward novel again (DE re-grows). 1.0 = static world = exactly the
        # original integer counting (no behaviour change). 0<decay<1 = continual.
        if not (0.0 < recency_decay <= 1.0):
            raise ValueError(f"recency_decay must be in (0, 1], got {recency_decay}")
        self._decay = recency_decay

    # ----- observe -----

    def observe(self, state: State, action: Action, next_state: State) -> None:
        """Cập nhật counts với một transition (s, a, s')."""
        self._counts[(state, action)][next_state] += 1
        self._record_state(state)
        self._record_state(next_state)

    def observe_many(self, transitions: Iterable[Transition]) -> None:
        """Bulk observe — convenience wrapper."""
        for tr in transitions:
            self.observe(tr.state, tr.action, tr.next_state)

    def tick(self) -> None:
        """Advance time one step: decay all counts by `recency_decay` (T-face).

        No-op when recency_decay == 1.0 (static world). Otherwise every visit /
        transition count is multiplied by the decay factor, so a state/edge not
        re-observed steadily loses mass → its novelty (1/√(N+1)) climbs back
        toward 1 (DE re-grows). Call once per environment step in continual /
        volatile contexts; never call it (or keep decay=1.0) for a static world.
        """
        if self._decay >= 1.0:
            return
        for s in list(self._state_visits):
            self._state_visits[s] *= self._decay
        for bucket in self._counts.values():
            for s in list(bucket):
                bucket[s] *= self._decay

    def _record_state(self, state: State) -> None:
        if state not in self._known_states_set:
            self._known_states.append(state)
            self._known_states_set.add(state)
        self._state_visits[state] += 1

    # ----- query -----

    def probability(self, state: State, action: Action, next_state: State) -> float:
        """P(next_state | state, action). 0 nếu (s,a) chưa quan sát."""
        bucket = self._counts.get((state, action))
        if not bucket:
            return 0.0
        total = sum(bucket.values())
        if total == 0:
            return 0.0
        return bucket[next_state] / total

    def sample_next(self, state: State, action: Action) -> State:
        """Sample s' ~ P(·|s,a). Nếu (s,a) novel: trả 1 known state random.

        Khi model chưa biết transition từ (s,a), CDFL spec từ luận văn
        coi đây là branch "DE" (Dark Existence): unknown region. Em dùng
        random known state làm proxy cho rollout — đây là CDFL v3 nguyên bản.
        Nếu chưa có known_state nào: trả lại chính `state` (self-loop fallback).
        """
        bucket = self._counts.get((state, action))
        if bucket and sum(bucket.values()) > 0:
            choices = list(bucket.keys())
            weights = list(bucket.values())
            return self._rng.choices(choices, weights=weights, k=1)[0]
        if self._known_states:
            return self._rng.choice(self._known_states)
        return state

    def state_visit_count(self, state: State) -> int:
        return self._state_visits.get(state, 0)

    def state_action_count(self, state: State, action: Action) -> int:
        bucket = self._counts.get((state, action))
        if not bucket:
            return 0
        return sum(bucket.values())

    @property
    def known_states(self) -> tuple[State, ...]:
        return tuple(self._known_states)

    @property
    def num_transitions_seen(self) -> int:
        return sum(self._state_visits.values())

    # ----- adapters cho Process Mining -----

    @classmethod
    def from_direct_follows(
        cls,
        direct_follows: dict[tuple[Hashable, Hashable], int],
        *,
        rng: random.Random | None = None,
    ) -> "TransitionModel":
        """Build a TransitionModel từ output của HeuristicMiner.mine().

        `direct_follows` là dict {(from_type, to_type): count}. CDFL coi:
        - state = from_type (current event type)
        - action = to_type (chuyển sang event type kế tiếp được chọn)
        - next_state = to_type (deterministic vì action chính là next state)

        Đây là cách tabular nhất để bridge Process Mining → CDFL. Phase 2
        có thể mở rộng action ≠ next_state (decision branching) — Phase 1
        keep equal.
        """
        model = cls(rng=rng)
        for (from_type, to_type), count in direct_follows.items():
            # Tabular bridge: action symbol = target event type.
            for _ in range(int(count)):
                model.observe(from_type, to_type, to_type)
        return model
