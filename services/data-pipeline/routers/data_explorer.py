"""
F-NEW3 — Data Explorer overview (Phase 2 hub).

Hub endpoint that powers /p2/data on the FE: a single round-trip
returning per-tenant snapshots of the three Medallion layers (Bronze
/ Silver / Gold) plus a recent-activity strip across all layers.

Why one endpoint, not three
---------------------------
Drill-down browsing of raw rows + lineage is intentionally deferred
to Phase 2 v1 (BACKLOG.md F-NEW3 row: "Pilot UAT does not require
raw Bronze/Silver/Gold browsing"). What pilot users *do* need is a
landing page that shows "I have N bronze files, M silver rows, K
gold features, last activity X minutes ago" — that's a single SQL
batch over already-indexed columns.

Endpoint shape::

    GET /api/v1/data/explorer  →  {
        bronze: { file_count, row_count_total, size_gb,
                  last_ingested_at, failed_24h },
        silver: { dataset_count, row_count_total,
                  quality_avg_pct, last_processed_at },
        gold:   { feature_count, row_count_total,
                  last_aggregated_at, stale_count },
        recent: [ { id, layer, name, action, at, status } ]   // last 5
    }

K-1 / K-12: tenant from gateway-trusted ``X-Enterprise-ID`` header.
RLS via ``acquire_for_tenant`` — kaori_app dropped BYPASSRLS so the
filter is also enforced at the row level (Sprint 0.5 cutover).
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query, Request

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()

# Stale = gold_features.computed_at older than 90 days. Matches the
# F-032 cutoff for the gold aggregator (docs/specs/MEDALLION_CONTRACT.md).
STALE_DAYS = 90

# Recent activity strip — small enough to render inline, large enough
# to show the day's pipeline drumbeat.
RECENT_LIMIT = 5

# Map pipeline_runs.status → (layer, vietnamese action label, ui status).
# `failed` / `cancelled` keep the bronze layer as default since those
# occur most commonly during ingest; a failure mid-silver still lands
# here because we don't track per-stage failure granularity yet.
STATUS_MAP: dict[str, tuple[str, str, str]] = {
    "uploading":         ("bronze", "Đang tải lên",         "running"),
    "bronze_complete":   ("bronze", "Đã ingest",            "ok"),
    "schema_review":     ("silver", "Đang xác nhận schema", "running"),
    "silver_complete":   ("silver", "Đã làm sạch",          "ok"),
    "analyzing":         ("gold",   "Đang tổng hợp",        "running"),
    "analysis_complete": ("gold",   "Đã tổng hợp",          "ok"),
    "failed":            ("bronze", "Thất bại",             "fail"),
    "cancelled":         ("bronze", "Đã huỷ",               "fail"),
}


# =========================================================================
# GET /explorer
# =========================================================================

@router.get("/explorer")
async def get_explorer_snapshot(
    request: Request,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
) -> dict:
    """One-shot snapshot for the /p2/data hub.

    Each layer block is a single small SQL — bronze + silver + gold all
    use indexed enterprise_id columns. The recent-activity strip shares
    the pipeline_runs index. Total cost is well under the 50ms p95
    budget for a hub page.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # ---- Bronze -----------------------------------------------------
        bronze_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS file_count,
                COALESCE(SUM(row_count), 0) AS row_count_total,
                MAX(created_at) AS last_ingested_at
              FROM bronze_files
             WHERE enterprise_id = $1
            """,
            x_enterprise_id,
        )

        size_row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(original_size_bytes), 0)::BIGINT AS bytes_total
              FROM pipeline_runs
             WHERE enterprise_id = $1
            """,
            x_enterprise_id,
        )

        failed_24h_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS failed_24h
              FROM pipeline_runs
             WHERE enterprise_id = $1
               AND status = 'failed'
               AND updated_at > NOW() - INTERVAL '24 hours'
            """,
            x_enterprise_id,
        )

        # ---- Silver -----------------------------------------------------
        silver_row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT file_id) AS dataset_count,
                COUNT(*)                AS row_count_total,
                AVG(quality_score)      AS quality_avg,
                MAX(created_at)         AS last_processed_at
              FROM silver_rows
             WHERE enterprise_id = $1
            """,
            x_enterprise_id,
        )

        # ---- Gold -------------------------------------------------------
        gold_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)            AS feature_count,
                MAX(computed_at)    AS last_aggregated_at,
                COUNT(*) FILTER (
                    WHERE computed_at < NOW() - ($2::int * INTERVAL '1 day')
                ) AS stale_count
              FROM gold_features
             WHERE enterprise_id = $1
            """,
            x_enterprise_id,
            STALE_DAYS,
        )

        # ---- Recent activity --------------------------------------------
        recent_rows = await conn.fetch(
            """
            SELECT run_id, filename, status, updated_at
              FROM pipeline_runs
             WHERE enterprise_id = $1
             ORDER BY updated_at DESC
             LIMIT $2
            """,
            x_enterprise_id,
            RECENT_LIMIT,
        )

    bytes_total = int(size_row["bytes_total"] or 0)
    size_gb = round(bytes_total / 1_000_000_000, 4) if bytes_total else 0.0

    quality_avg = silver_row["quality_avg"]
    # quality_score is NUMERIC(5,4) → 0..1 ratio. FE expects %, and 0.0
    # when no silver rows exist (instead of None) so the dashboard tile
    # renders "0.0%" rather than "—".
    quality_pct = round(float(quality_avg) * 100, 1) if quality_avg is not None else 0.0

    return {
        "bronze": {
            "file_count":       int(bronze_row["file_count"] or 0),
            "row_count_total":  int(bronze_row["row_count_total"] or 0),
            "size_gb":          size_gb,
            "last_ingested_at": _iso(bronze_row["last_ingested_at"]),
            "failed_24h":       int(failed_24h_row["failed_24h"] or 0),
        },
        "silver": {
            "dataset_count":     int(silver_row["dataset_count"] or 0),
            "row_count_total":   int(silver_row["row_count_total"] or 0),
            "quality_avg_pct":   quality_pct,
            "last_processed_at": _iso(silver_row["last_processed_at"]),
        },
        "gold": {
            "feature_count":      int(gold_row["feature_count"] or 0),
            "row_count_total":    int(gold_row["feature_count"] or 0),  # 1 row per customer
            "last_aggregated_at": _iso(gold_row["last_aggregated_at"]),
            "stale_count":        int(gold_row["stale_count"] or 0),
        },
        "recent": [_serialise_recent(r) for r in recent_rows],
    }


# =========================================================================
# Helpers
# =========================================================================

def _iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO-8601 in UTC, or None when the column is NULL."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _serialise_recent(row) -> dict:
    """One pipeline_runs row → recent-activity entry shape (template 14)."""
    layer, action, status = STATUS_MAP.get(
        row["status"],
        ("bronze", row["status"], "ok"),    # safe fallback for unknown statuses
    )
    return {
        "id":     str(row["run_id"]),
        "layer":  layer,
        "name":   row["filename"],
        "action": action,
        "at":     _iso(row["updated_at"]),
        "status": status,
    }


# =========================================================================
# F-NEW3 v1 — Bronze drill-down
# =========================================================================

# Cursor for /data/bronze/files keyset on (created_at DESC, file_id DESC).
# Same pattern as enterprise_pipelines.py.
def _encode_cursor(created_at: datetime, file_id: UUID) -> str:
    raw = f"{created_at.astimezone(timezone.utc).isoformat()}|{file_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    pad = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + pad).encode("ascii")).decode("utf-8")
        ts_str, id_str = decoded.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(id_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}")


# Pagination defaults — small for the drill-down table (analysts scroll
# rather than scan thousands of files at once). MAX_LIMIT keeps the FE
# from accidentally pulling the whole tenant in one shot.
BRONZE_FILES_DEFAULT_LIMIT = 50
BRONZE_FILES_MAX_LIMIT     = 500

# Sample data (raw_data JSONB) is heavier than file metadata — clamp the
# preview to a sane window so the response stays under 1 MB even for
# wide CSVs.
BRONZE_SAMPLE_DEFAULT_LIMIT = 50
BRONZE_SAMPLE_MAX_LIMIT     = 200


@router.get("/bronze/files")
async def list_bronze_files(
    request: Request,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor: Optional[str] = Query(None,
        description="Opaque cursor from prior meta.cursor"),
    limit:  int = Query(BRONZE_FILES_DEFAULT_LIMIT,
                        ge=1, le=BRONZE_FILES_MAX_LIMIT),
):
    """List bronze files for the calling tenant, newest first.

    Each row joins ``bronze_files`` (per-sheet metadata) with the parent
    ``pipeline_runs`` (the upload that produced it) so the FE can show
    "X.csv → Sheet1 (1,200 rows)" without a second round-trip.
    """
    where_parts = ["bf.enterprise_id = $1"]
    params: list = [x_enterprise_id]

    if cursor:
        cursor_ts, cursor_id = _decode_cursor(cursor)
        # Tuple keyset: rows strictly older than the cursor row, breaking
        # ties on file_id. Same pattern as enterprise_pipelines.list.
        where_parts.append(
            f"(bf.created_at, bf.file_id) < (${len(params) + 1}, ${len(params) + 2})"
        )
        params.extend([cursor_ts, cursor_id])

    sql = f"""
        SELECT bf.file_id, bf.run_id, bf.sheet_name, bf.sheet_index,
               bf.detected_purpose, bf.detected_language,
               bf.row_count, bf.col_count, bf.file_format,
               bf.created_at,
               pr.filename AS source_filename,
               pr.status   AS run_status
          FROM bronze_files bf
          JOIN pipeline_runs pr ON pr.run_id = bf.run_id
         WHERE {' AND '.join(where_parts)}
         ORDER BY bf.created_at DESC, bf.file_id DESC
         LIMIT ${len(params) + 1}
    """
    # Fetch limit+1 so we know whether a next page exists without COUNT.
    params.append(limit + 1)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

    has_more  = len(rows) > limit
    page_rows = rows[:limit]

    next_cursor: Optional[str] = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_cursor(last["created_at"], last["file_id"])

    return {
        "data": [_serialise_bronze_file(r) for r in page_rows],
        "meta": {
            "cursor":   next_cursor,
            "limit":    limit,
            "count":    len(page_rows),
            "has_more": has_more,
        },
    }


@router.get("/bronze/files/{file_id}/sample")
async def sample_bronze_file(
    request: Request,
    file_id: UUID = Path(..., description="bronze_files.file_id"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    limit: int = Query(BRONZE_SAMPLE_DEFAULT_LIMIT,
                       ge=1, le=BRONZE_SAMPLE_MAX_LIMIT),
):
    """Sample N rows from a bronze file (default 50, max 200).

    K-2 — bronze_rows is append-only and contains the raw upload as
    JSONB. We return the first ``limit`` rows ordered by ``row_index``;
    the FE renders them as a table where columns are inferred from the
    JSON keys of the first row.
    """
    # Tenant guard first — 404 the request before we look up rows so
    # we don't leak existence of files in other tenants.
    async with acquire_for_tenant(x_enterprise_id) as conn:
        meta = await conn.fetchrow(
            """
            SELECT bf.file_id, bf.sheet_name, bf.row_count, bf.col_count,
                   bf.file_format, bf.created_at,
                   pr.filename AS source_filename
              FROM bronze_files bf
              JOIN pipeline_runs pr ON pr.run_id = bf.run_id
             WHERE bf.file_id = $1
               AND bf.enterprise_id = $2
            """,
            file_id, x_enterprise_id,
        )
        if meta is None:
            raise HTTPException(status_code=404, detail=f"Bronze file not found: {file_id}")

        rows = await conn.fetch(
            """
            SELECT row_index, raw_data, row_hash, created_at
              FROM bronze_rows
             WHERE file_id = $1
               AND enterprise_id = $2
             ORDER BY row_index
             LIMIT $3
            """,
            file_id, x_enterprise_id, limit,
        )

    return {
        "data": {
            "file": {
                "file_id":         str(meta["file_id"]),
                "sheet_name":      meta["sheet_name"],
                "row_count":       int(meta["row_count"] or 0),
                "col_count":       int(meta["col_count"] or 0),
                "file_format":     meta["file_format"],
                "source_filename": meta["source_filename"],
                "created_at":      _iso(meta["created_at"]),
            },
            "rows": [_serialise_bronze_row(r) for r in rows],
            "limit": limit,
        }
    }


def _serialise_bronze_file(row) -> dict:
    return {
        "file_id":           str(row["file_id"]),
        "run_id":            str(row["run_id"]),
        "source_filename":   row["source_filename"],
        "run_status":        row["run_status"],
        "sheet_name":        row["sheet_name"],
        "sheet_index":       int(row["sheet_index"] or 0),
        "detected_purpose":  row["detected_purpose"],
        "detected_language": row["detected_language"],
        "row_count":         int(row["row_count"] or 0),
        "col_count":         int(row["col_count"] or 0),
        "file_format":       row["file_format"],
        "created_at":        _iso(row["created_at"]),
    }


def _serialise_bronze_row(row) -> dict:
    """asyncpg returns JSONB columns as Python dicts already."""
    return {
        "row_index":  int(row["row_index"]),
        "raw_data":   row["raw_data"],
        "row_hash":   row["row_hash"],
        "created_at": _iso(row["created_at"]),
    }


# =========================================================================
# F-NEW3 v1 — Silver drill-down
# =========================================================================

# Silver "datasets" are silver_rows grouped by file_id — a dataset is the
# cleaned counterpart of a bronze file. Cursor keys on the dataset's
# last_processed_at (latest cleaning event), since silver_rows.created_at
# is the per-row insert time.

SILVER_DATASETS_DEFAULT_LIMIT = 50
SILVER_DATASETS_MAX_LIMIT     = 500
SILVER_SAMPLE_DEFAULT_LIMIT   = 50
SILVER_SAMPLE_MAX_LIMIT       = 200


def _encode_silver_cursor(last_processed_at: datetime, file_id: UUID) -> str:
    raw = f"{last_processed_at.astimezone(timezone.utc).isoformat()}|{file_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_silver_cursor(cursor: str) -> tuple[datetime, UUID]:
    # Same wire format as the bronze cursor — split out so the keyset
    # column name is documented at the call site.
    return _decode_cursor(cursor)


@router.get("/silver/datasets")
async def list_silver_datasets(
    request: Request,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor: Optional[str] = Query(None,
        description="Opaque cursor from prior meta.cursor"),
    limit:  int = Query(SILVER_DATASETS_DEFAULT_LIMIT,
                        ge=1, le=SILVER_DATASETS_MAX_LIMIT),
):
    """List silver datasets (group of silver_rows per file) for the tenant.

    Each row aggregates ``silver_rows`` and joins ``bronze_files`` +
    ``pipeline_runs`` so the FE shows the cleaned-rows count alongside
    the source filename and the average quality score.
    """
    where_parts = ["sr.enterprise_id = $1"]
    params: list = [x_enterprise_id]

    # Cursor compares against MAX(created_at) per file_id — done in the
    # outer HAVING because silver_rows itself is ungrouped.
    cursor_filter = ""
    if cursor:
        cursor_ts, cursor_id = _decode_silver_cursor(cursor)
        cursor_filter = (
            f" HAVING (MAX(sr.created_at), sr.file_id) "
            f"< (${len(params) + 1}, ${len(params) + 2})"
        )
        params.extend([cursor_ts, cursor_id])

    sql = f"""
        SELECT sr.file_id,
               COUNT(*)                      AS row_count,
               AVG(sr.quality_score)          AS quality_avg,
               MIN(sr.created_at)             AS first_processed_at,
               MAX(sr.created_at)             AS last_processed_at,
               bf.col_count                   AS col_count,
               bf.sheet_name                  AS sheet_name,
               pr.filename                    AS source_filename,
               pr.status                      AS run_status
          FROM silver_rows sr
          JOIN bronze_files bf  ON bf.file_id = sr.file_id
          JOIN pipeline_runs pr ON pr.run_id  = bf.run_id
         WHERE {' AND '.join(where_parts)}
         GROUP BY sr.file_id, bf.col_count, bf.sheet_name,
                  pr.filename, pr.status
         {cursor_filter}
         ORDER BY MAX(sr.created_at) DESC, sr.file_id DESC
         LIMIT ${len(params) + 1}
    """
    params.append(limit + 1)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

        # Top 5 applied rule_ids per file in this page — one round-trip
        # for the whole page. Skipped when the page is empty.
        rules_by_file: dict[str, list[dict]] = {}
        if rows:
            file_ids = [r["file_id"] for r in rows[:limit]]
            rule_rows = await conn.fetch(
                """
                SELECT file_id, rule_id, rule_category,
                       SUM(rows_affected)::BIGINT AS affected_total
                  FROM cleaning_rules_applied
                 WHERE enterprise_id = $1
                   AND file_id = ANY($2::uuid[])
                 GROUP BY file_id, rule_id, rule_category
                 ORDER BY affected_total DESC
                """,
                x_enterprise_id, file_ids,
            )
            for rr in rule_rows:
                key = str(rr["file_id"])
                rules_by_file.setdefault(key, [])
                if len(rules_by_file[key]) < 5:
                    rules_by_file[key].append({
                        "rule_id":         rr["rule_id"],
                        "rule_category":   rr["rule_category"],
                        "rows_affected":   int(rr["affected_total"]),
                    })

    has_more  = len(rows) > limit
    page_rows = rows[:limit]

    next_cursor: Optional[str] = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_silver_cursor(last["last_processed_at"], last["file_id"])

    return {
        "data": [_serialise_silver_dataset(r, rules_by_file) for r in page_rows],
        "meta": {
            "cursor":   next_cursor,
            "limit":    limit,
            "count":    len(page_rows),
            "has_more": has_more,
        },
    }


@router.get("/silver/datasets/{file_id}/sample")
async def sample_silver_dataset(
    request: Request,
    file_id: UUID = Path(..., description="silver dataset = silver_rows.file_id"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    limit: int = Query(SILVER_SAMPLE_DEFAULT_LIMIT,
                       ge=1, le=SILVER_SAMPLE_MAX_LIMIT),
):
    """Sample N cleaned rows from a silver dataset (default 50, max 200).

    K-5 — silver_rows.row_data already has PII redacted by the
    cleaning pipeline. We never re-mask here; the source of truth is
    what the cleaning step wrote.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        meta = await conn.fetchrow(
            """
            SELECT bf.file_id, bf.sheet_name, bf.col_count, bf.file_format,
                   pr.filename AS source_filename,
                   (SELECT COUNT(*) FROM silver_rows sr
                     WHERE sr.file_id = bf.file_id
                       AND sr.enterprise_id = $2) AS row_count,
                   (SELECT MAX(created_at) FROM silver_rows sr
                     WHERE sr.file_id = bf.file_id
                       AND sr.enterprise_id = $2) AS last_processed_at
              FROM bronze_files bf
              JOIN pipeline_runs pr ON pr.run_id = bf.run_id
             WHERE bf.file_id = $1
               AND bf.enterprise_id = $2
            """,
            file_id, x_enterprise_id,
        )
        if meta is None or (meta["row_count"] or 0) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Silver dataset not found (or never cleaned): {file_id}")

        rows = await conn.fetch(
            """
            SELECT row_index, row_data, applied_rules,
                   quality_score, created_at
              FROM silver_rows
             WHERE file_id = $1
               AND enterprise_id = $2
             ORDER BY row_index
             LIMIT $3
            """,
            file_id, x_enterprise_id, limit,
        )

    return {
        "data": {
            "file": {
                "file_id":           str(meta["file_id"]),
                "sheet_name":        meta["sheet_name"],
                "row_count":         int(meta["row_count"] or 0),
                "col_count":         int(meta["col_count"] or 0),
                "file_format":       meta["file_format"],
                "source_filename":   meta["source_filename"],
                "last_processed_at": _iso(meta["last_processed_at"]),
            },
            "rows":  [_serialise_silver_row(r) for r in rows],
            "limit": limit,
        }
    }


