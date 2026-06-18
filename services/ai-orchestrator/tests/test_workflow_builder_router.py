"""
P15-S11 Tuần 8 Step 5 — HTTP-surface tests for /workflows CRUD + tree.

Pure TestClient — mocks `acquire_for_tenant` so router SQL hits the
in-memory mock conn. No Postgres needed. Pattern mirrors
test_economics_router.py.

Coverage:
  - list / create / get / update / delete workflow
  - create node (card) + update + delete
  - create edge + reject self-loop + delete
  - tree endpoint joins nodes + documents
  - clone-from-template clones + rewrites client_id → real UUIDs
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE   = "11111111-1111-1111-1111-111111111111"
USER         = "22222222-2222-2222-2222-222222222222"
DEPT_ID      = "33333333-3333-3333-3333-333333333333"
BRANCH_ID    = "44444444-4444-4444-4444-444444444444"
WORKFLOW_ID  = "55555555-5555-5555-5555-555555555555"
NODE_ID      = "66666666-6666-6666-6666-666666666666"
NODE_ID_2    = "77777777-7777-7777-7777-777777777777"
EDGE_ID      = "88888888-8888-8888-8888-888888888888"
TEMPLATE_ID  = "99999999-9999-9999-9999-999999999999"
FILE_ID      = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
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


_DEFAULT_WS = UUID("99999999-aaaa-aaaa-aaaa-999999999999")


def _dept_row(*, enterprise_id=None, workspace_id=None, caller_workspace_id=None):
    """Mock row for the dept guard query in workflow_builder.

    After mig 059 + the workspace-aware dept lookup helper
    `_resolve_dept_workspace_match`, the dept guard query returns
    (enterprise_id, workspace_id, caller_workspace_id). All three must
    be present or the helper raises KeyError on row access.

    Defaults pick the same workspace_id for both enterprise + caller
    so the same-workspace check passes.
    """
    ws_id = workspace_id or _DEFAULT_WS
    return _row(
        enterprise_id=enterprise_id or UUID(ENTERPRISE),
        workspace_id=ws_id,
        caller_workspace_id=caller_workspace_id or ws_id,
    )


def _ws_aware_lookup_row(
    *,
    department_id=None,
    enterprise_id=None,
    workspace_id=None,
    extra=None,
):
    """Mock row for workflow / node lookup queries that read enterprise_id +
    workspace_id + department_id after the mig 059 workspace_id ALTER.

    Use this anywhere `_row(department_id=UUID(DEPT_ID))` was used pre-059.
    """
    base = dict(
        department_id=department_id or UUID(DEPT_ID),
        enterprise_id=enterprise_id or UUID(ENTERPRISE),
        workspace_id=workspace_id or _DEFAULT_WS,
    )
    if extra:
        base.update(extra)
    return _row(**base)


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    return r


def _wf_row(**overrides) -> MagicMock:
    base = {
        "workflow_id":      UUID(WORKFLOW_ID),
        "enterprise_id":    UUID(ENTERPRISE),
        "department_id":    UUID(DEPT_ID),
        "branch_id":        UUID(BRANCH_ID),
        "name":             "Lead Qualification",
        "name_vi":          "Thẩm định lead",
        "description":      "5-step pipeline",
        "category":         "pipeline",
        "state":            "DRAFT",
        "version":          1,
        "source":           "user_built",
        "created_at":       datetime(2026, 5, 15, tzinfo=timezone.utc),
        "last_modified_at": datetime(2026, 5, 15, tzinfo=timezone.utc),
        # K-22 prohibited-use guard reads risk_tier off the first fetchrow
        # in a runtime-state transition; a non-prohibited value lets the
        # transition proceed (ADR-0041).
        "risk_tier":        "high",
    }
    base.update(overrides)
    return _row(**base)


def _node_row(**overrides) -> MagicMock:
    base = {
        "node_id":              UUID(NODE_ID),
        "workflow_id":          UUID(WORKFLOW_ID),
        "title":                "Lead intake",
        "title_vi":             "Tiếp nhận lead",
        "note":                 "Nhận lead từ Zalo",
        "hashtags":             ["prospect_data"],
        "required_document_types": [{"kind": "csv", "name": "Lead list", "required": True}],
        "expected_mapping_template_id": None,
        "node_type":            "step",
        "category":             "data_input",
        "side_effect_class":    "read_only",
        "position_x":           100.0,
        "position_y":           100.0,
        "sequence_order":       1,
    }
    base.update(overrides)
    return _row(**base)


def _edge_row(**overrides) -> MagicMock:
    base = {
        "edge_id":         UUID(EDGE_ID),
        "workflow_id":     UUID(WORKFLOW_ID),
        "source_node_id":  UUID(NODE_ID),
        "target_node_id":  UUID(NODE_ID_2),
        "condition":       None,
        "label":           "next",
    }
    base.update(overrides)
    return _row(**base)


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.workflow_builder as wb
        test_app = FastAPI(title="Kaori workflow builder test")
        test_app.include_router(wb.router)
        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


# ─── List ────────────────────────────────────────────────────────────


class TestListWorkflows:

    def test_returns_empty_list_when_none(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get("/workflows", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_rows_serialised(self, app_client, conn):
        conn.fetch.return_value = [_wf_row()]
        resp = app_client.get("/workflows", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["workflow_id"] == WORKFLOW_ID
        assert body[0]["name"]        == "Lead Qualification"

    def test_filter_by_department_id(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            f"/workflows?department_id={DEPT_ID}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        # SQL should include department_id filter
        sql_arg = conn.fetch.await_args.args[0]
        assert "department_id" in sql_arg

    def test_filter_by_state_invalid_returns_422(self, app_client):
        resp = app_client.get("/workflows?state=BOGUS", headers=HEADERS)
        assert resp.status_code == 422


# ─── Create / Get / Update / Delete ─────────────────────────────────


class TestCreateWorkflow:

    def test_happy_path_creates_workflow(self, app_client, conn):
        # 1st fetchrow = dept guard, 2nd = INSERT RETURNING workflow_id,
        # 3rd = re-fetch with JOIN departments (department_name/dept_type).
        conn.fetchrow.side_effect = [
            _dept_row(),                                       # dept guard
            _row(workflow_id=UUID(WORKFLOW_ID)),               # INSERT RETURNING workflow_id
            _wf_row(department_name="JM", dept_type="sales"),  # re-fetch (JOIN)
        ]
        resp = app_client.post(
            "/workflows",
            headers=HEADERS,
            json={"name": "Lead Qualification", "department_id": DEPT_ID},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["state"] == "DRAFT"
        # Response must carry the REAL department name (no hardcoded label).
        assert resp.json()["department_name"] == "JM"
        assert resp.json()["dept_type"] == "sales"

    def test_dept_not_in_enterprise_returns_404(self, app_client, conn):
        """After mig 059 + _resolve_dept_workspace_match, missing dept
        is a 404 (resource not found) — not 400. The semantic is more
        accurate: dept doesn't exist anywhere, not "in wrong tenant"."""
        conn.fetchrow.side_effect = [None]   # dept guard fails
        resp = app_client.post(
            "/workflows",
            headers=HEADERS,
            json={"name": "Test", "department_id": DEPT_ID},
        )
        assert resp.status_code == 404
        assert "department_id not found" in resp.json()["detail"]
        assert "department_id" in resp.json()["detail"]

    def test_missing_name_returns_422(self, app_client):
        resp = app_client.post(
            "/workflows",
            headers=HEADERS,
            json={"department_id": DEPT_ID},
        )
        assert resp.status_code == 422


