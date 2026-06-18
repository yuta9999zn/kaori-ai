"""
Executor — dispatches each plan step through the chat tool registry.

Reuses ``ToolRegistry.dispatch`` so the K-12 forbidden-arg check, the
scope gate, and the K-15 audit row are enforced identically to the
chat agent. The only addition here is the per-step ``agent_transcripts``
row written alongside, which the orchestrator owns.

Behaviour per step:
    1. registry.dispatch(name, args, ctx) — async, returns (ok, payload)
       Raises ToolDispatchError on auth/arg violations.
    2. Build a TranscriptEntry capturing the result.
    3. Yield (entry, latency_ms) so the orchestrator can persist + run
       the next step (sequential — no parallel dispatch in v0).

This module is intentionally THIN — most of the work is in the
registry. Keeping the executor small means every code path is easy
to reason about when an agent run goes wrong.
"""
from __future__ import annotations

import time
from typing import AsyncIterator

import structlog

from ..chat.registry import ToolDispatchError, ToolRegistry
from ..chat.tools.base import ToolContext
from .schemas import Plan, PlanStep, TranscriptEntry

log = structlog.get_logger()


async def execute_steps(
    *,
    plan: Plan,
    ctx: ToolContext,
    registry: ToolRegistry,
    starting_step_index: int = 1,
) -> AsyncIterator[tuple[TranscriptEntry, int]]:
    """Run each step in order. Yield (transcript_entry, latency_ms).

    ``starting_step_index`` lets the orchestrator number transcript
    rows correctly when the planner is replanned mid-session — the
    first executor entry of run #2 picks up where #1 left off so the
    transcript table's ``UNIQUE(session_id, step_index)`` constraint
    doesn't collide.

    Stops on the FIRST hard failure (ToolDispatchError) — those are
    auth violations, not tool errors, so continuing would be unsafe.
    Tool-side errors (the tool returned ok=False) DO continue;
    the critic decides whether they invalidate the run.
    """
    for offset, step in enumerate(plan.steps):
        step_index = starting_step_index + offset
        entry, latency_ms = await _execute_one(step, ctx, registry, step_index)
        yield entry, latency_ms

        # Hard stop on a registry-side ``raise`` (auth/scope violation).
        # Tool-side ok=False is fine — keep going.
        if entry.reasoning.startswith("[BLOCKED]"):
            log.warning(
                "agents.executor.hard_block",
                step_index=step_index,
                tool=entry.tool_name,
                reasoning=entry.reasoning,
            )
            return


async def _execute_one(
    step: PlanStep,
    ctx: ToolContext,
    registry: ToolRegistry,
    step_index: int,
) -> tuple[TranscriptEntry, int]:
    """Dispatch ONE step and pack the transcript entry."""
    started = time.monotonic()

    log.info(
        "agents.executor.step_started",
        step_index=step_index,
        tool=step.tool_name,
        dry_run=ctx.dry_run,
    )

    tool_ok: bool
    tool_result: object
    reasoning: str

    try:
        tool_ok, tool_result = await registry.dispatch(
            name=step.tool_name,
            args=step.args,
            ctx=ctx,
        )
        reasoning = (
            f"dispatched ok={tool_ok} dry_run={ctx.dry_run} "
            f"rationale={step.rationale[:120] or '(none)'}"
        )
    except ToolDispatchError as exc:
        # Hard auth / scope / forbidden-arg violation. Don't continue
        # the plan — the orchestrator will surface this to the critic
        # which will likely escalate.
        tool_ok = False
        tool_result = {"error": str(exc)}
        reasoning = f"[BLOCKED] {exc}"
        log.warning(
            "agents.executor.dispatch_blocked",
            step_index=step_index,
            tool=step.tool_name,
            reason=str(exc),
        )

    latency_ms = int((time.monotonic() - started) * 1000)

    entry = TranscriptEntry(
        step_index=step_index,
        role="executor",
        tool_name=step.tool_name,
        tool_args=step.args,
        tool_result=tool_result,
        tool_ok=tool_ok,
        reasoning=reasoning,
    )
    return entry, latency_ms
