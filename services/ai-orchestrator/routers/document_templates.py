"""Doc-type templates + folder-as-page + typed metadata + index + insights
(ADR-0042 — Confluence-style document structure, mig 139).

Confluence mechanics served here:
* blueprint registry            → /document-templates CRUD (global seeds visible
  to every tenant via RLS; tenants write only their own)
* folder = nghiệp vụ page       → /document-folders/{id}/page (body_md + bound
  template + sample file), every save appends document_folder_version
  (page-version history; restore = new version, never rewrite — K-2 spirit)
* Page Properties               → PATCH /document-repository/{id}/metadata
  (validated by shared/doc_metadata.py — trust-first, degraded envelope)
* Page Properties Report        → GET /document-repository/index (generic:
  columns come from the template's metadata_schema)
* insight nhóm/folder           → /document-repository/insights (202 async job,
  reasoning/collection_insight.py — LLM off the request path)
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..reasoning.collection_insight import run_collection_insight
from ..reasoning.document_author import run_document_generation
from ..reasoning.template_author import ANALYZING_MARKER, run_template_analysis
from ..shared.db import acquire_for_tenant
from ..shared.doc_metadata import validate_content, validate_metadata

log = structlog.get_logger()
router = APIRouter()

_MAX_LIMIT = 500


def _j(v: Any, default: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return default
    return v if v is not None else default


# ─────────────────────────── models ─────────────────────────────────────
class TemplateCreate(BaseModel):
    type_key: str = Field(..., min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    name_vi: str = Field(..., min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=16)
    description: Optional[str] = None
    metadata_schema: list = Field(default_factory=list)
    section_outline: list = Field(default_factory=list)
    default_labels: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    approval_chain_id: Optional[UUID] = None
    clone_of: Optional[UUID] = None  # copy schema/outline from an existing (e.g. global) template


class TemplatePatch(BaseModel):
    name_vi: Optional[str] = Field(None, min_length=1, max_length=200)
    icon: Optional[str] = Field(None, max_length=16)
    description: Optional[str] = None
    metadata_schema: Optional[list] = None
    section_outline: Optional[list] = None
    default_labels: Optional[list[str]] = None
    requires_approval: Optional[bool] = None
    approval_chain_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class FolderPagePatch(BaseModel):
    """One save of the nghiệp vụ page — snapshot + version bump (Confluence)."""
    body_md: Optional[str] = None
    default_template_id: Optional[UUID] = None
    clear_template: bool = False
    sample_file_id: Optional[UUID] = None
    clear_sample: bool = False
    default_labels: Optional[list[str]] = None
    change_note: Optional[str] = Field(None, max_length=500)


class PageRestore(BaseModel):
    version_no: int = Field(..., ge=1)


class DocMetadataPatch(BaseModel):
    template_id: Optional[UUID] = None
    metadata: Optional[dict] = None
    labels: Optional[list[str]] = None


class InsightCreate(BaseModel):
    scope_kind: str = Field(..., pattern="^(group|folder)$")
    scope: dict = Field(default_factory=dict)


def _tpl_out(r) -> dict:
    return {
        "template_id": str(r["template_id"]), "external_ref": r["external_ref"],
        "enterprise_id": str(r["enterprise_id"]) if r["enterprise_id"] else None,
        "is_global": r["enterprise_id"] is None,
        "type_key": r["type_key"], "name_vi": r["name_vi"], "icon": r["icon"],
        "description": r["description"],
        "metadata_schema": _j(r["metadata_schema"], []),
        "section_outline": _j(r["section_outline"], []),
        "default_labels": list(r["default_labels"] or []),
        "requires_approval": r["requires_approval"],
        "approval_chain_id": str(r["approval_chain_id"]) if r["approval_chain_id"] else None,
        "is_active": r["is_active"],
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


_TPL_COLS = """template_id, external_ref, enterprise_id, type_key, name_vi, icon,
               description, metadata_schema, section_outline, default_labels,
               requires_approval, approval_chain_id, is_active, updated_at"""


# ─────────────────────────── templates CRUD ─────────────────────────────
@router.get("/document-templates")
async def list_templates(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    include_inactive: bool = Query(False),
):
    """Global seeds (enterprise_id NULL) + this tenant's templates — RLS filters."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT {_TPL_COLS} FROM document_type_template
                WHERE ($1 OR is_active)
                ORDER BY (enterprise_id IS NULL) DESC, name_vi""",
            include_inactive)
    return {"items": [_tpl_out(r) for r in rows]}


@router.get("/document-templates/{template_id}")
async def get_template(
    template_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        r = await conn.fetchrow(
            f"SELECT {_TPL_COLS} FROM document_type_template WHERE template_id = $1",
            template_id)
    if r is None:
        raise HTTPException(status_code=404, detail="template not found")
    return _tpl_out(r)


@router.post("/document-templates", status_code=201)
async def create_template(
    body: TemplateCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Create a tenant template. `clone_of` copies schema/outline from an
    existing visible template (the Confluence clone-a-blueprint flow)."""
    schema, outline, labels = body.metadata_schema, body.section_outline, body.default_labels
    async with acquire_for_tenant(x_enterprise_id) as conn:
        if body.clone_of is not None:
            src = await conn.fetchrow(
                """SELECT metadata_schema, section_outline, default_labels
                   FROM document_type_template WHERE template_id = $1""", body.clone_of)
            if src is None:
                raise HTTPException(status_code=404, detail="clone_of template not found")
            schema = schema or _j(src["metadata_schema"], [])
            outline = outline or _j(src["section_outline"], [])
            labels = labels or list(src["default_labels"] or [])
        try:
            r = await conn.fetchrow(
                f"""INSERT INTO document_type_template
                       (enterprise_id, department_id, type_key, name_vi, icon,
                        description, metadata_schema, section_outline, default_labels,
                        requires_approval, approval_chain_id, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9,
                           $10, $11, $12)
                   RETURNING {_TPL_COLS}""",
                x_enterprise_id, x_department_id, body.type_key, body.name_vi,
                body.icon, body.description,
                json.dumps(schema, ensure_ascii=False),
                json.dumps(outline, ensure_ascii=False),
                labels, body.requires_approval, body.approval_chain_id, x_user_id)
        except Exception as e:
            if "uq_doctpl_scope_key" in str(e):
                raise HTTPException(status_code=409,
                                    detail=f"Đã có mẫu với mã '{body.type_key}'")
            raise
    return _tpl_out(r)