class TestGetWorkflow:

    def test_returns_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}", headers=HEADERS)
        assert resp.status_code == 404

    def test_returns_workflow_when_found(self, app_client, conn):
        conn.fetchrow.return_value = _wf_row()
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["workflow_id"] == WORKFLOW_ID


class TestUpdateWorkflow:

    def test_state_transition_persists(self, app_client, conn):
        conn.fetchrow.return_value = _wf_row(state="ACTIVE_BASELINE")
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"state": "ACTIVE_BASELINE"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "ACTIVE_BASELINE"

    def test_invalid_state_returns_422(self, app_client):
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"state": "BOGUS"},
        )
        assert resp.status_code == 422

    # Gap 5 — dangling-branch validation on transition to runtime states
    # ------------------------------------------------------------------

    def test_activate_with_dangling_if_else_returns_400(self, app_client, conn):
        # decision_if_else with only 1 outgoing edge → IF_TRUE arm wired,
        # ELSE_FALSE arm dangling. Validator should refuse the transition.
        # The endpoint returns an RFC 7807 envelope directly so custom
        # fields (code, issues[]) survive the global problem handler.
        conn.fetch.return_value = [
            _row(
                node_id=UUID(NODE_ID),
                node_type="decision_if_else",
                title="Decide quality",
                title_vi="Quyết định chất lượng",
                decision_config=None,
                outgoing_count=1,
            ),
        ]
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"state": "ACTIVE_BASELINE"},
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["code"]   == "WORKFLOW.DANGLING_BRANCH"
        assert body["status"] == 400
        assert body["issues"][0]["node_id"]        == NODE_ID
        assert body["issues"][0]["node_type"]      == "decision_if_else"
        assert body["issues"][0]["expected_edges"] == 2
        assert body["issues"][0]["actual_edges"]   == 1
        # UPDATE must NOT be executed when validation fails so the workflow
        # stays in its previous state. (The K-22 prohibited-use guard issues a
        # read-only SELECT first, so fetchrow may be awaited once — assert the
        # UPDATE specifically never ran rather than fetchrow-never-awaited.)
        update_calls = [
            c for c in conn.fetchrow.await_args_list
            if "UPDATE workflows" in str(c.args[0])
        ]
        assert update_calls == []

    def test_activate_with_dangling_switch_returns_400(self, app_client, conn):
        # decision_switch with 3 cases but only 2 outgoing edges (missing
        # default + 1 case wiring). Validator reports expected=4, actual=2.
        conn.fetch.return_value = [
            _row(
                node_id=UUID(NODE_ID),
                node_type="decision_switch",
                title="Route by tier",
                title_vi="Định tuyến theo hạng",
                decision_config='{"cases": [{"value": "bronze"}, '
                                '{"value": "silver"}, {"value": "gold"}]}',
                outgoing_count=2,
            ),
        ]
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"state": "TESTING"},
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["code"] == "WORKFLOW.DANGLING_BRANCH"
        assert body["issues"][0]["expected_edges"] == 4
        assert body["issues"][0]["actual_edges"]   == 2

    def test_activate_with_healthy_decisions_passes(self, app_client, conn):
        # decision_if_else with both branches wired → no dangling issue, and
        # no approval_gate in the workflow. Activation runs two fetches in
        # order: _check_dangling_branches then _check_approval_gates (gap 5,
        # ADR-0037). side_effect feeds the decision row to the first and an
        # empty gate set to the second so neither validator blocks.
        conn.fetch.side_effect = [
            [
                _row(
                    node_id=UUID(NODE_ID),
                    node_type="decision_if_else",
                    title="Decide quality",
                    title_vi=None,
                    decision_config=None,
                    outgoing_count=2,
                ),
            ],
            [],  # _check_approval_gates → no gates
        ]
        conn.fetchrow.return_value = _wf_row(state="ACTIVE_BASELINE")
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"state": "ACTIVE_BASELINE"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "ACTIVE_BASELINE"

    def test_draft_state_skips_validation(self, app_client, conn):
        # Editing name on a draft must not trigger the dangling-branch
        # query — validator only fires on TESTING / ACTIVE_BASELINE.
        conn.fetchrow.return_value = _wf_row(state="DRAFT", name="Renamed")
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"name": "Renamed"},
        )
        assert resp.status_code == 200
        conn.fetch.assert_not_awaited()


