"""Kho ↔ pipeline bridge (ADR-0039 follow-up, demo AABW).

1. POST /document-repository/{doc_id}/cleanliness — cùng verdict engine với
   Cây tài liệu workflow (1 file 2 mặt nhìn).
2. GET /document-folders/{id}/files trả pipeline_run_id/pipeline_run_status
   (resolve qua K-8 sha256 → pipeline_runs) để FE nối "đi tiếp từ Lịch sử chạy".
"""
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.routers import document_repository as dr
from ai_orchestrator.routers import workflow_documents as wd


ENTERPRISE = str(uuid4())
DOC = str(uuid4())
FOLDER = str(uuid4())
RUN = uuid4()

CLEAN_CSV = (
    "ma_lo,ngay,kg,gia\n"
    + "".join(f"LO-{i},2026-07-{i:02d},1{i}0,15000\n" for i in range(1, 11))
).encode("utf-8")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(dr.router)
    return TestClient(app)


def _tenant_with(conn):
    @asynccontextmanager
    async def fake_tenant(_eid):
        yield conn
    return fake_tenant


# ─────────────────────────── cleanliness ────────────────────────────────
def _doc_conn(sha="a" * 64, name="bang_gia.csv"):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"sha256": sha, "name_vi": name})
    return conn


def test_repo_cleanliness_clean_csv(client):
    store = MagicMock()
    store.get = AsyncMock(return_value=CLEAN_CSV)
    with patch.object(dr, "acquire_for_tenant", _tenant_with(_doc_conn())), \
         patch.object(wd, "get_blob_store", return_value=store), \
         patch.object(wd, "_cleanliness_narrative", AsyncMock(return_value="Dữ liệu ổn.")):
        r = client.post(f"/document-repository/{DOC}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    body = r.json()
    assert body["is_clean"] is True
    assert body["recommendation"] == "analyze"
    assert body["narrative"] == "Dữ liệu ổn."
    assert body["filename"] == "bang_gia.csv"


def test_repo_cleanliness_doc_not_found(client):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    with patch.object(dr, "acquire_for_tenant", _tenant_with(conn)):
        r = client.post(f"/document-repository/{DOC}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 404


def test_repo_cleanliness_non_tabular_rejected(client):
    with patch.object(dr, "acquire_for_tenant",
                      _tenant_with(_doc_conn(name="hop_dong.pdf"))):
        r = client.post(f"/document-repository/{DOC}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 400


# ─────────────────────────── run link on file list ──────────────────────
def _file_row(**over):
    row = {
        "doc_id": uuid4(), "external_ref": "01ARZ" + "0" * 21,
        "name_vi": "bang_gia.csv", "doc_type": "csv", "status": "active",
        "version": 1, "storage_tier": "hot", "valid_until": None,
        "sha256": "a" * 64, "uploaded_at": datetime(2026, 7, 11, 8, 0),
        "doc_date": None, "period_kind": None, "file_id": None,
        "template_id": None, "labels": [], "metadata_completeness": None,
        "metadata": {}, "doc_kind": "file",
        "pipeline_run_id": RUN, "pipeline_run_status": "silver_complete",
        "first_uploaded_at": datetime(2026, 7, 1, 9, 0),
    }
    row.update(over)
    return row


def test_list_files_carries_pipeline_run(client):
    conn = AsyncMock()
    captured: dict = {}

    async def _fetch(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return [_file_row()]

    conn.fetch = _fetch
    with patch.object(dr, "acquire_for_tenant", _tenant_with(conn)):
        r = client.get(f"/document-folders/{FOLDER}/files",
                       headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["pipeline_run_id"] == str(RUN)
    assert item["pipeline_run_status"] == "silver_complete"
    # K-8 bridge phải resolve qua sha256 + tenant-filter tường minh (K-1)
    assert "pipeline_runs" in captured["sql"]
    assert "file_sha256" in captured["sql"]
    assert "enterprise_id" in captured["sql"]


def test_list_files_carries_created_and_updated_dates(client):
    """Ngày THÊM (v1 chuỗi version) + ngày SỬA cuối (uploaded_at bản current)
    — yêu cầu UX Kho 11/07."""
    conn = AsyncMock()
    captured: dict = {}

    async def _fetch(sql, *args):
        captured["sql"] = sql
        return [_file_row()]

    conn.fetch = _fetch
    with patch.object(dr, "acquire_for_tenant", _tenant_with(conn)):
        r = client.get(f"/document-folders/{FOLDER}/files",
                       headers={"X-Enterprise-ID": ENTERPRISE})
    item = r.json()["items"][0]
    assert item["first_uploaded_at"].startswith("2026-07-01")
    assert item["uploaded_at"].startswith("2026-07-11")
    assert "MIN(uploaded_at)" in captured["sql"]


def test_search_returns_first_uploaded_at(client):
    conn = AsyncMock()

    async def _fetch(sql, *args):
        return [{
            "doc_id": uuid4(), "name_vi": "bang_gia.csv", "doc_type": "csv",
            "status": "active", "folder_id": uuid4(), "path": "kinh_doanh",
            "doc_date": None, "period_kind": None,
            "uploaded_at": datetime(2026, 7, 11, 8, 0),
            "first_uploaded_at": datetime(2026, 7, 1, 9, 0),
        }]

    conn.fetch = _fetch
    with patch.object(dr, "acquire_for_tenant", _tenant_with(conn)):
        r = client.get("/document-repository/search?q=bang",
                       headers={"X-Enterprise-ID": ENTERPRISE})
    item = r.json()["items"][0]
    assert item["first_uploaded_at"].startswith("2026-07-01")
    assert item["uploaded_at"].startswith("2026-07-11")


def test_list_files_no_run_is_null(client):
    conn = AsyncMock()

    async def _fetch(sql, *args):
        return [_file_row(pipeline_run_id=None, pipeline_run_status=None)]

    conn.fetch = _fetch
    with patch.object(dr, "acquire_for_tenant", _tenant_with(conn)):
        r = client.get(f"/document-folders/{FOLDER}/files",
                       headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["pipeline_run_id"] is None
    assert item["pipeline_run_status"] is None
