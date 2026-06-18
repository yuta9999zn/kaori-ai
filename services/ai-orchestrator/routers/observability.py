"""
P2-S18 cross-cutting observability router — OBS-018, OBS-021, OBS-023.

Endpoints (mounted under /platform/observability)
-------------------------------------------------
OBS-018 — Anomaly detection:
    GET  /platform/observability/metric-anomalies
        ?metric=&window=&algorithm=&severity=

OBS-021 — Capacity planning:
    GET  /platform/observability/capacity
        ?resource=&horizon_days=

OBS-023 — Session replay:
    POST   /platform/observability/sessions/consent      grant or revoke
    GET    /platform/observability/sessions/consent      check current
    POST   /platform/observability/sessions/{session_id}/record
                                                          submit redacted events
    GET    /platform/observability/sessions/{session_id}/replay
                                                          fetch recorded events
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..org_intel.observability import (
    AnomalyAlert,
    CapacityForecast,
    MetricPoint,
    ResourceUsageHistory,
    detect_ewma_anomalies,
    detect_zscore_anomalies,
    forecast_capacity_linear,
    redact_recording_events,
)
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter(prefix="/platform/observability")


# ─── OBS-018 — Anomaly detection ─────────────────────────────────────


class AnomalyAlertOut(BaseModel):
    timestamp:  datetime
    metric:     str
    value:      float
    baseline:   float
    deviation:  float
    severity:   str
    algorithm:  str
    z_score:    float
    threshold:  float


@router.get("/metric-anomalies", response_model=list[AnomalyAlertOut])
async def detect_metric_anomalies(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    metric: str = Query(..., min_length=1, max_length=64,
                         description="Metric name to scan, e.g. 'api_p95_ms'"),
    window: int = Query(30, ge=10, le=200),
    algorithm: str = Query("zscore", pattern=r"^(zscore|ewma)$"),
    severity_min: str = Query("info", pattern=r"^(info|warning|critical)$"),
    lookback_hours: int = Query(24, ge=1, le=720),
):
    """Detect anomalies in a recent window of a metric's time series.

    Phase 1.5 reads from api_request_log + etl_run_log aggregations.
    Phase 2 will plumb through OTel/Prometheus directly.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Phase 1.5 baseline: aggregate api_request_log by hour for the
        # named metric. Currently supports a small whitelist.
        if metric == "api_p95_ms":
            rows = await conn.fetch(
                """SELECT date_trunc('hour', logged_at) AS bucket,
                          PERCENTILE_DISC(0.95) WITHIN GROUP (ORDER BY duration_ms) AS value
                   FROM api_request_log
                   WHERE enterprise_id = $1 AND logged_at >= $2
                   GROUP BY bucket ORDER BY bucket""",
                x_enterprise_id, cutoff,
            )
        elif metric == "api_error_rate":
            rows = await conn.fetch(
                """SELECT date_trunc('hour', logged_at) AS bucket,
                          AVG(CASE WHEN status_code >= 500 THEN 1.0 ELSE 0.0 END) AS value
                   FROM api_request_log
                   WHERE enterprise_id = $1 AND logged_at >= $2
                   GROUP BY bucket ORDER BY bucket""",
                x_enterprise_id, cutoff,
            )
        elif metric == "etl_failure_rate":
            rows = await conn.fetch(
                """SELECT date_trunc('hour', created_at) AS bucket,
                          AVG(CASE WHEN status = 'error' THEN 1.0 ELSE 0.0 END) AS value
                   FROM etl_run_log
                   WHERE enterprise_id = $1 AND created_at >= $2
                   GROUP BY bucket ORDER BY bucket""",
                x_enterprise_id, cutoff,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"metric={metric!r} not supported. Allowed: "
                    "api_p95_ms, api_error_rate, etl_failure_rate."
                ),
            )

    points = [
        MetricPoint(
            timestamp=r["bucket"],
            value=float(r["value"]) if r["value"] is not None else 0.0,
            metric=metric,
        )
        for r in rows
    ]

    if algorithm == "zscore":
        alerts = detect_zscore_anomalies(points, window=window)
    else:
        alerts = detect_ewma_anomalies(points)

    severity_rank = {"info": 0, "warning": 1, "critical": 2}
    min_rank = severity_rank[severity_min]
    filtered = [a for a in alerts if severity_rank[a.severity] >= min_rank]

    return [AnomalyAlertOut(**a.__dict__) for a in filtered]


