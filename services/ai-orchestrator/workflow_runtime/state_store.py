"""
State store — DB CRUD only, no business logic.

P1.1 of orchestration hardening: extracted from runner.py so the runner
can focus on dispatch + node iteration without knowing SQL.

Pattern: every function takes an explicit asyncpg connection or
enterprise_id and does ONE thing. No transition validation here — that
lives in state_machine.py. The runner composes the two.

Gap 1 (chaos-matrix.md follow-up, 2026-05-20): write-side functions
wrap DB calls in `retry_db_write` with 1 + 3 retry attempts on
connection-class failures. On exhaustion, raises DbWriteExhausted so
the caller (runner) marks the run as DB-unreachable in memory + emits
an ops metric instead of crashing or producing a zombie run state.

The retry helper lives in shared/db_retry.py so memory/postgres_l3.py
and other write-heavy modules can reuse without cross-layer import.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

from ai_orchestrator.shared.db_retry import (
    DbWriteExhausted,
    retry_db_write as _retry_db_write,
    is_retryable as _is_retryable,
)

log = structlog.get_logger()


# ─── workflow_runs CRUD ───────────────────────────────────────────


async def load_run(enterprise_id: UUID, run_id: UUID) -> Optional[dict[str, Any]]:
    """Read a workflow_runs row. Returns None if not found (or RLS hidden).
    Caller decides whether to raise on missing."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT run_id, workflow_id, input_data, status "
            "FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
    return dict(row) if row else None


async def fetch_run_status(enterprise_id: UUID, run_id: UUID) -> Optional[str]:
    """Lightweight status read — used by the resume flow to decide
    workflow_started vs workflow_resumed event tagging."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT status FROM workflow_runs WHERE run_id = $1",
            run_id,
        )
    return row["status"] if row else None


async def upsert_run_side_columns(
    enterprise_id:  UUID,
    run_id:         UUID,
    *,
    output_data:    Optional[dict] = None,
    error_summary:  Optional[str] = None,
    ended:          bool = False,
) -> None:
    """Update non-status columns. Status transitions go through
    state_machine.transition_workflow_status() — caller composes both
    inside one transaction in the runner.

    Gap 1: wrapped in _retry_db_write so transient pool/connection
    blips don't fail the run on first try."""
    params: list[Any] = []
    clauses: list[str] = []
    if output_data is not None:
        clauses.append(f"output_data = ${len(params) + 1}")
        params.append(json.dumps(output_data))
    if error_summary is not None:
        clauses.append(f"error_summary = ${len(params) + 1}")
        params.append(error_summary)
    if ended:
        clauses.append(f"ended_at = ${len(params) + 1}")
        params.append(datetime.now(timezone.utc))
    if not clauses:
        return
    params.append(run_id)
    sql = (
        f"UPDATE workflow_runs SET {', '.join(clauses)} "
        f"WHERE run_id = ${len(params)}"
    )

    async def _do():
        from ai_orchestrator.shared.db import acquire_for_tenant
        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(sql, *params)

    await _retry_db_write("upsert_run_side_columns", _do)


# ─── workflow_run_nodes CRUD ──────────────────────────────────────


async def upsert_run_node(
    *,
    run_id:             UUID,
    node:               dict[str, Any],
    enterprise_id:      UUID,
    side_effect_class:  str,
    status:             str,
    input_data:         dict[str, Any],
    output_data:        Optional[dict[str, Any]] = None,
    error_message:      Optional[str] = None,
) -> None:
    """INSERT-or-UPDATE workflow_run_nodes row. Same UPSERT semantics
    as the prior runner._record_node — pulled out so runner.py doesn't
    own the SQL.

    Gap 1: retry on connection-class failures. After exhaustion the
    caller (runner) catches DbWriteExhausted + degrades gracefully.
    """
    async def _do():
        from ai_orchestrator.shared.db import acquire_for_tenant
        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """INSERT INTO workflow_run_nodes
                       (run_id, node_id, enterprise_id, node_type_key,
                        side_effect_class, sequence_order, status,
                        input_data, output_data, error_message,
                        started_at, ended_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::text, $8, $9, $10,
                           NOW(),
                           CASE WHEN $7::text IN ('completed','failed','skipped')
                                THEN NOW() ELSE NULL END)
                   ON CONFLICT (run_id, node_id) DO UPDATE
                   SET status = EXCLUDED.status,
                       output_data = EXCLUDED.output_data,
                       error_message = EXCLUDED.error_message,
                       ended_at = CASE WHEN EXCLUDED.status IN ('completed','failed','skipped')
                                       THEN NOW() ELSE workflow_run_nodes.ended_at END,
                       retry_count = workflow_run_nodes.retry_count + 1""",
                run_id, node["node_id"], enterprise_id,
                node["node_type_catalog_key"], side_effect_class,
                node.get("sequence_order", 0), status,
                json.dumps(input_data),
                json.dumps(output_data) if output_data is not None else None,
                error_message,
            )

    await _retry_db_write("upsert_run_node", _do)


