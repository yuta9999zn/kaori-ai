"""
P15-S11 Hướng A — HTTP-surface tests for PATCH /enterprise-users/{id}/role.

Mocks acquire_for_tenant; no Postgres required.

Coverage focus:
  1. Template path resolves dept → seniority → role + writes audit.
  2. Override path applies explicit role + writes a different event_type.
  3. Validator: 422 when neither template nor override fields present.
  4. Validator: 422 when BOTH template AND override sent.
  5. Validator: 422 when seniority_level / role out of vocab.
  6. Authz: non-MANAGER forbidden when X-User-Role header set.
  7. Cross-enterprise grant blocked with 403.
  8. 404 when user / department missing.
  9. No-op when previous == new still emits audit row.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE      = "11111111-1111-1111-1111-111111111111"
OTHER_ENT       = "22222222-2222-2222-2222-222222222222"
CALLER          = "33333333-3333-3333-3333-333333333333"
TARGET_USER     = "44444444-4444-4444-4444-444444444444"
DEPT_ID         = "55555555-5555-5555-5555-555555555555"
WORKSPACE       = "66666666-6666-6666-6666-666666666666"
TEMPLATE        = "77777777-7777-7777-7777-777777777777"
AUDIT_EVENT     = "88888888-8888-8888-8888-888888888888"

MANAGER_HEADERS = {
    "X-Enterprise-ID": ENTERPRISE,
    "X-User-ID":       CALLER,
    "X-User-Role":     "MANAGER",
}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "UPDATE 1"
    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)
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
    with patch("ai_orchestrator.routers.enterprise_users.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.enterprise_users as eu
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(eu.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


# ─── helpers to wire fetchrow side-effects per path ────────────────


def _target_user_row(role="VIEWER", enterprise=ENTERPRISE):
    return _row(
        user_id=UUID(TARGET_USER),
        email="newbie@kaori.local",
        role=role,
        enterprise_id=UUID(enterprise),
    )


def _dept_row(dept_type="finance", enterprise=ENTERPRISE):
    return _row(
        department_id=UUID(DEPT_ID),
        dept_type=dept_type,
        enterprise_id=UUID(enterprise),
    )


def _template_row(default_role="ANALYST"):
    return _row(template_id=UUID(TEMPLATE), default_role=default_role)


def _workspace_row():
    return _row(workspace_id=UUID(WORKSPACE))


def _audit_row():
    return _row(event_id=UUID(AUDIT_EVENT))


# ─── Template path ──────────────────────────────────────────────────


class TestTemplatePath:

    def test_resolves_and_applies(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _target_user_row(role="VIEWER"),
            _dept_row(dept_type="finance"),
            _template_row(default_role="ANALYST"),
            _workspace_row(),
            _audit_row(),
        ]
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={
                "department_id": DEPT_ID,
                "seniority_level": "junior",
                "reason": "Onboarding NV-002 — Sales Executive Vinhomes.",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_id"]        == TARGET_USER
        assert body["role"]           == "ANALYST"
        assert body["previous_role"]  == "VIEWER"
        assert body["source"]         == "template"
        assert body["template_id"]    == TEMPLATE
        assert body["audit_event_id"] == AUDIT_EVENT

    def test_no_template_for_combination_returns_404(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _target_user_row(),
            _dept_row(dept_type="marketing"),
            None,                     # template miss
        ]
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={
                "department_id": DEPT_ID,
                "seniority_level": "mid",
            },
        )
        assert resp.status_code == 404
        assert "marketing" in resp.json()["title"]
        assert "mid"       in resp.json()["title"]


# ─── Override path ──────────────────────────────────────────────────


class TestOverridePath:

    def test_applies_explicit_role(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _target_user_row(role="ANALYST"),
            _workspace_row(),
            _audit_row(),
        ]
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={
                "role": "MANAGER",
                "reason": "Tạm acting MANAGER trong 1 tuần.",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["role"]          == "MANAGER"
        assert body["previous_role"] == "ANALYST"
        assert body["source"]        == "override"
        assert body["template_id"]   is None


# ─── Body validator ─────────────────────────────────────────────────


class TestRequestValidator:

    def test_422_when_both_paths_supplied(self, app_client):
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={
                "department_id": DEPT_ID,
                "seniority_level": "mid",
                "role": "MANAGER",
            },
        )
        assert resp.status_code == 422

    def test_422_when_no_path_supplied(self, app_client):
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={"reason": "test"},
        )
        assert resp.status_code == 422

    def test_422_when_seniority_out_of_vocab(self, app_client):
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={"department_id": DEPT_ID, "seniority_level": "guru"},
        )
        assert resp.status_code == 422

    def test_422_when_role_out_of_vocab(self, app_client):
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={"role": "SUPERHERO"},
        )
        assert resp.status_code == 422


# ─── Authz / scope ──────────────────────────────────────────────────


class TestAuthz:

    def test_non_manager_role_forbidden(self, app_client):
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers={**MANAGER_HEADERS, "X-User-Role": "ANALYST"},
            json={"role": "MANAGER"},
        )
        assert resp.status_code == 403

    def test_cross_enterprise_grant_blocked(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _target_user_row(enterprise=OTHER_ENT),
        ]
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={"role": "MANAGER"},
        )
        assert resp.status_code == 403
        assert "different enterprise" in resp.json()["title"]

    def test_target_user_missing_returns_404(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={"role": "MANAGER"},
        )
        assert resp.status_code == 404


# ─── Edge — no-op same role ─────────────────────────────────────────


class TestNoOp:

    def test_assigning_same_role_still_emits_audit(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _target_user_row(role="MANAGER"),
            _workspace_row(),
            _audit_row(),
        ]
        resp = app_client.patch(
            f"/enterprise-users/{TARGET_USER}/role",
            headers=MANAGER_HEADERS,
            json={"role": "MANAGER", "reason": "Manager review confirms."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == body["previous_role"] == "MANAGER"
        # Audit row still emitted — manager intent ("I checked this") is
        # what the audit captures, not just role-change deltas.
        assert body["audit_event_id"] == AUDIT_EVENT
