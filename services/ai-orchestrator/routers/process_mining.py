"""
Process Mining router — P15-S11 Build Week prep (Tuần 4).

POST /process-mining/mine — runs HeuristicMiner over an inline event log
and returns the MinedWorkflow (direct_follows + event_counts + durations).

Build Week demo path: caller POSTs the events directly. Production path
(post-Build-Week): caller POSTs a session_id and the orchestrator loads
events from Bronze via the data-pipeline service. Inline path stays
useful for sandbox / what-if analysis on a hypothetical event log.

Auth + tenant scoping via X-Enterprise-Id header (K-12 / K-16).

Wire shape mirrors HeuristicMiner.mine() output exactly. Tuple keys are
serialised as "{from}|{to}" delimited strings because JSON keys must be
strings. Callers split on '|' to recover the pair; '|' never appears in
sanitised event_type names (FE pipeline wizard enforces).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..org_intel.adoption.cohort import (
    HealthSample,
    compare_to_cohort,
)
from ..org_intel.process_mining import (
    Event,
    EventLog,
    FuzzyMiner,
    HeuristicMiner,
    InductiveMiner,
    MinedWorkflow,
    analyze_conformance,
    detect_approval_bypass,
    detect_rework_loops,
    score_bypass_risk,
    token_replay,
)

log = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Wire shapes
# ---------------------------------------------------------------------------


class EventIn(BaseModel):
    """One event for the inline mine request."""

    event_id: str = Field(..., min_length=1, max_length=128)
    source: str = Field(..., min_length=1, max_length=64)
    event_type: str = Field(..., min_length=1, max_length=128)
    occurred_at: datetime
    actor: Optional[str] = Field(default=None, max_length=255)
    case_id: Optional[str] = Field(default=None, max_length=128)


class MineRequest(BaseModel):
    """Inline mine request — caller passes events directly.

    For session-id-backed mode (load from Bronze) use `session_id` —
    inline `events` MUST be empty in that case. Either mode required.
    """

    events: list[EventIn] = Field(default_factory=list)
    session_id: Optional[str] = Field(default=None, max_length=128)
    min_frequency: int = Field(default=1, ge=1, le=10_000)

    def model_post_init(self, _ctx) -> None:  # type: ignore[override]
        if not self.events and not self.session_id:
            raise ValueError("either `events` or `session_id` must be provided")
        if self.events and self.session_id:
            raise ValueError("provide `events` OR `session_id`, not both")


class MinedWorkflowOut(BaseModel):
    """Serialised MinedWorkflow. Tuple keys flattened to 'from|to' strings."""

    direct_follows: dict[str, int]
    event_counts: dict[str, int]
    avg_durations: dict[str, float]
    case_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/process-mining/mine",
    response_model=MinedWorkflowOut,
    tags=["Process Mining"],
)
async def mine_workflow(
    body: MineRequest,
    x_enterprise_id: Annotated[str, Header()],
) -> MinedWorkflowOut:
    """Run Heuristic Miner over inline events; return discovered workflow.

    Build Week demo flow:
        FE uploads CSV → BE normalises to events → POST here →
        rendered as graph on Process Mining canvas screen.

    Session-id mode is reserved for post-Build-Week. Returns 501 if used.
    """
    enterprise_id = _parse_enterprise_id(x_enterprise_id)

    if body.session_id is not None:
        raise HTTPException(
            status_code=501,
            detail={
                "type": "https://kaori.ai/errors/not-implemented",
                "title": "session_id mining not yet wired",
                "detail": (
                    "Phase 1.5 demo uses inline events. session_id-backed "
                    "Bronze load lands when Temporal worker cutover completes."
                ),
                "errcode": "SYS-ERR1",
            },
        )

    events = tuple(
        Event(
            tenant_id=enterprise_id,
            event_id=ev.event_id,
            source=ev.source,
            event_type=ev.event_type,
            occurred_at=ev.occurred_at,
            actor=ev.actor,
            case_id=ev.case_id,
        )
        for ev in body.events
    )
    try:
        event_log = EventLog(tenant_id=enterprise_id, events=events)
    except ValueError as exc:
        # PM-PII-012 — event tenant mismatch (constructor enforces); should not
        # happen here because we just stamped enterprise_id, but defensive.
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://kaori.ai/errors/tenant-mismatch",
                "title": "event tenant_id mismatch",
                "detail": str(exc),
                "errcode": "SYS-ERR1",
            },
        )

    miner = HeuristicMiner(min_frequency=body.min_frequency)
    mined = miner.mine(event_log)

    log.info(
        "process_mining.mined",
        tenant_id=str(enterprise_id),
        event_count=len(events),
        case_count=mined.case_count,
        edge_count=len(mined.direct_follows),
        min_frequency=body.min_frequency,
    )

    return _serialise(mined)


def _serialise(mined: MinedWorkflow) -> MinedWorkflowOut:
    """Flatten tuple keys → 'from|to' for JSON serialisation."""
    return MinedWorkflowOut(
        direct_follows={f"{f}|{t}": c for (f, t), c in mined.direct_follows.items()},
        event_counts=dict(mined.event_counts),
        avg_durations={f"{f}|{t}": d for (f, t), d in mined.avg_durations.items()},
        case_count=mined.case_count,
    )


def _parse_enterprise_id(header_value: str) -> UUID:
    try:
        return UUID(header_value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://kaori.ai/errors/bad-enterprise-id",
                "title": "X-Enterprise-Id must be a UUID",
                "detail": f"got {header_value!r}",
                "errcode": "USR-ERR4",
            },
        )


# ---------------------------------------------------------------------------
# P2-S14 — algorithm dispatch + anomaly detection + cohort comparison
# ---------------------------------------------------------------------------


class _EventInline(BaseModel):
    event_id:    str = Field(..., min_length=1, max_length=128)
    source:      str = Field(..., min_length=1, max_length=64)
    event_type:  str = Field(..., min_length=1, max_length=128)
    occurred_at: datetime
    actor:       Optional[str] = Field(default=None, max_length=255)
    case_id:     Optional[str] = Field(default=None, max_length=128)
    payload:     Optional[dict] = None


class RunAlgorithmRequest(BaseModel):
    algorithm: str = Field(..., description="'heuristic' | 'inductive' | 'fuzzy'")
    events:    list[_EventInline] = Field(default_factory=list, min_length=1, max_length=50_000)
    min_frequency:          int = Field(default=1, ge=1, le=10_000)
    min_case_support:       float = Field(default=0.0, ge=0.0, le=1.0)
    significance_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    correlation_threshold:  float = Field(default=0.2, ge=0.0, le=1.0)


class RunAlgorithmResponse(BaseModel):
    algorithm: str
    heuristic: Optional[dict] = None
    inductive: Optional[dict] = None
    fuzzy:     Optional[dict] = None


def _build_event_tuple(items: list, enterprise_id: UUID) -> tuple[Event, ...]:
    return tuple(
        Event(
            tenant_id=enterprise_id, event_id=e.event_id,
            source=e.source, event_type=e.event_type,
            occurred_at=e.occurred_at, actor=e.actor, case_id=e.case_id,
            payload=e.payload or {},
        )
        for e in items
    )


@router.post(
    "/process-mining/sessions/{session_id}/run-algorithm",
    response_model=RunAlgorithmResponse,
    tags=["Process Mining"],
)
async def run_algorithm(
    session_id: str,
    body: RunAlgorithmRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """PM-ALG-016/017 — dispatch one of 3 algorithms over inline events."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    events = _build_event_tuple(body.events, enterprise_id)
    try:
        event_log = EventLog(tenant_id=enterprise_id, events=events)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    algo = body.algorithm.lower().strip()
    if algo == "heuristic":
        result = HeuristicMiner(min_frequency=body.min_frequency).mine(event_log)
        return RunAlgorithmResponse(
            algorithm="heuristic",
            heuristic={
                "direct_follows": {f"{f}|{t}": c
                                     for (f, t), c in result.direct_follows.items()},
                "event_counts":   dict(result.event_counts),
                "case_count":     result.case_count,
            },
        )
    if algo == "inductive":
        result = InductiveMiner(min_case_support=body.min_case_support).mine(event_log)
        return RunAlgorithmResponse(
            algorithm="inductive",
            inductive={
                "tree":           result.root.to_dict(),
                "activity_count": result.activity_count,
                "case_count":     result.case_count,
                "fitness":        result.fitness,
            },
        )
    if algo == "fuzzy":
        result = FuzzyMiner(
            significance_threshold=body.significance_threshold,
            correlation_threshold=body.correlation_threshold,
        ).mine(event_log)
        return RunAlgorithmResponse(
            algorithm="fuzzy",
            fuzzy={
                "nodes": list(result.nodes),
                "edges": [
                    {"from_act": e.from_act, "to_act": e.to_act,
                     "count": e.count, "correlation": e.correlation,
                     "significance": e.significance, "is_bundled": e.is_bundled}
                    for e in result.edges
                ],
                "pruned_node_count":      result.pruned_node_count,
                "pruned_edge_count":      result.pruned_edge_count,
                "correlation_threshold":  result.correlation_threshold,
                "significance_threshold": result.significance_threshold,
            },
        )

    raise HTTPException(
        status_code=400,
        detail=f"algorithm must be 'heuristic' | 'inductive' | 'fuzzy'; got {algo!r}",
    )


