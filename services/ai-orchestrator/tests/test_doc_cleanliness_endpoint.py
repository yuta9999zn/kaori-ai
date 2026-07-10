"""
Tests for POST /workflow-documents/{attachment_id}/cleanliness — the
"đã sạch chưa?" gate on tabular Cây-tài-liệu attachments.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.routers import workflow_documents as wd


ENTERPRISE = str(uuid4())
ATTACHMENT = str(uuid4())

DIRTY_CSV = (
    "ma_lo,ngay,kg,tien\n"
    "LO-1,2026-05-02,850,11.475.000\n"
    "LO-2,03/05/2026,-50,2tr7\n"
    "LO-2,03/05/2026,-50,2tr7\n"
    "LO-4,2026-05-08,9999,129.987.000\n"
).encode("utf-8")

CLEAN_CSV = (
    "ma_lo,ngay,kg,gia\n"
    + "".join(f"LO-{i},2026-07-{i:02d},1{i}0,15000\n" for i in range(1, 11))
).encode("utf-8")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(wd.router)
    return TestClient(app)


def _wire(content: bytes, filename: str = "file.csv"):
    """Patch DB row + blob store for one attachment."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "file_sha256": "a" * 64, "mime_type": "text/csv", "filename": filename,
    })

    @asynccontextmanager
    async def fake_tenant(_eid):
        yield conn

    store = MagicMock()
    store.get = AsyncMock(return_value=content)
    return fake_tenant, store


def test_dirty_csv_routes_to_pipeline(client):
    fake_tenant, store = _wire(DIRTY_CSV)
    with patch.object(wd, "acquire_for_tenant", fake_tenant), \
         patch.object(wd, "get_blob_store", return_value=store), \
         patch.object(wd, "_cleanliness_narrative", AsyncMock(return_value=None)):
        r = client.post(f"/workflow-documents/{ATTACHMENT}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    body = r.json()
    assert body["is_clean"] is False
    assert body["recommendation"] == "run_pipeline"
    assert body["issues"]


def test_clean_csv_routes_to_analysis(client):
    fake_tenant, store = _wire(CLEAN_CSV)
    with patch.object(wd, "acquire_for_tenant", fake_tenant), \
         patch.object(wd, "get_blob_store", return_value=store), \
         patch.object(wd, "_cleanliness_narrative", AsyncMock(return_value="Dữ liệu ổn.")):
        r = client.post(f"/workflow-documents/{ATTACHMENT}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    body = r.json()
    assert body["is_clean"] is True
    assert body["recommendation"] == "analyze"
    assert body["narrative"] == "Dữ liệu ổn."


def test_non_tabular_file_rejected(client):
    fake_tenant, store = _wire(b"%PDF-1.4 ...", filename="hop_dong.pdf")
    with patch.object(wd, "acquire_for_tenant", fake_tenant), \
         patch.object(wd, "get_blob_store", return_value=store):
        r = client.post(f"/workflow-documents/{ATTACHMENT}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 400


def test_llm_failure_does_not_break_verdict(client):
    fake_tenant, store = _wire(CLEAN_CSV)
    with patch.object(wd, "acquire_for_tenant", fake_tenant), \
         patch.object(wd, "get_blob_store", return_value=store), \
         patch.object(wd, "_cleanliness_narrative",
                      AsyncMock(side_effect=RuntimeError("gateway down"))):
        r = client.post(f"/workflow-documents/{ATTACHMENT}/cleanliness",
                        headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    assert r.json()["is_clean"] is True
    assert r.json()["narrative"] is None