def _serialise_silver_dataset(row, rules_by_file: dict) -> dict:
    quality = row["quality_avg"]
    quality_pct = round(float(quality) * 100, 1) if quality is not None else 0.0
    return {
        "file_id":             str(row["file_id"]),
        "source_filename":     row["source_filename"],
        "sheet_name":          row["sheet_name"],
        "run_status":          row["run_status"],
        "row_count":           int(row["row_count"] or 0),
        "col_count":           int(row["col_count"] or 0),
        "quality_avg_pct":     quality_pct,
        "first_processed_at":  _iso(row["first_processed_at"]),
        "last_processed_at":   _iso(row["last_processed_at"]),
        "applied_rules_top":   rules_by_file.get(str(row["file_id"]), []),
    }


def _serialise_silver_row(row) -> dict:
    return {
        "row_index":     int(row["row_index"]),
        # FE expects `clean_data` for backwards-compat with the
        # pre-migration-006 column name. Migration 006 renamed
        # silver_rows.clean_data → row_data; the FE shape stays.
        "clean_data":    row["row_data"],
        "applied_rules": list(row["applied_rules"] or []),
        "quality_score": float(row["quality_score"]) if row["quality_score"] is not None else None,
        "created_at":    _iso(row["created_at"]),
    }


# =========================================================================
# F-NEW3 v1 — Gold drill-down
# =========================================================================

