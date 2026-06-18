"""
PM-ALG-015 (P1-S7) — Heuristic Miner baseline for Phase 1.

Heuristic Miner counts direct-follow relations between event_types
across all cases, then keeps the relations that pass a frequency
threshold. Output is a directed graph of event_type → next_event_type
with weights.

This is the simplest Process Mining algorithm that actually works —
sufficient for Phase 1 SME workflows (typically 5-15 distinct event
types per process). Phase 2 swaps in Inductive Miner + Fuzzy Miner
for noisier event logs.

PM-ALG-019 (temporal pattern) + PM-ALG-020 (frequency analysis) are
implemented inline here because they're cheap byproducts of the same
direct-follow scan.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .case_inference import infer_cases
from .types import Event, EventLog


@dataclass(frozen=True)
class MinedWorkflow:
    """Output of HeuristicMiner.mine() — a workflow graph + analytics.

    Fields:
      direct_follows  — {(from_type, to_type): count} edges that passed
                        the frequency threshold
      event_counts    — {event_type: count} how often each type fired
      avg_durations   — {(from_type, to_type): seconds} mean elapsed
                        between adjacent steps (PM-ALG-019)
      case_count      — total cases mined
    """
    direct_follows: dict[tuple[str, str], int] = field(default_factory=dict)
    event_counts: dict[str, int] = field(default_factory=dict)
    avg_durations: dict[tuple[str, str], float] = field(default_factory=dict)
    case_count: int = 0


class HeuristicMiner:
    """Baseline Heuristic Miner.

    Args:
        min_frequency: drop direct-follow edges occurring fewer than
                       N times. Default 1 (Phase 1 — keep everything;
                       Phase 1.5+ tune per data volume).

    Usage::

        miner = HeuristicMiner(min_frequency=2)
        result = miner.mine(event_log)
        # → MinedWorkflow with direct_follows + counts + durations
    """

    def __init__(self, *, min_frequency: int = 1) -> None:
        if min_frequency < 1:
            raise ValueError("min_frequency must be >= 1")
        self.min_frequency = min_frequency

    def mine(self, log: EventLog) -> MinedWorkflow:
        """Run the algorithm against a session-scoped EventLog."""
        cases = infer_cases(log.events)
        return self._mine_cases(cases)

    def _mine_cases(self, cases: dict[str, list[Event]]) -> MinedWorkflow:
        """Internal — accept pre-grouped cases (used by tests)."""
        direct_follows: Counter[tuple[str, str]] = Counter()
        event_counts: Counter[str] = Counter()
        # durations[(from, to)] = list of elapsed seconds, averaged at end
        durations: dict[tuple[str, str], list[float]] = defaultdict(list)

        for case_events in cases.values():
            for ev in case_events:
                event_counts[ev.event_type] += 1

            # Adjacent pairs in chronological order → direct-follow
            for prev, curr in zip(case_events, case_events[1:]):
                edge = (prev.event_type, curr.event_type)
                direct_follows[edge] += 1
                durations[edge].append(
                    (curr.occurred_at - prev.occurred_at).total_seconds()
                )

        # Apply frequency threshold
        kept_follows = {
            edge: count
            for edge, count in direct_follows.items()
            if count >= self.min_frequency
        }
        kept_durations = {
            edge: statistics.mean(durs)
            for edge, durs in durations.items()
            if edge in kept_follows
        }

        return MinedWorkflow(
            direct_follows=kept_follows,
            event_counts=dict(event_counts),
            avg_durations=kept_durations,
            case_count=len(cases),
        )
