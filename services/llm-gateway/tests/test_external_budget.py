"""
Tests for services/llm-gateway/external_budget.py — the per-tenant USD
budget gate for external LLM calls ($-cap → silent Qwen downgrade).

Module-level: cap/spend math, fail-open semantics, pricing fallback.
Router-level: /v1/infer with an exhausted budget dispatches to internal
Ollama instead of the externally-routed model — and never 429s.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway import external_budget
from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import router as v1_router


# ─── Pool scaffold ────────────────────────────────────────────────────

def _mock_pool(*, fetchrow_results=None, fetchrow_side_effect=None):
    conn = AsyncMock()
    if fetchrow_side_effect is not None:
        conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    else:
        conn.fetchrow = AsyncMock(side_effect=list(fetchrow_results or []))
    conn.execute = AsyncMock(return_value=None)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


@pytest.fixture(autouse=True)
def _clear_pricing_cache():
    external_budget._pricing_cache.clear()
    yield
    external_budget._pricing_cache.clear()


# ─── is_exhausted ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_budget_row_means_no_cap():
    pool, _ = _mock_pool(fetchrow_results=[None])
    assert await external_budget.is_exhausted(pool, str(uuid4())) is False


@pytest.mark.asyncio
async def test_under_budget_not_exhausted():
    pool, _ = _mock_pool(
        fetchrow_results=[{"max_value": 300}, {"spent": 120.5}],
    )
    assert await external_budget.is_exhausted(pool, str(uuid4())) is False


@pytest.mark.asyncio
async def test_at_budget_is_exhausted():
    pool, _ = _mock_pool(
        fetchrow_results=[{"max_value": 300}, {"spent": 300.0}],
    )
    assert await external_budget.is_exhausted(pool, str(uuid4())) is True


@pytest.mark.asyncio
async def test_over_budget_is_exhausted():
    pool, _ = _mock_pool(
        fetchrow_results=[{"max_value": 300}, {"spent": 412.7}],
    )
    assert await external_budget.is_exhausted(pool, str(uuid4())) is True


@pytest.mark.asyncio
async def test_infra_error_fails_open():
    pool, _ = _mock_pool(fetchrow_side_effect=RuntimeError("db down"))
    assert await external_budget.is_exhausted(pool, str(uuid4())) is False


@pytest.mark.asyncio
async def test_empty_enterprise_id_fails_open():
    pool, _ = _mock_pool(fetchrow_results=[])
    assert await external_budget.is_exhausted(pool, "") is False


@pytest.mark.asyncio
async def test_guc_is_set_inside_transaction():
    ent = str(uuid4())
    pool, conn = _mock_pool(
        fetchrow_results=[{"max_value": 300}, {"spent": 0}],
    )
    await external_budget.is_exhausted(pool, ent)
    sql, arg = conn.execute.call_args_list[0].args
    assert "set_config('app.enterprise_id'" in sql
    assert arg == ent


# ─── estimate_cost_cents / pricing ────────────────────────────────────

@pytest.mark.asyncio
async def test_cost_math_with_db_pricing():
    # 4000 prompt chars = 1000 tokens @ 0.003/1k → $0.003
    # 4000 completion chars = 1000 tokens @ 0.015/1k → $0.015
    # total $0.018 = 1.8 cents
    pool, _ = _mock_pool(
        fetchrow_results=[
            {"cost_per_1k_prompt": 0.003, "cost_per_1k_completion": 0.015},
        ],
    )
    cents = await external_budget.estimate_cost_cents(pool, "claude-sonnet-4-6", 4000, 4000)
    assert cents == pytest.approx(1.8)


@pytest.mark.asyncio
async def test_pricing_falls_back_to_defaults_when_model_unknown():
    pool, _ = _mock_pool(fetchrow_results=[None])
    pricing = await external_budget.get_pricing(pool, "claude-new-model")
    assert pricing == (
        external_budget._DEFAULT_COST_PER_1K_PROMPT,
        external_budget._DEFAULT_COST_PER_1K_COMPLETION,
    )


@pytest.mark.asyncio
async def test_pricing_lookup_failure_never_zero_rates():
    pool, _ = _mock_pool(fetchrow_side_effect=RuntimeError("db down"))
    cents = await external_budget.estimate_cost_cents(pool, "claude-sonnet-4-6", 4000, 0)
    assert cents > 0


@pytest.mark.asyncio
async def test_pricing_cache_skips_second_lookup():
    pool, conn = _mock_pool(
        fetchrow_results=[
            {"cost_per_1k_prompt": 0.003, "cost_per_1k_completion": 0.015},
        ],
    )
    await external_budget.get_pricing(pool, "claude-sonnet-4-6")
    await external_budget.get_pricing(pool, "claude-sonnet-4-6")
    assert conn.fetchrow.call_count == 1


# ─── Router integration: exhausted budget → internal dispatch ─────────

@pytest.fixture
def client():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
    return TestClient(app)


def _infer_payload():
    return {
        "task": "analysis_summary",
        "prompt": "Summarise Q2 revenue",
        "enterprise_id": str(uuid4()),
        "consent_external": True,
        "max_tokens": 200,
    }


def test_budget_exhausted_downgrades_external_to_internal(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:14b")
    invoke_mock = AsyncMock(return_value=("OK", "qwen2.5:14b"))
    with (
        patch("llm_gateway.router.get_pool", return_value=MagicMock()),
        patch(
            "llm_gateway.router.routing.resolve_model",
            AsyncMock(return_value=("claude-sonnet-4-6", "external")),
        ),
        patch(
            "llm_gateway.router.external_budget.is_exhausted",
            AsyncMock(return_value=True),
        ),
        patch("llm_gateway.router.providers.invoke", invoke_mock),
        patch("llm_gateway.router.audit.log_decision", AsyncMock(return_value=None)),
        patch("llm_gateway.router.ai_governance.record_ai_call", AsyncMock(return_value=None)),
        patch("llm_gateway.router.tenant_quotas.check_and_consume", AsyncMock(return_value=None)),
    ):
        resp = client.post("/v1/infer", json=_infer_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "internal"
    assert body["model_used"] == "qwen2.5:14b"
    # The provider was invoked with the downgraded model, not Claude.
    assert invoke_mock.call_args.kwargs["model_id"] == "qwen2.5:14b"
    assert invoke_mock.call_args.kwargs["method"] == "internal"


def test_budget_headroom_keeps_external_dispatch(client):
    invoke_mock = AsyncMock(return_value=("OK", "claude-sonnet-4-6"))
    governance_mock = AsyncMock(return_value=None)
    with (
        patch("llm_gateway.router.get_pool", return_value=MagicMock()),
        patch(
            "llm_gateway.router.routing.resolve_model",
            AsyncMock(return_value=("claude-sonnet-4-6", "external")),
        ),
        patch(
            "llm_gateway.router.external_budget.is_exhausted",
            AsyncMock(return_value=False),
        ),
        patch(
            "llm_gateway.router.external_budget.estimate_cost_cents",
            AsyncMock(return_value=1.8),
        ),
        patch("llm_gateway.router.providers.invoke", invoke_mock),
        patch("llm_gateway.router.audit.log_decision", AsyncMock(return_value=None)),
        patch("llm_gateway.router.ai_governance.record_ai_call", governance_mock),
        patch("llm_gateway.router.tenant_quotas.check_and_consume", AsyncMock(return_value=None)),
    ):
        resp = client.post("/v1/infer", json=_infer_payload())

    assert resp.status_code == 200
    assert resp.json()["method"] == "external"
    # Real cost lands on the governance audit row (budget accrual source).
    assert governance_mock.call_args.kwargs["cost_cents"] == 1.8
