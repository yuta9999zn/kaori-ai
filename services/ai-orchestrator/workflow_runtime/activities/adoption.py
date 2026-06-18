"""
Adoption cron activities — wraps the existing org_intel.adoption module
for Temporal scheduling.

Closes the gap raised in workflow-gap audit where 9 adoption signals
existed but cron-driven auto-compute was paused (TEMPORAL_ENABLE_WORKER
defaulted off).

Activities (K-17 classes match the underlying compute):
  list_active_tenants_for_adoption       read_only  — list tenants needing snapshot
  compute_tenant_health_snapshot         pure       — compute composite score
  persist_health_snapshot                write_idempotent — UPSERT snapshot row
  trigger_intervention_if_needed         external   — call /adoption/interventions/trigger
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
import structlog
from temporalio import activity

log = structlog.get_logger()


@dataclass
class TenantHealthTask:
    enterprise_id: str   # UUID-str; activities can't carry asyncpg UUIDs cleanly
    window_days:   int = 30


@dataclass
class HealthSnapshotResult:
    enterprise_id: str
    health_score:  float
    classification: str
    intervention_triggered: bool
    error:         Optional[str] = None


@activity.defn(name="list_active_tenants_for_adoption")
async def list_active_tenants_for_adoption() -> list[TenantHealthTask]:
    """Read-only: pull every active enterprise that needs a health
    snapshot. 'Needs' = last snapshot older than 1 hour OR no snapshot
    yet."""
    from ai_orchestrator.shared.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT e.enterprise_id
               FROM enterprises e
               WHERE e.status = 'active'
                 AND (
                   NOT EXISTS (
                     SELECT 1 FROM adoption_health_snapshots s
                     WHERE s.enterprise_id = e.enterprise_id
                       AND s.captured_at > NOW() - INTERVAL '1 hour'
                   )
                 )
               LIMIT 500"""
        )
    return [TenantHealthTask(enterprise_id=str(r["enterprise_id"]))
            for r in rows]


@activity.defn(name="compute_tenant_health_snapshot")
async def compute_tenant_health_snapshot(task: TenantHealthTask) -> HealthSnapshotResult:
    """Pure compute over recent signals. Returns the score + class
    without writing anything (writer is the next activity)."""
    from org_intel.adoption import (
        compute_composite_score,
        classify_health,
        SignalExtractor,
    )
    from ai_orchestrator.shared.db import acquire_for_tenant

    eid = UUID(task.enterprise_id)
    try:
        async with acquire_for_tenant(eid) as conn:
            extractor = SignalExtractor(conn=conn,
                                          enterprise_id=eid,
                                          window_days=task.window_days)
            samples = await extractor.extract_all()
        composite = compute_composite_score(samples)
        classification = classify_health(composite.score)
    except Exception as exc:  # noqa: BLE001
        log.exception("adoption.snapshot.compute_failed",
                       enterprise_id=task.enterprise_id)
        return HealthSnapshotResult(
            enterprise_id=task.enterprise_id,
            health_score=0.0,
            classification="unknown",
            intervention_triggered=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    return HealthSnapshotResult(
        enterprise_id=task.enterprise_id,
        health_score=float(composite.score),
        classification=classification.value
            if hasattr(classification, "value") else str(classification),
        intervention_triggered=False,
    )


@activity.defn(name="persist_health_snapshot")
async def persist_health_snapshot(result: HealthSnapshotResult) -> HealthSnapshotResult:
    """Write_idempotent: UPSERT into adoption_health_snapshots. Same
    (tenant, captured_hour) → identical row state."""
    if result.error:
        return result
    from ai_orchestrator.shared.db import acquire_for_tenant

    eid = UUID(result.enterprise_id)
    async with acquire_for_tenant(eid) as conn:
        await conn.execute(
            """INSERT INTO adoption_health_snapshots
                   (enterprise_id, captured_at, health_score, classification)
               VALUES ($1, date_trunc('hour', NOW()), $2, $3)
               ON CONFLICT (enterprise_id, captured_at) DO UPDATE
               SET health_score = EXCLUDED.health_score,
                   classification = EXCLUDED.classification""",
            eid, result.health_score, result.classification,
        )
    log.info("adoption.snapshot.persisted",
              enterprise_id=result.enterprise_id,
              score=result.health_score,
              classification=result.classification)
    return result


@activity.defn(name="trigger_intervention_if_needed")
async def trigger_intervention_if_needed(result: HealthSnapshotResult) -> HealthSnapshotResult:
    """External: POST /adoption/interventions/trigger when classification
    is at_risk or churn_imminent. Idempotency via per-tenant per-day key
    in the existing trigger endpoint."""
    if result.error:
        return result
    if result.classification not in ("at_risk", "churn_imminent"):
        return result

    base_url = os.getenv("AI_ORCH_INTERNAL_URL", "http://localhost:8093")
    payload = {
        "intervention_type": "auto_health_drop",
        "context": {
            "score":           result.health_score,
            "classification":  result.classification,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/adoption/interventions/trigger",
                json=payload,
                headers={
                    "X-Enterprise-Id": result.enterprise_id,
                    "Idempotency-Key": f"adoption-auto-{result.enterprise_id}-"
                                         f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                },
            )
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("adoption.intervention.trigger_failed",
                     enterprise_id=result.enterprise_id, error=str(exc))
        result.error = f"trigger fail: {type(exc).__name__}"
        return result

    result.intervention_triggered = True
    return result
