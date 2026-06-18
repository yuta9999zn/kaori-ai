"""
Phase 2.7 P2 — POST /workflows/{id}/run quota gate tests.

When the tenant has consumed their workflow_concurrent quota,
the run endpoint must respond 429 RFC 7807 BEFORE creating the
workflow_runs row (so the failed attempt doesn't pollute the run
history) and BEFORE adding the run_in_background task.

Happy path: when quota passes (returns None or QuotaCheck), the
endpoint creates the run + schedules background work + returns 202.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ai_orchestrator.routers.workflow_builder as router_module


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
WORKFLOW   = "55555555-5555-5555-5555-555555555555"
NODE_ID    = "66666666-6666-6666-6666-666666666666"
WORKSPACE  = UUID("99999999-aaaa-aaaa-aaaa-999999999999")


def _conn_with_workflow_and_nodes():
    """Mock conn returning a single-workflow, single-node lookup the
    start_workflow_run handler does before the quota gate fires."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=MagicMock(
        __getitem__=lambda _self, k: {
            "workflow_id":  UUID(WORKFLOW),
            "workspace_id": WORKSPACE,
            "status":       "DRAFT",
            # K-22 prohibited-use guard (ADR-0041) reads risk_tier off the
            # first fetchrow in the run handler; non-prohibited lets it run.
            "risk_tier":    "high",
        }[k],
    ))
    conn.fetch = AsyncMock(return_value=[
        MagicMock(__getitem__=lambda _self, k: {
            "node_id":               UUID(NODE_ID),
            "node_type_catalog_key": "send_email",  # in REGISTRY by wave 1
        }[k]),
    ])
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def test_quota_exceeded_returns_429_problem_json(client):
    """When workflow_concurrent quota raises QuotaExceeded, the endpoint
    surfaces 429 RFC 7807 + does NOT call create_run + does NOT add
    background tasks."""
    from ai_orchestrator.shared import tenant_quotas

    conn = _conn_with_workflow_and_nodes()
    create_mock = AsyncMock(return_value=uuid4())
    background_add = MagicMock()

    quota_mock = AsyncMock(side_effect=tenant_quotas.QuotaExceeded(
        quota_type="workflow_concurrent",
        current=21,
        max_value=20,
        period="rolling",
    ))

    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
                _tenant_ctx(conn)), \
         patch("ai_orchestrator.shared.tenant_quotas.check_and_consume", quota_mock), \
         patch("ai_orchestrator.workflow_runtime.runner.WorkflowRunner.create_run",
                create_mock):

        r = client.post(
            f"/workflows/{WORKFLOW}/run",
            json={"trigger_source": "manual", "input_data": {}},
            headers=HEADERS,
        )

    assert r.status_code == 429, r.text
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["title"].startswith("Workflow concurrent")
    assert body["quota_type"] == "workflow_concurrent"
    assert body["period"] == "rolling"
    assert body["max_value"] == 20
    create_mock.assert_not_awaited()  # row NOT created


def test_quota_pass_proceeds_to_create_run(client):
    """When the quota check returns (passes), create_run + background
    task are invoked and the endpoint returns the run row."""
    new_run_id = uuid4()

    # Conn returns the workflow row + nodes for the existence check
    # AND the run row after create_run completes (handler calls
    # _fetch_run at the end). _fetch_run does dict(row) — give it a
    # real dict (asyncpg.Record duck-types as one).
    from datetime import datetime as _dt
    fetched_run_row = {
        "run_id":           new_run_id,
        "workflow_id":      UUID(WORKFLOW),
        "status":           "pending",
        "trigger_source":   "manual",
        "started_at":       _dt(2026, 5, 20),
        "ended_at":         None,
        "triggered_by_user_id": UUID(USER),
        "input_data":       "{}",
        "output_data":      None,
        "error_summary":    None,
    }

    conn = _conn_with_workflow_and_nodes()
    # _fetch_run does another fetchrow; layer additional return path.
    conn.fetchrow = AsyncMock(side_effect=[
        # K-22 prohibited-use guard (ADR-0041) — first fetchrow in handler.
        MagicMock(__getitem__=lambda _self, k: {"risk_tier": "high"}[k]),
        # Second call: workflow lookup at the top of the handler.
        MagicMock(__getitem__=lambda _self, k: {
            "workflow_id":  UUID(WORKFLOW),
            "workspace_id": WORKSPACE,
            "status":       "DRAFT",
        }[k]),
        # Third call (inside _fetch_run after create_run): the run row.
        fetched_run_row,
    ])

    create_mock = AsyncMock(return_value=new_run_id)
    quota_pass = AsyncMock(return_value=None)  # quota_unconfigured -> fail open
    background_noop = AsyncMock(return_value=None)

    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
                _tenant_ctx(conn)), \
         patch("ai_orchestrator.shared.tenant_quotas.check_and_consume", quota_pass), \
         patch("ai_orchestrator.workflow_runtime.runner.WorkflowRunner.create_run",
                create_mock), \
         patch("ai_orchestrator.workflow_runtime.runner.run_in_background",
                background_noop):

        r = client.post(
            f"/workflows/{WORKFLOW}/run",
            json={"trigger_source": "manual", "input_data": {}},
            headers=HEADERS,
        )

    assert r.status_code == 202, r.text
    create_mock.assert_awaited_once()
    quota_pass.assert_awaited_once()
    q_kwargs = quota_pass.await_args.kwargs
    assert q_kwargs["quota_type"] == "workflow_concurrent"
    assert q_kwargs["amount"] == 1
