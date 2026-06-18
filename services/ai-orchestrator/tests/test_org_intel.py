"""
Tests for org_intel — P1-S7 (Process Mining + Adoption Intel + NOV/Economics).

Three sections, one per subpackage. Bundled here Phase 1; split into
test_process_mining.py / test_adoption.py / test_economics.py when
each section grows past ~15 tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from org_intel.adoption import (
    AI_SIG_001_workflow_abandonment,
    AI_SIG_002_ai_decision_override_rate,
    AI_SIG_003_side_channel_detection,
    AI_SIG_004_workaround_file_creation,
    AI_SIG_005_manager_intervention_frequency,
    AI_SIG_006_workflow_completion_rate,
    AI_SIG_007_negative_sentiment,
    AI_SIG_008_time_on_task_variance,
    AI_SIG_009_feature_usage_decline,
    HealthClassification,
    SignalSample,
    classify_health,
    compute_composite_score,
    detect_trend,
)
from org_intel.economics import (
    INDUSTRY_BENCHMARKS,
    compute_monthly_nov,
    estimate_ai_token_cost,
    estimate_infrastructure_cost,
    estimate_integration_cost,
    estimate_people_cost,
    estimate_revenue_ab_attribution,
    estimate_revenue_industry_benchmark,
    estimate_revenue_pre_post,
    time_to_payback_months,
)
from org_intel.process_mining import (
    Event,
    EventLog,
    HeuristicMiner,
    infer_cases,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _ev(et, t=None, *, case_id=None, actor=None, source="postgres_cdc"):
    """Test helper — build an Event with sensible defaults."""
    if t is None:
        t = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)
    return Event(
        tenant_id=TENANT, event_id=f"ev-{et}-{t.timestamp()}",
        source=source, event_type=et, occurred_at=t,
        case_id=case_id, actor=actor,
    )


# ═════════════════════════════════════════════════════════════════════
# PROCESS MINING (PM-PII-009/012, PM-ALG-014/015)
# ═════════════════════════════════════════════════════════════════════


def test_event_log_rejects_cross_tenant_events():
    """PM-PII-012 — EventLog refuses events from other tenants. Tenant
    isolation is the most-tested invariant in this codebase; the mining
    layer enforces it at the data structure layer too."""
    other_tenant = UUID("22222222-2222-2222-2222-222222222222")
    bad_ev = Event(
        tenant_id=other_tenant, event_id="x", source="s",
        event_type="t", occurred_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="PM-PII-012"):
        EventLog(tenant_id=TENANT, events=(bad_ev,))


def test_infer_cases_groups_by_explicit_case_id():
    e1 = _ev("order.created", case_id="ord-1")
    e2 = _ev("order.paid", case_id="ord-1")
    e3 = _ev("order.created", case_id="ord-2")
    cases = infer_cases([e1, e2, e3])
    assert set(cases.keys()) == {"ord-1", "ord-2"}
    assert len(cases["ord-1"]) == 2
    assert len(cases["ord-2"]) == 1


def test_infer_cases_falls_back_to_actor_when_case_id_missing():
    e1 = _ev("login", actor="u-7")
    e2 = _ev("view_dashboard", actor="u-7")
    cases = infer_cases([e1, e2])
    assert "actor:u-7" in cases
    assert len(cases["actor:u-7"]) == 2


def test_infer_cases_buckets_unknown_when_both_missing():
    """Events without case_id AND without actor go into 'unknown:<source>'
    so a data quality issue is visible (not silently dropped)."""
    e = _ev("background_job")
    cases = infer_cases([e])
    assert "unknown:postgres_cdc" in cases


def test_infer_cases_sorts_chronologically():
    """Heuristic Miner reads adjacent pairs as direct-follow — order matters."""
    t1 = datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)
    # Insert out of order
    cases = infer_cases([_ev("c", t3, case_id="x"), _ev("a", t1, case_id="x"), _ev("b", t2, case_id="x")])
    types_in_order = [e.event_type for e in cases["x"]]
    assert types_in_order == ["a", "b", "c"]


def test_heuristic_miner_emits_direct_follows_and_durations():
    base = datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc)
    log = EventLog(tenant_id=TENANT, events=(
        _ev("created", base + timedelta(seconds=0), case_id="c1"),
        _ev("paid",    base + timedelta(seconds=60), case_id="c1"),
        _ev("created", base + timedelta(seconds=0), case_id="c2"),
        _ev("paid",    base + timedelta(seconds=120), case_id="c2"),
    ))
    miner = HeuristicMiner(min_frequency=1)
    result = miner.mine(log)

    assert result.case_count == 2
    assert result.direct_follows[("created", "paid")] == 2
    assert result.event_counts["created"] == 2
    assert result.event_counts["paid"] == 2
    # Average of 60s + 120s
    assert result.avg_durations[("created", "paid")] == 90.0


def test_heuristic_miner_drops_low_frequency_edges():
    base = datetime(2026, 5, 8, tzinfo=timezone.utc)
    log = EventLog(tenant_id=TENANT, events=(
        _ev("a", base + timedelta(seconds=0),  case_id="c1"),
        _ev("b", base + timedelta(seconds=30), case_id="c1"),
        # rare edge a→c only fires once
        _ev("a", base + timedelta(seconds=0),  case_id="c2"),
        _ev("c", base + timedelta(seconds=30), case_id="c2"),
    ))
    miner = HeuristicMiner(min_frequency=2)
    result = miner.mine(log)
    # a→b edge appears only once (case c1) → below threshold; same for a→c
    assert ("a", "b") not in result.direct_follows
    assert ("a", "c") not in result.direct_follows


def test_heuristic_miner_min_frequency_must_be_positive():
    with pytest.raises(ValueError, match="min_frequency"):
        HeuristicMiner(min_frequency=0)


# ═════════════════════════════════════════════════════════════════════
# ADOPTION INTEL (AI-SIG-001..006, AI-HSC-010..015)
# ═════════════════════════════════════════════════════════════════════


def test_signal_sample_rejects_score_outside_unit_range():
    """SignalSample contract: score ∈ [0, 1]. Bad input fails loud."""
    with pytest.raises(ValueError):
        SignalSample(signal_id="X", score=1.5, raw_count=0, sample_size=0)
    with pytest.raises(ValueError):
        SignalSample(signal_id="X", score=-0.1, raw_count=0, sample_size=0)


def test_ai_sig_001_no_starts_returns_neutral_score():
    s = AI_SIG_001_workflow_abandonment(starts=0, completions=0)
    assert s.score == 1.0
    assert "no signal" in (s.note or "")


def test_ai_sig_001_full_completion_rate_scores_1():
    s = AI_SIG_001_workflow_abandonment(starts=10, completions=10)
    assert s.score == 1.0
    assert s.raw_count == 0  # 0 abandonments


def test_ai_sig_001_partial_completion_drops_score():
    s = AI_SIG_001_workflow_abandonment(starts=10, completions=4)
    assert s.score == 0.4
    assert s.raw_count == 6  # 6 abandonments


def test_ai_sig_002_high_override_rate_drops_score():
    s = AI_SIG_002_ai_decision_override_rate(decisions=10, overrides=6)
    assert s.score == pytest.approx(0.4)
    assert s.raw_count == 6


def test_ai_sig_003_side_channel_detected_drops_score():
    s = AI_SIG_003_side_channel_detection(
        in_workflow_actions=2, side_channel_actions=8,
    )
    assert s.score == pytest.approx(0.2)
    assert s.raw_count == 8


def test_ai_sig_005_manager_intervention_drops_score():
    s = AI_SIG_005_manager_intervention_frequency(
        completions=10, manager_interventions=3,
    )
    assert s.score == pytest.approx(0.7)


def test_ai_sig_006_under_target_drops_score():
    s = AI_SIG_006_workflow_completion_rate(
        target_completions=10, actual_completions=6,
    )
    assert s.score == 0.6


def test_ai_sig_006_over_target_caps_at_1():
    """Beating target doesn't scale score above 1.0 — overflow doesn't
    inflate composite health."""
    s = AI_SIG_006_workflow_completion_rate(
        target_completions=10, actual_completions=20,
    )
    assert s.score == 1.0


# ─── P15-S9 D6 — 4 remaining signals ────────────────────────────────


# AI-SIG-004 — Workaround file creation (parallel Excel files)


def test_ai_sig_004_no_runs_no_files_returns_neutral():
    """Empty window — neither numerator nor denominator. No signal yet."""
    s = AI_SIG_004_workaround_file_creation(workflow_runs=0, suspicious_files=0)
    assert s.score == 1.0
    assert "no signal" in (s.note or "")


def test_ai_sig_004_no_workarounds_scores_1():
    """Workflow runs but no parallel Excel files = healthy."""
    s = AI_SIG_004_workaround_file_creation(workflow_runs=50, suspicious_files=0)
    assert s.score == 1.0
    assert s.raw_count == 0


def test_ai_sig_004_partial_workaround_proportional_score():
    """5 workaround files vs 50 runs = 10% rate → score 0.9."""
    s = AI_SIG_004_workaround_file_creation(workflow_runs=50, suspicious_files=5)
    assert s.score == pytest.approx(0.9)
    assert s.raw_count == 5
    assert s.sample_size == 50


def test_ai_sig_004_more_workarounds_than_runs_clamps_to_zero():
    """5 workaround files in a window with 1 workflow run → entirely
    bypassed; clamp to 0.0 instead of going negative."""
    s = AI_SIG_004_workaround_file_creation(workflow_runs=1, suspicious_files=5)
    assert s.score == 0.0


# AI-SIG-007 — Negative sentiment


def test_ai_sig_007_no_comments_returns_neutral():
    s = AI_SIG_007_negative_sentiment(total_comments=0, negative_comments=0)
    assert s.score == 1.0
    assert "no signal" in (s.note or "")


def test_ai_sig_007_all_negative_scores_zero():
    s = AI_SIG_007_negative_sentiment(total_comments=10, negative_comments=10)
    assert s.score == 0.0
    assert s.raw_count == 10


def test_ai_sig_007_partial_negative_proportional_score():
    """3 negative out of 10 = 30% → score 0.7."""
    s = AI_SIG_007_negative_sentiment(total_comments=10, negative_comments=3)
    assert s.score == pytest.approx(0.7)


# AI-SIG-008 — Time-on-task variance


def test_ai_sig_008_no_baseline_returns_neutral():
    """A workflow that just went live has no historical baseline yet."""
    s = AI_SIG_008_time_on_task_variance(baseline_seconds=0, observed_seconds=120)
    assert s.score == 1.0
    assert "no baseline" in (s.note or "")


def test_ai_sig_008_observed_at_or_below_baseline_scores_1():
    """Faster than baseline = healthy. Equal = healthy."""
    s = AI_SIG_008_time_on_task_variance(baseline_seconds=120, observed_seconds=90)
    assert s.score == 1.0


def test_ai_sig_008_observed_50_pct_over_baseline_scores_half():
    """observed 1.5x baseline → halfway through the [baseline..2*baseline]
    span → score 0.5."""
    s = AI_SIG_008_time_on_task_variance(baseline_seconds=100, observed_seconds=150)
    assert s.score == pytest.approx(0.5)


def test_ai_sig_008_observed_at_or_above_2x_baseline_scores_zero():
    """Spec threshold — 2x baseline = friction signal → score 0.
    Beyond 2x stays clamped at 0."""
    s = AI_SIG_008_time_on_task_variance(baseline_seconds=100, observed_seconds=200)
    assert s.score == 0.0
    s2 = AI_SIG_008_time_on_task_variance(baseline_seconds=100, observed_seconds=500)
    assert s2.score == 0.0


# AI-SIG-009 — Feature usage decline trend


def test_ai_sig_009_no_baseline_returns_neutral():
    """No prior baseline → workflow just deployed, no decline to detect."""
    s = AI_SIG_009_feature_usage_decline(
        baseline_uses_per_period=0, current_uses_per_period=10,
    )
    assert s.score == 1.0


def test_ai_sig_009_usage_held_or_grew_scores_1():
    """50 → 50 (held) and 50 → 70 (grew) both healthy."""
    held = AI_SIG_009_feature_usage_decline(
        baseline_uses_per_period=50, current_uses_per_period=50,
    )
    grew = AI_SIG_009_feature_usage_decline(
        baseline_uses_per_period=50, current_uses_per_period=70,
    )
    assert held.score == 1.0
    assert grew.score == 1.0


def test_ai_sig_009_spec_example_50_to_30_drops_to_0_6():
    """Spec example: 50/day → 30/day = signal. score = 30/50 = 0.6."""
    s = AI_SIG_009_feature_usage_decline(
        baseline_uses_per_period=50, current_uses_per_period=30,
    )
    assert s.score == pytest.approx(0.6)
    # Composite ranking: 0.6 → 60 → AT_RISK band (50 ≤ x < 70)
    assert "-40%" in (s.note or "")


def test_ai_sig_009_zero_usage_scores_zero():
    """Workflow abandoned this period → score 0."""
    s = AI_SIG_009_feature_usage_decline(
        baseline_uses_per_period=50, current_uses_per_period=0,
    )
    assert s.score == 0.0


# Composite — verify all 9 signals can roll up cleanly


def test_compute_composite_score_with_all_9_signals():
    """All 9 SIG functions plug into compute_composite_score with the
    same SignalSample contract — pinning the integration so a future
    SignalSample shape change can't break the aggregator silently."""
    samples = [
        AI_SIG_001_workflow_abandonment(starts=10, completions=8),
        AI_SIG_002_ai_decision_override_rate(decisions=10, overrides=2),
        AI_SIG_003_side_channel_detection(
            in_workflow_actions=8, side_channel_actions=2,
        ),
        AI_SIG_004_workaround_file_creation(workflow_runs=50, suspicious_files=5),
        AI_SIG_005_manager_intervention_frequency(
            completions=10, manager_interventions=1,
        ),
        AI_SIG_006_workflow_completion_rate(
            target_completions=10, actual_completions=9,
        ),
        AI_SIG_007_negative_sentiment(total_comments=10, negative_comments=2),
        AI_SIG_008_time_on_task_variance(
            baseline_seconds=100, observed_seconds=120,
        ),
        AI_SIG_009_feature_usage_decline(
            baseline_uses_per_period=50, current_uses_per_period=45,
        ),
    ]
    result = compute_composite_score(samples)
    assert len(result.per_signal) == 9
    assert 70 <= result.composite <= 100
    # Healthy band — no resistance dominant in this synthetic mix
    assert result.classification in (
        HealthClassification.EXCELLENT, HealthClassification.HEALTHY,
    )


