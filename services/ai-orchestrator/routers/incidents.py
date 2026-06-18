"""EU AI Act post-market monitoring + incident register — Layer 3 (ADR-0041, K-26).

Admin-gated (SUPER_ADMIN/ADMIN), tenant-scoped (K-1/K-12). Record-only this
slice: record_incident() is the single write path future auto-hooks call.
Namespace /admin/incidents — same edge reachability as /admin/dlq.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant
from ..shared.ai_governance import record_ai_call
from ..reasoning import incident_rules as ir

log = structlog.get_logger()
router = APIRouter()


def _require_admin(role: Optional[str]) -> None:
    if role not in ("SUPER_ADMIN", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail=f"incident console requires SUPER_ADMIN or ADMIN role; got {role!r}",
        )


class IncidentIn(BaseModel):
    incident_type: str = Field(..., max_length=48)
    severity:      str
    title:         str = Field(..., max_length=200)
    description:   Optional[str] = None
    decision_id:   Optional[UUID] = None
    run_id:        Optional[UUID] = None
    workflow_id:   Optional[UUID] = None
    detail:        Optional[dict] = None


class IncidentPatch(BaseModel):
    status:          str
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


class IncidentOut(BaseModel):
    incident_id:   str
    public_ref:    str
    incident_type: str
    severity:      str
    status:        str
    title:         str
    description:   Optional[str]
    decision_id:   Optional[str]
    run_id:        Optional[str]
    workflow_id:   Optional[str]
    reported_at:   Optional[str]
    resolved_at:   Optional[str]


def _row_to_out(row) -> IncidentOut:
    def _s(v):
        return str(v) if v else None
    return IncidentOut(
        incident_id=str(row["incident_id"]),
        public_ref=row["public_ref"],
        incident_type=row["incident_type"],
        severity=row["severity"],
        status=row["status"],
        title=row["title"],
        description=row["description"],
        decision_id=_s(row["decision_id"]),
        run_id=_s(row["run_id"]),
        workflow_id=_s(row["workflow_id"]),
        reported_at=row["reported_at"].isoformat() if row["reported_at"] else None,
        resolved_at=row["resolved_at"].isoformat() if row["resolved_at"] else None,
    )


async def record_incident(
    *,
    enterprise_id: UUID,
    incident_type: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    decision_id: Optional[UUID] = None,
    run_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    detail: Optional[dict] = None,
    reported_by: Optional[UUID] = None,
):
    """Single write path for K-26 incidents. Validates severity, inserts the
    row, audits (K-6). Returns the new row record."""
    sev = ir.validate_severity(severity)
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO ai_incident
                   (enterprise_id, incident_type, severity, title, description,
                    decision_id, run_id, workflow_id, detail, reported_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
               RETURNING incident_id, public_ref, incident_type, severity, status,
                         title, description, decision_id, run_id, workflow_id,
                         reported_at, resolved_at""",
            enterprise_id, incident_type, sev, title, description,
            decision_id, run_id, workflow_id, json.dumps(detail or {}), reported_by,
        )
    try:
        await record_ai_call(
            enterprise_id=enterprise_id, task_kind="incident_recorded",
            model_version="rules-only", model_provider="kaori-compliance",
            prompt=f"incident|{incident_type}|sev={sev}|{title}",
            output=json.dumps({"severity": sev, "type": incident_type}),
            confidence=None,
        )
    except Exception as e:  # noqa: BLE001 — audit must not break recording
        log.warning("incident.audit_failed", error=str(e))
    return row


@router.post("/admin/incidents", response_model=IncidentOut, status_code=201)
async def create_incident(
    body: IncidentIn,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    _require_admin(x_user_role)
    try:
        ir.validate_severity(body.severity)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid severity: {body.severity}")
    row = await record_incident(
        enterprise_id=x_enterprise_id, incident_type=body.incident_type,
        severity=body.severity, title=body.title, description=body.description,
        decision_id=body.decision_id, run_id=body.run_id, workflow_id=body.workflow_id,
        detail=body.detail, reported_by=x_user_id,
    )
    return _row_to_out(row)


@router.get("/admin/incidents", response_model=list[IncidentOut])
async def list_incidents(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    _require_admin(x_user_role)
    clauses, params = [], []
    if status:
        params.append(ir.validate_status(status)); clauses.append(f"status = ${len(params)}")
    if severity:
        params.append(ir.validate_severity(severity)); clauses.append(f"severity = ${len(params)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT incident_id, public_ref, incident_type, severity, status,
                       title, description, decision_id, run_id, workflow_id,
                       reported_at, resolved_at
                FROM ai_incident{where}
                ORDER BY reported_at DESC LIMIT ${len(params)}""",
            *params,
        )
    return [_row_to_out(r) for r in rows]


@router.patch("/admin/incidents/{incident_id}", response_model=IncidentOut)
async def update_incident(
    body: IncidentPatch,
    incident_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
):
    _require_admin(x_user_role)
    try:
        new_status = ir.validate_status(body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid status: {body.status}")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE ai_incident
                  SET status = $2,
                      resolved_at = CASE WHEN $2 = 'resolved' THEN NOW() ELSE resolved_at END,
                      detail = detail || $3::jsonb
                WHERE incident_id = $1
              RETURNING incident_id, public_ref, incident_type, severity, status,
                        title, description, decision_id, run_id, workflow_id,
                        reported_at, resolved_at""",
            incident_id, new_status,
            json.dumps({"resolution_note": body.resolution_note} if body.resolution_note else {}),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return _row_to_out(row)


@router.get("/admin/incidents/summary")
async def incidents_summary(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    window_days: int = Query(7, ge=1, le=90),
    low_confidence_threshold: float = Query(0.5, ge=0.0, le=1.0),
):
    """Art 72 monitoring single-pane: open incidents by severity + recent
    failed runs + recent low-confidence decisions.

    Note: workflow_runs has no `created_at` — its creation timestamp column is
    `started_at` (mig 088). The interval cast follows the repo idiom
    (chat/tools/platform.py): ``($N::text || ' days')::interval``.
    """
    _require_admin(x_user_role)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sev_rows = await conn.fetch(
            """SELECT severity, COUNT(*) AS n FROM ai_incident
               WHERE status <> 'resolved' GROUP BY severity""",
        )
        failed_runs = await conn.fetchval(
            """SELECT COUNT(*) FROM workflow_runs
                WHERE status = 'failed'
                  AND started_at >= NOW() - ($1::text || ' days')::interval""",
            window_days,
        )
        low_conf = await conn.fetchval(
            """SELECT COUNT(*) FROM ai_decision_audit
                WHERE confidence IS NOT NULL AND confidence < $1
                  AND created_at >= NOW() - ($2::text || ' days')::interval""",
            low_confidence_threshold, window_days,
        )
    return {
        "open_incidents_by_severity": {r["severity"]: int(r["n"]) for r in sev_rows},
        "failed_runs_recent": int(failed_runs or 0),
        "low_confidence_decisions_recent": int(low_conf or 0),
        "window_days": window_days,
        "low_confidence_threshold": low_confidence_threshold,
    }
