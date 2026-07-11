"""ADR-0037 Tier-3 Phase 1 — Document Tree backend.

Sits beside workflow_builder.router (same /workflows/... namespace, no prefix):

  Requirement templates (builder-time):
    POST   /workflows/{wf}/nodes/{node}/doc-requirements
    GET    /workflows/{wf}/nodes/{node}/doc-requirements
    PUT    /doc-requirements/{requirement_id}
    DELETE /doc-requirements/{requirement_id}

  Document instances (run-time lifecycle):
    PATCH  /workflow-documents/{attachment_id}/classify     — set class + requirement
    POST   /workflow-documents/{attachment_id}/transition   — 7-state machine
    POST   /workflow-documents/{attachment_id}/new-version   — supersede with a new file

  Enriched tree:
    GET    /workflows/{wf}/document-tree                     — 3-tier input/output/reference

File bytes + bronze rows come from the data-pipeline upload path (X-Workflow-
Step-ID). This router owns CLASSIFICATION + STATUS + VERSION only — clean split.
K-1 RLS via acquire_for_tenant; K-12 (dept_id resolved from the workflow, never
from the client). The pure status machine lives in workflow_runtime/doc_status.py.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant
from ..shared.blob_store import get_blob_store, blob_key
from ..workflow_runtime import doc_status as ds
from ..reasoning.document_analyzer import analyze_document

log = structlog.get_logger()
router = APIRouter()

_CLASSES = ("input", "output", "reference")


# ─────────────────────────── models ───────────────────────────
class DocRequirementIn(BaseModel):
    doc_class: str = Field(..., description="input | output | reference")
    name_vi: str
    description: Optional[str] = None
    is_required: bool = True
    allowed_formats: Optional[list[str]] = None
    template_file_id: Optional[UUID] = None
    sort_order: int = 0
    # Mig 144 — mẫu tài liệu (Kho) mà slot tham chiếu
    doc_template_id: Optional[UUID] = None


class DocClassifyIn(BaseModel):
    doc_class: str
    requirement_id: Optional[UUID] = None
    notes: Optional[str] = None


class DocTransitionIn(BaseModel):
    to_status: str
    note: Optional[str] = None


class NewVersionIn(BaseModel):
    file_id: UUID
    change_reason: Optional[str] = None


# ─────────────────────────── helpers ───────────────────────────
async def _workflow_dept(conn, workflow_id: UUID) -> UUID:
    row = await conn.fetchrow(
        "SELECT department_id FROM workflows WHERE workflow_id = $1", workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return row["department_id"]


def build_document_tree(nodes: list[dict], requirements: list[dict],
                        documents: list[dict]) -> list[dict]:
    """Pure: assemble the 3-tier shape (node → {input,output,reference}) from flat
    rows. Each class bucket holds requirements with their fulfilling CURRENT
    document (+ the document's version chain length). Ad-hoc documents (no
    requirement) are appended as a synthetic requirement so nothing is hidden.

    Kept pure (no DB) so it is unit-testable and the SQL stays in the endpoint.
    """
    reqs_by_node: dict[str, list[dict]] = {}
    for r in requirements:
        reqs_by_node.setdefault(str(r["node_id"]), []).append(r)

    docs_by_req: dict[str, list[dict]] = {}
    docs_loose_by_node: dict[str, list[dict]] = {}
    for d in documents:
        rid = d.get("requirement_id")
        if rid:
            docs_by_req.setdefault(str(rid), []).append(d)
        else:
            docs_loose_by_node.setdefault(str(d["node_id"]), []).append(d)

    out = []
    for n in nodes:
        nid = str(n["node_id"])
        buckets = {"input": [], "output": [], "reference": []}
        for r in sorted(reqs_by_node.get(nid, []), key=lambda x: x.get("sort_order", 0)):
            cls = r["doc_class"] if r["doc_class"] in _CLASSES else "input"
            fulfilling = docs_by_req.get(str(r["requirement_id"]), [])
            current = next((x for x in fulfilling if x.get("is_current")), None)
            buckets[cls].append({
                "requirement_id": str(r["requirement_id"]),
                "name_vi": r["name_vi"],
                "description": r.get("description"),
                "is_required": r.get("is_required", True),
                "status": (current or {}).get("status", ds.CHO_NOP),
                "document": current,
                "version_count": len(fulfilling),
                # Mig 144 — mẫu tài liệu slot tham chiếu (hiển thị tại bước)
                "doc_template_id": (str(r["doc_template_id"])
                                    if r.get("doc_template_id") else None),
                "doc_template_name": r.get("doc_template_name"),
                "doc_template_icon": r.get("doc_template_icon"),
            })
        # Loose (ad-hoc) docs — surface under their own class, no requirement.
        for d in docs_loose_by_node.get(nid, []):
            cls = d.get("doc_class") if d.get("doc_class") in _CLASSES else "input"
            buckets[cls].append({
                "requirement_id": None,
                "name_vi": d.get("filename") or "Tài liệu",
                "description": None,
                "is_required": False,
                "status": d.get("status", ds.DA_NOP),
                "document": d,
                "version_count": 1,
            })
        out.append({
            "node_id": nid,
            "title": n.get("title_vi") or n.get("title"),
            "lane_name": n.get("lane_name"),
            "input": buckets["input"],
            "output": buckets["output"],
            "reference": buckets["reference"],
            "doc_count": sum(len(b) for b in buckets.values()),
        })
    return out


# ─────────────────────── requirement CRUD ───────────────────────
@router.post("/workflows/{workflow_id}/nodes/{node_id}/doc-requirements", status_code=201)
async def create_doc_requirement(
    body: DocRequirementIn,
    workflow_id: UUID = Path(...),
    node_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    if body.doc_class not in _CLASSES:
        raise HTTPException(status_code=400, detail=f"doc_class must be one of {_CLASSES}")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        dept = await _workflow_dept(conn, workflow_id)
        try:
            row = await conn.fetchrow(
                """INSERT INTO workflow_step_document_requirements
                       (workflow_id, node_id, enterprise_id, department_id, doc_class,
                        name_vi, description, is_required, allowed_formats,
                        template_file_id, sort_order, doc_template_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,
                           COALESCE($9, ARRAY['pdf','docx','xlsx','csv','jpg','png']),
                           $10,$11,$12)
                   RETURNING requirement_id""",
                workflow_id, node_id, x_enterprise_id, dept, body.doc_class,
                body.name_vi, body.description, body.is_required, body.allowed_formats,
                body.template_file_id, body.sort_order, body.doc_template_id,
            )
        except Exception as exc:  # noqa: BLE001 — unique (node,class,name) clash → 409
            if "uq_wsdr" in str(exc):
                raise HTTPException(status_code=409,
                                    detail="a requirement with this name + class already exists on this step")
            raise
    return {"requirement_id": str(row["requirement_id"])}


@router.get("/workflows/{workflow_id}/nodes/{node_id}/doc-requirements")
async def list_doc_requirements(
    workflow_id: UUID = Path(...),
    node_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT r.requirement_id, r.doc_class, r.name_vi, r.description,
                      r.is_required, r.allowed_formats, r.template_file_id,
                      r.sort_order, r.doc_template_id,
                      t.name_vi AS doc_template_name, t.icon AS doc_template_icon
               FROM workflow_step_document_requirements r
               LEFT JOIN document_type_template t ON t.template_id = r.doc_template_id
               WHERE r.node_id = $1
               ORDER BY r.doc_class, r.sort_order""",
            node_id,
        )
    return {"requirements": [
        {**dict(r), "requirement_id": str(r["requirement_id"]),
         "template_file_id": str(r["template_file_id"]) if r["template_file_id"] else None,
         "doc_template_id": str(r["doc_template_id"]) if r["doc_template_id"] else None}
        for r in rows
    ]}


