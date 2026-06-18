"""Industry comparison endpoint (RAG chuyên ngành compare).

GET /api/v1/insights/industry-compare — benchmark the tenant's Gold metrics
against the curated SME-retail KB, grounded + |OR|-gated. Routed via the
insights gateway group; reads gold_* + knowledge_documents under one RLS-scoped
connection (K-1).
"""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Header

from ..shared.db import acquire_for_tenant
from ..reasoning.industry_compare import compare_to_industry
from ..reasoning.knowledge.embed import embed_text

log = structlog.get_logger()
router = APIRouter()


@router.get("/insights/industry-compare")
async def industry_compare(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        result = await compare_to_industry(conn, x_enterprise_id, embed_fn=embed_text)
    log.info("industry_compare.done", enterprise_id=str(x_enterprise_id),
             status=result.get("status"), coverage=result.get("coverage"))
    return result
