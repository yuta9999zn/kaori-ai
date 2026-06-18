"""Clean router — GET /clean/suggestions, POST /clean/apply"""
import json
import uuid
from typing import Any, Optional
from uuid import UUID

import pandas as pd
import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from datetime import datetime, timezone

from ..data_plane.silver.rule_catalog import (
    get_applicable_rules, RULE_BY_ID, apply_rules_to_df, measure_amount_signals,
)
from ..data_plane.silver.quality import compute_scorecard
from ..shared.audit import log_decision
from ..shared.db import acquire_for_tenant
from ..shared.event_bus import event_bus
from ..shared.kafka_producer import emit

log = structlog.get_logger()
router = APIRouter()


class CleanSuggestRequest(BaseModel):
    run_id: UUID
    file_id: UUID | None = None


class ApplyRulesRequest(BaseModel):
    run_id: UUID
    rule_ids: list[str]


async def _amount_signals_for_run(conn, run_id, enterprise_id):
    """Build a sampled canonical-named DataFrame for the run's transaction file
    and MEASURE its amount signals (rule_catalog.measure_amount_signals). Returns
    the signals dict, or None when no file carries quantity + a monetary column."""
    rows = await conn.fetch(
        """SELECT cs.file_id, cs.source_column, cs.canonical_name
           FROM canonical_schemas cs JOIN bronze_files bf ON bf.file_id = cs.file_id
           WHERE bf.run_id = $1 AND cs.enterprise_id = $2""",
        run_id, enterprise_id,
    )
    by_file: dict = {}
    for r in rows:
        by_file.setdefault(r["file_id"], {})[r["source_column"]] = r["canonical_name"]
    for file_id, col_map in by_file.items():
        canon = set(col_map.values())
        if "quantity" not in canon or not ({"unit_price", "amount", "revenue"} & canon):
            continue
        sample = await conn.fetch(
            "SELECT raw_data FROM bronze_rows WHERE file_id = $1 LIMIT 500", file_id,
        )
        if not sample:
            continue
        recs = []
        for s in sample:
            raw = s["raw_data"]
            if isinstance(raw, str):
                raw = json.loads(raw)
            recs.append({col_map.get(k, k): v for k, v in raw.items()})
        return measure_amount_signals(pd.DataFrame(recs))
    return None


def _suggest_line_total(sig: dict):
    """Suggestion for DERIVE_LINE_TOTAL derived from PRESENCE facts only
    (measured — NO hard-coded threshold gating). Returns (suggested: bool|None,
    rationale: str); the measured share is surfaced as supporting evidence."""
    if sig.get("has_explicit_total"):
        share = sig.get("total_matches_unit_times_qty")
        extra = (f" (đối chiếu: {round(share * 100)}% dòng có thành tiền ≈ đơn giá × số lượng)"
                 if share is not None else "")
        return False, ("Đã có cột thành tiền sẵn → KHÔNG cần nhân lại" + extra + ".")
    if sig.get("has_unit_price") and sig.get("has_quantity"):
        up, q = sig.get("unit_price_median"), sig.get("quantity_median")
        imp = sig.get("implied_line_total_median")
        return True, (f"Có đơn giá (median {up}) + số lượng (median {q}) nhưng CHƯA có cột "
                      f"thành tiền → nên nhân để ra thành tiền (ước {imp}/đơn). Bạn xác nhận.")
    return None, "Chưa đủ tín hiệu để gợi ý — xem số đo bên dưới và tự quyết."