@router.put("/doc-requirements/{requirement_id}")
async def update_doc_requirement(
    body: DocRequirementIn,
    requirement_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    if body.doc_class not in _CLASSES:
        raise HTTPException(status_code=400, detail=f"doc_class must be one of {_CLASSES}")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE workflow_step_document_requirements
               SET doc_class=$2, name_vi=$3, description=$4, is_required=$5,
                   allowed_formats=COALESCE($6, allowed_formats),
                   template_file_id=$7, sort_order=$8, doc_template_id=$9,
                   updated_at=NOW()
               WHERE requirement_id=$1
               RETURNING requirement_id""",
            requirement_id, body.doc_class, body.name_vi, body.description,
            body.is_required, body.allowed_formats, body.template_file_id, body.sort_order,
            body.doc_template_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    return {"requirement_id": str(requirement_id)}


@router.delete("/doc-requirements/{requirement_id}", status_code=204)
async def delete_doc_requirement(
    requirement_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            "DELETE FROM workflow_step_document_requirements WHERE requirement_id = $1",
            requirement_id,
        )
    return None


# ─────────────────── document instance lifecycle ───────────────────
@router.patch("/workflow-documents/{attachment_id}/classify")
async def classify_document(
    body: DocClassifyIn,
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Set the class + requirement on a freshly-uploaded attachment (the upload
    path created the row; this gives it meaning in the tree)."""
    if body.doc_class not in _CLASSES:
        raise HTTPException(status_code=400, detail=f"doc_class must be one of {_CLASSES}")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE workflow_step_documents
               SET doc_class=$2, requirement_id=$3,
                   notes=COALESCE($4, notes)
               WHERE attachment_id=$1
               RETURNING attachment_id, status""",
            attachment_id, body.doc_class, body.requirement_id, body.notes,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return {"attachment_id": str(attachment_id), "status": row["status"]}


@router.post("/workflow-documents/{attachment_id}/transition")
async def transition_document(
    body: DocTransitionIn,
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Advance a document through the 7-state machine. Reject / request-more
    require a note; approve/reject/request-more stamp the reviewer."""
    if body.to_status not in ds.ALL_STATES:
        raise HTTPException(status_code=400, detail="unknown status")
    if ds.requires_note(body.to_status) and not (body.note and body.note.strip()):
        raise HTTPException(status_code=400,
                            detail=f"'{ds.STATUS_LABEL[body.to_status]}' yêu cầu nhập lý do")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        cur = await conn.fetchrow(
            "SELECT status, department_id FROM workflow_step_documents WHERE attachment_id = $1",
            attachment_id)
        if cur is None:
            raise HTTPException(status_code=404, detail="document not found")
        # RBAC (ADR-0037): a review decision (approve/reject/request-more) needs
        # the 'approve' functional permission in the document's department. Opt-in
        # per dept — falls through where roles aren't configured.
        if ds.is_review_decision(body.to_status):
            from ..shared.rbac_guard import assert_permission
            await assert_permission(conn, user_id=x_user_id,
                                    department_id=cur["department_id"], action="approve")
        if not ds.can_transition(cur["status"], body.to_status):
            raise HTTPException(
                status_code=409,
                detail=f"không thể chuyển từ '{ds.STATUS_LABEL.get(cur['status'], cur['status'])}' "
                       f"sang '{ds.STATUS_LABEL[body.to_status]}'")
        is_review = ds.is_review_decision(body.to_status)
        await conn.execute(
            """UPDATE workflow_step_documents
               SET status=$2,
                   review_note=CASE WHEN $3 THEN $4 ELSE review_note END,
                   reviewed_by=CASE WHEN $3 THEN $5 ELSE reviewed_by END,
                   reviewed_at=CASE WHEN $3 THEN NOW() ELSE reviewed_at END
               WHERE attachment_id=$1""",
            attachment_id, body.to_status, is_review, body.note, x_user_id,
        )
    log.info("workflow.doc.transition", attachment_id=str(attachment_id),
             to=body.to_status, by=str(x_user_id) if x_user_id else None)
    return {"attachment_id": str(attachment_id), "status": body.to_status}


@router.post("/workflow-documents/{attachment_id}/new-version", status_code=201)
async def new_document_version(
    body: NewVersionIn,
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Register a new version (already-uploaded bronze file_id) that supersedes
    this document: the old row goes is_current=FALSE + superseded_by=new; the new
    row inherits class/requirement, version+1, status='da_nop' (re-review)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        old = await conn.fetchrow(
            """SELECT workflow_id, node_id, enterprise_id, department_id, doc_class,
                      requirement_id, document_kind, version
               FROM workflow_step_documents WHERE attachment_id = $1""",
            attachment_id)
        if old is None:
            raise HTTPException(status_code=404, detail="document not found")
        new = await conn.fetchrow(
            """INSERT INTO workflow_step_documents
                   (workflow_id, node_id, file_id, enterprise_id, department_id,
                    document_kind, doc_class, requirement_id, status, version,
                    supersedes, change_reason, is_current, uploaded_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'da_nop',$9,$10,$11,TRUE,$12)
               RETURNING attachment_id""",
            old["workflow_id"], old["node_id"], body.file_id, old["enterprise_id"],
            old["department_id"], old["document_kind"], old["doc_class"],
            old["requirement_id"], (old["version"] or 1) + 1, attachment_id,
            body.change_reason, x_user_id,
        )
        await conn.execute(
            """UPDATE workflow_step_documents
               SET is_current=FALSE, superseded_by=$2 WHERE attachment_id=$1""",
            attachment_id, new["attachment_id"],
        )
    return {"attachment_id": str(new["attachment_id"]),
            "version": (old["version"] or 1) + 1, "supersedes": str(attachment_id)}


# ─────────────────── analyze document → insight (Option 1) ──────────────
async def _run_doc_analysis(attachment_id: UUID, enterprise_id: UUID) -> None:
    """Background: read the extracted text, analyze, append a document_analysis row."""
    try:
        async with acquire_for_tenant(enterprise_id) as conn:
            row = await conn.fetchrow(
                """SELECT bf.metadata->>'docsage_text' AS text, pr.filename
                   FROM workflow_step_documents sd
                   JOIN bronze_files bf ON bf.file_id = sd.file_id   -- tenant-filter-lint: allow
                   LEFT JOIN pipeline_runs pr ON pr.run_id = bf.run_id  -- tenant-filter-lint: allow
                   WHERE sd.attachment_id = $1""",
                attachment_id)
            if row is None:
                return
            res = await analyze_document(
                text=row["text"] or "",
                filename=row["filename"] or "",
                enterprise_id=str(enterprise_id),
            )
            await conn.execute(
                """INSERT INTO document_analysis
                       (enterprise_id, attachment_id, model, summary, key_fields, risks)
                   VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)""",
                enterprise_id, attachment_id, res.model, res.summary,
                json.dumps(res.key_fields), json.dumps(res.risks))
        log.info("doc_analyze.stored", attachment_id=str(attachment_id),
                 model=res.model, risks=len(res.risks), fields=len(res.key_fields))
    except Exception as e:  # pragma: no cover - background safety net
        log.exception("doc_analyze.failed", attachment_id=str(attachment_id), error=str(e))


@router.post("/workflow-documents/{attachment_id}/analyze", status_code=202)
async def analyze_workflow_document(
    background_tasks: BackgroundTasks,
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Analyze an uploaded document (summary + key fields + risks). Async — the
    LLM runs off the request path; poll GET …/analysis for the result."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        ok = await conn.fetchrow(
            "SELECT 1 FROM workflow_step_documents WHERE attachment_id = $1", attachment_id)
    if ok is None:
        raise HTTPException(status_code=404, detail="document not found")
    background_tasks.add_task(_run_doc_analysis, attachment_id, x_enterprise_id)
    return {"status": "running"}


@router.get("/workflow-documents/{attachment_id}/analysis")
async def get_workflow_document_analysis(
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Latest analysis for a document, or {status:'never_run'}."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT analysis_id, model, summary, key_fields, risks, created_at
               FROM document_analysis
               WHERE attachment_id = $1
               ORDER BY created_at DESC LIMIT 1""",
            attachment_id)
    if row is None:
        return {"status": "never_run"}

    def _j(v, default):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return default
        return v if v is not None else default

    return {
        "status": "done",
        "analysis_id": str(row["analysis_id"]),
        "model": row["model"],
        "summary": row["summary"],
        "key_fields": _j(row["key_fields"], []),
        "risks": _j(row["risks"], []),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


# ─────────────────────── download bytes (Phase 0) ───────────────────────
_TABULAR_EXTS = {".csv", ".tsv", ".xlsx", ".xls"}


async def _cleanliness_narrative(verdict: dict, filename: str, enterprise_id: str) -> Optional[str]:
    """Qwen viết 2-3 câu nhận xét tiếng Việt về verdict — bounded + best-effort
    (LLM in request path must be bounded); verdict là của heuristics, LLM
    không quyết định."""
    import asyncio
    import os as _os

    from ..engine.llm_router import llm_router

    issues_txt = "; ".join(i["label"] for i in verdict["issues"][:6]) or "không phát hiện lỗi"
    prompt = (
        f"File bảng '{filename}' được chấm điểm sạch {verdict['score']:.2f}/1. "
        f"Các vấn đề: {issues_txt}. "
        "Viết 2 câu tiếng Việt cho người dùng doanh nghiệp: dữ liệu có dùng "
        "ngay được không và vì sao. Không markdown."
    )
    # FE api client cắt ở 30s — deadline ở đây phải NHỎ HƠN hẳn để verdict
    # (heuristics, tức thời) luôn về tới người dùng; model lạnh thì nhận xét
    # degrade còn None thay vì kéo sập cả response.
    timeout_s = float(_os.getenv("KAORI_DOC_CLEAN_LLM_TIMEOUT_S", "18"))
    return await asyncio.wait_for(
        llm_router.complete(prompt, task="doc_cleanliness",
                            enterprise_id=enterprise_id, max_tokens=80),
        timeout=timeout_s,
    )


async def cleanliness_payload(
    enterprise_id: UUID, sha256: str, filename: Optional[str],
) -> dict:
    """Verdict engine dùng chung — Cây tài liệu workflow VÀ Kho (ADR-0039,
    1 file 2 mặt nhìn). Heuristics tất định quyết định verdict; Qwen chỉ
    viết nhận xét (best-effort, bounded). Bẩn → 'run_pipeline'; sạch →
    'analyze'. Raise HTTPException 400/409 như endpoint gốc."""
    import io

    import pandas as pd

    from ..reasoning.doc_cleanliness import assess_cleanliness

    fname = (filename or "").lower()
    ext = next((e for e in _TABULAR_EXTS if fname.endswith(e)), None)
    if ext is None:
        raise HTTPException(
            status_code=400,
            detail="Kiểm tra sạch chỉ áp dụng cho file bảng (csv/tsv/xlsx/xls)")

    content = await get_blob_store().get(blob_key(str(enterprise_id), sha256))
    if content is None:
        raise HTTPException(status_code=409,
                            detail="file bytes chưa được lưu trữ cho tài liệu này")

    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            sep = "\t" if ext == ".tsv" else ","
            try:
                df = pd.read_csv(io.BytesIO(content), sep=sep, encoding="utf-8-sig", dtype=str)
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(content), sep=sep, encoding="cp1258", dtype=str)
    except Exception as exc:  # noqa: BLE001 — parse failure = not clean, not a 500
        log.warning("doc_cleanliness.parse_failed",
                    filename=filename, error=str(exc))
        return {
            "is_clean": False, "score": 0.0, "recommendation": "run_pipeline",
            "issues": [{"code": "parse_failed",
                        "label": "Không đọc được bảng — cần chuẩn hóa qua 5 bước",
                        "count": 0}],
            "narrative": None, "filename": filename, "row_count": 0,
        }

    verdict = assess_cleanliness(df)

    narrative: Optional[str] = None
    try:
        narrative = await _cleanliness_narrative(verdict, filename or "file",
                                                 str(enterprise_id))
    except Exception as exc:  # noqa: BLE001 — nhận xét là phụ, verdict là chính
        log.warning("doc_cleanliness.narrative_failed", error=str(exc))

    return {**verdict, "narrative": narrative,
            "filename": filename, "row_count": int(len(df))}


@router.post("/workflow-documents/{attachment_id}/cleanliness")
async def check_document_cleanliness(
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Chấm độ sạch một tài liệu BẢNG trong Cây tài liệu (demo AABW)."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT pr.file_sha256, pr.mime_type, pr.filename
               FROM workflow_step_documents sd
               JOIN bronze_files bf ON bf.file_id = sd.file_id  -- tenant-filter-lint: allow
               JOIN pipeline_runs pr ON pr.run_id = bf.run_id   -- tenant-filter-lint: allow
               WHERE sd.attachment_id = $1""",
            attachment_id)
    if row is None or not row["file_sha256"]:
        raise HTTPException(status_code=404, detail="document not found")
    return await cleanliness_payload(
        x_enterprise_id, row["file_sha256"], row["filename"])


@router.get("/workflow-documents/{attachment_id}/download")
async def download_document(
    attachment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Serve the raw file bytes for a workflow document (ADR-0037 Phase 0).
    Resolves attachment → bronze file → pipeline_runs (sha256 + mime), reads the
    content-addressed blob. RLS-scoped; the key uses the caller's enterprise."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT pr.file_sha256, pr.mime_type, pr.filename
               FROM workflow_step_documents sd
               JOIN bronze_files bf ON bf.file_id = sd.file_id  -- tenant-filter-lint: allow
               JOIN pipeline_runs pr ON pr.run_id = bf.run_id   -- tenant-filter-lint: allow
               WHERE sd.attachment_id = $1""",
            attachment_id)
    if row is None or not row["file_sha256"]:
        raise HTTPException(status_code=404, detail="document not found")
    content = await get_blob_store().get(blob_key(str(x_enterprise_id), row["file_sha256"]))
    if content is None:
        # Bytes not stored (uploaded before Phase 0, or storage backend empty).
        raise HTTPException(status_code=409,
                            detail="file bytes chưa được lưu trữ cho tài liệu này")
    fname = row["filename"] or f"{attachment_id}"
    return Response(
        content=content,
        media_type=row["mime_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# ─────────────────────── enriched tree ───────────────────────
@router.get("/workflows/{workflow_id}/document-tree")
async def get_document_tree(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """3-tier document tree: workflow → step → {input[], output[], reference[]},
    each requirement carrying its current document's status + version count."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow(
            "SELECT workflow_id, name, name_vi FROM workflows WHERE workflow_id = $1",
            workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        nodes = await conn.fetch(
            """SELECT node_id, title, title_vi, lane_name, sequence_order
               FROM workflow_nodes WHERE workflow_id = $1
               ORDER BY sequence_order, created_at""",
            workflow_id)
        reqs = await conn.fetch(
            """SELECT r.requirement_id, r.node_id, r.doc_class, r.name_vi,
                      r.description, r.is_required, r.sort_order,
                      r.doc_template_id,
                      t.name_vi AS doc_template_name, t.icon AS doc_template_icon
               FROM workflow_step_document_requirements r
               LEFT JOIN document_type_template t ON t.template_id = r.doc_template_id
               WHERE r.workflow_id = $1""",
            workflow_id)
        docs = await conn.fetch(
            """SELECT sd.attachment_id, sd.node_id, sd.requirement_id, sd.doc_class,
                      sd.status, sd.version, sd.is_current, sd.valid_until,
                      sd.uploaded_at, sd.reviewed_at, sd.review_note,
                      COALESCE(pr.filename, bf.sheet_name) AS filename,
                      COALESCE(pr.file_sha256, '') AS sha256
               FROM workflow_step_documents sd
               JOIN bronze_files bf ON bf.file_id = sd.file_id  -- tenant-filter-lint: allow
               LEFT JOIN pipeline_runs pr ON pr.run_id = bf.run_id  -- tenant-filter-lint: allow
               WHERE sd.workflow_id = $1
               ORDER BY sd.version DESC""",
            workflow_id)

    def _doc(d):
        return {
            "attachment_id": str(d["attachment_id"]),
            "filename": d["filename"], "sha256": d["sha256"],
            "status": d["status"], "version": d["version"],
            "is_current": d["is_current"], "doc_class": d["doc_class"],
            "requirement_id": str(d["requirement_id"]) if d["requirement_id"] else None,
            "node_id": str(d["node_id"]),
            "valid_until": d["valid_until"].isoformat() if d["valid_until"] else None,
            "reviewed_at": d["reviewed_at"].isoformat() if d["reviewed_at"] else None,
            "review_note": d["review_note"],
            "uploaded_at": d["uploaded_at"].isoformat() if d["uploaded_at"] else None,
        }

    tree = build_document_tree(
        [dict(n) for n in nodes],
        [dict(r) for r in reqs],
        [_doc(d) for d in docs],
    )
    return {
        "workflow_id": str(workflow_id),
        "name": wf["name_vi"] or wf["name"],
        "steps": tree,
    }
