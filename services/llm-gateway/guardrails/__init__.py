"""
P2-S23 SH-M56a — guardrails layer for llm-gateway.

Closes 26 features under BACKLOG SH-M56a-001..026 (most ship in this
sprint; 026 contribute-to-Hub defers Phase 3 per BACKLOG).

Architecture
------------
A guardrail is a `Rule` subclass that takes `RuleContext` (prompt or
completion + per-tenant config) and returns a `RuleResult` (passed +
optional Violation + optional fixed_text). The `GuardrailEngine` runs
a sequenced list of rules and dispatches `OnFailAction` per-rule
(EXCEPTION blocks, REASK signals retry, FIX swaps text, NOOP logs).

Three rule families:
  - input_rules/  — applied to outgoing prompts (PII, prompt injection,
                    topic restriction, toxic, rate-limit, length)
  - output_rules/ — applied to LLM completions (JSON schema, length,
                    toxic, profanity, competitor)
  - kaori_rules/  — domain rules (TopFactors, Citation, BusinessLanguage,
                    NumericPrecision, Hallucination)

All violations write to `guardrail_violations` (mig 082, partitioned
monthly) via `violations.record_violation()`.

K-rules
-------
K-3: every external LLM call MUST pass through GuardrailEngine.run_input
     before dispatch + GuardrailEngine.run_output after response.
K-5: input PII rule auto-FIXes by redacting before external dispatch.
K-15: rule execution audited per call (writes to guardrail_violations).
"""
from .engine import GuardrailEngine
from .on_fail import OnFailAction, GuardrailBlockedError
from .types import (
    Layer,
    Rule,
    RuleContext,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    "GuardrailEngine",
    "GuardrailBlockedError",
    "Layer",
    "OnFailAction",
    "Rule",
    "RuleContext",
    "RuleResult",
    "Severity",
    "Violation",
]
