"""HTTP-surface tests for the EU AI Act K-26 incident register + monitoring
summary router (ADR-0041 Layer 3, slice 3).

Mocks acquire_for_tenant (no Postgres) + patches record_ai_call with an
AsyncMock. Pattern mirrors test_industry_bootstrap_router.py — fake conn that
dispatches by SQL fragment.

Coverage:
  1. POST /admin/incidents (ADMIN) → 201, severity/status echoed, INSERT issued,
     record_ai_call awaited once with task_kind="incident_recorded".
  2. POST severity 'catastrophic' (ADMIN) → 422.
  3. POST with VIEWER role → 403.
  4. GET /admin/incidents?status=open&severity=serious (ADMIN) → 200 + rows.
  5. PATCH /admin/incidents/{uuid} {status:resolved} (ADMIN) → 200, UPDATE issued.
  6. PATCH {status:closed} (ADMIN) → 422.
  7. GET /admin/incidents/summary (ADMIN) → 200 with the 5 summary keys.
  8. POST without X-Enterprise-ID → 422.
"""
from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "55555555-5555-5555-5555-555555555555"
INCIDENT_ID = "88888888-8888-8888-8888-888888888888"

ADMIN_HEADERS = {
    "X-Enterprise-ID": ENTERPRISE_ID,
    "X-User-Role": "ADMIN",
    "X-User-ID": USER_ID,
}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


_REPORTED_AT = datetime.datetime(2026, 6, 4, 9, 0, 0, tzinfo=datetime.timezone.utc)


def _incident_row(severity="serious", status="open", incident_type="wrong_decision"):
    return _row(
        incident_id=UUID(INCIDENT_ID),
        public_ref="01J0XREF000000000000000000",
        incident_type=incident_type,
        severity=severity,
        status=status,
        title="x",
        description=None,
        decision_id=None,
        run_id=None,
        workflow_id=None,
        reported_at=_REPORTED_AT,
        resolved_at=None,
    )


def _make_conn() -> AsyncMock:
    """Fake conn that dispatches by SQL fragment."""
    conn = AsyncMock()

    async def fetchrow(sql, *args, **kwargs):
        s = sql.upper()
        if "INSERT INTO AI_INCIDENT" in s:
            return _incident_row()
        if "UPDATE AI_INCIDENT" in s:
            # new_status is the 2nd positional param ($2)
            new_status = args[1] if len(args) > 1 else "resolved"
            return _incident_row(status=new_status)
        return None

    async def fetch(sql, *args, **kwargs):
        s = sql.upper()
        if "GROUP BY SEVERITY" in s:
            return [_row(severity="serious", n=2), _row(severity="high", n=1)]
        if "FROM AI_INCIDENT" in s:  # list endpoint
            return [_incident_row()]
        return []

    async def fetchval(sql, *args, **kwargs):
        s = sql.upper()
        if "FROM WORKFLOW_RUNS" in s:
            return 4
        if "FROM AI_DECISION_AUDIT" in s:
            return 7
        return 0

    conn.fetchrow.side_effect = fetchrow
    conn.fetch.side_effect = fetch
    conn.fetchval.side_effect = fetchval
    conn.execute.return_value = "OK"
    return conn


def _ctx(conn):
    @asynccontextmanager
    async def _fake(*_args, **_kwargs):
        yield conn
    return _fake


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def record_mock():
    return AsyncMock()


@pytest.fixture
def app_client(conn, record_mock):
    with patch("ai_orchestrator.routers.incidents.acquire_for_tenant", _ctx(conn)), \
         patch("ai_orchestrator.routers.incidents.record_ai_call", record_mock):
        import ai_orchestrator.routers.incidents as inc
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(inc.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


# ─── 1. create ───────────────────────────────────────────────────────


def test_create_incident_201(app_client, conn, record_mock):
    resp = app_client.post(
        "/admin/incidents",
        json={"incident_type": "wrong_decision", "severity": "serious", "title": "x"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["severity"] == "serious"
    assert body["status"] == "open"

    # INSERT into ai_incident was issued.
    insert_calls = [
        c for c in conn.fetchrow.await_args_list
        if "INSERT INTO ai_incident" in c.args[0]
    ]
    assert len(insert_calls) == 1

    # record_ai_call awaited once with task_kind="incident_recorded".
    record_mock.assert_awaited_once()
    assert record_mock.await_args.kwargs["task_kind"] == "incident_recorded"


# ─── 2. invalid severity ─────────────────────────────────────────────


def test_create_incident_invalid_severity_422(app_client):
    resp = app_client.post(
        "/admin/incidents",
        json={"incident_type": "wrong_decision", "severity": "catastrophic", "title": "x"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 422, resp.text


# ─── 3. authz ────────────────────────────────────────────────────────


def test_create_incident_viewer_403(app_client):
    headers = dict(ADMIN_HEADERS, **{"X-User-Role": "VIEWER"})
    resp = app_client.post(
        "/admin/incidents",
        json={"incident_type": "wrong_decision", "severity": "serious", "title": "x"},
        headers=headers,
    )
    assert resp.status_code == 403


# ─── 4. list ─────────────────────────────────────────────────────────


def test_list_incidents_200(app_client):
    resp = app_client.get(
        "/admin/incidents?status=open&severity=serious",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["severity"] == "serious"
    assert body[0]["status"] == "open"


# ─── 5. patch resolve ────────────────────────────────────────────────


def test_patch_incident_resolved_200(app_client, conn):
    resp = app_client.patch(
        f"/admin/incidents/{INCIDENT_ID}",
        json={"status": "resolved"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "resolved"

    update_calls = [
        c for c in conn.fetchrow.await_args_list
        if "UPDATE ai_incident" in c.args[0]
    ]
    assert len(update_calls) == 1


# ─── 6. patch invalid status ─────────────────────────────────────────


def test_patch_incident_invalid_status_422(app_client):
    resp = app_client.patch(
        f"/admin/incidents/{INCIDENT_ID}",
        json={"status": "closed"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 422, resp.text


# ─── 7. summary ──────────────────────────────────────────────────────


def test_summary_200(app_client):
    resp = app_client.get("/admin/incidents/summary", headers=ADMIN_HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in (
        "open_incidents_by_severity",
        "failed_runs_recent",
        "low_confidence_decisions_recent",
        "window_days",
        "low_confidence_threshold",
    ):
        assert key in body, f"missing summary key {key}"
    assert body["open_incidents_by_severity"]["serious"] == 2
    assert body["failed_runs_recent"] == 4
    assert body["low_confidence_decisions_recent"] == 7


# ─── 8. missing enterprise header ────────────────────────────────────


def test_create_incident_missing_enterprise_422(app_client):
    headers = {"X-User-Role": "ADMIN", "X-User-ID": USER_ID}
    resp = app_client.post(
        "/admin/incidents",
        json={"incident_type": "wrong_decision", "severity": "serious", "title": "x"},
        headers=headers,
    )
    assert resp.status_code == 422
