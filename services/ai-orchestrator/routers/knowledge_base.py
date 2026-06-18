"""Knowledge Base router (CR-0017) — ingest + retrieve domain knowledge.

Mounted under /knowledge-base/* (gateway rewrites /api/v1/knowledge-base/... →
/knowledge-base/...). The store of curated industry knowledge the AI reasons
WITH — distinct from the per-tenant RAG corpus (the customer's uploaded data).

Scope model (migration 106, 4-tier authority):
  * This tenant-facing router ingests TENANT-SPECIFIC knowledge only (tier 4,
    tenant_id = caller's enterprise) — a tenant's own SOPs/targets. Global
    tier 1-3 (regulatory / Kaori-curated / market) are seeded by the platform,
    never created here.
  * Search + list expose global (tier 1-3) + the tenant's own (tier 4) via RLS.

acquire_for_tenant + embed_text are module-level so tests inject mocks.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..reasoning.knowledge import KnowledgeDocument, KnowledgeStore, embed_text
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()

# A tenant's own ingestion is, by the authority model, tier 4 (high for them
# only) — not a configurable choice. Global tiers are platform-curated.
_TENANT_TIER = 4
_MAX_TOP_K = 20


# ── wire models ───────────────────────────────────────────────────────
class IngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    category: Optional[str] = Field(None, max_length=64)
    source: Optional[str] = Field(None, max_length=255)
    source_url: Optional[str] = None
    lang: str = Field("vi", max_length=8)
    tags: list[str] = Field(default_factory=list)


class DocumentOut(BaseModel):
    document_id: str
    tier: int
    scope: str                 # "global" | "tenant"
    category: Optional[str]
    title: str
    source: Optional[str]
    source_url: Optional[str]
    lang: str
    tags: list[str]
    snippet: Optional[str] = None        # truncated content for display
    similarity: Optional[float] = None   # search only (1 - cosine distance)


class IngestResponse(BaseModel):
    document_id: str
    status: str


class ListResponse(BaseModel):
    documents: list[DocumentOut]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=_MAX_TOP_K)
    category: Optional[str] = Field(None, max_length=64)


class SearchResponse(BaseModel):
    query: str
    results: list[DocumentOut]


# ── helpers ───────────────────────────────────────────────────────────
def _parse_enterprise_id(header_value: str) -> UUID:
    """K-14 RFC 7807 envelope on a bad UUID (mirrors rag.py)."""
    try:
        return UUID(header_value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://kaori.ai/errors/bad-enterprise-id",
                "title": "X-Enterprise-Id must be a UUID",
                "detail": f"got {header_value!r}",
                "errcode": "USR-ERR4",
            },
        )


def _to_out(doc: KnowledgeDocument) -> DocumentOut:
    return DocumentOut(
        document_id=str(doc.document_id),
        tier=doc.tier,
        scope="tenant" if doc.tenant_id is not None else "global",
        category=doc.category,
        title=doc.title,
        source=doc.source,
        source_url=doc.source_url,
        lang=doc.lang,
        tags=doc.tags,
        snippet=((doc.content or "")[:300] or None),
        similarity=(round(1.0 - doc.distance, 4) if doc.distance is not None else None),
    )


async def _embed_or_503(text: str, *, enterprise_id: str) -> list[float]:
    try:
        vec = await embed_text(text, enterprise_id=enterprise_id)
    except Exception as e:  # noqa: BLE001 — surface gateway outage cleanly
        log.warning("knowledge.embed_failed", error=str(e))
        raise HTTPException(status_code=503, detail={
            "type": "https://kaori.ai/errors/embedding-unavailable",
            "title": "Embedding service unavailable",
            "detail": "llm-gateway /v1/embed did not respond",
            "errcode": "SVC-ERR3",
        })
    if not vec:
        raise HTTPException(status_code=503, detail={
            "type": "https://kaori.ai/errors/embedding-empty",
            "title": "Embedding service returned no vector",
            "errcode": "SVC-ERR3",
        })
    return vec


# ── endpoints ─────────────────────────────────────────────────────────
@router.post("/knowledge-base/documents", response_model=IngestResponse, status_code=201)
async def ingest_document(
    req: IngestRequest,
    x_enterprise_id: str = Header(..., alias="X-Enterprise-ID"),
):
    """Ingest one tenant-specific (tier 4) knowledge doc. Embedded synchronously
    so it is searchable immediately."""
    eid = _parse_enterprise_id(x_enterprise_id)
    embedding = await _embed_or_503(f"{req.title}\n\n{req.content}", enterprise_id=str(eid))
    doc = KnowledgeDocument(
        title=req.title, content=req.content, tier=_TENANT_TIER,
        tenant_id=eid, category=req.category, source=req.source,
        source_url=req.source_url, lang=req.lang, tags=req.tags, status="active",
    )
    store = KnowledgeStore(acquire_for_tenant=acquire_for_tenant)
    doc_id = await store.put(doc, embedding=embedding, scope_tenant_id=eid)
    return IngestResponse(document_id=str(doc_id), status="active")


@router.get("/knowledge-base/documents", response_model=ListResponse)
async def list_documents(
    x_enterprise_id: str = Header(..., alias="X-Enterprise-ID"),
    category: Optional[str] = None,
    limit: int = 100,
):
    """List knowledge visible to the tenant: global (tier 1-3) + own (tier 4)."""
    eid = _parse_enterprise_id(x_enterprise_id)
    store = KnowledgeStore(acquire_for_tenant=acquire_for_tenant)
    docs = await store.list_documents(eid, category=category, limit=min(max(limit, 1), 500))
    return ListResponse(documents=[_to_out(d) for d in docs])


@router.post("/knowledge-base/search", response_model=SearchResponse)
async def search_knowledge(
    req: SearchRequest,
    x_enterprise_id: str = Header(..., alias="X-Enterprise-ID"),
):
    """Semantic search over global + own knowledge (cosine over BGE-M3)."""
    eid = _parse_enterprise_id(x_enterprise_id)
    query_vec = await _embed_or_503(req.query, enterprise_id=str(eid))
    store = KnowledgeStore(acquire_for_tenant=acquire_for_tenant)
    docs = await store.semantic_search(eid, query_vec, top_k=req.top_k, category=req.category)
    return SearchResponse(query=req.query, results=[_to_out(d) for d in docs])
