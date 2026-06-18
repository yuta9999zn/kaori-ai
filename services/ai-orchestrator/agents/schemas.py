"""
Pydantic schemas — wire format + internal types for the agent loop.

The schemas are split into three layers:

  1. **Wire** (caller-facing) — ``SessionRequest`` / ``SessionResponse``.
     These are what the API gateway sees on POST /agents/sessions.
  2. **Plan** — ``PlanStep`` / ``Plan``. Output of the planner LLM,
     validated against an output_schema (Issue #3) before reaching the
     executor.
  3. **Verdict** — ``CriticVerdict``. Output of the critic LLM,
     validated against output_schema. The orchestrator branches on
     ``verdict.action`` to decide completed / escalated / replan.

Persistence shapes (``agent_sessions`` row, ``agent_transcripts`` row)
are NOT modelled here — they live in orchestrator.py as the only place
that talks to the DB. Keeping the wire schemas free of DB concerns
makes the dependency graph one-way: schemas.py → planner/executor/critic
→ orchestrator → DB.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# =========================================================================
# Wire — what the caller sends and gets back
# =========================================================================


class SessionRequest(BaseModel):
    """POST /api/v1/shared/agents/sessions body.

    ``input`` shape varies per workflow — validated against the
    workflow's input_schema (workflows.py) at the orchestrator layer
    rather than at the FastAPI surface, because the validator needs
    access to the registry. Letting the wrong shape through here would
    just bounce off the orchestrator with a 400.
    """

    workflow_id: str = Field(
        ...,
        description=(
            "ID of a built-in workflow. v0: 'insight-to-action'. "
            "Tenant-defined workflows are not supported."
        ),
        min_length=1,
        max_length=50,
    )
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow-specific input. See docs/specs/AGENT_FRAMEWORK.md.",
    )
    dry_run: bool = Field(
        default=True,
        description=(
            "When TRUE (default), action tools record what they WOULD have "
            "done but skip side-effects. Set FALSE to actually fire emails, "
            "mark customers, etc. Requires Idempotency-Key header at the "
            "router layer when FALSE."
        ),
    )


class SessionResponse(BaseModel):
    """POST /api/v1/shared/agents/sessions response body.

    A snapshot of the session at the moment the orchestrator finished.
    Status is one of the terminal values (completed | failed | escalated)
    OR a transient one if the caller polled mid-run (planning |
    executing | critiquing — only relevant for follow-up GET endpoint
    that we don't ship in PR1).
    """

    session_id: UUID
    workflow_id: str
    status: Literal[
        "planning", "executing", "critiquing",
        "completed", "failed", "escalated",
    ]
    dry_run: bool
    plan: Optional["Plan"] = None
    transcripts: list["TranscriptEntry"] = Field(default_factory=list)
    critic_verdict: Optional["CriticVerdict"] = None
    tokens_used: int = 0
    replan_count: int = 0
    error_message: Optional[str] = None


# =========================================================================
# Plan — output of the planner LLM
# =========================================================================


class PlanStep(BaseModel):
    """One executable step in the plan.

    ``tool_name`` must match a tool in the chat registry (the same
    registry the chat agent uses). ``args`` is the JSON arg payload
    the LLM produced; the executor still strips forbidden keys (K-12 /
    K-16) before dispatch.

    ``rationale`` is the planner's per-step justification. Surfaced in
    the transcript so a human auditor can see WHY the planner picked
    each step, not just what it did.
    """

    tool_name: str = Field(..., min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field("", max_length=500)


class Plan(BaseModel):
    """Planner output. The orchestrator hands this to the executor
    verbatim — no re-ordering, no per-step re-prompting.

    ``rationale`` is the planner's overall narrative ("I chose to fetch
    customer details first so I can personalise the draft email"). It
    does NOT influence execution but reads well in the transcript.
    """

    steps: list[PlanStep] = Field(..., min_length=1, max_length=10)
    rationale: str = Field("", max_length=2000)

    @field_validator("steps")
    @classmethod
    def _no_duplicate_consecutive(cls, v: list[PlanStep]) -> list[PlanStep]:
        # Cheap sanity check: catches the failure mode where a planner
        # emits the same step twice in a row (model artifact). The
        # critic would catch it but failing here saves an executor round.
        for i in range(1, len(v)):
            same_tool = v[i].tool_name == v[i - 1].tool_name
            same_args = v[i].args == v[i - 1].args
            if same_tool and same_args:
                raise ValueError(
                    f"plan step {i} duplicates the previous step "
                    f"({v[i].tool_name}); planner artefact."
                )
        return v


# =========================================================================
# Critic — verdict
# =========================================================================


class CriticVerdict(BaseModel):
    """Output of the critic LLM after it reviews the executor transcript.

    ``action`` is the routing decision. The orchestrator dispatches:
        accept    → status=completed
        replan    → loop back to planner (until MAX_REPLAN)
        escalate  → status=escalated (surface to human)

    ``reason`` is the critic's narrative — what it judged and why. It
    must be present (non-empty) regardless of the action so the
    transcript explains the verdict.
    """

    action: Literal["accept", "replan", "escalate"]
    reason: str = Field(..., min_length=1, max_length=1500)
    issues: list[str] = Field(
        default_factory=list,
        description="Specific issues spotted (each ≤ 200 chars).",
        max_length=10,
    )


# =========================================================================
# Transcript — one row per step in the response
# =========================================================================


class TranscriptEntry(BaseModel):
    """Snapshot of one ``agent_transcripts`` row, as returned by the API.

    Persistence row has more fields (latency_ms, llm_tokens, ...);
    those are shipped over the wire only when the caller asks for
    them via a follow-up detail endpoint. Keeping the response slim
    by default.
    """

    step_index: int
    role: Literal["planner", "executor", "critic"]
    tool_name: Optional[str] = None
    tool_args: Optional[dict[str, Any]] = None
    tool_result: Optional[Any] = None
    tool_ok: Optional[bool] = None
    reasoning: str = ""


# Forward refs — Pydantic v2 needs explicit rebuild after the class
# definitions above complete (Plan, CriticVerdict, TranscriptEntry are
# referenced as strings in SessionResponse).
SessionResponse.model_rebuild()
