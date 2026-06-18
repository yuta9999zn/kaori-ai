"""
Built-in workflow catalog. Workflows are code-only — a tenant cannot
register a new one by writing to ``agent_sessions.workflow_id``; the
orchestrator validates against ``WORKFLOWS`` here before doing
anything else.

A workflow defines:

* ``workflow_id``        — string identifier (matches the FK in
                           agent_sessions.workflow_id)
* ``description``        — short Vietnamese / English label
* ``input_schema``       — JSONSchema validated against
                           ``SessionRequest.input`` before planning
* ``allowed_tools``      — subset of the chat registry's enterprise
                           tools the planner is allowed to choose
                           from; everything else is invisible
* ``planner_prompt``     — function that builds the planner's user
                           prompt from validated input
* ``critic_prompt``      — function that builds the critic's user
                           prompt from the executed plan + transcript

v0 ships ONE workflow: ``insight-to-action``. The next two on the
roadmap are ``data-quality-check`` and ``retention-campaign-draft``;
they're follow-up PRs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .schemas import Plan, PlanStep, TranscriptEntry


# =========================================================================
# Workflow definition shape
# =========================================================================


@dataclass(frozen=True)
class Workflow:
    """Static workflow descriptor. Frozen so the catalog can't be
    mutated at runtime by accident."""

    workflow_id: str
    description: str
    input_schema: dict[str, Any]
    allowed_tools: frozenset[str]
    planner_prompt: Callable[[dict[str, Any]], str]
    critic_prompt: Callable[[Plan, list[TranscriptEntry], dict[str, Any]], str]
    # RAG×harness step 2 — when True, the critic enforces the |OR| grounding
    # gate: an ungrounded "accept" is downgraded to "replan" (gather evidence);
    # persistent insufficiency escalates (decline, no hallucination). Default
    # False so existing workflows are unaffected.
    requires_grounding: bool = False
    # Non-LLM harness paths (lets a deterministic, evidence-gathering workflow
    # run on a small local model where structured LLM planning/critique is too
    # heavy). static_plan: fixed plan, skip the LLM planner. llm_critic=False:
    # the critic verdict comes straight from the |OR| gate, skip the LLM critic.
    static_plan: Optional[Callable[[dict[str, Any]], list]] = None
    llm_critic: bool = True


# =========================================================================
# Workflow #1 — insight-to-action
# =========================================================================
#
# Input  : { insight_id: <uuid of a decision_audit_log row> }
# Goal   : turn an at-risk insight (e.g. "5 customers at-risk") into a
#          drafted follow-up + a "mark for human review" record so a
#          MANAGER can review before sending.
# Tools  : read = summarize_recent_decisions, get_top_at_risk_customers
#          action = draft_followup_email, mark_customer_for_review
#

_INSIGHT_TO_ACTION_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "insight_id": {
            "type": "string",
            "format": "uuid",
            "description": (
                "UUID of a decision_audit_log row that surfaced an at-risk "
                "customer cohort. The planner uses tool calls to fetch the "
                "row's details rather than receiving them inline (keeps "
                "input small + lets the executor's audit row carry the read)."
            ),
        },
    },
    "required": ["insight_id"],
    "additionalProperties": False,
}


_INSIGHT_TO_ACTION_ALLOWED_TOOLS = frozenset({
    # Read-side (Sprint 8 chat tools)
    "summarize_recent_decisions",
    "get_top_at_risk_customers",
    # Action-side (this PR)
    "draft_followup_email",
    "mark_customer_for_review",
})


def _insight_to_action_planner_prompt(input: dict[str, Any]) -> str:
    """Planner sees the insight_id + tool catalog, must produce a plan
    that fetches context first then drafts an action.

    We deliberately don't pre-fetch the insight inside the orchestrator
    and inline it here; making the planner ask for it via a tool keeps
    the audit trail honest (the executor's transcripts carry every read).
    """
    insight_id = input["insight_id"]
    return (
        "Bạn là Kaori — agent lập kế hoạch cho doanh nghiệp.\n"
        "\n"
        f"Insight cần xử lý: ID={insight_id}\n"
        "\n"
        "Mục tiêu workflow 'insight-to-action': biến insight này thành "
        "hành động cụ thể (draft follow-up email + đánh dấu KH cần review). "
        "AI không tự gửi email — chỉ chuẩn bị bản nháp để MANAGER duyệt.\n"
        "\n"
        "Hãy xây kế hoạch tuần tự bằng các tool có sẵn. Quy ước:\n"
        "  • Tool đọc trước, tool hành động sau.\n"
        "  • Tối đa 6 bước.\n"
        "  • Mỗi bước có rationale ngắn (≤ 1 câu).\n"
        "  • KHÔNG gọi cùng tool 2 lần liên tiếp với cùng tham số.\n"
        "  • TUYỆT ĐỐI không tự thêm enterprise_id / tenant_id / user_id "
        "vào args (sẽ bị registry từ chối).\n"
        "\n"
        "Trả về JSON đúng schema. Không thêm văn bản ngoài JSON."
    )


def _insight_to_action_critic_prompt(
    plan: Plan,
    transcripts: list[TranscriptEntry],
    input: dict[str, Any],
) -> str:
    """Critic gets the plan + executor transcript and must verdict.

    We render the transcript compactly (one line per step) so the
    critic can hold the full picture in context. Long tool results
    are truncated — the critic doesn't need byte-perfect data, it
    needs to judge the SHAPE of the run.
    """
    plan_render = "\n".join(
        f"  {i + 1}. {step.tool_name}({json.dumps(step.args, ensure_ascii=False)}) "
        f"— {step.rationale or '(no rationale)'}"
        for i, step in enumerate(plan.steps)
    )

    transcript_render = "\n".join(
        f"  step {t.step_index} [{t.role}] "
        f"tool={t.tool_name or '-'} ok={t.tool_ok} "
        f"reasoning={t.reasoning[:120] or '(empty)'}"
        for t in transcripts
    )

    insight_id = input.get("insight_id", "(unknown)")

    return (
        "Bạn là Kaori — critic đánh giá kết quả của agent loop.\n"
        "\n"
        f"Workflow đã chạy: insight-to-action cho insight_id={insight_id}\n"
        "\n"
        "Kế hoạch ban đầu:\n"
        f"{plan_render}\n"
        "\n"
        "Transcript thực thi:\n"
        f"{transcript_render}\n"
        "\n"
        "Hãy đánh giá:\n"
        "  1. Plan có hoàn thành mục tiêu workflow không? "
        "(tức là đã có draft email + mark for review chưa)\n"
        "  2. Có bước nào fail mà cần replan không?\n"
        "  3. Có dấu hiệu PII leak hoặc làm sai phạm phạm vi không?\n"
        "\n"
        "Trả verdict JSON với:\n"
        "  • action='accept'   — kế hoạch đã chạy ổn, cho phép completed.\n"
        "  • action='replan'   — có gap khắc phục được, planner sẽ chạy lại.\n"
        "  • action='escalate' — cần con người vào (gãy bất thường, "
        "PII leak, chính sách vi phạm).\n"
        "  • reason     — lý do verdict (≤ 2 câu, tiếng Việt).\n"
        "  • issues[]   — list cụ thể (mỗi issue ≤ 200 ký tự).\n"
        "\n"
        "Không thêm văn bản ngoài JSON."
    )


_INSIGHT_TO_ACTION = Workflow(
    workflow_id="insight-to-action",
    description="Biến insight at-risk thành draft email + mark for review",
    input_schema=_INSIGHT_TO_ACTION_INPUT_SCHEMA,
    allowed_tools=_INSIGHT_TO_ACTION_ALLOWED_TOOLS,
    planner_prompt=_insight_to_action_planner_prompt,
    critic_prompt=_insight_to_action_critic_prompt,
)


# =========================================================================
# Workflow #2 — grounded-advisory  (RAG×harness e2e)
# =========================================================================
#
# Input : { question: <câu hỏi nghiệp vụ tiếng Việt> }
# Goal  : trả lời câu hỏi CÓ CƠ SỞ — gather evidence (retrieve_evidence từ tri
#         thức ngành + recall_memory kinh nghiệm cũ) rồi để critic |OR| gate
#         quyết: đủ cơ sở → accept; thiếu → replan; DE áp đảo → escalate
#         (từ chối, không bịa). requires_grounding=True bật cổng cưỡng chế.
# Tools : retrieve_evidence, recall_memory (read-only — đây là workflow grounding).

_GROUNDED_ADVISORY_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "minLength": 3,
            "maxLength": 1000,
            "description": "Câu hỏi nghiệp vụ cần trả lời có cơ sở.",
        },
    },
    "required": ["question"],
    "additionalProperties": False,
}

_GROUNDED_ADVISORY_ALLOWED_TOOLS = frozenset({"retrieve_evidence", "recall_memory"})


def _grounded_advisory_planner_prompt(input: dict[str, Any]) -> str:
    question = input["question"]
    return (
        "Bạn là Kaori — agent trả lời câu hỏi nghiệp vụ CÓ CƠ SỞ.\n\n"
        f"Câu hỏi: {question}\n\n"
        "Trước khi kết luận, PHẢI thu thập bằng chứng. Lập kế hoạch tuần tự:\n"
        "  • retrieve_evidence(query=...) — lấy tri thức ngành liên quan.\n"
        "  • recall_memory(query=...) — nhớ lại kinh nghiệm/quyết định cũ (nếu hữu ích).\n"
        "  • Tối đa 4 bước; mỗi bước rationale ngắn.\n"
        "  • KHÔNG tự thêm enterprise_id/tenant_id/user_id vào args.\n\n"
        "Trả JSON đúng schema, không thêm văn bản ngoài JSON."
    )


def _grounded_advisory_critic_prompt(
    plan: Plan, transcripts: list[TranscriptEntry], input: dict[str, Any],
) -> str:
    transcript_render = "\n".join(
        f"  step {t.step_index} [{t.role}] tool={t.tool_name or '-'} ok={t.tool_ok}"
        for t in transcripts
    )
    return (
        "Bạn là Kaori — critic đánh giá độ CÓ CƠ SỞ của câu trả lời.\n\n"
        f"Câu hỏi: {input.get('question', '(?)')}\n\n"
        f"Transcript:\n{transcript_render}\n\n"
        "Đánh giá: agent đã thu đủ bằng chứng để trả lời câu hỏi chưa?\n"
        "  • action='accept'   — đủ bằng chứng, trả lời được.\n"
        "  • action='replan'   — thiếu bằng chứng, cần truy hồi thêm.\n"
        "  • action='escalate' — không có cơ sở nào liên quan.\n"
        "(Lưu ý: hệ thống cũng áp cổng |OR| khách quan dựa trên độ phủ bằng chứng.)\n"
        "Trả verdict JSON {action, reason, issues[]}. Không thêm văn bản ngoài JSON."
    )


def _grounded_advisory_static_plan(input: dict[str, Any]) -> list:
    """Deterministic plan — gathering evidence is a fixed pipeline, no LLM
    planner needed. Runs reliably on a small local model."""
    q = input["question"]
    return [
        PlanStep(tool_name="retrieve_evidence",
                 args={"query": q}, rationale="Thu tri thức ngành liên quan."),
        PlanStep(tool_name="recall_memory",
                 args={"query": q}, rationale="Nhớ lại kinh nghiệm/quyết định cũ."),
    ]


_GROUNDED_ADVISORY = Workflow(
    workflow_id="grounded-advisory",
    description="Trả lời câu hỏi nghiệp vụ có cơ sở (RAG + |OR| gate)",
    input_schema=_GROUNDED_ADVISORY_INPUT_SCHEMA,
    allowed_tools=_GROUNDED_ADVISORY_ALLOWED_TOOLS,
    planner_prompt=_grounded_advisory_planner_prompt,
    critic_prompt=_grounded_advisory_critic_prompt,
    requires_grounding=True,
    # Non-LLM: fixed evidence-gathering plan + |OR|-gate verdict → runs on 7B.
    static_plan=_grounded_advisory_static_plan,
    llm_critic=False,
)


# =========================================================================
# Catalog
# =========================================================================


WORKFLOWS: dict[str, Workflow] = {
    _INSIGHT_TO_ACTION.workflow_id: _INSIGHT_TO_ACTION,
    _GROUNDED_ADVISORY.workflow_id: _GROUNDED_ADVISORY,
}


def get_workflow(workflow_id: str) -> Workflow:
    """Lookup helper. Raises KeyError with a friendly message listing
    the available workflows so the caller's error response is useful."""
    wf = WORKFLOWS.get(workflow_id)
    if wf is None:
        available = ", ".join(sorted(WORKFLOWS.keys())) or "(none)"
        raise KeyError(
            f"Workflow '{workflow_id}' không tồn tại. "
            f"Có sẵn: {available}."
        )
    return wf
