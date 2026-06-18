"""
Adoption Intelligence signal extractors — Phase 1 v4 ships 5/9.

Each signal is a function with a uniform shape:
  signal(workflow_events, *, threshold=...) -> SignalSample

Returns a SignalSample with score 0.0-1.0 (1.0 = healthy, 0.0 =
strongly resistant) + raw evidence count for ops debugging.

The signal computation logic is intentionally light Phase 1 — ship
the contract surface + 1 reference impl per signal. Real production
calculation needs full event volume + per-tenant baselining (Phase 1.5).

9 signals (canonical names per BACKLOG_V4 + Feature_Tree_v4 sheet):
  AI-SIG-001  Workflow execution abandonment             — P1-S7
  AI-SIG-002  AI decision override rate tracking         — P1-S7
  AI-SIG-003  Side-channel detection (Zalo/Excel)        — P1-S7
  AI-SIG-004  Workaround file creation (parallel Excel)  — P15-S9
  AI-SIG-005  Manager intervention frequency             — P1-S7
  AI-SIG-006  Workflow completion rate per user/dept     — P1-S7
  AI-SIG-007  Negative sentiment in comments/feedback    — P15-S9
  AI-SIG-008  Time-on-task variance (vs baseline)        — P15-S9
  AI-SIG-009  Feature usage decline trend                — P15-S9

(Earlier docstring listed Phase 1.5 signals as "Login frequency drop /
Time-to-action increase / Feature usage skew / Negative feedback rate";
those names came from a draft P15-S9 plan that drifted from the Excel
sheet. The Excel + BACKLOG_V4 are canonical — em adjusted P15-S9 D6
to ship the canonical names.)
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class SignalSample:
    """One adoption signal measurement.

    Attributes:
        signal_id     — 'AI-SIG-001' / 'AI-SIG-002' / ...
        score         — 0.0 = strongly resistant, 1.0 = healthy
        raw_count     — evidence count (e.g. # of abandonments) for debug
        sample_size   — denominator (e.g. # of total starts) for context
        note          — human-readable summary, optional
    """
    signal_id: str
    score: float
    raw_count: int
    sample_size: int
    note: str | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(
                f"SignalSample.score must be in [0.0, 1.0]; got {self.score}"
            )


class SignalExtractor(abc.ABC):
    """Future-facing base class. Each signal lives as a function in this
    module Phase 1 (simpler test isolation). When a signal grows state
    (e.g. needs a window cache, needs Process Mining input), promote it
    to a class extending this ABC.
    """

    signal_id: str = ""

    @abc.abstractmethod
    def extract(self, *, tenant_id: UUID, workflow_id: str | None,
                events: list[dict[str, Any]]) -> SignalSample:
        ...


# ---------------------------------------------------------------------------
# AI-SIG-001 — Workflow execution abandonment
# ---------------------------------------------------------------------------

def AI_SIG_001_workflow_abandonment(
    *,
    starts: int,
    completions: int,
) -> SignalSample:
    """Detect users starting a workflow but quitting before completion.

    Args:
        starts:      number of workflow_started events in window
        completions: number of workflow_completed events in window
    Score: completions / starts (1.0 = all started workflows finished;
           0.0 = none did). starts==0 → score=1.0 (no signal — workflow
           wasn't used; not a resistance event).
    """
    if starts == 0:
        return SignalSample(
            signal_id="AI-SIG-001",
            score=1.0,
            raw_count=0,
            sample_size=0,
            note="no workflow starts in window — no signal",
        )
    completion_rate = max(0.0, min(1.0, completions / starts))
    abandonments = starts - completions
    return SignalSample(
        signal_id="AI-SIG-001",
        score=completion_rate,
        raw_count=abandonments,
        sample_size=starts,
        note=f"{abandonments}/{starts} workflows abandoned",
    )


# ---------------------------------------------------------------------------
# AI-SIG-002 — AI decision override rate tracking
# ---------------------------------------------------------------------------

def AI_SIG_002_ai_decision_override_rate(
    *,
    decisions: int,
    overrides: int,
) -> SignalSample:
    """Count overrides per workflow per user.

    Score: 1.0 - (overrides / decisions). High override rate (>40% per
    BACKLOG_V4 spec) means user doesn't trust AI suggestions.
    """
    if decisions == 0:
        return SignalSample(
            signal_id="AI-SIG-002",
            score=1.0,
            raw_count=0,
            sample_size=0,
            note="no AI decisions in window — no signal",
        )
    override_rate = overrides / decisions
    score = max(0.0, 1.0 - override_rate)
    return SignalSample(
        signal_id="AI-SIG-002",
        score=score,
        raw_count=overrides,
        sample_size=decisions,
        note=f"{overrides}/{decisions} decisions overridden ({override_rate:.0%})",
    )


# ---------------------------------------------------------------------------
# AI-SIG-003 — Side-channel detection (Vietnam-critical)
# ---------------------------------------------------------------------------

def AI_SIG_003_side_channel_detection(
    *,
    in_workflow_actions: int,
    side_channel_actions: int,
) -> SignalSample:
    """Detect users using Zalo/Excel for tasks the workflow handles.

    Counts events from external sources (zalo_metadata, excel_filesystem)
    that match a workflow node's purpose AFTER the workflow was deployed.
    High count = workflow exists but team still does it the old way.

    Score: in_workflow / (in_workflow + side_channel). 1.0 = fully
    adopted; 0.0 = entire team works around the workflow.
    """
    total = in_workflow_actions + side_channel_actions
    if total == 0:
        return SignalSample(
            signal_id="AI-SIG-003",
            score=1.0,
            raw_count=0,
            sample_size=0,
            note="no actions in window — no signal",
        )
    score = in_workflow_actions / total
    return SignalSample(
        signal_id="AI-SIG-003",
        score=score,
        raw_count=side_channel_actions,
        sample_size=total,
        note=f"{side_channel_actions}/{total} actions via side-channel "
             f"(Zalo/Excel) instead of workflow",
    )


# ---------------------------------------------------------------------------
# AI-SIG-005 — Manager intervention frequency
# ---------------------------------------------------------------------------

def AI_SIG_005_manager_intervention_frequency(
    *,
    completions: int,
    manager_interventions: int,
) -> SignalSample:
    """Measure how often a manager has to step in to complete a workflow
    a regular user couldn't finish.

    High intervention count = the workflow is too hard / too unclear /
    too risky for the assigned role.

    Score: 1.0 - (interventions / completions).
    """
    if completions == 0:
        return SignalSample(
            signal_id="AI-SIG-005",
            score=1.0,
            raw_count=0,
            sample_size=0,
            note="no completions in window — no signal",
        )
    rate = manager_interventions / completions
    score = max(0.0, 1.0 - rate)
    return SignalSample(
        signal_id="AI-SIG-005",
        score=score,
        raw_count=manager_interventions,
        sample_size=completions,
        note=f"{manager_interventions}/{completions} workflows needed manager step",
    )


# ---------------------------------------------------------------------------
# AI-SIG-006 — Workflow completion rate per user/dept
# ---------------------------------------------------------------------------

def AI_SIG_006_workflow_completion_rate(
    *,
    target_completions: int,
    actual_completions: int,
) -> SignalSample:
    """Per-user/per-dept goal completion vs target.

    Args:
        target_completions: expected workflows in window (from quota /
                            historical baseline)
        actual_completions: workflows actually completed
    Score: min(1.0, actual / target).
    """
    if target_completions == 0:
        return SignalSample(
            signal_id="AI-SIG-006",
            score=1.0,
            raw_count=actual_completions,
            sample_size=0,
            note="no target set — no signal",
        )
    score = min(1.0, actual_completions / target_completions)
    delta = actual_completions - target_completions
    return SignalSample(
        signal_id="AI-SIG-006",
        score=score,
        raw_count=actual_completions,
        sample_size=target_completions,
        note=f"completed {actual_completions}/{target_completions} "
             f"({'+' if delta >= 0 else ''}{delta} vs target)",
    )


# ---------------------------------------------------------------------------
# AI-SIG-004 — Workaround file creation (parallel Excel files)
# ---------------------------------------------------------------------------

def AI_SIG_004_workaround_file_creation(
    *,
    workflow_runs: int,
    suspicious_files: int,
) -> SignalSample:
    """Detect Excel/CSV files duplicating workflow output schema.

    The Process Mining excel_filesystem connector tags files whose
    column schema matches a deployed workflow's gold output. A high
    count means the team copies workflow data out + edits it offline
    instead of using the workflow — the textbook workaround signature.

    Args:
        workflow_runs:     # of workflow completions in the window
                           (denominator — keeps the signal proportional;
                           1 file in a tenant with 1 run/month is bigger
                           noise than 1 file in 1000 runs)
        suspicious_files:  # of detected workaround files in window
    Score: 1.0 - min(1.0, suspicious_files / max(workflow_runs, 1)).
           Capped so 1 file in 0 runs doesn't go negative.
    """
    if workflow_runs == 0 and suspicious_files == 0:
        return SignalSample(
            signal_id="AI-SIG-004",
            score=1.0,
            raw_count=0,
            sample_size=0,
            note="no workflow runs + no workaround files — no signal",
        )
    denom = max(workflow_runs, 1)
    workaround_rate = suspicious_files / denom
    score = max(0.0, 1.0 - min(1.0, workaround_rate))
    return SignalSample(
        signal_id="AI-SIG-004",
        score=score,
        raw_count=suspicious_files,
        sample_size=workflow_runs,
        note=f"{suspicious_files} workaround files vs {workflow_runs} workflow runs "
             f"({workaround_rate:.0%})",
    )


# ---------------------------------------------------------------------------
# AI-SIG-007 — Negative sentiment in comments/feedback
# ---------------------------------------------------------------------------

def AI_SIG_007_negative_sentiment(
    *,
    total_comments: int,
    negative_comments: int,
) -> SignalSample:
    """Negative-sentiment ratio across workflow comments + feedback.

    Phase 1.5 ships the contract surface (input: pre-classified counts);
    Phase 1.5+ wires the actual Vietnamese sentiment classifier
    (llm-gateway adapter route 'sentiment' — already part of L3 reasoning
    contract). The split keeps this signal cheap to compute when the
    NLP pipeline isn't running yet.

    Args:
        total_comments:    # of comments classified in window
        negative_comments: subset rated NEG by classifier
    Score: 1.0 - (negative / total). Empty input → 1.0 (no resistance
           observed because there's nothing to observe).
    """
    if total_comments == 0:
        return SignalSample(
            signal_id="AI-SIG-007",
            score=1.0,
            raw_count=0,
            sample_size=0,
            note="no comments in window — no signal",
        )
    negative_rate = negative_comments / total_comments
    score = max(0.0, 1.0 - negative_rate)
    return SignalSample(
        signal_id="AI-SIG-007",
        score=score,
        raw_count=negative_comments,
        sample_size=total_comments,
        note=f"{negative_comments}/{total_comments} comments negative "
             f"({negative_rate:.0%})",
    )


# ---------------------------------------------------------------------------
# AI-SIG-008 — Time-on-task variance (vs baseline)
# ---------------------------------------------------------------------------

def AI_SIG_008_time_on_task_variance(
    *,
    baseline_seconds: float,
    observed_seconds: float,
) -> SignalSample:
    """Detect users taking 2x longer than the baseline (per spec — 2x =
    friction signal).

    Score model:
      observed ≤ baseline       → 1.0  (faster than baseline, healthy)
      observed = 2 * baseline   → 0.0  (spec threshold)
      between                   → linear from 1.0 → 0.0 across that span
      observed > 2 * baseline   → 0.0  (clamped — anything beyond the
                                       threshold is equally bad for the
                                       UX so don't reward extreme outliers
                                       with negative scores)

    Args:
        baseline_seconds: median per-task duration before the workflow
                          went live (or rolling window baseline)
        observed_seconds: median in the current window
    """
    if baseline_seconds <= 0:
        return SignalSample(
            signal_id="AI-SIG-008",
            score=1.0,
            raw_count=int(observed_seconds),
            sample_size=0,
            note="no baseline established — no signal",
        )
    if observed_seconds <= baseline_seconds:
        return SignalSample(
            signal_id="AI-SIG-008",
            score=1.0,
            raw_count=int(observed_seconds),
            sample_size=int(baseline_seconds),
            note=f"observed {observed_seconds:.0f}s ≤ baseline {baseline_seconds:.0f}s — healthy",
        )
    # Map [baseline .. 2*baseline] → [1.0 .. 0.0], clamp beyond
    excess_ratio = (observed_seconds - baseline_seconds) / baseline_seconds
    score = max(0.0, 1.0 - excess_ratio)
    return SignalSample(
        signal_id="AI-SIG-008",
        score=score,
        raw_count=int(observed_seconds),
        sample_size=int(baseline_seconds),
        note=f"observed {observed_seconds:.0f}s vs baseline {baseline_seconds:.0f}s "
             f"(+{excess_ratio:.0%})",
    )


# ---------------------------------------------------------------------------
# AI-SIG-009 — Feature usage decline trend
# ---------------------------------------------------------------------------

def AI_SIG_009_feature_usage_decline(
    *,
    baseline_uses_per_period: float,
    current_uses_per_period: float,
) -> SignalSample:
    """Workflow usage trend — spec example: 50/day → 30/day = signal.

    Score model:
      current ≥ baseline   → 1.0   (usage held or grew — healthy)
      current = 0          → 0.0   (workflow abandoned)
      between              → current / baseline
                             (linear; 30/50 = 0.6 → score 0.6 → AT_RISK)

    Args:
        baseline_uses_per_period: rolling average from a prior healthy
                                  window (typically the 7d before the
                                  decline check)
        current_uses_per_period:  rolling average in the current window
    """
    if baseline_uses_per_period <= 0:
        return SignalSample(
            signal_id="AI-SIG-009",
            score=1.0,
            raw_count=int(current_uses_per_period),
            sample_size=0,
            note="no baseline — workflow not yet established",
        )
    score = max(0.0, min(1.0, current_uses_per_period / baseline_uses_per_period))
    delta_pct = (current_uses_per_period - baseline_uses_per_period) / baseline_uses_per_period
    return SignalSample(
        signal_id="AI-SIG-009",
        score=score,
        raw_count=int(current_uses_per_period),
        sample_size=int(baseline_uses_per_period),
        note=f"usage {current_uses_per_period:.0f}/period vs baseline "
             f"{baseline_uses_per_period:.0f}/period ({delta_pct:+.0%})",
    )
