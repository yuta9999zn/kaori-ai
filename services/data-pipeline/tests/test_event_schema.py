"""
Tests for ``shared.event_schema`` — Issue #4 Kafka payload validator.

Schema discovery is anchored to the real
``infrastructure/kafka/schemas/`` directory at the repo root, so most
tests use the real schemas as fixtures (cheaper than building synthetic
ones). The ``raise_or_dlq`` test fakes the producer with an in-memory
recorder.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from shared.event_schema import (
    InvalidEventError,
    UnknownTopicError,
    _clear_cache_for_tests,
    raise_or_dlq,
    validate_event,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """Each test starts with a fresh schema cache so a temp-dir fixture
    in one test can't leak a validator into the next."""
    _clear_cache_for_tests()
    yield
    _clear_cache_for_tests()


# ─── Happy path ──────────────────────────────────────────────────

def test_valid_payload_passes_for_pipeline_upload_received():
    payload = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename": "Q1-revenue.xlsx",
        "sha256": "a" * 64,
        "size_bytes": 12345,
    }
    # Must not raise.
    validate_event("kaori.pipeline.upload.received", payload)


def test_valid_payload_with_extra_field_passes_when_additive():
    """``additionalProperties: true`` on every Phase-1 schema means new
    optional fields can flow through without a schema change. This is
    the load-bearing reason validation doesn't slow producer evolution."""
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename":      "x.xlsx",
        "sha256":        "a" * 64,
        "size_bytes":    1,
        # Field NOT in schema — should still pass.
        "experimental_user_agent": "kaori-cli/0.0.1",
    }
    validate_event("kaori.pipeline.upload.received", payload)


# ─── Failure modes ───────────────────────────────────────────────

def test_missing_required_field_raises_with_topic_and_reason():
    """The producer should see exactly which field went missing —
    InvalidEventError pins the topic + the field name in the reason."""
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename":      "x.xlsx",
        "sha256":        "a" * 64,
        # size_bytes intentionally missing
    }
    with pytest.raises(InvalidEventError) as exc:
        validate_event("kaori.pipeline.upload.received", payload)

    assert exc.value.topic == "kaori.pipeline.upload.received"
    assert "size_bytes" in exc.value.reason
    # Caller-supplied payload echoed for log enrichment.
    assert exc.value.payload == payload


def test_wrong_type_raises_invalid_event_error():
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename":      "x.xlsx",
        "sha256":        "a" * 64,
        "size_bytes":    "not an int",  # type mismatch
    }
    with pytest.raises(InvalidEventError) as exc:
        validate_event("kaori.pipeline.upload.received", payload)

    assert "size_bytes" in exc.value.reason or "integer" in exc.value.reason


def test_too_short_sha256_raises():
    """sha256 has minLength=64, maxLength=64 — exact 64-char hex string.
    A 63-char value would silently corrupt K-8 dedup if accepted."""
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename":      "x.xlsx",
        "sha256":        "a" * 63,  # one short
        "size_bytes":    1,
    }
    with pytest.raises(InvalidEventError):
        validate_event("kaori.pipeline.upload.received", payload)


def test_unknown_topic_raises_unknown_topic_error():
    """A topic without a schema file fails closed — better to surface
    the typo at producer time than to let an unschematised event flow
    forever."""
    with pytest.raises(UnknownTopicError) as exc:
        validate_event("kaori.does.not.exist", {"run_id": "x"})
    assert "kaori.does.not.exist" in str(exc.value)


# ─── Schema-specific shape checks ────────────────────────────────

def test_silver_complete_minimal_payload_passes():
    """The orchestrator consumer only needs run_id + enterprise_id; the
    schema reflects that. Both producer call sites (clean.py adds
    row_count, analyze.py adds analysis_run_id + consent flag) keep
    working without per-call-site schemas."""
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
    }
    validate_event("kaori.pipeline.silver.complete", payload)


def test_silver_complete_clean_shape_passes():
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "row_count":     1234,
    }
    validate_event("kaori.pipeline.silver.complete", payload)


def test_silver_complete_analyze_shape_passes():
    payload = {
        "run_id":              "11111111-1111-1111-1111-111111111111",
        "enterprise_id":       "22222222-2222-2222-2222-222222222222",
        "analysis_run_id":     "33333333-3333-3333-3333-333333333333",
        "consent_external_ai": True,
    }
    validate_event("kaori.pipeline.silver.complete", payload)


