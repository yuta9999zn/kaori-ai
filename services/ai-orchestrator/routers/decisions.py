"""
F-029 — AI Decision Log (Phase 1 close-out, Sprint 2).

Read-only surface over ``decision_audit_log``. The table is append-only at
the rule layer (001/002 ``decision_audit_no_update`` / ``no_delete`` rules)
so K-2 immutability is honoured even if the handler had a bug.

Endpoints::

    GET /decisions?cursor=&limit=&type=&from=&to=&q=     cursor-paginated list
    GET /decisions/export.csv?type=&from=&to=&q=         streaming CSV (UTF-8 BOM)

K-1 / K-12: tenant comes from the gateway-trusted ``X-Enterprise-ID`` header.
``acquire_for_tenant`` (Sprint 0.5) sets ``app.enterprise_id`` so the
underlying SELECT is also row-level filtered when ``BYPASSRLS`` is dropped.

Cursor format mirrors F-022 (``services/data-pipeline/routers/enterprise_pipelines.py``):
``base64url("ISO8601|UUID")`` on the keyset ``(created_at DESC, decision_id DESC)``.
"""
from __future__ import annotations

import base64
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..shared import kafka_topics
from ..shared.db import acquire_for_tenant
from ..shared.kafka_producer import emit

log = structlog.get_logger()

router = APIRouter()

DEFAULT_LIMIT  = 50
MAX_LIMIT      = 500
EXPORT_MAX_ROWS = 10_000  # F-029 DoD: cap at 10k + X-Export-Truncated header


# =========================================================================
# Cursor encode / decode (mirrors F-022)
# =========================================================================

