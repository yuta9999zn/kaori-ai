"""
Strategy & AI router.
POST /api/v1/strategy/ask    — deterministic framework routing (K-10)
POST /api/v1/ai/query        — free-form AI question with data context
GET  /api/v1/ai/recommendations — top 3 data-driven recommendations
"""
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..agents.framework_router import route_framework, FRAMEWORK_PROMPTS
from ..engine.llm_router import llm_router
from ..shared.db import acquire_for_tenant

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    run_id: str | None = None
    consent_external: bool = False


class AIQueryRequest(BaseModel):
    question: str
    data_context: str = ""          # Caller provides a short data summary
    consent_external: bool = False


# ── POST /api/v1/strategy/ask ─────────────────────────────────────────────────

@router.post("/strategy/ask")
async def strategy_ask(
    body: AskRequest,
    x_enterprise_id: Annotated[str, Header()],
    x_user_id: Annotated[str, Header()],
):
    """
    Route question to exactly 1 framework (K-10), run it, return structured result.
    """
    framework = route_framework(body.question)

    data_context = ""
    if body.run_id:
        data_context = await _load_data_context(body.run_id, x_enterprise_id)

    prompt_template = FRAMEWORK_PROMPTS.get(framework, FRAMEWORK_PROMPTS["5w1h"])
    prompt = prompt_template.format(
        question=body.question,
        data_context=data_context or "Không có dữ liệu cụ thể.",
    )

    answer = await llm_router.complete(
        prompt=prompt,
        task=f"strategy_{framework}",
        consent_external=body.consent_external,
        enterprise_id=x_enterprise_id,
    )

    return {
        "framework": framework,
        "question": body.question,
        "answer": answer,
    }


# ── POST /api/v1/ai/query ─────────────────────────────────────────────────────

@router.post("/ai/query")
async def ai_query(
    body: AIQueryRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """Free-form AI question — does NOT route to a named framework."""
    prompt = (
        f"Câu hỏi từ người dùng: {body.question}\n\n"
        f"Ngữ cảnh dữ liệu: {body.data_context or 'Không có.'}\n\n"
        "Hãy trả lời ngắn gọn, thực tế bằng tiếng Việt."
    )
    answer = await llm_router.complete(
        prompt=prompt,
        task="ai_freeform",
        consent_external=body.consent_external,
        enterprise_id=x_enterprise_id,
    )
    return {"answer": answer}


# ── GET /api/v1/ai/recommendations ───────────────────────────────────────────

@router.get("/ai/recommendations")
async def recommendations(
    x_enterprise_id: Annotated[str, Header()],
    run_id: str | None = None,
):
    """
    Return top 3 data-driven recommendations based on latest analysis results.
    """
    # Get latest completed analysis run
    async with acquire_for_tenant(x_enterprise_id) as conn:
        run_row = await conn.fetchrow("""
            SELECT id, overview, templates, completed_at
            FROM analysis_runs
            WHERE enterprise_id = $1 AND status = 'done'
            ORDER BY completed_at DESC
            LIMIT 1
        """, x_enterprise_id)

    if not run_row:
        return {"recommendations": [], "note": "Chưa có kết quả phân tích."}

    overview = run_row["overview"] or {}
    narrative = overview.get("narrative", "")
    templates = run_row["templates"] or []

    prompt = (
        f"Dựa trên kết quả phân tích dữ liệu (phân tích: {', '.join(templates)}):\n"
        f"{narrative}\n\n"
        "Hãy đề xuất đúng 3 hành động cụ thể, ưu tiên theo tác động kinh doanh.\n"
        "Format: 1. ... | 2. ... | 3. ...\n"
        "Mỗi hành động ≤ 20 từ. Bằng tiếng Việt."
    )

    answer = await llm_router.complete(
        prompt=prompt,
        task="recommendations",
        enterprise_id=x_enterprise_id,
    )

    # Parse numbered list
    recs = [line.strip().lstrip("123. ") for line in answer.split("|") if line.strip()]

    return {
        "recommendations": recs[:3],
        "based_on_run_id": str(run_row["id"]),
    }


# ── Helper ────────────────────────────────────────────────────────────────────

async def _load_data_context(run_id: str, enterprise_id: str) -> str:
    """Build a brief text summary of the Silver data for the LLM prompt."""
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow("""
            SELECT row_count, quality_score, column_summary
            FROM pipeline_runs
            WHERE id = $1 AND enterprise_id = $2
        """, run_id, enterprise_id)
    if not row:
        return ""
    return (
        f"Dataset: {row['row_count']} hàng, "
        f"quality={row['quality_score']}, "
        f"cột: {row['column_summary'] or 'không rõ'}"
    )