# ─── OBS-021 — Capacity planning ─────────────────────────────────────


class CapacityForecastOut(BaseModel):
    resource:                 str
    current_usage:            float
    capacity_limit:           float
    usage_pct_now:            float
    slope_per_day:            float
    projected_usage_horizon:  float
    projected_date_to_limit:  Optional[datetime]
    r_squared:                float
    recommendation:           str
    horizon_days:             int


# In-memory capacity ceilings per resource. Phase 2 swap to a
# `capacity_limits` table editable by ops.
_CAPACITY_LIMITS: dict[str, float] = {
    "storage_gb":  1000.0,
    "connections": 500.0,
    "cpu_pct":     90.0,
    "memory_pct":  85.0,
}


@router.get("/capacity", response_model=CapacityForecastOut)
async def capacity_forecast(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    resource: str = Query(..., pattern=r"^(storage_gb|connections|cpu_pct|memory_pct)$"),
    horizon_days: int = Query(30, ge=1, le=180),
    lookback_days: int = Query(60, ge=7, le=365),
):
    """Project resource usage `horizon_days` ahead via linear regression."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Phase 1.5: use api_request_log volume as proxy for connections.
        # Storage / CPU / memory come from a `capacity_metrics_daily`
        # table in Phase 2; for now fall back to synthetic stub from
        # api_request_log when metric not directly available.
        rows = await conn.fetch(
            """SELECT date_trunc('day', logged_at) AS day,
                      COUNT(*) AS request_count
               FROM api_request_log
               WHERE enterprise_id = $1 AND logged_at >= $2
               GROUP BY day ORDER BY day""",
            x_enterprise_id, cutoff,
        )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No usage history for resource={resource!r} in lookback window",
        )

    # Scale request_count to the resource's pseudo-unit. Phase 2 reads
    # the real metric per-resource.
    scaler = {
        "storage_gb":  0.01,   # 100 requests ≈ 1 GB churn
        "connections": 1.0,    # peak concurrent connections proxy
        "cpu_pct":     0.001,  # rough proxy
        "memory_pct":  0.001,
    }[resource]
    pts = tuple((r["day"], float(r["request_count"]) * scaler) for r in rows)

    history = ResourceUsageHistory(
        resource=resource,
        capacity_limit=_CAPACITY_LIMITS[resource],
        points=pts,
    )
    forecast = forecast_capacity_linear(history, horizon_days=horizon_days)
    return CapacityForecastOut(**forecast.__dict__)


# ─── OBS-023 — Session replay ────────────────────────────────────────


class ConsentRequest(BaseModel):
    granted: bool
    notes:   Optional[str] = Field(default=None, max_length=500)


class ConsentOut(BaseModel):
    consent_id:  UUID
    user_id:     UUID
    granted:     bool
    granted_at:  Optional[datetime]
    revoked_at:  Optional[datetime]
    notes:       Optional[str]


class RecordingSubmit(BaseModel):
    started_at: datetime
    ended_at:   Optional[datetime] = None
    events:     list[dict] = Field(default_factory=list, max_length=10000)
    page_url:   Optional[str] = Field(default=None, max_length=1000)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    retention_days: int = Field(default=30, ge=1, le=365)


class RecordingOut(BaseModel):
    recording_id:     UUID
    user_id:          UUID
    session_id:       UUID
    started_at:       datetime
    ended_at:         Optional[datetime]
    duration_seconds: int
    page_url:         Optional[str]
    expires_at:       datetime
    event_count:      int


class ReplayOut(BaseModel):
    recording_id:     UUID
    session_id:       UUID
    started_at:       datetime
    duration_seconds: int
    events:           list[dict]


@router.post("/sessions/consent", response_model=ConsentOut)
async def set_consent(
    body: ConsentRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Grant or revoke session-replay consent for the calling user."""
    now = datetime.now(timezone.utc)
    granted_at = now if body.granted else None
    revoked_at = None if body.granted else now
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO user_session_consent
                   (enterprise_id, user_id, granted, granted_at, revoked_at, notes)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (enterprise_id, user_id) DO UPDATE SET
                   granted    = EXCLUDED.granted,
                   granted_at = CASE
                       WHEN EXCLUDED.granted THEN EXCLUDED.granted_at
                       ELSE user_session_consent.granted_at
                   END,
                   revoked_at = EXCLUDED.revoked_at,
                   notes      = EXCLUDED.notes,
                   updated_at = NOW()
               RETURNING *""",
            x_enterprise_id, x_user_id, body.granted,
            granted_at, revoked_at, body.notes,
        )
    return ConsentOut(
        consent_id=row["consent_id"], user_id=row["user_id"],
        granted=row["granted"], granted_at=row["granted_at"],
        revoked_at=row["revoked_at"], notes=row["notes"],
    )


@router.get("/sessions/consent", response_model=Optional[ConsentOut])
async def get_consent(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Return current consent state for the calling user, or null if
    no consent record exists yet (implies not-opted-in)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT * FROM user_session_consent
               WHERE enterprise_id = $1 AND user_id = $2""",
            x_enterprise_id, x_user_id,
        )
    if row is None:
        return None
    return ConsentOut(
        consent_id=row["consent_id"], user_id=row["user_id"],
        granted=row["granted"], granted_at=row["granted_at"],
        revoked_at=row["revoked_at"], notes=row["notes"],
    )