def test_compute_composite_score_averages_signals():
    samples = [
        SignalSample(signal_id="X", score=1.0, raw_count=0, sample_size=10),
        SignalSample(signal_id="Y", score=0.5, raw_count=5, sample_size=10),
        SignalSample(signal_id="Z", score=0.0, raw_count=10, sample_size=10),
    ]
    result = compute_composite_score(samples)
    assert result.composite == 50.0
    assert result.classification == HealthClassification.AT_RISK
    assert len(result.per_signal) == 3


def test_compute_composite_score_empty_returns_excellent():
    """No signals = no resistance observed = excellent default."""
    result = compute_composite_score([])
    assert result.classification == HealthClassification.EXCELLENT
    assert result.composite == 100.0


@pytest.mark.parametrize("composite,expected", [
    (95.0, HealthClassification.EXCELLENT),
    (85.0, HealthClassification.EXCELLENT),
    (84.9, HealthClassification.HEALTHY),
    (70.0, HealthClassification.HEALTHY),
    (69.9, HealthClassification.AT_RISK),
    (50.0, HealthClassification.AT_RISK),
    (49.9, HealthClassification.STRUGGLING),
    (0.0,  HealthClassification.STRUGGLING),
])
def test_classify_health_threshold_boundaries(composite, expected):
    assert classify_health(composite) == expected


