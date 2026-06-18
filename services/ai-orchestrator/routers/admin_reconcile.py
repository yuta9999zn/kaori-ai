"""
Admin reconcile endpoints — F3 of chaos-matrix.md follow-up.

Manual-invoke surface for the replay-driven reconciler. Admin role
required. Cron-mode lands when Temporal worker activates.

Endpoints:
  POST /admin/workflow-runs/{run_id}/reconcile
       Walk events for a single run + re-INSERT any missing
       workflow_run_nodes rows.

  POST /admin/reconcile/sweep?hours=24
       Find recent terminal runs + reconcile each. Bounds:
       hours 1..336 (max 2 weeks back); limit 1..1000.

Both return ReconcileResult / SweepResult JSON with counts.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel

log = structlog.get_logger()

router = APIRouter()


_ADMIN_ROLES = ("ADMIN", "SUPER_ADMIN", "SUPPORT")


def _require_admin(role: Optional[str]) -> None:
    if (role or "").upper() not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="admin role required (ADMIN / SUPER_ADMIN / SUPPORT)",
        )


# ─── Response models ──────────────────────────────────────────────────


class ReconcileOut(BaseModel):
    run_id:                str
    events_walked:         int
    nodes_in_projection:   int
    nodes_already_present: int
    nodes_inserted:        int
    insert_errors:         int
    inserted_node_ids:     list[str]


class SweepOut(BaseModel):
    runs_scanned:         int
    runs_reconciled:      int
    total_nodes_inserted: int
    total_insert_errors:  int
    per_run:              list[ReconcileOut]


# ─── Single-run reconcile ─────────────────────────────────────────────


@router.post(
    "/admin/workflow-runs/{run_id}/reconcile",
    response_model=ReconcileOut,
)
async def admin_reconcile_run(
    run_id:           UUID = Path(...),
    x_enterprise_id:  UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:      Optional[str] = Header(default=None, alias="X-User-Role"),
):
    """Re-INSERT any missing workflow_run_nodes rows for this run from
    the workflow_events log. Idempotent: ON CONFLICT DO NOTHING."""
    _require_admin(x_user_role)
    from ..workflow_runtime.reconciler import reconcile_run

    result = await reconcile_run(x_enterprise_id, run_id)
    return ReconcileOut(
        run_id=result.run_id,
        events_walked=result.events_walked,
        nodes_in_projection=result.nodes_in_projection,
        nodes_already_present=result.nodes_already_present,
        nodes_inserted=result.nodes_inserted,
        insert_errors=result.insert_errors,
        inserted_node_ids=result.inserted_node_ids,
    )


# ─── Sweep ────────────────────────────────────────────────────────────


@router.post("/admin/reconcile/sweep", response_model=SweepOut)
async def admin_reconcile_sweep(
    hours:           int = Query(default=24, ge=1, le=336),
    limit:           int = Query(default=100, ge=1, le=1000),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role:     Optional[str] = Header(default=None, alias="X-User-Role"),
):
    """Find all terminal runs in the last `hours` + reconcile each.
    Returns aggregate counts + per-run detail."""
    _require_admin(x_user_role)
    from ..workflow_runtime.reconciler import reconcile_recent

    sweep = await reconcile_recent(
        x_enterprise_id, hours=hours, limit=limit,
    )
    return SweepOut(
        runs_scanned=sweep.runs_scanned,
        runs_reconciled=sweep.runs_reconciled,
        total_nodes_inserted=sweep.total_nodes_inserted,
        total_insert_errors=sweep.total_insert_errors,
        per_run=[
            ReconcileOut(
                run_id=r.run_id,
                events_walked=r.events_walked,
                nodes_in_projection=r.nodes_in_projection,
                nodes_already_present=r.nodes_already_present,
                nodes_inserted=r.nodes_inserted,
                insert_errors=r.insert_errors,
                inserted_node_ids=r.inserted_node_ids,
            )
            for r in sweep.per_run
        ],
    )
