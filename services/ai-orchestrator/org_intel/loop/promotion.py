"""Promotion engine — turn an ABTestResult into a replace/migrate/keep
decision row.

The decision is **advisory** Phase 1.5 — a human (Studio analyst or
manager) reviews + executes. Phase 2 wires a Temporal workflow that
auto-promotes treatment_wins decisions to production.

K-6 audit: each PromotionDecision is append-only. Caller writes to
`decision_audit_log` with the decision row JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from .ab_test import ABTestResult


class PromotionAction(str, Enum):
    REPLACE_BASELINE = "replace_baseline"   # treatment wins → swap into prod
    KEEP_BASELINE    = "keep_baseline"      # control wins or inconclusive
    EXTEND_WINDOW    = "extend_window"      # near-significant; collect more data


@dataclass(frozen=True)
class PromotionDecision:
    decision_id:    UUID
    tenant_id:      UUID
    experiment_id:  str
    metric_name:    str
    action:         PromotionAction
    rationale:      str
    test_result:    ABTestResult
    decided_at:     datetime
    actor:          str   # 'system' | 'studio_analyst' | 'manager'


# Threshold band — if |t| is close to threshold but below, suggest
# extending the window rather than killing the experiment. 0.8 picked
# at 95% of TSTAT_THRESHOLD by default; configurable per call.
EXTEND_THRESHOLD_FRACTION = 0.8


class PromotionEngine:
    """Map ABTestResult.conclusion → PromotionDecision."""

    def decide(
        self, result: ABTestResult, *,
        actor: str = "system",
        tstat_target: float = 1.96,
        extend_fraction: float = EXTEND_THRESHOLD_FRACTION,
    ) -> PromotionDecision:
        if result.conclusion == "treatment_wins":
            action = PromotionAction.REPLACE_BASELINE
            rationale = (
                f"Treatment wins on {result.metric_name}: lift "
                f"{result.relative_lift:.2%}, t={result.t_statistic:.2f}. "
                f"Recommend replace baseline."
            )
        elif result.conclusion == "control_wins":
            action = PromotionAction.KEEP_BASELINE
            rationale = (
                f"Control wins on {result.metric_name}: lift "
                f"{result.relative_lift:.2%}, t={result.t_statistic:.2f}. "
                f"Keep baseline; consider revising treatment hypothesis."
            )
        else:
            # Inconclusive — if close to threshold, suggest extending window
            if abs(result.t_statistic) >= extend_fraction * tstat_target:
                action = PromotionAction.EXTEND_WINDOW
                rationale = (
                    f"Inconclusive but |t|={abs(result.t_statistic):.2f} is "
                    f"≥ {extend_fraction:.0%} of target {tstat_target}. "
                    f"Suggest extending data collection 30 days."
                )
            else:
                action = PromotionAction.KEEP_BASELINE
                rationale = (
                    f"Inconclusive ({result.reason}). Keep baseline."
                )

        return PromotionDecision(
            decision_id=uuid4(),
            tenant_id=result.tenant_id,
            experiment_id=result.experiment_id,
            metric_name=result.metric_name,
            action=action,
            rationale=rationale,
            test_result=result,
            decided_at=datetime.now(timezone.utc),
            actor=actor,
        )
