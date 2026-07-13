"""
Per-tenant USD budget gate for EXTERNAL (vendor) LLM calls.

A tenant opts into a hard spend cap by carrying a `tenant_quotas` row
with quota_type='llm_budget_cents_external'. `max_value` is the TOTAL
budget in cents for external calls across all time — the `period`
column is ignored by this gate (rows use 'rolling' by convention only
to satisfy the table's CHECK constraint).

Spend source of truth = SUM(ai_decision_audit.cost_cents) over the
tenant's rows with consent_external=TRUE. The gateway computes
cost_cents per external call from `llm_models` pricing
(cost_per_1k_prompt / cost_per_1k_completion, USD per 1k tokens;
tokens estimated as chars/4 — same heuristic the quota pre-flight
uses).

Breach behaviour is a SILENT DOWNGRADE, never an error: when spent
reaches the cap the router flips method external→internal so the
request is served by local Qwen (ADR-0015 Rule 5 spirit — budget
exhaustion is treated like a vendor being unavailable). No budget
row → no cap (fail-open), matching tenant_quotas conventions; infra
errors also fail open so the budget path can never block dispatch.
"""
from __future__ import annotations

import os
import time
from typing import Optional
from uuid import UUID

import asyncpg
import structlog

log = structlog.get_logger()

BUDGET_QUOTA_TYPE = "llm_budget_cents_external"

# Same rough chars-per-token average as the quota pre-flight estimate.
_CHARS_PER_TOKEN = 4

# Fallback pricing (USD per 1k tokens) when the model has no llm_models
# row — defaults follow the claude-sonnet seed in mig 010. Env-tunable
# so ops can correct drift without a redeploy.
_DEFAULT_COST_PER_1K_PROMPT = float(os.getenv("KAORI_EXT_COST_PER_1K_PROMPT", "0.003"))
_DEFAULT_COST_PER_1K_COMPLETION = float(os.getenv("KAORI_EXT_COST_PER_1K_COMPLETION", "0.015"))

# llm_models pricing barely changes — cache lookups in-process.
_PRICING_TTL_SECONDS = float(os.getenv("KAORI_EXT_PRICING_TTL_SECONDS", "300"))
_pricing_cache: dict[str, tuple[float, tuple[float, float]]] = {}


def _cache_get(model_id: str) -> Optional[tuple[float, float]]:
    hit = _pricing_cache.get(model_id)
    if hit is None:
        return None
    ts, pricing = hit
    if time.monotonic() - ts > _PRICING_TTL_SECONDS:
        _pricing_cache.pop(model_id, None)
        return None
    return pricing


async def get_pricing(pool: asyncpg.Pool, model_id: str) -> tuple[float, float]:
    """(cost_per_1k_prompt, cost_per_1k_completion) in USD for model_id.

    Falls back to env defaults when the model has no llm_models row or
    the lookup fails — a missing price must never zero-rate an external
    call (that would silently blow the budget).
    """
    cached = _cache_get(model_id)
    if cached is not None:
        return cached
    pricing = (_DEFAULT_COST_PER_1K_PROMPT, _DEFAULT_COST_PER_1K_COMPLETION)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT cost_per_1k_prompt, cost_per_1k_completion
                   FROM llm_models WHERE model_id = $1""",
                model_id,
            )
        if row is not None and row["cost_per_1k_prompt"] is not None:
            pricing = (
                float(row["cost_per_1k_prompt"]),
                float(row["cost_per_1k_completion"] or 0.0),
            )
    except Exception as exc:  # noqa: BLE001 — pricing lookup is best-effort
        log.warning("external_budget.pricing_lookup_failed", model=model_id, error=str(exc))
    _pricing_cache[model_id] = (time.monotonic(), pricing)
    return pricing


async def estimate_cost_cents(
    pool: asyncpg.Pool,
    model_id: str,
    prompt_chars: int,
    completion_chars: int,
) -> float:
    """Estimated USD cost in cents of one external call (chars/4 ≈ tokens)."""
    per_1k_prompt, per_1k_completion = await get_pricing(pool, model_id)
    prompt_tokens = prompt_chars / _CHARS_PER_TOKEN
    completion_tokens = completion_chars / _CHARS_PER_TOKEN
    usd = (prompt_tokens / 1000.0) * per_1k_prompt + (completion_tokens / 1000.0) * per_1k_completion
    return round(usd * 100.0, 4)


async def is_exhausted(pool: asyncpg.Pool, enterprise_id: str | UUID) -> bool:
    """True when the tenant has a budget row AND lifetime external spend
    (SUM ai_decision_audit.cost_cents, consent_external=TRUE) has reached
    it. False when no budget row exists or on any infra error (fail-open —
    this gate must never block dispatch)."""
    if not enterprise_id:
        return False
    try:
        ent_uuid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))
        async with pool.acquire() as conn:
            async with conn.transaction():
                # tenant_quotas + ai_decision_audit are RLS-protected —
                # scope the GUC to this transaction (K-1).
                await conn.execute(
                    "SELECT set_config('app.enterprise_id', $1, true)",
                    str(ent_uuid),
                )
                cap_row = await conn.fetchrow(
                    """SELECT max_value FROM tenant_quotas
                       WHERE enterprise_id = $1 AND quota_type = $2 AND enabled = TRUE
                       LIMIT 1""",
                    ent_uuid, BUDGET_QUOTA_TYPE,
                )
                if cap_row is None:
                    return False
                cap_cents = float(cap_row["max_value"])
                spent_row = await conn.fetchrow(
                    """SELECT COALESCE(SUM(cost_cents), 0) AS spent
                       FROM ai_decision_audit
                       WHERE enterprise_id = $1 AND consent_external = TRUE""",
                    ent_uuid,
                )
                spent_cents = float(spent_row["spent"])
        if spent_cents >= cap_cents:
            log.warning(
                "external_budget.exhausted",
                enterprise_id=str(ent_uuid),
                cap_cents=cap_cents,
                spent_cents=spent_cents,
            )
            return True
        return False
    except Exception as exc:  # noqa: BLE001 — fail OPEN, never block dispatch
        log.warning(
            "external_budget.check_failed.fail_open",
            enterprise_id=str(enterprise_id),
            error=str(exc),
        )
        return False
