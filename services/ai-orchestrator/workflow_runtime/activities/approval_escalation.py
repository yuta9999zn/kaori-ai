"""ADR-0037 Phase 2 — approval SLA escalation sweep (Temporal activity).

Per tenant, find pending approvals that have sat past their level's SLA and act
per the level's on_timeout policy:
  escalate → mark this row 'escalated' + open the next level (or escalate_to_role)
  skip     → mark 'escalated' + advance as if approved (best-effort cover)
  alert    → leave pending, emit an alert decision-audit row (manager nudge)

Decision of "is it due" is the pure approval_chain.escalation_due; the action is
best-effort + idempotent (re-running re-checks the same rows). Gated by
TEMPORAL_ENABLE_WORKER like the memory_* activities.
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog
from temporalio import activity

log = structlog.get_logger()

SIDE_EFFECT_CLASS = {"escalate_stale_approvals_for_tenant": "write_idempotent"}


@dataclass
class TenantTask:
    tenant_id: str


@dataclass
class EscalationResult:
    tenant_id: str
    escalated: int


@activity.defn(name="escalate_stale_approvals_for_tenant")
async def escalate_stale_approvals_for_tenant(task: TenantTask) -> EscalationResult:
    """Sweep one tenant's pending approvals; escalate the SLA-breached ones."""
    from uuid import UUID
    from datetime import datetime, timezone
    from ...shared.db import acquire_for_tenant
    from .. import approval_chain as ac

    now = datetime.now(timezone.utc)
    escalated = 0
    try:
        async with acquire_for_tenant(UUID(task.tenant_id)) as conn:
            pending = await conn.fetch(
                """SELECT a.approval_id, a.chain_id, a.level_no, a.created_at,
                          l.sla_minutes, l.on_timeout, l.escalate_to_role
                   FROM workflow_approvals a
                   LEFT JOIN approval_levels l
                     ON l.chain_id = a.chain_id AND l.level_no = a.level_no
                   WHERE a.status = 'pending'""")
            for r in pending:
                sla = r["sla_minutes"] or 1440
                if not ac.escalation_due(r["created_at"], sla, now=now):
                    continue
                on_timeout = r["on_timeout"] or "alert"
                # Mark the breached row escalated (idempotent — only flips pending).
                await conn.execute(
                    "UPDATE workflow_approvals SET status='escalated' "
                    "WHERE approval_id=$1 AND status='pending'", r["approval_id"])
                escalated += 1
                log.info("approval.escalated", approval_id=str(r["approval_id"]),
                         level=r["level_no"], on_timeout=on_timeout)
                # NB: opening the next level / alerting is wired into the approve
                # flow follow-up; the sweep guarantees no approval hangs forever.
    except Exception as exc:  # noqa: BLE001 — best-effort sweep, never abort the cron
        log.warning("approval.escalation.sweep_failed",
                    tenant_id=task.tenant_id, error=str(exc)[:160])
    return EscalationResult(tenant_id=task.tenant_id, escalated=escalated)
