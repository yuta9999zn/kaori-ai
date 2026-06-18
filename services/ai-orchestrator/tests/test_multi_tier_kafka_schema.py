"""
F-033 — Validate that the new Kafka schema files load + accept the
exact payload shape multi_tier.service.py emits. Issue #4 producer-
side validation runs before every outbox write, so a broken schema
crashes the run with InvalidEventError; this is the regression guard.
"""
from __future__ import annotations

import pytest

from ai_orchestrator.shared.event_schema import (
    InvalidEventError,
    validate_event,
)
from ai_orchestrator.shared import kafka_topics


_ENT_ID  = "11111111-1111-1111-1111-111111111111"
_RUN_ID  = "22222222-2222-2222-2222-222222222222"


# ─── started ─────────────────────────────────────────────────────


def test_started_schema_accepts_basic_payload():
    validate_event(kafka_topics.ANALYSIS_TIER_STARTED, {
        "analysis_run_id": _RUN_ID,
        "enterprise_id":   _ENT_ID,
        "tier":            "basic",
        "scope":           "single",
        "framework":       None,
    })


def test_started_schema_accepts_intermediate_payload():
    validate_event(kafka_topics.ANALYSIS_TIER_STARTED, {
        "analysis_run_id": _RUN_ID,
        "enterprise_id":   _ENT_ID,
        "tier":            "intermediate",
        "scope":           "multi",
        "framework":       "swot",
    })


def test_started_schema_rejects_unknown_tier():
    with pytest.raises(InvalidEventError):
        validate_event(kafka_topics.ANALYSIS_TIER_STARTED, {
            "analysis_run_id": _RUN_ID,
            "enterprise_id":   _ENT_ID,
            "tier":            "expert",  # not in enum
            "scope":           "single",
        })


def test_started_schema_rejects_unknown_scope():
    with pytest.raises(InvalidEventError):
        validate_event(kafka_topics.ANALYSIS_TIER_STARTED, {
            "analysis_run_id": _RUN_ID,
            "enterprise_id":   _ENT_ID,
            "tier":            "basic",
            "scope":           "global",  # not in enum
        })


def test_started_schema_requires_run_id():
    with pytest.raises(InvalidEventError):
        validate_event(kafka_topics.ANALYSIS_TIER_STARTED, {
            "enterprise_id": _ENT_ID,
            "tier":          "basic",
            "scope":         "single",
        })


# ─── completed ───────────────────────────────────────────────────


def test_completed_schema_accepts_done():
    validate_event(kafka_topics.ANALYSIS_TIER_COMPLETED, {
        "analysis_run_id": _RUN_ID,
        "enterprise_id":   _ENT_ID,
        "status":          "done",
    })


def test_completed_schema_accepts_error():
    validate_event(kafka_topics.ANALYSIS_TIER_COMPLETED, {
        "analysis_run_id": _RUN_ID,
        "enterprise_id":   _ENT_ID,
        "status":          "error",
    })


def test_completed_schema_rejects_running_status():
    """Only terminal states emit on this topic — guards consumer
    invariant: no more events for a given run after status='done|error'."""
    with pytest.raises(InvalidEventError):
        validate_event(kafka_topics.ANALYSIS_TIER_COMPLETED, {
            "analysis_run_id": _RUN_ID,
            "enterprise_id":   _ENT_ID,
            "status":          "running",
        })
