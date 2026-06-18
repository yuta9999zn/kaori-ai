"""
OBS-018 — Metric anomaly detection (P2-S18).

Two detection algorithms:
  - Z-score: classic statistical outlier detection on rolling window
  - EWMA: exponentially-weighted moving average + deviation band

Pure compute — caller passes in time-series points, gets back anomaly
alerts. No DB or HTTP I/O.

Both algorithms are deterministic + cheap (O(n)). Phase 3 swap to
isolation forest / autoencoder when data volume justifies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from math import sqrt
from typing import Iterable


@dataclass(frozen=True)
class MetricPoint:
    """One time-series sample."""
    timestamp: datetime
    value:     float
    metric:    str = ""


@dataclass(frozen=True)
class AnomalyAlert:
    """Detected anomaly with diagnostic context."""
    timestamp:  datetime
    metric:     str
    value:      float
    baseline:   float          # expected value
    deviation:  float          # observed - baseline (signed)
    severity:   str            # info / warning / critical
    algorithm:  str            # 'zscore' / 'ewma'
    z_score:    float = 0.0    # only for zscore alg
    threshold:  float = 0.0    # the threshold that fired


# ─── Severity bands ───────────────────────────────────────────────────


def _severity_for_zscore(z: float) -> str:
    abs_z = abs(z)
    if abs_z >= 4.0:
        return "critical"
    if abs_z >= 3.0:
        return "warning"
    return "info"


def _severity_for_ewma(deviation_pct: float) -> str:
    abs_d = abs(deviation_pct)
    if abs_d >= 50.0:
        return "critical"
    if abs_d >= 25.0:
        return "warning"
    return "info"


# ─── Z-score detector ────────────────────────────────────────────────


def detect_zscore_anomalies(
    points: Iterable[MetricPoint],
    *,
    window: int = 30,
    z_threshold: float = 3.0,
) -> list[AnomalyAlert]:
    """Sliding-window z-score detection.

    For each point at index i (where i >= window), compute mean+stddev
    of the prior `window` points. If |z| > threshold, emit an alert.

    Conservative defaults:
      window=30, z_threshold=3.0 → ~0.3% expected false-positive rate
      under Gaussian assumption.
    """
    pts = list(points)
    if len(pts) <= window:
        return []
    if z_threshold <= 0:
        raise ValueError("z_threshold must be > 0")

    alerts: list[AnomalyAlert] = []
    for i in range(window, len(pts)):
        prior = pts[i - window:i]
        n = len(prior)
        mean = sum(p.value for p in prior) / n
        variance = sum((p.value - mean) ** 2 for p in prior) / n
        stddev = sqrt(variance)
        if stddev == 0:
            # Degenerate — flat window. Any change is anomalous if
            # current differs; tag warning unless equal.
            current = pts[i]
            if current.value != mean:
                alerts.append(AnomalyAlert(
                    timestamp=current.timestamp,
                    metric=current.metric,
                    value=current.value,
                    baseline=mean,
                    deviation=current.value - mean,
                    severity="warning",
                    algorithm="zscore",
                    z_score=0.0,
                    threshold=z_threshold,
                ))
            continue

        current = pts[i]
        z = (current.value - mean) / stddev
        if abs(z) >= z_threshold:
            alerts.append(AnomalyAlert(
                timestamp=current.timestamp,
                metric=current.metric,
                value=current.value,
                baseline=mean,
                deviation=current.value - mean,
                severity=_severity_for_zscore(z),
                algorithm="zscore",
                z_score=z,
                threshold=z_threshold,
            ))
    return alerts


# ─── EWMA detector ───────────────────────────────────────────────────


def detect_ewma_anomalies(
    points: Iterable[MetricPoint],
    *,
    alpha: float = 0.3,
    deviation_pct_threshold: float = 25.0,
) -> list[AnomalyAlert]:
    """Exponentially-weighted moving average detection.

    EWMA_t = alpha * x_t + (1 - alpha) * EWMA_{t-1}
    If |x_t - EWMA_{t-1}| / |EWMA_{t-1}| * 100 > threshold_pct → anomaly.

    alpha=0.3 means recent points dominate (high responsiveness).
    threshold_pct=25 is conservative for business metrics.
    """
    pts = list(points)
    if len(pts) < 2:
        return []
    if not (0 < alpha <= 1):
        raise ValueError("alpha must be in (0, 1]")
    if deviation_pct_threshold <= 0:
        raise ValueError("deviation_pct_threshold must be > 0")

    alerts: list[AnomalyAlert] = []
    ewma = pts[0].value  # initialize at first point
    for i in range(1, len(pts)):
        current = pts[i]
        baseline = ewma
        deviation = current.value - baseline
        if baseline != 0:
            deviation_pct = (deviation / abs(baseline)) * 100.0
        else:
            deviation_pct = 100.0 if current.value != 0 else 0.0

        if abs(deviation_pct) >= deviation_pct_threshold:
            alerts.append(AnomalyAlert(
                timestamp=current.timestamp,
                metric=current.metric,
                value=current.value,
                baseline=baseline,
                deviation=deviation,
                severity=_severity_for_ewma(deviation_pct),
                algorithm="ewma",
                threshold=deviation_pct_threshold,
            ))
        # Update EWMA AFTER alert check (so the alert isn't dampened
        # by its own contribution to the baseline).
        ewma = alpha * current.value + (1 - alpha) * ewma
    return alerts