def test_detect_trend_improving():
    assert detect_trend([60, 65, 70, 75, 80]) == "improving"


def test_detect_trend_declining():
    assert detect_trend([80, 75, 70, 65, 60]) == "declining"


def test_detect_trend_stable():
    assert detect_trend([70, 71, 70, 69, 70]) == "stable"


def test_detect_trend_too_few_samples_is_stable():
    assert detect_trend([70]) == "stable"
    assert detect_trend([]) == "stable"


# ═════════════════════════════════════════════════════════════════════
# ECONOMICS / NOV (NOV-REV-001/003/004/005, NOV-CST-007..010, NOV-CORE-013/014/016)
# ═════════════════════════════════════════════════════════════════════


def test_estimate_revenue_pre_post_returns_positive_delta():
    r = estimate_revenue_pre_post(
        revenue_30d_before_vnd=Decimal("100000000"),
        revenue_30d_after_vnd=Decimal("105000000"),
    )
    assert r.revenue_vnd == Decimal("5000000")
    assert r.confidence == Decimal("0.7")
    assert r.method == "pre_post"


def test_estimate_revenue_pre_post_returns_zero_when_negative_delta():
    """Don't claim negative-revenue 'savings' — revenue dropped, that's
    not a Kaori benefit. NOV computation will show overall negative if
    cost outweighs other revenue."""
    r = estimate_revenue_pre_post(
        revenue_30d_before_vnd=Decimal("100000000"),
        revenue_30d_after_vnd=Decimal("90000000"),
    )
    assert r.revenue_vnd == Decimal("0")


