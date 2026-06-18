"""
F-038 Reports — HTTP router tests.

FastAPI TestClient with the service layer fully mocked. We're pinning
the wire shape (path, status code, response model fields) and the
header-based tenant scoping convention.

Three endpoints covered:

  POST /reports/generate
    happy path -> 202 + report_id
    invalid body (short title)  -> 422
    unknown template            -> 404
    background task spawned with both arg
  GET  /reports
    happy path -> ReportListResponse with cursor
    invalid cursor              -> 400
  GET  /reports/{id}
    happy path -> ReportDetail
    not found  -> 404
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.routers import reports as reports_router
from ai_orchestrator.reports.service import TemplateNotFoundError


_ENT_ID = "11111111-1111-1111-1111-111111111111"
_TEMPLATE_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(reports_router.router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _hdr() -> dict:
    return {"X-Enterprise-Id": _ENT_ID}


def _fake_acquire(conn):
    @asynccontextmanager
    async def _cm(_eid):
        yield conn
    return _cm


# ─── POST /reports/generate ──────────────────────────────────────

def test_generate_returns_202_with_report_id(client):
    new_id = uuid4()

    with patch("ai_orchestrator.routers.reports.service.queue_report",
               AsyncMock(return_value=new_id)) as queue_mock, \
         patch("ai_orchestrator.routers.reports.asyncio.create_task") as create_task_mock, \
         patch("ai_orchestrator.routers.reports.service.run_report",
               AsyncMock()):

        resp = client.post(
            "/reports/generate",
            headers=_hdr(),
            json={
                "template_id":  _TEMPLATE_ID,
                "title":        "Báo cáo demo",
                "owner_email":  "user@kaori.io",
                "params":       {"period": "2026-04"},
            },
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["report_id"] == str(new_id)
    assert body["status"] == "queued"

    queue_mock.assert_awaited_once()
    # The background worker is spawned via create_task — that single
    # call is what makes the endpoint return 202 instead of waiting
    # for the LLM.
    create_task_mock.assert_called_once()


def test_generate_unknown_template_returns_404(client):
    """Service raises TemplateNotFoundError; router maps to 404 so the
    FE can surface 'template không tồn tại'."""
    with patch("ai_orchestrator.routers.reports.service.queue_report",
               AsyncMock(side_effect=TemplateNotFoundError("template ... not found"))):
        resp = client.post(
            "/reports/generate",
            headers=_hdr(),
            json={
                "template_id":  _TEMPLATE_ID,
                "title":        "Báo cáo",
                "owner_email":  "user@kaori.io",
                "params":       {},
            },
        )

    assert resp.status_code == 404


def test_generate_validates_title_min_length(client):
    """Pydantic guard — title<3 chars is a caller bug."""
    resp = client.post(
        "/reports/generate",
        headers=_hdr(),
        json={
            "template_id":  _TEMPLATE_ID,
            "title":        "x",   # too short
            "owner_email":  "user@kaori.io",
            "params":       {},
        },
    )
    assert resp.status_code == 422


def test_generate_rejects_invalid_owner_email(client):
    resp = client.post(
        "/reports/generate",
        headers=_hdr(),
        json={
            "template_id":  _TEMPLATE_ID,
            "title":        "Báo cáo demo",
            "owner_email":  "not-an-email",
            "params":       {},
        },
    )
    assert resp.status_code == 422


# ─── GET /reports ────────────────────────────────────────────────

def test_list_reports_returns_items_and_no_cursor_when_under_limit(client):
    conn = AsyncMock()
    rows = [
        {
            "report_id":    uuid4(),
            "template_id":  UUID(_TEMPLATE_ID),
            "title":        "Báo cáo tháng 4",
            "owner_email":  "user@kaori.io",
            "status":       "ready",
            "narrative":    "Doanh thu vượt kế hoạch.",
            "created_at":   datetime(2026, 4, 30, tzinfo=timezone.utc),
            "completed_at": datetime(2026, 4, 30, 8, 1, tzinfo=timezone.utc),
            "last_error":   None,
        },
    ]

    with patch("ai_orchestrator.routers.reports.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.routers.reports.repository.list_reports",
               AsyncMock(return_value=rows)):

        resp = client.get("/reports", headers=_hdr(), params={"limit": 50})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Báo cáo tháng 4"
    assert body["next_cursor"] is None  # under limit -> no cursor


def test_list_reports_returns_next_cursor_when_more_pages_available(client):
    """When the repo returns limit+1 rows, the router strips the extra
    and emits a cursor for the next page."""
    conn = AsyncMock()
    rid_a, rid_b = uuid4(), uuid4()
    rows = [
        {
            "report_id":    rid_a,
            "template_id":  UUID(_TEMPLATE_ID),
            "title":        "A",
            "owner_email":  "u@k.io",
            "status":       "ready",
            "narrative":    None,
            "created_at":   datetime(2026, 4, 30, tzinfo=timezone.utc),
            "completed_at": None,
            "last_error":   None,
        },
        {
            "report_id":    rid_b,
            "template_id":  UUID(_TEMPLATE_ID),
            "title":        "B",
            "owner_email":  "u@k.io",
            "status":       "queued",
            "narrative":    None,
            "created_at":   datetime(2026, 4, 29, tzinfo=timezone.utc),
            "completed_at": None,
            "last_error":   None,
        },
    ]

    with patch("ai_orchestrator.routers.reports.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.routers.reports.repository.list_reports",
               AsyncMock(return_value=rows)):

        resp = client.get("/reports", headers=_hdr(), params={"limit": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1  # extra row stripped
    cursor = body["next_cursor"]
    assert cursor is not None
    # Cursor format: <iso8601>|<uuid>
    ts_part, id_part = cursor.split("|", 1)
    assert datetime.fromisoformat(ts_part)
    assert UUID(id_part) == rid_a


def test_list_reports_invalid_cursor_returns_400(client):
    """Garbled cursor is a caller bug — fail fast with a clear
    message rather than silently returning the first page."""
    resp = client.get("/reports", headers=_hdr(), params={"cursor": "not-a-cursor"})
    assert resp.status_code == 400
    assert "invalid cursor" in resp.json().get("detail", "").lower()


# ─── GET /reports/{id} ───────────────────────────────────────────

def test_get_report_returns_full_detail(client):
    rid = uuid4()
    conn = AsyncMock()
    detail = {
        "report_id":    rid,
        "template_id":  UUID(_TEMPLATE_ID),
        "title":        "Báo cáo tháng 4",
        "owner_email":  "user@kaori.io",
        "status":       "ready",
        "narrative":    "Tăng trưởng tốt.",
        "created_at":   datetime(2026, 4, 30, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 4, 30, 8, 1, tzinfo=timezone.utc),
        "last_error":   None,
        "content_json": {"kpi_overview": [], "trends": [], "top_risks": [], "recommendations": []},
    }

    with patch("ai_orchestrator.routers.reports.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.routers.reports.repository.fetch_report",
               AsyncMock(return_value=detail)):

        resp = client.get(f"/reports/{rid}", headers=_hdr())

    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"] == str(rid)
    assert body["status"] == "ready"
    assert "content_json" in body  # full detail includes content_json
    assert body["content_json"]["kpi_overview"] == []


def test_get_report_not_found_returns_404(client):
    """Wrong tenant or non-existent id -> RLS hides the row -> repo
    returns None -> router 404. Same code path covers both."""
    conn = AsyncMock()
    with patch("ai_orchestrator.routers.reports.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.routers.reports.repository.fetch_report",
               AsyncMock(return_value=None)):
        resp = client.get(f"/reports/{uuid4()}", headers=_hdr())

    assert resp.status_code == 404
