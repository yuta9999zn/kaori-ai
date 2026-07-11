"""
Bronze Ingestor — wraps existing etl/ingest.py with multi-tenant support.

K-8: Idempotency via SHA-256 file fingerprint.
K-2: Bronze rows are append-only (enforced at DB level via RULE).
"""
import asyncio
import hashlib
import io
import json
import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Optional

import structlog
from datetime import datetime, timezone
from fastapi import UploadFile

# NB: ``from ...shared.db import acquire_for_tenant`` is intentionally
# NOT done at module scope. Some unit tests (test_unit_whitebox.py) import
# names from this file via ``from bronze.ingestor import ...`` — when the
# top-level package is ``bronze`` (not ``data_pipeline``), the relative
# parent ``..shared`` resolves outside the package and ImportError fires.
# Each function that needs the helper imports it lazily inside the body,
# mirroring the existing pattern for ``..shared.kafka_topics``.

log = structlog.get_logger()


def _publish_status(run_id: str, status: str, **extra) -> None:
    """F-NEW2 — fire a status-transition event for any open SSE subscriber.

    Best-effort: lazy-imports the bus so this module stays importable from
    bare ``import bronze.ingestor`` (test_unit_whitebox path) which can't
    resolve ``..shared.*``. No-ops when nobody is watching (constant-time)."""
    try:
        from ...shared.event_bus import event_bus  # package-style import
    except ImportError:
        try:
            from shared.event_bus import event_bus  # bare-import fallback
        except ImportError:
            return  # event bus not available in this context — skip
    payload = {"run_id": run_id, "status": status,
               "updated_at": datetime.now(timezone.utc).isoformat()}
    payload.update(extra)
    event_bus.publish(run_id, payload)

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".xlsb", ".xls", ".csv", ".tsv",
                        ".ods", ".zip", ".txt", ".sql"}
# Stage 6 placeholder — unstructured docs that we ACCEPT but don't parse
# until DocSage / Knowledge Extraction lands (P15-S11+). Today the
# ingestor registers a bronze_files metadata row + workflow_step_documents
# attachment so the FE can list the file on the workflow card; the actual
# bytes are NOT yet persisted to MinIO (Phase 1.5+ infra). The status
# 'unstructured_pending' makes the deferred state explicit.
UNSTRUCTURED_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg",
                           ".jpeg", ".tiff", ".webp", ".pptx", ".md"}
ALL_ACCEPTED_EXTENSIONS = SUPPORTED_EXTENSIONS | UNSTRUCTURED_EXTENSIONS
MAX_FILE_SIZE_BYTES = int(os.getenv("UPLOAD_MAX_SIZE_MB", 100)) * 1024 * 1024


# ADR-0039/0042 bridge — root folder Kho cho chứng từ nộp ở bước workflow.
# Env-configurable (không hardcode tùy tiện); nil-dept để mọi phòng thấy root.
_WF_REPO_ROOT = os.getenv("KAORI_WF_REPO_ROOT", "Hồ sơ quy trình")
_NIL_DEPT = "00000000-0000-0000-0000-000000000000"


