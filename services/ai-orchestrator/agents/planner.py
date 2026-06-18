"""
Planner agent — single LLM call that turns a workflow goal into an
ordered list of tool steps.

Uses ``llm_router.complete_structured`` (Issue #3 / PR #112) so the
gateway validates the response against the Plan JSON schema and
applies one repair round on parse failure. The planner returns a
``Plan`` (parsed via Pydantic) that the executor consumes verbatim.

K-3   — every LLM call goes through the gateway
K-4   — consent_external=False (Qwen local default for v0)
K-15  — the gateway writes its own audit row for the LLM call;
        the orchestrator additionally writes an ``agent_transcripts``
        row for the planner step (role='planner').
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from ..chat.registry import ToolRegistry
from ..engine.llm_router import llm_router
from .schemas import Plan
from .workflows import Workflow

log = structlog.get_logger()


# Output schema mirrors Plan / PlanStep so the gateway validation
# catches malformed completions before they reach Pydantic. Kept as a
# module-level constant so unit tests can introspect.
PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool_name", "args", "rationale"],
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "args": {
                        "type": "object",
                        # Args are tool-specific; enforce shape downstream
                        # in the registry's BaseTool.execute validators.
                    },
                    "rationale": {
                        "type": "string",
                        "maxLength": 500,
                    },
                },
            },
        },
        "rationale": {
            "type": "string",
            "maxLength": 2000,
        },
    },
    "required": ["steps", "rationale"],
}


def _render_tools_section(
    registry: ToolRegistry,
    allowed_tools: frozenset[str],
) -> str:
    """Build the prompt's "available tools" block. Lists only tools
    the workflow whitelists, not the full enterprise catalog. Each
    entry: name + description + parameters schema."""
    lines: list[str] = ["Tool có sẵn:"]
    for tool in registry.list_for_scope("enterprise"):
        if tool.name not in allowed_tools:
            continue
        params_json = json.dumps(tool.parameters or {}, ensure_ascii=False)
        lines.append(
            f"  • {tool.name} — {tool.description}\n"
            f"      params: {params_json}"
        )
    if len(lines) == 1:
        # No tool matched workflow's allowlist. Surface this as a
        # config error rather than silently returning an empty plan.
        raise RuntimeError(
            "Planner has no tools to choose from — workflow allowed_tools "
            "intersected with the registry catalog is empty."
        )
    return "\n".join(lines)


async def plan_workflow(
    *,
    workflow: Workflow,
    input: dict[str, Any],
    registry: ToolRegistry,
    enterprise_id: str,
) -> tuple[Plan, int]:
    """Run the planner LLM call. Returns (plan, tokens_used).

    Tokens are best-effort: the gateway response shape exposes them
    when the upstream provider supplies usage stats; for Qwen local
    we count tokens at the gateway and propagate. If the field is
    missing we return 0 — the orchestrator's running sum still works,
    just less precise.
    """
    # Non-LLM path: a workflow with a fixed plan skips the (heavy, on small
    # models flaky) structured LLM planner. Still validated against the allowlist.
    if getattr(workflow, "static_plan", None) is not None:
        plan = Plan(steps=workflow.static_plan(input),
                    rationale="(static plan — no LLM planner)")
        for i, step in enumerate(plan.steps):
            if step.tool_name not in workflow.allowed_tools:
                raise ValueError(
                    f"Static plan step {i + 1} tool '{step.tool_name}' not in "
                    f"workflow '{workflow.workflow_id}' allowed_tools.")
        log.info("agents.planner.static", workflow_id=workflow.workflow_id,
                 steps=[s.tool_name for s in plan.steps])
        return plan, 0

    tools_block = _render_tools_section(registry, workflow.allowed_tools)
    user_prompt = (
        f"{workflow.planner_prompt(input)}\n"
        "\n"
        f"{tools_block}"
    )

    log.info(
        "agents.planner.started",
        workflow_id=workflow.workflow_id,
        enterprise_id=enterprise_id,
        prompt_chars=len(user_prompt),
    )

    parsed = await llm_router.complete_structured(
        prompt=user_prompt,
        task=f"agent.plan.{workflow.workflow_id}",
        output_schema=PLAN_OUTPUT_SCHEMA,
        # K-4: agent v0 is Qwen-local only. Same rationale as chat
        # (CLAUDE.md §8 Rule 7 — extend to chat-style scopes). External
        # chat / agent unlocks behind a separate consent flag in Phase 2.
        consent_external=False,
        enterprise_id=enterprise_id,
        max_tokens=2000,
    )

    # Pydantic enforces the additional invariants that JSON Schema
    # alone can't (no two consecutive identical steps, etc).
    plan = Plan.model_validate(parsed)

    # Cross-check: every tool the planner picked must actually be in
    # the workflow allowlist. The output_schema doesn't enforce this
    # because the allowed set varies per workflow.
    for i, step in enumerate(plan.steps):
        if step.tool_name not in workflow.allowed_tools:
            raise ValueError(
                f"Planner picked tool '{step.tool_name}' (step {i + 1}) "
                f"which is not in workflow '{workflow.workflow_id}' "
                f"allowed_tools={sorted(workflow.allowed_tools)}."
            )

    log.info(
        "agents.planner.completed",
        workflow_id=workflow.workflow_id,
        step_count=len(plan.steps),
    )

    # Token attribution — the gateway returns the upstream usage when
    # available. complete_structured strips this from its return so we
    # log it server-side instead of round-tripping. v0 returns 0 here
    # and lets the gateway audit row carry the precise number.
    return plan, 0
