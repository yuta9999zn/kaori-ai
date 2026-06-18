"""
Coordinator — owns the planner → executor → critic loop and the
agent_sessions / agent_transcripts persistence.

This is the only module that talks to the DB. Everything else
(planner, executor, critic, workflows, schemas) is pure logic that
takes inputs and returns outputs. That asymmetry keeps unit tests
trivial: mock the LLM router, run the orchestrator end-to-end without
a live Postgres, then a separate IT verifies the persistence.

Loop semantics
==============

::

    [PLAN] → [EXECUTE] → [CRITIC]
                            │
                            ├── action=accept   → status=completed (terminal)
                            ├── action=escalate → status=escalated (terminal)
                            └── action=replan   → back to [PLAN]
                                                  bounded by MAX_REPLAN=2;
                                                  exceeding the cap forces
                                                  status=escalated.

Token budget
============

Every LLM call increments ``agent_sessions.tokens_used``. After each
increment the orchestrator checks against ``MAX_TOKENS_PER_SESSION``
(6000 in v0). If the budget is blown the session terminates with
status='failed' and ``error_message`` records the cap.

The gateway audit row (K-3) is the source of truth for token counts.
What we track here is best-effort and intended for soft-cap enforcement,
not billing.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional
from uuid import UUID, uuid4

import jsonschema
import structlog
from jsonschema import Draft202012Validator

from ..chat.tools.base import ToolContext
from ..shared.db import acquire_for_tenant
from .critic import review_session
from .executor import execute_steps
from .planner import plan_workflow
from .registry_setup import get_agent_registry
from .schemas import (
    CriticVerdict,
    Plan,
    SessionResponse,
    TranscriptEntry,
)
from .workflows import Workflow, get_workflow

log = structlog.get_logger()


# Hard caps. v0 values; the workflow registry can override per-workflow
# in a follow-up if a particular flow needs a tighter / looser bound.
MAX_REPLAN = 2
MAX_TOKENS_PER_SESSION = 6000


class WorkflowInputError(ValueError):
    """Input shape failed JSON-schema validation."""


class TokenBudgetExceeded(RuntimeError):
    """Session blew through MAX_TOKENS_PER_SESSION."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Consolidation content budgets — tunable, never hardcoded.
_INTENT_LEN = _env_int("KAORI_MEM_CONSOLIDATE_INTENT_LEN", 200)
_EVIDENCE_MAX = _env_int("KAORI_MEM_CONSOLIDATE_MAX_EVIDENCE", 3)
_SNIPPET_LEN = _env_int("KAORI_MEM_CONSOLIDATE_SNIPPET_LEN", 160)


def _evidence_summary(transcripts: list[TranscriptEntry]) -> str:
    """Top retrieve_evidence citation snippets, trimmed — the grounding the
    session leaned on, so a recalled memory carries WHY, not just the verdict."""
    snippets: list[str] = []
    for t in transcripts:
        if getattr(t, "role", None) != "executor" or t.tool_name != "retrieve_evidence":
            continue
        res = t.tool_result if isinstance(t.tool_result, dict) else {}
        for c in (res.get("citations") or []):
            snip = (c.get("snippet") if isinstance(c, dict) else None) or ""
            snip = snip.strip()
            if snip:
                snippets.append(snip[:_SNIPPET_LEN])
            if len(snippets) >= _EVIDENCE_MAX:
                break
        if len(snippets) >= _EVIDENCE_MAX:
            break
    return " · ".join(snippets)


