"""Upload router — POST /upload, GET /upload/{run_id}/status"""
import hashlib
import uuid
from typing import Optional
from uuid import UUID

from fastapi import (APIRouter, BackgroundTasks, File, Header, HTTPException,
                     Path, UploadFile)
from fastapi.responses import JSONResponse

from pathlib import Path as _Path

from ..data_plane.bronze.ingestor import (MAX_FILE_SIZE_BYTES,
                                          SUPPORTED_EXTENSIONS, ingest_file)
from ..shared import kafka_producer as kafka
from ..shared.db import acquire_for_tenant, get_pool

router = APIRouter()


async def _safe_ingest(
    *, content: bytes, filename: str, run_id: str,
    enterprise_id: str, uploaded_by: str,
    department_id: Optional[str], branch_id: Optional[str], source_id: Optional[str],
) -> None:
    """BackgroundTask worker for the async (large-tabular) upload path.

    Runs the heavy Bronze ingest after the 202 response. On ANY failure, mark
    the run 'failed' (UPSERT — the row may or may not have been INSERTed yet)
    so the FE's status poll resolves instead of spinning forever. 'failed' rows
    are excluded from the idempotency partial-unique, so a failed UPSERT never
    collides on (enterprise_id, file_sha256)."""
    import structlog as _sl
    try:
        await ingest_file(
            content=content, filename=filename, run_id=run_id,
            enterprise_id=enterprise_id, uploaded_by=uploaded_by,
            db_pool=get_pool(), kafka_producer=kafka,
            department_id=department_id, branch_id=branch_id, source_id=source_id,
            workflow_step_id=None,
        )
    except Exception as e:  # noqa: BLE001 — background, must not crash silently
        _sl.get_logger().exception("upload.bg_failed", run_id=run_id, error=str(e))
        msg = str(e) if isinstance(e, ValueError) else "Xử lý upload thất bại"
        try:
            sha = hashlib.sha256(content).hexdigest()
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """INSERT INTO pipeline_runs
                         (run_id, enterprise_id, uploaded_by, filename,
                          original_size_bytes, file_sha256, mime_type, status, error_message)
                       VALUES ($1,$2,$3,$4,$5,$6,'application/octet-stream','failed',$7)
                       ON CONFLICT (run_id) DO UPDATE
                         SET status='failed', error_message=EXCLUDED.error_message,
                             updated_at=NOW()""",
                    UUID(run_id), UUID(enterprise_id), UUID(uploaded_by),
                    filename, len(content), sha, msg[:2000],
                )
        except Exception:  # noqa: BLE001
            _sl.get_logger().exception("upload.bg_mark_failed_failed", run_id=run_id)


