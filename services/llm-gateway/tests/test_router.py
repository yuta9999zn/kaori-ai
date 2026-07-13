"""
Tests for POST /v1/infer (services/llm-gateway/router.py).

End-to-end shape via FastAPI TestClient. The router is mounted in a
test app (no lifespan, no DB pool) so we can patch every collaborator:

  * ``routing.resolve_model``   — returns the (model_id, method) tuple
  * ``providers.invoke[_chat]`` — returns a fake completion + tool_calls
  * ``audit.log_decision``      — recorded as AsyncMock for assertions
  * ``pii.redact``              — wrapped to count calls per direction

Three K-* invariants are pinned end-to-end:

  K-4 (consent gate)  — covered indirectly: a request with
                         method='internal' returned by routing must
                         NOT call PII redact (no external boundary
                         crossed); a method='external' request MUST.
  K-5 (PII redact)    — single-prompt and chat paths both verified.
  K-6 (audit log)     — called once per request, even on PII path;
                         best-effort: a raise inside audit returns 500
                         (current behaviour — see comment on the test).

RFC 7807 (K-14) is checked via Content-Type on the validation 422 path.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import router as v1_router


# ─── Test-app fixture ────────────────────────────────────────────────

@pytest.fixture
def app():
    """Minimal FastAPI app — router + error handlers, no lifespan, no
    DB pool init. Every collaborator is patched per-test."""
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ─── Helpers ─────────────────────────────────────────────────────────

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


def _patch_router_internals(*, model="qwen2.5:14b", method="internal",
                            completion="OK", tool_calls=None,
                            finish_reason="stop",
                            routing_side_effect=None,
                            invoke_side_effect=None):
    """Patch the four collaborators router.py reaches for. Returns the
    mocks so individual tests can assert on call args.

    Pass ``routing_side_effect`` / ``invoke_side_effect`` to make those
    collaborators raise — used by the failure-path tests. Building the
    patches inside one factory means every test ends up with EXACTLY
    one patcher per target, so ``stop()`` order is unambiguous and
    nothing leaks into the next test (the bug that bit the first cut
    of these tests, when a second patcher was layered on top).

    ``providers.invoke`` returns (completion, model_used);
    ``providers.invoke_chat`` returns (completion, model_used,
    tool_calls, finish_reason). We patch BOTH because the router
    picks one based on whether ``messages`` is set.
    """
    pool = MagicMock()  # router only passes it to audit; never calls anything

    routing_mock = (
        AsyncMock(side_effect=routing_side_effect) if routing_side_effect
        else AsyncMock(return_value=(model, method))
    )
    invoke_mock = (
        AsyncMock(side_effect=invoke_side_effect) if invoke_side_effect
        else AsyncMock(return_value=(completion, model))
    )
    invoke_chat_mock = AsyncMock(return_value=(completion, model, tool_calls, finish_reason))
    audit_mock = AsyncMock(return_value=None)
    governance_mock = AsyncMock(return_value=None)
    quota_mock = AsyncMock(return_value=None)
    budget_mock = AsyncMock(return_value=False)  # headroom — no downgrade
    cost_mock = AsyncMock(return_value=0.0)

    return {
        "pool": pool,
        "routing": routing_mock,
        "invoke": invoke_mock,
        "invoke_chat": invoke_chat_mock,
        "audit": audit_mock,
        "governance": governance_mock,
        "quota": quota_mock,
        "patches": [
            patch("llm_gateway.router.get_pool", return_value=pool),
            patch("llm_gateway.router.routing.resolve_model", routing_mock),
            patch("llm_gateway.router.providers.invoke", invoke_mock),
            patch("llm_gateway.router.providers.invoke_chat", invoke_chat_mock),
            patch("llm_gateway.router.audit.log_decision", audit_mock),
            patch("llm_gateway.router.ai_governance.record_ai_call", governance_mock),
            patch("llm_gateway.router.tenant_quotas.check_and_consume", quota_mock),
            patch("llm_gateway.router.external_budget.is_exhausted", budget_mock),
            patch("llm_gateway.router.external_budget.estimate_cost_cents", cost_mock),
        ],
    }


def _enter(mocks):
    for p in mocks["patches"]:
        p.start()


def _exit(mocks):
    # Stop in reverse to keep nested-patch teardown LIFO-clean. With one
    # patcher per target this is mostly cosmetic, but it keeps the
    # invariant explicit if anyone adds a second patcher to the list.
    for p in reversed(mocks["patches"]):
        p.stop()


# ─── Happy path — single prompt ──────────────────────────────────────

def test_single_prompt_internal_happy_path(client):
    mocks = _patch_router_internals(completion="mapped column → revenue")
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload())
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    body = resp.json()
    assert body["completion"] == "mapped column → revenue"
    assert body["model_used"] == "qwen2.5:14b"
    assert body["method"] == "internal"
    assert body["cache_hit"] is False
    assert body["tool_calls"] is None
    assert body["finish_reason"] == "stop"
    assert body["tokens"]["prompt_chars"] == len("Map columns")
    assert body["tokens"]["completion_chars"] == len("mapped column → revenue")

    mocks["invoke"].assert_awaited_once()
    mocks["invoke_chat"].assert_not_awaited()
    mocks["audit"].assert_awaited_once()


def test_single_prompt_chat_path_when_messages_set(client):
    mocks = _patch_router_internals(completion="hi back",
                                    tool_calls=None, finish_reason="stop")
    payload = _payload(prompt="", messages=[
        {"role": "user", "content": "hi"},
    ])

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=payload)
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    mocks["invoke_chat"].assert_awaited_once()
    mocks["invoke"].assert_not_awaited()


# ─── K-5 PII redaction ───────────────────────────────────────────────

def test_pii_redact_called_when_method_is_external(client):
    """K-5: a prompt that crosses the external boundary must be PII-
    masked before dispatch. We spy on the actual redact function via
    a MagicMock side-effect proxy — verifies it's invoked AND that the
    masked text reaches providers.invoke."""
    mocks = _patch_router_internals(model="claude-sonnet-4-6", method="external",
                                    completion="masked answer")

    redact_spy = MagicMock(side_effect=lambda s: s.replace("user@example.com", "[email]"))

    _enter(mocks)
    redact_patch = patch("llm_gateway.router.pii.redact", redact_spy)
    redact_patch.start()
    try:
        resp = client.post("/v1/infer", json=_payload(
            prompt="Liên hệ user@example.com xác nhận hộ",
            consent_external=True,
        ))
    finally:
        redact_patch.stop()
        _exit(mocks)

    assert resp.status_code == 200
    redact_spy.assert_called_once()  # exactly one redact for the single prompt
    forwarded_prompt = mocks["invoke"].await_args.kwargs["prompt"]
    assert "user@example.com" not in forwarded_prompt
    assert "[email]" in forwarded_prompt


def test_pii_redact_NOT_called_when_method_is_internal(client):
    """Internal (Ollama on-prem) calls keep the original prompt — data
    never leaves the server, so masking is unnecessary cost. This is the
    other side of the K-5 contract."""
    mocks = _patch_router_internals(method="internal")

    redact_spy = MagicMock(side_effect=lambda s: s)
    _enter(mocks)
    redact_patch = patch("llm_gateway.router.pii.redact", redact_spy)
    redact_patch.start()
    try:
        resp = client.post("/v1/infer", json=_payload(
            prompt="Khách hàng a@b.io"
        ))
    finally:
        redact_patch.stop()
        _exit(mocks)

    assert resp.status_code == 200
    redact_spy.assert_not_called()
    forwarded = mocks["invoke"].await_args.kwargs["prompt"]
    assert "a@b.io" in forwarded  # untouched on internal path


def test_pii_redact_applied_per_user_message_in_chat_path(client):
    """Chat path redacts each user/system message separately so tool
    messages keep IDs intact (those came from us, not the public
    internet)."""
    mocks = _patch_router_internals(model="claude-sonnet-4-6", method="external",
                                    completion="ok", finish_reason="stop")
    redact_spy = MagicMock(side_effect=lambda s: s.replace("0987654321", "[phone]"))

    payload = _payload(prompt="", consent_external=True, messages=[
        {"role": "system", "content": "Bạn là trợ lý."},
        {"role": "user",   "content": "Số 0987654321 của khách"},
        {"role": "tool",   "content": "{\"id\": 0987654321}", "tool_call_id": "t1", "name": "lookup"},
    ])

    _enter(mocks)
    redact_patch = patch("llm_gateway.router.pii.redact", redact_spy)
    redact_patch.start()
    try:
        resp = client.post("/v1/infer", json=payload)
    finally:
        redact_patch.stop()
        _exit(mocks)

    assert resp.status_code == 200
    # Two redacts: system + user. Tool message bypassed (its ID is ours).
    assert redact_spy.call_count == 2

    forwarded = mocks["invoke_chat"].await_args.kwargs["messages"]
    user_msg = next(m for m in forwarded if m["role"] == "user")
    tool_msg = next(m for m in forwarded if m["role"] == "tool")
    assert "[phone]" in user_msg["content"]
    assert "0987654321" in tool_msg["content"]  # tool content untouched


# ─── Validation ──────────────────────────────────────────────────────

def test_empty_prompt_and_no_messages_returns_422(client):
    """Either prompt or messages must be non-empty."""
    mocks = _patch_router_internals()
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(prompt=""))
    finally:
        _exit(mocks)

    assert resp.status_code == 422
    # K-14: RFC 7807 problem+json envelope.
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert "prompt or messages required" in (body.get("detail") or body.get("title", ""))
    assert body["status"] == 422
    mocks["invoke"].assert_not_awaited()


def test_invalid_enterprise_id_returns_422_problem_json(client):
    """Pydantic UUID validation surfaces as a K-14 RFC 7807 422."""
    resp = client.post("/v1/infer", json={
        "task": "schema_mapping",
        "prompt": "x",
        "enterprise_id": "not-a-uuid",
    })
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")


# ─── Failure paths ───────────────────────────────────────────────────

def test_routing_failure_returns_500(client):
    """A DB blip during routing is a 500 — there's no caller-friendly
    way to recover. RFC 7807 envelope still returned."""
    mocks = _patch_router_internals(
        routing_side_effect=RuntimeError("pool exhausted"),
    )

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload())
    finally:
        _exit(mocks)

    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_provider_failure_returns_502_bad_gateway(client):
    """Upstream LLM call failed → 502 (Bad Gateway is the canonical
    code for 'upstream service borked', not 500)."""
    mocks = _patch_router_internals(
        invoke_side_effect=Exception("ollama timeout"),
    )

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload())
    finally:
        _exit(mocks)

    assert resp.status_code == 502
    body = resp.json()
    assert body["status"] == 502
    assert "upstream" in (body.get("detail") or body.get("title", "")).lower()


# ─── ADR-0015 Rule 5 — external failure degrades to local Qwen ───────

def test_external_failure_falls_back_to_internal_ollama(client):
    """A vendor error (Anthropic 5xx, rate-limit, refusal) must degrade
    to local Qwen rather than 5xx. The demo's analysis path routes to
    Claude; a transient vendor hiccup must not hard-fail the request.
    First invoke (external) raises; the router retries once via internal
    Ollama and returns 200 with the fallback model surfaced."""
    mocks = _patch_router_internals(
        model="claude-sonnet-4-6", method="external",
        invoke_side_effect=[Exception("anthropic 529 overloaded"),
                            ("Qwen local answer", "qwen2.5:7b")],
    )
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(consent_external=True))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    body = resp.json()
    assert body["completion"] == "Qwen local answer"
    assert body["model_used"] == "qwen2.5:7b"
    assert body["method"] == "internal"        # surfaced as internal post-fallback
    assert mocks["invoke"].await_count == 2     # external attempt + internal retry


def test_external_failure_and_fallback_failure_still_502(client):
    """If the local fallback ALSO fails, there's nothing left to serve —
    surface the 502 (fail loud, tenet #3)."""
    mocks = _patch_router_internals(
        model="claude-sonnet-4-6", method="external",
        invoke_side_effect=[Exception("anthropic down"),
                            Exception("ollama also down")],
    )
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(consent_external=True))
    finally:
        _exit(mocks)

    assert resp.status_code == 502
    assert mocks["invoke"].await_count == 2


