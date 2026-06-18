"""
Tests for task→model routing (services/llm-gateway/routing.py).

This is where the K-4 invariant lives at the gateway boundary: an
external model is silently downgraded to the safe local default when
the caller has not opted in via ``consent_external``. The tests pin
that downgrade for every entry path:

  * ``model_hint`` override                  — caller-supplied model
  * ``llm_task_routing`` lookup              — DB-driven default
  * missing rule                             — fallback default

A dedicated test asserts the hardcoded default is the on-prem Qwen
model, so a future maintainer can't accidentally retarget the K-4
fallback to something external.
"""
from unittest.mock import AsyncMock

import pytest

from llm_gateway import routing


# ─── Helpers ─────────────────────────────────────────────────────────

def _pool_with(*, hint_provider=None, task_row=None):
    """Build a mock asyncpg pool wired for the two queries
    routing.resolve_model can run:
      - fetchval('SELECT provider FROM llm_models WHERE model_id = $1')
      - fetchrow('SELECT default_model_id, provider FROM llm_task_routing ...')
    """
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=hint_provider)
    pool.fetchrow = AsyncMock(return_value=task_row)
    return pool


# ─── model_hint override path ────────────────────────────────────────

@pytest.mark.asyncio
async def test_model_hint_external_with_consent_true_returns_external():
    pool = _pool_with(hint_provider="anthropic")

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=True, model_hint="claude-sonnet-4-6"
    )

    assert model == "claude-sonnet-4-6"
    assert method == "external"
    pool.fetchrow.assert_not_called()  # hint short-circuits the task lookup


@pytest.mark.asyncio
async def test_model_hint_external_with_consent_false_downgrades_to_internal_default():
    """K-4: caller hinted Claude but didn't opt in → fall back to Qwen."""
    pool = _pool_with(hint_provider="anthropic")

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint="claude-sonnet-4-6"
    )

    assert method == "internal"
    assert model == "qwen2.5:14b"  # _DEFAULT_INTERNAL_MODEL


@pytest.mark.asyncio
async def test_model_hint_internal_passes_through_regardless_of_consent():
    pool = _pool_with(hint_provider="ollama")

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint="qwen2.5:7b"
    )

    assert model == "qwen2.5:7b"
    assert method == "internal"


@pytest.mark.asyncio
async def test_model_hint_unknown_provider_treated_as_internal():
    """fetchval returns None when the row is missing — routing must
    treat the hint as internal, not silently call out to the public
    internet."""
    pool = _pool_with(hint_provider=None)

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint="some-local-model"
    )

    assert model == "some-local-model"
    assert method == "internal"


# ─── Task-routing table path ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_lookup_returns_external_with_consent():
    pool = _pool_with(task_row={
        "default_model_id": "claude-sonnet-4-6",
        "provider": "anthropic",
    })

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=True, model_hint=None
    )

    assert model == "claude-sonnet-4-6"
    assert method == "external"


@pytest.mark.asyncio
async def test_task_lookup_external_without_consent_downgrades():
    """K-4 again — same enforcement on the DB-driven path."""
    pool = _pool_with(task_row={
        "default_model_id": "gpt-4o",
        "provider": "openai",
    })

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint=None
    )

    assert method == "internal"
    assert model == "qwen2.5:14b"


@pytest.mark.asyncio
async def test_task_lookup_ollama_provider_is_internal():
    pool = _pool_with(task_row={
        "default_model_id": "qwen2.5:14b",
        "provider": "ollama",
    })

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint=None
    )

    assert model == "qwen2.5:14b"
    assert method == "internal"


@pytest.mark.asyncio
async def test_task_lookup_internal_provider_is_internal():
    """The 'internal' provider literal is treated as internal too —
    operators sometimes use that string instead of 'ollama'."""
    pool = _pool_with(task_row={
        "default_model_id": "qwen2.5:14b",
        "provider": "internal",
    })

    model, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint=None
    )

    assert method == "internal"


@pytest.mark.asyncio
async def test_task_lookup_null_provider_treated_as_internal():
    """LEFT JOIN miss → provider is None → internal (fail safe)."""
    pool = _pool_with(task_row={
        "default_model_id": "qwen2.5:14b",
        "provider": None,
    })

    _, method = await routing.resolve_model(
        pool, task="insight", consent_external=False, model_hint=None
    )

    assert method == "internal"


# ─── No-rule fallback path ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_routing_rule_falls_back_to_default_internal():
    pool = _pool_with(task_row=None)

    model, method = await routing.resolve_model(
        pool, task="never_seen", consent_external=True, model_hint=None
    )

    assert model == "qwen2.5:14b"
    assert method == "internal"


# ─── K-4 anchor — the safe default must remain Qwen ──────────────────

def test_default_internal_model_is_pinned_to_on_prem_qwen():
    """If a future refactor renames _DEFAULT_INTERNAL_MODEL to anything
    that isn't an on-prem Qwen build, it would silently weaken K-4 —
    every K-4 downgrade ends up here. Pin it so the diff is loud."""
    assert routing._DEFAULT_INTERNAL_MODEL.startswith("qwen")