def test_estimate_revenue_pre_post_rejects_zero_baseline():
    """No baseline = caller should fall back to industry benchmark."""
    r = estimate_revenue_pre_post(
        revenue_30d_before_vnd=Decimal("0"),
        revenue_30d_after_vnd=Decimal("5000000"),
    )
    assert r.confidence == Decimal("0")
    assert "falling back" in (r.note or "")


def test_estimate_revenue_industry_benchmark_known_industry():
    r = estimate_revenue_industry_benchmark(
        industry="RETAIL", annual_revenue_vnd=Decimal("1200000000"),
    )
    # 5% × 1.2B / 12 = 5M VND/month
    assert r.revenue_vnd == Decimal("5000000.0000")
    assert r.confidence == Decimal("0.4")


def test_estimate_revenue_industry_benchmark_normalises_case():
    """Industry strings come from user input — normalise to upper."""
    r1 = estimate_revenue_industry_benchmark(industry="retail", annual_revenue_vnd=Decimal("12000000"))
    r2 = estimate_revenue_industry_benchmark(industry="RETAIL", annual_revenue_vnd=Decimal("12000000"))
    assert r1.revenue_vnd == r2.revenue_vnd


def test_estimate_revenue_industry_benchmark_unknown_industry_zero():
    r = estimate_revenue_industry_benchmark(
        industry="SPACE_TRAVEL", annual_revenue_vnd=Decimal("1000000000"),
    )
    assert r.revenue_vnd == Decimal("0")
    assert r.confidence == Decimal("0")


