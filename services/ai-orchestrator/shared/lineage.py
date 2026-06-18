"""
Data lineage — record + walk transformation chain across the platform.

P1 of Phase 2.7 (per anh's 2026-05-19 review §1B). Lineage answers:

  "This Gold view row says revenue=12M. Where did 12M come from?"

Walking backward: gold_view_row → ai_decision → ontology_entity →
silver_row → bronze_file. Walking forward: bronze_file → … →
workflow_insight that a user saw.

API
---
  record_edge()       — INSERT one (from → to) edge (ON CONFLICT DO NOTHING)
  record_edges_batch() — batch helper for stage extractors emitting many
                         edges per file
  walk_upstream()     — BFS backward from (kind, id), bounded depth
  walk_downstream()   — BFS forward from (kind, id), bounded depth
  ObjectKind          — enum of valid kinds (matches mig 097 narrative)

Caller pattern (Stage 6 extractor example):
    await record_edge(
        enterprise_id=eid,
        from_kind=ObjectKind.BRONZE_FILE,
        from_id=str(file_id),
        to_kind=ObjectKind.SILVER_ROW,
        to_id=str(silver_row_id),
        transformation="stage6.docsage_extract",
        run_id=workflow_run_id,
    )
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


class ObjectKind(str, Enum):
    BRONZE_FILE         = "bronze_file"
    SILVER_ROW          = "silver_row"
    SILVER_TABLE_ROW    = "silver_table_row"
    ONTOLOGY_ENTITY     = "ontology_entity"
    GOLD_VIEW_ROW       = "gold_view_row"
    AI_DECISION         = "ai_decision"
    WORKFLOW_RUN        = "workflow_run"
    WORKFLOW_RUN_NODE   = "workflow_run_node"
    WORKFLOW_INSIGHT    = "workflow_insight"
    WORKFLOW_ALERT      = "workflow_alert"
    WORKFLOW_TASK       = "workflow_task"
    EXPORT_FILE         = "export_file"


@dataclass(frozen=True)
class LineageEdge:
    edge_id:        UUID
    enterprise_id:  UUID
    from_kind:      str
    from_id:        str
    to_kind:        str
    to_id:          str
    transformation: str
    run_id:         Optional[UUID]
    node_id:        Optional[UUID]
    metadata:       dict[str, Any]


@dataclass
class LineageWalk:
    """Result of walk_upstream or walk_downstream — BFS layers + visited nodes."""
    root_kind:       str
    root_id:         str
    direction:       str   # 'upstream' | 'downstream'
    nodes:           set[tuple[str, str]] = field(default_factory=set)
    edges:           list[LineageEdge] = field(default_factory=list)
    truncated:       bool = False
    max_depth:       int = 0


# ─── Record ──────────────────────────────────────────────────────


async def record_edge(
    *,
    enterprise_id:    UUID,
    from_kind:        str,
    from_id:          str,
    to_kind:          str,
    to_id:            str,
    transformation:   str,
    run_id:           Optional[UUID] = None,
    node_id:          Optional[UUID] = None,
    metadata:         Optional[dict[str, Any]] = None,
) -> None:
    """Append-only INSERT. ON CONFLICT DO NOTHING via UNIQUE constraint
    so callers can re-fire safely (e.g. resume after worker crash).
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            """INSERT INTO data_lineage_edges
                   (enterprise_id, from_kind, from_id, to_kind, to_id,
                    transformation, run_id, node_id, metadata)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
               ON CONFLICT (enterprise_id, from_kind, from_id,
                             to_kind, to_id, transformation) DO NOTHING""",
            enterprise_id, str(from_kind), str(from_id),
            str(to_kind), str(to_id),
            transformation, run_id, node_id,
            json.dumps(metadata or {}, default=str),
        )


async def record_edges_batch(
    *,
    enterprise_id:  UUID,
    edges:          Iterable[dict[str, Any]],
) -> int:
    """Bulk insert for stage extractors that emit many edges per file.
    Each dict: from_kind / from_id / to_kind / to_id / transformation +
    optional run_id / node_id / metadata.

    Returns number of rows actually inserted (excluding ON CONFLICT skips).
    """
    edge_list = list(edges)
    if not edge_list:
        return 0
    from ai_orchestrator.shared.db import acquire_for_tenant

    inserted = 0
    async with acquire_for_tenant(enterprise_id) as conn:
        async with conn.transaction():
            for e in edge_list:
                result = await conn.execute(
                    """INSERT INTO data_lineage_edges
                           (enterprise_id, from_kind, from_id, to_kind, to_id,
                            transformation, run_id, node_id, metadata)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                       ON CONFLICT (enterprise_id, from_kind, from_id,
                                     to_kind, to_id, transformation) DO NOTHING""",
                    enterprise_id, str(e["from_kind"]), str(e["from_id"]),
                    str(e["to_kind"]), str(e["to_id"]),
                    e["transformation"],
                    e.get("run_id"), e.get("node_id"),
                    json.dumps(e.get("metadata") or {}, default=str),
                )
                # asyncpg returns 'INSERT 0 N' — N is 1 on insert, 0 on conflict
                try:
                    inserted += int(result.split()[-1])
                except (ValueError, IndexError):
                    pass
    return inserted