@router.post("/suggestions")
async def get_cleaning_suggestions(
    req: CleanSuggestRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Return applicable cleaning rules based on detected schema.

    CR-0016 closeout: when DERIVE_LINE_TOTAL applies, attach MEASURED amount
    signals + a suggestion (presence-based, no forced threshold) so the user
    approves the unit-price × quantity derivation with the evidence in view.

    Validation: UUID-typed run_id / file_id / X-Enterprise-ID return 422 on
    malformed values.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        schemas = await conn.fetch(
            """SELECT cs.canonical_name, cs.data_type, bf.detected_purpose
               FROM canonical_schemas cs
               JOIN bronze_files bf ON bf.file_id = cs.file_id
               WHERE bf.run_id = $1 AND cs.enterprise_id = $2""",
            req.run_id, x_enterprise_id,
        )
        if not schemas:
            raise HTTPException(400, "No schema found — confirm schema first")

        data_types = {row["canonical_name"]: row["data_type"] for row in schemas}
        purposes = list({row["detected_purpose"] for row in schemas if row["detected_purpose"]})
        purpose = purposes[0] if purposes else None

        rules = get_applicable_rules(data_types, purpose)

        # CR-0016 — surface measured evidence next to the line-total rule.
        # Best-effort: enrichment must never break the rules listing.
        derive = next((r for r in rules if r.get("rule_id") == "DERIVE_LINE_TOTAL"), None)
        if derive is not None:
            try:
                sig = await _amount_signals_for_run(conn, req.run_id, x_enterprise_id)
                if sig is not None:
                    suggested, rationale = _suggest_line_total(sig)
                    derive["amount_signals"] = sig
                    derive["suggested"] = suggested
                    derive["rationale"] = rationale
            except Exception as e:  # noqa: BLE001 — enrichment is best-effort
                log.warning("clean.amount_signals_failed", error=str(e))

    return {"run_id": str(req.run_id), "rules": rules}


@router.post("/apply", status_code=202)
async def apply_cleaning_rules(
    req: ApplyRulesRequest,
    background_tasks: BackgroundTasks,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """
    Apply selected cleaning rules to Bronze → write Silver. ASYNC: validate,
    then return 202 and run the heavy rule-application + Silver write (tens of
    thousands of rows across sheets — synchronously it blew the gateway 30s
    → 504) in a BackgroundTask. Poll GET /upload/{run_id}/status until
    'silver_complete' or 'failed'. K-2: Bronze rows never modified.

    Validation: UUID-typed inputs return 422 on malformed values.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        run = await conn.fetchrow(
            "SELECT status FROM pipeline_runs WHERE run_id=$1 AND enterprise_id=$2",
            req.run_id, x_enterprise_id,
        )
        if not run:
            raise HTTPException(404, "Run not found")
        if run["status"] not in ("schema_review", "bronze_complete", "cleaning_pending"):
            raise HTTPException(400, f"Run status '{run['status']}' not eligible for cleaning")
        has_schema = await conn.fetchval(
            """SELECT 1 FROM canonical_schemas cs
               JOIN bronze_files bf ON bf.file_id = cs.file_id
               WHERE bf.run_id = $1 AND cs.enterprise_id = $2 LIMIT 1""",
            req.run_id, x_enterprise_id,
        )
        if not has_schema:
            raise HTTPException(400, "No confirmed schema found — confirm schema first")

    background_tasks.add_task(
        _run_cleaning,
        run_id=str(req.run_id),
        rule_ids=req.rule_ids,
        enterprise_id=str(x_enterprise_id),
    )
    return JSONResponse(status_code=202, content={"run_id": str(req.run_id), "status": "cleaning"})


async def _run_cleaning(*, run_id: str, rule_ids: list[str], enterprise_id: str) -> None:
    """BackgroundTask wrapper — runs the heavy clean; on ANY failure marks the
    run 'failed' + error_message so the FE status poll resolves, not spins."""
    try:
        await _do_cleaning(run_id=run_id, rule_ids=rule_ids, enterprise_id=enterprise_id)
    except Exception as e:  # noqa: BLE001 — background, must not crash silently
        log.exception("pipeline.clean.bg_failed", run_id=run_id, error=str(e))
        msg = str(e) if isinstance(e, ValueError) else "Làm sạch dữ liệu thất bại"
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await conn.execute(
                    """UPDATE pipeline_runs SET status='failed', error_message=$1,
                       updated_at=NOW() WHERE run_id=$2 AND enterprise_id=$3""",
                    msg[:2000], UUID(run_id), UUID(enterprise_id),
                )
        except Exception:  # noqa: BLE001
            log.exception("pipeline.clean.bg_mark_failed_failed", run_id=run_id)


async def _do_cleaning(*, run_id: str, rule_ids: list[str], enterprise_id: str) -> None:
    """Heavy path (BackgroundTask): rule application + Silver write, sets
    status='silver_complete'. K-2: Bronze rows never modified."""
    enterprise_uuid = UUID(enterprise_id)
    run_uuid = UUID(run_id)

    async with acquire_for_tenant(enterprise_id) as conn:
        # Load canonical schema for this run
        schema_rows = await conn.fetch(
            """SELECT cs.source_column, cs.canonical_name, cs.data_type,
                      bf.file_id, bf.detected_purpose
               FROM canonical_schemas cs
               JOIN bronze_files bf ON bf.file_id = cs.file_id
               WHERE bf.run_id = $1 AND cs.enterprise_id = $2
               ORDER BY bf.file_id""",
            run_uuid, enterprise_uuid
        )
        if not schema_rows:
            raise ValueError("No confirmed schema found — confirm schema first")

        # Build per-file column map: {file_id → {source_col → canonical_name}}
        file_col_map: dict[uuid.UUID, dict[str, str]] = {}
        file_type_map: dict[uuid.UUID, dict[str, str]] = {}
        file_purpose: dict[uuid.UUID, str | None] = {}
        for row in schema_rows:
            fid = row["file_id"]
            file_col_map.setdefault(fid, {})[row["source_column"]] = row["canonical_name"]
            file_type_map.setdefault(fid, {})[row["canonical_name"]] = row["data_type"]
            file_purpose[fid] = row["detected_purpose"]

        # Load all bronze rows for this run
        bronze_rows = await conn.fetch(
            """SELECT br.row_id, br.file_id, br.row_index, br.raw_data
               FROM bronze_rows br
               JOIN bronze_files bf ON bf.file_id = br.file_id
               WHERE bf.run_id = $1 AND br.enterprise_id = $2
               ORDER BY br.file_id, br.row_index""",
            run_uuid, enterprise_uuid
        )
        if not bronze_rows:
            raise ValueError("No bronze data found for this run")

    # Group bronze rows by file
    from collections import defaultdict
    rows_by_file: dict[uuid.UUID, list] = defaultdict(list)
    for row in bronze_rows:
        rows_by_file[row["file_id"]].append(row)

    # Process each file separately (different schemas per sheet)
    silver_records: list[dict[str, Any]] = []
    rules_audit: list[dict[str, Any]] = []
    # Per-file scorecards: file_id -> compute_scorecard() return. Aggregated
    # into a run-level overall + dimensions for pipeline_runs after the loop.
    scorecards: dict[uuid.UUID, dict[str, Any]] = {}

    for file_id, file_rows in rows_by_file.items():
        col_map = file_col_map.get(file_id, {})
        data_types = file_type_map.get(file_id, {})
        purpose = file_purpose.get(file_id)

        # Build DataFrame from raw_data, renaming source → canonical
        records = []
        row_ids = []
        row_indices = []
        for br in file_rows:
            raw = br["raw_data"]
            if isinstance(raw, str):
                raw = json.loads(raw)
            canonical_row = {
                col_map.get(k, k): v for k, v in raw.items()
            }
            records.append(canonical_row)
            row_ids.append(br["row_id"])
            row_indices.append(br["row_index"])

        df = pd.DataFrame(records)
        orig_len = len(df)

        # Apply requested rules
        applied, rows_changed = apply_rules_to_df(df, rule_ids, data_types)
        df = applied

        # Stage 4 — 7-dim quality scorecard on the cleaned sheet. Stored
        # per-file so the FE can drill from run → file → dimension → issues.
        scorecards[file_id] = compute_scorecard(df, data_types, purpose)

        for rule_id, col, count in rows_changed:
            rules_audit.append({
                "file_id": file_id,
                "rule_id": rule_id,
                "col": col,
                "rows_affected": count,
                "category": RULE_BY_ID.get(rule_id, {}).get("category", "UNIVERSAL"),
            })

        # Handle row removal: rows that still exist after filtering
        # df may be shorter if REMOVE_EMPTY_ROWS or DEDUP rules ran
        # Map surviving rows back to their bronze row_id by original index
        surviving_indices = df.index.tolist() if hasattr(df, 'index') else list(range(len(df)))
        applied_rule_ids = [r for r in rule_ids if RULE_BY_ID.get(r)]

        for new_idx, orig_idx in enumerate(surviving_indices):
            bronze_row_id = row_ids[orig_idx] if orig_idx < len(row_ids) else None
            row_data = df.iloc[new_idx].where(pd.notna(df.iloc[new_idx]), other=None).to_dict()
            # Convert numpy types to native Python for JSON serialisation
            row_data = {
                k: (v.item() if hasattr(v, "item") else v)
                for k, v in row_data.items()
            }
            silver_records.append({
                "file_id": file_id,
                "enterprise_id": enterprise_uuid,
                "run_id": run_uuid,
                "bronze_row_id": bronze_row_id,
                "row_index": new_idx,
                "row_data": row_data,
                "applied_rules": applied_rule_ids,
                "quality_score": _compute_quality(row_data),
            })

    # Persist silver rows + audit records in one transaction
    # NB: acquire_for_tenant already opens a transaction so we don't nest a
    # second `conn.transaction()` block — the LOCAL setting + writes live in
    # the wrapper's transaction.
    async with acquire_for_tenant(enterprise_id) as conn:
        # Delete any existing silver rows for this run (idempotent re-apply)
        await conn.execute(
            "DELETE FROM silver_rows WHERE run_id=$1 AND enterprise_id=$2",
            run_uuid, enterprise_uuid
        )

        # Bulk-insert silver rows. executemany pipelines the batch server-side
        # — the previous await-per-row loop made one round-trip per row, so a
        # multi-sheet workbook (tens of thousands of rows) blew past the
        # gateway timeout → 504 at Step 3.
        await conn.executemany(
            """INSERT INTO silver_rows
               (file_id, enterprise_id, bronze_row_id, run_id,
                row_index, row_data, applied_rules, quality_score)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8)""",
            [
                (
                    rec["file_id"],
                    rec["enterprise_id"],
                    rec["bronze_row_id"],
                    rec["run_id"],
                    rec["row_index"],
                    json.dumps(rec["row_data"]),
                    rec["applied_rules"],
                    rec["quality_score"],
                )
                for rec in silver_records
            ],
        )

        # Record cleaning rules applied (batched — same round-trip concern)
        await conn.executemany(
            """INSERT INTO cleaning_rules_applied
               (file_id, enterprise_id, rule_id, rule_category,
                affected_column, rows_affected, user_approved)
               VALUES ($1,$2,$3,$4,$5,$6,true)""",
            [
                (
                    audit["file_id"],
                    enterprise_uuid,
                    audit["rule_id"],
                    audit["category"],
                    audit.get("col"),
                    audit["rows_affected"],
                )
                for audit in rules_audit
            ],
        )

        # Aggregate per-file scorecards into a single run-level overall +
        # dimensions JSON. Row-weighted across files so a big sheet with
        # many issues drags the run score down, not a tiny config sheet.
        run_scorecard = _aggregate_scorecards(scorecards)

        # Advance pipeline status + persist scorecard. quality_score now
        # carries the weighted overall (Stage 4 spec), not the legacy
        # null-rate stub; quality_dimensions JSON breaks it down per
        # dimension + issue list for the FE drill-down (mig 065).
        await conn.execute(
            """UPDATE pipeline_runs
               SET status='silver_complete',
                   row_count_silver=$1,
                   quality_score=$2,
                   quality_dimensions=$3::jsonb,
                   updated_at=NOW()
               WHERE run_id=$4 AND enterprise_id=$5""",
            len(silver_records),
            run_scorecard["overall"],
            json.dumps(run_scorecard),
            run_uuid,
            enterprise_uuid,
        )

    # F-NEW2: notify any open SSE subscriber AFTER the cleaning transaction
    # commits. Outside the `async with acquire_for_tenant` block by design.
    event_bus.publish(run_uuid, {
        "run_id":           str(run_uuid),
        "status":           "silver_complete",
        "row_count_silver": len(silver_records),
        "updated_at":       datetime.now(timezone.utc).isoformat(),
    })

    # Phase 2.7 P1 — lineage edge emit. One coarse-grained edge per
    # (bronze_file, run) summarising "this file produced N silver rows
    # under run_id". Per-row lineage stays in silver_rows.bronze_row_id
    # for fine-grained drilldown; the edge supports the file-level walk
    # ("where did this gold_view_row come from?" → silver_row → run
    # bundle → bronze_file). Best-effort: failures log + skip, no
    # impact on the primary pipeline.
    #
    # Group silver rows by file_id (a single /clean call may span
    # multiple files in a multi-sheet upload).
    files_in_run = {rec["file_id"] for rec in silver_records}
    if files_in_run:
        from ..shared.lineage import record_edge as _record_lineage
        per_file_counts: dict[Any, int] = {}
        for rec in silver_records:
            per_file_counts[rec["file_id"]] = per_file_counts.get(rec["file_id"], 0) + 1
        for fid in files_in_run:
            await _record_lineage(
                enterprise_id=enterprise_uuid,
                from_kind="bronze_file",
                from_id=str(fid),
                to_kind="silver_row",
                # Coarse-grained: to_id = run_id (silver_row aggregate
                # for this run). Walkers querying upstream from a
                # silver_run_id find the source bronze_file directly.
                to_id=str(run_uuid),
                transformation="stage4.clean.apply_rules",
                run_id=run_uuid,
                metadata={
                    "row_count":      per_file_counts[fid],
                    "quality_score":  run_scorecard["overall"],
                    "rules_applied":  len(rules_audit),
                },
            )

    # K-6 audit: one row per cleaning rule applied. Best-effort — uses
    # its own pool.execute() so the main transaction above already
    # committed when we get here. If audit DB is down, the cleaning
    # still succeeds.
    for audit_entry in rules_audit:
        rule_id = audit_entry["rule_id"]
        await log_decision(
            enterprise_id=str(enterprise_uuid),
            run_id=str(run_uuid),
            decision_type="cleaning_rule",
            subject=f"{rule_id}:{audit_entry.get('col') or '*'}",
            chosen_value="applied",
            confidence=1.0,
            method="user_approved",
            reasoning=(
                f"category={audit_entry.get('category', 'UNIVERSAL')} "
                f"rows_affected={audit_entry['rows_affected']}"
            ),
        )

    # Emit Kafka event so orchestrator knows silver is ready.
    # Topic constant from kafka_topics (G2). UUID payload fields are
    # converted to str so the JSON serializer in send_event doesn't choke
    # on the UUID type — Batch 1 introduced the wrap; keep it after rebase.
    from ..shared import kafka_topics
    await emit(kafka_topics.PIPELINE_SILVER_COMPLETE, {
        "run_id": run_id,
        "enterprise_id": enterprise_id,
        "row_count": len(silver_records),
    })

    log.info("pipeline.clean.applied",
             run_id=run_id, silver_rows=len(silver_records),
             rules=rule_ids)


def _compute_quality(row_data: dict) -> float:
    """Per-row null-rate kept for the legacy silver_rows.quality_score
    column. The MEANINGFUL Stage 4 score is the run-level scorecard
    persisted to pipeline_runs.quality_dimensions; this per-row scalar
    is a coarse filter useful for "show me the worst 10 rows" queries.
    """
    if not row_data:
        return 0.0
    non_null = sum(1 for v in row_data.values() if v is not None)
    return round(non_null / len(row_data), 4)


def _aggregate_scorecards(scorecards: dict) -> dict[str, Any]:
    """Row-weighted aggregation of per-file scorecards into one run-level
    scorecard. A file with 6000 rows weighs ~30x more than one with 200.

    Dimensions that are None on a file simply drop out of that file's
    contribution — the surviving weights re-scale, same as the
    single-file overall.
    """
    if not scorecards:
        return {"dimensions": {}, "weights": {}, "overall": 0.0,
                "issues": [], "row_count": 0}

    total_rows = sum(sc["row_count"] for sc in scorecards.values()) or 1
    # Per-dim weighted sum + active-row count
    sums:    dict[str, float] = {}
    rows_for_dim: dict[str, int] = {}
    issues:  list[dict] = []
    for sc in scorecards.values():
        n = sc["row_count"]
        for dim, val in sc.get("dimensions", {}).items():
            if val is None or n == 0:
                continue
            sums.setdefault(dim, 0.0)
            rows_for_dim.setdefault(dim, 0)
            sums[dim] += val * n
            rows_for_dim[dim] += n
        issues.extend(sc.get("issues", []))

    dims_out: dict[str, Optional[float]] = {}
    for dim in {"completeness", "validity", "uniqueness",
                "consistency", "timeliness", "accuracy", "integrity"}:
        if dim in sums and rows_for_dim[dim] > 0:
            dims_out[dim] = round(sums[dim] / rows_for_dim[dim], 4)
        else:
            dims_out[dim] = None

    # Default weights — same as quality.py DEFAULT_WEIGHTS
    weights = {"completeness": 0.25, "validity": 0.20, "uniqueness": 0.15,
               "consistency": 0.15, "timeliness": 0.10, "accuracy": 0.10,
               "integrity": 0.05}
    active = {k: v for k, v in dims_out.items() if v is not None}
    used_w = sum(weights[k] for k in active) or 1.0
    overall = sum(active[k] * weights[k] for k in active) / used_w if active else 0.0
    return {
        "dimensions": dims_out,
        "weights":    weights,
        "overall":    round(overall, 4),
        "issues":     issues[:50],  # cap so the JSONB column stays small
        "row_count":  int(total_rows),
    }
