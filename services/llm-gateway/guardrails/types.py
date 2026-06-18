"""
P2-S23 SH-M56a — guardrail rule types + base class.

Pure dataclasses + ABC; no I/O. Concrete rule modules import from here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class Layer(str, Enum):
    INPUT  = "input"
    OUTPUT = "output"


class Severity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# OnFailAction is in on_fail.py because the dispatch logic lives there;
# it imports types here so the back-reference is one-way.


@dataclass
class RuleContext:
    """Per-call context handed to every rule. Same dataclass shape for
    INPUT (prompt-side) and OUTPUT (completion-side) — rules know which
    layer they live in via the engine's `layer` argument.

    `tenant_config` is per-rule configuration loaded from the tenant
    profile (rate-limit budget, banned-word lists, citation minimums).
    Engine merges global defaults + tenant overrides before handing in.
    """
    text:           str
    enterprise_id:  UUID
    user_id:        Optional[UUID]      = None
    request_id:     Optional[UUID]      = None
    model_id:       Optional[str]       = None
    layer:          Layer               = Layer.INPUT
    tenant_config:  dict[str, Any]      = field(default_factory=dict)
    # OUTPUT layer rules may need the original input for cross-checks
    # (e.g., hallucination detector compares output entities vs input
    # citations).
    paired_input:   Optional[str]       = None
    # Already-parsed JSON for output_rules that need structural access
    # (json_schema, top_factors, citation, numeric_precision).
    parsed_output:  Optional[dict]      = None


@dataclass
class Violation:
    """One rule failure. Persisted via violations.record_violation()."""
    rule_name:         str
    layer:             Layer
    severity:          Severity
    enterprise_id:     UUID
    user_id:           Optional[UUID]            = None
    request_id:        Optional[UUID]            = None
    model_id:          Optional[str]             = None
    offending_excerpt: Optional[str]             = None
    rule_metadata:     dict[str, Any]            = field(default_factory=dict)


@dataclass
class RuleResult:
    """Output of one rule's check.

    `passed=True` → rule did not flag; engine moves on.
    `passed=False` → engine consults rule.on_fail to decide what to do.
    `fixed_text` populated only when rule.on_fail = FIX and rule was
        able to repair. Engine uses fixed_text as the new prompt /
        completion downstream.
    """
    passed:     bool
    violation:  Optional[Violation] = None
    fixed_text: Optional[str]       = None


class Rule(ABC):
    """Base class — concrete rules subclass and implement check()."""

    # Required class attributes — concrete rules MUST override.
    name:    str       = ""
    layer:   Layer
    severity: Severity = Severity.MEDIUM

    # On-fail dispatch is per-rule-instance, not per-class, so a tenant
    # can override (e.g., toxic rule = EXCEPTION for one tenant, FIX
    # for another). Default = EXCEPTION (safest).
    def __init__(self, *, on_fail: Optional["OnFailAction"] = None):  # type: ignore[name-defined]
        from .on_fail import OnFailAction
        self.on_fail = on_fail if on_fail is not None else OnFailAction.EXCEPTION

    @abstractmethod
    async def check(self, ctx: RuleContext) -> RuleResult:
        """Run the check. Pure-ish: may read tenant_config + external
        ML scorers but should not mutate inputs. Return RuleResult."""
        raise NotImplementedError