@router.patch("/document-templates/{template_id}")
async def patch_template(
    body: TemplatePatch,
    template_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Edit a TENANT template. Globals are read-only here (clone to customize) —
    the RLS WITH CHECK refuses the write, surfaced as 403."""
    sets, args = [], []

    def _set(col: str, val, cast: str = ""):
        args.append(val)
        sets.append(f"{col} = ${len(args)}{cast}")

    if body.name_vi is not None: _set("name_vi", body.name_vi)
    if body.icon is not None: _set("icon", body.icon)
    if body.description is not None: _set("description", body.description)
    if body.metadata_schema is not None:
        _set("metadata_schema", json.dumps(body.metadata_schema, ensure_ascii=False), "::jsonb")
    if body.section_outline is not None:
        _set("section_outline", json.dumps(body.section_outline, ensure_ascii=False), "::jsonb")
    if body.default_labels is not None: _set("default_labels", body.default_labels)
    if body.requires_approval is not None: _set("requires_approval", body.requires_approval)
    if body.approval_chain_id is not None: _set("approval_chain_id", body.approval_chain_id)
    if body.is_active is not None: _set("is_active", body.is_active)
    if not sets:
        raise HTTPException(status_code=400, detail="empty update")

    args.append(template_id)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        exists = await conn.fetchrow(
            "SELECT enterprise_id FROM document_type_template WHERE template_id = $1",
            template_id)
        if exists is None:
            raise HTTPException(status_code=404, detail="template not found")
        if exists["enterprise_id"] is None:
            raise HTTPException(
                status_code=403,
                detail="Mẫu hệ thống chỉ đọc — hãy nhân bản (clone) để tùy chỉnh")
        r = await conn.fetchrow(
            f"""UPDATE document_type_template SET {', '.join(sets)}, updated_at = NOW()
                WHERE template_id = ${len(args)}
                RETURNING {_TPL_COLS}""", *args)
    return _tpl_out(r)


class TemplateFromFile(BaseModel):
    run_id: UUID
    name_vi: str = Field(..., min_length=1, max_length=200)
    type_key: Optional[str] = Field(None, min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")


@router.post("/document-templates/from-file", status_code=202)
async def create_template_from_file(
    body: TemplateFromFile,
    background_tasks: BackgroundTasks,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Dựng BẢN NHÁP mẫu từ một file đã upload (run_id của /api/v1/upload):
    AI nhận diện cấu trúc (mục/bảng/cột) → bản nháp is_active=FALSE — người
    dùng duyệt/sửa trong trình sửa Mẫu rồi kích hoạt. Poll GET template tới
    khi description hết marker '⏳'."""
    import re as _re
    type_key = body.type_key or (_re.sub(r"[^a-z0-9]+", "_",
                                          body.name_vi.lower().replace("đ", "d"))
                                  .strip("_")[:40] or "mau_tu_file")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        run_ok = await conn.fetchval(
            "SELECT 1 FROM pipeline_runs WHERE run_id = $1", body.run_id)
        if not run_ok:
            raise HTTPException(status_code=404, detail="upload run not found")
        try:
            r = await conn.fetchrow(
                f"""INSERT INTO document_type_template
                       (enterprise_id, department_id, type_key, name_vi, icon,
                        description, is_active, created_by)
                   VALUES ($1, $2, $3, $4, '📄', $5, FALSE, $6)
                   RETURNING {_TPL_COLS}""",
                x_enterprise_id, x_department_id, type_key, body.name_vi,
                ANALYZING_MARKER, x_user_id)
        except Exception as e:
            if "uq_doctpl_scope_key" in str(e):
                raise HTTPException(status_code=409,
                                    detail=f"Đã có mẫu với mã '{type_key}'")
            raise
    background_tasks.add_task(run_template_analysis, r["template_id"],
                              x_enterprise_id, body.run_id)
    return {"template_id": str(r["template_id"]), "status": "analyzing"}


# ─────────────────────── folder-as-page (nghiệp vụ page) ─────────────────
async def _effective_template(conn, folder_id: UUID) -> Optional[dict]:
    """Nearest ancestor (incl. self) whose default_template_id is set —
    Confluence-style inheritance down the page tree. Returns
    {template_id, provider_folder_id, provider_page_version, chain_labels}."""
    frow = await conn.fetchrow(
        "SELECT path FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL",
        folder_id)
    if frow is None:
        return None
    chain = await conn.fetch(
        """SELECT folder_id, default_template_id, default_labels, page_version
           FROM document_folder
           WHERE deleted_at IS NULL AND ($1 = path OR $1 LIKE path || '/%')
           ORDER BY length(path) DESC""",
        frow["path"])
    labels: list[str] = []
    for c in chain:
        for lb in (c["default_labels"] or []):
            if lb not in labels:
                labels.append(lb)
    for c in chain:
        if c["default_template_id"] is not None:
            return {"template_id": c["default_template_id"],
                    "provider_folder_id": c["folder_id"],
                    "provider_page_version": c["page_version"],
                    "chain_labels": labels}
    return {"template_id": None, "provider_folder_id": None,
            "provider_page_version": None, "chain_labels": labels}


@router.get("/document-folders/{folder_id}/page")
async def get_folder_page(
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """The folder's nghiệp vụ page: body + own/effective template + sample file."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        f = await conn.fetchrow(
            """SELECT folder_id, name_vi, path, body_md, default_template_id,
                      sample_file_id, default_labels, page_version, updated_at
               FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL""",
            folder_id)
        if f is None:
            raise HTTPException(status_code=404, detail="folder not found")
        eff = await _effective_template(conn, folder_id)
        tpl = None
        if eff and eff["template_id"]:
            trow = await conn.fetchrow(
                f"SELECT {_TPL_COLS} FROM document_type_template WHERE template_id = $1",
                eff["template_id"])
            tpl = _tpl_out(trow) if trow else None
    return {
        "folder_id": str(f["folder_id"]), "name_vi": f["name_vi"], "path": f["path"],
        "body_md": f["body_md"],
        "default_template_id": str(f["default_template_id"]) if f["default_template_id"] else None,
        "sample_file_id": str(f["sample_file_id"]) if f["sample_file_id"] else None,
        "default_labels": list(f["default_labels"] or []),
        "page_version": f["page_version"],
        "updated_at": f["updated_at"].isoformat() if f["updated_at"] else None,
        "effective_template": tpl,
        "effective_labels": eff["chain_labels"] if eff else [],
        "template_inherited_from": (
            str(eff["provider_folder_id"])
            if eff and eff["provider_folder_id"] and eff["provider_folder_id"] != f["folder_id"]
            else None),
    }


async def _apply_page_edit(conn, folder_id: UUID, enterprise_id: UUID, *,
                           body_md, template_id, clear_template, sample_file_id,
                           clear_sample, default_labels, change_note, edited_by):
    """Apply one page edit: UPDATE folder + append the post-edit snapshot as
    version page_version+1 (Confluence: version N = state after Nth save)."""
    f = await conn.fetchrow(
        """SELECT body_md, default_template_id, sample_file_id, default_labels, page_version
           FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL FOR UPDATE""",
        folder_id)
    if f is None:
        raise HTTPException(status_code=404, detail="folder not found")

    new_body = body_md if body_md is not None else f["body_md"]
    new_tpl = (None if clear_template
               else template_id if template_id is not None
               else f["default_template_id"])
    new_sample = (None if clear_sample
                  else sample_file_id if sample_file_id is not None
                  else f["sample_file_id"])
    new_labels = default_labels if default_labels is not None else list(f["default_labels"] or [])
    new_version = f["page_version"] + 1

    tpl_snapshot = None
    if new_tpl is not None:
        trow = await conn.fetchrow(
            """SELECT type_key, name_vi, metadata_schema, section_outline, default_labels
               FROM document_type_template WHERE template_id = $1""", new_tpl)
        if trow is None:
            raise HTTPException(status_code=404, detail="template not found")
        tpl_snapshot = json.dumps({
            "template_id": str(new_tpl), "type_key": trow["type_key"],
            "name_vi": trow["name_vi"],
            "metadata_schema": _j(trow["metadata_schema"], []),
            "section_outline": _j(trow["section_outline"], []),
            "default_labels": list(trow["default_labels"] or []),
        }, ensure_ascii=False)

    await conn.execute(
        """UPDATE document_folder
           SET body_md = $2, default_template_id = $3, sample_file_id = $4,
               default_labels = $5, page_version = $6, updated_at = NOW()
           WHERE folder_id = $1""",
        folder_id, new_body, new_tpl, new_sample, new_labels, new_version)
    await conn.execute(
        """INSERT INTO document_folder_version
               (folder_id, enterprise_id, version_no, body_md, template_snapshot,
                sample_file_id, edited_by, change_note)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)""",
        folder_id, enterprise_id, new_version, new_body, tpl_snapshot,
        new_sample, edited_by, change_note)
    return new_version


@router.patch("/document-folders/{folder_id}/page")
async def patch_folder_page(
    body: FolderPagePatch,
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Save the nghiệp vụ page. Every save appends a document_folder_version
    row (Confluence page versioning) — history is never rewritten."""
    if (body.body_md is None and body.default_template_id is None
            and not body.clear_template and body.sample_file_id is None
            and not body.clear_sample and body.default_labels is None):
        raise HTTPException(status_code=400, detail="empty update")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        new_version = await _apply_page_edit(
            conn, folder_id, x_enterprise_id,
            body_md=body.body_md, template_id=body.default_template_id,
            clear_template=body.clear_template, sample_file_id=body.sample_file_id,
            clear_sample=body.clear_sample, default_labels=body.default_labels,
            change_note=body.change_note, edited_by=x_user_id)
    return {"folder_id": str(folder_id), "page_version": new_version, "status": "saved"}


@router.get("/document-folders/{folder_id}/page/versions")
async def list_page_versions(
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    limit: int = Query(50, ge=1, le=_MAX_LIMIT),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT version_no, body_md, template_snapshot, sample_file_id,
                      edited_by, edited_at, change_note
               FROM document_folder_version
               WHERE folder_id = $1 ORDER BY version_no DESC LIMIT $2""",
            folder_id, limit)
    return {"items": [{
        "version_no": r["version_no"],
        "body_md": r["body_md"],
        "template_snapshot": _j(r["template_snapshot"], None),
        "sample_file_id": str(r["sample_file_id"]) if r["sample_file_id"] else None,
        "edited_by": str(r["edited_by"]) if r["edited_by"] else None,
        "edited_at": r["edited_at"].isoformat() if r["edited_at"] else None,
        "change_note": r["change_note"],
    } for r in rows]}


@router.post("/document-folders/{folder_id}/page/restore")
async def restore_page_version(
    body: PageRestore,
    folder_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Restore = apply an old snapshot as a NEW version (Confluence semantics —
    history stays intact, K-2 spirit)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        snap = await conn.fetchrow(
            """SELECT body_md, template_snapshot, sample_file_id
               FROM document_folder_version
               WHERE folder_id = $1 AND version_no = $2""",
            folder_id, body.version_no)
        if snap is None:
            raise HTTPException(status_code=404, detail="version not found")
        tpl = _j(snap["template_snapshot"], None)
        tpl_id = UUID(tpl["template_id"]) if tpl and tpl.get("template_id") else None
        new_version = await _apply_page_edit(
            conn, folder_id, x_enterprise_id,
            body_md=snap["body_md"], template_id=tpl_id, clear_template=tpl_id is None,
            sample_file_id=snap["sample_file_id"], clear_sample=snap["sample_file_id"] is None,
            default_labels=None,
            change_note=f"Khôi phục từ phiên bản {body.version_no}",
            edited_by=x_user_id)
    return {"folder_id": str(folder_id), "page_version": new_version,
            "restored_from": body.version_no, "status": "saved"}


# ─────────────────── doc metadata (Bước 2/3 của pipeline) ────────────────
@router.patch("/document-repository/{doc_id}/metadata")
async def patch_doc_metadata(
    body: DocMetadataPatch,
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Fill/edit a document's Page Properties. Validation is trust-first:
    warnings + completeness, never a hard block (Tenet 13)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        doc = await conn.fetchrow(
            """SELECT doc_id, folder_id, template_id, metadata, is_current, superseded_by
               FROM document_repository_file
               WHERE doc_id = $1 AND deleted_at IS NULL""", doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        # A same-name re-upload may have stacked a newer version while this
        # form was open (Confluence same-name rule) — follow the supersedes
        # chain so the properties always land on the CURRENT version.
        hops = 0
        while (doc is not None and not doc["is_current"]
               and doc["superseded_by"] is not None and hops < 50):
            doc = await conn.fetchrow(
                """SELECT doc_id, folder_id, template_id, metadata, is_current, superseded_by
                   FROM document_repository_file
                   WHERE doc_id = $1 AND deleted_at IS NULL""",
                doc["superseded_by"])
            hops += 1
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        doc_id = doc["doc_id"]

        template_id = body.template_id or doc["template_id"]
        provider_version = None
        if template_id is None:
            eff = await _effective_template(conn, doc["folder_id"])
            if eff and eff["template_id"]:
                template_id = eff["template_id"]
                provider_version = eff["provider_page_version"]

        schema: list = []
        if template_id is not None:
            trow = await conn.fetchrow(
                "SELECT metadata_schema FROM document_type_template WHERE template_id = $1",
                template_id)
            if trow is None:
                raise HTTPException(status_code=404, detail="template not found")
            schema = _j(trow["metadata_schema"], [])

        known_users = {
            str(r["user_id"]) for r in await conn.fetch(
                "SELECT user_id FROM enterprise_users WHERE enterprise_id = $1",
                x_enterprise_id)
        } or None

        merged = {**_j(doc["metadata"], {}), **(body.metadata or {})}
        result = validate_metadata(schema, merged, known_user_ids=known_users)

        r = await conn.fetchrow(
            """UPDATE document_repository_file
               SET template_id = $2, metadata = $3::jsonb, metadata_completeness = $4,
                   labels = COALESCE($5, labels),
                   validated_page_version = COALESCE($6, validated_page_version)
               WHERE doc_id = $1
               RETURNING doc_id, template_id, metadata, labels, metadata_completeness""",
            doc_id, template_id,
            json.dumps(result.normalized, ensure_ascii=False, default=str),
            result.completeness, body.labels, provider_version)

    return {
        "doc_id": str(r["doc_id"]),
        "template_id": str(r["template_id"]) if r["template_id"] else None,
        "metadata": _j(r["metadata"], {}),
        "labels": list(r["labels"] or []),
        "completeness": float(r["metadata_completeness"]) if r["metadata_completeness"] is not None else None,
        "missing_required": result.missing_required,
        "warnings": result.warnings,
    }


# ─────────────── index — the Page Properties Report ─────────────────────
@router.get("/document-repository/index")
async def documents_index(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    template_id: Optional[UUID] = Query(None),
    folder_id: Optional[UUID] = Query(None, description="subtree scope"),
    labels: Optional[str] = Query(None, description="comma-separated, ALL must match"),
    q: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    cursor: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
):
    """Generic auto-index: columns come from the template's metadata_schema, so
    editing a template instantly reshapes every index built on it."""
    conds = ["d.is_current", "d.deleted_at IS NULL"]
    args: list[Any] = []

    def _arg(v) -> str:
        args.append(v)
        return f"${len(args)}"

    if template_id is not None:
        conds.append(f"d.template_id = {_arg(template_id)}")
    if folder_id is not None:
        p = _arg(folder_id)
        conds.append(
            f"d.folder_id IN (SELECT c.folder_id FROM document_folder c "
            f"JOIN document_folder root ON root.folder_id = {p} "
            f"WHERE c.deleted_at IS NULL "
            f"AND (c.folder_id = root.folder_id OR c.path LIKE root.path || '/%'))")
    if labels:
        conds.append(f"d.labels @> {_arg([s.strip() for s in labels.split(',') if s.strip()])}::text[]")
    if q:
        conds.append(f"d.name_vi ILIKE '%' || {_arg(q)} || '%'")
    if date_from is not None:
        conds.append(f"COALESCE(d.doc_date, d.uploaded_at::date) >= {_arg(date_from)}")
    if date_to is not None:
        conds.append(f"COALESCE(d.doc_date, d.uploaded_at::date) <= {_arg(date_to)}")
    if cursor is not None:
        c = _arg(cursor)
        conds.append(
            f"(d.uploaded_at, d.doc_id) < "
            f"(SELECT uploaded_at, doc_id FROM document_repository_file WHERE doc_id = {c})")

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT d.doc_id, d.external_ref, d.name_vi, d.template_id, d.folder_id,
                       d.metadata, d.labels, d.metadata_completeness, d.doc_date,
                       d.period_kind, d.uploaded_at, d.version, f.path
                FROM document_repository_file d
                JOIN document_folder f ON f.folder_id = d.folder_id
                WHERE {' AND '.join(conds)}
                ORDER BY d.uploaded_at DESC, d.doc_id DESC
                LIMIT {limit + 1}""",
            *args)
        columns: list = []
        if template_id is not None:
            trow = await conn.fetchrow(
                "SELECT metadata_schema FROM document_type_template WHERE template_id = $1",
                template_id)
            columns = _j(trow["metadata_schema"], []) if trow else []

    items = rows[:limit]
    next_cursor = str(items[-1]["doc_id"]) if len(rows) > limit else None
    return {
        "columns": columns,
        "items": [{
            "doc_id": str(r["doc_id"]), "external_ref": r["external_ref"],
            "name_vi": r["name_vi"],
            "template_id": str(r["template_id"]) if r["template_id"] else None,
            "folder_id": str(r["folder_id"]), "path": r["path"],
            "metadata": _j(r["metadata"], {}),
            "labels": list(r["labels"] or []),
            "completeness": float(r["metadata_completeness"]) if r["metadata_completeness"] is not None else None,
            "doc_date": r["doc_date"].isoformat() if r["doc_date"] else None,
            "period_kind": r["period_kind"], "version": r["version"],
            "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
        } for r in items],
        "next_cursor": next_cursor,
    }


# ───────────── authored documents (ADR-0042 P2, mig 140) ────────────────
class AuthoredCreate(BaseModel):
    folder_id: UUID
    name_vi: str = Field(..., min_length=1, max_length=300)
    template_id: Optional[UUID] = None
    content: Optional[dict] = None
    generate_prompt: Optional[str] = Field(None, max_length=8000,
                                           description="Mô tả tài liệu + yêu cầu — AI soạn nháp")


class ContentPatch(BaseModel):
    content: dict
    change_note: Optional[str] = Field(None, max_length=500)


async def _resolve_doc_template(conn, folder_id: UUID, template_id: Optional[UUID]):
    """(template_id, outline, provider_page_version) — own value or folder chain."""
    provider_version = None
    if template_id is None:
        eff = await _effective_template(conn, folder_id)
        if eff and eff["template_id"]:
            template_id = eff["template_id"]
            provider_version = eff["provider_page_version"]
    outline: list = []
    if template_id is not None:
        trow = await conn.fetchrow(
            "SELECT section_outline FROM document_type_template WHERE template_id = $1",
            template_id)
        if trow is None:
            raise HTTPException(status_code=404, detail="template not found")
        outline = _j(trow["section_outline"], [])
    return template_id, outline, provider_version


@router.post("/document-repository/authored", status_code=201)
async def create_authored_document(
    body: AuthoredCreate,
    background_tasks: BackgroundTasks,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Tạo tài liệu soạn-trong-Kaori theo bộ khung mẫu. Với `generate_prompt`,
    AI (Qwen local) soạn nháp per-section off the request path — poll GET
    …/content tới khi status='active'."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        folder = await conn.fetchrow(
            """SELECT folder_id, department_id FROM document_folder
               WHERE folder_id = $1 AND deleted_at IS NULL""", body.folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail="folder not found")
        dup = await conn.fetchval(
            """SELECT 1 FROM document_repository_file
               WHERE folder_id = $1 AND name_vi = $2 AND is_current AND deleted_at IS NULL""",
            body.folder_id, body.name_vi)
        if dup:
            raise HTTPException(status_code=409,
                                detail="Đã có tài liệu cùng tên trong thư mục — mở tài liệu đó để sửa")

        template_id, outline, provider_version = await _resolve_doc_template(
            conn, body.folder_id, body.template_id)
        eff = await _effective_template(conn, body.folder_id)
        labels = eff["chain_labels"] if eff else []
        if template_id is not None:
            trow = await conn.fetchrow(
                "SELECT default_labels FROM document_type_template WHERE template_id = $1",
                template_id)
            for lb in ((trow["default_labels"] if trow else None) or []):
                if lb not in labels:
                    labels.append(lb)

        result = validate_content(outline, body.content or {"sections": []})
        status = "generating" if body.generate_prompt else "active"
        r = await conn.fetchrow(
            """INSERT INTO document_repository_file
                  (enterprise_id, department_id, folder_id, name_vi, doc_kind,
                   doc_type, content, template_id, labels, validated_page_version,
                   status, uploaded_by)
               VALUES ($1, $2, $3, $4, 'authored', 'kaori_doc', $5::jsonb,
                       $6, $7, $8, $9, $10)
               RETURNING doc_id, external_ref""",
            x_enterprise_id, x_department_id or folder["department_id"],
            body.folder_id, body.name_vi,
            json.dumps(result.normalized, ensure_ascii=False, default=str),
            template_id, labels, provider_version, status, x_user_id)

    if body.generate_prompt:
        background_tasks.add_task(
            run_document_generation, r["doc_id"], x_enterprise_id, body.generate_prompt)
    return {"doc_id": str(r["doc_id"]), "external_ref": r["external_ref"],
            "status": status, "warnings": result.warnings}


class RegeneratePrompt(BaseModel):
    generate_prompt: str = Field(..., min_length=1, max_length=8000)


@router.post("/document-repository/{doc_id}/regenerate", status_code=202)
async def regenerate_document(
    body: RegeneratePrompt,
    background_tasks: BackgroundTasks,
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Chạy lại AI soạn nháp cho một tài liệu authored (vd lần đầu LLM quá
    tải). Ghi đè content hiện tại của CHÍNH phiên bản này — muốn giữ bản cũ
    thì Lưu (stack version) trước."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        d = await conn.fetchrow(
            """SELECT doc_kind, is_current FROM document_repository_file
               WHERE doc_id = $1 AND deleted_at IS NULL""", doc_id)
        if d is None:
            raise HTTPException(status_code=404, detail="document not found")
        if d["doc_kind"] != "authored" or not d["is_current"]:
            raise HTTPException(status_code=409,
                                detail="Chỉ tài liệu soạn trong Kaori (bản hiện tại) mới AI soạn lại được")
        await conn.execute(
            "UPDATE document_repository_file SET status = 'generating' WHERE doc_id = $1",
            doc_id)
    background_tasks.add_task(run_document_generation, doc_id, x_enterprise_id,
                              body.generate_prompt)
    return {"doc_id": str(doc_id), "status": "generating"}


_DOC_CONTENT_COLS = """d.doc_id, d.name_vi, d.doc_kind, d.status, d.version,
                       d.is_current, d.superseded_by, d.content, d.template_id,
                       d.labels, d.metadata, d.metadata_completeness, d.folder_id,
                       d.change_reason, d.uploaded_at"""


@router.get("/document-repository/{doc_id}/content")
async def get_document_content(
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Nội dung tài liệu soạn (bất kỳ phiên bản nào) + outline của mẫu để
    FE render/sửa đúng cột."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        d = await conn.fetchrow(
            f"""SELECT {_DOC_CONTENT_COLS}, t.section_outline, t.metadata_schema,
                       t.name_vi AS tpl_name, t.icon AS tpl_icon
                FROM document_repository_file d
                LEFT JOIN document_type_template t ON t.template_id = d.template_id
                WHERE d.doc_id = $1 AND d.deleted_at IS NULL""", doc_id)
    if d is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {
        "doc_id": str(d["doc_id"]), "name_vi": d["name_vi"],
        "doc_kind": d["doc_kind"], "status": d["status"],
        "version": d["version"], "is_current": d["is_current"],
        "content": _j(d["content"], {"sections": []}),
        "template_id": str(d["template_id"]) if d["template_id"] else None,
        "template_name": d["tpl_name"], "template_icon": d["tpl_icon"],
        "section_outline": _j(d["section_outline"], []),
        "metadata_schema": _j(d["metadata_schema"], []),
        "labels": list(d["labels"] or []),
        "metadata": _j(d["metadata"], {}),
        "completeness": float(d["metadata_completeness"]) if d["metadata_completeness"] is not None else None,
        "folder_id": str(d["folder_id"]),
        "change_reason": d["change_reason"],
        "uploaded_at": d["uploaded_at"].isoformat() if d["uploaded_at"] else None,
    }


@router.patch("/document-repository/{doc_id}/content")
async def patch_document_content(
    body: ContentPatch,
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Lưu tài liệu soạn = TẠO PHIÊN BẢN MỚI (Confluence page semantics) —
    History Changes tự sinh từ chuỗi, không ghi đè lịch sử."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        d = await conn.fetchrow(
            """SELECT doc_id, folder_id, name_vi, doc_kind, template_id, metadata,
                      metadata_completeness, validated_page_version, labels,
                      doc_date, period_kind, version, is_current, superseded_by,
                      department_id
               FROM document_repository_file
               WHERE doc_id = $1 AND deleted_at IS NULL""", doc_id)
        if d is None:
            raise HTTPException(status_code=404, detail="document not found")
        hops = 0
        while d is not None and not d["is_current"] and d["superseded_by"] and hops < 50:
            d = await conn.fetchrow(
                """SELECT doc_id, folder_id, name_vi, doc_kind, template_id, metadata,
                          metadata_completeness, validated_page_version, labels,
                          doc_date, period_kind, version, is_current, superseded_by,
                          department_id
                   FROM document_repository_file
                   WHERE doc_id = $1 AND deleted_at IS NULL""", d["superseded_by"])
            hops += 1
        if d is None:
            raise HTTPException(status_code=404, detail="document not found")
        if d["doc_kind"] != "authored":
            raise HTTPException(status_code=409,
                                detail="Tài liệu file upload không sửa nội dung trực tiếp được")

        _, outline, _ = await _resolve_doc_template(conn, d["folder_id"], d["template_id"])
        result = validate_content(outline, body.content)

        new_id = await conn.fetchval(
            """INSERT INTO document_repository_file
                  (enterprise_id, department_id, folder_id, name_vi, doc_kind,
                   doc_type, content, template_id, metadata, metadata_completeness,
                   labels, validated_page_version, doc_date, period_kind,
                   version, supersedes, change_reason, uploaded_by)
               VALUES ($1, $2, $3, $4, 'authored', 'kaori_doc', $5::jsonb,
                       $6, COALESCE($7, '{}')::jsonb, $8, $9, $10, $11, $12,
                       $13, $14, $15, $16)
               RETURNING doc_id""",
            x_enterprise_id, d["department_id"], d["folder_id"], d["name_vi"],
            json.dumps(result.normalized, ensure_ascii=False, default=str),
            d["template_id"], d["metadata"], d["metadata_completeness"],
            list(d["labels"] or []), d["validated_page_version"],
            d["doc_date"], d["period_kind"],
            d["version"] + 1, d["doc_id"],
            body.change_note or "Cập nhật nội dung", x_user_id)
        await conn.execute(
            """UPDATE document_repository_file
               SET is_current = FALSE, superseded_by = $2 WHERE doc_id = $1""",
            d["doc_id"], new_id)
    return {"doc_id": str(new_id), "version": d["version"] + 1,
            "status": "saved", "warnings": result.warnings}


@router.get("/document-repository/{doc_id}/history")
async def get_document_history(
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """History Changes — TỰ SINH từ chuỗi phiên bản (không ai gõ tay):
    mọi phiên bản cùng (folder, name) của tài liệu này."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        d = await conn.fetchrow(
            """SELECT folder_id, name_vi FROM document_repository_file
               WHERE doc_id = $1 AND deleted_at IS NULL""", doc_id)
        if d is None:
            raise HTTPException(status_code=404, detail="document not found")
        rows = await conn.fetch(
            """SELECT doc_id, version, is_current, change_reason, uploaded_by, uploaded_at
               FROM document_repository_file
               WHERE folder_id = $1 AND name_vi = $2 AND deleted_at IS NULL
               ORDER BY version DESC""",
            d["folder_id"], d["name_vi"])
    return {"items": [{
        "doc_id": str(r["doc_id"]), "version": r["version"],
        "is_current": r["is_current"], "change_reason": r["change_reason"],
        "uploaded_by": str(r["uploaded_by"]) if r["uploaded_by"] else None,
        "uploaded_at": r["uploaded_at"].isoformat() if r["uploaded_at"] else None,
    } for r in rows]}


# ───────────── ghi chú tài liệu (mig 141 — Confluence page comments) ────
class NoteCreate(BaseModel):
    body_md: str = Field(..., min_length=1, max_length=8000)


@router.get("/document-repository/{doc_id}/notes")
async def list_notes(
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Ghi chú theo TÀI LIỆU (mọi phiên bản cùng folder+name) — lưu nội dung
    tạo version mới không được làm 'mất' ghi chú của bản trước."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        d = await conn.fetchrow(
            """SELECT folder_id, name_vi FROM document_repository_file
               WHERE doc_id = $1 AND deleted_at IS NULL""", doc_id)
        if d is None:
            raise HTTPException(status_code=404, detail="document not found")
        rows = await conn.fetch(
            """SELECT n.note_id, n.body_md, n.author_id, n.created_at
               FROM document_note n
               JOIN document_repository_file f ON f.doc_id = n.doc_id  -- tenant-filter-lint: allow
               WHERE f.folder_id = $1 AND f.name_vi = $2
                 AND n.deleted_at IS NULL
               ORDER BY n.created_at""",
            d["folder_id"], d["name_vi"])
    return {"items": [{
        "note_id": str(r["note_id"]), "body_md": r["body_md"],
        "author_id": str(r["author_id"]) if r["author_id"] else None,
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]}


@router.post("/document-repository/{doc_id}/notes", status_code=201)
async def create_note(
    body: NoteCreate,
    doc_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        ok = await conn.fetchval(
            """SELECT 1 FROM document_repository_file
               WHERE doc_id = $1 AND deleted_at IS NULL""", doc_id)
        if not ok:
            raise HTTPException(status_code=404, detail="document not found")
        r = await conn.fetchrow(
            """INSERT INTO document_note (enterprise_id, doc_id, body_md, author_id)
               VALUES ($1, $2, $3, $4)
               RETURNING note_id, created_at""",
            x_enterprise_id, doc_id, body.body_md.strip(), x_user_id)
    return {"note_id": str(r["note_id"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None}


@router.delete("/document-repository/{doc_id}/notes/{note_id}")
async def delete_note(
    doc_id: UUID = Path(...),
    note_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE document_note SET deleted_at = NOW()
               WHERE note_id = $1 AND doc_id = $2 AND deleted_at IS NULL
               RETURNING note_id""", note_id, doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="note not found")
    return {"status": "deleted"}


# ─────────────────────────── insights (async) ───────────────────────────
@router.post("/document-repository/insights", status_code=202)
async def create_insight(
    body: InsightCreate,
    background_tasks: BackgroundTasks,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Kick off a group/folder analysis. 202 + insight_id; poll the GET.
    Stats are deterministic; Qwen only synthesises (off the request path)."""
    if body.scope_kind == "folder" and not body.scope.get("folder_id"):
        raise HTTPException(status_code=400, detail="scope.folder_id required for folder insight")
    if body.scope_kind == "group" and not any(
            body.scope.get(k) for k in ("doc_ids", "template_id", "labels", "folder_id")):
        raise HTTPException(status_code=400,
                            detail="group scope needs doc_ids / template_id / labels / folder_id")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        r = await conn.fetchrow(
            """INSERT INTO document_collection_insight
                   (enterprise_id, department_id, scope_kind, scope, requested_by)
               VALUES ($1, $2, $3, $4::jsonb, $5)
               RETURNING insight_id, external_ref""",
            x_enterprise_id, x_department_id, body.scope_kind,
            json.dumps(body.scope, ensure_ascii=False, default=str), x_user_id)
    background_tasks.add_task(run_collection_insight, r["insight_id"], x_enterprise_id)
    return {"insight_id": str(r["insight_id"]), "external_ref": r["external_ref"],
            "status": "pending"}


def _insight_out(r) -> dict:
    return {
        "insight_id": str(r["insight_id"]), "external_ref": r["external_ref"],
        "scope_kind": r["scope_kind"], "scope": _j(r["scope"], {}),
        "status": r["status"], "doc_count": r["doc_count"], "model": r["model"],
        "stats": _j(r["stats"], {}), "summary": r["summary"],
        "findings": _j(r["findings"], []), "error": r["error"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
    }


_INS_COLS = """insight_id, external_ref, scope_kind, scope, status, doc_count,
               model, stats, summary, findings, error, created_at, completed_at"""


@router.get("/document-repository/insights")
async def list_insights(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    limit: int = Query(20, ge=1, le=_MAX_LIMIT),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT {_INS_COLS} FROM document_collection_insight
                ORDER BY created_at DESC LIMIT $1""", limit)
    return {"items": [_insight_out(r) for r in rows]}


@router.get("/document-repository/insights/{insight_id}")
async def get_insight(
    insight_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        r = await conn.fetchrow(
            f"SELECT {_INS_COLS} FROM document_collection_insight WHERE insight_id = $1",
            insight_id)
    if r is None:
        raise HTTPException(status_code=404, detail="insight not found")
    return _insight_out(r)
