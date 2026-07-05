"""Collection insight — phân tích một lát cắt tài liệu (nhóm / folder) (ADR-0042).

Deterministic-first (Tenet 1): stats are computed from typed metadata in SQL/
Python — counts, completeness, status distribution, per-date-field overdue,
timeline. The LLM (Qwen local, K-3 via llm_router) only SYNTHESISES over those
stats + a capped list of doc lines — never raw file bytes — and degrades to
stats-only when unavailable (Tenet 13).

Runs as a background task off the request path (LLM never unbounded in a
request — PR #258 stance). Doc cap env-configurable: ``KAORI_DOCINS_MAX_DOCS``.
"""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Optional
from uuid import UUID

import structlog

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()


def _max_docs() -> int:
    return int(os.getenv("KAORI_DOCINS_MAX_DOCS", "200"))


def _jload(v: Any, default: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return default
    return v if v is not None else default


async def _fetch_slice(conn, scope: dict) -> tuple[list[dict], bool]:
    """Resolve the slice descriptor into doc rows. Returns (docs, truncated)."""
    cap = _max_docs()
    conds = ["d.is_current", "d.deleted_at IS NULL"]
    args: list[Any] = []

    def _arg(v) -> str:
        args.append(v)
        return f"${len(args)}"

    if scope.get("doc_ids"):
        ids = [UUID(str(x)) for x in scope["doc_ids"]][: cap + 1]
        conds.append(f"d.doc_id = ANY({_arg(ids)}::uuid[])")
    if scope.get("folder_id"):
        p = _arg(UUID(str(scope["folder_id"])))
        conds.append(
            f"d.folder_id IN (SELECT c.folder_id FROM document_folder c "
            f"JOIN document_folder root ON root.folder_id = {p} "
            f"WHERE c.deleted_at IS NULL "
            f"AND (c.folder_id = root.folder_id OR c.path LIKE root.path || '/%'))")
    if scope.get("template_id"):
        conds.append(f"d.template_id = {_arg(UUID(str(scope['template_id'])))}")
    if scope.get("labels"):
        conds.append(f"d.labels @> {_arg(list(scope['labels']))}::text[]")
    if scope.get("date_from"):
        conds.append(
            f"COALESCE(d.doc_date, d.uploaded_at::date) >= {_arg(date.fromisoformat(str(scope['date_from'])))}")
    if scope.get("date_to"):
        conds.append(
            f"COALESCE(d.doc_date, d.uploaded_at::date) <= {_arg(date.fromisoformat(str(scope['date_to'])))}")

    rows = await conn.fetch(
        f"""SELECT d.doc_id, d.name_vi, d.template_id, d.metadata, d.labels,
                   d.metadata_completeness, d.doc_date, d.uploaded_at, d.status
            FROM document_repository_file d
            WHERE {' AND '.join(conds)}
            ORDER BY COALESCE(d.doc_date, d.uploaded_at::date) DESC, d.doc_id
            LIMIT {cap + 1}""",
        *args)
    truncated = len(rows) > cap
    return [dict(r) for r in rows[:cap]], truncated


async def _load_templates(conn, template_ids: set) -> dict:
    if not template_ids:
        return {}
    rows = await conn.fetch(
        """SELECT template_id, name_vi, metadata_schema FROM document_type_template
           WHERE template_id = ANY($1::uuid[])""",
        list(template_ids))
    return {str(r["template_id"]): {
        "name_vi": r["name_vi"],
        "metadata_schema": _jload(r["metadata_schema"], []),
    } for r in rows}


def compute_stats(docs: list[dict], templates: dict, truncated: bool) -> dict:
    """Pure aggregation over the slice — no LLM, no I/O."""
    today = date.today().isoformat()
    stats: dict[str, Any] = {"doc_count": len(docs), "truncated": truncated}

    by_template: dict[str, int] = {}
    by_label: dict[str, int] = {}
    by_month: dict[str, int] = {}
    completeness_vals: list[float] = []
    status_counts: dict[str, dict[str, int]] = {}
    overdue: dict[str, int] = {}

    for d in docs:
        tid = str(d["template_id"]) if d["template_id"] else "khong_mau"
        tname = templates.get(tid, {}).get("name_vi", "Chưa gán mẫu")
        by_template[tname] = by_template.get(tname, 0) + 1

        for lb in (d.get("labels") or []):
            by_label[lb] = by_label.get(lb, 0) + 1

        eff = d.get("doc_date") or (d["uploaded_at"].date() if d.get("uploaded_at") else None)
        if eff:
            key = eff.isoformat()[:7]
            by_month[key] = by_month.get(key, 0) + 1

        if d.get("metadata_completeness") is not None:
            completeness_vals.append(float(d["metadata_completeness"]))

        meta = _jload(d.get("metadata"), {})
        schema = templates.get(tid, {}).get("metadata_schema", [])
        for f in schema:
            if not isinstance(f, dict):
                continue
            kind, key = f.get("kind"), f.get("key")
            label = f.get("label_vi") or key
            val = meta.get(key)
            if kind == "status" and val:
                status_counts.setdefault(label, {})
                status_counts[label][str(val)] = status_counts[label].get(str(val), 0) + 1
            if kind == "date" and isinstance(val, str) and val < today:
                overdue[label] = overdue.get(label, 0) + 1

    stats["by_template"] = by_template
    stats["by_label"] = dict(sorted(by_label.items(), key=lambda x: -x[1])[:20])
    stats["by_month"] = dict(sorted(by_month.items()))
    stats["status_counts"] = status_counts
    stats["past_date_counts"] = overdue
    if completeness_vals:
        stats["completeness"] = {
            "avg": round(sum(completeness_vals) / len(completeness_vals), 4),
            "incomplete_count": sum(1 for c in completeness_vals if c < 1.0),
            "scored_count": len(completeness_vals),
        }
    stats["unscored_count"] = len(docs) - len(completeness_vals)
    return stats


_PROMPT = """Bạn là trợ lý phân tích kho tài liệu doanh nghiệp. Dưới đây là THỐNG KÊ \
đã tính sẵn về một nhóm tài liệu, kèm danh sách tài liệu (tên + thuộc tính chính). \
CHỈ dùng dữ liệu được cung cấp — tuyệt đối không bịa.

Trả về DUY NHẤT một JSON object dạng:
{{"summary": "<3-4 câu tiếng Việt: nhóm tài liệu này gồm gì, tình trạng chung>", \
"findings": [{{"title": "<phát hiện ngắn>", "detail": "<giải thích 1-2 câu, dẫn số liệu>"}}]}}

- findings: 2-5 điểm đáng chú ý (quá hạn, thiếu thông tin, dồn vào một tháng, trạng thái tồn đọng…).

THỐNG KÊ:
{stats}

TÀI LIỆU:
{docs}
"""


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


def _doc_lines(docs: list[dict], templates: dict, limit: int = 60) -> str:
    lines = []
    for d in docs[:limit]:
        meta = _jload(d.get("metadata"), {})
        bits = [f"{k}={v}" for k, v in list(meta.items())[:5] if k != "_extra" and v]
        eff = d.get("doc_date")
        lines.append(f"- {d['name_vi']}"
                     + (f" ({eff.isoformat()})" if eff else "")
                     + (f" [{'; '.join(bits)}]" if bits else ""))
    if len(docs) > limit:
        lines.append(f"… và {len(docs) - limit} tài liệu khác (đã gộp trong thống kê).")
    return "\n".join(lines) or "(trống)"


async def run_collection_insight(insight_id: UUID, enterprise_id: UUID) -> None:
    """Background job: pending → running → complete/failed."""
    try:
        async with acquire_for_tenant(enterprise_id) as conn:
            row = await conn.fetchrow(
                "SELECT scope FROM document_collection_insight WHERE insight_id = $1",
                insight_id)
            if row is None:
                return
            await conn.execute(
                "UPDATE document_collection_insight SET status = 'running' WHERE insight_id = $1",
                insight_id)
            scope = _jload(row["scope"], {})
            docs, truncated = await _fetch_slice(conn, scope)
            templates = await _load_templates(
                conn, {str(d["template_id"]) for d in docs if d["template_id"]})

        stats = compute_stats(docs, templates, truncated)
        summary, findings, model = "", [], "rules-only"
        if truncated:
            findings.append({
                "title": "Lát cắt vượt giới hạn phân tích",
                "detail": f"Chỉ {_max_docs()} tài liệu đầu được đưa vào thống kê "
                          f"(KAORI_DOCINS_MAX_DOCS) — kết quả là thống kê một phần.",
            })

        if docs:
            try:
                from ..engine.llm_router import llm_router
                raw = await llm_router.complete(
                    prompt=_PROMPT.format(
                        stats=json.dumps(stats, ensure_ascii=False, default=str),
                        docs=_doc_lines(docs, templates)),
                    task="document_collection_insight",
                    consent_external=False,       # K-4: metadata may carry PII → Qwen local
                    enterprise_id=str(enterprise_id),
                    run_id=None,
                    max_tokens=800,
                )
                out = _extract_json(raw or "")
                if out:
                    summary = (out.get("summary") or "").strip()
                    findings.extend([
                        {"title": str(f.get("title", "")), "detail": str(f.get("detail", ""))}
                        for f in (out.get("findings") or [])
                        if isinstance(f, dict) and f.get("title")])
                    model = "qwen2.5-local"
            except Exception as e:  # pragma: no cover — LLM degrade → stats-only
                log.warning("collection_insight.llm_failed",
                            insight_id=str(insight_id), error=str(e))

        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """UPDATE document_collection_insight
                   SET status = 'complete', doc_count = $2, model = $3,
                       stats = $4::jsonb, summary = $5, findings = $6::jsonb,
                       completed_at = NOW()
                   WHERE insight_id = $1""",
                insight_id, len(docs), model,
                json.dumps(stats, ensure_ascii=False, default=str),
                summary, json.dumps(findings, ensure_ascii=False))
        log.info("collection_insight.complete", insight_id=str(insight_id),
                 docs=len(docs), model=model)
    except Exception as e:  # pragma: no cover — background safety net (fail loud in row)
        log.exception("collection_insight.failed", insight_id=str(insight_id), error=str(e))
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """UPDATE document_collection_insight
                       SET status = 'failed', error = $2, completed_at = NOW()
                       WHERE insight_id = $1""",
                    insight_id, str(e)[:500])
        except Exception:
            pass
