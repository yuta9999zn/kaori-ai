"""
AI-HSC-016 (P2-S14) — Cohort comparison for adoption health.

Given a target workflow's health metric vs a cohort of peer tenants'
same workflow, returns a percentile + verdict. Manager-facing UX is:
  "Bạn đứng top 20% so với các doanh nghiệp cùng ngành đang chạy
   workflow này."

Pure function — caller assembles the peer list (P15-S11 follow-up
defines what 'similar tenant' means; current implementation accepts
any list the caller deems comparable).

Cohort selection rules (caller's responsibility today):
  * Same industry vertical (RETAIL/F&B/FMCG/...)
  * Same workflow_id (canonical workflow template id, not tenant-instance id)
  * Last 30 days observation window
  * Anonymise peer tenant_ids before sending to the FE (return ranks only)
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, stdev
from typing import Sequence


@dataclass(frozen=True)
class HealthSample:
    """One tenant's health metric for a workflow."""
    tenant_id_hashed: str    # anonymised — caller SHA-256s the real id
    metric_value:     float
    sample_window_days: int = 30


@dataclass(frozen=True)
class CohortRanking:
    """Result of compare_to_cohort()."""
    target_value:          float
    cohort_size:           int
    cohort_mean:           float
    cohort_median:         float
    cohort_stddev:         float
    target_rank:           int      # 1-based; 1 = best
    target_percentile:     float    # 0-100; 100 = best
    verdict:               str      # 'top_10pct' / 'top_25pct' / 'average' / 'bottom_25pct' / 'bottom_10pct'
    note:                  str


def compare_to_cohort(
    *,
    target_value: float,
    peer_samples: Sequence[HealthSample],
    higher_is_better: bool = True,
) -> CohortRanking:
    """Rank `target_value` against `peer_samples`.

    Args:
      target_value:      the tenant we're reporting for
      peer_samples:      other tenants' same-workflow metric values
      higher_is_better:  True for adoption % / completion rate; False for
                          time-to-action / error rate
    """
    if not peer_samples:
        return CohortRanking(
            target_value=target_value, cohort_size=0,
            cohort_mean=0.0, cohort_median=0.0, cohort_stddev=0.0,
            target_rank=1, target_percentile=100.0,
            verdict="cohort_empty",
            note="No peer tenants in this cohort yet — can't rank.",
        )

    values = [s.metric_value for s in peer_samples]
    cohort_mean = round(mean(values), 4)
    cohort_med = round(median(values), 4)
    cohort_std = round(stdev(values), 4) if len(values) > 1 else 0.0

    # Rank: count of peers WORSE than target (for higher-is-better).
    if higher_is_better:
        worse_than_target = sum(1 for v in values if v < target_value)
    else:
        worse_than_target = sum(1 for v in values if v > target_value)
    # Rank in 1..cohort_size+1 (target_value not in peer list).
    rank = (len(values) - worse_than_target) + 1
    percentile = round((worse_than_target / len(values)) * 100, 2)
    if not higher_is_better:
        # Invert percentile so "top 10%" still means good.
        pass   # already correct: worse_than_target counted on inverted side

    if percentile >= 90:
        verdict = "top_10pct"
    elif percentile >= 75:
        verdict = "top_25pct"
    elif percentile >= 25:
        verdict = "average"
    elif percentile >= 10:
        verdict = "bottom_25pct"
    else:
        verdict = "bottom_10pct"

    direction = "cao hơn" if higher_is_better else "thấp hơn"
    note = (
        f"Doanh nghiệp anh đứng top {100 - percentile:.0f}% "
        f"({direction} {worse_than_target}/{len(values)} đối thủ trong "
        f"cohort cùng ngành)."
    )
    return CohortRanking(
        target_value=target_value, cohort_size=len(values),
        cohort_mean=cohort_mean, cohort_median=cohort_med,
        cohort_stddev=cohort_std,
        target_rank=rank, target_percentile=percentile,
        verdict=verdict, note=note,
    )
