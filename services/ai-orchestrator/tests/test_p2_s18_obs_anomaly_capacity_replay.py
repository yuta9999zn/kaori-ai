"""
P2-S18 cross-cutting observability tests:
  OBS-018 — metric anomaly detection (z-score + EWMA)
  OBS-021 — capacity planning forecast
  OBS-023 — session replay with consent + PII redaction

8-section template:
  1. Mig 073 shape — 2 tables + CHECK + UNIQUE + indexes
  2. Z-score anomaly detection
  3. EWMA anomaly detection
  4. Capacity forecast (linear regression + edge cases)
  5. Session replay PII redaction
  6. Consent + recording endpoint smoke
  7. Tenant isolation
  8. Performance — 1000-point series anomaly scan < 50ms
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.observability import (
    MetricPoint,
    ResourceUsageHistory,
    detect_ewma_anomalies,
    detect_zscore_anomalies,
    forecast_capacity_linear,
    redact_recording_events,
    REDACTABLE_FIELDS,
)


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
SESSION_ID = "33333333-3333-3333-3333-333333333333"
HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}
ENTERPRISE_HEADERS = {"X-Enterprise-ID": ENTERPRISE}

REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"

NOW = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


def _row(**kw):
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kw[k]
    r.keys = MagicMock(return_value=list(kw.keys()))
    return r


def _make_app():
    from ai_orchestrator.routers import observability
    app = FastAPI()
    app.include_router(observability.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 073 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig073Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        return (MIG_DIR / "073_session_replay.sql").read_text(encoding="utf-8")

    def test_2_tables_present(self, mig_text: str):
        for t in ("user_session_consent", "user_session_recordings"):
            assert f"CREATE TABLE IF NOT EXISTS {t}" in mig_text

    def test_consent_unique_pair(self, mig_text: str):
        assert "uq_user_consent" in mig_text

    def test_consent_grant_revoke_check(self, mig_text: str):
        assert "chk_consent_grant_revoke" in mig_text

    def test_recording_duration_nonneg(self, mig_text: str):
        assert "chk_recording_duration_nonneg" in mig_text
        assert "duration_seconds >= 0" in mig_text

    def test_recording_expiry_future(self, mig_text: str):
        assert "chk_recording_expiry_future" in mig_text

    def test_indexes_present(self, mig_text: str):
        for idx in (
            "idx_session_consent_user",
            "idx_session_recordings_enterprise",
            "idx_session_recordings_user",
            "idx_session_recordings_expiry",
        ):
            assert idx in mig_text


# ═════════════════════════════════════════════════════════════════════
# 2. Z-score anomaly detection
# ═════════════════════════════════════════════════════════════════════


def _series(values: list[float], metric: str = "test") -> list[MetricPoint]:
    return [
        MetricPoint(
            timestamp=NOW + timedelta(hours=i),
            value=v, metric=metric,
        )
        for i, v in enumerate(values)
    ]


class TestZScoreDetector:

    def test_flat_series_no_alerts(self):
        alerts = detect_zscore_anomalies(_series([10.0] * 50), window=30)
        assert alerts == []

    def test_clear_spike_alerts(self):
        # 30 points around 10, then 1 huge spike at 100
        values = [10.0] * 30 + [100.0]
        alerts = detect_zscore_anomalies(_series(values), window=30,
                                         z_threshold=3.0)
        assert len(alerts) == 1
        assert alerts[0].severity in {"warning", "critical"}
        assert alerts[0].algorithm == "zscore"
        assert alerts[0].value == 100.0

    def test_window_smaller_than_history_yields_no_alerts(self):
        # Only 10 points, window 30 → no alerts (insufficient history)
        alerts = detect_zscore_anomalies(_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                         window=30)
        assert alerts == []

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            detect_zscore_anomalies(_series([1, 2, 3]), window=2, z_threshold=0)

    def test_severity_critical_for_very_high_z(self):
        # Build a clean baseline then add a 10-sigma spike
        baseline = [10.0 + (i % 2) * 0.1 for i in range(50)]  # very low variance
        values = baseline + [1000.0]
        alerts = detect_zscore_anomalies(_series(values), window=50)
        assert len(alerts) >= 1
        assert any(a.severity == "critical" for a in alerts)


# ═════════════════════════════════════════════════════════════════════
# 3. EWMA detector
# ═════════════════════════════════════════════════════════════════════


class TestEWMADetector:

    def test_flat_series_no_alerts(self):
        alerts = detect_ewma_anomalies(_series([100.0] * 50))
        assert alerts == []

    def test_step_change_fires_alert(self):
        # 20 points at 100, then jumps to 200 → 100% deviation
        values = [100.0] * 20 + [200.0]
        alerts = detect_ewma_anomalies(_series(values),
                                       deviation_pct_threshold=25.0)
        assert len(alerts) >= 1
        assert alerts[0].algorithm == "ewma"
        assert alerts[0].severity in {"warning", "critical"}

    def test_invalid_alpha_raises(self):
        with pytest.raises(ValueError):
            detect_ewma_anomalies(_series([1, 2]), alpha=1.5)

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError):
            detect_ewma_anomalies(_series([1, 2]), deviation_pct_threshold=-1)


# ═════════════════════════════════════════════════════════════════════
# 4. Capacity planning forecast
# ═════════════════════════════════════════════════════════════════════


def _capacity_history(values: list[float], resource="storage_gb",
                      limit=1000.0) -> ResourceUsageHistory:
    pts = tuple(
        (NOW + timedelta(days=i), v) for i, v in enumerate(values)
    )
    return ResourceUsageHistory(
        resource=resource, capacity_limit=limit, points=pts,
    )


class TestCapacityForecast:

    def test_flat_usage_recommendation(self):
        h = _capacity_history([500.0] * 14)
        f = forecast_capacity_linear(h, horizon_days=30)
        assert abs(f.slope_per_day) < 1e-6
        assert "ổn định" in f.recommendation.lower()
        assert f.projected_date_to_limit is None

    def test_growing_usage_projects_limit_date(self):
        # Linear growth 0→100 over 14 days; limit 1000
        h = _capacity_history(list(range(0, 1400, 100)))
        f = forecast_capacity_linear(h, horizon_days=30)
        assert f.slope_per_day > 0
        # Projected to cross limit somewhere
        assert f.projected_date_to_limit is not None

    def test_too_few_points_returns_wait_message(self):
        h = _capacity_history([100.0, 200.0, 300.0])
        f = forecast_capacity_linear(h, horizon_days=30, min_points=7)
        assert f.slope_per_day == 0.0
        assert "Cần ít nhất" in f.recommendation

    def test_decreasing_usage_no_limit_date(self):
        # Usage shrinking — slope negative
        h = _capacity_history([500.0 - i * 5 for i in range(14)])
        f = forecast_capacity_linear(h, horizon_days=30)
        assert f.slope_per_day < 0
        assert f.projected_date_to_limit is None

    def test_r_squared_perfect_for_clean_linear(self):
        h = _capacity_history([10.0 * i for i in range(14)])
        f = forecast_capacity_linear(h, horizon_days=30)
        assert f.r_squared > 0.99


# ═════════════════════════════════════════════════════════════════════
# 5. Session replay PII redaction
# ═════════════════════════════════════════════════════════════════════


class TestRedaction:

    def test_redactable_fields_masked(self):
        events = [
            {"type": 3, "data": {"text": "Hello, my name is Nguyen Van A"}},
            {"type": 3, "data": {"email": "user@example.com"}},
            {"type": 3, "data": {"phone": "0901234567"}},
        ]
        out = redact_recording_events(events)
        # text masked to <REDACTED>
        assert out[0]["data"]["text"] == "<REDACTED>"
        # email + phone in known-PII fields → <REDACTED>
        assert out[1]["data"]["email"] == "<REDACTED>"
        assert out[2]["data"]["phone"] == "<REDACTED>"

    def test_embedded_email_in_generic_field_masked(self):
        """A regular field like 'log_message' containing an email should
        still get regex-masked (defense-in-depth)."""
        events = [
            {"type": 5, "data": {"log_message": "User john@acme.com logged in"}},
        ]
        out = redact_recording_events(events)
        assert "john@acme.com" not in out[0]["data"]["log_message"]
        assert "<EMAIL>" in out[0]["data"]["log_message"]

    def test_phone_pattern_regex_masked(self):
        events = [{"data": {"description": "Call me at 0987654321"}}]
        out = redact_recording_events(events)
        assert "0987654321" not in out[0]["data"]["description"]
        assert "<PHONE>" in out[0]["data"]["description"]

    def test_empty_events_returns_empty(self):
        assert redact_recording_events([]) == []

    def test_redaction_is_non_destructive(self):
        events = [{"data": {"text": "secret"}}]
        original = [{"data": {"text": "secret"}}]
        redact_recording_events(events)
        # Caller's input unchanged
        assert events == original

    def test_redactable_fields_includes_pii_attrs(self):
        for f in ("email", "phone", "ssn", "creditCard", "fullName"):
            assert f in REDACTABLE_FIELDS


# ═════════════════════════════════════════════════════════════════════
# 6. Consent + recording endpoint smoke
# ═════════════════════════════════════════════════════════════════════


class TestEndpointSmoke:

    def test_set_consent_grant(self):
        from ai_orchestrator.routers import observability

        conn = _make_conn()
        conn.fetchrow.return_value = _row(
            consent_id=uuid4(), user_id=UUID(USER),
            granted=True, granted_at=NOW, revoked_at=None, notes=None,
        )
        with patch.object(observability, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/platform/observability/sessions/consent",
                            json={"granted": True}, headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["granted"] is True

    def test_submit_recording_without_consent_returns_403(self):
        from ai_orchestrator.routers import observability

        conn = _make_conn()
        conn.fetchrow.return_value = _row(granted=False)
        with patch.object(observability, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post(
                f"/platform/observability/sessions/{SESSION_ID}/record",
                json={
                    "started_at": NOW.isoformat(),
                    "events": [{"data": {"text": "foo"}}],
                },
                headers=HEADERS,
            )
        assert r.status_code == 403
        assert "consent" in r.json()["detail"]

    def test_metric_anomalies_invalid_metric_400(self):
        from ai_orchestrator.routers import observability

        conn = _make_conn()
        with patch.object(observability, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get(
                "/platform/observability/metric-anomalies?metric=bogus",
                headers=ENTERPRISE_HEADERS,
            )
        assert r.status_code == 400

    def test_capacity_invalid_resource_422(self):
        from ai_orchestrator.routers import observability

        conn = _make_conn()
        with patch.object(observability, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get(
                "/platform/observability/capacity?resource=alien",
                headers=ENTERPRISE_HEADERS,
            )
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 7. Tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    def test_anomaly_endpoint_requires_enterprise(self):
        client = TestClient(_make_app())
        r = client.get("/platform/observability/metric-anomalies?metric=api_p95_ms")
        assert r.status_code == 422

    def test_capacity_endpoint_requires_enterprise(self):
        client = TestClient(_make_app())
        r = client.get("/platform/observability/capacity?resource=storage_gb")
        assert r.status_code == 422

    def test_consent_requires_user(self):
        client = TestClient(_make_app())
        r = client.post("/platform/observability/sessions/consent",
                        json={"granted": True},
                        headers={"X-Enterprise-ID": ENTERPRISE})
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 8. Performance
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_1000_point_zscore_under_50ms(self):
        values = [10.0 + (i % 100) * 0.5 for i in range(1000)]
        t0 = time.perf_counter()
        detect_zscore_anomalies(_series(values), window=30)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.05, f"too slow: {elapsed:.3f}s"

    def test_1000_point_ewma_under_50ms(self):
        values = [100.0 + i * 0.1 for i in range(1000)]
        t0 = time.perf_counter()
        detect_ewma_anomalies(_series(values))
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.05, f"too slow: {elapsed:.3f}s"

    def test_redaction_1000_events_under_100ms(self):
        events = [
            {"type": 3, "data": {"text": f"message {i} from user@host.com",
                                  "email": f"u{i}@a.com"}}
            for i in range(1000)
        ]
        t0 = time.perf_counter()
        redact_recording_events(events)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"too slow: {elapsed:.3f}s"
