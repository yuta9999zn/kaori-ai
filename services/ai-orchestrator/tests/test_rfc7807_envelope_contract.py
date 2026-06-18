"""
Contract test — RFC 7807 envelope must allow custom extension members.

Why this exists:
  shared/errors.py:73 only honors `HTTPException(detail=<str>)`. dict detail
  is silently dropped and the response is rewritten to a default envelope
  with `code = VALIDATION.GENERIC`. This bit Gap 5 hard during the Edge
  contract test on 2026-05-16: the dangling-branch endpoint raised
  HTTPException with detail={"code": "WORKFLOW.DANGLING_BRANCH", "issues":
  [...]} and the wire response only carried {"code": "VALIDATION.GENERIC"}.

The fix (commit d56b6f5) was to return JSONResponse directly with
`media_type="application/problem+json"`. This test pins the contract so
the regression doesn't come back, AND documents the trap for the next
endpoint author: if you need extension members in a 4xx body, use
JSONResponse — NOT HTTPException with dict detail.

If a future refactor wraps JSONResponse the wrong way or rewrites the
handler to swallow custom fields, this test fails loud.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE  = "11111111-1111-1111-1111-111111111111"
USER        = "22222222-2222-2222-2222-222222222222"
DEPT_ID     = "33333333-3333-3333-3333-333333333333"
WORKFLOW_ID = "55555555-5555-5555-5555-555555555555"
NODE_ID     = "66666666-6666-6666-6666-666666666666"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    return r


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


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    """Mount ai-orchestrator's workflow_builder router with the global
    problem handlers attached — same wiring as production main.py."""
    with patch("ai_orchestrator.routers.workflow_builder.acquire_for_tenant",
               _tenant_ctx(conn)):
        from ai_orchestrator.routers import workflow_builder as wb
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI(title="rfc7807 contract test")
        test_app.include_router(wb.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


class TestRFC7807ExtensionFieldsPreserved:
    """Contract: when an endpoint needs RFC 7807 extension members on a
    4xx (e.g. ``code`` + ``issues[]``), those members MUST reach the
    client. Returning JSONResponse(media_type=problem+json, content={...})
    is the supported pattern. HTTPException(detail=<dict>) is NOT — the
    global handler strips dict detail."""

    def test_dangling_branch_envelope_carries_code_and_issues(self, app_client, conn):
        # Fake a dangling decision_if_else node (1 outgoing edge, expected 2).
        # This drives the workflow_builder endpoint through the RFC 7807
        # JSONResponse path — the canonical example of a structured 4xx in
        # this service.
        conn.fetch.return_value = [
            _row(
                node_id=UUID(NODE_ID),
                node_type="decision_if_else",
                title="Approve campaign?",
                title_vi=None,
                decision_config=None,
                outgoing_count=1,
            ),
        ]
        resp = app_client.put(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
            json={"state": "ACTIVE_BASELINE"},
        )

        # 1. Status + content type — RFC 7807 demands problem+json.
        assert resp.status_code == 400
        assert resp.headers["content-type"].startswith("application/problem+json")

        body = resp.json()

        # 2. Mandatory members per RFC 7807 §3.1.
        assert body["type"]   == "/problems/workflow-dangling-branch"
        assert body["title"]  == "Workflow has decision nodes with missing branches"
        assert body["status"] == 400

        # 3. Project-level extension: machine-readable code. This is the
        # one that was being rewritten to VALIDATION.GENERIC before
        # commit d56b6f5.
        assert body["code"] == "WORKFLOW.DANGLING_BRANCH", (
            f"code was rewritten by the global problem handler — "
            f"either someone resurrected HTTPException(detail=<dict>) "
            f"or shared/errors.py changed. Got: {body['code']!r}"
        )

        # 4. Domain extension: issues[]. Lost the moment dict detail is
        # passed through HTTPException.
        assert isinstance(body["issues"], list)
        assert len(body["issues"]) == 1
        issue = body["issues"][0]
        assert issue["node_type"]      == "decision_if_else"
        assert issue["expected_edges"] == 2
        assert issue["actual_edges"]   == 1

    def test_plain_string_detail_still_renders_envelope(self, app_client, conn):
        """Sanity check the str-detail path still works.

        Most 4xx in the service uses ``raise HTTPException(detail="...")`` —
        this confirms the global handler still envelopes those correctly
        without depending on extension members."""
        # 404 path: workflow not found.
        conn.fetchrow.return_value = None
        resp = app_client.get(
            f"/workflows/{WORKFLOW_ID}",
            headers=HEADERS,
        )

        assert resp.status_code == 404
        body = resp.json()
        # str detail becomes the title; envelope keeps RFC 7807 shape +
        # auto-derived ``code``.
        assert body["title"]  == "workflow not found"
        assert body["status"] == 404
        # code falls back to a status-derived default (NOT_FOUND etc) —
        # we just assert it's populated; the exact key is owned by
        # shared/error_codes.py.
        assert body["code"]
