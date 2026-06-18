"""
P2-S23 SH-M56a-007..011 — generic output-layer guardrail rules.

  007 ValidJson schema enforcement
  008 ValidLength min/max
  009 ToxicLanguage output side (stricter threshold 0.5)
  010 ProfanityFree
  011 CompetitorCheck — don't mention configured competitor names

For Kaori-specific output rules (012-016), see kaori_rules.py.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .input_rules import score_toxic
from .on_fail import OnFailAction
from .types import Layer, Rule, RuleContext, RuleResult, Severity, Violation


# ─── 007 — JSON schema ───────────────────────────────────────────────


class ValidJsonRule(Rule):
    """SH-M56a-007 — completion must parse as JSON and (optionally)
    validate against tenant_config['output_schema']. Pairs with
    output_validator.py's repair-once logic upstream — this rule is
    the post-repair gate."""
    name = "valid_json"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.EXCEPTION)
        self.layer = Layer.OUTPUT
        self.severity = Severity.HIGH

    async def check(self, ctx: RuleContext) -> RuleResult:
        if ctx.parsed_output is not None:
            obj: Any = ctx.parsed_output
        else:
            try:
                obj = json.loads(ctx.text)
            except Exception as e:   # noqa: BLE001
                return RuleResult(
                    passed=False,
                    violation=Violation(
                        rule_name=self.name,
                        layer=Layer.OUTPUT,
                        severity=self.severity,
                        enterprise_id=ctx.enterprise_id,
                        user_id=ctx.user_id,
                        request_id=ctx.request_id,
                        model_id=ctx.model_id,
                        offending_excerpt=ctx.text[:200],
                        rule_metadata={
                            "reason":    "completion is not valid JSON",
                            "parse_err": str(e)[:150],
                        },
                    ),
                )

        schema = ctx.tenant_config.get("output_schema")
        if not schema:
            return RuleResult(passed=True)
        try:
            from jsonschema import Draft202012Validator
            validator = Draft202012Validator(schema)
            errs = list(validator.iter_errors(obj))
        except Exception as e:   # noqa: BLE001
            return RuleResult(
                passed=False,
                violation=Violation(
                    rule_name=self.name,
                    layer=Layer.OUTPUT,
                    severity=self.severity,
                    enterprise_id=ctx.enterprise_id,
                    user_id=ctx.user_id,
                    request_id=ctx.request_id,
                    model_id=ctx.model_id,
                    offending_excerpt=ctx.text[:200],
                    rule_metadata={
                        "reason":     "schema validator failed",
                        "schema_err": str(e)[:150],
                    },
                ),
            )
        if not errs:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":     "JSON does not match schema",
                    "n_errors":   len(errs),
                    "first_err":  errs[0].message[:200],
                    "feedback":   "Return ONLY JSON matching the schema.",
                },
            ),
        )


# ─── 008 — Length ────────────────────────────────────────────────────


class OutputLengthRule(Rule):
    """SH-M56a-008 — min/max char count on completions. Defaults
    forgiving (min=1, max=64_000)."""
    name = "output_length"

    def __init__(self, *, min_chars: int = 1, max_chars: int = 64_000,
                 on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.LOW
        self.min_chars = min_chars
        self.max_chars = max_chars

    async def check(self, ctx: RuleContext) -> RuleResult:
        cfg = ctx.tenant_config or {}
        mn = int(cfg.get("output_min_chars", self.min_chars))
        mx = int(cfg.get("output_max_chars", self.max_chars))
        n = len(ctx.text)
        if mn <= n <= mx:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=None,
                rule_metadata={
                    "reason":     f"output length {n} not in [{mn}, {mx}]",
                    "n_chars":    n,
                    "min":        mn,
                    "max":        mx,
                    "feedback":   "Adjust length to within the configured bounds.",
                },
            ),
        )


# ─── 009 — Toxic output (stricter 0.5 default) ───────────────────────


class ToxicLanguageOutputRule(Rule):
    """SH-M56a-009 — output toxicity threshold 0.5 (stricter than input
    0.7 since completions are user-facing)."""
    name = "toxic_output"

    def __init__(self, *, threshold: float = 0.5,
                 on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.HIGH
        self.threshold = threshold

    async def check(self, ctx: RuleContext) -> RuleResult:
        score = score_toxic(ctx.text)
        if score < self.threshold:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":     f"toxicity score {score:.2f} >= {self.threshold:.2f}",
                    "score":      score,
                    "threshold":  self.threshold,
                    "feedback":   "Avoid offensive language; rephrase neutrally.",
                },
            ),
        )


# ─── 010 — Profanity-free (zero tolerance — any match = fail) ────────


_PROFANITY_TERMS = [
    "địt mẹ", "đm", "shit", "fuck", "bullshit",
]


class ProfanityFreeRule(Rule):
    """SH-M56a-010 — any profanity match blocks the response."""
    name = "profanity_free"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.HIGH

    async def check(self, ctx: RuleContext) -> RuleResult:
        t = ctx.text.lower()
        matched = [w for w in _PROFANITY_TERMS if w in t]
        if not matched:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":  "profanity detected",
                    "matched": matched,
                    "feedback": "Remove profanity and rephrase professionally.",
                },
            ),
        )


# ─── 011 — Competitor check ──────────────────────────────────────────


class CompetitorCheckRule(Rule):
    """SH-M56a-011 — don't mention any tenant-configured competitor.
    Tenant supplies `tenant_config['competitors']` as a list of names."""
    name = "competitor_check"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.FIX)
        self.layer = Layer.OUTPUT
        self.severity = Severity.MEDIUM

    async def check(self, ctx: RuleContext) -> RuleResult:
        competitors: list[str] = (ctx.tenant_config or {}).get("competitors") or []
        if not competitors:
            return RuleResult(passed=True)
        t_lower = ctx.text.lower()
        matched = [c for c in competitors if c.lower() in t_lower]
        if not matched:
            return RuleResult(passed=True)
        # FIX strategy: mask competitor names with [redacted]
        fixed = ctx.text
        for c in matched:
            import re
            fixed = re.sub(re.escape(c), "[competitor]", fixed,
                           flags=re.IGNORECASE)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":   "competitor mentioned",
                    "matched":  matched,
                },
            ),
            fixed_text=fixed,
        )
