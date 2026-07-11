"""HTTP-surface tests for Kho tài liệu business-date features (mig 138).

Time is METADATA, not tree depth: doc_date (business date — a daily report
dated 30/06 can be uploaded 02/07) + period_kind (day|week|month|quarter|year;
weekly reports straddle months so a physical tree cannot hold them). Filters
and the virtual timeline both key off COALESCE(doc_date, uploaded_at::date).

Mocks acquire_for_tenant; no Postgres. Pattern mirrors
test_compliance_model_card_router.py.
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
DOC_ID = "99999999-9999-9999-9999-999999999999"
FOLDER_ID = "88888888-8888-8888-8888-888888888888"
HEADERS = {"X-Enterprise-ID": ENTERPRISE_ID}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _file_row(**overrides) -> MagicMock:
    base = dict(
        doc_id=UUID(DOC_ID), external_ref="doc_01HZZZ", name_vi="bao_cao_ngay.txt",
        doc_type="txt", status="active", version=1, storage_tier="hot",
        valid_until=None, sha256="ab" * 32,
        uploaded_at=datetime.datetime(2026, 7, 2, 10, 0),
        doc_date=datetime.date(2026, 6, 30), period_kind="day",
    )
    base.update(overrides)
    return _row(**base)


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    conn.execute.return_value = "OK"
    return conn


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    @asynccontextmanager
    async def _fake(*_args, **_kwargs):
        yield conn

    with patch("ai_orchestrator.routers.document_repository.acquire_for_tenant", _fake):
        import ai_orchestrator.routers.document_repository as dr
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(dr.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


# ─── search date filters ─────────────────────────────────────────────


def test_search_passes_date_range_and_period(app_client, conn):
    resp = app_client.get(
        "/document-repository/search",
        params={"date_from": "2026-06-01", "date_to": "2026-06-30",
                "period_kind": "day"},
        headers=HEADERS)
    assert resp.status_code == 200, resp.text

    sql = conn.fetch.await_args.args[0]
    args = conn.fetch.await_args.args[1:]
    # Business-date semantics: filter hits the EFFECTIVE date, not uploaded_at.
    assert "COALESCE(d.doc_date, d.uploaded_at::date)" in sql
    assert datetime.date(2026, 6, 1) in args
    assert datetime.date(2026, 6, 30) in args
    assert "day" in args


def test_search_returns_doc_date_fields(app_client, conn):
    conn.fetch.return_value = [_row(
        doc_id=UUID(DOC_ID), name_vi="bao_cao_ngay.txt", doc_type="txt",
        status="active", folder_id=UUID(FOLDER_ID), path="2026/quy_2",
        doc_date=datetime.date(2026, 6, 30), period_kind="day",
        uploaded_at=datetime.datetime(2026, 7, 2, 10, 0),
        first_uploaded_at=datetime.datetime(2026, 7, 2, 10, 0),
    )]
    resp = app_client.get("/document-repository/search", headers=HEADERS)
    item = resp.json()["items"][0]
    assert item["doc_date"] == "2026-06-30"
    assert item["period_kind"] == "day"


def test_search_rejects_bad_period_kind(app_client):
    resp = app_client.get("/document-repository/search",
                          params={"period_kind": "decade"}, headers=HEADERS)
    assert resp.status_code == 422


# ─── folder file listing date filters ────────────────────────────────


def test_list_files_passes_date_range(app_client, conn):
    resp = app_client.get(
        f"/document-folders/{FOLDER_ID}/files",
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
        headers=HEADERS)
    assert resp.status_code == 200, resp.text
    sql = conn.fetch.await_args.args[0]
    args = conn.fetch.await_args.args[1:]
    assert "COALESCE(d.doc_date, d.uploaded_at::date)" in sql
    assert datetime.date(2026, 6, 1) in args and datetime.date(2026, 6, 30) in args


def test_list_files_returns_doc_date(app_client, conn):
    conn.fetch.return_value = [_file_row()]
    resp = app_client.get(f"/document-folders/{FOLDER_ID}/files", headers=HEADERS)
    item = resp.json()["items"][0]
    assert item["doc_date"] == "2026-06-30"
    assert item["period_kind"] == "day"


# ─── PATCH business date ─────────────────────────────────────────────


def test_patch_sets_doc_date_and_period(app_client, conn):
    conn.fetchrow.return_value = _file_row()
    resp = app_client.patch(
        f"/document-repository/{DOC_ID}",
        json={"doc_date": "2026-06-30", "period_kind": "day"},
        headers=HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["doc_date"] == "2026-06-30"
    sql = conn.fetchrow.await_args.args[0]
    assert "UPDATE document_repository_file" in sql
    assert datetime.date(2026, 6, 30) in conn.fetchrow.await_args.args[1:]


def test_patch_404_when_missing(app_client, conn):
    conn.fetchrow.return_value = None
    resp = app_client.patch(f"/document-repository/{DOC_ID}",
                            json={"doc_date": "2026-06-30"}, headers=HEADERS)
    assert resp.status_code == 404


def test_patch_empty_body_400(app_client):
    resp = app_client.patch(f"/document-repository/{DOC_ID}", json={},
                            headers=HEADERS)
    assert resp.status_code == 400


def test_patch_rejects_bad_period_kind(app_client):
    resp = app_client.patch(f"/document-repository/{DOC_ID}",
                            json={"period_kind": "fortnight"}, headers=HEADERS)
    assert resp.status_code == 422


# ─── virtual timeline ────────────────────────────────────────────────


def test_timeline_month_groups_and_drills(app_client, conn):
    conn.fetch.return_value = [
        _row(doc_count=3, year=2026, quarter=2, month=6),
        _row(doc_count=1, year=2026, quarter=3, month=7),
    ]
    resp = app_client.get("/document-repository/timeline",
                          params={"granularity": "month"}, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["granularity"] == "month"
    assert body["buckets"][0] == {"doc_count": 3, "year": 2026, "quarter": 2, "month": 6}

    sql = conn.fetch.await_args.args[0]
    # Effective-date semantics + drill filters present.
    assert "COALESCE(doc_date, uploaded_at::date)" in sql
    assert "EXTRACT(QUARTER FROM eff)" in sql


def test_timeline_day_accepts_drill_params(app_client, conn):
    resp = app_client.get(
        "/document-repository/timeline",
        params={"granularity": "day", "year": 2026, "quarter": 2, "month": 6},
        headers=HEADERS)
    assert resp.status_code == 200
    args = conn.fetch.await_args.args[1:]
    assert 2026 in args and 2 in args and 6 in args


def test_timeline_rejects_bad_granularity(app_client):
    resp = app_client.get("/document-repository/timeline",
                          params={"granularity": "week"}, headers=HEADERS)
    assert resp.status_code == 422
