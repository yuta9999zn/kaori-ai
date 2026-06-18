"""
Critic agent — single LLM call that reviews the executor transcript
and emits a verdict (accept / replan / escalate).

Same plumbing as the planner (``llm_router.complete_structured`` with
output_schema) but a different prompt + output shape. Critic prompt
is workflow-defined (workflows.py renders plan + transcript into a
review request).

Hard cap on critic loops is enforced by the orchestrator's MAX_REPLAN,
not here — the critic just emits action='replan' when it thinks
another planner round would help. The orchestrator decides whether
to actually obey.
"""
from __future__ import annotations

import structlog

from ..engine.llm_router import llm_router
from .grounding_gate import assess_grounding
from .schemas import CriticVerdict, Plan, TranscriptEntry
from .workflows import Workflow

log = structlog.get_logger()


CRITIC_OUTPUT_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "reason"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["accept", "replan", "escalate"],
        },
        "reason": {
            "type": "string",
            "minLength": 1,
            "maxLength": 1500,
        },
        "issues": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "string",
                "maxLength": 200,
            },
        },
    },
}


async def review_session(
    *,
    workflow: Workflow,
    input: dict,
    plan: Plan,
    transcripts: list[TranscriptEntry],
    enterprise_id: str,
) -> CriticVerdict:
    """Run the critic LLM call. Returns parsed CriticVerdict.

    The transcript passed in includes the planner row (step_index=0)
    + every executor row, so the critic sees the full run. It does
    NOT see its own previous verdicts (Phase 2.7 — pass replan
    history when MAX_REPLAN > 1 once the prompt budget allows).
    """
    # |OR| grounding gate (ADR-0033 / RAG×harness step 2). Always computed +
    # surfaced to the LLM as a signal; ENFORCED (override) only for workflows
    # that opt in via requires_grounding.
    grounding = assess_grounding(transcripts)
    grounding_note = (
        f"\n\n[Cổng |OR| — độ phủ bằng chứng đã truy hồi]: "
        f"{grounding['coverage']:.0%} ({grounding['band']}); "
        f"{grounding['evidence_count']} trích dẫn, {grounding['memory_hits']} ký ức. "
        f"{grounding['note']}"
    )
    # Non-LLM critic: for a grounding workflow the verdict IS the |OR| gate —
    # skip the (heavy on small models) structured LLM critic entirely.
    if not getattr(workflow, "llm_critic", True):
        action = "accept" if grounding["can_generalize"] else "replan"
        log.info("agents.critic.deterministic", workflow_id=workflow.workflow_id,
                 action=action, coverage=grounding["coverage"])
        return CriticVerdict(
            action=action,
            reason=(f"Cổng |OR| (tất định): độ phủ {grounding['coverage']:.0%} "
                    f"({grounding['band']}). {grounding['note']}")[:1500],
            issues=([] if action == "accept" else ["|OR| grounding insufficient"]),
        )

    user_prompt = workflow.critic_prompt(plan, transcripts, input) + grounding_note

    log.info(
        "agents.critic.started",
        workflow_id=workflow.workflow_id,
        enterprise_id=enterprise_id,
        prompt_chars=len(user_prompt),
        transcript_steps=len(transcripts),
        grounding_coverage=grounding["coverage"],
        grounding_band=grounding["band"],
    )

    parsed = await llm_router.complete_structured(
        prompt=user_prompt,
        task=f"agent.critic.{workflow.workflow_id}",
        output_schema=CRITIC_OUTPUT_SCHEMA,
        consent_external=False,   # K-4 — Qwen local
        enterprise_id=enterprise_id,
        max_tokens=1500,
    )

    verdict = CriticVerdict.model_validate(parsed)

    # Enforce the |OR| gate: an ungrounded "accept" can't stand for a workflow
    # that requires grounding — downgrade to "replan" so the agent gathers
    # evidence. Persistent insufficiency hits MAX_REPLAN → escalate (decline),
    # which is the "DE dominates → don't hallucinate" branch (K-3).
    if (getattr(workflow, "requires_grounding", False)
            and not grounding["can_generalize"]
            and verdict.action == "accept"):
        original = verdict.action
        verdict = CriticVerdict(
            action="replan",
            reason=(
                f"Cổng |OR|: chưa đủ cơ sở ({grounding['coverage']:.0%}) để chấp "
                f"nhận — cần truy hồi thêm bằng chứng (retrieve_evidence) trước "
                f"khi kết luận. {verdict.reason}"[:1500]
            ),
            issues=(list(verdict.issues) + ["|OR| grounding insufficient"])[:10],
        )
        log.info(
            "agents.critic.grounding_override",
            workflow_id=workflow.workflow_id,
            from_action=original, to_action="replan",
            coverage=grounding["coverage"],
        )

    log.info(
        "agents.critic.completed",
        workflow_id=workflow.workflow_id,
        action=verdict.action,
        issue_count=len(verdict.issues),
    )

    return verdict
