"""
P2-S21 D6 — NOV-RPT-023 Negative NOV workflow recommendations.

When the CFO digest shows NOV < 0 for a quarter, this module identifies
the top-K underperforming workflows (ROI < 0 or significantly below
target), maps each to a candidate replacement template from mig 069's
25-template catalog, and surfaces which OKRs are blocked.

Pure computation — no I/O. Caller (routers/economics.py) does the SQL
join + passes the row tuples in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class WorkflowRoiRow:
    """One row from the workflow-NOV rollup join."""
    workflow_id:        UUID
    workflow_name:      str
    department_type:    str             # marketing / sales / customer_service / warehouse / finance
    revenue_vnd:        Decimal
    cost_vnd:           Decimal
    nov_vnd:            Decimal         # revenue - cost
    roi:                Decimal         # NOV / cost (Decimal; 0 if cost=0)


@dataclass(frozen=True)
class TemplateCandidate:
    """One row from workflow_templates available for replacement."""
    template_id:        UUID
    display_name:       str
    display_name_vi:    str
    department_type:    str
    industry_vertical:  Optional[str]
    category:           Optional[str]
    estimated_setup_minutes: int


@dataclass(frozen=True)
class OKRRef:
    """Compact OKR reference for blocked-OKR surfacing."""
    okr_id:           UUID
    objective_text:   str
    progress:         Decimal
    contribution_weight: Decimal


@dataclass(frozen=True)
class WorkflowRecommendation:
    """One workflow → replacement template + blocked OKRs."""
    workflow_id:        UUID
    workflow_name:      str
    department_type:    str
    current_roi:        Decimal
    nov_vnd:            Decimal
    severity:           str             # critical / warning / info
    reason_vi:          str
    suggested_template: Optional[TemplateCandidate]
    blocked_okrs:       tuple[OKRRef, ...] = field(default_factory=tuple)


# ─── Severity classifier (pure) ──────────────────────────────────────


def classify_severity(nov_vnd: Decimal, roi: Decimal) -> str:
    """3-band severity per anh's "chuẩn chỉ" convention:

      critical  — NOV strongly negative AND ROI < -0.5 (losing more than half)
      warning   — NOV negative OR ROI < 0
      info      — NOV positive but low ROI (under-performing, not failing)
    """
    if nov_vnd < Decimal("0") and roi < Decimal("-0.5"):
        return "critical"
    if nov_vnd < Decimal("0") or roi < Decimal("0"):
        return "warning"
    return "info"


def _reason_vi(severity: str, workflow_name: str, roi: Decimal) -> str:
    """Vietnamese-business-language reason per anh's tenet #7."""
    pct = (roi * Decimal("100")).quantize(Decimal("0.1"))
    if severity == "critical":
        return (
            f"Workflow '{workflow_name}' đang lỗ nặng — ROI = {pct}%. "
            f"Cân nhắc thay bằng template chuẩn ngay quý này."
        )
    if severity == "warning":
        return (
            f"Workflow '{workflow_name}' có ROI âm = {pct}%. "
            f"Review để xác định bottleneck + thử template phù hợp hơn."
        )
    return (
        f"Workflow '{workflow_name}' có ROI dương nhưng dưới target — "
        f"có thể tối ưu thêm."
    )


# ─── Template matching (pure) ────────────────────────────────────────


def _match_template(
    workflow: WorkflowRoiRow,
    available: list[TemplateCandidate],
) -> Optional[TemplateCandidate]:
    """Pick the best replacement template by:
      1. Exact department_type match.
      2. Industry vertical alignment (if both have one).
      3. Shortest estimated_setup_minutes (faster replacement = lower risk).

    Returns None if no template matches department_type — caller
    surfaces "no auto-suggestion" in that case.
    """
    same_dept = [t for t in available if t.department_type == workflow.department_type]
    if not same_dept:
        return None
    # Sort: shorter setup first as tiebreaker; secondary by name for determinism.
    same_dept.sort(key=lambda t: (t.estimated_setup_minutes, t.display_name))
    return same_dept[0]


# ─── Main recommendation function ────────────────────────────────────


def recommend_workflow_fixes(
    *,
    workflows: list[WorkflowRoiRow],
    available_templates: list[TemplateCandidate],
    linked_okrs_by_workflow: dict[UUID, list[OKRRef]],
    top_k: int = 3,
) -> list[WorkflowRecommendation]:
    """Build up-to-`top_k` recommendations for underperforming workflows.

    Ranking: severity (critical > warning > info), then most-negative NOV
    first. Deterministic tiebreaker by workflow_id string.
    """
    severity_rank = {"critical": 0, "warning": 1, "info": 2}

    # Filter to underperformers only (NOV < 0 OR ROI < 0.2 = "should review")
    candidates = [
        w for w in workflows
        if w.nov_vnd < Decimal("0") or w.roi < Decimal("0.2")
    ]
    # Sort by severity then NOV ascending (most negative first)
    candidates.sort(
        key=lambda w: (
            severity_rank.get(classify_severity(w.nov_vnd, w.roi), 99),
            w.nov_vnd,
            str(w.workflow_id),
        )
    )

    out: list[WorkflowRecommendation] = []
    for wf in candidates[:top_k]:
        sev = classify_severity(wf.nov_vnd, wf.roi)
        template = _match_template(wf, available_templates)
        okrs = tuple(linked_okrs_by_workflow.get(wf.workflow_id, []))
        out.append(WorkflowRecommendation(
            workflow_id=wf.workflow_id,
            workflow_name=wf.workflow_name,
            department_type=wf.department_type,
            current_roi=wf.roi,
            nov_vnd=wf.nov_vnd,
            severity=sev,
            reason_vi=_reason_vi(sev, wf.workflow_name, wf.roi),
            suggested_template=template,
            blocked_okrs=okrs,
        ))
    return out
