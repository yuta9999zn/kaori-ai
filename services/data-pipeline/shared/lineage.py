"""
Phase 2.7 P1 — Data lineage writer (data-pipeline local).

Mirror of services/ai-orchestrator/shared/lineage.py focused on the
write-side only. Read/walk happens on the ai-orchestrator side via its
admin endpoints; data-pipeline only PRODUCES edges (bronze→silver at
the /clean endpoint, future stage 5/6 emitters when they ship).

The data-pipeline service uses its own asyncpg pool via the local
shared/db.acquire_for_tenant helper (G4a). RLS on data_lineage_edges
passes via the GUC the helper sets.

Best-effort writes: a DB failure logs but never raises. The primary
ingestion path must never 500 because the lineage table is down — the
audit gap is recoverable, a broken pipeline isn't.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


# Allowed object kinds. Mirror of ai-orchestrator ObjectKind enum —
# kept as a frozenset of strings so data-pipeline doesn't depend on
# ai-orchestrator. Adding a kind: extend this set + the enum in the
# orch-side module (the table column is just VARCHAR).
ALLOWED_KINDS = frozenset({
    "bronze_file", "silver_row", "silver_table_row", "ontology_entity",
    "gold_view_row", "ai_decision", "workflow_run", "workflow_run_node",
    "workflow_insight", "workflow_alert", "workflow_task", "export_file",
})


async def record_edge(
    *,
    enterprise_id:    UUID | str,
    from_kind:        str,
    from_id:          str,
    to_kind:          str,
    to_id:            str,
    transformation:   str,
    run_id:           Optional[UUID | str] = None,
    node_id:          Optional[UUID | str] = None,
    metadata:         Optional[dict[str, Any]] = None,
) -> bool:
    """INSERT one edge into data_lineage_edges. ON CONFLICT DO NOTHING
    so retries don't double-insert.

    Returns True on insert, False on best-effort failure or silently-
    skipped (already exists / unknown kind).
    """
    if from_kind not in ALLOWED_KINDS or to_kind not in ALLOWED_KINDS:
        log.warning("lineage.unknown_kind",
                     from_kind=from_kind, to_kind=to_kind)
        return False
    if not enterprise_id:
        return False

    ent_uuid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))
    run_uuid = (
        run_id if isinstance(run_id, UUID)
        else UUID(str(run_id)) if run_id else None
    )
    node_uuid = (
        node_id if isinstance(node_id, UUID)
        else UUID(str(node_id)) if node_id else None
    )
    meta_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

    try:
        from .db import acquire_for_tenant
        async with acquire_for_tenant(ent_uuid) as conn:
            await conn.execute(
                """INSERT INTO data_lineage_edges
                       (enterprise_id, from_kind, from_id, to_kind, to_id,
                        transformation, run_id, node_id, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                   ON CONFLICT (enterprise_id, from_kind, from_id, to_kind, to_id, transformation)
                   DO NOTHING""",
                ent_uuid, from_kind, from_id, to_kind, to_id,
                transformation, run_uuid, node_uuid, meta_json,
            )
    except Exception as exc:
        log.warning(
            "lineage.write_failed",
            from_kind=from_kind, to_kind=to_kind, transformation=transformation,
            enterprise_id=str(ent_uuid), error=str(exc),
        )
        return False
    return True
