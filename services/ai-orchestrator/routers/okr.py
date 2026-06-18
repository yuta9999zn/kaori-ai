"""
P2-S21 D5 — P2-M212-001 OKR (Objectives + Key Results) router.

Endpoints (mounted at /p2/strategy/okr)
---------------------------------------
    POST   /p2/strategy/okr                       — create OKR (+ optional KRs in same call)
    GET    /p2/strategy/okr                       — list (filter by period/status/dept)
    GET    /p2/strategy/okr/{okr_id}              — detail with KRs + linked workflows
    PATCH  /p2/strategy/okr/{okr_id}              — update meta (status/objective/notes)
    DELETE /p2/strategy/okr/{okr_id}              — cascade delete KRs + links

    POST   /p2/strategy/okr/{okr_id}/key-results  — add KR
    PATCH  /p2/strategy/okr/{okr_id}/key-results/{kr_id} — update current_value
                                                          (triggers progress recalc)
    DELETE /p2/strategy/okr/{okr_id}/key-results/{kr_id} — remove KR

    POST   /p2/strategy/okr/{okr_id}/link-workflow
                                            body {workflow_id, contribution_weight?}
    DELETE /p2/strategy/okr/{okr_id}/link-workflow/{workflow_id}

K-rules
-------
K-1 / K-12: tenant from X-Enterprise-ID JWT header
K-9: target/current/baseline NUMERIC(20,4)
K-14: 404 / 400 returned as RFC 7807 (delegated to global handler)
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator

from ..shared.db import acquire_for_tenant
from ..shared.idempotency_helper import (
    idempotency_short_circuit,
    record_idempotency_outcome,
)

log = structlog.get_logger()

router = APIRouter(prefix="/p2/strategy/okr")


# ─── Shapes ──────────────────────────────────────────────────────────


class KeyResultIn(BaseModel):
    kr_text:       str = Field(..., min_length=1, max_length=500)
    kr_text_vi:    Optional[str] = Field(default=None, max_length=500)
    metric_type:   str = Field(...,
                               pattern=r"^(count|percentage|currency|score|duration|binary)$")
    target_value:  Decimal = Field(..., decimal_places=4)
    current_value: Decimal = Field(default=Decimal("0"), decimal_places=4)
    baseline_value: Decimal = Field(default=Decimal("0"), decimal_places=4)
    weight:        Decimal = Field(default=Decimal("0.25"), gt=0, le=1, decimal_places=4)
    unit:          Optional[str] = Field(default=None, max_length=32)
    sort_order:    int = 0


class KeyResultOut(BaseModel):
    kr_id:         UUID
    okr_id:        UUID
    kr_text:       str
    kr_text_vi:    Optional[str]
    metric_type:   str
    target_value:  Decimal
    current_value: Decimal
    baseline_value: Decimal
    weight:        Decimal
    unit:          Optional[str]
    sort_order:    int


class OKRCreate(BaseModel):
    objective_text:    str = Field(..., min_length=1, max_length=500)
    objective_text_vi: Optional[str] = Field(default=None, max_length=500)
    department_id:     Optional[UUID] = None
    workspace_id:      Optional[UUID] = None
    period_label:      str = Field(..., min_length=1, max_length=32)
    period_start:      date
    period_end:        date
    owner_user_id:     Optional[UUID] = None
    notes:             Optional[str] = None
    key_results:       list[KeyResultIn] = Field(default_factory=list, max_length=20)

    @field_validator("period_end")
    @classmethod
    def _end_ge_start(cls, v: date, info):
        if "period_start" in info.data and v < info.data["period_start"]:
            raise ValueError("period_end must be >= period_start")
        return v


class OKRUpdate(BaseModel):
    objective_text:    Optional[str] = Field(default=None, min_length=1, max_length=500)
    objective_text_vi: Optional[str] = Field(default=None, max_length=500)
    status:            Optional[str] = Field(default=None,
                                              pattern=r"^(DRAFT|ACTIVE|ACHIEVED|MISSED|CANCELLED)$")
    notes:             Optional[str] = None


class KeyResultUpdate(BaseModel):
    current_value: Optional[Decimal] = Field(default=None, decimal_places=4)
    target_value:  Optional[Decimal] = Field(default=None, decimal_places=4)
    weight:        Optional[Decimal] = Field(default=None, gt=0, le=1, decimal_places=4)
    kr_text:       Optional[str] = Field(default=None, min_length=1, max_length=500)


class WorkflowLinkCreate(BaseModel):
    workflow_id:         UUID
    contribution_weight: Decimal = Field(default=Decimal("0.5"), gt=0, le=1, decimal_places=4)
    notes:               Optional[str] = None


class WorkflowLinkOut(BaseModel):
    link_id:             UUID
    workflow_id:         UUID
    okr_id:              UUID
    contribution_weight: Decimal
    notes:               Optional[str]


class OKROut(BaseModel):
    okr_id:            UUID
    enterprise_id:     UUID
    department_id:     Optional[UUID]
    workspace_id:      Optional[UUID]
    objective_text:    str
    objective_text_vi: Optional[str]
    period_label:      str
    period_start:      date
    period_end:        date
    owner_user_id:     Optional[UUID]
    status:            str
    progress:          Decimal
    notes:             Optional[str]


class OKRDetailOut(OKROut):
    key_results:    list[KeyResultOut] = Field(default_factory=list)
    linked_workflows: list[WorkflowLinkOut] = Field(default_factory=list)


# ─── Progress recalc helper ──────────────────────────────────────────


async def _recalc_progress(conn, okr_id: UUID) -> Decimal:
    """Weighted aggregate of KRs' (current/target) clamped to 1.0.

    Returns the new progress value and persists it to the okrs row.
    Per K-2 spirit (no silent partial updates), the function is sync
    on completion — caller commits the surrounding transaction.
    """
    rows = await conn.fetch(
        """SELECT target_value, current_value, baseline_value, weight, metric_type
           FROM key_results WHERE okr_id = $1""",
        okr_id,
    )
    if not rows:
        progress = Decimal("0")
    else:
        total_weight = Decimal("0")
        weighted_sum = Decimal("0")
        for r in rows:
            target = Decimal(r["target_value"])
            current = Decimal(r["current_value"])
            baseline = Decimal(r["baseline_value"])
            w = Decimal(r["weight"])

            if target == baseline:
                # Degenerate KR: no movement possible — count as 1 if
                # current met/exceeded baseline, else 0.
                kr_progress = Decimal("1") if current >= baseline else Decimal("0")
            else:
                # Relative progress from baseline → target.
                kr_progress = (current - baseline) / (target - baseline)
                kr_progress = max(Decimal("0"), min(Decimal("1"), kr_progress))

            weighted_sum += kr_progress * w
            total_weight += w

        progress = (weighted_sum / total_weight) if total_weight > 0 else Decimal("0")
        progress = max(Decimal("0"), min(Decimal("1"), progress))

    await conn.execute(
        "UPDATE okrs SET progress = $1, updated_at = NOW() WHERE okr_id = $2",
        progress, okr_id,
    )
    return progress


# ─── Row mappers ─────────────────────────────────────────────────────


def _row_to_okr(row) -> OKROut:
    return OKROut(
        okr_id=row["okr_id"],
        enterprise_id=row["enterprise_id"],
        department_id=row["department_id"],
        workspace_id=row["workspace_id"],
        objective_text=row["objective_text"],
        objective_text_vi=row["objective_text_vi"],
        period_label=row["period_label"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        owner_user_id=row["owner_user_id"],
        status=row["status"],
        progress=Decimal(row["progress"]),
        notes=row["notes"],
    )


def _row_to_kr(row) -> KeyResultOut:
    return KeyResultOut(
        kr_id=row["kr_id"],
        okr_id=row["okr_id"],
        kr_text=row["kr_text"],
        kr_text_vi=row["kr_text_vi"],
        metric_type=row["metric_type"],
        target_value=Decimal(row["target_value"]),
        current_value=Decimal(row["current_value"]),
        baseline_value=Decimal(row["baseline_value"]),
        weight=Decimal(row["weight"]),
        unit=row["unit"],
        sort_order=row["sort_order"],
    )


# ─── OKR CRUD ────────────────────────────────────────────────────────


@router.post("", response_model=OKRDetailOut, status_code=201)
async def create_okr(
    body: OKRCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Create OKR + optional inline KRs. Progress recomputed on commit.

    K-13: pass Idempotency-Key header; double-click on save button returns
    the original OKR (with the same okr_id) instead of creating a 2nd row.
    """
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return OKRDetailOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        async with conn.transaction():
            okr_row = await conn.fetchrow(
                """INSERT INTO okrs (enterprise_id, workspace_id, department_id,
                       objective_text, objective_text_vi, period_label,
                       period_start, period_end, owner_user_id, notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   RETURNING *""",
                x_enterprise_id, body.workspace_id, body.department_id,
                body.objective_text, body.objective_text_vi,
                body.period_label, body.period_start, body.period_end,
                body.owner_user_id, body.notes,
            )
            okr_id = okr_row["okr_id"]

            kr_rows = []
            for kr in body.key_results:
                kr_row = await conn.fetchrow(
                    """INSERT INTO key_results (okr_id, enterprise_id, kr_text,
                           kr_text_vi, metric_type, target_value, current_value,
                           baseline_value, weight, unit, sort_order)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                       RETURNING *""",
                    okr_id, x_enterprise_id, kr.kr_text, kr.kr_text_vi,
                    kr.metric_type, kr.target_value, kr.current_value,
                    kr.baseline_value, kr.weight, kr.unit, kr.sort_order,
                )
                kr_rows.append(kr_row)

            if kr_rows:
                await _recalc_progress(conn, okr_id)
                # Refresh to pick up new progress
                okr_row = await conn.fetchrow(
                    "SELECT * FROM okrs WHERE okr_id = $1", okr_id
                )

    out = OKRDetailOut(
        **_row_to_okr(okr_row).model_dump(),
        key_results=[_row_to_kr(r) for r in kr_rows],
        linked_workflows=[],
    )
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.get("", response_model=list[OKROut])
async def list_okrs(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    period: Optional[str] = Query(default=None, max_length=32),
    status: Optional[str] = Query(default=None,
                                   pattern=r"^(DRAFT|ACTIVE|ACHIEVED|MISSED|CANCELLED)$"),
    department_id: Optional[UUID] = None,
):
    """List OKRs with optional period / status / department filter."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = "SELECT * FROM okrs WHERE 1=1"
        params: list[Any] = []
        if period is not None:
            params.append(period)
            sql += f" AND period_label = ${len(params)}"
        if status is not None:
            params.append(status)
            sql += f" AND status = ${len(params)}"
        if department_id is not None:
            params.append(department_id)
            sql += f" AND department_id = ${len(params)}"
        sql += " ORDER BY period_start DESC, created_at DESC"
        rows = await conn.fetch(sql, *params)
    return [_row_to_okr(r) for r in rows]


@router.get("/{okr_id}", response_model=OKRDetailOut)
async def get_okr(
    okr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Detail with KRs + linked workflows."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        okr_row = await conn.fetchrow(
            "SELECT * FROM okrs WHERE okr_id = $1", okr_id
        )
        if okr_row is None:
            raise HTTPException(status_code=404, detail="OKR not found")
        kr_rows = await conn.fetch(
            "SELECT * FROM key_results WHERE okr_id = $1 ORDER BY sort_order, created_at",
            okr_id,
        )
        link_rows = await conn.fetch(
            "SELECT * FROM workflow_okr_links WHERE okr_id = $1",
            okr_id,
        )
    return OKRDetailOut(
        **_row_to_okr(okr_row).model_dump(),
        key_results=[_row_to_kr(r) for r in kr_rows],
        linked_workflows=[
            WorkflowLinkOut(
                link_id=r["link_id"], workflow_id=r["workflow_id"],
                okr_id=r["okr_id"], contribution_weight=Decimal(r["contribution_weight"]),
                notes=r["notes"],
            )
            for r in link_rows
        ],
    )


@router.patch("/{okr_id}", response_model=OKROut)
async def update_okr(
    body: OKRUpdate,
    okr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Patch objective/status/notes — never KRs (use sub-endpoint)."""
    updates: list[str] = []
    params: list[Any] = []
    if body.objective_text is not None:
        params.append(body.objective_text)
        updates.append(f"objective_text = ${len(params)}")
    if body.objective_text_vi is not None:
        params.append(body.objective_text_vi)
        updates.append(f"objective_text_vi = ${len(params)}")
    if body.status is not None:
        params.append(body.status)
        updates.append(f"status = ${len(params)}")
    if body.notes is not None:
        params.append(body.notes)
        updates.append(f"notes = ${len(params)}")
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at = NOW()")
    params.append(okr_id)
    sql = f"UPDATE okrs SET {', '.join(updates)} WHERE okr_id = ${len(params)} RETURNING *"
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(sql, *params)
    if row is None:
        raise HTTPException(status_code=404, detail="OKR not found")
    return _row_to_okr(row)


