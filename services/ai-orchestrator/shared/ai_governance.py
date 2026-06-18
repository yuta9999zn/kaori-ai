"""
AI governance audit layer — P3 of Phase 2.7.

Records every LLM call with model_version + prompt_hash + context_refs +
confidence + human_override per anh's §3C requirement.

API
---
  record_ai_call()        — INSERT one audit row after the LLM call
  record_human_override() — UPDATE the override fields (only fields the
                              trigger allows)
  hash_prompt()           — SHA-256 of the rendered prompt
  list_for_tenant()       — paginated read for compliance export

Caller pattern (inside llm_router.complete after response):
    await record_ai_call(
        enterprise_id=...,
        task_kind="classify_document",
        model_version="qwen2.5-14b",
        model_provider="ollama",
        prompt=full_prompt,
        context_refs=[{"doc_id":"X","page":2},...],
        confidence=0.83,
        output=completion_text,
        latency_ms=2400,
        token_input_count=1200,
        token_output_count=250,
        cost_cents=0.0042,
    )
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


@dataclass(frozen=True)
class AiAuditRow:
    audit_id:           UUID
    enterprise_id:      UUID
    task_kind:          str
    model_version:      str
    model_provider:     str
    prompt_hash:        str
    confidence:         Optional[float]
    consent_external:   bool
    pii_redacted:       bool
    human_override_at:  Optional[datetime]
    latency_ms:         int
    token_input_count:  int
    token_output_count: int
    cost_cents:         float
    created_at:         datetime


def hash_prompt(prompt: str) -> str:
    """SHA-256 hex of the prompt as fed to the model. Caller passes
    the rendered string (after template + variable substitution).
    Truncates pre-hash if > 1 MB to avoid OOM — collision is irrelevant
    for governance (we're tracking 'same prompt' not crypto-uniqueness)."""
    if not prompt:
        return hashlib.sha256(b"").hexdigest()
    if len(prompt) > 1_000_000:
        prompt = prompt[:1_000_000]
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def hash_output(output: str) -> str:
    """Same shape as hash_prompt for the LLM completion."""
    return hash_prompt(output or "")


async def record_ai_call(
    *,
    enterprise_id:       UUID,
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
) -> UUID:
    """Append-only AI audit. Returns the new audit_id for caller to
    correlate downstream (decision_audit_log row, etc.)."""
    if not task_kind:
        raise ValueError("ai_governance.record_ai_call: task_kind required")
    if not model_version:
        raise ValueError("ai_governance.record_ai_call: model_version required")
    if not model_provider:
        raise ValueError("ai_governance.record_ai_call: model_provider required")
    if confidence is not None and not (0.0 <= float(confidence) <= 1.0):
        raise ValueError("ai_governance.record_ai_call: confidence must be 0..1")

    from ai_orchestrator.shared.db import acquire_for_tenant

    prompt_h = hash_prompt(prompt)
    output_h = hash_output(output) if output else None
    refs_json = json.dumps(context_refs or [], ensure_ascii=False, default=str)

    async with acquire_for_tenant(enterprise_id) as conn:
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
            enterprise_id, request_id, decision_id, run_id, node_id,
            task_kind, model_version, model_provider,
            prompt_h, len(prompt or ""),
            refs_json, confidence,
            output_h, len(output or ""), output_validated,
            consent_external, pii_redacted,
            latency_ms, token_input_count, token_output_count, cost_cents,
        )

    log.debug("ai_governance.recorded",
                audit_id=str(row["audit_id"]),
                task_kind=task_kind, model_version=model_version,
                confidence=confidence, enterprise_id=str(enterprise_id))
    return row["audit_id"]


async def record_human_override(
    *,
    enterprise_id:        UUID,
    audit_id:             UUID,
    user_id:              UUID,
    note:                 str = "",
) -> bool:
    """Stamp the override fields on an existing audit row. The mig 098
    trigger allows updates only on (human_override_user_id, at, note)
    columns — every other field is immutable.

    Returns True if a row was updated; False if audit_id not found
    (or RLS hidden).
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        result = await conn.execute(
            """UPDATE ai_decision_audit
               SET human_override_user_id = $1,
                   human_override_at      = NOW(),
                   human_override_note    = $2
               WHERE audit_id = $3""",
            user_id, note[:2000], audit_id,
        )
    rows = 0
    try:
        rows = int(result.split()[-1])
    except (ValueError, IndexError):
        pass
    if rows == 0:
        log.warning("ai_governance.override.audit_not_found",
                      audit_id=str(audit_id),
                      enterprise_id=str(enterprise_id))
        return False
    log.info("ai_governance.override.recorded",
              audit_id=str(audit_id), user_id=str(user_id),
              enterprise_id=str(enterprise_id))
    return True


async def list_for_tenant(
    *,
    enterprise_id: UUID,
    limit:         int = 100,
    only_overridden: bool = False,
) -> list[AiAuditRow]:
    """Read audit rows for compliance export. Most-recent-first."""
    if limit < 1 or limit > 10_000:
        raise ValueError("limit must be 1..10000")

    from ai_orchestrator.shared.db import acquire_for_tenant

    where = ""
    if only_overridden:
        where = "AND human_override_user_id IS NOT NULL"

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT audit_id, enterprise_id, task_kind, model_version,
                       model_provider, prompt_hash, confidence,
                       consent_external, pii_redacted, human_override_at,
                       latency_ms, token_input_count, token_output_count,
                       cost_cents, created_at
                FROM ai_decision_audit
                WHERE enterprise_id = $1 {where}
                ORDER BY created_at DESC LIMIT $2""",
            enterprise_id, limit,
        )

    return [AiAuditRow(
        audit_id=r["audit_id"],
        enterprise_id=r["enterprise_id"],
        task_kind=r["task_kind"],
        model_version=r["model_version"],
        model_provider=r["model_provider"],
        prompt_hash=r["prompt_hash"],
        confidence=float(r["confidence"]) if r["confidence"] is not None else None,
        consent_external=r["consent_external"],
        pii_redacted=r["pii_redacted"],
        human_override_at=r["human_override_at"],
        latency_ms=r["latency_ms"],
        token_input_count=r["token_input_count"],
        token_output_count=r["token_output_count"],
        cost_cents=float(r["cost_cents"]),
        created_at=r["created_at"],
    ) for r in rows]
