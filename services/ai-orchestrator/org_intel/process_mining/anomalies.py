"""
P2-S14 — Process Mining anomaly detectors.

Five detector functions, one per backlog item:

  PM-ANM-023  detect_approval_bypass    cases that skipped a required approver
  PM-ANM-024  detect_rework_loops       cases where same activity repeats
  PM-ANM-025  score_bypass_risk         high-value bypass = high risk
  PM-ANM-026  analyze_conformance       actual vs designed workflow ordering
  PM-ANM-027  token_replay              fitness via classical token replay

All pure functions over EventLog + designed-workflow spec. No DB
access, no LLM, no I/O. Caller composes via the
GET /process-mining/sessions/{id}/anomalies endpoint.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .case_inference import infer_cases
from .types import Event, EventLog


# ─── Result shapes ──────────────────────────────────────────────────


@dataclass(frozen=True)
class BypassEvent:
    """One case that skipped the required approval step."""
    case_id:                str
    expected_approver_step: str
    actual_sequence:        tuple[str, ...]
    sample_size:            int   # how many cases were checked


@dataclass(frozen=True)
class ReworkLoop:
    """One detected rework — same activity fires N>1 times in one case."""
    case_id:        str
    activity:       str
    occurrence_count: int


@dataclass(frozen=True)
class BypassRiskScore:
    """Risk score for one bypass case (PM-ANM-025).

    score = base_severity × revenue_at_risk_factor; 0-1 range.
    Higher = more dangerous bypass.
    """
    case_id:           str
    base_severity:     float        # 0.0..1.0
    revenue_factor:    float        # multiplier from payload.amount
    final_score:       float        # min(1.0, base × factor)
    risk_band:         str          # 'low' | 'medium' | 'high' | 'critical'


@dataclass(frozen=True)
class ConformanceCheck:
    """PM-ANM-026 — case-level conformance against designed workflow."""
    case_id:               str
    designed_sequence:     tuple[str, ...]
    actual_sequence:       tuple[str, ...]
    matches_designed:      bool
    longest_common_subsequence_length: int
    conformance_score:     float    # LCS_len / max(|designed|, |actual|)


@dataclass(frozen=True)
class TokenReplayResult:
    """PM-ANM-027 — token-replay fitness over a Petri-net-like spec.

    Phase 2.5 ships the full Petri-net replay; today we simulate the
    designed sequence as a single-token marking that fires when actual
    activities arrive in expected order.
    """
    case_id:           str
    tokens_consumed:   int
    tokens_remaining:  int
    tokens_missing:    int      # how many expected activities never arrived
    fitness:           float    # 1 - missing / total_expected


# ─── Detectors ──────────────────────────────────────────────────────


def detect_approval_bypass(
    event_log: EventLog,
    *,
    required_approver_step: str,
    sample_limit: int = 100,
) -> list[BypassEvent]:
    """PM-ANM-023 — cases where the required approval activity DID NOT
    fire. Useful for "Was the finance director sign-off skipped on any
    invoice approval?"

    Returns up to `sample_limit` bypass cases. Empty list = no bypass.
    """
    cases = infer_cases(event_log.events).values()
    out: list[BypassEvent] = []
    for case in cases:
        seq = tuple(ev.event_type for ev in case)
        if required_approver_step in seq:
            continue
        # Bypass — capture for the result.
        cid = case[0].case_id or case[0].event_id
        out.append(BypassEvent(
            case_id=cid,
            expected_approver_step=required_approver_step,
            actual_sequence=seq,
            sample_size=len(cases),
        ))
        if len(out) >= sample_limit:
            break
    return out


def detect_rework_loops(
    event_log: EventLog, *, min_occurrence: int = 2,
) -> list[ReworkLoop]:
    """PM-ANM-024 — cases where one activity fires ≥ min_occurrence
    times. Indicates rework / back-and-forth / revision loops."""
    cases = infer_cases(event_log.events).values()
    out: list[ReworkLoop] = []
    for case in cases:
        cid = case[0].case_id or case[0].event_id
        counts: Counter[str] = Counter(ev.event_type for ev in case)
        for activity, count in counts.items():
            if count >= min_occurrence:
                out.append(ReworkLoop(
                    case_id=cid, activity=activity, occurrence_count=count,
                ))
    return out


def score_bypass_risk(
    bypass: BypassEvent,
    *,
    case_events: list[Event],
    amount_payload_key: str = "amount_vnd",
    base_severity: float = 0.5,
    high_value_threshold_vnd: float = 100_000_000,
) -> BypassRiskScore:
    """PM-ANM-025 — revenue-weighted risk for one bypass case.

    Multiplies a base severity by a revenue factor:
      transaction_amount ≥ 10× threshold → factor 2.0  (cap at 1.0 final)
      transaction_amount ≥ threshold     → factor 1.5
      transaction_amount > 0              → factor 1.0
      else (no amount in payload)         → factor 0.8

    Risk bands:
      ≥ 0.85  critical
      ≥ 0.65  high
      ≥ 0.40  medium
      <  0.40 low
    """
    if not 0.0 <= base_severity <= 1.0:
        raise ValueError(f"base_severity must be in [0,1]; got {base_severity}")
    # Pull the largest amount across the case's events.
    max_amount = 0.0
    for ev in case_events:
        val = ev.payload.get(amount_payload_key)
        try:
            amt = float(val) if val is not None else 0.0
        except (TypeError, ValueError):
            amt = 0.0
        max_amount = max(max_amount, amt)

    if max_amount >= 10 * high_value_threshold_vnd:
        factor = 2.0
    elif max_amount >= high_value_threshold_vnd:
        factor = 1.5
    elif max_amount > 0:
        factor = 1.0
    else:
        factor = 0.8

    final = min(1.0, round(base_severity * factor, 4))
    if final >= 0.85:
        band = "critical"
    elif final >= 0.65:
        band = "high"
    elif final >= 0.40:
        band = "medium"
    else:
        band = "low"
    return BypassRiskScore(
        case_id=bypass.case_id, base_severity=base_severity,
        revenue_factor=factor, final_score=final, risk_band=band,
    )


def analyze_conformance(
    event_log: EventLog, *, designed_sequence: tuple[str, ...],
) -> list[ConformanceCheck]:
    """PM-ANM-026 — per-case conformance against the workflow designer's
    intended path. Returns 1 row per case."""
    cases = infer_cases(event_log.events).values()
    out: list[ConformanceCheck] = []
    for case in cases:
        cid = case[0].case_id or case[0].event_id
        actual = tuple(ev.event_type for ev in case)
        lcs_len = _lcs_length(actual, designed_sequence)
        max_len = max(len(actual), len(designed_sequence), 1)
        score = round(lcs_len / max_len, 4)
        out.append(ConformanceCheck(
            case_id=cid, designed_sequence=designed_sequence,
            actual_sequence=actual,
            matches_designed=(actual == designed_sequence),
            longest_common_subsequence_length=lcs_len,
            conformance_score=score,
        ))
    return out


def _lcs_length(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    """Standard LCS DP. O(|a|×|b|) — fine for workflow sequences (<50 steps)."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def token_replay(
    event_log: EventLog, *, expected_sequence: tuple[str, ...],
) -> list[TokenReplayResult]:
    """PM-ANM-027 — simplified token-replay per case.

    Walk each case's events; a 'token' advances when the next expected
    activity arrives. At end:
      fitness = 1 - (missing / |expected_sequence|)
    """
    cases = infer_cases(event_log.events).values()
    out: list[TokenReplayResult] = []
    total_expected = max(len(expected_sequence), 1)
    for case in cases:
        cid = case[0].case_id or case[0].event_id
        actual = [ev.event_type for ev in case]
        cursor = 0
        for a in actual:
            if cursor < len(expected_sequence) and a == expected_sequence[cursor]:
                cursor += 1
        consumed = cursor
        missing = len(expected_sequence) - cursor
        remaining = max(0, len(actual) - cursor)
        fitness = round(1 - (missing / total_expected), 4)
        out.append(TokenReplayResult(
            case_id=cid,
            tokens_consumed=consumed,
            tokens_remaining=remaining,
            tokens_missing=missing,
            fitness=fitness,
        ))
    return out