class TestDeleteWorkflow:

    def test_delete_returns_204_when_present(self, app_client, conn):
        conn.execute.return_value = "DELETE 1"
        resp = app_client.delete(f"/workflows/{WORKFLOW_ID}", headers=HEADERS)
        assert resp.status_code == 204

    def test_delete_returns_404_when_missing(self, app_client, conn):
        conn.execute.return_value = "DELETE 0"
        resp = app_client.delete(f"/workflows/{WORKFLOW_ID}", headers=HEADERS)
        assert resp.status_code == 404


# ─── Nodes (cards) ──────────────────────────────────────────────────


class TestCreateNode:

    def test_creates_node_with_card_fields(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _ws_aware_lookup_row(),  # workflow lookup (ws-aware after mig 059)
            _node_row(),              # INSERT RETURNING
        ]
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/nodes",
            headers=HEADERS,
            json={
                "title": "Lead intake",
                "title_vi": "Tiếp nhận lead",
                "note": "Nhận lead từ Zalo",
                "hashtags": ["prospect_data", "q1_campaign"],
                "required_document_types": [
                    {"kind": "csv", "name": "Lead list", "required": True}
                ],
                "position_x": 100, "position_y": 100,
                "sequence_order": 1,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["title"] == "Lead intake"
        assert body["hashtags"] == ["prospect_data"]   # mock returns prospect_data only

    def test_workflow_not_found_returns_404(self, app_client, conn):
        conn.fetchrow.return_value = None   # workflow lookup fails
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/nodes",
            headers=HEADERS,
            json={"title": "X"},
        )
        assert resp.status_code == 404


