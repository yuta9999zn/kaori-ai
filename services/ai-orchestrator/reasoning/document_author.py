"""Document author — sinh tài liệu soạn-trong-Kaori từ bộ khung template
(ADR-0042 Phase 2, mig 140).

Template = bộ xương sống cho LLM hiểu chuẩn: mỗi section mang heading + hint +
(nếu là bảng) danh sách cột có kiểu. Người dùng đưa PROMPT mô tả tài liệu +
yêu cầu; Qwen (K-3, local — K-4) sinh draft TỪNG SECTION MỘT:

* per-section (không one-shot cả tài liệu) → prompt nhỏ, vừa Qwen 7B, một mục
  fail không kéo sập cả tài liệu (Tenet 13 — degrade per section);
* output ép JSON theo đúng columns của section rồi đi qua validate_content —
  AI không thể sinh sai cấu trúc bảng;
* grounded: chỉ dùng thông tin trong prompt người dùng; kind=link chỉ nhận
  URL đã xuất hiện trong prompt — tuyệt đối không bịa link.

Chạy nền (BackgroundTasks) — LLM không bao giờ nằm trong request path.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
from uuid import UUID

import structlog

from ..shared.db import acquire_for_tenant
from ..shared.doc_metadata import validate_content

log = structlog.get_logger()

_URL_RE = re.compile(r"https?://[^\s)\]}>\"']+")


def _max_rows() -> int:
    return int(os.getenv("KAORI_DOCGEN_MAX_ROWS", "12"))


def _jload(v: Any, default: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return default
    return v if v is not None else default


def _extract_json(raw: str) -> dict:
    if not raw:
        return {}
    s, e = raw.find("{"), raw.rfind("}")
    if s < 0 or e <= s:
        return {}
    try:
        obj = json.loads(raw[s:e + 1])
        return obj if isinstance(obj, dict) else {}
    except (ValueError, TypeError):
        return {}


_SECTION_PROMPT = """Bạn đang soạn MỘT MỤC của một tài liệu nghiệp vụ tiếng Việt theo mẫu chuẩn.

TÀI LIỆU: {doc_name}
MẪU: {template_name} — {template_desc}
MỤC CẦN SOẠN: "{heading}" — {hint}

YÊU CẦU CỦA NGƯỜI DÙNG (nguồn thông tin DUY NHẤT — tuyệt đối không bịa thêm):
{user_prompt}

{table_spec}

Trả về DUY NHẤT một JSON object (không thêm chữ nào ngoài JSON):
{{"body_md": "<đoạn mô tả ngắn cho mục này, Markdown; có thể dùng ## tiêu đề phụ, **đậm**, ==đánh dấu quan trọng==, - gạch đầu dòng; để \\"\\" nếu không cần>", "rows": [{row_shape}]}}