@router.post(
    "/sessions/{session_id}/record",
    response_model=RecordingOut, status_code=201,
)
async def submit_recording(
    body: RecordingSubmit,
    session_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Submit a redacted session recording. Server re-applies redaction
    (defense-in-depth) before persisting."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        consent = await conn.fetchrow(
            """SELECT granted FROM user_session_consent
               WHERE enterprise_id = $1 AND user_id = $2""",
            x_enterprise_id, x_user_id,
        )
        if consent is None or not consent["granted"]:
            raise HTTPException(
                status_code=403,
                detail="user has not granted session-replay consent",
            )

        # K-5 defense-in-depth: re-redact before persist
        redacted = redact_recording_events(body.events)
        ended = body.ended_at or body.started_at
        duration = int((ended - body.started_at).total_seconds()) if ended else 0
        if duration < 0:
            raise HTTPException(status_code=400,
                                detail="ended_at must be >= started_at")
        expires = body.started_at + timedelta(days=body.retention_days)

        import json
        row = await conn.fetchrow(
            """INSERT INTO user_session_recordings
                   (enterprise_id, user_id, session_id,
                    started_at, ended_at, duration_seconds,
                    recording_events, page_url, user_agent, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10)
               RETURNING *""",
            x_enterprise_id, x_user_id, session_id,
            body.started_at, ended, duration,
            json.dumps(redacted), body.page_url, body.user_agent, expires,
        )
    return RecordingOut(
        recording_id=row["recording_id"], user_id=row["user_id"],
        session_id=row["session_id"],
        started_at=row["started_at"], ended_at=row["ended_at"],
        duration_seconds=row["duration_seconds"],
        page_url=row["page_url"], expires_at=row["expires_at"],
        event_count=len(redacted),
    )


@router.get("/sessions/{session_id}/replay", response_model=ReplayOut)
async def get_replay(
    session_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Fetch the recorded event stream. Returns redacted events
    (K-5) — the raw was never stored."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT * FROM user_session_recordings
               WHERE session_id = $1 AND expires_at > NOW()""",
            session_id,
        )
    if row is None:
        raise HTTPException(status_code=404,
                            detail="recording not found or expired")
    import json
    events = row["recording_events"]
    if isinstance(events, str):
        events = json.loads(events)
    return ReplayOut(
        recording_id=row["recording_id"],
        session_id=row["session_id"],
        started_at=row["started_at"],
        duration_seconds=row["duration_seconds"],
        events=events,
    )
