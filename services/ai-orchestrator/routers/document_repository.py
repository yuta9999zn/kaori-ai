"""Enterprise Document Repository / DMS (ADR-0039).

Enterprise-wide hierarchical document store (Năm → Quý → Loại hồ sơ), independent
of any workflow. Folders = adjacency (parent_id) + materialized slug `path`
(NOT ltree). Files reuse bronze_files (K-8). RLS K-1 + ABAC dept via
acquire_for_tenant. Lazy: children/files are fetched per folder, keyset-paginated
(§6 cursor convention) so we never return the whole tree.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()
router = APIRouter()

_NIL = "00000000-0000-0000-0000-000000000000"
_MAX_LIMIT = 500


def _slug(name: str) -> str:
    """VN-aware slug for the materialized path segment (ltree-free)."""
    s = (name or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "muc"


# ─────────────────────────── models ─────────────────────────────────────
class FolderCreate(BaseModel):
    name_vi: str = Field(..., min_length=1, max_length=200)
    parent_id: Optional[UUID] = None
    sort_order: int = 0


class FolderPatch(BaseModel):
    name_vi: Optional[str] = Field(None, min_length=1, max_length=200)
    sort_order: Optional[int] = None


_PERIOD_KINDS = ("day", "week", "month", "quarter", "year")


class FilePatch(BaseModel):
    """Mig 138 — business-date metadata. A daily report dated 30/06 can be
    uploaded on 02/07, so filters/timeline key off doc_date, not uploaded_at."""
    doc_date: Optional[date] = None
    period_kind: Optional[str] = Field(None, pattern="^(day|week|month|quarter|year)$")


def _dept(x_department_id: Optional[UUID]) -> str:
    return str(x_department_id) if x_department_id else _NIL


# ─────────────────────────── folders ────────────────────────────────────
@router.post("/document-folders", status_code=201)
async def create_folder(
    body: FolderCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID"),
):
    dept = _dept(x_department_id)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        parent_path = ""
        if body.parent_id is not None:
            prow = await conn.fetchrow(
                "SELECT path FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL",
                body.parent_id)
            if prow is None:
                raise HTTPException(status_code=404, detail="parent folder not found")
            parent_path = prow["path"]
        path = (parent_path + "/" if parent_path else "") + _slug(body.name_vi)
        try:
            row = await conn.fetchrow(
                """INSERT INTO document_folder
                       (enterprise_id, department_id, parent_id, path, name_vi, sort_order)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   RETURNING folder_id, external_ref, path""",
                x_enterprise_id, dept, body.parent_id, path, body.name_vi, body.sort_order)
        except Exception as e:
            if "uq_docfolder_sibling" in str(e):
                raise HTTPException(status_code=409, detail="Đã có thư mục cùng tên ở cấp này")
            raise
    return {"folder_id": str(row["folder_id"]), "external_ref": row["external_ref"],
            "path": row["path"], "name_vi": body.name_vi}


@router.get("/document-folders")
async def list_folders(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    parent_id: Optional[UUID] = Query(None, description="omit for root folders"),
    cursor: Optional[UUID] = Query(None),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
):
    """Direct child folders of `parent_id` (or root when omitted). Keyset-paginated."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT folder_id, external_ref, parent_id, path, name_vi, sort_order,
                      (SELECT COUNT(*) FROM document_folder c
                       WHERE c.parent_id = f.folder_id AND c.deleted_at IS NULL) AS child_count,
                      (SELECT COUNT(*) FROM document_repository_file d
                       WHERE d.folder_id = f.folder_id AND d.is_current AND d.deleted_at IS NULL) AS file_count
               FROM document_folder f
               WHERE parent_id IS NOT DISTINCT FROM $1
                 AND deleted_at IS NULL
                 AND ($2::uuid IS NULL OR
                      (name_vi, folder_id) > (SELECT name_vi, folder_id FROM document_folder WHERE folder_id = $2))
               ORDER BY name_vi, folder_id
               LIMIT $3""",
            parent_id, cursor, limit + 1)
    items = [dict(r) for r in rows[:limit]]
    next_cursor = str(items[-1]["folder_id"]) if len(rows) > limit else None
    return {"items": [{
        "folder_id": str(i["folder_id"]), "external_ref": i["external_ref"],
        "parent_id": str(i["parent_id"]) if i["parent_id"] else None,
        "path": i["path"], "name_vi": i["name_vi"], "sort_order": i["sort_order"],
        "child_count": i["child_count"], "file_count": i["file_count"],
    } for i in items], "next_cursor": next_cursor}


@router.get("/document-folders/{folder_id}/breadcrumb")
async def folder_breadcrumb(
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Ancestor chain root→folder (for the breadcrumb), derived from the slug path."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT path FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL", folder_id)
        if row is None:
            raise HTTPException(status_code=404, detail="folder not found")
        # all ancestors share a path prefix; fetch them in one query
        crumbs = await conn.fetch(
            """SELECT folder_id, name_vi, path FROM document_folder
               WHERE enterprise_id = $1 AND deleted_at IS NULL
                 AND $2 LIKE path || '%'
               ORDER BY length(path)""",
            x_enterprise_id, row["path"])
    return {"items": [{"folder_id": str(c["folder_id"]), "name_vi": c["name_vi"]} for c in crumbs]}


@router.patch("/document-folders/{folder_id}")
async def patch_folder(
    body: FolderPatch,
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    sets, args = [], []
    if body.name_vi is not None:
        args.append(body.name_vi); sets.append(f"name_vi = ${len(args)}")
    if body.sort_order is not None:
        args.append(body.sort_order); sets.append(f"sort_order = ${len(args)}")
    if not sets:
        raise HTTPException(status_code=400, detail="empty update")
    args.append(folder_id)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            f"UPDATE document_folder SET {', '.join(sets)}, updated_at = NOW() "
            f"WHERE folder_id = ${len(args)} AND deleted_at IS NULL RETURNING folder_id", *args)
    if row is None:
        raise HTTPException(status_code=404, detail="folder not found")
    return {"folder_id": str(row["folder_id"]), "status": "updated"}


@router.delete("/document-folders/{folder_id}")
async def delete_folder(
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Soft-delete a folder + its subtree (legal/audit — never hard-delete)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT path FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL", folder_id)
        if row is None:
            raise HTTPException(status_code=404, detail="folder not found")
        n = await conn.execute(
            """UPDATE document_folder SET deleted_at = NOW()
               WHERE enterprise_id = $1 AND deleted_at IS NULL
                 AND (folder_id = $2 OR path LIKE $3 || '/%')""",
            x_enterprise_id, folder_id, row["path"])
    return {"status": "deleted", "subtree": n}


# ─────────────────────────── files in folder ────────────────────────────
@router.get("/document-folders/{folder_id}/files")
async def list_files(
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor: Optional[UUID] = Query(None),
    limit: int = Query(200, ge=1, le=_MAX_LIMIT),
    date_from: Optional[date] = Query(None, description="effective doc date >= (mig 138)"),
    date_to: Optional[date] = Query(None, description="effective doc date <="),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT doc_id, external_ref, name_vi, doc_type, status, version,
                      storage_tier, valid_until, sha256, uploaded_at,
                      doc_date, period_kind
               FROM document_repository_file
               WHERE folder_id = $1 AND is_current AND deleted_at IS NULL
                 AND ($2::uuid IS NULL OR
                      (name_vi, doc_id) > (SELECT name_vi, doc_id FROM document_repository_file WHERE doc_id = $2))
                 AND ($4::date IS NULL OR COALESCE(doc_date, uploaded_at::date) >= $4)
                 AND ($5::date IS NULL OR COALESCE(doc_date, uploaded_at::date) <= $5)
               ORDER BY name_vi, doc_id
               LIMIT $3""",
            folder_id, cursor, limit + 1, date_from, date_to)
    items = rows[:limit]
    next_cursor = str(items[-1]["doc_id"]) if len(rows) > limit else None
    return {"items": [_file_out(r) for r in items], "next_cursor": next_cursor}