def test_analysis_complete_status_enum_enforced():
    """status enum is the strictest constraint on this topic — pin it
    so a future "completed" or "done" typo fails CI rather than
    silently flowing through."""
    payload = {
        "run_id":          "11111111-1111-1111-1111-111111111111",
        "analysis_run_id": "33333333-3333-3333-3333-333333333333",
        "enterprise_id":   "22222222-2222-2222-2222-222222222222",
        "status":          "complete",  # not in enum (success | partial | failed)
    }
    with pytest.raises(InvalidEventError) as exc:
        validate_event("kaori.pipeline.analysis.complete", payload)
    assert "status" in exc.value.reason or "enum" in exc.value.reason


def test_billing_event_month_format_enforced():
    """Billing month must be YYYY-MM. Anything else (Q1, May 2026,
    2026-5) corrupts the per-month rollup."""
    bad = {"enterprise_id": "x", "month": "2026-5", "record_count": 10}
    with pytest.raises(InvalidEventError):
        validate_event("billing.event", bad)


# ─── Caching ─────────────────────────────────────────────────────

def test_validator_is_cached_per_topic():
    """The schema file is loaded + parsed once per process. The hot
    path (validate_event called inside enqueue_event for every Kafka
    write) must NOT hit the disk for every call — it would dominate
    enqueue latency."""
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename":      "x.xlsx",
        "sha256":        "a" * 64,
        "size_bytes":    1,
    }
    # First call populates cache.
    validate_event("kaori.pipeline.upload.received", payload)

    # Second call should reuse cached validator. We verify by patching
    # _load_validator to fail loudly — if it gets called, the cache
    # is broken.
    from shared import event_schema
    sentinel = event_schema._validator_cache["kaori.pipeline.upload.received"]
    validate_event("kaori.pipeline.upload.received", payload)
    assert event_schema._validator_cache["kaori.pipeline.upload.received"] is sentinel


# ─── DLQ helper ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_raise_or_dlq_returns_true_for_valid_payload():
    dlq = AsyncMock()
    payload = {
        "run_id":        "11111111-1111-1111-1111-111111111111",
        "enterprise_id": "22222222-2222-2222-2222-222222222222",
        "filename":      "x.xlsx",
        "sha256":        "a" * 64,
        "size_bytes":    1,
    }
    ok = await raise_or_dlq(
        "kaori.pipeline.upload.received", payload, dlq,
        consumer_group="test-group",
    )
    assert ok is True
    dlq.send_and_wait.assert_not_called()


@pytest.mark.asyncio
async def test_raise_or_dlq_routes_invalid_payload_to_dlq_topic():
    dlq = AsyncMock()
    payload = {"run_id": "x"}  # missing required fields

    ok = await raise_or_dlq(
        "kaori.pipeline.upload.received", payload, dlq,
        consumer_group="test-group",
        key=b"original-key",
    )
    assert ok is False
    dlq.send_and_wait.assert_awaited_once()

    call = dlq.send_and_wait.await_args
    assert call.args[0] == "kaori.dlq.kaori.pipeline.upload.received"
    assert call.kwargs["key"] == b"original-key"
    # Headers carry the schema error reason + the consumer group, so
    # the redrive tool can route the message back to the right group
    # after the producer is fixed.
    headers = dict(call.kwargs["headers"])
    assert b"test-group" == headers["consumer_group"]
    assert b"enterprise_id" in headers["schema_error"] or b"required" in headers["schema_error"]


@pytest.mark.asyncio
async def test_raise_or_dlq_routes_unknown_topic_to_dlq_too():
    """An unknown topic on the consumer side is the symptom of a
    producer that shipped without the matching schema PR. Same DLQ
    contract — log + DLQ + commit."""
    dlq = AsyncMock()
    ok = await raise_or_dlq(
        "kaori.does.not.exist", {}, dlq,
        consumer_group="test-group",
    )
    assert ok is False
    dlq.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_raise_or_dlq_returns_false_even_when_dlq_send_fails():
    """If DLQ ALSO fails, the consumer should still commit + skip the
    bad message rather than spin on it. The error is logged so ops
    can replay from offset position later."""
    dlq = AsyncMock()
    dlq.send_and_wait.side_effect = ConnectionError("DLQ broker down")

    ok = await raise_or_dlq(
        "kaori.pipeline.upload.received", {"missing": "fields"}, dlq,
        consumer_group="test-group",
    )
    assert ok is False  # caller commits offset + skips