def _parse_actor(actor_user_id: Optional[str]) -> Optional[UUID]:
    """Parse the forwarded X-User-ID into a UUID.

    In production the gateway always forwards a UUID from the JWT, but a
    malformed header (or a direct service call) must NOT crash with a raw
    ValueError that escapes to a 500 — surface it as WorkflowInputError so
    the router returns a clean 400 RFC 7807 (K-14)."""
    if not actor_user_id:
        return None
    try:
        return UUID(actor_user_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise WorkflowInputError(
            f"X-User-ID không phải UUID hợp lệ: {actor_user_id!r}"
        ) from exc


# =========================================================================
# Public entry point
# =========================================================================


async def run_session(
    *,
    workflow_id: str,
    input: dict[str, Any],
    dry_run: bool,
    enterprise_id: str,
    actor_user_id: Optional[str],
) -> SessionResponse:
    """Execute one agent session end-to-end. Returns the final
    SessionResponse with the full transcript inlined.

    Validates the workflow + input first, then opens a session row,
    drives the loop, and finalises the row. Any exception raised
    inside the loop short-circuits to status='failed' with the
    exception text in ``error_message`` so the caller always gets
    a structured response (no 500 from the orchestrator).
    """
    workflow = get_workflow(workflow_id)
    _validate_input(input, workflow)

    session_id = uuid4()
    actor_uuid = _parse_actor(actor_user_id)

    await _insert_session(
        session_id=session_id,
        enterprise_id=enterprise_id,
        workflow_id=workflow_id,
        input=input,
        dry_run=dry_run,
        actor_user_id=actor_uuid,
    )

    transcripts: list[TranscriptEntry] = []
    tokens_used = 0
    replan_count = 0
    last_plan: Optional[Plan] = None
    last_verdict: Optional[CriticVerdict] = None
    error_message: Optional[str] = None
    final_status = "failed"

    registry = get_agent_registry()

    try:
        while True:
            # ---- PLANNER --------------------------------------------------
            await _set_status(session_id, "planning", enterprise_id)

            try:
                plan, planner_tokens = await plan_workflow(
                    workflow=workflow,
                    input=input,
                    registry=registry,
                    enterprise_id=enterprise_id,
                )
            except Exception as exc:
                log.exception(
                    "agents.orchestrator.planner_failed",
                    session_id=str(session_id),
                    error=str(exc),
                )
                error_message = f"planner_failed: {exc}"
                break

            tokens_used += planner_tokens
            last_plan = plan

            planner_step_index = len(transcripts)
            planner_entry = TranscriptEntry(
                step_index=planner_step_index,
                role="planner",
                reasoning=plan.rationale or "(no rationale)",
            )
            transcripts.append(planner_entry)
            await _insert_transcript(
                session_id=session_id,
                enterprise_id=enterprise_id,
                entry=planner_entry,
            )

            await _persist_plan(session_id, plan, enterprise_id)

            if tokens_used > MAX_TOKENS_PER_SESSION:
                error_message = (
                    f"token_budget_exceeded: {tokens_used} > "
                    f"{MAX_TOKENS_PER_SESSION}"
                )
                break

            # ---- EXECUTOR -------------------------------------------------
            await _set_status(session_id, "executing", enterprise_id)

            ctx = ToolContext(
                scope="enterprise",
                enterprise_id=enterprise_id,
                user_id=actor_user_id,
                role=None,        # role check inside registry uses scope only for enterprise tools
                dry_run=dry_run,
            )
            starting_step_index = len(transcripts)
            async for entry, _latency_ms in execute_steps(
                plan=plan,
                ctx=ctx,
                registry=registry,
                starting_step_index=starting_step_index,
            ):
                transcripts.append(entry)
                await _insert_transcript(
                    session_id=session_id,
                    enterprise_id=enterprise_id,
                    entry=entry,
                )

            # ---- CRITIC ---------------------------------------------------
            await _set_status(session_id, "critiquing", enterprise_id)

            try:
                verdict = await review_session(
                    workflow=workflow,
                    input=input,
                    plan=plan,
                    transcripts=transcripts,
                    enterprise_id=enterprise_id,
                )
            except Exception as exc:
                log.exception(
                    "agents.orchestrator.critic_failed",
                    session_id=str(session_id),
                    error=str(exc),
                )
                error_message = f"critic_failed: {exc}"
                break

            last_verdict = verdict

            critic_entry = TranscriptEntry(
                step_index=len(transcripts),
                role="critic",
                reasoning=verdict.reason,
            )
            transcripts.append(critic_entry)
            await _insert_transcript(
                session_id=session_id,
                enterprise_id=enterprise_id,
                entry=critic_entry,
            )

            await _persist_verdict(session_id, verdict, enterprise_id)

            # ---- BRANCH ---------------------------------------------------
            if verdict.action == "accept":
                final_status = "completed"
                break

            if verdict.action == "escalate":
                final_status = "escalated"
                break

            # action == "replan"
            replan_count += 1
            await _bump_replan(session_id, replan_count, enterprise_id)
            if replan_count > MAX_REPLAN:
                final_status = "escalated"
                error_message = f"max_replan_reached: {MAX_REPLAN}"
                break
            # else: loop back to planner

    except Exception as exc:
        # Belt-and-suspenders — anything we didn't catch above lands
        # here so the session row never stays in a transient state.
        log.exception(
            "agents.orchestrator.unhandled",
            session_id=str(session_id),
            error=str(exc),
        )
        error_message = f"unhandled: {exc}"
        final_status = "failed"

    await _finalise_session(
        session_id=session_id,
        status=final_status,
        tokens_used=tokens_used,
        error_message=error_message,
        enterprise_id=enterprise_id,
    )

    # RAG×harness step 3 — consolidate a SUCCESSFUL session into the memory
    # palace so recall_memory surfaces it next time (the IF-grows loop).
    # Best-effort + non-fatal: a memory write must never fail the session.
    if final_status == "completed" and last_plan is not None:
        await _consolidate_session(
            workflow_id=workflow_id, plan=last_plan, verdict=last_verdict,
            transcripts=transcripts, enterprise_id=enterprise_id,
            dry_run=dry_run, input=input,
        )

    return SessionResponse(
        session_id=session_id,
        workflow_id=workflow_id,
        status=final_status,                     # type: ignore[arg-type]
        dry_run=dry_run,
        plan=last_plan,
        transcripts=transcripts,
        critic_verdict=last_verdict,
        tokens_used=tokens_used,
        replan_count=replan_count,
        error_message=error_message,
    )


# =========================================================================
# Consolidation — write the session experience into the memory palace
# =========================================================================


async def _consolidate_session(
    *,
    workflow_id: str,
    plan: Plan,
    verdict: Optional[CriticVerdict],
    transcripts: list[TranscriptEntry],
    enterprise_id: str,
    dry_run: bool = False,
    input: Optional[dict[str, Any]] = None,
) -> None:
    """Persist an episodic memory of what this session concluded, embedded
    inline so recall_memory surfaces it on a future *similar* question. Non-fatal.

    The content carries the original question + the grounding evidence (not just
    workflow metadata) — otherwise the embedding only matches "Workflow X →
    accept" and recall returns 0 on business questions (audit 2026-06-02).

    Skipped entirely under dry_run — a dry run must produce no side effects,
    and a persisted memory IS a side effect."""
    if dry_run:
        return
    try:
        from ..reasoning.memory.factory import build_memory_service
        from ..reasoning.memory.types import MemoryType

        actions = [t.tool_name for t in transcripts
                   if t.role == "executor" and t.tool_name]
        outcome = verdict.action if verdict else "completed"
        # The intent we want future questions to match against: the explicit
        # question if the workflow has one, else the planner's rationale.
        question = ((input or {}).get("question") or "").strip()
        intent = question or (plan.rationale or "").strip() or "(không rõ)"
        evidence = _evidence_summary(transcripts)
        content = (
            f"[{workflow_id}] Hỏi: {intent[:_INTENT_LEN]} → {outcome}. "
            f"Cơ sở: {evidence or '(không có bằng chứng)'} "
            f"| Hành động: {', '.join(actions[:6]) or '(không)'}."
        )
        mem = build_memory_service()
        # OPERATIONAL (action outcome) defaults to the L3 tier — the persistent
        # Postgres store — so recall_memory surfaces it in FUTURE sessions.
        # (EPISODIC defaults to L2 in-memory → would be lost per-process.)
        rec = await mem.write(
            UUID(enterprise_id), MemoryType.OPERATIONAL, content,
            metadata={"workflow_id": workflow_id, "outcome": outcome,
                      "question": question or None},
        )
        # Embed inline (bge-m3) so semantic recall works without waiting on the
        # background embedding worker. Best-effort.
        if rec is not None and hasattr(mem.l3, "set_embedding"):
            try:
                from ..reasoning.knowledge.embed import embed_text
                vec = await embed_text(content, enterprise_id=enterprise_id)
                if vec:
                    await mem.l3.set_embedding(UUID(enterprise_id), rec.record_id, vec)
            except Exception as e:  # pragma: no cover
                log.warning("agents.orchestrator.consolidate_embed_failed", error=str(e))
        log.info("agents.orchestrator.consolidated",
                 workflow_id=workflow_id, outcome=outcome,
                 record_id=str(rec.record_id) if rec else None)
    except Exception as e:  # pragma: no cover - memory must never fail a session
        log.warning("agents.orchestrator.consolidate_failed",
                    workflow_id=workflow_id, error=str(e))


# =========================================================================
# Validation
# =========================================================================


def _validate_input(input: dict[str, Any], workflow: Workflow) -> None:
    """Validate ``input`` against the workflow's input_schema. Raises
    WorkflowInputError on failure with a list of jsonschema errors.

    ``format_checker`` is passed so the ``format: uuid`` declared on
    e.g. ``insight-to-action.input_schema.insight_id`` is enforced — by
    default jsonschema treats ``format`` as annotation-only.
    """
    validator = Draft202012Validator(
        workflow.input_schema,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(input), key=lambda e: e.path)
    if errors:
        msg_lines = [
            f"  • {'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        ]
        raise WorkflowInputError(
            f"Workflow '{workflow.workflow_id}' input invalid:\n"
            + "\n".join(msg_lines)
        )


# =========================================================================
# Persistence (only DB writes in this module)
# =========================================================================


async def _insert_session(
    *,
    session_id: UUID,
    enterprise_id: str,
    workflow_id: str,
    input: dict[str, Any],
    dry_run: bool,
    actor_user_id: Optional[UUID],
) -> None:
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            """
            INSERT INTO agent_sessions
                (session_id, enterprise_id, workflow_id, input,
                 dry_run, actor_user_id, status)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6, 'planning')
            """,
            session_id,
            UUID(enterprise_id),
            workflow_id,
            json.dumps(input),
            dry_run,
            actor_user_id,
        )


# NOTE: these persist helpers MUST run inside acquire_for_tenant(enterprise_id)
# — pilot's agent_sessions RLS casts the enterprise GUC to uuid, so a raw pool
# connection (GUC unset → "") raises "invalid uuid". The old SET LOCAL is_admin
# bypass was a no-op (SET LOCAL needs an explicit tx). See feedback:
# audit-rls-guc-raw-pool.
async def _set_status(session_id: UUID, status: str, enterprise_id: str) -> None:
    from ..shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            "UPDATE agent_sessions SET status = $1 WHERE session_id = $2",
            status, session_id,
        )


