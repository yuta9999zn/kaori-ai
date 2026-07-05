"""Unit tests for shared/doc_metadata.py (ADR-0042 typed metadata validator).

Pure function, no I/O. Trust-first semantics (Tenet 13): wrong-typed values
are dropped with a warning, missing required fields lower completeness —
nothing hard-blocks. Unknown keys survive under ``_extra`` (additive contract:
a template edit never destroys data).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ai_orchestrator.shared.doc_metadata import validate_metadata

U1 = "11111111-1111-1111-1111-111111111111"
U2 = "22222222-2222-2222-2222-222222222222"

SCHEMA = [
    {"key": "nguoi_phu_trach", "label_vi": "Người phụ trách", "kind": "user", "required": True},
    {"key": "muc_tieu", "label_vi": "Mục tiêu", "kind": "text", "required": True},
    {"key": "han_chot", "label_vi": "Hạn chót", "kind": "date", "required": True},
    {"key": "gia_tri", "label_vi": "Giá trị", "kind": "money", "required": False},
    {"key": "trang_thai", "label_vi": "Trạng thái", "kind": "status", "required": True,
     "options": ["chua_bat_dau", "dang_thuc_hien", "hoan_thanh"], "default": "chua_bat_dau"},
]


def test_all_valid_full_completeness():
    r = validate_metadata(SCHEMA, {
        "nguoi_phu_trach": U1,
        "muc_tieu": "Tăng retention",
        "han_chot": "2026-08-01",
        "gia_tri": 1500000,
        "trang_thai": "dang_thuc_hien",
    })
    assert r.completeness == Decimal("1.0000")
    assert r.warnings == []
    assert r.normalized["nguoi_phu_trach"] == U1
    assert r.normalized["han_chot"] == "2026-08-01"
    assert r.normalized["gia_tri"] == 1500000.0
    assert r.normalized["trang_thai"] == "dang_thuc_hien"


def test_missing_required_lowers_completeness_not_blocking():
    r = validate_metadata(SCHEMA, {"muc_tieu": "X"})
    # 4 required: nguoi_phu_trach(miss), muc_tieu(ok), han_chot(miss),
    # trang_thai(default applied → ok) → 2/4
    assert r.completeness == Decimal("0.5000")
    assert "nguoi_phu_trach" in r.missing_required
    assert "han_chot" in r.missing_required
    assert any(w["code"] == "missing_required" for w in r.warnings)


def test_default_applied_when_absent():
    r = validate_metadata(SCHEMA, {
        "nguoi_phu_trach": U1, "muc_tieu": "X", "han_chot": "2026-08-01"})
    assert r.normalized["trang_thai"] == "chua_bat_dau"
    assert r.completeness == Decimal("1.0000")


def test_invalid_status_option_dropped_with_warning():
    r = validate_metadata(SCHEMA, {"trang_thai": "xong_roi"})
    # invalid → dropped, but default backfills it
    assert r.normalized["trang_thai"] == "chua_bat_dau"
    assert any(w["code"] == "invalid_option" and w["key"] == "trang_thai" for w in r.warnings)


def test_wrong_type_money_dropped():
    r = validate_metadata(SCHEMA, {"gia_tri": "một tỷ"})
    assert "gia_tri" not in r.normalized
    assert any(w["code"] == "wrong_type" and w["key"] == "gia_tri" for w in r.warnings)


def test_negative_money_dropped():
    r = validate_metadata(SCHEMA, {"gia_tri": -5})
    assert "gia_tri" not in r.normalized
    assert any(w["code"] == "wrong_type" for w in r.warnings)


def test_bool_is_not_a_number():
    r = validate_metadata(SCHEMA, {"gia_tri": True})
    assert "gia_tri" not in r.normalized


def test_date_accepts_date_object_and_iso_string():
    r = validate_metadata(SCHEMA, {"han_chot": date(2026, 8, 1)})
    assert r.normalized["han_chot"] == "2026-08-01"
    r2 = validate_metadata(SCHEMA, {"han_chot": "31/08/2026"})
    assert "han_chot" not in r2.normalized
    assert any(w["code"] == "wrong_type" and w["key"] == "han_chot" for w in r2.warnings)


def test_user_checked_against_known_set_when_provided():
    ok = validate_metadata(SCHEMA, {"nguoi_phu_trach": U1}, known_user_ids={U1})
    assert ok.normalized["nguoi_phu_trach"] == U1
    bad = validate_metadata(SCHEMA, {"nguoi_phu_trach": U2}, known_user_ids={U1})
    assert "nguoi_phu_trach" not in bad.normalized
    assert any(w["code"] == "unknown_user" for w in bad.warnings)


def test_user_without_known_set_only_needs_uuid_shape():
    r = validate_metadata(SCHEMA, {"nguoi_phu_trach": "not-a-uuid"})
    assert "nguoi_phu_trach" not in r.normalized
    assert any(w["code"] == "wrong_type" for w in r.warnings)


def test_unknown_keys_preserved_under_extra():
    r = validate_metadata(SCHEMA, {"muc_tieu": "X", "ghi_chu_rieng": "giữ lại"})
    assert r.normalized["_extra"] == {"ghi_chu_rieng": "giữ lại"}


def test_empty_or_invalid_schema_everything_extra():
    r = validate_metadata([], {"a": 1})
    assert r.completeness == Decimal("1.0000")
    assert r.normalized["_extra"] == {"a": 1}
    r2 = validate_metadata(None, {"a": 1})
    assert r2.normalized["_extra"] == {"a": 1}


def test_completeness_quantized_4dp():
    schema = [
        {"key": f"f{i}", "label_vi": f"F{i}", "kind": "text", "required": True}
        for i in range(3)
    ]
    r = validate_metadata(schema, {"f0": "x"})
    assert r.completeness == Decimal("0.3333")


def test_text_truncated_to_knob_with_warning(monkeypatch):
    monkeypatch.setenv("KAORI_DOCMETA_MAX_TEXT_LEN", "10")
    r = validate_metadata(SCHEMA, {"muc_tieu": "a" * 50})
    assert r.normalized["muc_tieu"] == "a" * 10
    assert any(w["code"] == "truncated" for w in r.warnings)


def test_empty_string_treated_as_missing():
    r = validate_metadata(SCHEMA, {"muc_tieu": "   "})
    assert "muc_tieu" in r.missing_required


# ─── validate_content (ADR-0042 P2 — authored documents) ─────────────

from ai_orchestrator.shared.doc_metadata import validate_content

OUTLINE = [
    {"key": "glossary", "heading_vi": "Thuật ngữ", "body_kind": "table",
     "columns": [
         {"key": "acronym", "label_vi": "Viết tắt", "kind": "text"},
         {"key": "link", "label_vi": "Link", "kind": "link"},
     ]},
    {"key": "intro", "heading_vi": "Giới thiệu", "body_kind": "prose"},
]


def test_content_valid_rows_and_prose():
    r = validate_content(OUTLINE, {"sections": [
        {"key": "glossary", "rows": [{"acronym": "KPI", "link": {"text": "Tài liệu", "url": "https://x.vn/a"}}]},
        {"key": "intro", "body_md": "# Mở đầu\n==quan trọng=="},
    ]})
    assert r.warnings == []
    sec = r.normalized["sections"][0]
    assert sec["rows"][0]["acronym"] == "KPI"
    assert sec["rows"][0]["link"]["url"] == "https://x.vn/a"


def test_content_bad_link_scheme_dropped():
    r = validate_content(OUTLINE, {"sections": [
        {"key": "glossary", "rows": [{"acronym": "A", "link": {"text": "x", "url": "javascript:alert(1)"}}]},
    ]})
    row = r.normalized["sections"][0]["rows"][0]
    assert "link" not in row
    assert any(w["code"] == "wrong_type" for w in r.warnings)


def test_content_unknown_row_keys_dropped_with_warning():
    r = validate_content(OUTLINE, {"sections": [
        {"key": "glossary", "rows": [{"acronym": "A", "hacker": "x"}]},
    ]})
    assert "hacker" not in r.normalized["sections"][0]["rows"][0]
    assert any(w["code"] == "unknown_column" for w in r.warnings)


def test_content_custom_section_allowed_prose_only():
    r = validate_content(OUTLINE, {"sections": [
        {"key": "custom_note", "heading_vi": "Ghi chú riêng", "body_md": "text tự do"},
    ]})
    assert r.normalized["sections"][0]["heading_vi"] == "Ghi chú riêng"


def test_content_none_and_garbage_safe():
    assert validate_content(OUTLINE, None).normalized == {"sections": []}
    assert validate_content(None, {"sections": "not-a-list"}).normalized == {"sections": []}


def test_content_adhoc_table_with_inline_columns():
    """Tài liệu không mẫu: mục mang cột riêng trong content — bảng tự do."""
    r = validate_content([], {"sections": [
        {"key": "bang_rieng", "heading_vi": "Bảng tự tạo",
         "columns": [
             {"key": "ten", "label_vi": "Tên", "kind": "text"},
             {"key": "lk", "label_vi": "Link", "kind": "link"},
             {"key": "hacked", "label_vi": "X", "kind": "drop_table"},  # kind lạ → text
         ],
         "rows": [{"ten": "A", "lk": {"text": "tài liệu", "url": "https://x.vn"}}]},
    ]})
    sec = r.normalized["sections"][0]
    assert sec["columns"][2]["kind"] == "text"
    assert sec["rows"][0]["ten"] == "A"
    assert sec["rows"][0]["lk"]["url"] == "https://x.vn"


# ─── sanitize_template_draft (AI dựng mẫu từ file — ADR-0042 P3) ──────

from ai_orchestrator.shared.doc_metadata import sanitize_template_draft


def test_template_draft_sanitized():
    clean = sanitize_template_draft({
        "icon": "💬", "description": "Chuẩn thông báo",
        "metadata_schema": [
            {"key": "owner", "label_vi": "Người thực hiện", "kind": "user", "required": True},
            {"key": "bad", "label_vi": "Kiểu lạ", "kind": "sql_injection"},
        ],
        "section_outline": [
            {"key": "loi", "heading_vi": "Bảng lỗi", "body_kind": "table",
             "columns": [{"key": "ma", "label_vi": "Mã", "kind": "text", "width": 100},
                          {"key": "lk", "label_vi": "Link", "kind": "link", "width": 5000}]},
            {"key": "loi", "heading_vi": "Trùng key — bỏ"},
            {"heading_vi": "Mô tả tự do"},
        ],
    })
    assert clean["metadata_schema"][1]["kind"] == "text"          # kind lạ → text
    cols = clean["section_outline"][0]["columns"]
    assert cols[0]["width"] == 90                                  # snap 100 → 90
    assert cols[1]["width"] == 420                                 # kẹp 5000 → 420
    keys = [s["key"] for s in clean["section_outline"]]
    assert keys.count("loi") == 1                                  # trùng key bỏ
    assert clean["section_outline"][1]["body_kind"] == "prose"


def test_template_draft_garbage_safe():
    clean = sanitize_template_draft(None)
    assert clean["metadata_schema"] == [] and clean["section_outline"] == []
