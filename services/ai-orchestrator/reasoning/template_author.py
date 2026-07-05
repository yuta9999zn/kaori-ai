"""Template author — dựng BẢN NHÁP mẫu tài liệu từ một file có sẵn
(ADR-0042 P3: upload template → AI nhận diện cấu trúc → user duyệt).

Qwen (K-3, local — K-4) phân tích CẤU TRÚC của file — tài liệu có những
mục nào, mục nào là bảng, bảng có cột gì kiểu gì — KHÔNG chép nội dung.
Kết quả đi qua ``sanitize_template_draft`` (kind whitelist, width snap về
mức chuẩn, giới hạn số mục/cột) rồi ghi vào bản ghi template ``is_active
= FALSE`` — người dùng duyệt/sửa trong trình sửa Mẫu rồi mới kích hoạt.

Trạng thái qua ``description`` marker (không thêm cột):
  '⏳ …' đang phân tích · thành công = mô tả AI · '⚠️ …' thất bại.
"""
from __future__ import annotations

import json
import os
from typing import Optional
from uuid import UUID

import structlog

from ..shared.blob_store import blob_key, get_blob_store
from ..shared.db import acquire_for_tenant
from ..shared.doc_metadata import sanitize_template_draft

log = structlog.get_logger()

ANALYZING_MARKER = "⏳ AI đang phân tích cấu trúc từ file…"
FAILED_MARKER = ("⚠️ AI chưa phân tích được cấu trúc — sửa mẫu thủ công "
                 "hoặc thử lại với file rõ cấu trúc hơn.")

_MAX_CHARS = int(os.getenv("KAORI_TPLGEN_MAX_CHARS", "7000"))

_PROMPT = """Bạn là chuyên gia chuẩn hoá tài liệu doanh nghiệp. Dưới đây là nội dung MỘT FILE MẪU. \
Nhiệm vụ: nhận diện BỘ KHUNG của loại tài liệu này để làm mẫu tái sử dụng — KHÔNG chép nội dung cụ thể.

Trả về DUY NHẤT một JSON object:
{{"icon": "<1 emoji>", "description": "<1-2 câu tiếng Việt: mẫu này dùng cho loại tài liệu gì>",
"metadata_schema": [{{"key": "<slug>", "label_vi": "<nhãn>", "label_en": "<EN>", "kind": "<kiểu>", "required": true/false}}],
"section_outline": [{{"key": "<slug>", "heading_vi": "<tiêu đề mục>", "heading_en": "<EN>", "hint_vi": "<mục này chứa gì>",
"body_kind": "prose|table", "columns": [{{"key": "<slug>", "label_vi": "<nhãn cột>", "label_en": "<EN>", "kind": "<kiểu>", "width": 90|160|280|420}}]}}]}}

Quy tắc:
- kind CHỈ được là: text, long_text, number, money, date, user, select, status, link.
- metadata_schema = các trường quản lý chung của tài liệu (người thực hiện/duyệt → kind user; trạng thái → kind status kèm "options").
- section_outline: theo đúng thứ tự các mục trong file; mục có bảng → body_kind "table" + đúng danh sách cột của bảng đó; cột chứa URL/tham chiếu → kind "link"; cột mô tả dài → long_text, width 280.
- Bỏ qua mục "lịch sử chỉnh sửa/history changes" nếu có — hệ thống tự sinh.
- Tối đa 8 trường, 8 mục, 10 cột mỗi bảng. Chỉ dựa trên file — không bịa mục không có.

NỘI DUNG FILE:
{text}
"""


def _extract_json(raw: str) -> dict:
    """Rút JSON từ completion; JSON bị CẮT CỤT (hết token giữa chừng) được
    vá bằng cách bỏ phần tử dở dang + đóng ngoặc còn thiếu."""
    if not raw:
        return {}
    s = raw.find("{")
    if s < 0:
        return {}
    frag = raw[s: raw.rfind("}") + 1] if raw.rfind("}") > s else raw[s:]
    try:
        obj = json.loads(frag)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, TypeError):
        pass
    # vá: cắt lùi tới dấu phẩy/ngoặc đóng gần nhất rồi cân bằng ngoặc
    frag = raw[s:]
    for cut in range(len(frag), max(len(frag) - 2000, 10), -1):
        piece = frag[:cut].rstrip().rstrip(",")
        opens = piece.count("{") - piece.count("}")
        opens_sq = piece.count("[") - piece.count("]")
        if opens < 0 or opens_sq < 0 or piece.count('"') % 2 == 1:
            continue
        candidate = piece + "]" * opens_sq + "}" * opens
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            continue
    return {}