def test_internal_failure_does_not_retry(client):
    """An already-internal call that fails must NOT loop back into
    another internal attempt — one failure, one 502."""
    mocks = _patch_router_internals(
        method="internal",
        invoke_side_effect=Exception("ollama timeout"),
    )
    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload())
    finally:
        _exit(mocks)

    assert resp.status_code == 502
    assert mocks["invoke"].await_count == 1


# ─── K-6 audit ───────────────────────────────────────────────────────

def test_audit_log_decision_called_with_request_context(client):
    """K-6: every LLM call writes one decision_audit_log row."""
    mocks = _patch_router_internals(method="internal", completion="OK")
    eid = str(uuid4())
    rid = str(uuid4())

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            enterprise_id=eid, run_id=rid,
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    mocks["audit"].assert_awaited_once()
    kwargs = mocks["audit"].await_args.kwargs
    assert kwargs["enterprise_id"] == eid
    assert kwargs["run_id"] == rid
    assert kwargs["decision_type"] == "llm_call"
    assert kwargs["subject"] == "schema_mapping"
    assert kwargs["chosen_value"] == "OK"
    assert kwargs["method"] == "internal"
    assert kwargs["llm_provider"] == "qwen2.5:14b"
    assert "latency_ms=" in kwargs["reasoning"]


