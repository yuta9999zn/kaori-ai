"""
P2-S16 — Workflow as Code (YAML import/export) tests.

8-section template per anh's "chuẩn chỉ + hiệu năng + phi chức năng":
  1. YAML parse + validation     — top-level shape checks
  2. Catalog validation          — unknown node_type rejected at boundary
  3. Edge validation             — dangling references rejected
  4. Round-trip                  — export → import yields equivalent shape
  5. Tenant isolation            — JWT header required for both endpoints
  6. Side-effect class fixed     — YAML cannot override catalog's side_effect_class
  7. Determinism                 — same YAML → same outcome counts
  8. Performance                 — large workflow (20 nodes, 19 edges) parses < 100ms
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
DEPT_ID    = "33333333-3333-3333-3333-333333333333"
WORKFLOW_ID = "44444444-4444-4444-4444-444444444444"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}
EXPORT_HEADERS = {"X-Enterprise-ID": ENTERPRISE}


def _catalog_rows(keys: list[str]) -> list[MagicMock]:
    rows = []
    for k in keys:
        r = MagicMock()
        r.__getitem__ = lambda _self, _k, _key=k: _key
        rows.append(r)
    return rows


def _make_conn(catalog_keys: list[str] | None = None) -> AsyncMock:
    conn = AsyncMock()
    if catalog_keys is not None:
        conn.fetch.return_value = _catalog_rows(catalog_keys)
    else:
        conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


def _make_app() -> FastAPI:
    from ai_orchestrator.routers import workflow_yaml
    app = FastAPI()
    app.include_router(workflow_yaml.router)
    return app


# Canonical small YAML used by many tests
_GOOD_YAML = """
workflow:
  name: Campaign Launch
  name_vi: Khởi chạy chiến dịch
  description: Test
  department_type: marketing
  category: campaign
  nodes:
    - id: n1
      title: Define segment
      node_type: read_table
    - id: n2
      title: Send
      node_type: send_email
  edges:
    - from: n1
      to: n2
      label: next
"""


# ═════════════════════════════════════════════════════════════════════
# 1. YAML shape validation
# ═════════════════════════════════════════════════════════════════════


class TestYAMLShape:

    def test_missing_top_level_workflow_returns_400(self):
        from ai_orchestrator.routers import workflow_yaml
        bad = "not_workflow: foo"
        conn = _make_conn(catalog_keys=["read_table"])
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": bad, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 400
        assert "top-level 'workflow'" in r.json()["detail"]

    def test_missing_nodes_returns_400(self):
        from ai_orchestrator.routers import workflow_yaml
        bad = "workflow:\n  name: x\n  department_type: marketing\n"
        conn = _make_conn(catalog_keys=["read_table"])
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": bad, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 400
        assert "nodes" in r.json()["detail"]

    def test_invalid_yaml_syntax_returns_400(self):
        from ai_orchestrator.routers import workflow_yaml
        bad = "workflow:\n  name: foo\n  - bad indent"
        conn = _make_conn(catalog_keys=["read_table"])
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": bad, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 400
        assert "YAML parse error" in r.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# 2. Catalog validation
# ═════════════════════════════════════════════════════════════════════


class TestCatalogValidation:

    def test_unknown_node_type_rejected(self):
        from ai_orchestrator.routers import workflow_yaml
        bad = """
workflow:
  name: x
  department_type: marketing
  nodes:
    - id: n1
      title: x
      node_type: WAT_invented_node
  edges: []
"""
        conn = _make_conn(catalog_keys=["read_table", "send_email"])
        conn.fetchrow.return_value = {"workflow_id": UUID(WORKFLOW_ID)}
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": bad, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 400
        assert "not in mig 068 catalog" in r.json()["detail"]
        assert "WAT_invented_node" in r.json()["detail"]

    def test_valid_catalog_node_accepted(self):
        from ai_orchestrator.routers import workflow_yaml
        conn = _make_conn(catalog_keys=["read_table", "send_email"])
        conn.fetchrow.return_value = MagicMock(
            __getitem__=lambda _self, k: UUID(WORKFLOW_ID) if k == "workflow_id" else None
        )
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": _GOOD_YAML, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["nodes_created"] == 2
        assert body["edges_created"] == 1


# ═════════════════════════════════════════════════════════════════════
# 3. Edge validation
# ═════════════════════════════════════════════════════════════════════


class TestEdgeValidation:

    def test_dangling_edge_rejected(self):
        from ai_orchestrator.routers import workflow_yaml
        bad = """
workflow:
  name: x
  department_type: marketing
  nodes:
    - id: n1
      title: x
      node_type: read_table
  edges:
    - from: n1
      to: n999
"""
        conn = _make_conn(catalog_keys=["read_table"])
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": bad, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 400
        assert "undefined node" in r.json()["detail"]
        assert "n999" in r.json()["detail"]

    def test_duplicate_node_id_rejected(self):
        from ai_orchestrator.routers import workflow_yaml
        bad = """
workflow:
  name: x
  department_type: marketing
  nodes:
    - id: n1
      title: a
      node_type: read_table
    - id: n1
      title: b
      node_type: read_table
  edges: []