def test_industry_benchmarks_keys_are_uppercase():
    """Catch typos: lowercase keys would cause silent-zero industry
    lookups even when normalised."""
    for key in INDUSTRY_BENCHMARKS:
        assert key == key.upper()


# ---------------------------------------------------------------------------
# NOV-REV-002 — A/B attribution method (P15-S10 D5)
# ---------------------------------------------------------------------------


def test_estimate_revenue_ab_treatment_beats_control_attributes_uplift():
    """Treatment per-user > control per-user → positive uplift attributed
    to total population (defaults to sum of both groups)."""
    r = estimate_revenue_ab_attribution(
        control_revenue_vnd=Decimal("100000000"),    # 100M VND across 100 users = 1M/user
        treatment_revenue_vnd=Decimal("120000000"),  # 120M VND across 100 users = 1.2M/user
        control_group_size=100,
        treatment_group_size=100,
    )
    # Δ/user = 200,000 VND × population (200) = 40,000,000 VND
    assert r.method == "a_b"
    assert r.revenue_vnd == Decimal("40000000.0000")
    assert r.confidence == Decimal("0.8")  # both groups in [100, 1000) bucket


def test_estimate_revenue_ab_treatment_loses_returns_zero():
    """Treatment underperforms → revenue_vnd = 0 but confidence + note
    still convey the experiment outcome."""
    r = estimate_revenue_ab_attribution(
        control_revenue_vnd=Decimal("120000000"),    # 1.2M/user
        treatment_revenue_vnd=Decimal("100000000"),  # 1M/user
        control_group_size=100,
        treatment_group_size=100,
    )
    assert r.revenue_vnd == Decimal("0")
    assert r.confidence == Decimal("0.8")
    assert "treatment did not beat control" in r.note


def test_estimate_revenue_ab_scales_to_explicit_population():
    """When total_population is supplied, scale to it rather than the
    experiment cohort sum (i.e. project the uplift to a 100% rollout)."""
    r = estimate_revenue_ab_attribution(
        control_revenue_vnd=Decimal("100000000"),
        treatment_revenue_vnd=Decimal("120000000"),
        control_group_size=100,
        treatment_group_size=100,
        total_population=10_000,
    )
    # Δ/user = 200,000 × 10,000 = 2,000,000,000 VND
    assert r.revenue_vnd == Decimal("2000000000.0000")


def test_estimate_revenue_ab_zero_group_size_returns_zero():
    """Zero or negative group size = malformed experiment; return 0 +
    error note rather than ZeroDivisionError."""
    r = estimate_revenue_ab_attribution(
        control_revenue_vnd=Decimal("0"),
        treatment_revenue_vnd=Decimal("100000000"),
        control_group_size=0,
        treatment_group_size=100,
    )
    assert r.revenue_vnd == Decimal("0")
    assert r.confidence == Decimal("0")
    assert "requires both groups" in r.note


