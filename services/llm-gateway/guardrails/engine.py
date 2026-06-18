"""
P2-S23 SH-M56a — GuardrailEngine: orchestrates rules + dispatches
on-fail strategies.

Lifecycle of one call:
  router.invoke(prompt) →
    engine.run_input(prompt, ctx) → maybe-fixed prompt
    provider.invoke(prompt') →
    engine.run_output(completion, ctx) → maybe-fixed completion
    return completion'

Per-rule on_fail:
  EXCEPTION → raise GuardrailBlockedError (router → 400/403)
  REASK     → engine appends feedback to ctx.metadata['reask_feedback'],
              caller-router decides whether to round-trip the model
  FIX       → engine uses rule.fixed_text as the new prompt/completion
  NOOP      → log + persist + continue

Every failed rule writes one row to guardrail_violations (mig 082)
via violations.record_violation().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

from .on_fail import GuardrailBlockedError, OnFailAction
from .types import Layer, Rule, RuleContext, Severity, Violation
from .violations import record_violation

log = structlog.get_logger()


@dataclass
class EngineReport:
    """Outcome of one engine pass."""
    text:           str                       # possibly fixed
    violations:     list[Violation] = field(default_factory=list)
    reask_feedback: list[str]       = field(default_factory=list)
    layer:          Optional[Layer] = None


class GuardrailEngine:
    """Holds the rule registry + drives the per-call check loop."""

    def __init__(
        self,
        input_rules:  list[Rule] | None = None,
        output_rules: list[Rule] | None = None,
        *,
        persist_violations: bool = True,
    ):
        self.input_rules  = list(input_rules or [])
        self.output_rules = list(output_rules or [])
        self.persist      = persist_violations

    async def run_input(self, ctx: RuleContext) -> EngineReport:
        ctx.layer = Layer.INPUT
        return await self._run(ctx, self.input_rules)

    async def run_output(self, ctx: RuleContext) -> EngineReport:
        ctx.layer = Layer.OUTPUT
        return await self._run(ctx, self.output_rules)

    async def _run(self, ctx: RuleContext, rules: list[Rule]) -> EngineReport:
        report = EngineReport(text=ctx.text, layer=ctx.layer)

        for rule in rules:
            result = await rule.check(ctx)
            if result.passed:
                continue

            # Failed — persist + dispatch on_fail
            if result.violation is not None:
                report.violations.append(result.violation)
                if self.persist:
                    try:
                        await record_violation(
                            result.violation,
                            on_fail_action=rule.on_fail,
                        )
                    except Exception as e:   # noqa: BLE001
                        log.warning("guardrails.persist_failed",
                                    rule=rule.name, error=str(e))

            if rule.on_fail is OnFailAction.EXCEPTION:
                feedback = (
                    result.violation.rule_metadata.get("feedback")
                    if result.violation is not None else None
                )
                raise GuardrailBlockedError(
                    rule_name=rule.name,
                    reason=_short_reason(result.violation),
                    feedback=feedback,
                )

            if rule.on_fail is OnFailAction.FIX:
                if result.fixed_text is not None:
                    # Engine uses the fixed text for subsequent rules
                    report.text = result.fixed_text
                    ctx.text     = result.fixed_text
                continue

            if rule.on_fail is OnFailAction.REASK:
                feedback = _short_reason(result.violation)
                report.reask_feedback.append(f"{rule.name}: {feedback}")
                continue

            # NOOP — already logged
            log.info("guardrails.noop",
                     rule=rule.name, layer=ctx.layer,
                     severity=_severity(result.violation))
            continue

        return report


def _short_reason(v: Optional[Violation]) -> str:
    if v is None:
        return "unspecified"
    md = v.rule_metadata or {}
    if "reason" in md:
        return str(md["reason"])
    return f"{v.rule_name} violated"


def _severity(v: Optional[Violation]) -> str:
    if v is None:
        return Severity.MEDIUM.value
    return v.severity.value if hasattr(v.severity, "value") else str(v.severity)