@router.post("")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
    x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID"),
    x_branch_id: Optional[UUID] = Header(None, alias="X-Branch-ID"),
    x_source_id: Optional[UUID] = Header(None, alias="X-Source-ID"),
    x_workflow_step_id: Optional[UUID] = Header(None, alias="X-Workflow-Step-ID"),
    x_requirement_id: Optional[UUID] = Header(None, alias="X-Requirement-ID"),
    x_folder_id: Optional[UUID] = Header(None, alias="X-Folder-ID"),  # ADR-0039 DMS
    # Lựa chọn của user trên dialog nộp file: 'skip' = chỉ tải lên, không lưu
    # Kho; bỏ trống = bridge tự filing vào 'Hồ sơ quy trình/<workflow>'.
    x_repo_filing: Optional[str] = Header(None, alias="X-Repo-Filing"),
    # ADR-0042 P3 — upload một FILE MẪU chỉ để AI phân tích cấu trúc thành
    # template: đi đường sync (nhận unstructured + DocSage extract inline)
    # nhưng KHÔNG đính vào workflow/folder nào.
    x_template_analysis: Optional[str] = Header(None, alias="X-Template-Analysis"),
):
    """Upload a data file (Excel, CSV, ODS, ZIP, SQL).

    Two paths:
      • **Workflow-card attach** (X-Workflow-Step-ID set) → SYNCHRONOUS. These
        carry the required_document_types whitelist (must reject wrong-kind
        before the dedup short-circuit) and are typically small docs. Returns
        the full ingest result, as before.
      • **Basic data upload** (no X-Workflow-Step-ID) → ASYNC. A large workbook
        (parse + detect + Bronze write) can exceed the gateway timeout, so we
        return 202 {run_id, status:'uploading'} immediately and ingest in a
        BackgroundTask. Poll GET /upload/{run_id}/status until 'bronze_complete'
        / 'silver_complete' / 'unstructured_pending' / 'failed'.

    Idempotent (K-8): same file hash + enterprise → existing non-failed run_id
    is reused (async path checks before spawning; sync path checks inside
    ingest_file). Cross-tenant guard: a supplied ID not in the enterprise → 400.
    """
    # ---- Sync path: workflow-card attach OR file into the Document Repository
    # OR template-analysis upload (all accept unstructured docs + extraction inline) ----
    if x_workflow_step_id is not None or x_folder_id is not None or x_template_analysis:
        run_id = str(uuid.uuid4())
        try:
            return await ingest_file(
                file=file,
                run_id=run_id,
                enterprise_id=str(x_enterprise_id),
                uploaded_by=str(x_user_id),
                db_pool=get_pool(),
                kafka_producer=kafka,
                department_id=str(x_department_id) if x_department_id else None,
                branch_id=str(x_branch_id) if x_branch_id else None,
                source_id=str(x_source_id) if x_source_id else None,
                workflow_step_id=str(x_workflow_step_id) if x_workflow_step_id else None,
                requirement_id=str(x_requirement_id) if x_requirement_id else None,
                folder_id=str(x_folder_id) if x_folder_id else None,
                repo_filing=x_repo_filing,
            )
        except ValueError as e:
            # MinerU wire-in 2026-05-18 — surface workflow whitelist rejections
            # with the specific code so the FE renders the friendly VN copy.
            msg = str(e)
            if "chỉ chấp nhận các loại tài liệu" in msg or "required_document_types" in msg:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code":    "USR-ERR-DOC-TYPE-MISMATCH",
                        "message": msg,
                        "hint":    "Kiểm tra danh sách loại tài liệu cho bước này trên trình duyệt workflow.",
                    },
                )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            import structlog as _sl
            _sl.get_logger().exception("upload.failed", run_id=run_id, error=str(e))
            raise HTTPException(status_code=500, detail="Upload failed")

    # ---- Async path: read bytes now (the UploadFile stream closes once the
    # response is sent), validate cheaply (sync), dedup, then ingest in bg. ----
    content = await file.read()
    filename = file.filename or ""

    # Fast, synchronous gates so bad files fail immediately with 400 instead of
    # a 202-then-poll-then-failed round-trip. The basic upload path accepts only
    # TABULAR formats; unstructured docs (pdf/docx/…) go through a workflow card
    # (X-Workflow-Step-ID, the sync path above).
    ext = _Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext or '(none)'}. "
                   f"Accepted: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.",
        )
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {len(content) / 1024 / 1024:.1f}MB "
                   f"(max {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB).",
        )

    sha = hashlib.sha256(content).hexdigest()

    # K-8 dedup — mirrors idx_pipeline_runs_idempotent so a re-upload is
    # instant (FE just polls the existing run, already complete).
    async with acquire_for_tenant(x_enterprise_id) as conn:
        existing = await conn.fetchrow(
            """SELECT run_id, status FROM pipeline_runs
               WHERE enterprise_id = $1 AND file_sha256 = $2
                 AND status NOT IN ('failed', 'cancelled')
               ORDER BY created_at DESC LIMIT 1""",
            x_enterprise_id, sha,
        )
    if existing is not None:
        return JSONResponse(status_code=200, content={
            "run_id":       str(existing["run_id"]),
            "status":       existing["status"],
            "is_duplicate": True,
        })

    run_id = str(uuid.uuid4())
    background_tasks.add_task(
        _safe_ingest,
        content=content, filename=filename, run_id=run_id,
        enterprise_id=str(x_enterprise_id), uploaded_by=str(x_user_id),
        department_id=str(x_department_id) if x_department_id else None,
        branch_id=str(x_branch_id) if x_branch_id else None,
        source_id=str(x_source_id) if x_source_id else None,
    )
    return JSONResponse(status_code=202, content={"run_id": run_id, "status": "uploading"})


@router.get("/{run_id}/status")
async def get_upload_status(
    run_id: UUID = Path(..., description="Pipeline run UUID"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """
    Poll pipeline run status. Frontend polls every 2s until status =
    'bronze_complete' or 'failed'.

    Validation: malformed run_id or X-Enterprise-ID returns 422 from
    FastAPI's path/header parser before hitting the handler.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT run_id, status, filename, detected_language,
                      sheet_count, row_count_bronze, row_count_silver,
                      quality_score, quality_dimensions, error_message
               FROM pipeline_runs
               WHERE run_id = $1 AND enterprise_id = $2""",
            run_id, x_enterprise_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    result = dict(row)
    # asyncpg returns JSONB as str — parse so the FE doesn't have to.
    import json as _j
    if isinstance(result.get("quality_dimensions"), str):
        try:
            result["quality_dimensions"] = _j.loads(result["quality_dimensions"])
        except Exception:
            result["quality_dimensions"] = {}
    return result