# gold_features is per (enterprise_id, customer_external_id). The
# /customers/at-risk endpoint already exposes the HIGH-risk slice
# filtered to is_actioned=false; this endpoint is the analyst-facing
# "browse all features regardless of risk" view.

GOLD_CUSTOMERS_DEFAULT_LIMIT = 50
GOLD_CUSTOMERS_MAX_LIMIT     = 500


def _encode_gold_cursor(computed_at: datetime, customer_external_id: str) -> str:
    raw = f"{computed_at.astimezone(timezone.utc).isoformat()}|{customer_external_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_gold_cursor(cursor: str) -> tuple[datetime, str]:
    pad = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + pad).encode("ascii")).decode("utf-8")
        ts_str, ext_id = decoded.split("|", 1)
        return datetime.fromisoformat(ts_str), ext_id
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}")


@router.get("/gold/customers")
async def list_gold_customers(
    request: Request,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor: Optional[str] = Query(None,
        description="Opaque cursor from prior meta.cursor"),
    limit:  int = Query(GOLD_CUSTOMERS_DEFAULT_LIMIT,
                        ge=1, le=GOLD_CUSTOMERS_MAX_LIMIT),
    actioned: Optional[bool] = Query(None,
        description="Filter to is_actioned=true|false; omit for all rows"),
):
    """List gold_features for the tenant — analyst browse view.

    Note this is the *all customers* version. /api/v1/customers/at-risk
    (F-060) is the focused HIGH-risk slice with extra revenue tile +
    action toggle; this endpoint is for "show me everything in gold"
    so analysts can validate the aggregator output.
    """
    where_parts = ["enterprise_id = $1"]
    params: list = [x_enterprise_id]

    if cursor:
        cursor_ts, cursor_id = _decode_gold_cursor(cursor)
        where_parts.append(
            f"(computed_at, customer_external_id) "
            f"< (${len(params) + 1}, ${len(params) + 2})"
        )
        params.extend([cursor_ts, cursor_id])

    if actioned is not None:
        where_parts.append(f"is_actioned = ${len(params) + 1}")
        params.append(actioned)

    sql = f"""
        SELECT customer_external_id, revenue_at_risk, last_purchase_at,
               total_purchases, purchase_count, avg_purchase_value,
               is_actioned, actioned_at, computed_at
          FROM gold_features
         WHERE {' AND '.join(where_parts)}
         ORDER BY computed_at DESC, customer_external_id DESC
         LIMIT ${len(params) + 1}
    """
    params.append(limit + 1)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

    has_more  = len(rows) > limit
    page_rows = rows[:limit]

    next_cursor: Optional[str] = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_gold_cursor(last["computed_at"], last["customer_external_id"])

    return {
        "data": [_serialise_gold_customer(r) for r in page_rows],
        "meta": {
            "cursor":   next_cursor,
            "limit":    limit,
            "count":    len(page_rows),
            "has_more": has_more,
        },
    }


