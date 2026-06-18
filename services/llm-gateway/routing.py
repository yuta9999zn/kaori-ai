"""
Task → model routing (P-1 scaffold).

Reads llm_task_routing for the requested task. Falls back to a hard-
coded "internal qwen" default if the task isn't mapped, so the
service stays useful even when the table is empty (e.g. during
migration). Real implementations should populate llm_task_routing.
"""
from __future__ import annotations

import os
from typing import Optional

import asyncpg
import structlog

log = structlog.get_logger()


# Single source of truth for the local model name, shared with
# providers.py. Env-driven so a pilot box running the 7B model on
# limited RAM (qwen2.5:7b) doesn't 404 against an unpulled 14B default.
_DEFAULT_INTERNAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")


async def resolve_model(
    pool: asyncpg.Pool,
    *,
    task: str,
    consent_external: bool,
    model_hint: Optional[str],
) -> tuple[str, str]:
    """Return (model_id, method) for a request.

    method ∈ {"internal", "external"}.

    Resolution order:
      1. ``model_hint`` (caller override) — used as-is. Method derived
         from llm_models.provider for that id (default 'internal' if
         the row is missing).
      2. llm_task_routing[task] — default_model_id, plus the matching
         llm_models.provider for method.
      3. fallback: _DEFAULT_INTERNAL_MODEL with method='internal'.

    External models are silently downgraded to internal when
    ``consent_external`` is False (K-4 invariant).
    """
    if model_hint:
        method = await _provider_method(pool, model_hint)
        if method == "external" and not consent_external:
            log.info("llm_gateway.routing.external_blocked", model=model_hint)
            return _DEFAULT_INTERNAL_MODEL, "internal"
        return model_hint, method

    # F1 follow-up — when caller passes an explicit pool (tests +
    # transitional), use it directly; else retry through helper.
    sql = """
        SELECT r.default_model_id, m.provider
        FROM llm_task_routing r
        LEFT JOIN llm_models m ON m.model_id = r.default_model_id
        WHERE r.task_type = $1
    """
    if pool is not None:
        row = await pool.fetchrow(sql, task)
    else:
        from .db import acquire_with_retry
        async with acquire_with_retry() as conn:
            row = await conn.fetchrow(sql, task)
    if row is None:
        log.info("llm_gateway.routing.no_rule_using_default", task=task)
        return _DEFAULT_INTERNAL_MODEL, "internal"

    model_id = row["default_model_id"]
    method = "external" if row["provider"] not in (None, "ollama", "internal") else "internal"
    if method == "external" and not consent_external:
        # Downgrade to a safe local fallback.
        return _DEFAULT_INTERNAL_MODEL, "internal"
    return model_id, method


async def _provider_method(pool: asyncpg.Pool, model_id: str) -> str:
    # F1 follow-up — honor explicit pool; retry via helper otherwise.
    sql = "SELECT provider FROM llm_models WHERE model_id = $1"
    if pool is not None:
        provider = await pool.fetchval(sql, model_id)
    else:
        from .db import acquire_with_retry
        async with acquire_with_retry() as conn:
            provider = await conn.fetchval(sql, model_id)
    if provider in (None, "ollama", "internal"):
        return "internal"
    return "external"
