"""60-day baseline collection.

A `BaselineTracker` collects (metric, value) observations over a
rolling window. The 60-day default mirrors the CLAUDE.md §5 Stage 12
spec; the window is configurable per experiment.

`summary()` returns mean + variance + sample size — enough for
ABTestFramework to use as the control distribution.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Observation:
    """One metric measurement.

    Attributes:
      tenant_id      — K-1 isolation key
      experiment_id  — optional; null means baseline-only (no A/B yet)
      metric_name    — 'conversion_rate' / 'avg_revenue' / 'churn_rate' / ...
      value          — the measurement
      occurred_at    — when the metric was observed (NOT recorded)
      arm            — 'control' | 'treatment' | None (None for baseline)
    """
    tenant_id:     UUID
    metric_name:   str
    value:         float
    occurred_at:   datetime    = field(default_factory=lambda: datetime.now(timezone.utc))
    experiment_id: Optional[str] = None
    arm:           Optional[str] = None
    observation_id: UUID        = field(default_factory=uuid4)


@dataclass(frozen=True)
class BaselineSummary:
    """Aggregate of observations inside a window."""
    tenant_id:     UUID
    metric_name:   str
    window_start:  datetime
    window_end:    datetime
    sample_size:   int
    mean:          float
    variance:      float
    stddev:        float

    @property
    def is_valid(self) -> bool:
        """Baseline needs ≥30 samples to be statistically meaningful at
        Phase 1.5 acceptance (rule of thumb — Phase 2 swaps for power
        calc). Below that, ABTestFramework refuses to call this a
        baseline."""
        return self.sample_size >= 30


class BaselineTracker:
    """Append-only store of Observations + windowed summary helpers.

    In-memory single-process. Phase 2 swaps backing dict for Postgres
    rows under `baseline_observations` table (mig TBD).
    """

    DEFAULT_WINDOW_DAYS = 60

    def __init__(self) -> None:
        # (tenant_id, metric_name) → list[Observation]
        self._obs: dict[tuple[UUID, str], list[Observation]] = defaultdict(list)

    def record(self, observation: Observation) -> Observation:
        """Append-only — never mutate prior rows."""
        key = (observation.tenant_id, observation.metric_name)
        self._obs[key].append(observation)
        return observation

    def observations(
        self, tenant_id: UUID, metric_name: str, *,
        window_days: int = DEFAULT_WINDOW_DAYS,
        experiment_id: Optional[str] = None,
        arm: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> list[Observation]:
        """Return observations matching filters, within the time window."""
        if now is None:
            now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=window_days)
        out: list[Observation] = []
        for o in self._obs.get((tenant_id, metric_name), []):
            if o.occurred_at < cutoff:
                continue
            if experiment_id is not None and o.experiment_id != experiment_id:
                continue
            if arm is not None and o.arm != arm:
                continue
            out.append(o)
        return out

    def summary(
        self, tenant_id: UUID, metric_name: str, *,
        window_days: int = DEFAULT_WINDOW_DAYS,
        experiment_id: Optional[str] = None,
        arm: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> BaselineSummary:
        """Compute mean + variance over the matched window."""
        if now is None:
            now = datetime.now(timezone.utc)
        obs = self.observations(
            tenant_id, metric_name, window_days=window_days,
            experiment_id=experiment_id, arm=arm, now=now,
        )
        n = len(obs)
        if n == 0:
            return BaselineSummary(
                tenant_id=tenant_id, metric_name=metric_name,
                window_start=now - timedelta(days=window_days),
                window_end=now, sample_size=0,
                mean=0.0, variance=0.0, stddev=0.0,
            )
        values = [o.value for o in obs]
        mean = sum(values) / n
        # Sample variance (Bessel's correction) when n>1; else 0.
        variance = (
            sum((v - mean) ** 2 for v in values) / (n - 1)
            if n > 1 else 0.0
        )
        return BaselineSummary(
            tenant_id=tenant_id, metric_name=metric_name,
            window_start=now - timedelta(days=window_days),
            window_end=now, sample_size=n,
            mean=mean, variance=variance,
            stddev=math.sqrt(variance),
        )

    def forget(self, tenant_id: UUID) -> int:
        """GDPR — wipe every observation for the tenant."""
        keys = [k for k in self._obs if k[0] == tenant_id]
        wiped = sum(len(self._obs[k]) for k in keys)
        for k in keys:
            del self._obs[k]
        return wiped