def _serialise_gold_customer(row) -> dict:
    return {
        "customer_external_id": row["customer_external_id"],
        "revenue_at_risk":      float(row["revenue_at_risk"] or 0),
        "last_purchase_at":     _iso(row["last_purchase_at"]),
        "total_purchases":      float(row["total_purchases"]) if row["total_purchases"] is not None else None,
        "purchase_count":       int(row["purchase_count"] or 0),
        "avg_purchase_value":   float(row["avg_purchase_value"]) if row["avg_purchase_value"] is not None else None,
        "is_actioned":          bool(row["is_actioned"]),
        "actioned_at":          _iso(row["actioned_at"]),
        "computed_at":          _iso(row["computed_at"]),
    }


# =========================================================================
# F-NEW3 v1 — Lineage (final follow-up — closes the v1 surface)
# =========================================================================

# Customer-id key the gold aggregator looks up in silver_rows.row_data.
# Matches docs/specs/MEDALLION_CONTRACT.md + the fall-through default
# in the F-032 aggregator. The lineage endpoint uses the same key when
# counting "how many distinct customer_external_id values does this
# bronze file's silver layer contribute to gold".
GOLD_CUSTOMER_ID_KEY = "customer_external_id"


@router.get("/lineage")
async def get_lineage(
    request: Request,
    file_id: UUID = Query(..., description="bronze_files.file_id to trace"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Trace one bronze file through Silver and Gold.

    Bronze: file + parent run metadata (always present if 404 doesn't fire).
    Silver: aggregate of silver_rows for this file + applied_rules
             top-3 (null when the file has never been cleaned).
    Gold:   best-effort COUNT DISTINCT customer_external_id seen in
             this file's silver row_data → how many gold_features
             rows this file contributes to. Null when the silver
             row_data doesn't carry the canonical customer key
             (per MEDALLION_CONTRACT.md the tenant must onboard with
             that mapping; older pipelines may not have it).
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        # ---- Bronze (also enforces tenancy) ----------------------------
        bronze_row = await conn.fetchrow(
            """
            SELECT bf.file_id, bf.run_id, bf.sheet_name, bf.sheet_index,
                   bf.detected_purpose, bf.detected_language,
                   bf.row_count, bf.col_count, bf.file_format,
                   bf.created_at,
                   pr.filename       AS source_filename,
                   pr.status         AS run_status,
                   pr.uploaded_by    AS uploaded_by,
                   pr.row_count_bronze,
                   pr.row_count_silver,
                   pr.quality_score  AS run_quality_score
              FROM bronze_files bf
              JOIN pipeline_runs pr ON pr.run_id = bf.run_id
             WHERE bf.file_id = $1
               AND bf.enterprise_id = $2
            """,
            file_id, x_enterprise_id,
        )
        if bronze_row is None:
            raise HTTPException(status_code=404, detail=f"Bronze file not found: {file_id}")

        # ---- Silver (null when no cleaned rows yet) -------------------
        silver_row = await conn.fetchrow(
            """
            SELECT COUNT(*)            AS row_count,
                   AVG(quality_score)   AS quality_avg,
                   MIN(created_at)      AS first_processed_at,
                   MAX(created_at)      AS last_processed_at
              FROM silver_rows
             WHERE file_id = $1
               AND enterprise_id = $2
            """,
            file_id, x_enterprise_id,
        )
        silver_row_count = int(silver_row["row_count"] or 0)

        applied_rules: list[dict] = []
        gold_block: Optional[dict] = None
        if silver_row_count > 0:
            rule_rows = await conn.fetch(
                """
                SELECT rule_id, rule_category,
                       SUM(rows_affected)::BIGINT AS affected_total
                  FROM cleaning_rules_applied
                 WHERE file_id = $1
                   AND enterprise_id = $2
                 GROUP BY rule_id, rule_category
                 ORDER BY affected_total DESC
                 LIMIT 5
                """,
                file_id, x_enterprise_id,
            )
            applied_rules = [{
                "rule_id":       r["rule_id"],
                "rule_category": r["rule_category"],
                "rows_affected": int(r["affected_total"]),
            } for r in rule_rows]

            # ---- Gold (best-effort customer link via JSONB key) -------
            #
            # Two-step lookup so we can distinguish "key not present in
            # this file's row_data" (gold = null) from "key present
            # but no matching gold row" (gold.linked_customer_count = 0).
            # NB: silver_rows.clean_data was renamed → row_data ở mig 006.
            link_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE row_data ? $3
                    ) AS rows_with_key,
                    COUNT(DISTINCT row_data ->> $3) FILTER (
                        WHERE row_data ? $3
                    ) AS distinct_customers
                  FROM silver_rows
                 WHERE file_id = $1
                   AND enterprise_id = $2
                """,
                file_id, x_enterprise_id, GOLD_CUSTOMER_ID_KEY,
            )
            rows_with_key = int(link_row["rows_with_key"] or 0)
            if rows_with_key > 0:
                # Cross-check against actual gold_features so we count
                # customers that survived to the per-tenant rollup, not
                # just IDs that appeared in the raw upload.
                gold_count_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) AS c
                      FROM gold_features gf
                     WHERE gf.enterprise_id = $1
                       AND gf.customer_external_id IN (
                          SELECT DISTINCT row_data ->> $3
                            FROM silver_rows
                           WHERE file_id = $2
                             AND enterprise_id = $1
                             AND row_data ? $3
                       )
                    """,
                    x_enterprise_id, file_id, GOLD_CUSTOMER_ID_KEY,
                )
                gold_block = {
                    "linked_customer_count": int(gold_count_row["c"] or 0),
                    "silver_rows_with_key":  rows_with_key,
                    "distinct_ids_in_silver": int(link_row["distinct_customers"] or 0),
                    "customer_id_key":       GOLD_CUSTOMER_ID_KEY,
                }
            # else: row_data doesn't carry the canonical key → gold_block stays None

    # ---- Assemble response ----
    silver_quality = silver_row["quality_avg"]
    silver_quality_pct = (round(float(silver_quality) * 100, 1)
                          if silver_quality is not None else 0.0)

    bronze_block = {
        "file_id":           str(bronze_row["file_id"]),
        "run_id":            str(bronze_row["run_id"]),
        "source_filename":   bronze_row["source_filename"],
        "run_status":        bronze_row["run_status"],
        "uploaded_by":       str(bronze_row["uploaded_by"]) if bronze_row["uploaded_by"] else None,
        "sheet_name":        bronze_row["sheet_name"],
        "sheet_index":       int(bronze_row["sheet_index"] or 0),
        "detected_purpose":  bronze_row["detected_purpose"],
        "detected_language": bronze_row["detected_language"],
        "row_count":         int(bronze_row["row_count"] or 0),
        "col_count":         int(bronze_row["col_count"] or 0),
        "file_format":       bronze_row["file_format"],
        "ingested_at":       _iso(bronze_row["created_at"]),
        "run_row_count_bronze": int(bronze_row["row_count_bronze"] or 0)
                                  if bronze_row["row_count_bronze"] is not None else None,
        "run_row_count_silver": int(bronze_row["row_count_silver"] or 0)
                                  if bronze_row["row_count_silver"] is not None else None,
        "run_quality_score":    float(bronze_row["run_quality_score"])
                                  if bronze_row["run_quality_score"] is not None else None,
    }

    if silver_row_count == 0:
        silver_block = None
    else:
        silver_block = {
            "row_count":          silver_row_count,
            "quality_avg_pct":    silver_quality_pct,
            "first_processed_at": _iso(silver_row["first_processed_at"]),
            "last_processed_at":  _iso(silver_row["last_processed_at"]),
            "applied_rules_top":  applied_rules,
        }

    return {
        "data": {
            "bronze": bronze_block,
            "silver": silver_block,
            "gold":   gold_block,
        }
    }