class TestUpdateNode:

    def test_update_hashtags_only(self, app_client, conn):
        conn.fetchrow.return_value = _node_row(hashtags=["q1_campaign", "vip"])
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}/nodes/{NODE_ID}",
            headers=HEADERS,
            json={"hashtags": ["q1_campaign", "vip"]},
        )
        assert resp.status_code == 200
        assert resp.json()["hashtags"] == ["q1_campaign", "vip"]

    def test_update_node_missing_returns_404(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}/nodes/{NODE_ID}",
            headers=HEADERS,
            json={"title": "renamed"},
        )
        assert resp.status_code == 404


# ─── Edges ──────────────────────────────────────────────────────────


class TestCreateEdge:

    def test_self_loop_rejected_400(self, app_client):
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/edges",
            headers=HEADERS,
            json={"source_node_id": NODE_ID, "target_node_id": NODE_ID},
        )
        assert resp.status_code == 400
        assert "self-loop" in resp.json()["detail"]

    def test_endpoints_outside_workflow_returns_400(self, app_client, conn):
        # First fetchrow: workflow lookup (ws-aware after mig 059)
        conn.fetchrow.return_value = _ws_aware_lookup_row()
        conn.fetch.return_value = []  # 0 endpoints found
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/edges",
            headers=HEADERS,
            json={"source_node_id": NODE_ID, "target_node_id": NODE_ID_2},
        )
        assert resp.status_code == 400

    def test_happy_path_inserts_edge(self, app_client, conn):
        # fetchrow side_effect: 1st = workflow lookup, 2nd = INSERT RETURNING
        conn.fetchrow.side_effect = [
            _ws_aware_lookup_row(),   # workflow exists + ws-aware fields
            _edge_row(),              # INSERT RETURNING
        ]
        conn.fetch.return_value = [
            _ws_aware_lookup_row(extra={"node_id": UUID(NODE_ID)}),
            _ws_aware_lookup_row(extra={"node_id": UUID(NODE_ID_2)}),
        ]
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/edges",
            headers=HEADERS,
            json={"source_node_id": NODE_ID, "target_node_id": NODE_ID_2, "label": "next"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["edge_id"] == EDGE_ID


# ─── Tree ───────────────────────────────────────────────────────────


class TestWorkflowTree:

    def test_tree_includes_attached_documents(self, app_client, conn):
        # 3 fetchrow calls: workflow, then nothing else (fetch lists below).
        conn.fetchrow.return_value = _wf_row()
        # fetch.side_effect = nodes, edges, docs (3 calls in get_workflow_tree)
        conn.fetch.side_effect = [
            [_node_row()],                                          # nodes
            [_edge_row()],                                          # edges
            [                                                       # docs
                _row(
                    attachment_id=uuid4(),
                    node_id=UUID(NODE_ID),
                    file_id=UUID(FILE_ID),
                    document_kind="csv",
                    uploaded_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
                    uploaded_by=UUID(USER),
                    notes=None,
                    filename="leads_2026q1.csv",
                    row_count=120,
                    sha256="deadbeef",
                ),
            ],
        ]
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}/tree", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["workflow"]["workflow_id"] == WORKFLOW_ID
        assert len(body["nodes"]) == 1
        attached = body["nodes"][0]["attached_documents"]
        assert len(attached) == 1
        assert attached[0]["filename"] == "leads_2026q1.csv"

    def test_tree_missing_workflow_returns_404(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}/tree", headers=HEADERS)
        assert resp.status_code == 404