@router.delete("/{okr_id}", status_code=204)
async def delete_okr(
    okr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await conn.execute(
            "DELETE FROM okrs WHERE okr_id = $1", okr_id
        )
    return None


# ─── KR sub-endpoints ────────────────────────────────────────────────


@router.post("/{okr_id}/key-results", response_model=KeyResultOut, status_code=201)
async def add_key_result(
    body: KeyResultIn,
    okr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """K-13: Idempotency-Key dedupes double-click add-KR."""
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return KeyResultOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        async with conn.transaction():
            parent = await conn.fetchrow(
                "SELECT 1 FROM okrs WHERE okr_id = $1", okr_id
            )
            if parent is None:
                raise HTTPException(status_code=404, detail="OKR not found")
            row = await conn.fetchrow(
                """INSERT INTO key_results (okr_id, enterprise_id, kr_text,
                       kr_text_vi, metric_type, target_value, current_value,
                       baseline_value, weight, unit, sort_order)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                   RETURNING *""",
                okr_id, x_enterprise_id, body.kr_text, body.kr_text_vi,
                body.metric_type, body.target_value, body.current_value,
                body.baseline_value, body.weight, body.unit, body.sort_order,
            )
            await _recalc_progress(conn, okr_id)
    out = _row_to_kr(row)
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.patch("/{okr_id}/key-results/{kr_id}", response_model=KeyResultOut)
async def update_key_result(
    body: KeyResultUpdate,
    okr_id: UUID = Path(...),
    kr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    updates: list[str] = []
    params: list[Any] = []
    for fname in ("current_value", "target_value", "weight", "kr_text"):
        val = getattr(body, fname)
        if val is not None:
            params.append(val)
            updates.append(f"{fname} = ${len(params)}")
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at = NOW()")
    params.extend([kr_id, okr_id])
    sql = (
        f"UPDATE key_results SET {', '.join(updates)} "
        f"WHERE kr_id = ${len(params) - 1} AND okr_id = ${len(params)} RETURNING *"
    )
    async with acquire_for_tenant(x_enterprise_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(sql, *params)
            if row is None:
                raise HTTPException(status_code=404, detail="KR not found")
            await _recalc_progress(conn, okr_id)
    return _row_to_kr(row)


@router.delete("/{okr_id}/key-results/{kr_id}", status_code=204)
async def delete_key_result(
    okr_id: UUID = Path(...),
    kr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM key_results WHERE kr_id = $1 AND okr_id = $2",
                kr_id, okr_id,
            )
            await _recalc_progress(conn, okr_id)
    return None


# ─── Workflow link sub-endpoints ─────────────────────────────────────


@router.post("/{okr_id}/link-workflow", response_model=WorkflowLinkOut, status_code=201)
async def link_workflow(
    body: WorkflowLinkCreate,
    okr_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Link a workflow to this OKR with a contribution weight.

    K-13: DB-level UNIQUE(workflow_id, okr_id) already prevents duplicate;
    Idempotency-Key returns the original link payload so client gets the
    same 201 on retry (instead of 409 from UNIQUE conflict).
    """
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_idempotent")
    if cached is not None:
        return WorkflowLinkOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        okr_row = await conn.fetchrow(
            "SELECT 1 FROM okrs WHERE okr_id = $1", okr_id
        )
        if okr_row is None:
            raise HTTPException(status_code=404, detail="OKR not found")
        # Application-level FK check on workflow (mig 071's link table
        # doesn't FK to workflows for cross-schema independence).
        wf_row = await conn.fetchrow(
            "SELECT 1 FROM workflows WHERE workflow_id = $1", body.workflow_id
        )
        if wf_row is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        try:
            row = await conn.fetchrow(
                """INSERT INTO workflow_okr_links (workflow_id, okr_id,
                       enterprise_id, contribution_weight, notes)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                body.workflow_id, okr_id, x_enterprise_id,
                body.contribution_weight, body.notes,
            )
        except Exception as e:  # noqa: BLE001
            if "uq_workflow_okr" in str(e):
                raise HTTPException(
                    status_code=409,
                    detail="workflow already linked to this OKR",
                ) from e
            raise
    out = WorkflowLinkOut(
        link_id=row["link_id"], workflow_id=row["workflow_id"],
        okr_id=row["okr_id"],
        contribution_weight=Decimal(row["contribution_weight"]),
        notes=row["notes"],
    )
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.delete("/{okr_id}/link-workflow/{workflow_id}", status_code=204)
async def unlink_workflow(
    okr_id: UUID = Path(...),
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            "DELETE FROM workflow_okr_links WHERE okr_id = $1 AND workflow_id = $2",
            okr_id, workflow_id,
        )
    return None
