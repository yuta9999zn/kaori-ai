"""
Stage 12 — Organisational Learning Loop (60-day baseline + 90-day testing).

Per CLAUDE.md §5 Stage 12 + PIPELINE_UNIFIED.md §11.8 (the feedback
loop that closes the learning cycle):
  prediction → action → outcome → feedback → training data → better predictions

This module ships the **measurement + promotion** mechanics that close
the loop:

  1. BaselineTracker — collects 60 days of (metric, value) tuples per
     tenant + experiment_id; computes mean + variance + control window.
  2. ABTestFramework — runs a 90-day window with control (old behaviour)
     vs treatment (new behaviour); pulls baseline as control; computes
     lift + significance.
  3. PromotionEngine — given test results, decides replace / migrate /
     keep-baseline + emits a PromotionDecision row.

Out of scope (defer):
  - Cron-scheduled runs (this commit is pure functions + an in-memory
    backend; airflow / temporal wiring lands separately)
  - Real statistical t-test / Mann-Whitney U (Phase 1.5 uses a simple
    threshold-based lift check; rigorous stats Phase 2)
  - Multi-armed bandit allocation (single-treatment A/B only Phase 1.5)
  - Migration runbook execution (PromotionDecision is advisory; humans
    execute Phase 1.5 — Temporal workflow Phase 2)

K-1: every observation / experiment carries tenant_id.
K-6: PromotionDecision is the audit row — append-only.
"""
from __future__ import annotations

from .baseline import (
    BaselineSummary,
    BaselineTracker,
    Observation,
)
from .ab_test import (
    ABTestFramework,
    ABTestResult,
    ExperimentArm,
)
from .promotion import (
    PromotionDecision,
    PromotionEngine,
)

__all__ = [
    "ABTestFramework",
    "ABTestResult",
    "BaselineSummary",
    "BaselineTracker",
    "ExperimentArm",
    "Observation",
    "PromotionDecision",
    "PromotionEngine",
]