def _slug(name: str) -> str:
    """VN-aware slug cho path segment — mirror của
    ai-orchestrator/routers/document_repository._slug (giữ 2 bản đồng bộ)."""
    s = (name or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "muc"


async def _ensure_workflow_repo_folder(
    conn, *, enterprise_id: str, workflow_name: str, department_id,
) -> str:
    """1 file 2 mặt nhìn — file nộp ở bước workflow cũng là tài liệu doanh
    nghiệp: resolve (tạo nếu thiếu) folder Kho '<root>/<tên quy trình>' để
    ``_file_into_repository`` filing luôn, không bắt user upload 2 lần.

    Race trên uq_docfolder_sibling → đọc lại (thua race là ổn, folder đã có).
    """
    # Ưu tiên folder TRÙNG TÊN workflow ở bất kỳ đâu trong Kho — user có thể
    # đã tự tổ chức folder theo nghiệp vụ (vd 'Kinh doanh/Thu mua nông sản
    # từ HTX'); có rồi thì lưu thẳng vào đó, không đẻ folder trùng.
    existing = await conn.fetchrow(
        """SELECT folder_id, path FROM document_folder
           WHERE enterprise_id = $1 AND name_vi = $2 AND deleted_at IS NULL
           ORDER BY length(path) LIMIT 1""",
        uuid.UUID(enterprise_id), workflow_name)
    if existing is not None:
        return str(existing["folder_id"])

    async def _get_or_create(parent_id, parent_path, name, dept):
        sel = ("SELECT folder_id, path FROM document_folder "
               "WHERE enterprise_id = $1 AND parent_id IS NOT DISTINCT FROM $2 "
               "AND name_vi = $3 AND deleted_at IS NULL")
        row = await conn.fetchrow(sel, uuid.UUID(enterprise_id), parent_id, name)
        if row is None:
            path = (parent_path + "/" if parent_path else "") + _slug(name)
            try:
                row = await conn.fetchrow(
                    """INSERT INTO document_folder
                           (enterprise_id, department_id, parent_id, path, name_vi)
                       VALUES ($1, $2, $3, $4, $5)
                       RETURNING folder_id, path""",
                    uuid.UUID(enterprise_id), dept, parent_id, path, name)
            except Exception:
                row = await conn.fetchrow(
                    sel, uuid.UUID(enterprise_id), parent_id, name)
                if row is None:
                    raise
        return row["folder_id"], row["path"]

    root_id, root_path = await _get_or_create(
        None, "", _WF_REPO_ROOT, uuid.UUID(_NIL_DEPT))
    wf_id, _ = await _get_or_create(
        root_id, root_path, workflow_name, department_id)
    return str(wf_id)


async def _file_into_repository(
    conn, *, folder_id: str, file_id, name_vi: str, doc_type: str,
    sha256: str, uploaded_by, department_id=None,
) -> None:
    """ADR-0042 — file an upload into the Document Repository with Confluence
    semantics (single writer for all three ingest branches):

    1. Identical bytes already current in this folder → skip (K-8 dedup).
    2. Same ``name_vi`` already current in the folder → stack as the next
       VERSION (Confluence same-name attachment rule): version+1, supersedes
       chain, metadata/template/labels carry over from the old version.
    3. Otherwise fresh insert inheriting the folder chain's template + labels
       (folder-as-page, mig 139) — nearest ancestor's template wins.

    Predicates carry explicit enterprise_id (self-sufficient under RLS —
    mirror of the pipeline_runs lesson at the tabular branch).
    """
    folder = await conn.fetchrow(
        """SELECT folder_id, enterprise_id, department_id, path
           FROM document_folder WHERE folder_id = $1 AND deleted_at IS NULL""",
        uuid.UUID(folder_id))
    if folder is None:
        log.warning("repo.file.folder_missing", folder_id=folder_id)
        return
    dept = department_id or folder["department_id"]

    dup = await conn.fetchval(
        """SELECT 1 FROM document_repository_file
           WHERE enterprise_id = $1 AND folder_id = $2 AND sha256 = $3
             AND is_current AND deleted_at IS NULL""",
        folder["enterprise_id"], folder["folder_id"], sha256)
    if dup:
        return

    # folder-as-page inheritance: labels union up the chain; nearest template wins
    chain = await conn.fetch(
        """SELECT default_template_id, default_labels, page_version
           FROM document_folder
           WHERE enterprise_id = $1 AND deleted_at IS NULL
             AND ($2 = path OR $2 LIKE path || '/%')
           ORDER BY length(path) DESC""",
        folder["enterprise_id"], folder["path"])
    template_id, page_version = None, None
    labels: list = []
    for c in chain:
        for lb in (c["default_labels"] or []):
            if lb not in labels:
                labels.append(lb)
        if template_id is None and c["default_template_id"] is not None:
            template_id = c["default_template_id"]
            page_version = c["page_version"]
    if template_id is not None:
        trow = await conn.fetchrow(
            """SELECT default_labels FROM document_type_template
               WHERE template_id = $1
                 AND (enterprise_id IS NULL OR enterprise_id = $2)""",
            template_id, folder["enterprise_id"])
        for lb in ((trow["default_labels"] if trow else None) or []):
            if lb not in labels:
                labels.append(lb)

    prev = await conn.fetchrow(
        """SELECT doc_id, version, template_id, metadata, labels,
                  metadata_completeness, validated_page_version, doc_date, period_kind
           FROM document_repository_file
           WHERE enterprise_id = $1 AND folder_id = $2 AND name_vi = $3
             AND is_current AND deleted_at IS NULL
           ORDER BY version DESC LIMIT 1""",
        folder["enterprise_id"], folder["folder_id"], name_vi)

    if prev is not None:
        # Confluence same-name-stacks: new bytes, same name → next version.
        new_id = await conn.fetchval(
            """INSERT INTO document_repository_file
                  (enterprise_id, department_id, folder_id, file_id, name_vi,
                   doc_type, sha256, uploaded_by, version, supersedes,
                   change_reason, template_id, metadata, labels,
                   metadata_completeness, validated_page_version, doc_date, period_kind)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                       $11, $12, COALESCE($13, '{}')::jsonb, $14, $15, $16, $17, $18)
               RETURNING doc_id""",
            folder["enterprise_id"], dept, folder["folder_id"], file_id, name_vi,
            doc_type, sha256, uploaded_by, prev["version"] + 1, prev["doc_id"],
            "Tải lên lại cùng tên — phiên bản mới",
            prev["template_id"], prev["metadata"], list(prev["labels"] or []),
            prev["metadata_completeness"], prev["validated_page_version"],
            prev["doc_date"], prev["period_kind"])
        await conn.execute(
            """UPDATE document_repository_file
               SET is_current = FALSE, superseded_by = $2
               WHERE doc_id = $1""",
            prev["doc_id"], new_id)
        log.info("repo.file.version_stacked", folder_id=folder_id,
                 name_vi=name_vi, version=prev["version"] + 1)
        return

    await conn.execute(
        """INSERT INTO document_repository_file
              (enterprise_id, department_id, folder_id, file_id, name_vi,
               doc_type, sha256, uploaded_by, template_id, labels,
               validated_page_version)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
        folder["enterprise_id"], dept, folder["folder_id"], file_id, name_vi,
        doc_type, sha256, uploaded_by, template_id, labels, page_version)


async def ingest_file(
    file: Optional[UploadFile] = None,
    run_id: str = "",
    enterprise_id: str = "",
    uploaded_by: str = "",
    db_pool=None,
    kafka_producer=None,
    department_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    source_id: Optional[str] = None,
    workflow_step_id: Optional[str] = None,
    # ADR-0037 Tier-3: when the upload fulfils a declared per-step document
    # requirement (📥/📤/📎), the FE passes its requirement_id so the resulting
    # workflow_step_documents row lands already classified + linked to the
    # requirement (status 'da_nop'), instead of as a loose ad-hoc attachment.
    requirement_id: Optional[str] = None,
    # ADR-0039 DMS — when the upload files into the enterprise Document
    # Repository, the FE passes the target folder; the ingested bronze file is
    # also registered as a document_repository_file row (reuse byte store + K-8).
    folder_id: Optional[str] = None,
    # X-Repo-Filing — user's choice on the nộp-file dialog: 'skip' = chỉ tải
    # lên (không lưu Kho); None/'auto' = bridge tự filing vào
    # 'Hồ sơ quy trình/<workflow>' khi không có folder_id tường minh.
    repo_filing: Optional[str] = None,
    # Async-upload support: the handler reads the file then runs this in a
    # BackgroundTask, where the UploadFile stream is already closed. Passing
    # the pre-read bytes + filename lets ingest run without a live stream.
    content: Optional[bytes] = None,
    filename: Optional[str] = None,
) -> dict:
    """Stage 1: Raw file → Bronze landing.

    1. Validate file type + size
    2. Compute SHA-256 (K-8: idempotency)
    3. Resolve branch/dept/source via org_resolver (defaults filled in)
    4. Check for existing run with same hash (skip if already processed)
    5. Stream parse with existing utils/excel_parser.py logic
    6. Write raw JSONB rows to bronze_rows (append-only) with attribution
    7. Auto-match a mapping_template by filename glob → returned to FE
    8. Emit Kafka event: pipeline.upload.received

    The returned dict carries `matched_template` when an active template
    matched on (enterprise, source, filename glob). FE uses it to pre-fill
    Stage 2C column mapping confirmation.
    """
    _fname = filename or (file.filename if file else "") or ""
    ext = Path(_fname).suffix.lower()
    if ext not in ALL_ACCEPTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {ext}. "
            f"Tabular: {', '.join(sorted(SUPPORTED_EXTENSIONS))}. "
            f"Unstructured (accepted but not yet auto-extracted): "
            f"{', '.join(sorted(UNSTRUCTURED_EXTENSIONS))}."
        )
    is_unstructured = ext in UNSTRUCTURED_EXTENSIONS

    # Read file content (chunked to avoid memory issues). When the caller
    # already read the bytes (async-upload BackgroundTask), reuse them.
    if content is None:
        content = await _read_chunked(file)

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large: {len(content) / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB)")

    # MinerU pattern wire-in 2026-05-18 — magic-byte-aware detection.
    # We keep the legacy `ext`-based gates above (back-compat) but
    # ALSO compute the typed DocumentType so the workflow whitelist
    # check below catches "wrong content type in correct ext" (e.g.
    # a renamed .pdf that's actually a Word doc inside).
    from ..silver.document_type import detect_document_type as _detect_dt
    detection = _detect_dt(
        content=content,
        mime_type=(file.content_type if file else None),
        filename=_fname,
    )
    log.info("pipeline.ingest.detected",
             run_id=run_id,
             ext=ext,
             detected_type=detection.document_type.value,
             confidence=detection.confidence,
             evidence=detection.evidence)

    sha256 = hashlib.sha256(content).hexdigest()

    # ADR-0037 Phase 0 — persist the raw BYTES so the Document Tree / Contract
    # modules can serve the file back. Content-addressed (enterprise/sha256) =
    # dedup (K-8). Best-effort: a storage blip must not fail the upload — the
    # row + parse still land; the byte fetch degrades.
    try:
        from data_pipeline.shared.blob_store import get_blob_store, blob_key
        await get_blob_store().put(
            blob_key(enterprise_id, sha256), content, content_type=_guess_mime(ext))
    except Exception as exc:  # noqa: BLE001
        log.warning("pipeline.ingest.blob_store_failed",
                    run_id=run_id, error=str(exc)[:160])

    log.info("pipeline.ingest.start",
             run_id=run_id,
             enterprise_id=enterprise_id,
             filename=_fname,
             size_bytes=len(content),
             sha256=sha256[:16] + "...")

    # K-8: Check idempotency. Migration 024 cutover — acquire_for_tenant
    # sets app.enterprise_id so pipeline_runs RLS resolves under
    # NOBYPASSRLS. The application-level WHERE enterprise_id stays for
    # belt-and-suspenders + lint-friendliness.
    from ...shared.db import acquire_for_tenant
    from ...shared.org_resolver import resolve_org_attribution, match_mapping_template
    workflow_step_row = None
    req_doc_class = None  # ADR-0037 Tier-3 — set from the fulfilled requirement
    async with acquire_for_tenant(enterprise_id) as conn:
        # P15-S11 Tuần 8 — workflow card attachment. Resolved BEFORE the
        # K-8 dedupe check so the required_document_types whitelist can
        # reject "wrong kind on this card" cleanly — even when the same
        # file was uploaded under a different card earlier (the dedupe
        # would otherwise short-circuit with status='duplicate' and
        # silently hide the kind mismatch from the user).
        if workflow_step_id is not None:
            # branch_id lives on workflows (mig 053), not workflow_nodes
            # (mig 053 + 058 — workflow_nodes carries dept-level scope only
            # because cards inherit branch from the parent workflow). Join
            # so the upload picks up the workflow's branch context when the
            # card itself doesn't have one.
            workflow_step_row = await conn.fetchrow(
                """SELECT n.node_id, n.workflow_id, n.department_id,
                          w.branch_id, w.workspace_id,
                          n.expected_mapping_template_id, n.title,
                          n.required_document_types,
                          COALESCE(w.name_vi, w.name) AS wf_name
                   FROM workflow_nodes n
                   JOIN workflows w ON w.workflow_id = n.workflow_id
                   WHERE n.node_id = $1 AND n.enterprise_id = $2""",
                uuid.UUID(workflow_step_id), uuid.UUID(enterprise_id),
            )
            if workflow_step_row is None:
                raise ValueError(
                    f"X-Workflow-Step-ID {workflow_step_id} does not belong to enterprise"
                )
            # Card's dept overrides explicit X-Department-ID if mismatch —
            # the card is the source of truth for attribution when caller
            # has chosen a workflow context.
            department_id = str(workflow_step_row["department_id"])
            if workflow_step_row["branch_id"] is not None and branch_id is None:
                branch_id = str(workflow_step_row["branch_id"])

            # ADR-0037 Tier-3 — if this upload fulfils a declared requirement,
            # resolve its doc_class from the requirement (RLS-scoped, must
            # belong to this node). Trust the DB for the class, never the
            # client (K-1/K-12). Stays None for ad-hoc (loose) attachments.
            req_doc_template = None  # mig 144 — mẫu tài liệu slot tham chiếu
            if requirement_id is not None:
                _rq = await conn.fetchrow(
                    """SELECT doc_class, doc_template_id
                       FROM workflow_step_document_requirements
                       WHERE requirement_id = $1 AND node_id = $2""",
                    uuid.UUID(requirement_id), workflow_step_row["node_id"],
                )
                if _rq is not None:
                    req_doc_class = _rq["doc_class"]
                    req_doc_template = _rq["doc_template_id"]
                else:
                    # Fail-soft: still ingest, just don't link the requirement.
                    requirement_id = None
                    log.warning(
                        "ingest.requirement_not_on_node",
                        node_id=str(workflow_step_row["node_id"]),
                    )

            # ADR-0039/0042 bridge — file nộp ở bước workflow tự filing vào
            # Kho, trừ khi caller đã chỉ định X-Folder-ID hoặc user chọn
            # 'Chỉ tải lên' (X-Repo-Filing: skip). Thứ tự chọn folder:
            #   1. slot gắn MẪU (mig 144) → folder đang gắn đúng mẫu đó;
            #   2. folder TRÙNG TÊN workflow (user tự tổ chức);
            #   3. tự tạo 'Hồ sơ quy trình/<tên quy trình>'.
            # Fail-soft: lỗi ở đây không được chặn upload.
            if folder_id is None and (repo_filing or "auto") != "skip":
                try:
                    if req_doc_template is not None:
                        trow = await conn.fetchrow(
                            """SELECT folder_id FROM document_folder
                               WHERE enterprise_id = $1
                                 AND default_template_id = $2
                                 AND deleted_at IS NULL
                               ORDER BY length(path) LIMIT 1""",
                            uuid.UUID(enterprise_id), req_doc_template)
                        if trow is not None:
                            folder_id = str(trow["folder_id"])
                    if folder_id is None:
                        folder_id = await _ensure_workflow_repo_folder(
                            conn, enterprise_id=enterprise_id,
                            workflow_name=workflow_step_row["wf_name"] or "Quy trình",
                            department_id=workflow_step_row["department_id"])
                except Exception as exc:  # noqa: BLE001 — filing là phụ
                    log.warning("ingest.autofile_folder_failed", error=str(exc))

            # Stage 1.5 — workflow card declares which document kinds it
            # accepts via required_document_types[]. We enforce a whitelist
            # ONLY when the card has at least one required=True entry —
            # cards with an empty list (or only optional entries) stay
            # permissive so legacy uploads + ad-hoc attachments keep
            # working. The whitelist union: required + optional kinds.
            req_docs_raw = workflow_step_row["required_document_types"]
            req_docs = _coerce_required_docs(req_docs_raw)
            has_required = any(d.get("required") for d in req_docs)
            if has_required:
                allowed_kinds = {
                    _normalize_kind(d.get("kind", ""))
                    for d in req_docs if d.get("kind")
                }
                # MinerU pattern wire-in 2026-05-18 — detected kind is
                # AUTHORITATIVE; ext is fallback only when detection
                # returns UNKNOWN. Rationale: a renamed file
                # (invoice.xlsx → invoice.pdf) MUST fail when the card
                # wants pdf — otherwise the spoof attack succeeds.
                # Octet-stream uploads with no clear ext still work
                # because detected = correct via magic bytes.
                upload_kind_ext = _normalize_kind(ext.lstrip("."))
                upload_kind_detected = _normalize_kind(
                    _detected_kind(detection.document_type)
                )
                # If detection produced "unknown", fall back to ext.
                if upload_kind_detected == "unknown":
                    effective_kind = upload_kind_ext
                    decision_source = "ext_fallback"
                else:
                    effective_kind = upload_kind_detected
                    decision_source = "detected"

                if effective_kind not in allowed_kinds:
                    # Telemetry on the rejection path
                    log.info(
                        "pipeline.ingest.whitelist_reject",
                        run_id=run_id,
                        ext_kind=upload_kind_ext,
                        detected_kind=upload_kind_detected,
                        effective_kind=effective_kind,
                        decision_source=decision_source,
                        allowed_kinds=sorted(allowed_kinds),
                    )
                    raise ValueError(
                        f"Card '{workflow_step_row['title']}' chỉ chấp nhận "
                        f"các loại tài liệu: {', '.join(sorted(allowed_kinds))}. "
                        f"File anh upload đuôi '{ext}' (phát hiện nội dung: "
                        f"'{upload_kind_detected}') — không khớp. "
                        f"Đổi đuôi file hoặc cập nhật required_document_types "
                        f"trên card nếu loại mới được phép."
                    )
                # Telemetry when ext + detected disagree (potential spoof
                # that happened to pass because detected matched anyway).
                if upload_kind_ext and upload_kind_ext != upload_kind_detected \
                        and upload_kind_detected != "unknown":
                    log.warning(
                        "pipeline.ingest.kind_mismatch",
                        run_id=run_id,
                        ext_kind=upload_kind_ext,
                        detected_kind=upload_kind_detected,
                        detection_confidence=detection.confidence,
                        detection_evidence=detection.evidence,
                        accepted_via=decision_source,
                    )

        # K-8: idempotency check — only AFTER the workflow-card whitelist
        # has had a chance to reject. Same SHA + same enterprise → return
        # the existing run_id. Note: we also relink the existing
        # bronze_files to the new workflow card if one was given, so
        # re-attach across cards works without re-parsing the file.
        existing = await conn.fetchval(
            """SELECT run_id FROM pipeline_runs
               WHERE enterprise_id = $1 AND file_sha256 = $2
               AND status NOT IN ('failed', 'cancelled')
               LIMIT 1""",
            uuid.UUID(enterprise_id), sha256
        )
        if existing:
            log.info("pipeline.ingest.skip_duplicate", existing_run_id=str(existing))
            # Re-attach the existing bronze_files to the new workflow card
            # so the user's "re-upload to a different card" intent works.
            if workflow_step_row is not None:
                await conn.execute(
                    """INSERT INTO workflow_step_documents
                          (workflow_id, node_id, file_id, enterprise_id,
                           department_id, workspace_id, document_kind,
                           uploaded_by, uploaded_at, requirement_id, doc_class)
                       SELECT $1, $2, bf.file_id, bf.enterprise_id,
                              bf.department_id, $3, bf.file_format,
                              $4, NOW(), $7, $8
                         FROM bronze_files bf
                        WHERE bf.run_id = $5 AND bf.enterprise_id = $6
                       ON CONFLICT (workflow_id, node_id, file_id) DO NOTHING""",
                    workflow_step_row["workflow_id"],
                    workflow_step_row["node_id"],
                    workflow_step_row["workspace_id"],
                    uuid.UUID(uploaded_by),
                    existing,
                    uuid.UUID(enterprise_id),
                    uuid.UUID(requirement_id) if requirement_id else None,
                    req_doc_class,
                )
            if folder_id is not None:
                # ADR-0039/0042 — file the (deduped) existing bronze file into
                # the repo. A prose .txt run lands zero bronze_files rows →
                # file_id NULL; bytes serve from the sha256-keyed blob store.
                bf = await conn.fetchrow(
                    """SELECT file_id, department_id, file_format
                       FROM bronze_files
                       WHERE run_id = $1 AND enterprise_id = $2 LIMIT 1""",
                    existing, uuid.UUID(enterprise_id))
                await _file_into_repository(
                    conn, folder_id=folder_id,
                    file_id=bf["file_id"] if bf else None,
                    name_vi=_fname or "tài liệu",
                    doc_type=(bf["file_format"] if bf else None) or ext.lstrip("."),
                    sha256=sha256,
                    uploaded_by=uuid.UUID(uploaded_by) if uploaded_by else None,
                    department_id=bf["department_id"] if bf else None,
                )
            return {"run_id": str(existing), "status": "duplicate", "sha256": sha256}

        # P15-S11 Tuần 8 — resolve dept/branch/source. Defaults filled when
        # caller didn't supply (legacy clients + Pipeline Wizard pre-step-1).
        # Raises ValueError if any caller-supplied ID escapes the enterprise.
        org = await resolve_org_attribution(
            conn,
            enterprise_id,
            branch_id=branch_id,
            department_id=department_id,
            source_id=source_id,
        )

        # Create pipeline_run record. Unstructured uploads jump straight to
        # 'unstructured_pending' — no Bronze parsing today; the
        # status signals Stage 6 (DocSage) is the next gate. Tabular uploads
        # follow the normal status chain (uploading → bronze_complete → …).
        initial_status = (
            "unstructured_pending" if is_unstructured else "uploading"
        )
        await conn.execute(
            """INSERT INTO pipeline_runs
               (run_id, enterprise_id, uploaded_by, filename, original_size_bytes,
                file_sha256, mime_type, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            uuid.UUID(run_id),
            uuid.UUID(enterprise_id),
            uuid.UUID(uploaded_by),
            _fname,
            len(content),
            sha256,
            _guess_mime(ext),
            initial_status,
        )

        # Unstructured branch — register one bronze_files metadata row +
        # workflow_step_documents attachment, then run D2 Stage 6 text
        # extraction inline. PDF/DOCX parse is sub-second per file, so we
        # don't background it; FE gets the docsage_text + page_offsets in
        # the same response.
        if is_unstructured:
            # D2 — run extraction BEFORE the INSERT so bronze_files.metadata
            # is populated in one go. Extraction never raises; it returns
            # a status field instead.
            from data_pipeline.data_plane.silver.docsage_extract import (
                content_fingerprint as _docsage_fingerprint,
                extract_text as _docsage_extract,
            )
            extract = _docsage_extract(
                content=content,
                mime_type=_guess_mime(ext),
                filename=_fname or "",
            )

            # Phase 2.5 — OCR escape hatch. If pypdf/python-docx couldn't
            # handle the file (image PDF, image upload), try Qwen2.5-VL
            # via llm-gateway. Failure here is non-fatal — keeps the file
            # in `unstructured_pending` for manual queue or future retry.
            # K-4: gateway enforces local-only for OCR; em pass no
            # consent flag.
            ocr_text = ""
            ocr_status = ""
            if extract.status == "unsupported_today":
                from data_pipeline.data_plane.silver.ocr_client import (
                    is_ocr_candidate, ocr_image_to_text,
                )
                if is_ocr_candidate(mime_type=_guess_mime(ext), ext=ext):
                    ocr = await ocr_image_to_text(
                        content=content,
                        enterprise_id=enterprise_id,
                        mime_type=_guess_mime(ext),
                        ext=ext,
                    )
                    ocr_status = ocr.status
                    if ocr.status == "ok":
                        ocr_text = ocr.text
                        # Promote extract to look like a successful read
                        # so the downstream status logic + metadata fields
                        # treat it identically to a native-text doc.
                        extract = type(extract)(
                            text=ocr.text,
                            page_offsets=[0, len(ocr.text) + 1],
                            status="ok",
                            page_count=1,
                            char_count=len(ocr.text),
                        )

            # Status downgrade per extract.status:
            #   ok / partial      → silver_complete (queryable text landed)
            #   unsupported_today → unstructured_pending (waits on OCR /
            #                        manual)
            #   failed            → failed
            if extract.status in ("ok", "partial"):
                final_status = "silver_complete"
            elif extract.status == "unsupported_today":
                final_status = "unstructured_pending"
            else:
                final_status = "failed"

            file_id = uuid.uuid4()
            extraction_meta = {
                "unstructured":          True,
                "size_bytes":            len(content),
                "sha256":                sha256,
                "ext":                   ext,
                # D2 extraction result — DocSage (D3-D6) reads this.
                "docsage_text":          extract.text,
                "docsage_page_offsets":  extract.page_offsets,
                "docsage_status":        extract.status,
                "docsage_error":         extract.error_message,
                "docsage_page_count":    extract.page_count,
                "docsage_char_count":    extract.char_count,
                "docsage_fingerprint":   _docsage_fingerprint(
                    content, lib_version="pypdf-5.0.1|python-docx-1.1.2"
                ),
                "pending_stage": (
                    None
                    if extract.status in ("ok", "partial")
                    else "ocr_phase2" if extract.status == "unsupported_today"
                    else "extraction_failed"
                ),
                # Phase 2.5 OCR audit trail. Empty string when not attempted
                # (non-image, native-text PDF). 'ok' when Qwen2.5-VL filled
                # in for the upload; otherwise the failure reason routes the
                # file into the manual queue.
                "ocr_status":            ocr_status,
                "ocr_char_count":        len(ocr_text),
            }
            await conn.execute(
                """INSERT INTO bronze_files
                   (file_id, run_id, enterprise_id, sheet_name, sheet_index,
                    detected_purpose, detected_language, header_row,
                    row_count, col_count, file_format, metadata,
                    branch_id, department_id, source_id)
                   VALUES ($1, $2, $3, $4, 0, $5, NULL, 0,
                           0, 0, $6, $7::jsonb, $8, $9, $10)""",
                file_id,
                uuid.UUID(run_id),
                uuid.UUID(enterprise_id),
                _fname,
                "unstructured",
                ext.lstrip("."),
                json.dumps(extraction_meta, ensure_ascii=False),
                uuid.UUID(str(org["branch_id"])),
                uuid.UUID(str(org["department_id"])),
                uuid.UUID(str(org["source_id"])),
            )
            # Advance pipeline_runs.status now that extraction has landed.
            # Fail-loud (tenet #3): surface WHY a doc failed (e.g. corrupt PDF
            # "startxref not found") instead of a silent 'failed' with no reason.
            await conn.execute(
                "UPDATE pipeline_runs SET status = $1, error_message = $3, updated_at = NOW() WHERE run_id = $2",
                final_status, uuid.UUID(run_id),
                (extract.error_message or "Không trích xuất được nội dung tài liệu")
                if final_status == "failed" else None,
            )
            if workflow_step_row is not None:
                await conn.execute(
                    """INSERT INTO workflow_step_documents
                          (workflow_id, node_id, file_id, enterprise_id,
                           department_id, workspace_id, document_kind,
                           uploaded_by, uploaded_at, requirement_id, doc_class)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), $9, $10)
                       ON CONFLICT (workflow_id, node_id, file_id) DO NOTHING""",
                    workflow_step_row["workflow_id"],
                    workflow_step_row["node_id"],
                    file_id,
                    uuid.UUID(enterprise_id),
                    uuid.UUID(str(org["department_id"])),
                    workflow_step_row["workspace_id"],
                    ext.lstrip("."),
                    uuid.UUID(uploaded_by),
                    uuid.UUID(requirement_id) if requirement_id else None,
                    req_doc_class,
                )
            if folder_id is not None:
                # ADR-0039/0042 — register in the enterprise repository
                # (version-stacks on same name; inherits folder template/labels).
                await _file_into_repository(
                    conn, folder_id=folder_id, file_id=file_id,
                    name_vi=_fname or "tài liệu", doc_type=ext.lstrip("."),
                    sha256=sha256,
                    uploaded_by=uuid.UUID(uploaded_by) if uploaded_by else None,
                    department_id=uuid.UUID(str(org["department_id"])),
                )
            log.info("pipeline.ingest.unstructured_extracted",
                     run_id=run_id, filename=_fname, ext=ext,
                     workflow_step_id=workflow_step_id,
                     docsage_status=extract.status,
                     docsage_page_count=extract.page_count,
                     docsage_char_count=extract.char_count,
                     final_status=final_status)
            response = {
                "run_id":        run_id,
                "status":        final_status,
                "sha256":        sha256,
                "department_id": str(org["department_id"]),
                "branch_id":     str(org["branch_id"]),
                "source_id":     str(org["source_id"]),
                "kind":          "unstructured",
                "extension":     ext,
                "docsage": {
                    "status":      extract.status,
                    "page_count":  extract.page_count,
                    "char_count":  extract.char_count,
                    "error":       extract.error_message,
                },
                "note": (
                    f"Trích xuất thành công — {extract.char_count} ký tự, "
                    f"{extract.page_count} trang. DocSage QA sẵn sàng."
                    if extract.status == "ok" else
                    f"Trích xuất một phần — {extract.error_message}"
                    if extract.status == "partial" else
                    extract.error_message or "Trích xuất thất bại."
                ),
            }
            if workflow_step_row is not None:
                response["workflow_step_id"]    = str(workflow_step_row["node_id"])
                response["workflow_id"]         = str(workflow_step_row["workflow_id"])
                response["workflow_step_title"] = workflow_step_row["title"]
            return response

        # Auto-match mapping template — card's expected_mapping_template_id
        # wins if supplied (skips Stage 2C guessing); otherwise filename glob
        # under the resolved source.
        matched = None
        if workflow_step_row and workflow_step_row["expected_mapping_template_id"]:
            tpl_id = workflow_step_row["expected_mapping_template_id"]
            matched_row = await conn.fetchrow(
                """SELECT template_id, name, file_pattern, file_kind,
                          column_mapping, domain, confirmed_count, last_used_at
                   FROM mapping_templates
                   WHERE template_id = $1 AND enterprise_id = $2 AND is_active = TRUE""",
                tpl_id, uuid.UUID(enterprise_id),
            )
            if matched_row:
                matched = dict(matched_row)
        if matched is None:
            matched = await match_mapping_template(
                conn,
                enterprise_id,
                org["source_id"],
                _fname or "",
            )

    # Parse in background (don't block upload response). Attribution IDs
    # propagate so bronze_files + bronze_rows inserts carry them.
    asyncio.create_task(
        _parse_and_land(
            content, ext, run_id, enterprise_id, _fname,
            db_pool, kafka_producer,
            branch_id=str(org["branch_id"]),
            department_id=str(org["department_id"]),
            source_id=str(org["source_id"]),
            workflow_step_id=workflow_step_id,
            workflow_id=str(workflow_step_row["workflow_id"]) if workflow_step_row else None,
            workspace_id=str(workflow_step_row["workspace_id"]) if workflow_step_row else None,
            uploaded_by=uploaded_by,
            requirement_id=requirement_id,
            doc_class=req_doc_class,
            folder_id=folder_id,
        )
    )

    # Emit upload received event
    from ...shared import kafka_topics
    await kafka_producer.send_event(kafka_topics.PIPELINE_UPLOAD_RECEIVED, {
        "run_id": run_id,
        "enterprise_id": enterprise_id,
        "filename": _fname,
        "sha256": sha256,
        "size_bytes": len(content),
        "department_id": str(org["department_id"]),
        "branch_id": str(org["branch_id"]),
        "source_id": str(org["source_id"]),
        "workflow_step_id": workflow_step_id,
    })

    response = {
        "run_id":        run_id,
        "status":        "uploading",
        "sha256":        sha256,
        "department_id": str(org["department_id"]),
        "branch_id":     str(org["branch_id"]),
        "source_id":     str(org["source_id"]),
    }
    if workflow_step_row is not None:
        response["workflow_step_id"] = str(workflow_step_row["node_id"])
        response["workflow_id"] = str(workflow_step_row["workflow_id"])
        response["workflow_step_title"] = workflow_step_row["title"]
    if matched:
        response["matched_template"] = _serialize_matched_template(matched)
    return response


def _serialize_matched_template(row: dict) -> dict:
    """Convert asyncpg row (or dict) to JSON-safe payload for the FE."""
    last_used = row.get("last_used_at")
    return {
        "template_id":     str(row["template_id"]),
        "name":            row["name"],
        "file_pattern":    row["file_pattern"],
        "file_kind":       row["file_kind"],
        "column_mapping":  row["column_mapping"],
        "domain":          row.get("domain"),
        "confirmed_count": row.get("confirmed_count", 0),
        "last_used_at":    last_used.isoformat() if last_used else None,
    }


async def _parse_and_land(content: bytes, ext: str, run_id: str, enterprise_id: str,
                           filename: str, db_pool, kafka_producer,
                           branch_id: Optional[str] = None,
                           department_id: Optional[str] = None,
                           source_id: Optional[str] = None,
                           workflow_step_id: Optional[str] = None,
                           workflow_id: Optional[str] = None,
                           workspace_id: Optional[str] = None,
                           uploaded_by: Optional[str] = None,
                           requirement_id: Optional[str] = None,
                           doc_class: Optional[str] = None,
                           folder_id: Optional[str] = None):
    """Parse file using existing utils/excel_parser.py and land to bronze_rows.

    P15-S11 Tuần 8 — attribution columns (branch_id, department_id,
    source_id) propagate from the upload handler. The columns are
    NULLABLE during Build Week (see mig 047 TODO Tuần 8); when callers
    omit them the rows land without attribution and the FE falls back to
    showing them under "Unattributed" in the Data Explorer.
    """
    try:
        # Import existing Kaori ETL utilities
        from utils.excel_parser import ExcelParser

        parser = ExcelParser()
        sheets = parser.parse(io.BytesIO(content), filename=filename)

        total_rows = 0
        # Migration 024 cutover — INSERTs into bronze_files / bronze_rows
        # have to satisfy RLS WITH-CHECK under NOBYPASSRLS. acquire_for_tenant
        # sets app.enterprise_id so the policy resolves. The explicit
        # enterprise_id column in each INSERT VALUES list also stays —
        # makes the row tenant-correct independent of the GUC.
        from ...shared.db import acquire_for_tenant
        br_uuid   = uuid.UUID(branch_id)     if branch_id     else None
        dept_uuid = uuid.UUID(department_id) if department_id else None
        src_uuid  = uuid.UUID(source_id)     if source_id     else None
        first_file_id: Optional[str] = None
        async with acquire_for_tenant(enterprise_id) as conn:
            for sheet_idx, sheet_data in enumerate(sheets):
                file_id = str(uuid.uuid4())
                if first_file_id is None:
                    first_file_id = file_id
                await conn.execute(
                    """INSERT INTO bronze_files
                       (file_id, run_id, enterprise_id, sheet_name, sheet_index,
                        detected_purpose, detected_language, header_row,
                        row_count, col_count, file_format, metadata,
                        branch_id, department_id, source_id)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb,
                               $13, $14, $15)""",
                    uuid.UUID(file_id),
                    uuid.UUID(run_id),
                    uuid.UUID(enterprise_id),
                    sheet_data.get("sheet_name"),
                    sheet_idx,
                    sheet_data.get("purpose"),
                    sheet_data.get("language"),
                    sheet_data.get("header_row", 0),
                    len(sheet_data.get("rows", [])),
                    sheet_data.get("col_count", 0),
                    ext.lstrip("."),
                    '{}',
                    br_uuid,
                    dept_uuid,
                    src_uuid,
                )

                # P15-S11 Tuần 8 — workflow card attachment. When upload
                # routed through X-Workflow-Step-ID, link each bronze_file
                # to that card so the tree viewer can list it (mig 053).
                if workflow_step_id and workflow_id:
                    # workspace_id is NOT NULL on workflow_step_documents
                    # since mig 059 (workspace-scoped workflows). The
                    # value comes from the caller's workflows.workspace_id
                    # joined in ingest_file() above.
                    await conn.execute(
                        """INSERT INTO workflow_step_documents
                              (workflow_id, node_id, file_id, enterprise_id,
                               department_id, workspace_id, document_kind,
                               uploaded_by, uploaded_at, requirement_id, doc_class)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), $9, $10)
                           ON CONFLICT (workflow_id, node_id, file_id) DO NOTHING""",
                        uuid.UUID(workflow_id),
                        uuid.UUID(workflow_step_id),
                        uuid.UUID(file_id),
                        uuid.UUID(enterprise_id),
                        dept_uuid,
                        uuid.UUID(workspace_id) if workspace_id else None,
                        ext.lstrip("."),
                        uuid.UUID(uploaded_by) if uploaded_by else None,
                        uuid.UUID(requirement_id) if requirement_id else None,
                        doc_class,
                    )

                # Insert raw rows (K-2: append-only)
                rows = sheet_data.get("rows", [])
                for row_idx, row in enumerate(rows):
                    row_hash = hashlib.sha256(str(sorted(row.items())).encode()).hexdigest()
                    await conn.execute(
                        """INSERT INTO bronze_rows
                           (file_id, enterprise_id, row_index, raw_data, row_hash,
                            branch_id, department_id, source_id)
                           VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)""",
                        uuid.UUID(file_id),
                        uuid.UUID(enterprise_id),
                        row_idx,
                        json.dumps(row),
                        row_hash,
                        br_uuid,
                        dept_uuid,
                        src_uuid,
                    )
                total_rows += len(rows)

            # ADR-0039 DMS — a tabular file uploaded INTO a repository folder
            # (X-Folder-ID) is still an enterprise document (price list, SOP
            # in .txt, …). File it once per upload. file_id points at the
            # first bronze_files sheet when one landed; a prose .txt parses
            # to zero sheets → file_id NULL (column is nullable by design) —
            # download serves the original bytes from the sha256-keyed blob
            # store either way (K-8). Mirrors the unstructured-branch insert.
            if folder_id is not None:
                await _file_into_repository(
                    conn, folder_id=folder_id,
                    file_id=uuid.UUID(first_file_id) if first_file_id else None,
                    name_vi=filename or "tài liệu", doc_type=ext.lstrip("."),
                    sha256=hashlib.sha256(content).hexdigest(),
                    uploaded_by=uuid.UUID(uploaded_by) if uploaded_by else None,
                    department_id=dept_uuid,
                )

            # Update run status. Migration 024 cutover — bare db_pool.acquire()
            # in this branch does NOT set app.enterprise_id, so under NOBYPASSRLS
            # the RLS policy on pipeline_runs would silently update 0 rows when
            # filtering by run_id alone. Tightening to AND enterprise_id=$5
            # makes the predicate self-sufficient regardless of whether the
            # connection has a GUC set; mirrors the exception-handler fix
            # already in place at line ~213.
            detected_lang = sheets[0].get("language", "unknown") if sheets else "unknown"
            await conn.execute(
                """UPDATE pipeline_runs
                   SET status = 'bronze_complete', row_count_bronze = $1,
                       detected_language = $2, sheet_count = $3, updated_at = NOW()
                   WHERE run_id = $4 AND enterprise_id = $5""",
                total_rows, detected_lang, len(sheets),
                uuid.UUID(run_id), uuid.UUID(enterprise_id),
            )

        _publish_status(run_id, "bronze_complete",
                        row_count_bronze=total_rows,
                        sheet_count=len(sheets))

        from ...shared import kafka_topics
        # Gap 4 — when the upload is attached to a workflow step, include
        # the workflow/step/dept identifiers in the bronze_complete event
        # so the ai-orchestrator KPI handler can fire compute_kpi without
        # an extra round-trip to look them up by run_id.
        bronze_payload = {
            "run_id": run_id,
            "enterprise_id": enterprise_id,
            "row_count": total_rows,
            "detected_lang": detected_lang,
            "sheet_count": len(sheets),
        }
        if workflow_step_id and workflow_id:
            bronze_payload["workflow_id"]      = workflow_id
            bronze_payload["workflow_step_id"] = workflow_step_id
            if department_id:
                bronze_payload["department_id"] = department_id
            if branch_id:
                bronze_payload["branch_id"] = branch_id
            if uploaded_by:
                bronze_payload["uploaded_by"] = uploaded_by
        await kafka_producer.send_event(
            kafka_topics.PIPELINE_BRONZE_COMPLETE, bronze_payload,
        )

        # Log event names use snake_case (pipeline.bronze_complete) so they
        # don't collide with the kaori.pipeline.bronze.complete topic name —
        # arch-guards G2 lints any "pipeline.X.Y" literal as a possible
        # legacy Kafka topic.
        log.info("pipeline.bronze_complete", run_id=run_id, rows=total_rows)

    except Exception as e:
        log.error("pipeline.bronze_failed", run_id=run_id, error=str(e))
        # Migration 024 cutover — UPDATE on pipeline_runs requires either
        # the RLS GUC OR a bypass role. acquire_for_tenant gives us the GUC
        # cleanly. Catch a second failure here so a downstream Postgres
        # outage doesn't mask the original parser exception (the structlog
        # error above is already published).
        try:
            from ...shared.db import acquire_for_tenant
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    "UPDATE pipeline_runs SET status='failed', error_message=$1 "
                    "WHERE run_id=$2 AND enterprise_id=$3",
                    str(e), uuid.UUID(run_id), uuid.UUID(enterprise_id),
                )
        except Exception as inner:
            log.error("pipeline.bronze_failed.update_skipped",
                      run_id=run_id, error=str(inner))
        _publish_status(run_id, "failed", error_message=str(e))


async def _read_chunked(file: UploadFile, chunk_size: int = 1024 * 1024) -> bytes:
    """Read file in chunks to avoid memory spike on large files."""
    chunks = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_FILE_SIZE_BYTES:
            raise ValueError("File too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _coerce_required_docs(raw) -> list[dict]:
    """asyncpg returns JSONB as str when no codec is registered; this
    helper handles both shapes. Returns a list of dicts, or [] on any
    parse problem (fail-open to keep upload flow resilient)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _normalize_kind(kind: str) -> str:
    """Folder kinds onto a small canonical set. 'pdf' / '.pdf' / 'PDF' →
    'pdf'; common image aliases collapsed so a card saying 'image' or
    'jpg' both accept .png + .jpeg."""
    k = (kind or "").lower().lstrip(".").strip()
    aliases = {
        "image":  "image",
        "img":    "image",
        "jpeg":   "image",
        "jpg":    "image",
        "png":    "image",
        "tiff":   "image",
        "webp":   "image",
        "word":   "docx",
        "excel":  "xlsx",
        "spreadsheet": "xlsx",
        "doc":    "docx",
    }
    return aliases.get(k, k)


def _detected_kind(document_type) -> str:
    """Map a DocumentType (from silver/document_type.detect) onto the
    same canonical kind string the whitelist uses. Lets the workflow
    whitelist compare upload-kind correctly when filename/mime are
    untrustworthy (octet-stream, renamed extensions) but magic bytes
    reveal the real format."""
    # Import lazily to keep this module importable from bare paths.
    from ..silver.document_type import DocumentType
    mapping = {
        DocumentType.STRUCTURED_CSV:    "csv",
        DocumentType.STRUCTURED_TSV:    "tsv",
        DocumentType.STRUCTURED_XLSX:   "xlsx",
        DocumentType.STRUCTURED_XLS:    "xlsx",
        DocumentType.STRUCTURED_JSON:   "json",
        DocumentType.UNSTRUCTURED_PDF:  "pdf",
        DocumentType.UNSTRUCTURED_DOCX: "docx",
        DocumentType.UNSTRUCTURED_TXT:  "txt",
        DocumentType.IMAGE_RASTER:      "image",
        DocumentType.IMAGE_VECTOR:      "image",
    }
    return mapping.get(document_type, "unknown")


def _guess_mime(ext: str) -> str:
    return {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls":  "application/vnd.ms-excel",
        ".csv":  "text/csv",
        ".tsv":  "text/tab-separated-values",
        ".ods":  "application/vnd.oasis.opendocument.spreadsheet",
        ".zip":  "application/zip",
        ".sql":  "application/sql",
        # Unstructured kinds — registered for the FE document tree
        # even though we don't extract their content yet.
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc":  "application/msword",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
        ".md":   "text/markdown",
    }.get(ext, "application/octet-stream")
