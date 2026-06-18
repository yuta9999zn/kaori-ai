"""Tests for intervention tracker (D3) + Vietnamese context resolver (D4)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from org_intel.adoption import (
    ApprovalGate,
    CHECKPOINT_DAYS,
    EFFECTIVE_IMPROVEMENT_THRESHOLD,
    HealthClassification,
    HealthScore,
    InterventionBaseline,
    InterventionChannel,
    InterventionMisconfigError,
    InterventionOutcomeClass,
    InterventionPlan,
    TenantInterventionSettings,
    capture_baseline,
    evaluate_at_checkpoint,
    project_checkpoint_due_at,
    resolve_intervention_plan,
)


_TEST_ENT = UUID("00000000-0000-0000-0001-000000011577")
_TEST_TIME = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)


def _score(value: float) -> HealthScore:
    """Helper — synthesize a HealthScore at the requested composite."""
    return HealthScore(
        composite=value,
        classification=HealthClassification.HEALTHY,
        per_signal=(),
    )


# ---------------------------------------------------------------------------
# D3 — capture_baseline + outcome classification + checkpoint scheduling
# ---------------------------------------------------------------------------


def test_capture_baseline_constructs_dataclass():
    b = capture_baseline(
        intervention_id="int-1",
        workflow_id="wf-1",
        enterprise_id=_TEST_ENT,
        intervention_type="csm_email",
        triggered_at=_TEST_TIME,
        pre_score=72.5,
    )
    assert b.intervention_id == "int-1"
    assert b.pre_score == 72.5
    assert b.intervention_type == "csm_email"


def test_capture_baseline_rejects_score_outside_range():
    """Pre-score must be in [0, 100]; mirrors HealthScore.__post_init__."""
    with pytest.raises(ValueError):
        capture_baseline(
            intervention_id="int-1", workflow_id="wf-1",
            enterprise_id=_TEST_ENT, intervention_type="csm_email",
            triggered_at=_TEST_TIME, pre_score=150.0,
        )


def test_evaluate_classifies_effective_when_improvement_above_5():
    """Per spec WORKFLOW_SYSTEM.md §31.4 — improvement > 5 = effective."""
    baseline = _make_baseline(pre_score=60.0)

    async def reader(_wf, _ent):
        return _score(70.0)            # +10 improvement

    ck = asyncio.run(
        evaluate_at_checkpoint(
            baseline=baseline, checkpoint_days=14, score_reader=reader,
        )
    )
    assert ck.classification == InterventionOutcomeClass.EFFECTIVE
    assert ck.improvement == 10.0
    assert ck.checkpoint_days == 14


def test_evaluate_classifies_neutral_within_noise_floor():
    """|improvement| ≤ 5 = noise floor → NEUTRAL."""
    baseline = _make_baseline(pre_score=70.0)

    async def reader(_wf, _ent):
        return _score(73.0)            # +3 → neutral

    ck = asyncio.run(
        evaluate_at_checkpoint(
            baseline=baseline, checkpoint_days=30, score_reader=reader,
        )
    )
    assert ck.classification == InterventionOutcomeClass.NEUTRAL


def test_evaluate_classifies_regression_when_improvement_below_minus_5():
    """improvement < -5 = REGRESSION (intervention backfired)."""
    baseline = _make_baseline(pre_score=70.0)

    async def reader(_wf, _ent):
        return _score(58.0)            # -12 improvement

    ck = asyncio.run(
        evaluate_at_checkpoint(
            baseline=baseline, checkpoint_days=14, score_reader=reader,
        )
    )
    assert ck.classification == InterventionOutcomeClass.REGRESSION
    assert ck.improvement == -12.0


def test_evaluate_rejects_arbitrary_checkpoint_day():
    """checkpoint_days must be in CHECKPOINT_DAYS (14, 30) per spec."""
    baseline = _make_baseline(pre_score=70.0)

    async def reader(_wf, _ent):
        return _score(75.0)

    with pytest.raises(ValueError):
        asyncio.run(
            evaluate_at_checkpoint(
                baseline=baseline, checkpoint_days=7, score_reader=reader,
            )
        )


def test_evaluate_calls_side_effect_detector_when_supplied():
    """Optional side_effect_detector is called + result lands on the
    checkpoint dataclass."""
    baseline = _make_baseline(pre_score=70.0)

    async def reader(_wf, _ent):
        return _score(75.0)

    detector_calls: list[InterventionBaseline] = []

    def detector(b):
        detector_calls.append(b)
        return ["override_rate_spiked"]

    ck = asyncio.run(
        evaluate_at_checkpoint(
            baseline=baseline, checkpoint_days=14,
            score_reader=reader, side_effect_detector=detector,
        )
    )
    assert detector_calls == [baseline]
    assert ck.side_effects == ("override_rate_spiked",)


def test_project_checkpoint_due_at_adds_days():
    baseline = _make_baseline(pre_score=70.0)
    due_14 = project_checkpoint_due_at(baseline, 14)
    due_30 = project_checkpoint_due_at(baseline, 30)
    assert due_14 == _TEST_TIME + timedelta(days=14)
    assert due_30 == _TEST_TIME + timedelta(days=30)


def test_project_checkpoint_due_at_rejects_arbitrary_day():
    baseline = _make_baseline(pre_score=70.0)
    with pytest.raises(ValueError):
        project_checkpoint_due_at(baseline, 7)


def test_threshold_constant_value():
    """Catch typos: spec WORKFLOW_SYSTEM.md §31.4 says 5 score-points."""
    assert EFFECTIVE_IMPROVEMENT_THRESHOLD == 5.0
    assert CHECKPOINT_DAYS == (14, 30)


# ---------------------------------------------------------------------------
# D4 — Vietnamese context resolver
# ---------------------------------------------------------------------------


def test_resolve_vi_zalo_configured_picks_zalo_auto():
    """Vietnamese tenant + Zalo OA → ZALO channel + AUTO gate (default)."""
    plan = resolve_intervention_plan(
        TenantInterventionSettings(
            locale="vi", zalo_oa_configured=True, telegram_chat_id="abc",
        )
    )
    assert plan.channel == InterventionChannel.ZALO
    assert plan.gate == ApprovalGate.AUTO
    assert plan.locale == "vi"


def test_resolve_vi_telegram_only_picks_telegram():
    """Vietnamese tenant, no Zalo, but Telegram bound → TELEGRAM (S9 D5)."""
    plan = resolve_intervention_plan(
        TenantInterventionSettings(
            locale="vi", zalo_oa_configured=False, telegram_chat_id="abc",
        )
    )
    assert plan.channel == InterventionChannel.TELEGRAM


def test_resolve_vi_no_vietnamese_channel_falls_back_to_email():
    """Vietnamese tenant + no Zalo + no Telegram → EMAIL graceful fallback."""
    plan = resolve_intervention_plan(
        TenantInterventionSettings(
            locale="vi", zalo_oa_configured=False, telegram_chat_id=None,
        )
    )
    assert plan.channel == InterventionChannel.EMAIL


def test_resolve_en_locale_picks_email():
    """International tenant defaults to email (no locale-specific
    adapter wired Phase 1.5)."""
    plan = resolve_intervention_plan(
        TenantInterventionSettings(
            locale="en", zalo_oa_configured=True, telegram_chat_id="abc",
        )
    )
    assert plan.channel == InterventionChannel.EMAIL


def test_resolve_manager_approval_with_telegram_gates():
    """requires_manager_approval=True + telegram_chat_id → MANAGER_APPROVAL."""
    plan = resolve_intervention_plan(
        TenantInterventionSettings(
            locale="vi", zalo_oa_configured=False, telegram_chat_id="abc",
            requires_manager_approval=True,
        )
    )
    assert plan.gate == ApprovalGate.MANAGER_APPROVAL


def test_resolve_manager_approval_no_telegram_raises_misconfig():
    """Misconfig fail-closed (post-I1): tenant wants approval but no
    Telegram → raise so the workflow surfaces it. K-6 spirit: an audit
    gate the tenant configured must never be silently bypassed.
    """
    with pytest.raises(InterventionMisconfigError) as exc:
        resolve_intervention_plan(
            TenantInterventionSettings(
                locale="vi", zalo_oa_configured=True, telegram_chat_id=None,
                requires_manager_approval=True,
            )
        )
    assert "telegram_chat_id" in str(exc.value)


def test_resolve_locale_normalises_case():
    """'VI' or 'Vi' should resolve same as 'vi'."""
    plan = resolve_intervention_plan(
        TenantInterventionSettings(
            locale="VI", zalo_oa_configured=True,
        )
    )
    assert plan.channel == InterventionChannel.ZALO
    assert plan.locale == "vi"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_baseline(*, pre_score: float) -> InterventionBaseline:
    return capture_baseline(
        intervention_id="int-1",
        workflow_id="wf-1",
        enterprise_id=_TEST_ENT,
        intervention_type="csm_email",
        triggered_at=_TEST_TIME,
        pre_score=pre_score,
    )
