"""Orchestrate a workflow-advisor run (ADR-0040): profile → detect → narrate.

Findings are deterministic (detectors). Qwen only writes a short Vietnamese
executive summary GROUNDED on those findings (K-3 / ADR-0033 — it must not
invent issues). Narrative is best-effort: if Qwen is down we still return the
rule findings (model='rules-only').
"""
from __future__ import annotations

from uuid import UUID

import structlog

from . import detectors
from . import profile as profile_mod
from .schema import overall_health

log = structlog.get_logger()


async def evaluate(conn, workflow_id: UUID, enterprise_id, *, with_narrative: bool = True) -> dict | None:
    """Run the advisor; returns the review payload or None if workflow missing."""
    prof = await profile_mod.build_profile(conn, workflow_id)
    if not prof:
        return None

    findings = detectors.run_all(prof)
    # high severity first so the FE + narrative lead with what matters
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))

    health = overall_health(findings)
    run_mode = "runtime" if prof.get("runtime") else "static"
    model = "rules-only"
    narrative = None

    if with_narrative and findings:
        narrative = await _narrate(prof, findings, enterprise_id, workflow_id)
        if narrative:
            model = "qwen2.5-local"

    return {
        "run_mode": run_mode,
        "model": model,
        "overall_health": health,
        "findings": findings,
        "narrative": narrative,
    }


async def narrate(workflow_id: UUID, enterprise_id, findings: list[dict]) -> str | None:
    """Best-effort Qwen narrative for an already-computed finding set.

    Self-manages a short DB connection (just to rebuild the profile for the
    workflow name) and RELEASES it before the slow LLM call — callers run
    this as a second phase AFTER the rules-only review is already stored, so
    a slow/failing Qwen (pilot 7B) never holds the findings hostage. Returns
    None when Qwen is down/slow; callers keep the rules-only row.
    """
    if not findings:
        return None
    from ...shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        prof = await profile_mod.build_profile(conn, workflow_id)
    if not prof:
        return None
    return await _narrate(prof, findings, enterprise_id, workflow_id)


_PROMPT = """Bạn là trợ lý phân tích quy trình. Dưới đây là các vấn đề ĐÃ ĐƯỢC PHÁT HIỆN \
(bằng luật, không phải bạn tự nghĩ ra) cho workflow "{name}" ({health:.0%} sức khoẻ).

CHỈ được tóm tắt và sắp xếp ưu tiên các vấn đề trong danh sách — TUYỆT ĐỐI không \
thêm vấn đề mới, không bịa bước. Viết 2-4 câu tiếng Việt cho người quản lý: tình \
trạng tổng thể + 1-2 việc nên làm trước. Ngắn gọn, không liệt kê lại từng dòng.

Các vấn đề:
{findings}
"""


async def _narrate(prof: dict, findings: list[dict], enterprise_id, workflow_id) -> str | None:
    try:
        # 3 dots: workflow_advisor → reasoning → ai_orchestrator → engine
        from ...engine.llm_router import llm_router, NARRATIVE_MAX_TOKENS
    except Exception:
        return None

    lines = "\n".join(
        f"- [{f['severity']}] {f['title']}: {f['detail']}" for f in findings[:12]
    )
    prompt = _PROMPT.format(
        name=prof.get("name", ""),
        health=overall_health(findings),
        findings=lines,
    )
    try:
        text = await llm_router.complete(
            prompt=prompt,
            task="workflow_advisor_narrative",
            consent_external=False,            # Qwen local only (K-4) — structure, no PII
            enterprise_id=str(enterprise_id),
            run_id=str(workflow_id),
            max_tokens=NARRATIVE_MAX_TOKENS,
        )
        return text.strip() if text and text.strip() else None
    except Exception as e:  # pragma: no cover - network/LLM degrade
        log.warning("advisor.narrative_failed", workflow_id=str(workflow_id), error=str(e))
        return None
