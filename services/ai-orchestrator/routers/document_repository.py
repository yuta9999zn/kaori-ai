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
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT doc_id, external_ref, name_vi, doc_type, status, version,
                      storage_tier, valid_until, sha256, uploaded_at
               FROM document_repository_file
               WHERE folder_id = $1 AND is_current AND deleted_at IS NULL
                 AND ($2::uuid IS NULL OR
                      (name_vi, doc_id) > (SELECT name_vi, doc_id FROM document_repository_file WHERE doc_id = $2))
               ORDER BY name_vi, doc_id
               LIMIT $3""",
            folder_id, cursor, limit + 1)
    items = rows[:limit]
    next_cursor = str(items[-1]["doc_id"]) if len(rows) > limit else None
    return {"items": [{
        "doc_id": str(r["doc_id"]), "external_ref": r["external_ref"],
        "name_vi": r["name_vi"], "doc_type": r["doc_type"], "status": r["status"],
        "version": r["version"], "storage_tier": r["storage_tier"],
        "valid_until": r["valid_until"].isoformat() if r["valid_until"] else None,
        "sha256": r["sha256"],
        "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
    } for r in items], "next_cursor": next_cursor}


# ─────────────────────────── search ─────────────────────────────────────
@router.get("/document-repository/search")
async def search_repository(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    q: str = Query("", description="name substring"),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
):
    """Indexed search across the repository (name + type + status), not tree-walk."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT d.doc_id, d.name_vi, d.doc_type, d.status, d.folder_id, f.path
               FROM document_repository_file d
               JOIN document_folder f ON f.folder_id = d.folder_id
               WHERE d.is_current AND d.deleted_at IS NULL
                 AND ($1 = '' OR d.name_vi ILIKE '%' || $1 || '%')
                 AND ($2::text IS NULL OR d.doc_type = $2)
                 AND ($3::text IS NULL OR d.status = $3)
               ORDER BY d.name_vi
               LIMIT $4""",
            q, doc_type, status, limit)
    return {"items": [{
        "doc_id": str(r["doc_id"]), "name_vi": r["name_vi"], "doc_type": r["doc_type"],
        "status": r["status"], "folder_id": str(r["folder_id"]), "path": r["path"],
    } for r in rows]}