def _encode_cursor(created_at: datetime, decision_id: UUID) -> str:
    raw = f"{created_at.astimezone(timezone.utc).isoformat()}|{decision_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    pad = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + pad).encode("ascii")).decode("utf-8")
        ts_str, decision_id_str = decoded.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(decision_id_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cursor: {exc}")


# =========================================================================
# Filter -> SQL fragment helper, shared by list and export.
# =========================================================================

def _build_where(
    enterprise_id: UUID,
    *,
    cursor: Optional[str],
    type_: Optional[str],
    from_:  Optional[datetime],
    to:     Optional[datetime],
    q:      Optional[str],
) -> tuple[str, list]:
    where_parts = ["enterprise_id = $1"]
    params: list = [enterprise_id]

    if cursor:
        cursor_ts, cursor_id = _decode_cursor(cursor)
        where_parts.append(
            f"(created_at, decision_id) < (${len(params) + 1}, ${len(params) + 2})"
        )
        params.extend([cursor_ts, cursor_id])

    if type_:
        types = [t.strip() for t in type_.split(",") if t.strip()]
        if types:
            where_parts.append(f"decision_type = ANY(${len(params) + 1}::text[])")
            params.append(types)

    if from_:
        where_parts.append(f"created_at >= ${len(params) + 1}")
        params.append(from_)

    if to:
        where_parts.append(f"created_at <= ${len(params) + 1}")
        params.append(to)

    if q:
        # Case-insensitive substring search across the three free-text columns
        # the UI surfaces. Indexed scans are still fine because the WHERE is
        # predominantly tenant_id + created_at; q narrows after.
        ilike = f"%{q}%"
        where_parts.append(
            f"(subject ILIKE ${len(params) + 1} "
            f" OR reasoning ILIKE ${len(params) + 1} "
            f" OR chosen_value ILIKE ${len(params) + 1})"
        )
        params.append(ilike)

    return " AND ".join(where_parts), params


# =========================================================================
# GET /decisions
# =========================================================================

@router.get("")
async def list_decisions(
    request: Request,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    cursor: Optional[str] = Query(None),
    limit:  int           = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    type:   Optional[str] = Query(None, description="Comma-separated decision_type filter"),
    from_:  Optional[datetime] = Query(None, alias="from"),
    to:     Optional[datetime] = Query(None),
    q:      Optional[str] = Query(None, description="Substring search on subject/reasoning/chosen_value"),
):
    """List decision audit rows for the calling tenant, newest first."""

    if from_ and to and from_ > to:
        raise HTTPException(status_code=400, detail="from must be ≤ to")

    where, params = _build_where(
        x_enterprise_id, cursor=cursor, type_=type,
        from_=from_, to=to, q=q,
    )

    # Sprint 7 PR D — LEFT JOIN decision_actions so the FE can render the
    # is_actioned checkbox without a second round-trip per row. The action
    # row may not exist (DEFAULT FALSE semantically); LEFT JOIN keeps the
    # decision row in the page either way.
    sql = f"""
        SELECT d.decision_id, d.run_id, d.decision_type, d.subject, d.chosen_value,
               d.confidence, d.method, d.alternatives, d.uncertainty_flags,
               d.reasoning, d.needs_user_confirm, d.created_at,
               COALESCE(a.is_actioned, FALSE) AS is_actioned,
               a.actioned_at,
               a.actioned_by,
               a.notes                         AS action_notes
          FROM decision_audit_log d
          LEFT JOIN decision_actions a
                 ON a.decision_id = d.decision_id
         WHERE {where.replace("enterprise_id", "d.enterprise_id")}
         ORDER BY d.created_at DESC, d.decision_id DESC
         LIMIT ${len(params) + 1}
    """
    params.append(limit + 1)  # +1 trick to detect has_more

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

    has_more = len(rows) > limit
    page_rows = rows[:limit]

    next_cursor: Optional[str] = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_cursor(last["created_at"], last["decision_id"])

    return {
        "data": [_row_to_view(r) for r in page_rows],
        "meta": {
            "cursor":      next_cursor,
            "limit":       limit,
            "count":       len(page_rows),
            "has_more":    has_more,
            "request_id":  _request_id(request),
            "trace_id":    request.headers.get("X-Trace-ID"),
            "server_time": datetime.now(timezone.utc).isoformat(),
        },
    }


# =========================================================================
# GET /decisions/export.csv
# =========================================================================

CSV_COLUMNS = [
    "decision_id", "created_at", "decision_type", "subject", "chosen_value",
    "confidence", "method", "needs_user_confirm", "uncertainty_flags",
    "reasoning", "run_id",
]


@router.get("/export.csv")
async def export_decisions_csv(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    type:   Optional[str] = Query(None),
    from_:  Optional[datetime] = Query(None, alias="from"),
    to:     Optional[datetime] = Query(None),
    q:      Optional[str] = Query(None),
):
    """Stream a UTF-8-BOM CSV of decision rows. Capped at 10 000 rows; when
    the cap fires we set ``X-Export-Truncated: true`` so the FE can warn.

    BOM (``\\xef\\xbb\\xbf``) is required for Vietnamese Excel — without it
    Excel guesses Windows-1252 and renders mojibake on diacritics."""

    if from_ and to and from_ > to:
        raise HTTPException(status_code=400, detail="from must be ≤ to")

    where, params = _build_where(
        x_enterprise_id, cursor=None, type_=type,
        from_=from_, to=to, q=q,
    )

    # Fetch +1 so we know whether to set the truncation header before we
    # start streaming. Practical for 10 000 rows; if this ever needs to
    # serve millions, switch to server-side cursor + chunked yields.
    sql = f"""
        SELECT decision_id, created_at, decision_type, subject, chosen_value,
               confidence, method, needs_user_confirm, uncertainty_flags,
               reasoning, run_id
          FROM decision_audit_log
         WHERE {where}
         ORDER BY created_at DESC, decision_id DESC
         LIMIT ${len(params) + 1}
    """
    params.append(EXPORT_MAX_ROWS + 1)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(sql, *params)

    truncated = len(rows) > EXPORT_MAX_ROWS
    rows_to_emit = rows[:EXPORT_MAX_ROWS]

    headers = {
        "Content-Disposition": (
            f'attachment; filename="kaori-decisions-'
            f'{datetime.now(timezone.utc).strftime("%Y-%m-%d")}.csv"'
        ),
    }
    if truncated:
        headers["X-Export-Truncated"] = "true"

    return StreamingResponse(
        _csv_stream(rows_to_emit),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


def _csv_stream(rows) -> AsyncIterator[bytes]:
    """Yield BOM, header, then one line per row.

    Implemented as a regular generator returning bytes — StreamingResponse
    drives it as the response body. Using csv.writer against an in-memory
    StringIO per row keeps the quoting / escaping correct without pulling
    in pandas just for the dump.
    """
    async def _gen() -> AsyncIterator[bytes]:
        # UTF-8 BOM for Vietnamese Excel (same pattern F-011).
        yield b"\xef\xbb\xbf"

        # Header
        buf = io.StringIO()
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_COLUMNS)
        yield buf.getvalue().encode("utf-8")

        for r in rows:
            buf = io.StringIO()
            writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([
                str(r["decision_id"]),
                r["created_at"].astimezone(timezone.utc).isoformat()
                if r["created_at"] else "",
                r["decision_type"] or "",
                r["subject"] or "",
                r["chosen_value"] or "",
                f"{float(r['confidence']):.4f}" if r["confidence"] is not None else "",
                r["method"] or "",
                "true" if r["needs_user_confirm"] else "false",
                "|".join(r["uncertainty_flags"] or []),
                (r["reasoning"] or "").replace("\r", " ").replace("\n", " "),
                str(r["run_id"]) if r["run_id"] else "",
            ])
            yield buf.getvalue().encode("utf-8")

    return _gen()


# =========================================================================
# Helpers
# =========================================================================

def _row_to_view(r) -> dict:
    """Project the BE row to the FE-expected shape (matches the existing
    ``frontend/app/(app)/decisions/page.tsx`` ``DecisionAudit`` interface,
    plus the long-form fields the detail panel will eventually need).

    Sprint 7 PR D — also surfaces ``is_actioned`` + ``actioned_at`` from
    the LEFT JOIN on ``decision_actions``. Rows without an action row
    project as ``is_actioned=False, actioned_at=None``.
    """
    actioned_at = r.get("actioned_at") if hasattr(r, "get") else r["actioned_at"] if "actioned_at" in r else None
    return {
        "id":                  str(r["decision_id"]),
        "decision_id":         str(r["decision_id"]),
        "decision_type":       r["decision_type"],
        "entity_ref":          r["subject"],
        "subject":             r["subject"],
        "chosen_value":        r["chosen_value"],
        "confidence":          float(r["confidence"]) if r["confidence"] is not None else None,
        "method":              r["method"],
        "alternatives":        r["alternatives"] or [],
        "uncertainty_flags":   r["uncertainty_flags"] or [],
        "reasoning":           r["reasoning"],
        "needs_user_confirm":  bool(r["needs_user_confirm"]),
        "run_id":              str(r["run_id"]) if r["run_id"] else None,
        "created_at":          r["created_at"].astimezone(timezone.utc).isoformat()
                               if r["created_at"] else None,
        "is_actioned":         bool(r["is_actioned"]) if "is_actioned" in r else False,
        "actioned_at":         actioned_at.astimezone(timezone.utc).isoformat()
                               if actioned_at else None,
    }


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())


