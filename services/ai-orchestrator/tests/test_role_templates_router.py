"""
P15-S11 Hướng A — HTTP-surface tests for /role-templates +
/departments/{id}/role-template.

Mocks acquire_for_tenant; no Postgres required. Pattern mirrors
test_corporate_tree_router.py.

Coverage focus:
  1. /role-templates with default flags returns rows.
  2. dept_type filter pushes through to the SQL parameter.
  3. /departments/{id}/role-template returns 404 when dept is missing.
  4. Resolver picks the enterprise override row when one exists.
  5. Resolver returns 422 when seniority_level is out of vocab.
  6. Resolver returns 404 with a clear hint when no template matches.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
DEPT_ID    = "33333333-3333-3333-3333-333333333333"
TEMPLATE_G = "44444444-4444-4444-4444-444444444444"
TEMPLATE_O = "55555555-5555-5555-5555-555555555555"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    # Make dict(row) work — asyncpg.Record supports keys() iteration which
    # dict(...) uses. Mirror that here so the router's `dict(r)` calls
    # round-trip without surprises.
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_eid):
        yield conn
    return _fake


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    with patch("ai_orchestrator.routers.role_templates.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.role_templates as rt
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(rt.router)
        # Production parity — register the RFC 7807 problem handler so
        # 4xx responses match what the gateway forwards to FE.
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


def _global_row(**overrides):
    """Default global-tier template row (enterprise_id NULL)."""
    base = {
        "template_id":     UUID(TEMPLATE_G),
        "enterprise_id":   None,
        "dept_type":       "marketing",
        "seniority_level": "executive",
        "default_role":    "MANAGER",
        "overridable":     True,
        "description_vi":  "Trưởng phòng marketing.",
        "is_active":       True,
        "is_override":     False,
    }
    base.update(overrides)
    return _row(**base)


def _override_row(**overrides):
    """Enterprise-specific override."""
    base = {
        "template_id":     UUID(TEMPLATE_O),
        "enterprise_id":   UUID(ENTERPRISE),
        "dept_type":       "finance",
        "seniority_level": "entry",
        "default_role":    "ANALYST",
        "overridable":     True,
        "description_vi":  "Override — A/R clerks ở enterprise này được ANALYST.",
        "is_active":       True,
        "is_override":     True,
    }
    base.update(overrides)
    return _row(**base)


# ─── /role-templates listing ────────────────────────────────────────


class TestListRoleTemplates:

    def test_returns_rows_with_overrides_merged(self, app_client, conn):
        conn.fetch.return_value = [_global_row(), _override_row()]
        resp = app_client.get("/role-templates", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["is_override"] is False
        assert body[1]["is_override"] is True
        # Override row carries the enterprise_id.
        assert body[1]["enterprise_id"] == ENTERPRISE

    def test_dept_type_filter_passes_to_sql(self, app_client, conn):
        conn.fetch.return_value = [_global_row(dept_type="hr",
                                              seniority_level="senior",
                                              default_role="MANAGER")]
        resp = app_client.get("/role-templates?dept_type=hr", headers=HEADERS)
        assert resp.status_code == 200
        # Confirm the dept_type was forwarded into the SQL params (last
        # positional arg of the include-overrides branch).
        args = conn.fetch.call_args.args
        assert "hr" in args

    def test_include_overrides_false_drops_enterprise_param(self, app_client, conn):
        conn.fetch.return_value = [_global_row()]
        resp = app_client.get(
            "/role-templates?include_overrides=false",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        # The no-override branch should NOT pass enterprise_id as a
        # positional arg (only the dept_type filter goes through).
        args = conn.fetch.call_args.args
        assert UUID(ENTERPRISE) not in args


# ─── /departments/{id}/role-template resolver ───────────────────────


class TestResolveRoleTemplate:

    def test_404_when_department_missing(self, app_client, conn):
        conn.fetchrow.side_effect = [None]   # dept lookup fails
        resp = app_client.get(
            f"/departments/{DEPT_ID}/role-template?seniority_level=executive",
            headers=HEADERS,
        )
        assert resp.status_code == 404
        assert "department not found" in resp.json()["title"].lower()

    def test_422_when_seniority_out_of_vocab(self, app_client, conn):
        resp = app_client.get(
            f"/departments/{DEPT_ID}/role-template?seniority_level=guru",
            headers=HEADERS,
        )
        assert resp.status_code == 422
        assert "seniority_level" in resp.json()["title"]

    def test_resolves_global_default(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(department_id=UUID(DEPT_ID), dept_type="marketing"),
            _global_row(),
        ]
        resp = app_client.get(
            f"/departments/{DEPT_ID}/role-template?seniority_level=executive",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["department_id"] == DEPT_ID
        assert body["dept_type"]       == "marketing"
        assert body["seniority_level"] == "executive"
        assert body["template"]["default_role"] == "MANAGER"
        assert body["template"]["is_override"]  is False
        assert body["template"]["enterprise_id"] is None

    def test_picks_enterprise_override_over_global(self, app_client, conn):
        # Real query uses ORDER BY enterprise_id NULLS LAST + LIMIT 1, so
        # asserting the router returns whatever fetchrow gives back is
        # sufficient — we verify the override case end-to-end.
        conn.fetchrow.side_effect = [
            _row(department_id=UUID(DEPT_ID), dept_type="finance"),
            _override_row(),
        ]
        resp = app_client.get(
            f"/departments/{DEPT_ID}/role-template?seniority_level=entry",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["template"]["default_role"]   == "ANALYST"
        assert body["template"]["is_override"]    is True
        assert body["template"]["enterprise_id"]  == ENTERPRISE

    def test_404_when_no_template_matches(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(department_id=UUID(DEPT_ID), dept_type="marketing"),
            None,                              # template lookup misses
        ]
        resp = app_client.get(
            f"/departments/{DEPT_ID}/role-template?seniority_level=mid",
            headers=HEADERS,
        )
        assert resp.status_code == 404
        # Helpful hint should mention both dept_type and seniority.
        title = resp.json()["title"]
        assert "marketing" in title and "mid" in title
