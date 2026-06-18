"""Stage 12 — Loop tests (BaselineTracker + ABTestFramework + PromotionEngine).

Pure Python. Pre-populates the tracker with synthetic observations,
runs an evaluation, then asserts the promotion decision.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.org_intel.loop import (
    ABTestFramework,
    BaselineTracker,
    ExperimentArm,
    Observation,
    PromotionEngine,
)
from ai_orchestrator.org_intel.loop.promotion import PromotionAction


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")


def _seed_observations(
    tracker: BaselineTracker, *,
    tenant_id: UUID, metric: str, count: int,
    mean: float, stddev: float = 0.1,
    days_ago_start: int = 60, days_ago_end: int = 0,
    experiment_id: str | None = None, arm: str | None = None,
    seed: int = 42,
) -> None:
    rng = random.Random(seed)
    span = max(1, days_ago_start - days_ago_end)
    base_now = datetime.now(timezone.utc)
    for i in range(count):
        days_offset = days_ago_end + (i * span / count)
        occurred = base_now - timedelta(days=days_offset)
        tracker.record(Observation(
            tenant_id=tenant_id,
            metric_name=metric,
            value=rng.gauss(mean, stddev),
            occurred_at=occurred,
            experiment_id=experiment_id, arm=arm,
        ))


# ─── BaselineTracker ────────────────────────────────────────────────


class TestBaselineTracker:

    def test_record_and_summary(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="conv_rate",
                            count=50, mean=0.10, stddev=0.01)
        summ = tr.summary(T1, "conv_rate")
        assert summ.sample_size == 50
        assert summ.is_valid
        assert summ.mean == pytest.approx(0.10, abs=0.02)
        assert summ.stddev > 0

    def test_summary_empty_returns_zero_sample(self):
        tr = BaselineTracker()
        summ = tr.summary(T1, "no_data")
        assert summ.sample_size == 0
        assert not summ.is_valid

    def test_summary_tenant_isolated(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="conv_rate", count=50, mean=0.1)
        summ_t2 = tr.summary(T2, "conv_rate")
        assert summ_t2.sample_size == 0

    def test_window_excludes_old_observations(self):
        tr = BaselineTracker()
        # 50 fresh + 30 old (>60 days)
        _seed_observations(tr, tenant_id=T1, metric="m", count=50, mean=1.0,
                            days_ago_start=30, days_ago_end=0)
        _seed_observations(tr, tenant_id=T1, metric="m", count=30, mean=99.0,
                            days_ago_start=120, days_ago_end=70, seed=7)
        # 60-day window: only the fresh 50 should count
        summ = tr.summary(T1, "m", window_days=60)
        assert summ.sample_size == 50
        assert summ.mean == pytest.approx(1.0, abs=0.5)

    def test_summary_arm_filter(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="m", count=40, mean=1.0,
                            experiment_id="exp-001", arm="treatment")
        _seed_observations(tr, tenant_id=T1, metric="m", count=40, mean=2.0,
                            experiment_id="exp-001", arm="control", seed=9)
        treat = tr.summary(T1, "m", experiment_id="exp-001", arm="treatment")
        ctrl  = tr.summary(T1, "m", experiment_id="exp-001", arm="control")
        assert treat.mean == pytest.approx(1.0, abs=0.5)
        assert ctrl.mean == pytest.approx(2.0, abs=0.5)

    def test_is_valid_below_30_samples(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="m", count=20, mean=1.0)
        summ = tr.summary(T1, "m")
        assert not summ.is_valid

    def test_forget_tenant_wipes_only_target(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="m", count=10, mean=1.0)
        _seed_observations(tr, tenant_id=T2, metric="m", count=10, mean=2.0, seed=11)
        wiped = tr.forget(T1)
        assert wiped == 10
        assert tr.summary(T2, "m").sample_size == 10
        assert tr.summary(T1, "m").sample_size == 0


# ─── ABTestFramework ────────────────────────────────────────────────


class TestABTestFramework:

    @pytest.fixture
    def tracker_with_baseline(self):
        tr = BaselineTracker()
        # 50 baseline observations: mean 0.10, stddev 0.01
        _seed_observations(tr, tenant_id=T1, metric="conv_rate",
                            count=50, mean=0.10, stddev=0.01,
                            days_ago_start=60, days_ago_end=30)
        return tr

    def test_treatment_wins_with_large_lift(self, tracker_with_baseline):
        # Treatment: 40 observations with 30% lift
        _seed_observations(tracker_with_baseline, tenant_id=T1,
                            metric="conv_rate", count=40, mean=0.13, stddev=0.01,
                            days_ago_start=30, days_ago_end=0,
                            experiment_id="exp-1", arm="treatment", seed=100)
        ab = ABTestFramework(tracker_with_baseline)
        result = ab.evaluate(tenant_id=T1, experiment_id="exp-1",
                              metric_name="conv_rate")
        assert result.conclusion == "treatment_wins"
        assert result.relative_lift > 0.05
        assert result.t_statistic > 1.96

    def test_inconclusive_when_baseline_too_small(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="m", count=10, mean=0.1)
        ab = ABTestFramework(tr)
        result = ab.evaluate(tenant_id=T1, experiment_id="x", metric_name="m")
        assert result.conclusion == "inconclusive"
        assert "baseline too small" in result.reason

    def test_inconclusive_when_treatment_arm_too_small(self, tracker_with_baseline):
        # Only 5 treatment samples
        _seed_observations(tracker_with_baseline, tenant_id=T1,
                            metric="conv_rate", count=5, mean=0.13,
                            days_ago_start=10, days_ago_end=0,
                            experiment_id="exp-tiny", arm="treatment", seed=2)
        ab = ABTestFramework(tracker_with_baseline)
        result = ab.evaluate(tenant_id=T1, experiment_id="exp-tiny",
                              metric_name="conv_rate")
        assert result.conclusion == "inconclusive"
        assert "treatment arm too small" in result.reason

    def test_inconclusive_when_lift_small(self, tracker_with_baseline):
        # Treatment ≈ baseline (1% lift, far below 5% threshold)
        _seed_observations(tracker_with_baseline, tenant_id=T1,
                            metric="conv_rate", count=40, mean=0.101, stddev=0.01,
                            days_ago_start=30, days_ago_end=0,
                            experiment_id="exp-flat", arm="treatment", seed=3)
        ab = ABTestFramework(tracker_with_baseline)
        result = ab.evaluate(tenant_id=T1, experiment_id="exp-flat",
                              metric_name="conv_rate")
        assert result.conclusion == "inconclusive"

    def test_control_wins_when_treatment_drops(self, tracker_with_baseline):
        # Treatment significantly worse than baseline
        _seed_observations(tracker_with_baseline, tenant_id=T1,
                            metric="conv_rate", count=40, mean=0.05, stddev=0.01,
                            days_ago_start=30, days_ago_end=0,
                            experiment_id="exp-bad", arm="treatment", seed=4)
        ab = ABTestFramework(tracker_with_baseline)
        result = ab.evaluate(tenant_id=T1, experiment_id="exp-bad",
                              metric_name="conv_rate")
        assert result.conclusion == "control_wins"
        assert result.relative_lift < -0.05


# ─── PromotionEngine ────────────────────────────────────────────────


class TestPromotionEngine:

    @pytest.fixture
    def winning_result(self):
        tr = BaselineTracker()
        _seed_observations(tr, tenant_id=T1, metric="conv_rate",
                            count=50, mean=0.10, stddev=0.01,
                            days_ago_start=60, days_ago_end=30)
        _seed_observations(tr, tenant_id=T1, metric="conv_rate",
                            count=40, mean=0.13, stddev=0.01,
                            days_ago_start=30, days_ago_end=0,
                            experiment_id="exp-1", arm="treatment", seed=100)
        return ABTestFramework(tr).evaluate(tenant_id=T1, experiment_id="exp-1",
                                              metric_name="conv_rate")

    def test_treatment_wins_action_replace(self, winning_result):
        eng = PromotionEngine()
        decision = eng.decide(winning_result)
        assert decision.action == PromotionAction.REPLACE_BASELINE
        assert decision.tenant_id == T1
        assert decision.experiment_id == "exp-1"

    def test_inconclusive_near_threshold_suggests_extend(self):
        """Directly construct an ABTestResult with |t| in the extend
        band (0.8 × 1.96 ≤ |t| < 1.96) so the threshold logic itself
        is the test target (not the random sample-generation path)."""
        from ai_orchestrator.org_intel.loop.ab_test import ABTestResult
        from ai_orchestrator.org_intel.loop.baseline import BaselineSummary
        now = datetime.now(timezone.utc)
        ctrl = BaselineSummary(
            tenant_id=T1, metric_name="m",
            window_start=now - timedelta(days=60), window_end=now,
            sample_size=40, mean=0.10, variance=0.01, stddev=0.1,
        )
        treat = BaselineSummary(
            tenant_id=T1, metric_name="m",
            window_start=now - timedelta(days=30), window_end=now,
            sample_size=40, mean=0.115, variance=0.01, stddev=0.1,
        )
        near = ABTestResult(
            tenant_id=T1, experiment_id="exp-near", metric_name="m",
            control=ctrl, treatment=treat,
            relative_lift=0.15, t_statistic=1.7,   # in extend band
            conclusion="inconclusive",
            reason="|t|=1.70 < 1.96",
            computed_at=now,
        )
        decision = PromotionEngine().decide(near)
        assert decision.action == PromotionAction.EXTEND_WINDOW

    def test_far_below_threshold_keeps_baseline(self):
        from ai_orchestrator.org_intel.loop.ab_test import ABTestResult
        from ai_orchestrator.org_intel.loop.baseline import BaselineSummary
        now = datetime.now(timezone.utc)
        ctrl  = BaselineSummary(tenant_id=T1, metric_name="m", window_start=now,
                                  window_end=now, sample_size=40, mean=0.10,
                                  variance=0.01, stddev=0.1)
        treat = BaselineSummary(tenant_id=T1, metric_name="m", window_start=now,
                                  window_end=now, sample_size=40, mean=0.101,
                                  variance=0.01, stddev=0.1)
        flat = ABTestResult(tenant_id=T1, experiment_id="exp-flat", metric_name="m",
                              control=ctrl, treatment=treat,
                              relative_lift=0.01, t_statistic=0.2,
                              conclusion="inconclusive",
                              reason="lift below threshold", computed_at=now)
        decision = PromotionEngine().decide(flat)
        assert decision.action == PromotionAction.KEEP_BASELINE

    def test_decision_audit_fields_present(self, winning_result):
        eng = PromotionEngine()
        decision = eng.decide(winning_result, actor="studio_analyst")
        assert decision.decision_id is not None
        assert decision.decided_at is not None
        assert decision.actor == "studio_analyst"
        assert "lift" in decision.rationale.lower()