# =========================================================================
# POST /decisions/{id}/action — Sprint 7 PR D
#
# Half-closes the North Star "is_actioned" gap. Real per-customer
# tracking ships in F-060 (Phase 2). For pilot, CS team toggles a
# checkbox on /decisions and the result is persisted to the side
# table created in migration 019. UPSERT semantics: same toggle hit
# twice is a no-op the second time.
# =========================================================================

class DecisionActionRequest(BaseModel):
    is_actioned: bool
    notes: Optional[str] = Field(default=None, max_length=2000)


@router.post("/{decision_id}/action")
async def upsert_decision_action(
    decision_id: UUID,
    body:        DecisionActionRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Mark / unmark a decision as actioned. Idempotent UPSERT."""

    sql = """
        INSERT INTO decision_actions (
            decision_id, enterprise_id, is_actioned, actioned_at,
            actioned_by, notes
        ) VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (decision_id) DO UPDATE SET
            is_actioned = EXCLUDED.is_actioned,
            actioned_at = EXCLUDED.actioned_at,
            actioned_by = EXCLUDED.actioned_by,
            notes       = EXCLUDED.notes,
            updated_at  = NOW()
        RETURNING decision_id, is_actioned, actioned_at, actioned_by, notes,
                  updated_at
    """
    actioned_at = datetime.now(timezone.utc) if body.is_actioned else None

    async with acquire_for_tenant(x_enterprise_id) as conn:
        # Defence-in-depth: confirm the decision belongs to this tenant
        # before writing the side row. RLS on decision_actions enforces
        # the same predicate at the DB layer; this gives a clean 404
        # instead of a 500 / silent miss when a foreign decision_id is
        # POSTed.
        owner = await conn.fetchval(
            "SELECT 1 FROM decision_audit_log "
            "WHERE decision_id = $1 AND enterprise_id = $2",
            decision_id, x_enterprise_id,
        )
        if not owner:
            raise HTTPException(status_code=404, detail="Decision not found")

        row = await conn.fetchrow(
            sql, decision_id, x_enterprise_id, body.is_actioned,
            actioned_at, x_user_id, body.notes,
        )

    log.info("decision.action.upsert",
             enterprise_id=str(x_enterprise_id),
             decision_id=str(decision_id),
             is_actioned=body.is_actioned,
             actioned_by=str(x_user_id) if x_user_id else None)

    return {
        "data": {
            "decision_id":   str(row["decision_id"]),
            "is_actioned":   bool(row["is_actioned"]),
            "actioned_at":   row["actioned_at"].astimezone(timezone.utc).isoformat()
                             if row["actioned_at"] else None,
            "actioned_by":   str(row["actioned_by"]) if row["actioned_by"] else None,
            "notes":         row["notes"],
            "updated_at":    row["updated_at"].astimezone(timezone.utc).isoformat(),
        }
    }


# =========================================================================
# F-036 — GET /decisions/{id} (detail) + POST /decisions/{id}/override
#
# Closes the North Star feedback loop: domain experts disagree with an AI
# decision → record an explicit override + reason → kaori.feedback.actions
# Kafka event picks it up for F-074 fine-tuning + F-060 ROI rollup.
#
# v0 surface:
#   GET    /decisions/{id}                    detail with overrides history
#   POST   /decisions/{id}/override           append override + emit Kafka
#   POST   /decisions/{id}/override/{oid}/revoke  soft-revoke prior override
# =========================================================================

class OverrideRequest(BaseModel):
    override_value: str = Field(
        ...,
        min_length=1, max_length=500,
        description="Human-supplied corrected value the user thinks is right.",
    )
    reason: str = Field(
        ...,
        min_length=1, max_length=2000,
        description="Why the AI's choice was wrong — feeds F-074 fine-tuning.",
    )


class OverrideRevokeRequest(BaseModel):
    reason: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional — why the override is being revoked.",
    )


@router.get("/{decision_id}")
async def get_decision_detail(
    decision_id: UUID,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Single decision row + action toggle + override history.

    RLS scopes the SELECT — cross-tenant requests get the same 404 as
    a missing decision_id. The override list is ordered newest-first so
    the FE can pick ``[0]`` for the currently effective override (with
    ``revoked_at IS NULL``)."""

    sql_decision = """
        SELECT d.decision_id, d.run_id, d.decision_type, d.subject,
               d.chosen_value, d.confidence, d.method, d.alternatives,
               d.uncertainty_flags, d.reasoning, d.needs_user_confirm,
               d.created_at,
               COALESCE(a.is_actioned, FALSE) AS is_actioned,
               a.actioned_at, a.actioned_by, a.notes AS action_notes
          FROM decision_audit_log d
          LEFT JOIN decision_actions a ON a.decision_id = d.decision_id
         WHERE d.decision_id = $1
           AND d.enterprise_id = $2
    """

    sql_overrides = """
        SELECT override_id, decision_id, original_chosen_value,
               override_value, reason, overridden_by_user, overridden_at,
               revoked_at, revoked_by_user, revoke_reason
          FROM decision_overrides
         WHERE decision_id = $1
         ORDER BY overridden_at DESC
    """

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(sql_decision, decision_id, x_enterprise_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        overrides = await conn.fetch(sql_overrides, decision_id)

    return {
        "data": {
            **_row_to_view(row),
            "overrides": [_override_to_view(o) for o in overrides],
        }
    }


@router.post("/{decision_id}/override", status_code=201)
async def create_override(
    decision_id: UUID,
    body:        OverrideRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Append a new override row + emit kaori.feedback.actions.

    Append-only: an override on a decision that already has overrides
    is fine — the latest non-revoked one is the "current" effective
    override. The audit trail keeps the full history for forensics +
    fine-tuning data exports."""

    sql_lookup = """
        SELECT chosen_value, decision_type
          FROM decision_audit_log
         WHERE decision_id = $1 AND enterprise_id = $2
    """

    sql_insert = """
        INSERT INTO decision_overrides
            (enterprise_id, decision_id, original_chosen_value,
             override_value, reason, overridden_by_user)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING override_id, overridden_at
    """

    async with acquire_for_tenant(x_enterprise_id) as conn:
        original = await conn.fetchrow(sql_lookup, decision_id, x_enterprise_id)
        if original is None:
            raise HTTPException(status_code=404, detail="Decision not found")

        row = await conn.fetchrow(
            sql_insert,
            x_enterprise_id, decision_id, original["chosen_value"],
            body.override_value, body.reason, x_user_id,
        )

    occurred_at = row["overridden_at"].astimezone(timezone.utc).isoformat()

    # Best-effort Kafka emit. A relay outage must not roll back the
    # override row (matches the F-038 reports terminal-event pattern).
    try:
        await emit(kafka_topics.FEEDBACK_ACTIONS, {
            "override_id":    str(row["override_id"]),
            "decision_id":    str(decision_id),
            "enterprise_id":  str(x_enterprise_id),
            "action":         "override.created",
            "decision_type":  original["decision_type"] or "",
            "original_value": original["chosen_value"] or "",
            "override_value": body.override_value,
            "reason":         body.reason,
            "user_id":        str(x_user_id) if x_user_id else "",
            "occurred_at":    occurred_at,
        })
    except Exception as exc:
        log.error(
            "decision.override.kafka_emit_failed",
            decision_id=str(decision_id),
            override_id=str(row["override_id"]),
            error=str(exc),
        )

    log.info("decision.override.created",
             enterprise_id=str(x_enterprise_id),
             decision_id=str(decision_id),
             override_id=str(row["override_id"]),
             user_id=str(x_user_id) if x_user_id else None)

    return {
        "data": {
            "override_id":         str(row["override_id"]),
            "decision_id":         str(decision_id),
            "original_chosen_value": original["chosen_value"],
            "override_value":      body.override_value,
            "reason":              body.reason,
            "overridden_by_user":  str(x_user_id) if x_user_id else None,
            "overridden_at":       occurred_at,
        }
    }


@router.post("/{decision_id}/override/{override_id}/revoke")
async def revoke_override(
    decision_id: UUID,
    override_id: UUID,
    body:        OverrideRevokeRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Soft-revoke a prior override. The row stays for forensics; the
    FE filters by ``revoked_at IS NULL`` to find the currently
    effective override.

    Re-revoking an already-revoked override is a no-op (returns 409)
    rather than overwriting the original revoke metadata — preserves
    "first revoke wins" semantics for audit clarity."""

    sql_update = """
        UPDATE decision_overrides
           SET revoked_at      = NOW(),
               revoked_by_user = $3,
               revoke_reason   = $4
         WHERE override_id   = $1
           AND decision_id   = $2
           AND enterprise_id = $5
           AND revoked_at IS NULL
        RETURNING override_id, decision_id, override_value, reason,
                  revoked_at, revoked_by_user, revoke_reason
    """

    sql_check_exists = """
        SELECT revoked_at FROM decision_overrides
         WHERE override_id   = $1
           AND decision_id   = $2
           AND enterprise_id = $3
    """

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            sql_update, override_id, decision_id, x_user_id,
            body.reason, x_enterprise_id,
        )
        if row is None:
            existing = await conn.fetchrow(
                sql_check_exists, override_id, decision_id, x_enterprise_id,
            )
            if existing is None:
                raise HTTPException(status_code=404, detail="Override not found")
            # Existed but already revoked — preserve first-revoke metadata.
            raise HTTPException(
                status_code=409,
                detail="Override already revoked at "
                       + existing["revoked_at"].astimezone(timezone.utc).isoformat(),
            )

    revoked_at_iso = row["revoked_at"].astimezone(timezone.utc).isoformat()

    try:
        await emit(kafka_topics.FEEDBACK_ACTIONS, {
            "override_id":    str(row["override_id"]),
            "decision_id":    str(decision_id),
            "enterprise_id":  str(x_enterprise_id),
            "action":         "override.revoked",
            "decision_type":  "",  # not strictly needed on revoke; consumer joins
            "original_value": "",
            "override_value": row["override_value"] or "",
            "reason":         row["revoke_reason"] or "",
            "user_id":        str(x_user_id) if x_user_id else "",
            "occurred_at":    revoked_at_iso,
        })
    except Exception as exc:
        log.error(
            "decision.override.revoke_kafka_emit_failed",
            decision_id=str(decision_id),
            override_id=str(override_id),
            error=str(exc),
        )

    log.info("decision.override.revoked",
             enterprise_id=str(x_enterprise_id),
             decision_id=str(decision_id),
             override_id=str(override_id),
             user_id=str(x_user_id) if x_user_id else None)

    return {
        "data": {
            "override_id":      str(row["override_id"]),
            "decision_id":      str(decision_id),
            "revoked_at":       revoked_at_iso,
            "revoked_by_user":  str(row["revoked_by_user"]) if row["revoked_by_user"] else None,
            "revoke_reason":    row["revoke_reason"],
        }
    }


def _override_to_view(o) -> dict:
    return {
        "override_id":           str(o["override_id"]),
        "decision_id":           str(o["decision_id"]),
        "original_chosen_value": o["original_chosen_value"],
        "override_value":        o["override_value"],
        "reason":                o["reason"],
        "overridden_by_user":    str(o["overridden_by_user"]) if o["overridden_by_user"] else None,
        "overridden_at":         o["overridden_at"].astimezone(timezone.utc).isoformat()
                                 if o["overridden_at"] else None,
        "revoked_at":            o["revoked_at"].astimezone(timezone.utc).isoformat()
                                 if o["revoked_at"] else None,
        "revoked_by_user":       str(o["revoked_by_user"]) if o["revoked_by_user"] else None,
        "revoke_reason":         o["revoke_reason"],
        "is_active":             o["revoked_at"] is None,
    }