# ─── Templates ──────────────────────────────────────────────────────


class TestListTemplates:

    def test_list_returns_counts(self, app_client, conn):
        conn.fetch.return_value = [
            _row(
                template_id=UUID(TEMPLATE_ID),
                display_name="Lead Qualification Workflow",
                display_name_vi="Quy trình thẩm định lead",
                description="5-step pipeline",
                department_type="sales",
                category="pipeline",
                industry_vertical=None,
                estimated_setup_minutes=12,
                workflow_definition={
                    "nodes": [{"client_id": "n1"}, {"client_id": "n2"}],
                    "edges": [{"source_client_id": "n1", "target_client_id": "n2"}],
                },
            ),
        ]
        resp = app_client.get("/workflow-templates", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body[0]["node_count"] == 2
        assert body[0]["edge_count"] == 1

    def test_filter_invalid_dept_returns_422(self, app_client):
        resp = app_client.get(
            "/workflow-templates?department_type=bogus",
            headers=HEADERS,
        )
        assert resp.status_code == 422


class TestCloneFromTemplate:

    def test_clone_creates_workflow_and_replaces_client_ids(self, app_client, conn):
        # fetchrow calls in order:
        #   1) dept guard
        #   2) template lookup
        #   3) workflow INSERT RETURNING
        conn.fetchrow.side_effect = [
            _dept_row(),                                                     # dept guard
            _row(                                                            # template lookup
                template_id=UUID(TEMPLATE_ID),
                display_name="Lead Qualification Workflow",
                display_name_vi="Quy trình thẩm định lead",
                description="5-step pipeline",
                category="pipeline",
                workflow_definition={
                    "nodes": [
                        {"client_id": "n1", "title": "Lead intake",
                         "title_vi": "Tiếp nhận", "sequence_order": 1,
                         "position_x": 100, "position_y": 100},
                        {"client_id": "n2", "title": "Score lead",
                         "sequence_order": 2, "position_x": 320, "position_y": 100},
                    ],
                    "edges": [
                        {"source_client_id": "n1", "target_client_id": "n2"}
                    ],
                },
            ),
            _wf_row(source="template_based"),                                # workflow INSERT
        ]
        resp = app_client.post(
            "/workflows/from-template",
            headers=HEADERS,
            json={"template_id": TEMPLATE_ID, "department_id": DEPT_ID},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["source"] == "template_based"

        # Verify INSERTs ran for 2 nodes + 1 edge (conn.execute called).
        assert conn.execute.await_count >= 3

    def test_clone_template_not_found_returns_404(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _dept_row(),                     # dept guard
            None,                            # template lookup fails
        ]
        resp = app_client.post(
            "/workflows/from-template",
            headers=HEADERS,
            json={"template_id": TEMPLATE_ID, "department_id": DEPT_ID},
        )
        assert resp.status_code == 404


# ─── Cross-workflow links (mig 057) ──────────────────────────────────


WORKFLOW_A = "aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa"
WORKFLOW_B = "bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb"
WORKSPACE_W = "33333333-3333-3333-3333-333333333333"
LINK_ID    = "cccccccc-3333-3333-3333-cccccccccccc"


class TestCrossWorkflowLinks:

    def test_self_link_rejected_400(self, app_client):
        resp = app_client.post(
            "/workflow-cross-links",
            headers=HEADERS,
            json={
                "source_workflow_id": WORKFLOW_A,
                "target_workflow_id": WORKFLOW_A,
            },
        )
        assert resp.status_code == 400

    def test_invalid_link_type_returns_422(self, app_client):
        resp = app_client.post(
            "/workflow-cross-links",
            headers=HEADERS,
            json={
                "source_workflow_id": WORKFLOW_A,
                "target_workflow_id": WORKFLOW_B,
                "link_type": "bogus",
            },
        )
        assert resp.status_code == 422

    def test_create_link_rejects_cross_workspace(self, app_client, conn):
        other_ws = "44444444-4444-4444-4444-444444444444"
        conn.fetch.return_value = [
            _row(workflow_id=UUID(WORKFLOW_A), enterprise_id=UUID(ENTERPRISE),
                 department_id=UUID(DEPT_ID), workspace_id=UUID(WORKSPACE_W)),
            _row(workflow_id=UUID(WORKFLOW_B), enterprise_id=UUID(ENTERPRISE),
                 department_id=UUID(DEPT_ID), workspace_id=UUID(other_ws)),
        ]
        resp = app_client.post(
            "/workflow-cross-links",
            headers=HEADERS,
            json={"source_workflow_id": WORKFLOW_A, "target_workflow_id": WORKFLOW_B},
        )
        assert resp.status_code == 400
        assert "cross-workspace" in resp.json()["detail"]

    def test_create_link_happy_path(self, app_client, conn):
        conn.fetch.return_value = [
            _row(workflow_id=UUID(WORKFLOW_A), enterprise_id=UUID(ENTERPRISE),
                 department_id=UUID(DEPT_ID), workspace_id=UUID(WORKSPACE_W)),
            _row(workflow_id=UUID(WORKFLOW_B), enterprise_id=UUID(ENTERPRISE),
                 department_id=UUID(DEPT_ID), workspace_id=UUID(WORKSPACE_W)),
        ]
        conn.fetchrow.return_value = _row(
            link_id=UUID(LINK_ID),
            workspace_id=UUID(WORKSPACE_W),
            source_workflow_id=UUID(WORKFLOW_A),
            source_node_id=None,
            target_workflow_id=UUID(WORKFLOW_B),
            target_node_id=None,
            link_type='triggers',
            condition=None,
            label='Marketing → CS handoff',
            is_active=True,
        )
        resp = app_client.post(
            "/workflow-cross-links",
            headers=HEADERS,
            json={
                "source_workflow_id": WORKFLOW_A,
                "target_workflow_id": WORKFLOW_B,
                "link_type": "triggers",
                "label": "Marketing → CS handoff",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["link_type"] == "triggers"

    def test_list_links_with_cross_dimension_flags(self, app_client, conn):
        conn.fetch.return_value = [
            _row(
                link_id=UUID(LINK_ID),
                workspace_id=UUID(WORKSPACE_W),
                source_workflow_id=UUID(WORKFLOW_A),
                source_node_id=None,
                target_workflow_id=UUID(WORKFLOW_B),
                target_node_id=None,
                link_type='triggers',
                condition=None,
                label='VinMart → VinEco',
                is_active=True,
                source_workflow_name='VinMart Reorder',
                source_workflow_name_vi='Đặt lại hàng VinMart',
                source_enterprise_name='VinMart',
                source_node_title=None,
                source_node_title_vi=None,
                source_department_name='Warehouse',
                source_dept_type='warehouse',
                target_workflow_name='VinEco Production',
                target_workflow_name_vi='Sản xuất VinEco',
                target_enterprise_name='VinEco',
                target_node_title=None,
                target_node_title_vi=None,
                target_department_name='Warehouse',
                target_dept_type='warehouse',
                crosses_enterprise=True,
                crosses_department=False,
                crosses_branch=False,
                crosses_division=True,        # VinMart Bán lẻ → VinEco Nông nghiệp
                crosses_corporate_group=False,
            ),
        ]
        resp = app_client.get(
            f"/workflow-cross-links?workflow_id={WORKFLOW_A}",
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 1
        # Cross-dimension flags surface for FE badges
        assert body[0]["crosses_enterprise"] is True
        assert body[0]["crosses_division"]   is True
        assert body[0]["crosses_corporate_group"] is False
        assert body[0]["source_enterprise_name"] == "VinMart"
        assert body[0]["target_enterprise_name"] == "VinEco"

    def test_delete_link_returns_204(self, app_client, conn):
        conn.execute.return_value = "DELETE 1"
        resp = app_client.delete(f"/workflow-cross-links/{LINK_ID}", headers=HEADERS)
        assert resp.status_code == 204

    def test_delete_link_404_when_missing(self, app_client, conn):
        conn.execute.return_value = "DELETE 0"
        resp = app_client.delete(f"/workflow-cross-links/{LINK_ID}", headers=HEADERS)
        assert resp.status_code == 404


# ─── Phase 2 — Decision node types + folder CRUD + stats (mig 058) ──


class TestDecisionNodes:

    def test_create_if_else_node(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _ws_aware_lookup_row(),
            _node_row(
                node_type="decision_if_else",
                category="decision",
                side_effect_class="pure",
                title="Doanh thu giảm > 10%?",
            ),
        ]
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/nodes",
            headers=HEADERS,
            json={
                "title": "Doanh thu giảm > 10%?",
                "node_type": "decision_if_else",
                "category": "decision",
                "side_effect_class": "pure",
                "decision_config": {
                    "condition": "revenue_change_pct < -10",
                    "true_target_id": NODE_ID,
                    "false_target_id": NODE_ID_2,
                },
            },
        )
        assert resp.status_code == 201, resp.text

    def test_invalid_node_type_returns_422(self, app_client):
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/nodes",
            headers=HEADERS,
            json={"title": "X", "node_type": "bogus_type"},
        )
        assert resp.status_code == 422


FOLDER_ID = "fffffff0-0000-0000-0000-000000000fff"


class TestFolderCRUD:

    def test_create_folder_node_not_found(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.post(
            "/workflow-step-folders",
            headers=HEADERS,
            json={
                "workflow_id": WORKFLOW_ID,
                "node_id":     NODE_ID,
                "name":        "Hợp đồng 2026",
            },
        )
        assert resp.status_code == 404

    def test_create_folder_happy_path(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _ws_aware_lookup_row(),                # node lookup
            _row(folder_id=UUID(FOLDER_ID), workflow_id=UUID(WORKFLOW_ID),
                 node_id=UUID(NODE_ID), parent_folder_id=None,
                 name='Hợp đồng 2026', sort_order=0, status='active'),
        ]
        resp = app_client.post(
            "/workflow-step-folders",
            headers=HEADERS,
            json={
                "workflow_id": WORKFLOW_ID,
                "node_id":     NODE_ID,
                "name":        "Hợp đồng 2026",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["name"] == "Hợp đồng 2026"

    def test_create_subfolder_validates_parent(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _ws_aware_lookup_row(),    # node lookup
            None,                                  # parent folder lookup fails
        ]
        resp = app_client.post(
            "/workflow-step-folders",
            headers=HEADERS,
            json={
                "workflow_id": WORKFLOW_ID,
                "node_id":     NODE_ID,
                "name":        "Hợp đồng Q1",
                "parent_folder_id": FOLDER_ID,
            },
        )
        assert resp.status_code == 400
        assert "parent_folder_id" in resp.json()["detail"]

    def test_archive_folder_returns_204(self, app_client, conn):
        conn.execute.return_value = "UPDATE 1"
        resp = app_client.delete(
            f"/workflow-step-folders/{FOLDER_ID}",
            headers=HEADERS,
        )
        assert resp.status_code == 204

    def test_archive_folder_404_when_missing(self, app_client, conn):
        conn.execute.return_value = "UPDATE 0"
        resp = app_client.delete(
            f"/workflow-step-folders/{FOLDER_ID}",
            headers=HEADERS,
        )
        assert resp.status_code == 404


class TestWorkflowStats:

    def test_stats_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(
            f"/workflows/{WORKFLOW_ID}/stats",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_stats_aggregates_files_links_kpis(self, app_client, conn):
        # fetchrow 1: workflow lookup
        # fetchrow 2: cross_counts
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID), name='Test', name_vi='Kiểm thử',
                 department_id=UUID(DEPT_ID), enterprise_id=UUID(ENTERPRISE),
                 branch_id=None),
            _row(outgoing=2, incoming=1),
        ]
        # fetch 1: per-step file rows
        # fetch 2: kpi snapshots
        conn.fetch.side_effect = [
            [
                _row(node_id=UUID(NODE_ID),    file_count=3, document_kind='csv'),
                _row(node_id=UUID(NODE_ID),    file_count=1, document_kind='pdf'),
                _row(node_id=UUID(NODE_ID_2),  file_count=2, document_kind='csv'),
            ],
            [],   # no kpi snapshots
        ]
        # fetchval calls: folder_count, node_count, edge_count
        conn.fetchval.side_effect = [4, 5, 4]

        resp = app_client.get(
            f"/workflows/{WORKFLOW_ID}/stats",
            headers=HEADERS,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_files"] == 6           # 3+1+2
        assert body["files_per_kind"]["csv"] == 5
        assert body["files_per_kind"]["pdf"] == 1
        assert body["files_per_step"][NODE_ID] == 4
        assert body["files_per_step"][NODE_ID_2] == 2
        assert body["cross_links"]["outgoing"] == 2
        assert body["cross_links"]["incoming"] == 1
        assert body["folder_count"] == 4
        assert body["node_count"]   == 5
        assert body["edge_count"]   == 4
        assert body["recent_kpis"] == []


# ─── BPMN diagram (mig 115, builder pivot 2026-05-29) ───────────────


_VALID_BPMN = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'
    ' xmlns:kaori="http://kaori.ai/bpmn" id="Defs_1"'
    ' targetNamespace="http://kaori.ai/bpmn">'
    '<bpmn:process id="Process_1" isExecutable="true">'
    '<bpmn:startEvent id="S"><bpmn:outgoing>f</bpmn:outgoing></bpmn:startEvent>'
    '<bpmn:serviceTask id="T" name="Phân loại" kaori:nodeType="classify_text">'
    '<bpmn:incoming>f</bpmn:incoming></bpmn:serviceTask>'
    '<bpmn:sequenceFlow id="f" sourceRef="S" targetRef="T"/>'
    '</bpmn:process></bpmn:definitions>'
)


class TestWorkflowBpmn:

    def test_get_returns_null_when_unset(self, app_client, conn):
        # _wf_row has no bpmn_xml key → row.get('bpmn_xml') is None.
        conn.fetchrow.return_value = _wf_row()
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}/bpmn", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["bpmn_xml"] is None
        assert body["design_summary"] is None

    def test_get_returns_summary_when_set(self, app_client, conn):
        conn.fetchrow.return_value = _wf_row(bpmn_xml=_VALID_BPMN)
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}/bpmn", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["bpmn_xml"] == _VALID_BPMN
        assert body["design_summary"]["node_count"] == 2
        assert body["design_summary"]["executable_count"] == 2

    def test_get_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(f"/workflows/{WORKFLOW_ID}/bpmn", headers=HEADERS)
        assert resp.status_code == 404

    def test_put_stores_and_summarises(self, app_client, conn):
        conn.fetchrow.return_value = _wf_row(bpmn_xml=_VALID_BPMN)
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}/bpmn",
            headers=HEADERS,
            json={"bpmn_xml": _VALID_BPMN},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["design_summary"]["node_count"] == 2
        assert body["design_summary"]["trigger_count"] == 1

    def test_put_malformed_returns_400(self, app_client, conn):
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}/bpmn",
            headers=HEADERS,
            json={"bpmn_xml": "<bpmn:definitions><oops>"},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == "WORKFLOW.INVALID_BPMN"
        # Must reject BEFORE touching the DB.
        conn.fetchrow.assert_not_awaited()

    def test_put_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}/bpmn",
            headers=HEADERS,
            json={"bpmn_xml": _VALID_BPMN},
        )
        assert resp.status_code == 404