# ─── Walk ────────────────────────────────────────────────────────


async def walk_upstream(
    *,
    enterprise_id:  UUID,
    kind:           str,
    object_id:      str,
    max_depth:      int = 10,
    max_nodes:      int = 1000,
) -> LineageWalk:
    """BFS backward from (kind, id). 'Where did this come from?'"""
    return await _walk(
        enterprise_id=enterprise_id, kind=kind, object_id=object_id,
        max_depth=max_depth, max_nodes=max_nodes, direction="upstream",
    )


async def walk_downstream(
    *,
    enterprise_id:  UUID,
    kind:           str,
    object_id:      str,
    max_depth:      int = 10,
    max_nodes:      int = 1000,
) -> LineageWalk:
    """BFS forward from (kind, id). 'What did this produce?'"""
    return await _walk(
        enterprise_id=enterprise_id, kind=kind, object_id=object_id,
        max_depth=max_depth, max_nodes=max_nodes, direction="downstream",
    )


async def _walk(
    *,
    enterprise_id: UUID,
    kind:          str,
    object_id:     str,
    max_depth:     int,
    max_nodes:     int,
    direction:     str,
) -> LineageWalk:
    if direction not in ("upstream", "downstream"):
        raise ValueError(f"direction={direction!r} invalid")
    if max_depth < 1 or max_depth > 50:
        raise ValueError("max_depth must be 1..50")
    if max_nodes < 1 or max_nodes > 10_000:
        raise ValueError("max_nodes must be 1..10000")

    result = LineageWalk(root_kind=kind, root_id=object_id, direction=direction)
    visited: set[tuple[str, str]] = {(kind, object_id)}
    queue: deque[tuple[str, str, int]] = deque([(kind, object_id, 0)])

    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        while queue:
            cur_kind, cur_id, depth = queue.popleft()
            if depth >= max_depth:
                result.truncated = True
                continue
            if len(visited) >= max_nodes:
                result.truncated = True
                break

            if direction == "upstream":
                rows = await conn.fetch(
                    "SELECT edge_id, enterprise_id, from_kind, from_id, "
                    "       to_kind, to_id, transformation, run_id, node_id, metadata "
                    "FROM data_lineage_edges "
                    "WHERE to_kind = $1 AND to_id = $2",
                    cur_kind, cur_id,
                )
                next_kind_col, next_id_col = "from_kind", "from_id"
            else:
                rows = await conn.fetch(
                    "SELECT edge_id, enterprise_id, from_kind, from_id, "
                    "       to_kind, to_id, transformation, run_id, node_id, metadata "
                    "FROM data_lineage_edges "
                    "WHERE from_kind = $1 AND from_id = $2",
                    cur_kind, cur_id,
                )
                next_kind_col, next_id_col = "to_kind", "to_id"

            for r in rows:
                meta = r["metadata"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta) if meta else {}
                    except json.JSONDecodeError:
                        meta = {}
                edge = LineageEdge(
                    edge_id=r["edge_id"],
                    enterprise_id=r["enterprise_id"],
                    from_kind=r["from_kind"], from_id=r["from_id"],
                    to_kind=r["to_kind"], to_id=r["to_id"],
                    transformation=r["transformation"],
                    run_id=r["run_id"], node_id=r["node_id"],
                    metadata=meta or {},
                )
                result.edges.append(edge)
                next_node = (r[next_kind_col], r[next_id_col])
                if next_node in visited:
                    continue
                visited.add(next_node)
                if len(visited) >= max_nodes:
                    result.truncated = True
                    break
                queue.append((next_node[0], next_node[1], depth + 1))
                if depth + 1 > result.max_depth:
                    result.max_depth = depth + 1

    result.nodes = visited
    log.info("lineage.walked",
              direction=direction, root_kind=kind,
              nodes_visited=len(visited), edges=len(result.edges),
              max_depth=result.max_depth, truncated=result.truncated)
    return result