Quy tắc:
- CHỈ dùng thông tin có trong YÊU CẦU CỦA NGƯỜI DÙNG. Thiếu thông tin cho mục này → body_md ghi ngắn gọn phần còn thiếu và rows để [].
- Tối đa {max_rows} dòng.
- Cột dạng link: chỉ dùng URL xuất hiện NGUYÊN VĂN trong yêu cầu; không có thì bỏ trống cột đó.
"""


def _table_spec(columns: list[dict]) -> tuple[str, str]:
    if not columns:
        return ("Mục này KHÔNG có bảng — rows luôn là [].", "")
    lines = []
    shape_bits = []
    for c in columns:
        kind = c.get("kind", "text")
        label = c.get("label_vi") or c["key"]
        opts = f" (một trong: {', '.join(c['options'])})" if c.get("options") else ""
        if kind == "link":
            lines.append(f'- "{c["key"]}" ({label}) — dạng link: {{"text": "...", "url": "https://..."}}{opts}')
            shape_bits.append(f'"{c["key"]}": {{"text": "…", "url": "https://…"}}')
        else:
            lines.append(f'- "{c["key"]}" ({label}) — {kind}{opts}')
            shape_bits.append(f'"{c["key"]}": "…"')
    spec = "BẢNG của mục này có các cột (dùng ĐÚNG key):\n" + "\n".join(lines)
    return spec, "{" + ", ".join(shape_bits) + "}"


def _strip_uninvited_links(section: dict, allowed_urls: set[str]) -> None:
    """Grounding hard-stop: mọi URL không có nguyên văn trong prompt bị gỡ."""
    for row in section.get("rows", []):
        for k, v in list(row.items()):
            if isinstance(v, dict) and "url" in v and v["url"] not in allowed_urls:
                del row[k]
    if "links" in section:
        section["links"] = [l for l in section["links"] if l.get("url") in allowed_urls]
        if not section["links"]:
            del section["links"]


async def generate_document_content(
    *, enterprise_id: str, doc_name: str, user_prompt: str,
    template: dict,
) -> tuple[dict, str]:
    """Sinh content per-section. Returns (content, model). Mục nào LLM fail
    thì để skeleton trống + ghi chú — không raise."""
    outline = _jload(template.get("section_outline"), [])
    allowed_urls = set(_URL_RE.findall(user_prompt or ""))
    sections: list[dict] = []
    model = "rules-only"

    try:
        from ..engine.llm_router import llm_router
    except Exception:
        llm_router = None

    for odef in outline:
        if not isinstance(odef, dict) or not odef.get("key"):
            continue
        key = odef["key"]
        columns = odef.get("columns") or []
        sec: dict[str, Any] = {"key": key}

        if llm_router is not None:
            spec, row_shape = _table_spec(columns)
            prompt = _SECTION_PROMPT.format(
                doc_name=doc_name,
                template_name=template.get("name_vi", ""),
                template_desc=(template.get("description") or "")[:300],
                heading=odef.get("heading_vi", key),
                hint=odef.get("hint_vi", ""),
                user_prompt=(user_prompt or "")[:4000],
                table_spec=spec,
                row_shape=row_shape or "",
                max_rows=_max_rows(),
            )
            try:
                raw = await llm_router.complete(
                    prompt=prompt,
                    task="document_author",
                    consent_external=False,        # K-4 — nội dung nghiệp vụ, Qwen local
                    enterprise_id=enterprise_id,
                    run_id=None,
                    max_tokens=int(os.getenv("KAORI_DOCGEN_MAX_TOKENS", "600")),
                )
                out = _extract_json(raw or "")
                if out:
                    if isinstance(out.get("body_md"), str) and out["body_md"].strip():
                        sec["body_md"] = out["body_md"].strip()
                    rows = out.get("rows")
                    if isinstance(rows, list) and rows:
                        sec["rows"] = rows[: _max_rows()]
                    model = "qwen2.5-local"
            except Exception as e:  # pragma: no cover — per-section degrade
                log.warning("doc_author.section_failed", section=key, error=str(e))

        if "body_md" not in sec and "rows" not in sec:
            sec["body_md"] = "_(Mục này chưa được AI soạn — bổ sung thủ công.)_"
        _strip_uninvited_links(sec, allowed_urls)
        sections.append(sec)

    validated = validate_content(outline, {"sections": sections})
    return validated.normalized, model


async def run_document_generation(doc_id: UUID, enterprise_id: UUID, user_prompt: str) -> None:
    """Background job: doc ở status 'generating' → 'active' (content điền)
    hoặc 'active' với skeleton + ghi chú khi LLM không chạy được."""
    try:
        async with acquire_for_tenant(enterprise_id) as conn:
            row = await conn.fetchrow(
                """SELECT d.name_vi, d.template_id, t.name_vi AS tpl_name, t.description,
                          t.section_outline
                   FROM document_repository_file d
                   LEFT JOIN document_type_template t ON t.template_id = d.template_id
                   WHERE d.doc_id = $1""", doc_id)
            if row is None:
                return
        template = {
            "name_vi": row["tpl_name"] or "",
            "description": row["description"] or "",
            "section_outline": row["section_outline"] or "[]",
        }
        content, model = await generate_document_content(
            enterprise_id=str(enterprise_id), doc_name=row["name_vi"],
            user_prompt=user_prompt, template=template)

        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """UPDATE document_repository_file
                   SET content = $2::jsonb, status = 'active',
                       change_reason = $3
                   WHERE doc_id = $1""",
                doc_id, json.dumps(content, ensure_ascii=False, default=str),
                f"AI soạn nháp ({model})")
        log.info("doc_author.complete", doc_id=str(doc_id), model=model,
                 sections=len(content.get("sections", [])))
    except Exception as e:  # pragma: no cover — background safety net
        log.exception("doc_author.failed", doc_id=str(doc_id), error=str(e))
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """UPDATE document_repository_file
                       SET status = 'active',
                           content = COALESCE(content, '{"sections": []}'::jsonb),
                           change_reason = $2
                       WHERE doc_id = $1""",
                    doc_id, f"AI soạn thất bại: {str(e)[:200]}")
        except Exception:
            pass