class TestWorkflowBpmnSync:

    def test_sync_projects_nodes_and_edges(self, app_client, conn):
        conn.fetchrow.return_value = _wf_row(
            bpmn_xml=_VALID_BPMN, workspace_id=_DEFAULT_WS)
        conn.fetch.return_value = []   # node_type_catalog keys (none → known=None)
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/bpmn/sync", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["nodes_created"] == 2     # startEvent + serviceTask
        assert body["edges_created"] == 1
        assert body["design_summary"]["executable_count"] == 2
        assert body["dangling_branches"] == []
        # DELETE nodes + edges + INSERTs all went through conn.execute.
        assert conn.execute.await_count >= 4
        # The resolved executor key (classify_text) must be written so the
        # runner can route the node (mig 117).
        all_args = [a for c in conn.execute.await_args_list for a in c.args]
        assert "classify_text" in all_args

    def test_sync_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/bpmn/sync", headers=HEADERS)
        assert resp.status_code == 404

    def test_sync_422_when_no_bpmn(self, app_client, conn):
        conn.fetchrow.return_value = _wf_row(workspace_id=_DEFAULT_WS)  # no bpmn_xml
        resp = app_client.post(
            f"/workflows/{WORKFLOW_ID}/bpmn/sync", headers=HEADERS)
        assert resp.status_code == 422
