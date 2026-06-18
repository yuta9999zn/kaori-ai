"""
P15-S11 Tuần 8 — HTTP-surface tests for /corporate-tree + cross-workflow links.

Mocks acquire_for_tenant; no Postgres required. Pattern mirrors
test_workflow_builder_router.py.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE   = "11111111-1111-1111-1111-111111111111"
USER         = "22222222-2222-2222-2222-222222222222"
WORKSPACE    = "33333333-3333-3333-3333-333333333333"
GROUP_ID     = "44444444-4444-4444-4444-444444444444"
DIVISION_ID  = "55555555-5555-5555-5555-555555555555"
SUBSID_ID    = "66666666-6666-6666-6666-666666666666"
PARENT_ENT   = "77777777-7777-7777-7777-777777777777"
WORKFLOW_A   = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
WORKFLOW_B   = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    conn.execute.return_value = "INSERT 0 1"
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


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    return r


def _corp_row(**overrides) -> MagicMock:
    base = {
        "corporate_group_id": UUID(GROUP_ID),
        "workspace_id":       UUID(WORKSPACE),
        "name":               "Vingroup",
        "name_vi":             "Tập đoàn Vingroup",
        "description":        "Demo",
        "founded_year":       1993,
        "headquarters":       "Hà Nội",
        "website":            None,
        "status":             "active",
        "created_at":         datetime(2026, 5, 15, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return _row(**base)


def _div_row(**overrides) -> MagicMock:
    base = {
        "division_id":        UUID(DIVISION_ID),
        "corporate_group_id": UUID(GROUP_ID),
        "workspace_id":       UUID(WORKSPACE),
        "name":               "Real Estate",
        "name_vi":            "Bất động sản",
        "description":        None,
        "industry_hint":      "real_estate",
        "sort_order":         1,
        "status":             "active",
    }
    base.update(overrides)
    return _row(**base)


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    with patch("ai_orchestrator.routers.corporate_tree.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.corporate_tree as ct
        test_app = FastAPI()
        test_app.include_router(ct.router)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


# ─── Tree view ──────────────────────────────────────────────────────


class TestTreeList:

    def test_returns_404_when_enterprise_not_found(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get("/corporate-tree", headers=HEADERS)
        assert resp.status_code == 404

    def test_returns_flat_node_list(self, app_client, conn):
        conn.fetchrow.return_value = _row(workspace_id=UUID(WORKSPACE))
        conn.fetch.return_value = [
            _row(level=1, node_type='group', node_id=UUID(GROUP_ID),
                 parent_id=None, workspace_id=UUID(WORKSPACE),
                 name='Vingroup', display_name='Tập đoàn Vingroup',
                 status='active', sort_order=0),
            _row(level=2, node_type='division', node_id=UUID(DIVISION_ID),
                 parent_id=UUID(GROUP_ID), workspace_id=UUID(WORKSPACE),
                 name='Real Estate', display_name='Bất động sản',
                 status='active', sort_order=1),
        ]
        resp = app_client.get("/corporate-tree", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["node_type"] == "group"
        assert body[1]["node_type"] == "division"

    def test_nested_tree_links_children_to_parent(self, app_client, conn):
        conn.fetchrow.return_value = _row(workspace_id=UUID(WORKSPACE))
        conn.fetch.return_value = [
            _row(level=1, node_type='group', node_id=UUID(GROUP_ID),
                 parent_id=None, workspace_id=UUID(WORKSPACE),
                 name='Vingroup', display_name='Tập đoàn Vingroup',
                 status='active', sort_order=0),
            _row(level=2, node_type='division', node_id=UUID(DIVISION_ID),
                 parent_id=UUID(GROUP_ID), workspace_id=UUID(WORKSPACE),
                 name='Real Estate', display_name='Bất động sản',
                 status='active', sort_order=1),
        ]
        resp = app_client.get("/corporate-tree/nested", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert len(body["roots"]) == 1
        assert body["roots"][0]["node_id"] == GROUP_ID
        assert len(body["roots"][0]["children"]) == 1
        assert body["roots"][0]["children"][0]["node_id"] == DIVISION_ID


# ─── Corporate group CRUD ───────────────────────────────────────────


class TestCorporateGroupCRUD:

    def test_create_requires_workspace_match(self, app_client, conn):
        conn.fetchrow.return_value = None   # workspace guard fails
        resp = app_client.post(
            "/corporate-groups",
            headers=HEADERS,
            json={"workspace_id": WORKSPACE, "name": "Vingroup"},
        )
        assert resp.status_code == 403

    def test_create_happy_path(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(workspace=1),       # guard OK
            _corp_row(),              # INSERT RETURNING
        ]
        resp = app_client.post(
            "/corporate-groups",
            headers=HEADERS,
            json={"workspace_id": WORKSPACE, "name": "Vingroup",
                  "name_vi": "Tập đoàn Vingroup", "founded_year": 1993},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["name"] == "Vingroup"

    def test_get_returns_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(f"/corporate-groups/{GROUP_ID}", headers=HEADERS)
        assert resp.status_code == 404

    def test_update_status_to_archived(self, app_client, conn):
        conn.fetchrow.return_value = _corp_row(status="archived")
        resp = app_client.put(
            f"/corporate-groups/{GROUP_ID}",
            headers=HEADERS,
            json={"status": "archived"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_invalid_status_returns_422(self, app_client):
        resp = app_client.put(
            f"/corporate-groups/{GROUP_ID}",
            headers=HEADERS,
            json={"status": "deleted"},   # not in enum
        )
        assert resp.status_code == 422

    def test_archive_returns_204(self, app_client, conn):
        conn.execute.return_value = "UPDATE 1"
        resp = app_client.delete(f"/corporate-groups/{GROUP_ID}", headers=HEADERS)
        assert resp.status_code == 204


# ─── Business division CRUD ─────────────────────────────────────────


class TestBusinessDivisionCRUD:

    def test_create_resolves_workspace_from_group(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(workspace_id=UUID(WORKSPACE)),   # group lookup
            _div_row(),                            # INSERT RETURNING
        ]
        resp = app_client.post(
            "/business-divisions",
            headers=HEADERS,
            json={
                "corporate_group_id": GROUP_ID,
                "name": "Real Estate",
                "name_vi": "Bất động sản",
                "industry_hint": "real_estate",
                "sort_order": 1,
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["name"] == "Real Estate"

    def test_create_group_not_found_returns_404(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.post(
            "/business-divisions",
            headers=HEADERS,
            json={"corporate_group_id": GROUP_ID, "name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_blocks_when_active_enterprises(self, app_client, conn):
        conn.fetchval.return_value = 3   # 3 active enterprises under division
        resp = app_client.delete(
            f"/business-divisions/{DIVISION_ID}",
            headers=HEADERS,
        )
        assert resp.status_code == 409
        assert "active enterprises" in resp.json()["detail"]

    def test_delete_succeeds_when_empty(self, app_client, conn):
        conn.fetchval.return_value = 0
        conn.execute.return_value = "DELETE 1"
        resp = app_client.delete(
            f"/business-divisions/{DIVISION_ID}",
            headers=HEADERS,
        )
        assert resp.status_code == 204


# ─── Enterprise re-parent ───────────────────────────────────────────


class TestEnterpriseReparent:

    def test_requires_exactly_one_fk(self, app_client):
        """0 FKs → 400."""
        resp = app_client.put(
            f"/enterprises/{SUBSID_ID}/parent",
            headers=HEADERS,
            json={},
        )
        assert resp.status_code == 400
        assert "exactly one" in resp.json()["detail"]

    def test_rejects_multiple_fks(self, app_client):
        resp = app_client.put(
            f"/enterprises/{SUBSID_ID}/parent",
            headers=HEADERS,
            json={"corporate_group_id": GROUP_ID, "business_division_id": DIVISION_ID},
        )
        assert resp.status_code == 400

    def test_rejects_cross_workspace_parent(self, app_client, conn):
        other_ws = "99999999-9999-9999-9999-999999999999"
        conn.fetchrow.side_effect = [
            _row(workspace_id=UUID(WORKSPACE)),         # enterprise lookup
            _row(workspace_id=UUID(other_ws)),           # division lookup — different ws
        ]
        resp = app_client.put(
            f"/enterprises/{SUBSID_ID}/parent",
            headers=HEADERS,
            json={"business_division_id": DIVISION_ID},
        )
        assert resp.status_code == 400
        assert "different workspace" in resp.json()["detail"]

    def test_happy_path_moves_to_division(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(workspace_id=UUID(WORKSPACE)),  # enterprise lookup
            _row(workspace_id=UUID(WORKSPACE)),  # division lookup
        ]
        resp = app_client.put(
            f"/enterprises/{SUBSID_ID}/parent",
            headers=HEADERS,
            json={"business_division_id": DIVISION_ID},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    # ─── org-detail endpoint ────────────────────────────────────────

    def test_org_detail_rejects_cross_workspace(self, app_client, conn):
        other_ws = "99999999-9999-9999-9999-999999999999"
        conn.fetchrow.side_effect = [
            _row(workspace_id=UUID(WORKSPACE)),                         # caller
            _row(enterprise_id=UUID(SUBSID_ID), workspace_id=UUID(other_ws),
                 name='X', corporate_group_id=None, business_division_id=None,
                 parent_enterprise_id=None, industry=None, status='active'),
        ]
        resp = app_client.get(
            f"/enterprises/{SUBSID_ID}/org-detail",
            headers=HEADERS,
        )
        assert resp.status_code == 403

    def test_org_detail_happy_path_returns_branches_and_depts(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(workspace_id=UUID(WORKSPACE)),
            _row(enterprise_id=UUID(SUBSID_ID), workspace_id=UUID(WORKSPACE),
                 name='VinMart', corporate_group_id=UUID(GROUP_ID),
                 business_division_id=UUID(DIVISION_ID), parent_enterprise_id=None,
                 industry='retail', status='active'),
        ]
        conn.fetch.side_effect = [
            [_row(branch_id=UUID("99999999-1111-1111-1111-999999999999"),
                  name='Trụ sở chính', code='MAIN', is_default=True,
                  timezone='Asia/Ho_Chi_Minh', status='active')],
            [_row(department_id=UUID("99999999-2222-2222-2222-999999999999"),
                  branch_id=UUID("99999999-1111-1111-1111-999999999999"),
                  name='Sales', dept_type='sales', status='active',
                  pii_sensitivity='normal', description='Bán hàng')],
        ]
        resp = app_client.get(
            f"/enterprises/{SUBSID_ID}/org-detail",
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enterprise"]["name"] == "VinMart"
        assert len(body["branches"]) == 1
        assert body["branches"][0]["is_default"] is True
        assert len(body["departments"]) == 1
        assert body["departments"][0]["dept_type"] == "sales"

    def test_cycle_detection_on_parent_enterprise_id(self, app_client, conn):
        """Try to set enterprise A's parent to enterprise B, where B's
        parent chain already includes A."""
        conn.fetchrow.side_effect = [
            _row(workspace_id=UUID(WORKSPACE)),   # enterprise A lookup
            _row(workspace_id=UUID(WORKSPACE),    # target B
                 parent_enterprise_id=UUID(SUBSID_ID)),
        ]
        resp = app_client.put(
            f"/enterprises/{SUBSID_ID}/parent",
            headers=HEADERS,
            json={"parent_enterprise_id": PARENT_ENT},
        )
        assert resp.status_code == 400
        assert "cycle" in resp.json()["detail"]
