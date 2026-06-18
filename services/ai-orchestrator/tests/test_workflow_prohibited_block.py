"""
Task 6 — block publish/run of an EU AI Act *prohibited*-tier workflow
(ADR-0041, K-22).

Two guard points in routers/workflow_builder.py:
  • update_workflow (PUT /workflows/{id})  — when transitioning to a runtime
    state, the prohibited-use check runs FIRST (before dangling-branch / gate).
  • start_workflow_run (POST /workflows/{id}/run) — the check runs right after
    the tenant connection opens, before any run side-effect.

On a prohibited classification both return 403 RFC 7807 with
`code == "COMPLIANCE.PROHIBITED_USE"` returned directly (not via
HTTPException) so the COMPLIANCE.* code survives shared/errors.py.

Pattern mirrors test_compliance_risk_router.py: fake conn + TestClient +
monkeypatch of acquire_for_tenant. The fake conn dispatches fetchrow on the
SQL text — anything touching `ai_use_risk_register` returns the canned
classification row; everything else returns the rows the other code paths
need.
"""
from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "55555555-5555-5555-5555-555555555555"
WORKFLOW_ID = "66666666-6666-6666-6666-666666666666"
WORKSPACE_ID = "77777777-7777-7777-7777-777777777777"
RUN_ID = "99999999-9999-9999-9999-999999999999"

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


def _make_conn(risk_tier: str | None) -> AsyncMock:
    """Fake tenant connection.

    fetchrow dispatches on SQL text:
      • ai_use_risk_register  -> canned classification row (or None)
      • UPDATE workflows / SELECT ... w.workflow_id -> a workflow row
      • SELECT workflow_id, workspace_id (run pre-flight) -> workflow row
    fetch (used by dangling-branch + approval-gate + node lookups) -> [].
    """
    conn = AsyncMock()

    risk_row = _row(risk_tier=risk_tier) if risk_tier is not None else None

    wf_row = _row(
        workflow_id=UUID(WORKFLOW_ID),
        workspace_id=UUID(WORKSPACE_ID),
        enterprise_id=UUID(ENTERPRISE_ID),
        department_id=UUID("44444444-4444-4444-4444-444444444444"),
        department_name=None,
        dept_type=None,
        branch_id=None,
        name="wf",
        name_vi=None,
        description=None,
        category=None,
        state="DRAFT",
        version=1,
        source="builder",
        created_at=datetime.datetime(2026, 6, 3),
        last_modified_at=datetime.datetime(2026, 6, 3),
    )

    async def _fetchrow(sql, *args, **kwargs):
        s = sql if isinstance(sql, str) else str(sql)
        if "ai_use_risk_register" in s:
            return risk_row
        return wf_row

    conn.fetchrow.side_effect = _fetchrow
    conn.fetch.return_value = []
    conn.fetchval.return_value = 0
    conn.execute.return_value = "OK"
    return conn


def _client(conn) -> TestClient:
    import ai_orchestrator.routers.workflow_builder as wb
    from ai_orchestrator.shared.errors import register_problem_handlers
    test_app = FastAPI()
    test_app.include_router(wb.router)
    register_problem_handlers(test_app)
    return TestClient(test_app, raise_server_exceptions=True)


# ─── PUT (publish) ───────────────────────────────────────────────────


def test_put_runtime_state_prohibited_blocks_and_skips_update():
    conn = _make_conn(risk_tier="prohibited")
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)):
        with _client(conn) as c:
            resp = c.put(
                f"/workflows/{WORKFLOW_ID}",
                json={"state": "ACTIVE_BASELINE"},
                headers=HEADERS,
            )

    assert resp.status_code == 403, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["code"] == "COMPLIANCE.PROHIBITED_USE"

    # The prohibited guard must short-circuit BEFORE the UPDATE fetchrow.
    update_calls = [
        call for call in conn.fetchrow.await_args_list
        if "UPDATE workflows" in str(call.args[0])
    ]
    assert update_calls == [], "UPDATE must not run when prohibited"


def test_put_runtime_state_high_tier_does_not_prohibited_block():
    conn = _make_conn(risk_tier="high")
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)):
        with _client(conn) as c:
            resp = c.put(
                f"/workflows/{WORKFLOW_ID}",
                json={"state": "ACTIVE_BASELINE"},
                headers=HEADERS,
            )

    # It proceeds past the prohibited guard. It may 200 (no dangling/gate
    # issues with empty fetch) — just assert it's NOT the prohibited 403.
    if resp.status_code == 403:
        assert resp.json().get("code") != "COMPLIANCE.PROHIBITED_USE", resp.text


# ─── POST run ────────────────────────────────────────────────────────


def test_run_prohibited_blocks():
    conn = _make_conn(risk_tier="prohibited")
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _ctx(conn)):
        with _client(conn) as c:
            resp = c.post(
                f"/workflows/{WORKFLOW_ID}/run",
                json={"trigger_source": "manual", "input_data": {}},
                headers=HEADERS,
            )

    assert resp.status_code == 403, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["code"] == "COMPLIANCE.PROHIBITED_USE"
