"""
Intervention effectiveness tracker — AI-INT-021 (P15-S10 D3).

Per docs/strategic/WORKFLOW_SYSTEM.md §31.4. When an intervention fires
(e.g. CSM outreach email after AI-SIG-001 abandonment spike), this
module:

  1. Captures the workflow's pre-intervention adoption score
     (snapshot via compute_composite_score on the signals at trigger time).
  2. Schedules two follow-up evaluations: 14 days + 30 days post.
  3. At each evaluation point: recompute adoption score, log the
     improvement vs baseline, classify intervention as effective
     (improvement > 5 score-points per spec §31.4).
  4. Feed back into the intervention recommendation engine so the
     model learns which intervention archetype works for which
     resistance pattern.

Side-effect class assignments (K-17):
  capture_baseline       write_idempotent  UPSERT keyed by intervention_id
  evaluate_at_checkpoint read_only         SELECT signal samples
  log_outcome            write_non_idempotent  INSERT into intervention_outcomes
                                                (REL-005 dedup key required)

The Temporal workflow that orchestrates these is in
workflow_runtime/workflows/intervention_followup.py — this module is
the pure activity logic so it tests without Temporal. Tests inject
fake adoption-score readers so we can simulate "score dropped 8 points
after 14 days" without standing up a Postgres + signal generator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from .health_score import HealthScore


# ---------------------------------------------------------------------------
# Per-spec WORKFLOW_SYSTEM.md §31.4: improvement > 5 score-points = effective
# ---------------------------------------------------------------------------
EFFECTIVE_IMPROVEMENT_THRESHOLD: float = 5.0

# Two follow-up checkpoints per spec.
CHECKPOINT_DAYS: tuple[int, ...] = (14, 30)


class InterventionOutcomeClass(str, Enum):
    """Three-bucket classification at evaluation time."""
    EFFECTIVE = "effective"            # improvement > 5
    NEUTRAL = "neutral"                # |improvement| ≤ 5 (within noise)
    REGRESSION = "regression"          # improvement < -5 (intervention backfired)


@dataclass(frozen=True)
class InterventionBaseline:
    """Capture point — what we know at trigger time. Persisted by the
    write_idempotent activity (intervention_outcomes row, baseline_*
    columns); the workflow re-reads it at each checkpoint.
    """
    intervention_id: str
    workflow_id: str
    enterprise_id: UUID
    triggered_at: datetime
    pre_score: float                   # composite 0-100 at trigger time
    intervention_type: str             # 'csm_email' / 'manager_alert' / etc.


@dataclass(frozen=True)
class InterventionCheckpoint:
    """One evaluation result. The activity emits two of these per
    intervention (14d + 30d), each becoming a separate row in
    intervention_outcomes via the write_non_idempotent log_outcome path.
    """
    intervention_id: str
    checkpoint_days: int               # 14 or 30 per CHECKPOINT_DAYS
    evaluated_at: datetime
    pre_score: float
    post_score: float
    improvement: float                 # post - pre (signed)
    classification: InterventionOutcomeClass
    side_effects: tuple[str, ...]      # detected regressions in adjacent signals


# ---------------------------------------------------------------------------
# Type alias — the workflow injects this so tests can supply synthetic
# scores without standing up a real signal pipeline.
# ---------------------------------------------------------------------------

ScoreReader = Callable[[str, UUID], Awaitable[HealthScore]]


# ---------------------------------------------------------------------------
# Pure activities (testable without Temporal)
# ---------------------------------------------------------------------------


def capture_baseline(
    *,
    intervention_id: str,
    workflow_id: str,
    enterprise_id: UUID,
    intervention_type: str,
    triggered_at: datetime,
    pre_score: float,
) -> InterventionBaseline:
    """Pure construction — the persistence layer (Temporal activity)
    wraps this in an UPSERT keyed by intervention_id.

    Pre_score must be in [0, 100] (HealthScore contract). Intervention
    type comes from the playbook taxonomy (CLAUDE.md §10 / strategic
    PLAYBOOK_90DAY.md §6) — this function doesn't validate the string
    so the playbook can grow without coupling to the tracker.
    """
    if not (0.0 <= pre_score <= 100.0):
        raise ValueError(
            f"capture_baseline: pre_score must be in [0, 100]; got {pre_score}"
        )
    return InterventionBaseline(
        intervention_id=intervention_id,
        workflow_id=workflow_id,
        enterprise_id=enterprise_id,
        triggered_at=triggered_at,
        pre_score=pre_score,
        intervention_type=intervention_type,
    )


async def evaluate_at_checkpoint(
    *,
    baseline: InterventionBaseline,
    checkpoint_days: int,
    score_reader: ScoreReader,
    side_effect_detector: Optional[Callable[[InterventionBaseline], list[str]]] = None,
    now: Optional[datetime] = None,
) -> InterventionCheckpoint:
    """Read the current adoption score, compute improvement, classify.

    K-17 class: read_only (no DB writes). The Temporal workflow wraps
    this; the log_outcome step (separate activity) handles the
    write_non_idempotent INSERT.

    Args:
        baseline:                captured at trigger time
        checkpoint_days:         14 or 30 per CHECKPOINT_DAYS
        score_reader:            async fn (workflow_id, enterprise_id) → HealthScore
                                 - injected so tests can supply deterministic scores
        side_effect_detector:    optional sync fn to detect regressions in
                                 adjacent signals (e.g. intervention fixed
                                 abandonment but spiked override rate).
                                 Default returns empty tuple.
        now:                     time hook for tests; defaults to UTC now.
    """
    if checkpoint_days not in CHECKPOINT_DAYS:
        raise ValueError(
            f"checkpoint_days must be one of {CHECKPOINT_DAYS}; got {checkpoint_days}"
        )
    current_score = await score_reader(baseline.workflow_id, baseline.enterprise_id)
    improvement = current_score.composite - baseline.pre_score
    classification = _classify_outcome(improvement)
    side_effects = (
        tuple(side_effect_detector(baseline)) if side_effect_detector else ()
    )
    return InterventionCheckpoint(
        intervention_id=baseline.intervention_id,
        checkpoint_days=checkpoint_days,
        evaluated_at=now or datetime.now(timezone.utc),
        pre_score=baseline.pre_score,
        post_score=current_score.composite,
        improvement=improvement,
        classification=classification,
        side_effects=side_effects,
    )


def _classify_outcome(improvement: float) -> InterventionOutcomeClass:
    """Three-bucket per spec WORKFLOW_SYSTEM.md §31.4 + symmetric
    regression threshold (|delta| ≤ 5 = noise floor).
    """
    if improvement > EFFECTIVE_IMPROVEMENT_THRESHOLD:
        return InterventionOutcomeClass.EFFECTIVE
    if improvement < -EFFECTIVE_IMPROVEMENT_THRESHOLD:
        return InterventionOutcomeClass.REGRESSION
    return InterventionOutcomeClass.NEUTRAL


def project_checkpoint_due_at(
    baseline: InterventionBaseline, checkpoint_days: int,
) -> datetime:
    """When this checkpoint is due — used by the Temporal workflow to
    schedule the sleep+evaluate loop. Pure for testability.
    """
    if checkpoint_days not in CHECKPOINT_DAYS:
        raise ValueError(
            f"checkpoint_days must be one of {CHECKPOINT_DAYS}; got {checkpoint_days}"
        )
    return baseline.triggered_at + timedelta(days=checkpoint_days)