# ─── Phase 2.7 P3 — AI governance audit (parallel writer) ─────────────


def test_governance_audit_called_alongside_decision_audit(client):
    """Every successful /v1/infer dispatch writes BOTH the K-6
    decision_audit_log row AND the Phase 2.7 ai_decision_audit row.
    Together they form the governance trail (decision + the LLM call
    that fed it)."""
    mocks = _patch_router_internals(completion="OK")
    eid = str(uuid4())
    rid = str(uuid4())

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            enterprise_id=eid, run_id=rid, prompt="hi",
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    mocks["governance"].assert_awaited_once()
    gov_kwargs = mocks["governance"].await_args.kwargs
    # enterprise_id is forwarded as a UUID object (not string) because
    # router passes req.enterprise_id directly from the parsed pydantic
    # model. Match by string compare to be robust.
    assert str(gov_kwargs["enterprise_id"]) == eid
    assert str(gov_kwargs["run_id"]) == rid
    assert gov_kwargs["task_kind"] == "schema_mapping"
    assert gov_kwargs["model_version"] == "qwen2.5:14b"
    assert gov_kwargs["model_provider"] == "ollama"
    assert gov_kwargs["consent_external"] is False     # method='internal'
    assert gov_kwargs["pii_redacted"] is False         # method='internal'
    assert gov_kwargs["output_validated"] is False     # no output_schema set
    assert gov_kwargs["prompt"] == "hi"
    assert gov_kwargs["output"] == "OK"
    assert gov_kwargs["latency_ms"] >= 0


