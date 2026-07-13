"""
Tests for P1-S5 net-new behaviour in services/llm-gateway/router.py:

  * P1-LLM-004 — workflow-pinned model + version override task routing
  * OBS-008    — kaori_ai_calls_total + kaori_ai_tokens_total Counters

Reuses the patch helper pattern from test_router.py. We don't import
the helpers because they're test-private; copying the small bits keeps
each test file self-contained (same convention as the existing splits).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import (
    AI_CALLS_TOTAL,
    AI_TOKENS_TOTAL,
    _provider_label,
    router as v1_router,
)


# ─── Fixtures ────────────────────────────────────────────────────────


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
        "task": "schema_mapping",
        "prompt": "Map columns",
        "enterprise_id": str(uuid4()),
        "consent_external": False,
        "max_tokens": 200,
    }
    base.update(overrides)
    return base


def _setup_mocks(*, model="qwen2.5:14b", method="internal", completion="OK"):
    pool = MagicMock()
    routing_mock = AsyncMock(return_value=(model, method))
    invoke_mock = AsyncMock(return_value=(completion, model))
    invoke_chat_mock = AsyncMock(return_value=(completion, model, None, "stop"))
    audit_mock = AsyncMock(return_value=None)

    patches = [
        patch("llm_gateway.router.get_pool", return_value=pool),
        patch("llm_gateway.router.routing.resolve_model", routing_mock),
        patch("llm_gateway.router.providers.invoke", invoke_mock),
        patch("llm_gateway.router.providers.invoke_chat", invoke_chat_mock),
        patch("llm_gateway.router.audit.log_decision", audit_mock),
        patch("llm_gateway.router.ai_governance.record_ai_call",
              new=AsyncMock(return_value=None)),
        patch("llm_gateway.router.tenant_quotas.check_and_consume",
              new=AsyncMock(return_value=None)),
        patch("llm_gateway.router.external_budget.is_exhausted",
              new=AsyncMock(return_value=False)),
        patch("llm_gateway.router.external_budget.estimate_cost_cents",
              new=AsyncMock(return_value=0.0)),
    ]
    return {
        "routing": routing_mock,
        "invoke": invoke_mock,
        "audit": audit_mock,
        "patches": patches,
    }


def _enter(mocks):
    for p in mocks["patches"]:
        p.start()


def _exit(mocks):
    for p in reversed(mocks["patches"]):
        p.stop()


def _counter_value(counter, **labels) -> float:
    """Read a single label combination from a Counter — None means
    'no samples for that label combination yet'. Calling .labels(...)
    auto-instantiates a 0-value child, which we don't want in queries
    (it would inflate cardinality)."""
    for sample in counter.collect()[0].samples:
        if sample.name.endswith("_total") and sample.labels == labels:
            return sample.value
    return 0.0


# ─── P1-LLM-004 — workflow-pinned model + version (K-20) ─────────────


def test_pinned_model_overrides_task_routing(client):
    """When pinned_model is set, router uses it directly and skips
    routing.resolve_model. This is K-20 (LLM version pinning per
    workflow) — workflow YAML stays on a tested model even after the
    vendor releases a new version."""
    mocks = _setup_mocks(model="qwen2.5:14b", method="internal")
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            pinned_model="claude-sonnet-4-6",
            pinned_version="2026-01-01",
            consent_external=True,
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    # routing.resolve_model MUST NOT be called — pinned shortcut wins.
    mocks["routing"].assert_not_awaited()


def test_pinned_model_external_inferred_from_prefix(client):
    """claude-* prefix → method='external' so the audit/metric records
    the right provider class."""
    mocks = _setup_mocks(model="claude-sonnet-4-6", method="external",
                          completion="anthropic answer")
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            pinned_model="claude-sonnet-4-6",
            pinned_version="2026-01-01",
            consent_external=True,
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    body = resp.json()
    # invoke (single prompt path) was the one called, with the pinned model
    mocks["invoke"].assert_awaited_once()
    call_kwargs = mocks["invoke"].await_args.kwargs
    assert call_kwargs["model_id"] == "claude-sonnet-4-6"
    assert call_kwargs["method"] == "external"


def test_pinned_model_unknown_prefix_falls_back_to_internal(client):
    """A pinned model with no recognised prefix (e.g. a future
    self-hosted Llama fine-tune) defaults to method='internal' — the
    safe choice (no PII leak to vendor by accident)."""
    mocks = _setup_mocks(model="my-finetuned-vn-model", method="internal")
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            pinned_model="my-finetuned-vn-model",
            pinned_version="v1",
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    call_kwargs = mocks["invoke"].await_args.kwargs
    assert call_kwargs["method"] == "internal"


def test_pinned_model_without_pinned_version_returns_422(client):
    """K-20 contract: both or neither. Missing pinned_version with
    pinned_model set is a malformed pin — fail loud at request time."""
    mocks = _setup_mocks()
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            pinned_model="claude-sonnet-4-6",
            # pinned_version omitted
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 422
    assert "pinned_model and pinned_version" in resp.text


def test_pinned_version_without_pinned_model_returns_422(client):
    """Mirror of the above — versions without a model are meaningless."""
    mocks = _setup_mocks()
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            pinned_version="2026-01-01",
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 422


def test_pinned_model_appears_in_audit_reasoning(client):
    """Audit row reasoning must carry the pinned model+version so a
    quality-regression investigator can grep for the exact model build
    that produced a flagged decision."""
    mocks = _setup_mocks(model="claude-sonnet-4-6", method="external")
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            pinned_model="claude-sonnet-4-6",
            pinned_version="2026-01-01",
            consent_external=True,
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    audit_call = mocks["audit"].await_args
    reasoning = audit_call.kwargs["reasoning"]
    assert "pinned=claude-sonnet-4-6@2026-01-01" in reasoning


# ─── OBS-008 — kaori_ai_calls_total + kaori_ai_tokens_total ─────────


def test_obs008_call_counter_increments_on_success(client):
    """Successful call increments kaori_ai_calls_total with status=success."""
    tenant = str(uuid4())
    before = _counter_value(
        AI_CALLS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, status="success",
    )

    mocks = _setup_mocks(model="qwen2.5:14b", method="internal")
    _enter(mocks)
    try:
        client.post("/v1/infer", json=_payload(enterprise_id=tenant))
    finally:
        _exit(mocks)

    after = _counter_value(
        AI_CALLS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, status="success",
    )
    assert after == before + 1


def test_obs008_token_counter_increments_input_and_output(client):
    """Token counter splits input + output so cost dashboards can show
    'we spent X on prompts vs Y on completions' — useful when prompt
    bloat (system prompts, few-shot examples) dominates the bill."""
    tenant = str(uuid4())
    completion = "this is the response"
    prompt = "ask me something"

    in_before = _counter_value(
        AI_TOKENS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, direction="input",
    )
    out_before = _counter_value(
        AI_TOKENS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, direction="output",
    )

    mocks = _setup_mocks(model="qwen2.5:14b", method="internal", completion=completion)
    _enter(mocks)
    try:
        client.post("/v1/infer", json=_payload(prompt=prompt, enterprise_id=tenant))
    finally:
        _exit(mocks)

    in_after = _counter_value(
        AI_TOKENS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, direction="input",
    )
    out_after = _counter_value(
        AI_TOKENS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, direction="output",
    )
    assert in_after - in_before == len(prompt)
    assert out_after - out_before == len(completion)


def test_obs008_provider_label_anthropic_for_claude_models():
    """_provider_label maps model_used to the provider tag dashboards
    aggregate by. Test the four cases the helper handles."""
    assert _provider_label("internal", "qwen2.5:14b") == "ollama"
    assert _provider_label("external", "claude-sonnet-4-6") == "anthropic"
    assert _provider_label("external", "gpt-4o") == "openai"
    assert _provider_label("external", "o1-preview") == "openai"
    assert _provider_label("external", "cohere-command-r") == "external"


def test_obs008_call_counter_on_provider_failure_marks_status_upstream_error(client):
    """When the provider raises, we still increment the counter — but
    with status=upstream_error so dashboards see error rate, not
    (silently) a missing call."""
    tenant = str(uuid4())
    before = _counter_value(
        AI_CALLS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, status="upstream_error",
    )

    invoke_fail = AsyncMock(side_effect=RuntimeError("ollama offline"))
    pool = MagicMock()
    routing_mock = AsyncMock(return_value=("qwen2.5:14b", "internal"))
    audit_mock = AsyncMock(return_value=None)
    patches = [
        patch("llm_gateway.router.get_pool", return_value=pool),
        patch("llm_gateway.router.routing.resolve_model", routing_mock),
        patch("llm_gateway.router.providers.invoke", invoke_fail),
        patch("llm_gateway.router.audit.log_decision", audit_mock),
        patch("llm_gateway.router.ai_governance.record_ai_call",
              new=AsyncMock(return_value=None)),
        patch("llm_gateway.router.tenant_quotas.check_and_consume",
              new=AsyncMock(return_value=None)),
        patch("llm_gateway.router.external_budget.is_exhausted",
              new=AsyncMock(return_value=False)),
        patch("llm_gateway.router.external_budget.estimate_cost_cents",
              new=AsyncMock(return_value=0.0)),
    ]
    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload(enterprise_id=tenant))
        assert resp.status_code == 502
    finally:
        for p in reversed(patches):
            p.stop()

    after = _counter_value(
        AI_CALLS_TOTAL,
        provider="ollama", model="qwen2.5:14b", tenant_id=tenant, status="upstream_error",
    )
    assert after == before + 1