class AnomaliesRequest(BaseModel):
    events: list[_EventInline] = Field(default_factory=list,
                                          min_length=1, max_length=50_000)
    required_approver_step:   Optional[str] = Field(default=None, max_length=128)
    designed_sequence:        Optional[list[str]] = None
    expected_replay_sequence: Optional[list[str]] = None
    rework_min_occurrence:    int = Field(default=2, ge=2, le=100)
    bypass_sample_limit:      int = Field(default=100, ge=1, le=10_000)


@router.post(
    "/process-mining/sessions/{session_id}/anomalies",
    tags=["Process Mining"],
)
async def get_anomalies(
    session_id: str,
    body: AnomaliesRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """PM-ANM-023..027 — run 5 anomaly detectors over inline events."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    events = _build_event_tuple(body.events, enterprise_id)
    try:
        event_log = EventLog(tenant_id=enterprise_id, events=events)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    out: dict = {"session_id": session_id, "event_count": len(events)}

    if body.required_approver_step:
        bypass_list = detect_approval_bypass(
            event_log, required_approver_step=body.required_approver_step,
            sample_limit=body.bypass_sample_limit,
        )
        events_by_case: dict[str, list] = {}
        for ev in events:
            events_by_case.setdefault(ev.case_id or ev.event_id, []).append(ev)
        risks = [
            score_bypass_risk(b, case_events=events_by_case.get(b.case_id, []))
            for b in bypass_list
        ]
        out["bypass"] = [
            {"case_id": b.case_id, "expected_approver_step": b.expected_approver_step,
              "actual_sequence": list(b.actual_sequence)}
            for b in bypass_list
        ]
        out["bypass_risk"] = [
            {"case_id": r.case_id, "base_severity": r.base_severity,
              "revenue_factor": r.revenue_factor, "final_score": r.final_score,
              "risk_band": r.risk_band}
            for r in risks
        ]
    else:
        out["bypass"] = []
        out["bypass_risk"] = []

    rework = detect_rework_loops(event_log, min_occurrence=body.rework_min_occurrence)
    out["rework"] = [
        {"case_id": r.case_id, "activity": r.activity,
          "occurrence_count": r.occurrence_count}
        for r in rework
    ]

    if body.designed_sequence:
        confs = analyze_conformance(
            event_log, designed_sequence=tuple(body.designed_sequence),
        )
        out["conformance"] = [
            {"case_id": c.case_id, "matches_designed": c.matches_designed,
              "longest_common_subsequence_length": c.longest_common_subsequence_length,
              "conformance_score": c.conformance_score}
            for c in confs
        ]
    else:
        out["conformance"] = []

    if body.expected_replay_sequence:
        replays = token_replay(
            event_log, expected_sequence=tuple(body.expected_replay_sequence),
        )
        out["token_replay"] = [
            {"case_id": r.case_id, "tokens_consumed": r.tokens_consumed,
              "tokens_remaining": r.tokens_remaining,
              "tokens_missing": r.tokens_missing, "fitness": r.fitness}
            for r in replays
        ]
    else:
        out["token_replay"] = []
    return out


class _HealthSampleIn(BaseModel):
    tenant_id_hashed:   str = Field(..., min_length=1, max_length=128)
    metric_value:       float
    sample_window_days: int = Field(default=30, ge=1, le=365)


class CohortCompareRequest(BaseModel):
    target_value:     float
    peer_samples:     list[_HealthSampleIn]
    higher_is_better: bool = True


@router.post("/adoption/health/cohort-compare", tags=["Process Mining"])
async def cohort_compare(
    body: CohortCompareRequest,
    x_enterprise_id: Annotated[str, Header()],
):
    """AI-HSC-016 — rank a tenant's health metric against an anonymised
    peer cohort."""
    enterprise_id = _parse_enterprise_id(x_enterprise_id)
    peers = [
        HealthSample(
            tenant_id_hashed=s.tenant_id_hashed,
            metric_value=s.metric_value,
            sample_window_days=s.sample_window_days,
        )
        for s in body.peer_samples
    ]
    ranking = compare_to_cohort(
        target_value=body.target_value,
        peer_samples=peers,
        higher_is_better=body.higher_is_better,
    )
    log.info("adoption.cohort_compared", tenant_id=str(enterprise_id),
             cohort_size=ranking.cohort_size, verdict=ranking.verdict)
    return {
        "target_value":      ranking.target_value,
        "cohort_size":       ranking.cohort_size,
        "cohort_mean":       ranking.cohort_mean,
        "cohort_median":     ranking.cohort_median,
        "cohort_stddev":     ranking.cohort_stddev,
        "target_rank":       ranking.target_rank,
        "target_percentile": ranking.target_percentile,
        "verdict":           ranking.verdict,
        "note":              ranking.note,
    }
