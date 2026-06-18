"""
Tests for the router-side wiring of Issue #3 output_schema validation.

These complement ``test_router.py`` (which pins the legacy raw-string
flow) by driving requests that DO carry an ``output_schema``. We stub
``providers.invoke`` with a side_effect list so the first call returns
a bad completion and the second returns a good one — the repair round
exercises the full pipeline end to end without needing a real LLM.

The tests cover four shapes the router can return when ``output_schema``
is set:

  1. First attempt valid               → 200, output_validation present,
                                          was_repaired=False, providers
                                          called once.
  2. First attempt invalid + repair OK → 200, output_validation present,
                                          was_repaired=True, providers
                                          called twice with augmented
                                          prompt second time.
  3. Both attempts invalid             → 502 with structured detail,
                                          providers called twice.
  4. No output_schema set              → legacy path unchanged
                                          (output_validation absent).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import router as v1_router


_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["canonical", "confidence"],
    "properties": {
        "canonical":  {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


@pytest.fixture
def app():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _payload(**overrides):
    base = {
        "task":              "schema_mapping",
        "prompt":            "Map column 'doanh thu' to canonical English name.",
        "enterprise_id":     str(uuid4()),
        "consent_external":  False,
        "max_tokens":        500,
    }
    base.update(overrides)
    return base


def _patch_for_invoke(invoke_mock):
    """Mount the minimal patch set the router needs to handle a
    single-prompt request — routing returns a stable internal model,
    audit + pool are no-ops, providers.invoke is the test-driven mock.
    """
    pool = MagicMock()
    routing_mock = AsyncMock(return_value=("qwen2.5:14b", "internal"))
    audit_mock = AsyncMock(return_value=None)
    return [
        patch("llm_gateway.router.get_pool", return_value=pool),
        patch("llm_gateway.router.routing.resolve_model", routing_mock),
        patch("llm_gateway.router.providers.invoke", invoke_mock),
        # invoke_chat patched as no-op so a stray call from a future
        # regression would surface (test for the chat path is below).
        patch("llm_gateway.router.providers.invoke_chat",
              AsyncMock(return_value=("", "qwen2.5:14b", None, "stop"))),
        patch("llm_gateway.router.audit.log_decision", audit_mock),
        # Phase 2.7 P3 — gov writer is best-effort; pin to no-op for tests.
        patch("llm_gateway.router.ai_governance.record_ai_call",
              new=AsyncMock(return_value=None)),
        # Phase 2.7 P2 — quota gate fails open (returns None) on no-config.
        patch("llm_gateway.router.tenant_quotas.check_and_consume",
              new=AsyncMock(return_value=None)),
    ], audit_mock


# ─── Shape 1: first attempt valid ────────────────────────────────

def test_first_attempt_valid_returns_parsed_json_no_repair(client):
    valid = '{"canonical":"revenue","confidence":0.91}'
    invoke = AsyncMock(return_value=(valid, "qwen2.5:14b"))
    patches, audit = _patch_for_invoke(invoke)

    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload(output_schema=_SCHEMA))
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["completion"] == valid
    assert body["output_validation"] is not None
    assert body["output_validation"]["was_repaired"] is False
    assert body["output_validation"]["attempts"] == 1
    assert body["output_validation"]["parsed_json"] == {
        "canonical": "revenue", "confidence": 0.91,
    }
    # Provider called exactly once on the happy path.
    assert invoke.await_count == 1
    # Audit row carries schema_validated marker so ops can grep.
    audit.assert_awaited_once()
    reasoning = audit.await_args.kwargs["reasoning"]
    assert "schema_validated=true" in reasoning
    assert "schema_repaired=false" in reasoning


# ─── Shape 2: first invalid → repair → valid ─────────────────────

def test_first_invalid_then_repair_succeeds_returns_was_repaired_true(client):
    """The router must call providers.invoke a SECOND time with an
    augmented prompt when the first response fails validation."""
    invoke = AsyncMock(side_effect=[
        # First attempt: missing required confidence.
        ('{"canonical":"revenue"}', "qwen2.5:14b"),
        # Repair attempt: valid.
        ('{"canonical":"revenue","confidence":0.85}', "qwen2.5:14b"),
    ])
    patches, audit = _patch_for_invoke(invoke)

    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload(output_schema=_SCHEMA))
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["output_validation"]["was_repaired"] is True
    assert body["output_validation"]["attempts"] == 2
    assert body["output_validation"]["parsed_json"] == {
        "canonical": "revenue", "confidence": 0.85,
    }
    # On the repair round, the audit row's chosen_value should be the
    # FINAL good completion (not the bad first attempt). The router
    # canonicalises by re-serialising the parsed dict, so the JSON
    # form is normalised but the content matches.
    assert audit.await_count == 1
    chosen_value = audit.await_args.kwargs["chosen_value"]
    assert "revenue" in chosen_value and "0.85" in chosen_value

    # Repair invoke must be called twice — first with original prompt,
    # second with the AUGMENTED prompt that includes both the schema
    # and the validation error so the model knows what to fix.
    assert invoke.await_count == 2
    second_call_prompt = invoke.await_args_list[1].kwargs["prompt"]
    assert "Map column 'doanh thu'" in second_call_prompt
    assert "Required JSON schema" in second_call_prompt
    assert "confidence" in second_call_prompt

    # Audit reasoning marks the repair so ops can grep ratio of
    # repaired vs first-try-valid responses per task.
    reasoning = audit.await_args.kwargs["reasoning"]
    assert "schema_repaired=true" in reasoning


# ─── Shape 3: both attempts invalid → 502 ────────────────────────

def test_both_attempts_invalid_returns_502_problem_json(client):
    """Last-resort failure: the gateway gives up after one repair and
    surfaces 502 with a problem+json envelope. The caller (e.g.,
    column_mapper) decides whether to fall back to a heuristic or
    propagate the error."""
    invoke = AsyncMock(side_effect=[
        ('I cannot answer this.',                          "qwen2.5:14b"),
        ('Still cannot. Sorry.',                           "qwen2.5:14b"),
    ])
    patches, _ = _patch_for_invoke(invoke)

    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload(output_schema=_SCHEMA))
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 502
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 502
    detail = body.get("detail") or body.get("title", "")
    assert "validation failed" in detail.lower()
    assert "2 attempts" in detail
    # Both attempts consumed.
    assert invoke.await_count == 2


def test_first_invalid_then_repair_returns_wrong_shape_returns_502(client):
    """Edge case from the validator suite — repair returned valid JSON
    but it doesn't match the schema either. Same 502 contract."""
    invoke = AsyncMock(side_effect=[
        ('{"canonical":"revenue"}',                            "qwen2.5:14b"),
        ('{"foo":"bar"}',                                      "qwen2.5:14b"),
    ])
    patches, _ = _patch_for_invoke(invoke)

    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload(output_schema=_SCHEMA))
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 502


# ─── Shape 4: legacy path (no output_schema) untouched ───────────

def test_no_output_schema_returns_raw_completion_with_no_validation_meta(client):
    """The change is opt-in. Existing callers (analytics summary,
    cleaning rule suggestions, etc.) that don't supply output_schema
    must see the same response shape they always have — completion as
    a string, output_validation absent."""
    invoke = AsyncMock(return_value=("Free-text reply with no JSON.", "qwen2.5:14b"))
    patches, _ = _patch_for_invoke(invoke)

    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload())  # no output_schema
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["completion"] == "Free-text reply with no JSON."
    assert body["output_validation"] is None
    # Single call — no repair logic should fire when output_schema is
    # absent, even if the completion happens to be unparseable JSON.
    assert invoke.await_count == 1
