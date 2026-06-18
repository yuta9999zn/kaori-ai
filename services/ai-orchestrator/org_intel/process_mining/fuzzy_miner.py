"""
PM-ALG-017 (P2-S14) — Fuzzy Miner (noise-tolerant variant).

Where Heuristic Miner / Inductive Miner produce deterministic graphs,
Fuzzy Miner abstracts low-significance + low-correlation edges into a
softer view. The key idea (Günther 2009): every event-type has a
**significance** (how often it occurs), every edge has a **correlation**
(how reliably one follows another), and the operator only displays
edges/nodes above a configurable threshold band.

For Kaori SME workflows this matters for **noisy chat-driven processes**
(Slack/Teams + email): there are hundreds of low-frequency event types
that swamp the canvas. Fuzzy Miner collapses the noise so the manager
sees the 5-10 important paths.

Output: FuzzyGraph with two thresholds applied:
  * significance_threshold — minimum activity frequency to display
  * correlation_threshold — minimum edge-strength to display

Edges below the correlation threshold are NOT dropped — they're
**bundled** into "rare path" aggregate edges so coverage is preserved.

Phase 2 baseline; Phase 3 may add edge-pruning by binary correlation
metrics + alphabetical clustering. We ship the metrics + the threshold
filter; FE renders the bundle visualisation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .case_inference import infer_cases
from .types import EventLog


@dataclass(frozen=True)
class FuzzyEdge:
    """One edge in the fuzzy graph."""
    from_act:        str
    to_act:          str
    count:           int
    correlation:     float    # 0-1; #(f→t) / #(f appearing followed by anything)
    significance:    float    # 0-1; normalized count vs max edge
    is_bundled:      bool = False    # True for synthetic 'rare paths' edge


@dataclass(frozen=True)
class FuzzyResult:
    """Output of FuzzyMiner.mine()."""
    nodes:                  tuple[str, ...]
    edges:                  tuple[FuzzyEdge, ...]
    pruned_node_count:      int
    pruned_edge_count:      int
    correlation_threshold:  float
    significance_threshold: float


class FuzzyMiner:
    """Noise-tolerant Process Mining.

    Args:
      significance_threshold: drop activities below this fraction of the
                                most-frequent activity (default 0.10 = 10%).
      correlation_threshold:  bundle edges below this correlation
                                (default 0.20 = 20%); kept as a single
                                synthetic bundle so coverage stays 100%.
    """

    def __init__(
        self, *,
        significance_threshold: float = 0.10,
        correlation_threshold: float = 0.20,
    ):
        if not 0.0 <= significance_threshold <= 1.0:
            raise ValueError(f"significance_threshold must be in [0,1]")
        if not 0.0 <= correlation_threshold <= 1.0:
            raise ValueError(f"correlation_threshold must be in [0,1]")
        self.significance_threshold = significance_threshold
        self.correlation_threshold = correlation_threshold

    def mine(self, event_log: EventLog) -> FuzzyResult:
        cases = list(infer_cases(event_log.events).values())
        if not cases:
            return FuzzyResult(
                nodes=(), edges=(), pruned_node_count=0, pruned_edge_count=0,
                correlation_threshold=self.correlation_threshold,
                significance_threshold=self.significance_threshold,
            )

        # 1. Activity counts.
        activity_counts: Counter[str] = Counter()
        for case in cases:
            for ev in case:
                activity_counts[ev.event_type] += 1
        if not activity_counts:
            return FuzzyResult(
                nodes=(), edges=(), pruned_node_count=0, pruned_edge_count=0,
                correlation_threshold=self.correlation_threshold,
                significance_threshold=self.significance_threshold,
            )

        max_count = max(activity_counts.values())
        kept_acts = {
            a for a, c in activity_counts.items()
            if c / max_count >= self.significance_threshold
        }
        pruned_node_count = len(activity_counts) - len(kept_acts)

        # 2. Direct-follow edges.
        follows: Counter[tuple[str, str]] = Counter()
        out_count: Counter[str] = Counter()
        for case in cases:
            for i in range(len(case) - 1):
                f = case[i].event_type
                t = case[i + 1].event_type
                if f in kept_acts and t in kept_acts:
                    follows[(f, t)] += 1
                    out_count[f] += 1

        if not follows:
            return FuzzyResult(
                nodes=tuple(sorted(kept_acts)),
                edges=(),
                pruned_node_count=pruned_node_count,
                pruned_edge_count=0,
                correlation_threshold=self.correlation_threshold,
                significance_threshold=self.significance_threshold,
            )

        max_edge = max(follows.values())
        # 3. Per-edge correlation + significance + threshold.
        kept_edges: list[FuzzyEdge] = []
        pruned_edges: list[FuzzyEdge] = []
        for (f, t), c in follows.items():
            corr = c / max(out_count[f], 1)
            sig = c / max_edge
            edge = FuzzyEdge(
                from_act=f, to_act=t, count=c,
                correlation=round(corr, 4),
                significance=round(sig, 4),
            )
            if corr >= self.correlation_threshold:
                kept_edges.append(edge)
            else:
                pruned_edges.append(edge)

        # 4. Bundle pruned edges into a synthetic edge so coverage isn't lost.
        if pruned_edges:
            bundle_count = sum(e.count for e in pruned_edges)
            kept_edges.append(FuzzyEdge(
                from_act="__bundle__", to_act="__bundle__",
                count=bundle_count,
                correlation=0.0, significance=round(bundle_count / max_edge, 4),
                is_bundled=True,
            ))

        return FuzzyResult(
            nodes=tuple(sorted(kept_acts)),
            edges=tuple(kept_edges),
            pruned_node_count=pruned_node_count,
            pruned_edge_count=len(pruned_edges),
            correlation_threshold=self.correlation_threshold,
            significance_threshold=self.significance_threshold,
        )
