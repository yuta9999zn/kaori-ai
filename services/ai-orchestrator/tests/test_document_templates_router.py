"""HTTP-surface tests for ADR-0042 (doc-type templates + folder-as-page +
typed metadata + index + insights). Mocks acquire_for_tenant; no Postgres.
Pattern mirrors test_document_repository_dates.py.
"""
from __future__ import annotations

import datetime
import json
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ENTERPRISE_ID = "11111111-1111-1111-1111-111111111111"
TEMPLATE_ID = "77777777-7777-7777-7777-777777777777"
FOLDER_ID = "88888888-8888-8888-8888-888888888888"
DOC_ID = "99999999-9999-9999-9999-999999999999"
USER_ID = "55555555-5555-5555-5555-555555555555"
HEADERS = {"X-Enterprise-ID": ENTERPRISE_ID}

SCHEMA = [
    {"key": "muc_tieu", "label_vi": "Mục tiêu", "kind": "text", "required": True},
    {"key": "trang_thai", "label_vi": "Trạng thái", "kind": "status", "required": True,
     "options": ["chua_bat_dau", "hoan_thanh"], "default": "chua_bat_dau"},
]


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _tpl_row(**overrides) -> MagicMock:
    base = dict(
        template_id=UUID(TEMPLATE_ID), external_ref="tpl_01HZZZ",
        enterprise_id=None, type_key="ke_hoach_du_an", name_vi="Kế hoạch dự án",
        icon="📋", description="x", metadata_schema=json.dumps(SCHEMA),
        section_outline="[]", default_labels=["loai:ke-hoach-du-an"],
        requires_approval=False, approval_chain_id=None, is_active=True,
        updated_at=datetime.datetime(2026, 7, 5, 9, 0),
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

    with patch("ai_orchestrator.routers.document_templates.acquire_for_tenant", _fake):
        import ai_orchestrator.routers.document_templates as dt
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(dt.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


# ─── templates ────────────────────────────────────────────────────────

def test_list_templates_marks_globals(app_client, conn):
    conn.fetch.return_value = [_tpl_row()]
    resp = app_client.get("/document-templates", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["is_global"] is True
    assert item["metadata_schema"][0]["key"] == "muc_tieu"


def test_patch_global_template_403_clone_hint(app_client, conn):
    conn.fetchrow.return_value = _row(enterprise_id=None)
    resp = app_client.patch(f"/document-templates/{TEMPLATE_ID}",
                            json={"name_vi": "Đổi tên"}, headers=HEADERS)
    assert resp.status_code == 403
    # RFC 7807: a string detail surfaces as the problem title
    assert "clone" in resp.json()["title"]


def test_create_template_conflict_409(app_client, conn):
    conn.fetchrow.side_effect = Exception("uq_doctpl_scope_key violated")
    resp = app_client.post(
        "/document-templates",
        json={"type_key": "sop", "name_vi": "SOP"}, headers=HEADERS)
    assert resp.status_code == 409


# ─── folder-as-page ───────────────────────────────────────────────────

def _folder_row(**overrides):
    base = dict(
        folder_id=UUID(FOLDER_ID), name_vi="Mua hàng", path="mua_hang",
        body_md="# Nghiệp vụ mua hàng", default_template_id=UUID(TEMPLATE_ID),
        sample_file_id=None, default_labels=["quy-trinh:mua-hang"],
        page_version=3, updated_at=datetime.datetime(2026, 7, 5, 9, 0),
    )
    base.update(overrides)
    return _row(**base)


def test_get_folder_page_resolves_effective_template(app_client, conn):
    conn.fetchrow.side_effect = [
        _folder_row(),                     # folder
        _row(path="mua_hang"),             # _effective_template folder lookup
        _tpl_row(),                        # template row
    ]
    conn.fetch.return_value = [_row(
        folder_id=UUID(FOLDER_ID), default_template_id=UUID(TEMPLATE_ID),
        default_labels=["quy-trinh:mua-hang"], page_version=3)]
    resp = app_client.get(f"/document-folders/{FOLDER_ID}/page", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["page_version"] == 3
    assert body["effective_template"]["template_id"] == TEMPLATE_ID
    assert body["effective_labels"] == ["quy-trinh:mua-hang"]
    assert body["template_inherited_from"] is None  # self-bound, not inherited


def test_patch_folder_page_bumps_version_and_snapshots(app_client, conn):
    conn.fetchrow.side_effect = [
        _folder_row(page_version=3),       # FOR UPDATE row
        _tpl_row(),                        # template snapshot load
    ]
    resp = app_client.patch(
        f"/document-folders/{FOLDER_ID}/page",
        json={"body_md": "# Sửa mô tả", "change_note": "cập nhật"},
        headers={**HEADERS, "X-User-ID": USER_ID})
    assert resp.status_code == 200, resp.text
    assert resp.json()["page_version"] == 4
    insert_sql = conn.execute.await_args_list[-1].args[0]
    assert "INSERT INTO document_folder_version" in insert_sql


def test_patch_folder_page_empty_400(app_client, conn):
    resp = app_client.patch(f"/document-folders/{FOLDER_ID}/page",
                            json={}, headers=HEADERS)
    assert resp.status_code == 400


def test_restore_appends_new_version_never_rewrites(app_client, conn):
    conn.fetchrow.side_effect = [
        _row(body_md="# Bản cũ", template_snapshot=None, sample_file_id=None),  # snapshot
        _folder_row(page_version=5),       # FOR UPDATE row
    ]
    resp = app_client.post(
        f"/document-folders/{FOLDER_ID}/page/restore",
        json={"version_no": 2}, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["page_version"] == 6
    assert resp.json()["restored_from"] == 2


# ─── doc metadata (Bước 2/3) ──────────────────────────────────────────

def _doc_row(**overrides):
    base = dict(doc_id=UUID(DOC_ID), folder_id=UUID(FOLDER_ID),
                template_id=UUID(TEMPLATE_ID), metadata="{}",
                is_current=True, superseded_by=None)
    base.update(overrides)
    return _row(**base)


def test_patch_metadata_validates_and_reports_warnings(app_client, conn):
    conn.fetchrow.side_effect = [
        _doc_row(),                                              # doc row
        _row(metadata_schema=json.dumps(SCHEMA)),                # template schema
        _row(doc_id=UUID(DOC_ID), template_id=UUID(TEMPLATE_ID),  # RETURNING
             metadata=json.dumps({"trang_thai": "chua_bat_dau"}),
             labels=[], metadata_completeness=Decimal("0.5000")),
    ]
    conn.fetch.return_value = []  # enterprise_users
    resp = app_client.patch(
        f"/document-repository/{DOC_ID}/metadata",
        json={"metadata": {"trang_thai": "chua_bat_dau"}}, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["completeness"] == 0.5
    assert "muc_tieu" in body["missing_required"]
    assert any(w["code"] == "missing_required" for w in body["warnings"])


def test_patch_metadata_follows_supersedes_chain_to_current(app_client, conn):
    """Form mở trên bản đã bị same-name re-upload chồng version → thuộc tính
    phải rơi vào bản CURRENT, không phải bản cũ."""
    current_id = "44444444-4444-4444-4444-444444444444"
    conn.fetchrow.side_effect = [
        _doc_row(is_current=False, superseded_by=UUID(current_id)),  # stale v1
        _doc_row(doc_id=UUID(current_id)),                           # current v2
        _row(metadata_schema=json.dumps(SCHEMA)),                    # template schema
        _row(doc_id=UUID(current_id), template_id=UUID(TEMPLATE_ID),
             metadata="{}", labels=[], metadata_completeness=Decimal("0.5000")),
    ]
    conn.fetch.return_value = []
    resp = app_client.patch(
        f"/document-repository/{DOC_ID}/metadata",
        json={"metadata": {"trang_thai": "chua_bat_dau"}}, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["doc_id"] == current_id
    update_args = conn.fetchrow.await_args_list[-1].args
    assert UUID(current_id) in update_args, "UPDATE must target the current version"


def test_patch_metadata_404_unknown_doc(app_client, conn):
    resp = app_client.patch(f"/document-repository/{DOC_ID}/metadata",
                            json={"metadata": {}}, headers=HEADERS)
    assert resp.status_code == 404


# ─── index (Page Properties Report) ───────────────────────────────────

def test_index_returns_columns_from_template_schema(app_client, conn):
    conn.fetch.return_value = [_row(
        doc_id=UUID(DOC_ID), external_ref="doc_x", name_vi="KH Q3",
        template_id=UUID(TEMPLATE_ID), folder_id=UUID(FOLDER_ID),
        metadata=json.dumps({"muc_tieu": "Tăng doanh thu"}), labels=["loai:ke-hoach-du-an"],
        metadata_completeness=Decimal("1.0000"), doc_date=datetime.date(2026, 7, 1),
        period_kind=None, uploaded_at=datetime.datetime(2026, 7, 5, 8, 0),
        version=1, path="mua_hang")]
    conn.fetchrow.return_value = _row(metadata_schema=json.dumps(SCHEMA))
    resp = app_client.get("/document-repository/index",
                          params={"template_id": TEMPLATE_ID}, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [c["key"] for c in body["columns"]] == ["muc_tieu", "trang_thai"]
    assert body["items"][0]["metadata"]["muc_tieu"] == "Tăng doanh thu"
    assert body["items"][0]["completeness"] == 1.0


def test_index_labels_filter_uses_array_contains(app_client, conn):
    resp = app_client.get("/document-repository/index",
                          params={"labels": "quy-trinh:mua-hang, loai:hop-dong"},
                          headers=HEADERS)
    assert resp.status_code == 200
    sql = conn.fetch.await_args.args[0]
    args = conn.fetch.await_args.args[1:]
    assert "d.labels @>" in sql
    assert ["quy-trinh:mua-hang", "loai:hop-dong"] in args


# ─── insights ─────────────────────────────────────────────────────────

def test_create_insight_202_and_background(app_client, conn):
    conn.fetchrow.return_value = _row(insight_id=UUID(DOC_ID), external_ref="ins_x")
    with patch("ai_orchestrator.routers.document_templates.run_collection_insight") as job:
        resp = app_client.post(
            "/document-repository/insights",
            json={"scope_kind": "folder", "scope": {"folder_id": FOLDER_ID}},
            headers=HEADERS)
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "pending"


def test_create_insight_folder_scope_requires_folder_id(app_client, conn):
    resp = app_client.post("/document-repository/insights",
                           json={"scope_kind": "folder", "scope": {}}, headers=HEADERS)
    assert resp.status_code == 400


def test_create_insight_group_scope_needs_a_filter(app_client, conn):
    resp = app_client.post("/document-repository/insights",
                           json={"scope_kind": "group", "scope": {}}, headers=HEADERS)
    assert resp.status_code == 400


# ─── compute_stats (pure) ─────────────────────────────────────────────

def test_compute_stats_deterministic():
    from ai_orchestrator.reasoning.collection_insight import compute_stats
    docs = [
        {"doc_id": "1", "name_vi": "HĐ A", "template_id": UUID(TEMPLATE_ID),
         "metadata": json.dumps({"trang_thai": "chua_bat_dau", "han_chot": "2020-01-01"}),
         "labels": ["loai:hop-dong"], "metadata_completeness": Decimal("0.5"),
         "doc_date": datetime.date(2026, 6, 30),
         "uploaded_at": datetime.datetime(2026, 7, 1, 8, 0), "status": "active"},
        {"doc_id": "2", "name_vi": "HĐ B", "template_id": None,
         "metadata": "{}", "labels": [], "metadata_completeness": None,
         "doc_date": None,
         "uploaded_at": datetime.datetime(2026, 7, 2, 8, 0), "status": "active"},
    ]
    templates = {TEMPLATE_ID: {"name_vi": "Kế hoạch dự án", "metadata_schema": [
        {"key": "trang_thai", "label_vi": "Trạng thái", "kind": "status",
         "options": ["chua_bat_dau", "hoan_thanh"]},
        {"key": "han_chot", "label_vi": "Hạn chót", "kind": "date"},
    ]}}
    stats = compute_stats(docs, templates, truncated=False)
    assert stats["doc_count"] == 2
    assert stats["by_template"] == {"Kế hoạch dự án": 1, "Chưa gán mẫu": 1}
    assert stats["status_counts"]["Trạng thái"]["chua_bat_dau"] == 1
    assert stats["past_date_counts"]["Hạn chót"] == 1
    assert stats["completeness"]["incomplete_count"] == 1
    assert stats["by_month"] == {"2026-06": 1, "2026-07": 1}


# ─── authored documents (ADR-0042 P2, mig 140) ────────────────────────

OUTLINE = [
    {"key": "glossary", "heading_vi": "Thuật ngữ", "body_kind": "table",
     "columns": [{"key": "acronym", "label_vi": "Viết tắt", "kind": "text"}]},
]


def test_create_authored_409_on_same_name(app_client, conn):
    conn.fetchrow.return_value = _row(folder_id=UUID(FOLDER_ID), department_id=None)
    conn.fetchval.return_value = 1  # name already current in folder
    resp = app_client.post(
        "/document-repository/authored",
        json={"folder_id": FOLDER_ID, "name_vi": "Message Definition"},
        headers=HEADERS)
    assert resp.status_code == 409


def test_create_authored_with_prompt_starts_generation(app_client, conn):
    conn.fetchval.return_value = None
    conn.fetch.return_value = [_row(
        folder_id=UUID(FOLDER_ID), default_template_id=UUID(TEMPLATE_ID),
        default_labels=["quy-trinh:mua-hang"], page_version=2)]
    conn.fetchrow.side_effect = [
        _row(folder_id=UUID(FOLDER_ID), department_id=None),   # folder
        _row(path="mua_hang"),                                  # _effective_template lookup
        _row(section_outline=json.dumps(OUTLINE)),              # _resolve template outline
        _row(path="mua_hang"),                                  # 2nd _effective_template lookup
        _row(default_labels=["loai:msgdef"]),                   # template default_labels
        _row(doc_id=UUID(DOC_ID), external_ref="doc_x"),        # RETURNING
    ]
    with patch("ai_orchestrator.routers.document_templates.run_document_generation"):
        resp = app_client.post(
            "/document-repository/authored",
            json={"folder_id": FOLDER_ID, "name_vi": "Message Definition",
                  "generate_prompt": "Tài liệu chuẩn hoá thông báo lỗi cho app bán hàng"},
            headers=HEADERS)
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "generating"
    insert_sql = conn.fetchrow.await_args_list[-1].args[0]
    assert "'authored'" in insert_sql


def test_patch_content_stacks_new_version(app_client, conn):
    doc = _row(doc_id=UUID(DOC_ID), folder_id=UUID(FOLDER_ID), name_vi="MD",
               doc_kind="authored", template_id=UUID(TEMPLATE_ID), metadata="{}",
               metadata_completeness=None, validated_page_version=None,
               labels=[], doc_date=None, period_kind=None, version=1,
               is_current=True, superseded_by=None, department_id=None)
    conn.fetchrow.side_effect = [
        doc,
        _row(section_outline=json.dumps(OUTLINE)),  # template outline
    ]
    new_id = "44444444-4444-4444-4444-444444444444"
    conn.fetchval.return_value = UUID(new_id)
    resp = app_client.patch(
        f"/document-repository/{DOC_ID}/content",
        json={"content": {"sections": [{"key": "glossary",
                                        "rows": [{"acronym": "KPI"}]}]},
              "change_note": "thêm thuật ngữ"},
        headers=HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 2
    flip_sql = conn.execute.await_args_list[-1].args[0]
    assert "superseded_by" in flip_sql


def test_patch_content_on_file_doc_409(app_client, conn):
    conn.fetchrow.return_value = _row(
        doc_id=UUID(DOC_ID), folder_id=UUID(FOLDER_ID), name_vi="f.csv",
        doc_kind="file", template_id=None, metadata="{}",
        metadata_completeness=None, validated_page_version=None, labels=[],
        doc_date=None, period_kind=None, version=1, is_current=True,
        superseded_by=None, department_id=None)
    resp = app_client.patch(
        f"/document-repository/{DOC_ID}/content",
        json={"content": {"sections": []}}, headers=HEADERS)
    assert resp.status_code == 409


def test_history_lists_version_chain(app_client, conn):
    conn.fetchrow.return_value = _row(folder_id=UUID(FOLDER_ID), name_vi="MD")
    conn.fetch.return_value = [
        _row(doc_id=UUID(DOC_ID), version=2, is_current=True,
             change_reason="AI soạn nháp (qwen2.5-local)", uploaded_by=None,
             uploaded_at=datetime.datetime(2026, 7, 5, 10, 0)),
        _row(doc_id=UUID("44444444-4444-4444-4444-444444444444"), version=1,
             is_current=False, change_reason=None, uploaded_by=None,
             uploaded_at=datetime.datetime(2026, 7, 5, 9, 0)),
    ]
    resp = app_client.get(f"/document-repository/{DOC_ID}/history", headers=HEADERS)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["version"] for i in items] == [2, 1]
    assert items[0]["is_current"] is True
