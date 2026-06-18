"""Workflow-advisor finding schema + scoring (ADR-0040).

Pure, dependency-free — unit-testable without a DB or LLM. Findings are
produced by deterministic detectors (detectors.py); this module just defines
their shape, the fixed category/severity vocabulary, and the overall_health
roll-up so the FE can render a single gauge.
"""
from __future__ import annotations

from typing import Optional

# Fixed categories — keep stable so JSONB containment queries + FE grouping work.
CATEGORIES = (
    "incomplete",        # step has no action/executor
    "branch_error",      # decision/switch/parallel missing outgoing branches
    "dead_branch",       # node never reached across runs (runtime)
    "bottleneck",        # node slow / high failure rate (runtime)
    "missing_doc",       # required document requirement with no current file
    "no_action_on_path", # node executed but has no action (runtime)
    "redundant",         # consecutive duplicate action
    "compliance",        # approval gate with no approver / missing control
)

SEVERITIES = ("high", "medium", "low")

# How much each severity subtracts from a perfect 1.0 health score.
_SEVERITY_WEIGHT = {"high": 0.20, "medium": 0.08, "low": 0.03}


def finding(
    *,
    category: str,
    severity: str,
    title: str,
    detail: str,
    suggestion: str,
    step_id: Optional[str] = None,
    confidence: float = 0.9,
) -> dict:
    """Build one finding dict (the unit the FE renders + we store in JSONB)."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown finding category: {category}")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity: {severity}")
    return {
        "category": category,
        "severity": severity,
        "step_id": step_id,
        "title": title,
        "detail": detail,
        "suggestion": suggestion,
        "confidence": round(float(confidence), 2),
    }


def overall_health(findings: list[dict]) -> float:
    """1.0 minus the severity-weighted finding load, clamped to [0, 1].

    A workflow with no findings scores 1.0; each finding chips away by its
    severity weight. Deterministic — no LLM input.
    """
    penalty = sum(_SEVERITY_WEIGHT.get(f.get("severity", "low"), 0.03) for f in findings)
    return round(max(0.0, min(1.0, 1.0 - penalty)), 3)