def test_estimate_revenue_ab_confidence_tiers():
    """Sample-size thresholds: <30 → 0.2, <100 → 0.5, <1000 → 0.8, ≥1000 → 0.9."""
    base = dict(
        control_revenue_vnd=Decimal("0"),
        treatment_revenue_vnd=Decimal("0"),
    )
    # Tiny sample — both 25
    tiny = estimate_revenue_ab_attribution(
        **base, control_group_size=25, treatment_group_size=25,
    )
    assert tiny.confidence == Decimal("0.2")

    # Acceptable — both 50
    acceptable = estimate_revenue_ab_attribution(
        **base, control_group_size=50, treatment_group_size=50,
    )
    assert acceptable.confidence == Decimal("0.5")

    # Good — both 500
    good = estimate_revenue_ab_attribution(
        **base, control_group_size=500, treatment_group_size=500,
    )
    assert good.confidence == Decimal("0.8")

    # High — both 5000
    high = estimate_revenue_ab_attribution(
        **base, control_group_size=5000, treatment_group_size=5000,
    )
    assert high.confidence == Decimal("0.9")


def test_estimate_revenue_ab_confidence_uses_smaller_group():
    """Confidence is bounded by the SMALLER group (statistical power
    is gated by the smaller sample, not the larger)."""
    r = estimate_revenue_ab_attribution(
        control_revenue_vnd=Decimal("0"),
        treatment_revenue_vnd=Decimal("0"),
        control_group_size=10000,    # huge
        treatment_group_size=20,     # tiny
    )
    assert r.confidence == Decimal("0.2")


def test_estimate_people_cost_time_times_rate():
    cost = estimate_people_cost(
        hours_required=Decimal("10"), hourly_rate_vnd=Decimal("200000"),
    )
    assert cost == Decimal("2000000.0000")


def test_estimate_people_cost_negative_hours_returns_zero():
    cost = estimate_people_cost(
        hours_required=Decimal("-5"), hourly_rate_vnd=Decimal("200000"),
    )
    assert cost == Decimal("0")


def test_estimate_ai_token_cost_per_1k_pricing():
    # 1000 input + 500 output, 100/1k input + 200/1k output = 100 + 100 = 200
    cost = estimate_ai_token_cost(
        tokens_input=1000, tokens_output=500,
        cost_per_1k_input_vnd=Decimal("100"),
        cost_per_1k_output_vnd=Decimal("200"),
    )
    assert cost == Decimal("200.0000")


def test_estimate_integration_cost_zero_calls_returns_zero():
    cost = estimate_integration_cost(
        api_calls=0, cost_per_call_vnd=Decimal("100"),
    )
    assert cost == Decimal("0")


def test_compute_monthly_nov_positive():
    nov = compute_monthly_nov(
        revenue_vnd=Decimal("10000000"),
        cost_vnd=Decimal("3000000"),
    )
    assert nov.nov_vnd == Decimal("7000000.0000")
    assert not nov.is_negative()


def test_compute_monthly_nov_negative_triggers_alert_helper():
    nov = compute_monthly_nov(
        revenue_vnd=Decimal("1000000"),
        cost_vnd=Decimal("3000000"),
    )
    assert nov.nov_vnd == Decimal("-2000000.0000")
    assert nov.is_negative()  # NOV-CORE-016 alert helper


def test_time_to_payback_months_normal_case():
    # 10M upfront / 2M monthly savings = 5 months
    assert time_to_payback_months(
        upfront_cost_vnd=Decimal("10000000"),
        monthly_net_savings_vnd=Decimal("2000000"),
    ) == 5


def test_time_to_payback_months_partial_month_rounds_up():
    # 10M / 3M = 3.33... months → 4 (must clear breakeven)
    assert time_to_payback_months(
        upfront_cost_vnd=Decimal("10000000"),
        monthly_net_savings_vnd=Decimal("3000000"),
    ) == 4


def test_time_to_payback_months_returns_none_when_savings_nonpositive():
    """Workflow won't pay back at current rate — caller surfaces 'never'."""
    assert time_to_payback_months(
        upfront_cost_vnd=Decimal("10000000"),
        monthly_net_savings_vnd=Decimal("0"),
    ) is None
    assert time_to_payback_months(
        upfront_cost_vnd=Decimal("10000000"),
        monthly_net_savings_vnd=Decimal("-1000"),
    ) is None