async def load_completed_node_outputs(
    enterprise_id: UUID,
    run_id:        UUID,
) -> dict[str, dict[str, Any]]:
    """Read every workflow_run_nodes row already in 'completed' state.
    Returns map keyed by node_id (str) → output_data dict."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT node_id, output_data FROM workflow_run_nodes "
            "WHERE run_id = $1 AND status = 'completed'",
            run_id,
        )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        data = r["output_data"]
        if isinstance(data, str):
            try:
                data = json.loads(data) if data else {}
            except json.JSONDecodeError:
                data = {}
        out[str(r["node_id"])] = data or {}
    return out


# ─── workflow_approvals CRUD ──────────────────────────────────────


async def load_resolved_approvals(
    enterprise_id: UUID,
    run_id:        UUID,
) -> dict[str, dict[str, Any]]:
    """Read every workflow_approvals row for this run with terminal
    state. Returns map keyed by node_id (str)."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT approval_id, node_id, status, "
            "       resolved_by_user_id, resolved_at, decision_note "
            "FROM workflow_approvals "
            "WHERE run_id = $1 AND status IN ('approved','rejected','expired','cancelled')",
            run_id,
        )
    return {str(r["node_id"]): dict(r) for r in rows}


# ─── workflows + workflow_nodes + workflow_edges (definition load) ───


async def load_workflow_definition(
    enterprise_id: UUID,
    workflow_id:   UUID,
) -> Optional[dict[str, Any]]:
    """Read workflow header + nodes + edges. Returns dict shape that
    the runner's topo-sort expects:
        {workflow_id, enterprise_id, workspace_id, nodes, edges}
    Or None if the workflow doesn't exist / RLS hides it.
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        wf_row = await conn.fetchrow(
            "SELECT workflow_id, enterprise_id, workspace_id "
            "FROM workflows WHERE workflow_id = $1",
            workflow_id,
        )
        if wf_row is None:
            return None
        node_rows = await conn.fetch(
            # type_version (ADR-0035): project it so the runner's get_versioned
            # actually pins the built version (B3 was a no-op without it).
            # config_json/condition_expr are the runner's internal names.
            # The builder writes node config to `decision_config` (approval
            # chain/role, if_else condition, …) while the YAML/import path writes
            # `config`. MERGE both so whatever the builder authored reaches the
            # executor — decision_config wins on key clash. (mig 053 cols; the
            # runner is the single consumer, so the merge is the source of truth.)
            "SELECT node_id, node_type_catalog_key, "
            "       (COALESCE(config, '{}'::jsonb) "
            "        || COALESCE(decision_config, '{}'::jsonb)) AS config_json, "
            "       sequence_order, type_version "
            "FROM workflow_nodes WHERE workflow_id = $1 "
            "ORDER BY sequence_order, node_id",
            workflow_id,
        )
        edge_rows = await conn.fetch(
            # port_type (ADR-0035 B5): runner topo-sorts only 'main'; ai_* are
            # side connections. label + is_default (mig 076/116) let the runner
            # match an outgoing edge to the branch a decision node took.
            "SELECT source_node_id, target_node_id, condition AS condition_expr, "
            "       label, is_default, port_type, flow_kind "
            "FROM workflow_edges WHERE workflow_id = $1",
            workflow_id,
        )
    return {
        "workflow_id":  wf_row["workflow_id"],
        "enterprise_id": wf_row["enterprise_id"],
        "workspace_id": wf_row["workspace_id"],
        "nodes":        [dict(r) for r in node_rows],
        "edges":        [dict(r) for r in edge_rows],
    }
