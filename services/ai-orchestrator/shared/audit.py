"""
K-6 audit log helper — writes to ``decision_audit_log``.

Per CLAUDE.md K-6: every automated decision (LLM routing call, schema
column-mapping decision, cleaning rule application, …) must produce a
row in ``decision_audit_log``. The table is append-only (RULE in
migration 001 / 002 prevents UPDATE/DELETE), so a write is a single
INSERT and never contends with downstream readers.

Design notes
------------

* **Best-effort.** A DB error here is logged but never raised. The
  primary path that triggered the audit (e.g. an LLM call) must not
  fail because we couldn't write the audit. The reverse — silent
  audit gap — is recoverable; a 500 in the LLM path is not.

* **No enterprise_id ⇒ skip.** ``decision_audit_log.enterprise_id``
  is NOT NULL with a FK to ``enterprises``. Callers that don't have
  a tenant context (rare; mostly background tasks) get a debug log
  and the row is dropped on the floor.

* **Truncation.** Long prompts / responses are truncated before
  insert to keep the table queryable. Full text belongs in object
  storage / structured logs, not the audit table.
"""
import json
from typing import Optional
from uuid import UUID

import structlog

from .db import acquire_for_tenant

log = structlog.get_logger()

# 4 KB per text column — enough to capture the gist of a prompt or
# response, small enough that 73 B audit rows × 4 KB stays under the
# Postgres-hot retention budget (90 days; per TARGET_ARCHITECTURE_1M.md).
_MAX_TEXT_LEN = 4000


async def log_decision(
    *,
    enterprise_id: str,
    decision_type: str,
    subject: str,
    chosen_value: Optional[str] = None,
    confidence: Optional[float] = None,
    method: Optional[str] = None,
    llm_provider: Optional[str] = None,
    reasoning: Optional[str] = None,
    run_id: Optional[str] = None,
    alternatives: Optional[list] = None,
    uncertainty_flags: Optional[list[str]] = None,
) -> None:
    """Insert a single row into ``decision_audit_log``.

    All errors are caught and logged. Callers can rely on this
    function never raising — see module docstring.
    """
    if not enterprise_id:
        log.debug("audit.skip.no_enterprise_id", decision_type=decision_type)
        return

    try:
        ent_uuid = UUID(enterprise_id)
    except (ValueError, TypeError):
        log.warning("audit.skip.invalid_enterprise_id",
                    value=enterprise_id, decision_type=decision_type)
        return

    run_uuid: Optional[UUID] = None
    if run_id:
        try:
            run_uuid = UUID(run_id)
        except (ValueError, TypeError):
            # run_id is nullable in the schema; just drop it
            log.debug("audit.invalid_run_id", value=run_id)

    try:
        # K-1: decision_audit_log has FORCED row-level security with a
        # ``enterprise_id = current_setting('app.enterprise_id')::uuid``
        # policy. Writing on a raw pool connection leaves that GUC unset,
        # so the policy evaluates ``''::uuid`` and the INSERT dies with
        # "invalid input syntax for type uuid: \"\"" — a silent audit gap.
        # acquire_for_tenant sets the GUC, so the policy passes.
        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute(
                """INSERT INTO decision_audit_log
                   (enterprise_id, run_id, decision_type, subject, chosen_value,
                    confidence, method, alternatives, uncertainty_flags,
                    llm_provider, reasoning)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11)""",
                ent_uuid,
                run_uuid,
                decision_type,
                _truncate(subject) or "",
                _truncate(chosen_value),
                confidence,
                method,
                json.dumps(alternatives) if alternatives else None,
                uncertainty_flags or [],
                llm_provider,
                _truncate(reasoning),
            )
    except RuntimeError:
        # Pool not initialised (e.g. early test bootstrap / failed
        # lifespan start). Skip silently — better to lose an audit row
        # than crash the caller.
        log.debug("audit.skip.pool_uninit", decision_type=decision_type)
    except Exception as e:
        # Best-effort: the LLM response / cleaning rule / etc. must
        # still flow back to the user even if the audit log is down.
        log.error("audit.write.failed",
                  decision_type=decision_type, error=str(e))


def _truncate(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= _MAX_TEXT_LEN:
        return text
    return text[:_MAX_TEXT_LEN] + "...[truncated]"
