"""
Gap 3 chaos test — /health/temporal endpoint surfaces worker presence.

The "schedules fire into a void" failure: TEMPORAL_ENABLE_WORKER=true
but no worker process running → activated crons (adoption hourly,
NOV monthly, memory loops) silently queue with no consumer. This
endpoint detects that gap so K8s readiness probe can fail the pod.

Cases:
  H1  TEMPORAL_ENABLE_WORKER=false → 200 status='disabled'
       (deliberate config — early Phase 1.5 envs without Temporal)
  H2  Worker enabled + cluster reachable + workers present → 200
       status='healthy' with per-queue poller counts
  H3  Worker enabled + cluster reachable + ZERO workers anywhere → 503
       status='no_workers' (the actual gap we're closing)
  H4  Worker enabled + cluster unreachable → 503 status='cluster_unreachable'
  H5  Per-queue probe partial failure → 200 if SOME queue has workers;
       probe_errors surface in body for visibility
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.routers import temporal_health


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(temporal_health.router)
    return TestClient(app)


# ─── H1: disabled by config → 200 status=disabled ──────────────────


def test_h1_disabled_config_returns_200(client, monkeypatch):
    """When TEMPORAL_ENABLE_WORKER not truthy, endpoint surfaces the
    deliberate config — NOT a fault."""
    fake_cfg = MagicMock(
        enable_worker=False,
        address="localhost:7233",
        namespace="kaori",
        task_queue="kaori-default",
    )
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.TemporalConfig.from_env",
        staticmethod(lambda: fake_cfg),
    )
    r = client.get("/health/temporal")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "disabled"
    assert body["worker_count"] == 0


# ─── H2: workers present → 200 status=healthy ──────────────────────


def test_h2_workers_present_returns_healthy(client, monkeypatch):
    """Worker enabled + describe_task_queue returns non-empty pollers
    on at least one critical queue."""
    fake_cfg = MagicMock(
        enable_worker=True, address="t:7233",
        namespace="kaori", task_queue="kaori-default",
    )
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.TemporalConfig.from_env",
        staticmethod(lambda: fake_cfg),
    )

    # Fake describe_task_queue → 2 pollers on kaori-default, 1 elsewhere
    poller_counts_by_queue = {
        "kaori-default":          2,
        "kaori-critical-finance": 1,
        "kaori-low-priority":     0,
    }

    async def _fake_describe(req):
        resp = MagicMock()
        # `req.task_queue` is a TaskQueue proto with `name` attr
        q = req.task_queue.name
        resp.pollers = [MagicMock()] * poller_counts_by_queue.get(q, 0)
        return resp

    fake_client = MagicMock()
    fake_client.workflow_service = MagicMock()
    fake_client.workflow_service.describe_task_queue = AsyncMock(
        side_effect=_fake_describe,
    )

    async def _fake_connect(cfg): return fake_client
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.connect",
        _fake_connect,
    )

    r = client.get("/health/temporal")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "healthy"
    assert body["total_workers"] == 3
    assert body["queues"]["kaori-default"] == 2
    assert body["queues"]["kaori-critical-finance"] == 1


# ─── H3: enabled + ZERO workers → 503 status=no_workers ────────────


def test_h3_zero_workers_returns_503(client, monkeypatch):
    """The actual gap we're closing: enabled flag set, cluster
    reachable, but every critical queue reports 0 pollers."""
    fake_cfg = MagicMock(
        enable_worker=True, address="t:7233",
        namespace="kaori", task_queue="kaori-default",
    )
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.TemporalConfig.from_env",
        staticmethod(lambda: fake_cfg),
    )

    async def _zero_pollers(req):
        resp = MagicMock()
        resp.pollers = []
        return resp

    fake_client = MagicMock()
    fake_client.workflow_service = MagicMock()
    fake_client.workflow_service.describe_task_queue = AsyncMock(
        side_effect=_zero_pollers,
    )
    async def _fake_connect(cfg): return fake_client
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.connect",
        _fake_connect,
    )

    r = client.get("/health/temporal")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "no_workers"
    assert body["total_workers"] == 0
    assert "detail" in body
    # K8s ops will see this — sanity check it explains the failure
    assert "TEMPORAL_ENABLE_WORKER" in body["detail"]


# ─── H4: cluster unreachable → 503 status=cluster_unreachable ──────


def test_h4_cluster_unreachable_returns_503(client, monkeypatch):
    """Temporal frontend down → connect() raises → endpoint reports
    `cluster_unreachable` with error_type so ops can distinguish from
    `no_workers`."""
    fake_cfg = MagicMock(
        enable_worker=True, address="t:7233",
        namespace="kaori", task_queue="kaori-default",
    )
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.TemporalConfig.from_env",
        staticmethod(lambda: fake_cfg),
    )

    async def _fail_connect(cfg):
        raise ConnectionRefusedError("temporal-frontend not reachable")
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.connect",
        _fail_connect,
    )

    r = client.get("/health/temporal")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "cluster_unreachable"
    assert body["error_type"] == "ConnectionRefusedError"


# ─── H5: partial probe failure but ≥1 worker → still healthy ───────


def test_h5_partial_probe_failure_still_healthy(client, monkeypatch):
    """describe_task_queue fails for one queue but others succeed with
    pollers > 0 → endpoint reports healthy + probe_errors surfaced."""
    fake_cfg = MagicMock(
        enable_worker=True, address="t:7233",
        namespace="kaori", task_queue="kaori-default",
    )
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.TemporalConfig.from_env",
        staticmethod(lambda: fake_cfg),
    )

    async def _mixed(req):
        q = req.task_queue.name
        if q == "kaori-critical-finance":
            raise TimeoutError("probe timeout on finance queue")
        resp = MagicMock()
        resp.pollers = [MagicMock()] * (3 if q == "kaori-default" else 0)
        return resp

    fake_client = MagicMock()
    fake_client.workflow_service = MagicMock()
    fake_client.workflow_service.describe_task_queue = AsyncMock(
        side_effect=_mixed,
    )
    async def _fake_connect(cfg): return fake_client
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.temporal_client.connect",
        _fake_connect,
    )

    r = client.get("/health/temporal")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["queues"]["kaori-default"] == 3
    assert body["queues"]["kaori-critical-finance"] == 0
    assert "probe_errors" in body
    assert body["probe_errors"]["kaori-critical-finance"] == "TimeoutError"
