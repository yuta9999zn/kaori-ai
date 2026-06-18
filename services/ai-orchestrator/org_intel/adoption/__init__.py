"""Adoption Intelligence — 9 resistance signals + composite health score.

Phase 1 v4 P1-S7 shipped 5/9 (AI-SIG-001/002/003/005/006).
Phase 1.5 P15-S9 D6 ships the remaining 4 (AI-SIG-004/007/008/009).
Composite health aggregator + classification + trend already shipped P1-S7.

Phase 2 extract target: services/adoption-intel/ (skeleton P1-S3).
"""

from .signals import (
    AI_SIG_001_workflow_abandonment,
    AI_SIG_002_ai_decision_override_rate,
    AI_SIG_003_side_channel_detection,
    AI_SIG_004_workaround_file_creation,
    AI_SIG_005_manager_intervention_frequency,
    AI_SIG_006_workflow_completion_rate,
    AI_SIG_007_negative_sentiment,
    AI_SIG_008_time_on_task_variance,
    AI_SIG_009_feature_usage_decline,
    SignalExtractor,
    SignalSample,
)
from .health_score import (
    HealthClassification,
    HealthScore,
    classify_health,
    compute_composite_score,
    detect_trend,
)
from .intervention_engine import (
    ApprovalGate,
    InterventionChannel,
    InterventionMisconfigError,
    InterventionPlan,
    TenantInterventionSettings,
    resolve_intervention_plan,
)
from .intervention_tracker import (
    CHECKPOINT_DAYS,
    EFFECTIVE_IMPROVEMENT_THRESHOLD,
    InterventionBaseline,
    InterventionCheckpoint,
    InterventionOutcomeClass,
    capture_baseline,
    evaluate_at_checkpoint,
    project_checkpoint_due_at,
)

__all__ = [
    "SignalExtractor",
    "SignalSample",
    "AI_SIG_001_workflow_abandonment",
    "AI_SIG_002_ai_decision_override_rate",
    "AI_SIG_003_side_channel_detection",
    "AI_SIG_004_workaround_file_creation",
    "AI_SIG_005_manager_intervention_frequency",
    "AI_SIG_006_workflow_completion_rate",
    "AI_SIG_007_negative_sentiment",
    "AI_SIG_008_time_on_task_variance",
    "AI_SIG_009_feature_usage_decline",
    "HealthClassification",
    "HealthScore",
    "compute_composite_score",
    "classify_health",
    "detect_trend",
    # AI-INT-021 P15-S10 D3
    "InterventionBaseline",
    "InterventionCheckpoint",
    "InterventionOutcomeClass",
    "CHECKPOINT_DAYS",
    "EFFECTIVE_IMPROVEMENT_THRESHOLD",
    "capture_baseline",
    "evaluate_at_checkpoint",
    "project_checkpoint_due_at",
    # AI-INT-022 P15-S10 D4
    "ApprovalGate",
    "InterventionChannel",
    "InterventionMisconfigError",
    "InterventionPlan",
    "TenantInterventionSettings",
    "resolve_intervention_plan",
]
