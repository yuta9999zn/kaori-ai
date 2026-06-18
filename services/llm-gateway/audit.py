"""
K-6 audit log helper — writes one row per LLM call to
``decision_audit_log``. Mirror of services/ai-orchestrator/shared/
audit.py so the gateway can stand on its own.

Best-effort by design: a DB error here is logged but never raised.
The primary path (the LLM call itself) must not fail because we
couldn't write the audit. The reverse — silent audit gap — is
recoverable; a 500 on the LLM path is not.

Long prompts / responses are truncated before insert to keep the
table queryable; full text belongs in object storage / logs.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

import asyncpg
import structlog

log = structlog.get_logger()

_MAX_TEXT_LEN = 8000


async def log_decision(
    pool: Optional[asyncpg.Pool] = None,
    *,
    enterprise_id: Optional[str | UUID],
    run_id: Optional[str | UUID],
    decision_type: str,
    subject: str,
    chosen_value: Optional[str],
    method: str,
    llm_provider: Optional[str],
    reasoning: Optional[str] = None,
) -> None:
    if not enterprise_id:
        # FK to enterprises is NOT NULL — drop the audit row rather
        # than insert garbage. Background callers without tenant
        # context are rare and visible via the debug log.
        log.debug("audit.skip.no_enterprise_id", subject=subject)
        return

    ent_uuid = enterprise_id if isinstance(enterprise_id, UUID) else UUID(str(enterprise_id))
    run_uuid = None
    if run_id:
        run_uuid = run_id if isinstance(run_id, UUID) else UUID(str(run_id))

    # F1 follow-up — when pool is None, use the retry helper. When the
    # caller passed an explicit pool (transitional + tests), keep the
    # legacy pool.execute() shape so existing test mocks stay valid.
    sql = """INSERT INTO decision_audit_log
                (enterprise_id, run_id, decision_type, subject, chosen_value,
                 confidence, method, alternatives, uncertainty_flags,
                 llm_provider, reasoning)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11)"""
    args = (
        ent_uuid, run_uuid, decision_type,
        _truncate(subject) or "", _truncate(chosen_value),
        None, method, "[]", [], llm_provider, _truncate(reasoning),
    )

    try:
        if pool is not None:
            await pool.execute(sql, *args)
        else:
            from .db import acquire_with_retry
            async with acquire_with_retry() as conn:
                await conn.execute(sql, *args)
    except Exception as exc:
        log.error("audit.write_failed", subject=subject, error=str(exc))


def _truncate(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= _MAX_TEXT_LEN:
        return text
    return text[:_MAX_TEXT_LEN] + "...[truncated]"
