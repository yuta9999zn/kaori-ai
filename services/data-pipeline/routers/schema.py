"""Schema router — POST /schema (get mappings), POST /schema/confirm"""
import json
import time
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from datetime import datetime, timezone

from ..data_plane.bronze.column_mapper import (
    _LANGUAGE_DICT, map_columns,
    sniff_value_type, is_unnamed, header_looks_like_data,
)
from ..data_plane.bronze.llm_column_fallback import enrich_with_llm_fallback
from ..shared.db import acquire_for_tenant
from ..shared.event_bus import event_bus

router = APIRouter()

# Total wall-clock budget for the LLM column-naming fallback across every
# sheet in one /schema request. Keeps multi-sheet workbooks under the gateway
# response timeout; the fallback itself is disabled on the pilot (7B).
_FALLBACK_BUDGET_S = 12.0


def _publish_status(run_id, status: str) -> None:
    """F-NEW2 — push status transition to any open SSE subscriber."""
    event_bus.publish(run_id, {
        "run_id":     str(run_id),
        "status":     status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


class SchemaRequest(BaseModel):
    run_id: UUID


class MappingOverride(BaseModel):
    source_column: str
    canonical_name: str
    data_type: str


class SchemaConfirmRequest(BaseModel):
    run_id: UUID
    overrides: list[MappingOverride] = []


@router.post("")
async def get_schema(
    req: SchemaRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """
    Detect canonical schema for a pipeline run.
    Returns column mappings with confidence scores + uncertainty flags.

    Validation: req.run_id and X-Enterprise-ID are typed as UUID — Pydantic +
    FastAPI return 422 automatically on malformed values.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        run = await conn.fetchrow(
            "SELECT detected_language, status FROM pipeline_runs WHERE run_id=$1 AND enterprise_id=$2",
            req.run_id, x_enterprise_id,
        )
        if not run:
            raise HTTPException(404, "Run not found")
        if run["status"] not in ("bronze_complete", "schema_review"):
            # Friendly, status-aware message instead of the raw technical one.
            # The common case is an SHA-256 duplicate (K-8): the file was already
            # ingested + cleaned, so the run jumps straight to silver_complete and
            # never needs a schema-detection pass.
            if run["status"] in ("silver_complete", "analysis_complete"):
                raise HTTPException(
                    400,
                    "File này đã được xử lý trước đó (trùng dữ liệu) — đang dùng lại "
                    "kết quả đã làm sạch (Silver). Hãy xem kết quả ở bước Phân tích.",
                )
            raise HTTPException(
                400,
                "Lần chạy chưa sẵn sàng để nhận diện cột "
                f"(trạng thái: {run['status']}). Hãy hoàn tất bước tải dữ liệu trước.",
            )

        # Get unique source columns from bronze rows
        files = await conn.fetch(
            "SELECT file_id, sheet_name, detected_purpose FROM bronze_files "
            "WHERE run_id=$1 AND enterprise_id=$2",
            req.run_id, x_enterprise_id,
        )

        # Shared budget for the (best-effort) LLM column-naming fallback
        # across ALL sheets in this request, so a multi-sheet workbook stays
        # within the gateway's response timeout. Sheets past the budget keep
        # passthrough names — the FE's 🔴 "cần xác nhận" tier lets the user
        # name them anyway.
        fallback_deadline = time.monotonic() + _FALLBACK_BUDGET_S

        result = []
        for file_row in files:
            file_id = file_row["file_id"]
            # Sample rows for both column names AND value-level signals
            # (sample values, null %, value-based type sniffing). One row
            # only gave names — the FE then had nothing to show in "Mẫu"
            # and every type fell back to string.
            rows = await conn.fetch(
                "SELECT raw_data FROM bronze_rows WHERE file_id=$1 AND enterprise_id=$2 LIMIT 200",
                file_id, x_enterprise_id,
            )
            if not rows:
                continue

            parsed = [
                json.loads(r["raw_data"]) if isinstance(r["raw_data"], str) else r["raw_data"]
                for r in rows
            ]
            source_cols = list(parsed[0].keys())
            col_values: dict[str, list] = {c: [] for c in source_cols}
            for row in parsed:
                for c in source_cols:
                    col_values[c].append(row.get(c))

            def _col_stats(col: str):
                """Return (non_empty_values, null_pct, up-to-3 distinct samples)
                computed over the sampled rows."""
                vals = col_values.get(col, [])
                non_empty = [v for v in vals if v not in (None, "") and str(v).strip() != ""]
                null_pct = (round(100.0 * (len(vals) - len(non_empty)) / len(vals), 1)
                            if vals else 100.0)
                seen: set[str] = set()
                samples: list[str] = []
                for v in non_empty:
                    sv = str(v).strip()
                    if sv not in seen:
                        seen.add(sv)
                        samples.append(sv)
                    if len(samples) >= 3:
                        break
                return non_empty, null_pct, samples

            mappings = map_columns(
                source_columns=source_cols,
                detected_language=run["detected_language"] or "unknown",
                run_id=str(req.run_id),
                enterprise_id=str(x_enterprise_id),
            )

            # Value-level enrichment FIRST: sample values + null %, an
            # empty/unnamed flag so the FE can collapse blank Excel columns
            # into one group, a data-as-header warning, and a value-sniffed
            # type when the name-based pass produced none (every dict entry
            # lacks data_type, so otherwise everything is "text"). Doing this
            # before the LLM fallback lets the fallback skip blank columns.
            for m in mappings:
                col = m["source_column"]
                non_empty, null_pct, samples = _col_stats(col)
                m["sample_values"] = samples
                m["null_pct"] = null_pct
                m["looks_unnamed"] = is_unnamed(col)
                m["is_empty"] = null_pct >= 100.0
                m["header_looks_like_data"] = header_looks_like_data(col)
                if m.get("method") == "no_match" or (m.get("data_type") or "text") == "text":
                    sniffed = sniff_value_type(non_empty)
                    if sniffed:
                        m["data_type"] = sniffed
                        flags = list(m.get("uncertainty_flags") or [])
                        if "VALUE_SNIFFED_TYPE" not in flags:
                            flags.append("VALUE_SNIFFED_TYPE")
                        m["uncertainty_flags"] = flags

            # Stage 2B — LLM fallback (Qwen via llm-gateway, K-4) for columns
            # exact+fuzzy didn't cover. Best-effort + bounded: it skips blank
            # columns, is disabled on the pilot (7B too slow), and shares a
            # request-wide deadline so a multi-sheet workbook can't blow the
            # gateway timeout (was: 1 call/sheet × 5s × 9 sheets → 504).
            await enrich_with_llm_fallback(
                mappings,
                language_dict=_LANGUAGE_DICT,
                detected_lang=run["detected_language"] or "unknown",
                enterprise_id=str(x_enterprise_id),
                run_id=str(req.run_id),
                deadline=fallback_deadline,
            )

            # Persist auto-detected mappings so /clean/suggestions can pick
            # them up even when the user submits an empty overrides list at
            # /schema/confirm. ON CONFLICT keeps the row stable across
            # repeated /schema calls (idempotent re-detection).
            for m in mappings:
                await conn.execute(
                    """INSERT INTO canonical_schemas
                       (file_id, enterprise_id, source_column, canonical_name,
                        data_type, confidence, method, user_confirmed)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE)
                       ON CONFLICT (file_id, source_column) DO UPDATE
                         SET canonical_name = EXCLUDED.canonical_name,
                             data_type      = EXCLUDED.data_type,
                             confidence     = EXCLUDED.confidence,
                             method         = EXCLUDED.method,
                             updated_at     = NOW()
                       WHERE canonical_schemas.user_confirmed = FALSE""",
                    file_id,
                    x_enterprise_id,
                    m["source_column"],
                    m["canonical_name"],
                    m["data_type"],
                    m["confidence"],
                    m["method"],
                )

            # Log decisions to decision_audit_log (K-6)
            for m in mappings:
                await conn.execute(
                    """INSERT INTO decision_audit_log
                       (enterprise_id, run_id, decision_type, subject, chosen_value,
                        confidence, method, alternatives, uncertainty_flags)
                       VALUES ($1, $2, 'column_map', $3, $4, $5, $6, $7::jsonb, $8)""",
                    x_enterprise_id,
                    req.run_id,
                    m["source_column"],
                    m["canonical_name"],
                    m["confidence"],
                    m["method"],
                    json.dumps(m.get("alternatives", [])),
                    m.get("uncertainty_flags", []),
                )

            result.append({
                "file_id": str(file_id),
                "sheet_name": file_row["sheet_name"],
                "detected_purpose": file_row["detected_purpose"],
                "mappings": mappings,
            })

        # Update run status
        await conn.execute(
            "UPDATE pipeline_runs SET status='schema_review', updated_at=NOW() WHERE run_id=$1",
            req.run_id,
        )

    _publish_status(req.run_id, "schema_review")

    return {"run_id": str(req.run_id), "language": run["detected_language"], "sheets": result}


@router.post("/confirm")
async def confirm_schema(
    req: SchemaConfirmRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """
    User confirms (and optionally overrides) column mappings.
    Saves to canonical_schemas table.

    Validation: UUID-typed inputs return 422 on malformed values.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Get current auto-detected mappings
        files = await conn.fetch(
            "SELECT file_id FROM bronze_files WHERE run_id=$1",
            req.run_id,
        )
        for file_row in files:
            file_id = file_row["file_id"]
            # Upsert confirmed mappings
            for override in req.overrides:
                await conn.execute(
                    """INSERT INTO canonical_schemas
                       (file_id, enterprise_id, source_column, canonical_name,
                        data_type, confidence, method, user_confirmed, user_override)
                       VALUES ($1, $2, $3, $4, $5, 1.0, 'user_override', TRUE, $4)
                       ON CONFLICT (file_id, source_column)
                       DO UPDATE SET canonical_name=$4, data_type=$5, user_confirmed=TRUE,
                                     user_override=$4, confidence=1.0""",
                    file_id, x_enterprise_id,
                    override.source_column, override.canonical_name, override.data_type,
                )

        await conn.execute(
            "UPDATE pipeline_runs SET status='schema_review', updated_at=NOW() WHERE run_id=$1",
            req.run_id,
        )

    _publish_status(req.run_id, "schema_review")

    return {"run_id": str(req.run_id), "status": "confirmed"}


# ── GET /schema/fields — canonical vocabulary for the Step-2 "Đây là gì?" picker ──
# Data-driven from language_dictionary.json (single source of truth) so the FE
# dropdown never hardcodes a field list that can drift from the dict. The VN
# label is the first `vi` alias (the cleanest canonical Vietnamese term);
# description feeds the option tooltip.
@router.get("/fields")
async def list_canonical_fields():
    fields = []
    for canonical, entry in _LANGUAGE_DICT.items():
        vi = entry.get("vi") or []
        raw = (vi[0] if vi else canonical).strip()
        label = (raw[:1].upper() + raw[1:]) if raw else canonical
        fields.append({
            "canonical":   canonical,
            "label":       label,
            "data_type":   entry.get("data_type", "text"),
            "description": entry.get("description", ""),
        })
    fields.sort(key=lambda f: f["label"])
    return {"fields": fields}