async def _load_run_text(conn, enterprise_id: UUID, run_id: UUID) -> tuple[str, str]:
    """(text, filename) từ một upload run: ưu tiên DocSage extract; file
    text thuần (txt/md/csv — nhánh tabular không có docsage) đọc thẳng blob."""
    row = await conn.fetchrow(
        """SELECT bf.metadata->>'docsage_text' AS text, pr.filename, pr.file_sha256
           FROM pipeline_runs pr
           LEFT JOIN bronze_files bf ON bf.run_id = pr.run_id  -- tenant-filter-lint: allow
           WHERE pr.run_id = $1
           ORDER BY (bf.metadata->>'docsage_text') IS NULL
           LIMIT 1""",
        run_id)
    if row is None:
        return "", ""
    text = (row["text"] or "").strip()
    filename = row["filename"] or ""
    if not text and row["file_sha256"]:
        raw = await get_blob_store().get(blob_key(str(enterprise_id), row["file_sha256"]))
        if raw:
            try:
                text = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                text = ""
    return text, filename


async def run_template_analysis(template_id: UUID, enterprise_id: UUID, run_id: UUID) -> None:
    """Background job: phân tích file → điền schema/outline vào bản nháp mẫu."""
    try:
        async with acquire_for_tenant(enterprise_id) as conn:
            text, filename = await _load_run_text(conn, enterprise_id, run_id)

        if not text:
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """UPDATE document_type_template
                       SET description = $2, updated_at = NOW() WHERE template_id = $1""",
                    template_id,
                    "⚠️ Không trích được nội dung từ file (định dạng chưa hỗ trợ trích xuất).")
            return

        draft: dict = {}
        raw: Optional[str] = ""
        try:
            from ..engine.llm_router import llm_router
            raw = await llm_router.complete(
                prompt=_PROMPT.format(text=text[:_MAX_CHARS]),
                task="template_author",
                consent_external=False,           # K-4 — file mẫu nội bộ, Qwen local
                enterprise_id=str(enterprise_id),
                run_id=None,
                max_tokens=int(os.getenv("KAORI_TPLGEN_MAX_TOKENS", "800")),
            )
            draft = _extract_json(raw or "")
        except Exception as e:  # pragma: no cover — LLM degrade
            log.warning("template_author.llm_failed", template_id=str(template_id), error=str(e))

        if not draft or not (draft.get("section_outline") or draft.get("metadata_schema")):
            # fail-loud vào log (Tenet 3) — trước đây nhánh này im lặng
            log.warning("template_author.parse_failed",
                        template_id=str(template_id), raw_len=len(raw or ""),
                        raw_head=(raw or "")[:200])

        async with acquire_for_tenant(enterprise_id) as conn:
            if not draft or not (draft.get("section_outline") or draft.get("metadata_schema")):
                await conn.execute(
                    """UPDATE document_type_template
                       SET description = $2, updated_at = NOW() WHERE template_id = $1""",
                    template_id, FAILED_MARKER)
                return
            clean = sanitize_template_draft(draft)
            desc = clean["description"] or "Mẫu dựng từ file."
            if filename:
                desc = f"{desc} (AI dựng từ file: {filename} — duyệt/sửa trước khi kích hoạt)"
            await conn.execute(
                """UPDATE document_type_template
                   SET icon = $2, description = $3,
                       metadata_schema = $4::jsonb, section_outline = $5::jsonb,
                       updated_at = NOW()
                   WHERE template_id = $1""",
                template_id, clean["icon"], desc[:600],
                json.dumps(clean["metadata_schema"], ensure_ascii=False),
                json.dumps(clean["section_outline"], ensure_ascii=False))
        log.info("template_author.complete", template_id=str(template_id),
                 fields=len(clean["metadata_schema"]), sections=len(clean["section_outline"]))
    except Exception as e:  # pragma: no cover — background safety net
        log.exception("template_author.failed", template_id=str(template_id), error=str(e))
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """UPDATE document_type_template
                       SET description = $2, updated_at = NOW() WHERE template_id = $1""",
                    template_id, FAILED_MARKER)
        except Exception:
            pass
