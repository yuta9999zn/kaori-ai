"""
Phase 2.7 P3 — AI governance audit, llm-gateway local writer.

Mirrors services/ai-orchestrator/shared/ai_governance.py but with:
  - llm-gateway's own asyncpg.Pool (no acquire_for_tenant helper here —
    we manually set `app.enterprise_id` GUC LOCAL=true inside the
    transaction so the RLS policy on ai_decision_audit passes).
  - Best-effort write: a DB failure is logged but never raises so the
    primary /v1/infer path can return successfully.

Together with the existing K-6 decision_audit_log (which captures the
business decision), ai_decision_audit captures the LLM CALL that fed
it: model + prompt hash + context refs + confidence + override metadata.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional
from uuid import UUID

import asyncpg
import structlog

log = structlog.get_logger()


def hash_prompt(prompt: str) -> str:
    """SHA-256 hex of the rendered prompt. Truncates pre-hash if > 1 MB
    to avoid OOM — collision is irrelevant for governance (we're
    tracking 'same prompt' not crypto-uniqueness)."""
    if not prompt:
        return hashlib.sha256(b"").hexdigest()
    if len(prompt) > 1_000_000:
        prompt = prompt[:1_000_000]
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def hash_output(output: str) -> str:
    """Same shape as hash_prompt for the LLM completion."""
    return hash_prompt(output or "")


async def record_ai_call(
    pool: Optional[asyncpg.Pool] = None,
    *,
    enterprise_id:       str | UUID,
    task_kind:           str,
    model_version:       str,
    model_provider:      str,
    prompt:              str,
    output:              str = "",
    context_refs:        Optional[list[dict[str, Any]]] = None,
    confidence:          Optional[float] = None,
    output_validated:    bool = False,
    consent_external:    bool = False,
    pii_redacted:        bool = True,
    request_id:          Optional[UUID] = None,
    decision_id:         Optional[UUID] = None,
    run_id:              Optional[UUID] = None,
    node_id:             Optional[UUID] = None,
    latency_ms:          int = 0,
    token_input_count:   int = 0,
    token_output_count:  int = 0,
    cost_cents:          float = 0.0,
) -> Optional[UUID]:
    """Append one row to ai_decision_audit. Returns audit_id on success,
    None on best-effort failure. Never raises.

    Validation lives in the orchestrator copy (it's authoritative for
    the contract); the gateway is a write-through, so we trust upstream
    callers and just log+drop on bad shape.
    """
    if not enterprise_id:
        log.debug("ai_governance.skip.no_enterprise_id", task_kind=task_kind)
        return None

    ent_uuid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))

    prompt_h = hash_prompt(prompt)
    output_h = hash_output(output) if output else None
    refs_json = json.dumps(context_refs or [], ensure_ascii=False, default=str)

    # F1 follow-up — prefer the retry helper but honor an explicit pool
    # passed by callers (tests + edge cases). When pool is None (the
    # default), use acquire_with_retry so transient pool blips don't
    # lose the gov row on first try.
    if pool is not None:
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def _cm():
            async with pool.acquire() as c:
                yield c
        acquire_cm = _cm()
    else:
        from .db import acquire_with_retry
        acquire_cm = acquire_with_retry()

    try:
        async with acquire_cm as conn:
            async with conn.transaction():
                # RLS GUC scoped to this txn — `true` 3rd arg = LOCAL.
                await conn.execute(
                    "SELECT set_config('app.enterprise_id', $1, true)",
                    str(ent_uuid),
                )
                row = await conn.fetchrow(
                    """INSERT INTO ai_decision_audit
                          (enterprise_id, request_id, decision_id, run_id, node_id,
                           task_kind, model_version, model_provider,
                           prompt_hash, prompt_size_bytes,
                           context_refs, confidence,
                           output_hash, output_size_bytes, output_validated,
                           consent_external, pii_redacted,
                           latency_ms, token_input_count, token_output_count, cost_cents)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                               $11::jsonb, $12, $13, $14, $15,
                               $16, $17, $18, $19, $20, $21)
                       RETURNING audit_id""",
                    ent_uuid, request_id, decision_id, run_id, node_id,
                    task_kind, model_version, model_provider,
                    prompt_h, len(prompt or ""),
                    refs_json, confidence,
                    output_h, len(output or ""), output_validated,
                    consent_external, pii_redacted,
                    latency_ms, token_input_count, token_output_count, cost_cents,
                )
    except Exception as exc:
        log.error(
            "ai_governance.write_failed",
            task_kind=task_kind,
            model_version=model_version,
            enterprise_id=str(ent_uuid),
            error=str(exc),
        )
        return None

    audit_id: UUID = row["audit_id"]
    log.debug(
        "ai_governance.recorded",
        audit_id=str(audit_id),
        task_kind=task_kind,
        model_version=model_version,
        enterprise_id=str(ent_uuid),
    )
    return audit_id
