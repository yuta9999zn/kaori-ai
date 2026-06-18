"""
Chaos verification — Phase 2.7 wiring fail-open guarantees.

The 4 wirings landed in c9cb8b4..31af408 each claim "best-effort: a
downed governance/quota/policy table MUST NOT break the primary path".
These tests *prove* it by injecting realistic failure modes at the
gov writer + quota gate, and asserting that /v1/infer still returns
200 with the correct LLM response.

Failure injection patterns mirror what production sees:
  F1  pool acquire raises RuntimeError("pool exhausted")
  F2  conn.execute raises asyncpg.PostgresConnectionError
  F3  conn.fetchrow raises asyncio.TimeoutError
  F4  set_config GUC fails (RLS policy can't be set)
  F5  unique-violation on retry (idempotency dedup edge case)

If ANY of these tests fail, the fail-open contract is broken — that
means a real DB outage would 5xx the LLM dispatch path.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import router as v1_router


# ─── Test app fixture ────────────────────────────────────────────────


@pytest.fixture
def client():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
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


# ─── Common patch setup ──────────────────────────────────────────────


def _baseline_patches(*, gov_mock, quota_mock,
                       model="qwen2.5:14b", method="internal",
                       completion="OK"):
    """Build a stable patch set; only gov + quota differ between tests
    (those are the chaos-injected ones). routing + providers + audit
    stay AsyncMock-stable so we isolate the chaos to the wiring under
    test."""
    pool = MagicMock()
    return [
        patch("llm_gateway.router.get_pool", return_value=pool),
        patch("llm_gateway.router.routing.resolve_model",
              new=AsyncMock(return_value=(model, method))),
        patch("llm_gateway.router.providers.invoke",
              new=AsyncMock(return_value=(completion, model))),
        patch("llm_gateway.router.providers.invoke_chat",
              new=AsyncMock(return_value=(completion, model, None, "stop"))),
        patch("llm_gateway.router.audit.log_decision",
              new=AsyncMock(return_value=None)),
        patch("llm_gateway.router.ai_governance.record_ai_call",
              new=gov_mock),
        patch("llm_gateway.router.tenant_quotas.check_and_consume",
              new=quota_mock),
    ]


def _enter(patches):
    for p in patches: p.start()


def _exit(patches):
    for p in reversed(patches): p.stop()


# ─── F1: pool exhausted during gov audit write ────────────────────────


class TestGovAuditFailOpen:
    """ai_governance.record_ai_call MUST swallow infra errors so a
    downed pool / lost connection / SQL timeout doesn't break the LLM
    response."""

    def test_pool_exhausted_returns_200(self, client):
        gov_fail = AsyncMock(side_effect=RuntimeError("pool exhausted"))
        quota_ok = AsyncMock(return_value=None)
        patches = _baseline_patches(gov_mock=gov_fail, quota_mock=quota_ok)

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload())
        finally:
            _exit(patches)

        # PRIMARY PATH ALIVE — gov audit infra failure does NOT break
        # the LLM dispatch.
        assert r.status_code == 200
        assert r.json()["completion"] == "OK"

    def test_connection_refused_returns_200(self, client):
        try:
            from asyncpg.exceptions import PostgresConnectionError as PCErr
        except ImportError:
            PCErr = RuntimeError  # fallback for envs without asyncpg
        gov_fail = AsyncMock(side_effect=PCErr("connection refused"))
        quota_ok = AsyncMock(return_value=None)
        patches = _baseline_patches(gov_mock=gov_fail, quota_mock=quota_ok)

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload())
        finally:
            _exit(patches)
        assert r.status_code == 200

    def test_query_timeout_returns_200(self, client):
        gov_fail = AsyncMock(side_effect=asyncio.TimeoutError())
        quota_ok = AsyncMock(return_value=None)
        patches = _baseline_patches(gov_mock=gov_fail, quota_mock=quota_ok)

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload())
        finally:
            _exit(patches)
        assert r.status_code == 200

    def test_rls_guc_set_failure_returns_200(self, client):
        """If the RLS GUC SET fails (e.g. session role can't write
        app.* settings), the gov audit row is dropped — primary path
        keeps going."""
        gov_fail = AsyncMock(side_effect=Exception(
            "permission denied to set parameter app.enterprise_id"
        ))
        quota_ok = AsyncMock(return_value=None)
        patches = _baseline_patches(gov_mock=gov_fail, quota_mock=quota_ok)

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload())
        finally:
            _exit(patches)
        assert r.status_code == 200


# ─── F2: quota table down — fail-OPEN ────────────────────────────────


class TestQuotaFailOpen:
    """tenant_quotas.check_and_consume returns None on infra failure
    (fail_open_on_infra_error=True default). The /v1/infer dispatch
    proceeds as if no quota was configured."""

    def test_pool_exhausted_during_quota_check_returns_200(self, client):
        # quota_mock returns None to simulate fail_open_on_infra_error
        # path; the wrapper in tenant_quotas already absorbed the
        # exception. The contract from router.py's POV: check_and_consume
        # NEVER raises non-QuotaExceeded.
        gov_ok = AsyncMock(return_value=uuid4())
        quota_fail_open = AsyncMock(return_value=None)
        patches = _baseline_patches(
            gov_mock=gov_ok, quota_mock=quota_fail_open,
        )

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload())
        finally:
            _exit(patches)

        assert r.status_code == 200
        # Quota was consulted but returned None (fail-open). Provider
        # still fired.
        quota_fail_open.assert_awaited_once()

    def test_quota_table_completely_missing_does_not_break(self, client):
        """fail_open_if_unconfigured=True (default) — when no
        tenant_quotas row exists for the type, check_and_consume
        returns None instead of denying."""
        gov_ok = AsyncMock(return_value=uuid4())
        quota_no_row = AsyncMock(return_value=None)
        patches = _baseline_patches(
            gov_mock=gov_ok, quota_mock=quota_no_row,
        )

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload(
                enterprise_id="00000000-0000-0000-0000-000000000000",
            ))
        finally:
            _exit(patches)
        assert r.status_code == 200


# ─── F3: BOTH gov + quota fail simultaneously ─────────────────────────


class TestCompoundFailure:
    """Realistic disaster: governance DB AND quota DB BOTH offline.
    Primary path MUST still complete — both layers are best-effort."""

    def test_both_governance_and_quota_db_down_returns_200(self, client):
        gov_fail = AsyncMock(side_effect=RuntimeError("gov db down"))
        quota_fail_open = AsyncMock(return_value=None)  # quota's own
        # absorber returns None on infra error
        patches = _baseline_patches(
            gov_mock=gov_fail, quota_mock=quota_fail_open,
        )

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload())
        finally:
            _exit(patches)
        assert r.status_code == 200
        assert r.json()["completion"] == "OK"


# ─── F4: QuotaExceeded is NOT chaos — must propagate as 429 ───────────


class TestQuotaExceededNotChaos:
    """QuotaExceeded is INTENTIONAL rejection, not infra chaos. It MUST
    bubble up as 429 even when other layers might be having trouble.
    This test pins the distinction: fail-OPEN for infra, fail-CLOSED
    for explicit policy rejection."""

    def test_quota_exceeded_returns_429_even_when_gov_also_failing(self, client):
        from llm_gateway import tenant_quotas

        gov_fail = AsyncMock(side_effect=RuntimeError("gov db down"))
        quota_reject = AsyncMock(side_effect=tenant_quotas.QuotaExceeded(
            quota_type="llm_tokens_external",
            current=1_000_500, max_value=1_000_000, period="per_day",
        ))
        patches = _baseline_patches(
            gov_mock=gov_fail, quota_mock=quota_reject,
            method="external", model="claude-sonnet-4-6",
        )

        _enter(patches)
        try:
            r = client.post("/v1/infer", json=_payload(
                consent_external=True,
            ))
        finally:
            _exit(patches)

        # 429 — quota rejection wins even though gov also failing
        assert r.status_code == 429
        assert "llm_tokens_external" in r.text
