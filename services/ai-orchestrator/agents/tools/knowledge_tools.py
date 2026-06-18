"""F-061 read-side knowledge tools — let the agent GROUND before it acts.

Two tools added to the agent registry so the planner can plan a "gather
evidence" step before the action tools (draft_followup_email, …) fire. This
is step (1) of wiring RAG + the memory palace into the existing
plan→execute→critic harness (the OR-expansion side of IF∩MF):

  * ``retrieve_evidence`` — pull supporting passages from the RAG layer
    (rag.RAGRouter — pgvector / pageindex / docsage / trace_recall). This is
    the "MF→OR" pull: domain/corpus knowledge into the working context.
  * ``recall_memory``     — recall prior episodic/semantic memory for the
    tenant (the memory palace, reasoning.memory.MemoryService). This is the
    persistent IF: what the system already learned across sessions.

Both are READ-only (no dry_run side effect). They return structured evidence
the critic can later check for grounding (the |OR| / học-1-hiểu-10 gate lands
in the critic in step 2 — not here).

Honest pilot caveat: the RAG pgvector/pageindex engines default to stubs and
BGE-M3 embeddings aren't pulled on the pilot box, so retrieval QUALITY is
placeholder today — the value proven here is the harness WIRING. Real engines
+ embeddings are a follow-up; these tools benefit automatically when they land.
"""
from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import structlog

from ...chat.tools.base import BaseTool, ToolContext

log = structlog.get_logger()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Relevance floor for memory recall — a weak lexical overlap (e.g. shared
# stopwords between an off-domain question and a memory) must not surface and
# inflate the agent |OR| coverage gate's memory mass (audit 2026-06-02). Jaccard
# ≈0.18 for a topically-relevant recall, ~0 for off-domain — 0.1 separates them.
_RECALL_FLOOR = _env_float("KAORI_MEM_RECALL_FLOOR", 0.1)

# Module-level singletons — building a router / memory facade per tool call
# would rebuild engine objects every hop. Lazily constructed.
_ROUTER = None
_MEMORY = None


def _router():
    global _ROUTER
    if _ROUTER is None:
        from ...reasoning.rag.router import RAGRouter
        from ...reasoning.rag.engines import PgVectorRealEngine
        # Wire the REAL pgvector engine (bronze docsage corpus + curated KB via
        # stored bge-m3 embeddings) instead of the stub default. db_pool truthy
        # gates corpus/KB access; the engine uses acquire_for_tenant internally.
        try:
            from ...shared.db import get_pool
            pool = get_pool()
        except Exception:
            pool = None
        pg = PgVectorRealEngine(db_pool=pool)
        try:
            from ...reasoning.rag.engines import TraceRecallEngine
            _ROUTER = RAGRouter(pgvector=pg, trace_recall=TraceRecallEngine(_memory()))
        except Exception:
            _ROUTER = RAGRouter(pgvector=pg)
    return _ROUTER


def _memory():
    global _MEMORY
    if _MEMORY is None:
        # Persistent L3 (Postgres) so recall sees what sessions consolidate.
        from ...reasoning.memory.factory import build_memory_service
        _MEMORY = build_memory_service()
    return _MEMORY


# =========================================================================
# retrieve_evidence
# =========================================================================
class RetrieveEvidenceTool(BaseTool):
    name = "retrieve_evidence"
    description = (
        "Truy hồi bằng chứng/đoạn tài liệu liên quan tới câu hỏi từ kho RAG "
        "(tài liệu, tri thức ngành) TRƯỚC khi đưa ra kết luận hay hành động. "
        "Chỉ đọc — không ghi gì. Dùng để có cơ sở, tránh bịa."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Câu hỏi/chủ đề cần tìm bằng chứng (tiếng Việt).",
                "minLength": 1,
                "maxLength": 1000,
            },
            "max_citations": {
                "type": "integer",
                "description": "Số trích dẫn tối đa muốn lấy (mặc định 5).",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict[str, Any]:
        query = args.get("query")
        if not query or not isinstance(query, str):
            raise ValueError("query phải là string không rỗng")
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")
        max_citations = int(args.get("max_citations") or 5)

        from ...reasoning.rag.engines import RAGQuery, RAGEngineUnavailable
        rq = RAGQuery(
            tenant_id=ctx.enterprise_id,
            query_text=query,
            user_id=ctx.user_id,
            max_citations=max_citations,
            synthesize=False,   # evidence only — skip the ~50s LLM synthesis
        )
        try:
            # Restrict to document engines — memory recall is recall_memory's job.
            ans = await _router().answer(rq, whitelist=["pgvector", "pageindex", "docsage"])
        except RAGEngineUnavailable as exc:
            return {"found": 0, "engine": None, "answer": None,
                    "note": f"không có engine RAG khả dụng: {exc}", "citations": []}

        citations = [{
            "engine": c.engine_name,
            "source_id": c.source_id,
            "snippet": getattr(c, "snippet", None),
            "similarity": getattr(c, "similarity", None),  # for the critic's |OR| gate
            "node_path": list(c.node_path) if getattr(c, "node_path", None) else None,
        } for c in (ans.citations or ())]
        return {
            "found": len(citations),
            "engine": ans.engine_name,
            "answer": ans.answer,
            "citations": citations,
        }


# =========================================================================
# recall_memory
# =========================================================================
class RecallMemoryTool(BaseTool):
    name = "recall_memory"
    description = (
        "Nhớ lại kinh nghiệm/quyết định/sự kiện liên quan đã lưu trước đây của "
        "doanh nghiệp (cung điện ký ức 4 tầng). Chỉ đọc. Dùng để tận dụng những "
        "gì hệ thống đã học, không bắt đầu lại từ đầu."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Nội dung cần nhớ lại (tiếng Việt).",
                "minLength": 1,
                "maxLength": 1000,
            },
            "top_k": {
                "type": "integer",
                "description": "Số ký ức tối đa trả về (mặc định 5).",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict[str, Any]:
        query = args.get("query")
        if not query or not isinstance(query, str):
            raise ValueError("query phải là string không rỗng")
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")
        top_k = int(args.get("top_k") or 5)

        records = await _memory().retrieve(
            UUID(ctx.enterprise_id), query, top_k=top_k, min_score=_RECALL_FLOOR)
        out = [{
            "memory_type": getattr(r.memory_type, "value", str(r.memory_type)),
            "tier": getattr(r.tier, "value", str(r.tier)),
            "content": (r.content if isinstance(r.content, str) else str(r.content))[:500],
            "importance": round(float(getattr(r, "importance", 0.0) or 0.0), 3),
        } for r in records]
        return {"recalled": len(out), "memories": out}
