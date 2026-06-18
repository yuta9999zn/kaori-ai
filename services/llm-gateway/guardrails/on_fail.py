"""
P2-S23 SH-M56a-017..020 — on-fail dispatch strategies.

  017 EXCEPTION — block the call entirely; raise GuardrailBlockedError
                   so the router returns 4xx Problem Details.
  018 REASK      — caller-handled; engine signals "ask the model again
                   with this feedback" via REASK action + feedback msg.
                   Returning REASK does NOT mutate text; the caller
                   wraps another LLM round with the feedback.
  019 FIX        — auto-correct in place. Rule must populate
                   RuleResult.fixed_text; engine swaps and proceeds.
  020 NOOP       — record violation, take no action. Useful for
                   metrics-only rollouts of new rules.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class OnFailAction(str, Enum):
    EXCEPTION = "exception"   # SH-M56a-017
    REASK     = "reask"       # SH-M56a-018
    FIX       = "fix"         # SH-M56a-019
    NOOP      = "noop"        # SH-M56a-020


class GuardrailBlockedError(Exception):
    """Raised by GuardrailEngine when a rule with on_fail=EXCEPTION
    fails. Router converts to 400/403 RFC 7807 Problem Details."""

    def __init__(
        self,
        *,
        rule_name: str,
        reason:    str,
        feedback:  Optional[str] = None,
    ):
        self.rule_name = rule_name
        self.reason    = reason
        self.feedback  = feedback
        super().__init__(f"Guardrail '{rule_name}' blocked: {reason}")
