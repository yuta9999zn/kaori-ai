"""
K-6 audit log helper — writes to ``decision_audit_log``.

Mirror of services/ai-orchestrator/shared/audit.py. Same signature,
same best-effort guarantee, same truncation. Kept as a separate
module per service so each service can be deployed independently
without cross-service Python imports.

Per CLAUDE.md K-6: every automated decision (column-mapping,
cleaning rule application, …) must produce a row in
``decision_audit_log``. The table is append-only (RULE in
migration 001 / 002 prevents UPDATE/DELETE), so a write is a
single INSERT and never contends with downstream readers.

Design notes
------------

* **Best-effort.** A DB error here is logged but never raised. The
  primary path that triggered the audit (e.g. a cleaning rule
  application) must not fail because we couldn't write the audit.
  The reverse — silent audit gap — is recoverable; a 500 in the
  cleaning path is not.

* **Separate transaction from the caller.** This helper uses
  ``pool.execute()`` directly, NOT the caller's
  ``acquire_for_tenant`` connection. That means:
  (a) the audit row survives if the caller's transaction rolls back
      → "we tried to do X" semantics;
  (b) the helper can be called from inside or outside the caller's
      ``async with`` block without nesting issues.
  Trade-off: not transactionally consistent with the main work. Use
  inline ``conn.execute(INSERT INTO decision_audit_log ...)`` in
  the caller's transaction if that matters (see schema.py).

* **No enterprise_id ⇒ skip.** ``decision_audit_log.enterprise_id``
  is NOT NULL with a FK to ``enterprises``. Callers that don't have
  a tenant context (rare; mostly background tasks) get a debug log
  and the row is dropped on the floor.

* **Truncation.** Long subjects / chosen_values / reasoning are
  truncated before insert to keep the table queryable.
"""
import json
from typing import Optional
from uuid import UUID

import structlog

from .db import get_pool

log = structlog.get_logger()

# 4 KB per text column — enough to capture the gist, small enough that
# 73 B audit rows × 4 KB stays under the Postgres-hot retention budget
# (90 days; per architecture/TARGET_ARCHITECTURE_1M.md).
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
        pool = get_pool()
    except RuntimeError:
        # Pool not initialised (e.g. during early test bootstrap or
        # a failed lifespan start). Skip silently — better to lose
        # an audit row than crash the caller.
        log.debug("audit.skip.pool_uninit", decision_type=decision_type)
        return

    try:
        await pool.execute(
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
    except Exception as e:
        # Best-effort: the cleaning rule / etc. must still flow back
        # to the user even if the audit log is down.
        log.error("audit.write.failed",
                  decision_type=decision_type, error=str(e))


def _truncate(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= _MAX_TEXT_LEN:
        return text
    return text[:_MAX_TEXT_LEN] + "...[truncated]"