def test_governance_audit_marks_external_consent_when_method_external(client):
    """K-4 + governance: when routing returns method='external', the
    governance row records consent_external=True + pii_redacted=True
    so compliance export can filter cross-border calls vs local-only."""
    mocks = _patch_router_internals(
        model="claude-sonnet-4-6", method="external",
        completion="masked answer",
    )

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            prompt="Map this column",
            consent_external=True,
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    mocks["governance"].assert_awaited_once()
    gov_kwargs = mocks["governance"].await_args.kwargs
    assert gov_kwargs["consent_external"] is True
    assert gov_kwargs["pii_redacted"] is True
    assert gov_kwargs["model_provider"] == "anthropic"  # _provider_label


def test_governance_audit_chat_path_concatenates_user_system_content(client):
    """Chat path: prompt field on governance row is system + user content
    concatenated (so the prompt_hash is meaningful for replay)."""
    mocks = _patch_router_internals(completion="reply")
    payload = _payload(prompt="", messages=[
        {"role": "system", "content": "You answer briefly."},
        {"role": "user", "content": "how are you"},
    ])

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=payload)
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    mocks["governance"].assert_awaited_once()
    gov_prompt = mocks["governance"].await_args.kwargs["prompt"]
    assert "You answer briefly." in gov_prompt
    assert "how are you" in gov_prompt


# ─── Phase 2.7 P2 — Tenant quota pre-flight gate ──────────────────────


def test_quota_check_called_with_external_type_when_method_external(client):
    """K-4 + quota: when routing returns method='external', the
    quota gate charges 'llm_tokens_external'; method='internal' charges
    'llm_tokens_local'. Lets ops bill external/local separately."""
    mocks = _patch_router_internals(
        model="claude-sonnet-4-6", method="external", completion="ok",
    )

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(
            prompt="hello", consent_external=True, max_tokens=100,
        ))
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    mocks["quota"].assert_awaited_once()
    q_kwargs = mocks["quota"].await_args.kwargs
    assert q_kwargs["quota_type"] == "llm_tokens_external"
    # amount = len("hello") + 100 * 4 = 405
    assert q_kwargs["amount"] == 5 + 100 * 4


def test_quota_check_internal_type_when_method_internal(client):
    mocks = _patch_router_internals(completion="ok")

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload())
    finally:
        _exit(mocks)

    assert resp.status_code == 200
    q_kwargs = mocks["quota"].await_args.kwargs
    assert q_kwargs["quota_type"] == "llm_tokens_local"


def test_quota_exceeded_returns_429(client):
    """When the quota gate raises QuotaExceeded, the router must
    surface a 429 Problem Details (K-14) WITHOUT calling
    providers.invoke — the LLM call never happens, no governance row,
    no token spend."""
    from llm_gateway import tenant_quotas

    mocks = _patch_router_internals(completion="should-never-run")
    mocks["quota"].side_effect = tenant_quotas.QuotaExceeded(
        quota_type="llm_tokens_external",
        current=1_000_500,
        max_value=1_000_000,
        period="per_day",
    )

    _enter(mocks)
    try:
        resp = client.post("/v1/infer", json=_payload(consent_external=True))
    finally:
        _exit(mocks)

    assert resp.status_code == 429
    assert "llm_tokens_external" in resp.text
    assert "per_day" in resp.text
    # K-13 / K-6: when quota gate refuses, the LLM dispatch is skipped
    # entirely — providers + audit + governance ALL remain uncalled.
    mocks["invoke"].assert_not_awaited()
    mocks["invoke_chat"].assert_not_awaited()
    mocks["governance"].assert_not_awaited()
    mocks["audit"].assert_not_awaited()