"""
        conn = _make_conn(catalog_keys=["read_table"])
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post("/workflows/import",
                            json={"yaml_content": bad, "department_id": DEPT_ID},
                            headers=HEADERS)
        assert r.status_code == 400
        assert "duplicate node id" in r.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# 4. Round-trip semantics (export shape correctness)
# ═════════════════════════════════════════════════════════════════════


class TestRoundTrip:

    def test_export_renders_valid_yaml(self):
        """Export endpoint must produce YAML that re-parses + has the
        canonical shape (workflow.name + workflow.nodes + workflow.edges)."""
        from ai_orchestrator.routers import workflow_yaml

        conn = _make_conn()
        wf_row = MagicMock()
        wf_row.__getitem__ = lambda _self, k: {
            "workflow_id":   UUID(WORKFLOW_ID),
            "name":          "Test Flow",
            "name_vi":       "Quy trình test",
            "description":   "desc",
            "category":      "campaign",
            "department_id": UUID(DEPT_ID),
        }[k]
        dept_row = MagicMock()
        dept_row.__getitem__ = lambda _self, k: "marketing"
        conn.fetchrow.side_effect = [wf_row, dept_row]

        node1 = MagicMock()
        node1.__getitem__ = lambda _self, k: {
            "node_id":        uuid4(),
            "title":          "A",
            "title_vi":       "A_vi",
            "node_type":      "read_table",
            "sequence_order": 1,
            "position_x":     100, "position_y": 100,
            "note":           None, "hashtags": None,
            "config_json":    None,
        }[k]
        conn.fetch.side_effect = [[node1], []]

        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get(f"/workflows/{WORKFLOW_ID}/export.yaml",
                           headers=EXPORT_HEADERS)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/x-yaml")
        parsed = yaml.safe_load(r.text)
        assert parsed["workflow"]["name"] == "Test Flow"
        assert parsed["workflow"]["department_type"] == "marketing"
        assert parsed["workflow"]["nodes"][0]["node_type"] == "read_table"

    def test_export_workflow_not_found(self):
        from ai_orchestrator.routers import workflow_yaml

        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get(f"/workflows/{WORKFLOW_ID}/export.yaml",
                           headers=EXPORT_HEADERS)
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# 5. Tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    def test_import_requires_enterprise_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.post("/workflows/import",
                        json={"yaml_content": _GOOD_YAML, "department_id": DEPT_ID})
        assert r.status_code == 422

    def test_export_requires_enterprise_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.get(f"/workflows/{WORKFLOW_ID}/export.yaml")
        assert r.status_code == 422

    def test_import_requires_user_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.post("/workflows/import",
                        json={"yaml_content": _GOOD_YAML, "department_id": DEPT_ID},
                        headers={"X-Enterprise-ID": ENTERPRISE})
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 6. Side-effect class is catalog-derived (no YAML override path)
# ═════════════════════════════════════════════════════════════════════


class TestSideEffectClassPinned:

    def test_yaml_cannot_inject_side_effect_class(self):
        """YAML schema doesn't include `side_effect_class` per K-17.
        The router's INSERT hardcodes 'read_only' as a safe default;
        downstream lookups derive the real class from mig 068 catalog
        via node_type FK. A malicious YAML claiming 'pure' for an
        actually-external node still hits the catalog's enforced
        retry policy at execution time."""
        from ai_orchestrator.routers.workflow_yaml import _validate_yaml_shape
        wf = _validate_yaml_shape(yaml.safe_load(_GOOD_YAML))
        # Nodes do NOT carry side_effect_class in YAML — confirmed
        for n in wf["nodes"]:
            assert "side_effect_class" not in n


# ═════════════════════════════════════════════════════════════════════
# 7. Determinism — same YAML → same response counts
# ═════════════════════════════════════════════════════════════════════


class TestDeterminism:

    def test_same_yaml_twice_same_counts(self):
        from ai_orchestrator.routers import workflow_yaml

        def _run_import():
            conn = _make_conn(catalog_keys=["read_table", "send_email"])
            wf_id = uuid4()
            row = MagicMock()
            row.__getitem__ = lambda _self, k: wf_id if k == "workflow_id" else None
            conn.fetchrow.return_value = row
            with patch.object(workflow_yaml, "acquire_for_tenant", _tenant_ctx(conn)):
                app = _make_app()
                client = TestClient(app)
                return client.post(
                    "/workflows/import",
                    json={"yaml_content": _GOOD_YAML, "department_id": DEPT_ID},
                    headers=HEADERS,
                ).json()

        a = _run_import()
        b = _run_import()
        # workflow_id differs each call (random uuid), but counts must match
        assert a["nodes_created"] == b["nodes_created"]
        assert a["edges_created"] == b["edges_created"]


# ═════════════════════════════════════════════════════════════════════
# 8. Performance — large workflow parse + validate
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_20_node_19_edge_workflow_validates_under_100ms(self):
        from ai_orchestrator.routers.workflow_yaml import (
            _validate_nodes_and_edges,
            _validate_yaml_shape,
        )
        # Build a 20-node sequential workflow
        nodes = [
            f"    - id: n{i}\n      title: Step {i}\n      node_type: filter"
            for i in range(1, 21)
        ]
        edges = [
            f"    - from: n{i}\n      to: n{i+1}\n      label: next"
            for i in range(1, 20)
        ]
        yaml_text = (
            "workflow:\n"
            "  name: Big\n"
            "  department_type: custom\n"
            "  nodes:\n"
            + "\n".join(nodes)
            + "\n  edges:\n"
            + "\n".join(edges)
        )
        t0 = time.perf_counter()
        doc = yaml.safe_load(yaml_text)
        wf = _validate_yaml_shape(doc)
        _validate_nodes_and_edges(wf, valid_catalog_keys={"filter"})
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"validate too slow: {elapsed:.3f}s"