def _file_out(r) -> dict:
    return {
        "doc_id": str(r["doc_id"]), "external_ref": r["external_ref"],
        "name_vi": r["name_vi"], "doc_type": r["doc_type"], "status": r["status"],
        "version": r["version"], "storage_tier": r["storage_tier"],
        "valid_until": r["valid_until"].isoformat() if r["valid_until"] else None,
        "sha256": r["sha256"],
        "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
        "doc_date": r["doc_date"].isoformat() if r["doc_date"] else None,
        "period_kind": r["period_kind"],
    }


@router.patch("/document-repository/{doc_id}")
async def patch_file_metadata(
    body: FilePatch,
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Set the business date / reporting period of a filed document (mig 138)."""
    if body.doc_date is None and body.period_kind is None:
        raise HTTPException(status_code=400, detail="nothing to update")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE document_repository_file
               SET doc_date    = COALESCE($2, doc_date),
                   period_kind = COALESCE($3, period_kind)
               WHERE doc_id = $1 AND deleted_at IS NULL
               RETURNING doc_id, external_ref, name_vi, doc_type, status, version,
                         storage_tier, valid_until, sha256, uploaded_at,
                         doc_date, period_kind""",
            doc_id, body.doc_date, body.period_kind)
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _file_out(row)


@router.get("/document-repository/timeline")
async def repository_timeline(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    granularity: str = Query("month", pattern="^(year|quarter|month|day)$"),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    quarter: Optional[int] = Query(None, ge=1, le=4),
    month: Optional[int] = Query(None, ge=1, le=12),
):
    """Virtual time tree (mig 138) — bucket counts over the EFFECTIVE date
    (COALESCE(doc_date, uploaded_at::date)). Time is metadata, not folders:
    the FE expands Năm → Quý → Tháng → Ngày by re-querying one level deeper.
    Weekly docs surface via their doc_date; period_kind stays a filter/badge."""
    parts = {
        "year":    "EXTRACT(YEAR FROM eff)::int",
        "quarter": "EXTRACT(QUARTER FROM eff)::int",
        "month":   "EXTRACT(MONTH FROM eff)::int",
        "day":     "EXTRACT(DAY FROM eff)::int",
    }
    levels = ["year", "quarter", "month", "day"]
    depth = levels.index(granularity)
    select_cols = ", ".join(f"{parts[l]} AS {l}" for l in levels[:depth + 1])
    group_cols = ", ".join(str(i + 2) for i in range(depth + 1))  # $-free ordinals

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT COUNT(*)::int AS doc_count, {select_cols}
                FROM (SELECT COALESCE(doc_date, uploaded_at::date) AS eff
                        FROM document_repository_file
                       WHERE is_current AND deleted_at IS NULL) t
                WHERE ($1::int IS NULL OR EXTRACT(YEAR FROM eff)::int = $1)
                  AND ($2::int IS NULL OR EXTRACT(QUARTER FROM eff)::int = $2)
                  AND ($3::int IS NULL OR EXTRACT(MONTH FROM eff)::int = $3)
                GROUP BY {group_cols}
                ORDER BY {group_cols}""",
            year, quarter, month)
    return {"granularity": granularity,
            "buckets": [dict(r) for r in rows]}


# ─────────────────────────── search ─────────────────────────────────────
@router.get("/document-repository/search")
async def search_repository(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    q: str = Query("", description="name substring"),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None, description="effective doc date >= (mig 138)"),
    date_to: Optional[date] = Query(None, description="effective doc date <="),
    period_kind: Optional[str] = Query(None, pattern="^(day|week|month|quarter|year)$"),
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
):
    """Indexed search across the repository (name + type + status + business
    date), not tree-walk. Date filters hit COALESCE(doc_date, uploaded_at) —
    a daily report dated 30/06 uploaded on 02/07 matches 30/06, not 02/07."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT d.doc_id, d.name_vi, d.doc_type, d.status, d.folder_id, f.path,
                      d.doc_date, d.period_kind, d.uploaded_at
               FROM document_repository_file d
               JOIN document_folder f ON f.folder_id = d.folder_id
               WHERE d.is_current AND d.deleted_at IS NULL
                 AND ($1 = '' OR d.name_vi ILIKE '%' || $1 || '%')
                 AND ($2::text IS NULL OR d.doc_type = $2)
                 AND ($3::text IS NULL OR d.status = $3)
                 AND ($4::date IS NULL OR COALESCE(d.doc_date, d.uploaded_at::date) >= $4)
                 AND ($5::date IS NULL OR COALESCE(d.doc_date, d.uploaded_at::date) <= $5)
                 AND ($6::text IS NULL OR d.period_kind = $6)
               ORDER BY d.name_vi
               LIMIT $7""",
            q, doc_type, status, date_from, date_to, period_kind, limit)
    return {"items": [{
        "doc_id": str(r["doc_id"]), "name_vi": r["name_vi"], "doc_type": r["doc_type"],
        "status": r["status"], "folder_id": str(r["folder_id"]), "path": r["path"],
        "doc_date": r["doc_date"].isoformat() if r["doc_date"] else None,
        "period_kind": r["period_kind"],
        "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
    } for r in rows]}
