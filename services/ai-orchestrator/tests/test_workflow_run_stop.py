"""
Task 4 — POST /workflow-runs/{run_id}/stop (EU AI Act Art 14 / K-23).

Human oversight: a user can stop a run mid-flight. The endpoint cancels the
run (workflow_runs.status -> 'cancelled'), cancels any pending approval gate,
and fires saga compensation for already-executed impactful nodes.

Contract:
  • awaiting_approval / running / queued -> 200, cancelled + compensation
  • already 'cancelled'                  -> 200 idempotent, NO compensation
  • completed (terminal)                 -> 409
  • missing run                          -> 404
  • missing X-Enterprise-ID header       -> 422

Pattern mirrors test_workflow_prohibited_block.py: fake conn + TestClient +
patch of acquire_for_tenant. run_compensation_chain is imported INSIDE the
handler, so we patch it at its source module
(ai_orchestrator.workflow_runtime.compensation.run_compensation_chain).
"""
from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "55555555-5555-5555-5555-555555555555"
RUN_ID = "99999999-9999-9999-9999-999999999999"
WORKFLOW_ID = "66666666-6666-6666-6666-666666666666"
NODE_ID = "33333333-3333-3333-3333-333333333333"

HEADERS = {"X-Enterprise-ID": ENTERPRISE_ID, "X-User-ID": USER_ID}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _ctx(conn):
    @asynccontextmanager
    async def _fake(*_args, **_kwargs):
        yield conn
    return _fake


def _fetch_run_row(status: str) -> MagicMock:
    """WorkflowRunOut-shaped row returned by _fetch_run's SELECT."""
    return _row(
        run_id=UUID(RUN_ID),
        workflow_id=UUID(WORKFLOW_ID),
        status=status,
        trigger_source="manual",
        started_at=datetime.datetime(2026, 6, 3),
        ended_at=datetime.datetime(2026, 6, 3),
        triggered_by_user_id=UUID(USER_ID),
        input_data={},
        output_data={},
        error_summary=None,
    )


def _make_conn(run_status: str | None, *, anchor: bool = True) -> AsyncMock:
    """Fake tenant connection.

    fetchrow dispatches on SQL text:
      • SELECT status FROM workflow_runs    -> seeded status row (or None)
      • workflow_run_nodes (anchor)         -> a node row (or None)
      • _fetch_run's SELECT (...FROM workflow_runs WHERE run_id) -> cancelled row
    execute records every UPDATE for assertions.
    """
    conn = AsyncMock()
    status_row = _row(status=run_status) if run_status is not None else None
    anchor_row = _row(node_id=UUID(NODE_ID)) if anchor else None
    # _fetch_run always reports the final (cancelled) state.
    final_row = _fetch_run_row("cancelled")

    async def _fetchrow(sql, *args, **kwargs):
        s = sql if isinstance(sql, str) else str(sql)
        if "workflow_run_nodes" in s:
            return anchor_row
        if "SELECT status FROM workflow_runs" in s:
            return status_row
        # _fetch_run's richer SELECT FROM workflow_runs
        if "FROM workflow_runs" in s:
            return final_row
        return None

    conn.fetchrow.side_effect = _fetchrow
    conn.fetch.return_value = []
    conn.fetchval.return_value = 0
    conn.execute.return_value = "OK"
    return conn


def _client() -> TestClient:
    import ai_orchestrator.routers.workflow_builder as wb
    from ai_orchestrator.shared.errors import register_problem_handlers
    test_app = FastAPI()
    test_app.include_router(wb.router)
    register_problem_handlers(test_app)
    return TestClient(test_app, raise_server_exceptions=True)


def _update_calls(conn, needle: str) -> list:
    return [
        call for call in conn.execute.await_args_list
        if needle in str(call.args[0])
    ]


# ─── 1. happy path: awaiting_approval -> cancelled + compensation ─────


def test_stop_awaiting_approval_run_cancels_and_compensates():
    conn = _make_conn("awaiting_approval", anchor=True)
    comp = AsyncMock()
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)), \
         patch("ai_orchestrator.workflow_runtime.compensation.run_compensation_chain",
               comp):
        with _client() as c:
            resp = c.post(
                f"/workflow-runs/{RUN_ID}/stop",
                json={"reason": "stop it"},
                headers=HEADERS,
            )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    runs_upd = _update_calls(conn, "UPDATE workflow_runs SET status = 'cancelled'")
    assert runs_upd, "workflow_runs must be cancelled"
    appr_upd = _update_calls(conn, "UPDATE workflow_approvals SET status = 'cancelled'")
    assert appr_upd, "pending approval must be cancelled"

    comp.assert_awaited_once()
    _, kwargs = comp.await_args
    assert kwargs["enterprise_id"] == UUID(ENTERPRISE_ID)
    assert kwargs["run_id"] == UUID(RUN_ID)
    assert kwargs["failed_node_id"] == UUID(NODE_ID)


# ─── 2. idempotent: already cancelled -> 200, no compensation ────────


def test_stop_already_cancelled_is_idempotent():
    conn = _make_conn("cancelled", anchor=True)
    comp = AsyncMock()
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)), \
         patch("ai_orchestrator.workflow_runtime.compensation.run_compensation_chain",
               comp):
        with _client() as c:
            resp = c.post(
                f"/workflow-runs/{RUN_ID}/stop",
                json={},
                headers=HEADERS,
            )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    comp.assert_not_awaited()
    # no second cancel UPDATE on an already-cancelled run
    assert _update_calls(conn, "UPDATE workflow_runs SET status = 'cancelled'") == []


# ─── 3. terminal completed -> 409 ────────────────────────────────────


def test_stop_completed_run_409():
    conn = _make_conn("completed", anchor=True)
    comp = AsyncMock()
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)), \
         patch("ai_orchestrator.workflow_runtime.compensation.run_compensation_chain",
               comp):
        with _client() as c:
            resp = c.post(
                f"/workflow-runs/{RUN_ID}/stop",
                json={},
                headers=HEADERS,
            )

    assert resp.status_code == 409, resp.text
    comp.assert_not_awaited()


# ─── 4. missing run -> 404 ───────────────────────────────────────────


def test_stop_missing_run_404():
    conn = _make_conn(None, anchor=False)
    comp = AsyncMock()
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)), \
         patch("ai_orchestrator.workflow_runtime.compensation.run_compensation_chain",
               comp):
        with _client() as c:
            resp = c.post(
                f"/workflow-runs/{RUN_ID}/stop",
                json={},
                headers=HEADERS,
            )

    assert resp.status_code == 404, resp.text
    comp.assert_not_awaited()


# ─── 5. missing X-Enterprise-ID header -> 422 ────────────────────────


def test_stop_missing_enterprise_header_422():
    conn = _make_conn("running", anchor=True)
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)):
        with _client() as c:
            resp = c.post(
                f"/workflow-runs/{RUN_ID}/stop",
                json={},
                headers={"X-User-ID": USER_ID},
            )

    assert resp.status_code == 422, resp.text
