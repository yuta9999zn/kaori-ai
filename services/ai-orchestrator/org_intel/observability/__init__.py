"""P2-S18 Cross-cutting observability features.

Three modules:
  - anomaly_detector.py — OBS-018 metric anomaly detection (z-score + EWMA)
  - capacity_planning.py — OBS-021 resource usage forecasting
  - session_replay.py    — OBS-023 helpers (consent + PII redaction)

All pure computation. I/O lives in routers/observability.py.
"""

from .anomaly_detector import (
    AnomalyAlert,
    MetricPoint,
    detect_zscore_anomalies,
    detect_ewma_anomalies,
)
from .capacity_planning import (
    CapacityForecast,
    ResourceUsageHistory,
    forecast_capacity_linear,
)
from .session_replay import (
    REDACTABLE_FIELDS,
    redact_recording_events,
)

__all__ = [
    "AnomalyAlert",
    "MetricPoint",
    "detect_zscore_anomalies",
    "detect_ewma_anomalies",
    "CapacityForecast",
    "ResourceUsageHistory",
    "forecast_capacity_linear",
    "REDACTABLE_FIELDS",
    "redact_recording_events",
]
