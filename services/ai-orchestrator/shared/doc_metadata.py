"""Typed document-metadata validation (ADR-0042).

Validates a filled Page-Properties dict against a document_type_template's
``metadata_schema`` (mig 139). Pure function, no I/O — callers resolve the
schema row and (optionally) the enterprise user/department id sets.

Trust-first semantics (Tenet 13, mirror of K-25 completeness):
* wrong-typed values → dropped from the normalized set + warning — never 4xx;
* missing required fields → lower ``completeness`` + warning — never 4xx;
* unknown keys → preserved under ``_extra`` (additive contract: a template
  edit must never destroy previously-entered data).

Knobs (env, per KAORI_* convention):
* ``KAORI_DOCMETA_MAX_TEXT_LEN``      — cap for kind=text values (default 4000)
* ``KAORI_DOCMETA_MAX_LONG_TEXT_LEN`` — cap for kind=long_text (default 20000)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN
from typing import Any, Optional
from uuid import UUID

KINDS = ("text", "long_text", "number", "money", "date",
         "user", "department", "select", "status", "link")

_Q4 = Decimal("0.0001")


def _max_len(kind: str) -> int:
    if kind == "long_text":
        return int(os.getenv("KAORI_DOCMETA_MAX_LONG_TEXT_LEN", "20000"))
    return int(os.getenv("KAORI_DOCMETA_MAX_TEXT_LEN", "4000"))


@dataclass
class MetadataValidation:
    normalized: dict[str, Any]
    completeness: Decimal
    warnings: list[dict] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)


def _warn(warnings: list[dict], key: str, code: str, message_vi: str) -> None:
    warnings.append({"key": key, "code": code, "message_vi": message_vi})


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _coerce(kind: str, value: Any, fdef: dict, warnings: list[dict],
            known_user_ids: Optional[set], known_department_ids: Optional[set]):
    """Return (ok, normalized_value). On failure a warning is already emitted."""
    key = fdef.get("key", "")
    label = fdef.get("label_vi") or key

    if kind in ("text", "long_text"):
        if not isinstance(value, str):
            _warn(warnings, key, "wrong_type", f"'{label}' phải là chuỗi văn bản")
            return False, None
        s = value.strip()
        cap = _max_len(kind)
        if len(s) > cap:
            _warn(warnings, key, "truncated", f"'{label}' dài quá {cap} ký tự — đã cắt bớt")
            s = s[:cap]
        return True, s

    if kind in ("number", "money"):
        if isinstance(value, bool):
            _warn(warnings, key, "wrong_type", f"'{label}' phải là số")
            return False, None
        try:
            n = float(value)
        except (TypeError, ValueError):
            _warn(warnings, key, "wrong_type", f"'{label}' phải là số")
            return False, None
        if kind == "money" and n < 0:
            _warn(warnings, key, "wrong_type", f"'{label}' không được âm")
            return False, None
        return True, n

    if kind == "date":
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return True, value.isoformat()
        if isinstance(value, str):
            try:
                return True, date.fromisoformat(value.strip()).isoformat()
            except ValueError:
                pass
        _warn(warnings, key, "wrong_type", f"'{label}' phải là ngày dạng YYYY-MM-DD")
        return False, None

    if kind in ("user", "department"):
        try:
            uid = str(UUID(str(value)))
        except (TypeError, ValueError):
            _warn(warnings, key, "wrong_type", f"'{label}' phải là một ID hợp lệ")
            return False, None
        known = known_user_ids if kind == "user" else known_department_ids
        if known is not None and uid not in {str(k) for k in known}:
            code = "unknown_user" if kind == "user" else "unknown_department"
            _warn(warnings, key, code, f"'{label}' không thuộc doanh nghiệp này")
            return False, None
        return True, uid

    if kind in ("select", "status"):
        options = fdef.get("options") or []
        if options and value not in options:
            _warn(warnings, key, "invalid_option",
                  f"'{label}' phải là một trong: {', '.join(map(str, options))}")
            return False, None
        return True, value

    if kind == "link":
        link = _coerce_link(value)
        if link is None:
            _warn(warnings, key, "wrong_type", f"'{label}' phải là link http(s)")
            return False, None
        return True, link

    # unknown kind in the schema — keep the raw value, flag the template
    _warn(warnings, key, "unknown_kind", f"Kiểu '{kind}' của '{label}' không được hỗ trợ")
    return True, value


def validate_metadata(
    schema: Any,
    values: Optional[dict],
    *,
    known_user_ids: Optional[set] = None,
    known_department_ids: Optional[set] = None,
) -> MetadataValidation:
    """Validate ``values`` against a template ``metadata_schema`` (list of
    field defs). Returns normalized values + completeness + warnings."""
    values = dict(values or {})
    warnings: list[dict] = []
    normalized: dict[str, Any] = {}
    missing_required: list[str] = []

    fdefs = [f for f in (schema if isinstance(schema, list) else [])
             if isinstance(f, dict) and f.get("key")]
    schema_keys = {f["key"] for f in fdefs}

    required_total = 0
    required_ok = 0

    for fdef in fdefs:
        key = fdef["key"]
        kind = str(fdef.get("kind", "text"))
        required = bool(fdef.get("required", False))
        if required:
            required_total += 1

        value = values.get(key)
        valid = False

        if not _is_blank(value):
            valid, coerced = _coerce(kind, value, fdef, warnings,
                                     known_user_ids, known_department_ids)
            if valid:
                normalized[key] = coerced

        if not valid and "default" in fdef and not _is_blank(fdef["default"]):
            dvalid, dval = _coerce(kind, fdef["default"], fdef, warnings,
                                   known_user_ids, known_department_ids)
            if dvalid:
                normalized[key] = dval
                valid = True

        if required:
            if valid:
                required_ok += 1
            else:
                missing_required.append(key)
                label = fdef.get("label_vi") or key
                _warn(warnings, key, "missing_required", f"'{label}' là trường bắt buộc")

    extra = {k: v for k, v in values.items() if k not in schema_keys and k != "_extra"}
    prior_extra = values.get("_extra")
    if isinstance(prior_extra, dict):
        extra = {**prior_extra, **extra}
    if extra:
        normalized["_extra"] = extra

    if required_total == 0:
        completeness = Decimal("1.0000")
    else:
        completeness = (Decimal(required_ok) / Decimal(required_total)).quantize(
            _Q4, rounding=ROUND_DOWN)

    return MetadataValidation(
        normalized=normalized,
        completeness=completeness,
        warnings=warnings,
        missing_required=missing_required,
    )


# ─── template draft sanitizer (AI dựng mẫu từ file — ADR-0042 P3) ──────
_WIDTH_PRESETS = (90, 160, 280, 420)


def _clean_columns(cols: Any, limit: int = 12) -> list[dict]:
    out: list[dict] = []
    if not isinstance(cols, list):
        return out
    for c in cols[:limit]:
        if not isinstance(c, dict) or not (c.get("key") or c.get("label_vi")):
            continue
        kind = str(c.get("kind", "text"))
        width = c.get("width")
        if isinstance(width, (int, float)) and not isinstance(width, bool):
            width = min(_WIDTH_PRESETS, key=lambda p: abs(p - int(width)))
        else:
            width = None
        out.append({
            "key": str(c.get("key") or c["label_vi"])[:40],
            "label_vi": str(c.get("label_vi") or c["key"])[:120],
            **({"label_en": str(c["label_en"])[:120]} if c.get("label_en") else {}),
            "kind": kind if kind in KINDS else "text",
            **({"options": [str(o)[:60] for o in c["options"][:20]]}
               if isinstance(c.get("options"), list) and c["options"] else {}),
            **({"width": width} if width else {}),
        })
    return out


def sanitize_template_draft(draft: Any) -> dict:
    """Ép bản nháp template do AI sinh về đúng khuôn: kind trong whitelist,
    width snap về mức chuẩn, giới hạn số field/mục/cột. AI đề xuất — hệ
    thống ép khuôn — người duyệt."""
    draft = draft if isinstance(draft, dict) else {}
    fields: list[dict] = []
    for f in (draft.get("metadata_schema") or [])[:10]:
        if not isinstance(f, dict) or not (f.get("key") or f.get("label_vi")):
            continue
        kind = str(f.get("kind", "text"))
        fields.append({
            "key": str(f.get("key") or f["label_vi"])[:40],
            "label_vi": str(f.get("label_vi") or f["key"])[:120],
            **({"label_en": str(f["label_en"])[:120]} if f.get("label_en") else {}),
            "kind": kind if kind in KINDS else "text",
            "required": bool(f.get("required", False)),
            **({"options": [str(o)[:60] for o in f["options"][:20]]}
               if isinstance(f.get("options"), list) and f["options"] else {}),
            **({"default": str(f["default"])[:60]} if f.get("default") else {}),
        })

    sections: list[dict] = []
    seen_keys: set[str] = set()
    for s in (draft.get("section_outline") or [])[:10]:
        if not isinstance(s, dict) or not (s.get("key") or s.get("heading_vi")):
            continue
        key = str(s.get("key") or s["heading_vi"])[:40]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        body_kind = str(s.get("body_kind", "prose"))
        columns = _clean_columns(s.get("columns"))
        sections.append({
            "key": key,
            "heading_vi": str(s.get("heading_vi") or key)[:300],
            **({"heading_en": str(s["heading_en"])[:300]} if s.get("heading_en") else {}),
            **({"icon": str(s["icon"])[:16]} if s.get("icon") else {}),
            **({"hint_vi": str(s["hint_vi"])[:500]} if s.get("hint_vi") else {}),
            "body_kind": body_kind if body_kind in ("prose", "table", "checklist") else "prose",
            **({"columns": columns} if columns and body_kind == "table" else {}),
        })

    return {
        "icon": str(draft.get("icon") or "📄")[:16],
        "description": str(draft.get("description") or "")[:600],
        "metadata_schema": fields,
        "section_outline": sections,
    }


# ─── authored-document content (ADR-0042 Phase 2, mig 140) ─────────────
_LINK_SCHEMES = ("http://", "https://")


def _coerce_link(value: Any) -> Optional[dict]:
    """A link cell/item is {"text","url"} with an http(s) URL — nothing else
    (no javascript:/data: smuggling into rendered pages)."""
    if not isinstance(value, dict):
        return None
    url = str(value.get("url") or "").strip()
    if not url.lower().startswith(_LINK_SCHEMES):
        return None
    text = str(value.get("text") or url).strip()
    return {"text": text[:300], "url": url[:2000]}


def validate_content(outline: Any, content: Any) -> MetadataValidation:
    """Validate an authored document's ``content`` against the template's
    ``section_outline`` (table sections carry ``columns``). Trust-first, same
    stance as validate_metadata: bad cells dropped + warning, unknown columns
    dropped + warning, custom sections (not in outline) allowed as prose.

    Returns MetadataValidation — ``normalized`` is ``{"sections": [...]}``;
    ``completeness`` is 1.0 (authored completeness lives in metadata, not body).
    """
    warnings: list[dict] = []
    out_sections: list[dict] = []

    outline_by_key = {
        s["key"]: s for s in (outline if isinstance(outline, list) else [])
        if isinstance(s, dict) and s.get("key")
    }
    sections = content.get("sections") if isinstance(content, dict) else None
    if not isinstance(sections, list):
        sections = []

    for sec in sections:
        if not isinstance(sec, dict) or not sec.get("key"):
            continue
        key = str(sec["key"])
        odef = outline_by_key.get(key)
        norm_sec: dict[str, Any] = {"key": key}

        for hk in ("heading_vi", "heading_en"):
            if sec.get(hk):
                norm_sec[hk] = str(sec[hk])[:300]

        body_md = sec.get("body_md")
        if isinstance(body_md, str) and body_md.strip():
            cap = int(os.getenv("KAORI_DOCMETA_MAX_LONG_TEXT_LEN", "20000"))
            if len(body_md) > cap:
                _warn(warnings, key, "truncated", f"Mục '{key}' dài quá {cap} ký tự — đã cắt bớt")
                body_md = body_md[:cap]
            norm_sec["body_md"] = body_md

        # links block (ngoài bảng) — mỗi item là một link hợp lệ
        links = sec.get("links")
        if isinstance(links, list):
            good = [l for l in (_coerce_link(x) for x in links) if l]
            if len(good) < len(links):
                _warn(warnings, key, "wrong_type", f"Mục '{key}' có link không hợp lệ — đã bỏ")
            if good:
                norm_sec["links"] = good

        # Bảng tự do: mục KHÔNG có trong outline (hoặc outline không khai cột)
        # được phép mang cột riêng trong content — sanitize kind về whitelist.
        inline_cols = sec.get("columns")
        if isinstance(inline_cols, list) and inline_cols:
            clean_cols = []
            for c in inline_cols[:20]:
                if not isinstance(c, dict) or not c.get("key"):
                    continue
                kind = str(c.get("kind", "text"))
                width = c.get("width")
                clean_cols.append({
                    "key": str(c["key"])[:40],
                    "label_vi": str(c.get("label_vi") or c["key"])[:120],
                    **({"label_en": str(c["label_en"])[:120]} if c.get("label_en") else {}),
                    "kind": kind if kind in KINDS else "text",
                    **({"options": [str(o)[:60] for o in c["options"][:20]]}
                       if isinstance(c.get("options"), list) else {}),
                    # độ rộng cột theo px — kẹp 40..1200
                    **({"width": max(40, min(1200, int(width)))}
                       if isinstance(width, (int, float)) and not isinstance(width, bool) else {}),
                })
            if clean_cols:
                norm_sec["columns"] = clean_cols

        rows = sec.get("rows")
        if isinstance(rows, list) and rows:
            columns = ((odef or {}).get("columns") or norm_sec.get("columns") or [])
            coldefs = {c["key"]: c for c in columns
                       if isinstance(c, dict) and c.get("key")}
            if not coldefs:
                _warn(warnings, key, "no_columns",
                      f"Mục '{key}' không phải dạng bảng trong mẫu — bỏ qua các dòng")
            else:
                norm_rows: list[dict] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    norm_row: dict[str, Any] = {}
                    for ck, cv in row.items():
                        cdef = coldefs.get(ck)
                        if cdef is None:
                            _warn(warnings, key, "unknown_column",
                                  f"Cột '{ck}' không có trong mẫu — đã bỏ")
                            continue
                        if _is_blank(cv):
                            continue
                        kind = str(cdef.get("kind", "text"))
                        if kind == "link":
                            link = _coerce_link(cv)
                            if link is None:
                                _warn(warnings, ck, "wrong_type",
                                      f"'{cdef.get('label_vi') or ck}' phải là link http(s)")
                                continue
                            norm_row[ck] = link
                        else:
                            ok, coerced = _coerce(kind, cv, cdef, warnings, None, None)
                            if ok:
                                norm_row[ck] = coerced
                    if norm_row:
                        norm_rows.append(norm_row)
                if norm_rows:
                    norm_sec["rows"] = norm_rows

        out_sections.append(norm_sec)

    return MetadataValidation(
        normalized={"sections": out_sections},
        completeness=Decimal("1.0000"),
        warnings=warnings,
        missing_required=[],
    )
