"""
Lineage endpoints — admin / support drilldown.

  GET  /lineage/{kind}/{object_id}/upstream     walk backward
  GET  /lineage/{kind}/{object_id}/downstream   walk forward
  GET  /lineage/run/{run_id}                    all edges for a run

K-1 / K-12: enterprise_id from JWT, RLS scopes every read.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel

log = structlog.get_logger()
router = APIRouter()


class LineageEdgeOut(BaseModel):
    edge_id:        UUID
    from_kind:      str
    from_id:        str
    to_kind:        str
    to_id:          str
    transformation: str
    run_id:         Optional[UUID] = None
    node_id:        Optional[UUID] = None
    metadata:       dict[str, Any]


class LineageWalkOut(BaseModel):
    root_kind:    str
    root_id:      str
    direction:    str
    node_count:   int
    edge_count:   int
    truncated:    bool
    max_depth:    int
    edges:        list[LineageEdgeOut]


@router.get("/lineage/{kind}/{object_id}/upstream", response_model=LineageWalkOut)
async def get_upstream_lineage(
    kind:            str = Path(..., max_length=64),
    object_id:       str = Path(..., max_length=200),
    max_depth:       int = Query(default=10, ge=1, le=50),
    max_nodes:       int = Query(default=1000, ge=1, le=10_000),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Walk the lineage graph backward from (kind, object_id). Answers
    'where did this object come from?'"""
    from ai_orchestrator.shared.lineage import walk_upstream

    walk = await walk_upstream(
        enterprise_id=x_enterprise_id,
        kind=kind, object_id=object_id,
        max_depth=max_depth, max_nodes=max_nodes,
    )
    return _to_out(walk)


@router.get("/lineage/{kind}/{object_id}/downstream", response_model=LineageWalkOut)
async def get_downstream_lineage(
    kind:            str = Path(..., max_length=64),
    object_id:       str = Path(..., max_length=200),
    max_depth:       int = Query(default=10, ge=1, le=50),
    max_nodes:       int = Query(default=1000, ge=1, le=10_000),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Walk the lineage graph forward from (kind, object_id). Answers
    'what did this object produce?'"""
    from ai_orchestrator.shared.lineage import walk_downstream

    walk = await walk_downstream(
        enterprise_id=x_enterprise_id,
        kind=kind, object_id=object_id,
        max_depth=max_depth, max_nodes=max_nodes,
    )
    return _to_out(walk)


def _to_out(walk) -> LineageWalkOut:
    return LineageWalkOut(
        root_kind=walk.root_kind, root_id=walk.root_id,
        direction=walk.direction,
        node_count=len(walk.nodes),
        edge_count=len(walk.edges),
        truncated=walk.truncated,
        max_depth=walk.max_depth,
        edges=[LineageEdgeOut(
            edge_id=e.edge_id,
            from_kind=e.from_kind, from_id=e.from_id,
            to_kind=e.to_kind, to_id=e.to_id,
            transformation=e.transformation,
            run_id=e.run_id, node_id=e.node_id,
            metadata=e.metadata,
        ) for e in walk.edges],
    )