async def _persist_plan(session_id: UUID, plan: Plan, enterprise_id: str) -> None:
    from ..shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            "UPDATE agent_sessions SET plan = $1::jsonb WHERE session_id = $2",
            json.dumps(plan.model_dump()), session_id,
        )


async def _persist_verdict(session_id: UUID, verdict: CriticVerdict, enterprise_id: str) -> None:
    from ..shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            "UPDATE agent_sessions SET critic_verdict = $1::jsonb WHERE session_id = $2",
            json.dumps(verdict.model_dump()), session_id,
        )


async def _bump_replan(session_id: UUID, replan_count: int, enterprise_id: str) -> None:
    from ..shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            "UPDATE agent_sessions SET replan_count = $1 WHERE session_id = $2",
            replan_count, session_id,
        )


async def _finalise_session(
    *,
    session_id: UUID,
    status: str,
    tokens_used: int,
    error_message: Optional[str],
    enterprise_id: str,
) -> None:
    from ..shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            """
            UPDATE agent_sessions
               SET status = $1,
                   tokens_used = $2,
                   error_message = $3,
                   completed_at = NOW()
             WHERE session_id = $4
            """,
            status, tokens_used, error_message, session_id,
        )


async def _insert_transcript(
    *,
    session_id: UUID,
    enterprise_id: str,
    entry: TranscriptEntry,
) -> None:
    from ..shared.db import acquire_for_tenant
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            """
            INSERT INTO agent_transcripts
                (transcript_id, session_id, enterprise_id, step_index,
                 role, tool_name, tool_args, tool_result, tool_ok,
                 reasoning)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10)
            """,
            uuid4(),
            session_id,
            UUID(enterprise_id),
            entry.step_index,
            entry.role,
            entry.tool_name,
            json.dumps(entry.tool_args) if entry.tool_args is not None else None,
            json.dumps(entry.tool_result, default=str) if entry.tool_result is not None else None,
            entry.tool_ok,
            entry.reasoning,
        )
