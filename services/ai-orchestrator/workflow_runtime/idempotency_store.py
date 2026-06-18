"""
Persistent idempotency store — P0.3 of orchestration hardening.

Replaces the in-process Dict cache that call_api used in wave 3 (the
cache evaporated on every worker restart, allowing re-fire of POSTs to
partners). This module surfaces a typed get_or_set() that's safe across
worker restarts + cross-pod when multiple workers share Postgres.

API
---
  derive_key()      pure — sha256-based key from (tenant, run, node, attempt)
                            OR pass-through of a caller-supplied
                            Idempotency-Key header value.
  get_or_set()      atomic — returns cached payload on hit, INSERTs new on
                            miss (caller proceeds with side effect on miss).
  record_outcome()  atomic — UPDATE the row with the side-effect result
                            after the operation completes.
  sweep_expired()   admin — DELETE rows past expires_at (background job).

Typical caller flow (external executor):
    key = derive_key(run_id=ctx.run_id, node_id=ctx.node_id, attempt=N)
    hit = await get_or_set(
        enterprise_id=ctx.enterprise_id, key=key,
        side_effect_class='external',
        ttl_seconds=86_400,   # 24h
    )
    if hit.cached:
        return hit.response_payload   # short-circuit
    # ... fire the side effect ...
    await record_outcome(
        enterprise_id=ctx.enterprise_id, key=key,
        response_payload={'status_code': 200, ...},
    )
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


@dataclass(frozen=True)
class IdempotencyHit:
    """Returned by get_or_set(). cached=True means a previous run
    already executed — caller should NOT re-fire the side effect."""
    cached:           bool
    record_id:        UUID
    response_payload: dict[str, Any]
    response_status:  str
    attempt_count:    int


def derive_key(
    *,
    run_id:   UUID,
    node_id:  UUID,
    attempt:  int = 1,
    seed:     str = "",
) -> str:
    """Deterministic SHA-256 hex (first 64 chars) of run+node+attempt.

    `seed` is an optional discriminator the caller can mix in (e.g. the
    method + URL for call_api so different URLs from the same node get
    different keys).
    """
    payload = f"{run_id}|{node_id}|{attempt}|{seed}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_or_set(
    *,
    enterprise_id:     UUID,
    key:               str,
    side_effect_class: str,
    run_id:            Optional[UUID] = None,
    node_id:           Optional[UUID] = None,
    ttl_seconds:       int = 86_400,
) -> IdempotencyHit:
    """Atomic lookup-or-reserve. Hot path on every retry.

    Strategy:
      1. SELECT existing row + check NOT expired.
      2. If exists + not expired: return cached=True.
      3. INSERT placeholder row with response_status='pending'; on
         conflict UPDATE attempt_count + return cached=True (race lost).
      4. Return cached=False (caller proceeds with side effect).
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    async with acquire_for_tenant(enterprise_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT record_id, response_payload, response_status,
                          attempt_count, expires_at
                   FROM workflow_idempotency_records
                   WHERE enterprise_id = $1 AND idempotency_key = $2
                   FOR UPDATE""",
                enterprise_id, key,
            )
            if row is not None:
                now = datetime.now(timezone.utc)
                if row["expires_at"] > now:
                    # Bump last_seen_at + attempt_count so callers see retry pressure
                    await conn.execute(
                        """UPDATE workflow_idempotency_records
                           SET attempt_count = attempt_count + 1,
                               last_seen_at  = NOW()
                           WHERE record_id = $1""",
                        row["record_id"],
                    )
                    payload = row["response_payload"]
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload) if payload else {}
                        except json.JSONDecodeError:
                            payload = {}
                    return IdempotencyHit(
                        cached=True,
                        record_id=row["record_id"],
                        response_payload=payload or {},
                        response_status=row["response_status"],
                        attempt_count=row["attempt_count"] + 1,
                    )
                # Expired — overwrite in place.
                await conn.execute(
                    """UPDATE workflow_idempotency_records
                       SET response_status = 'pending',
                           response_payload = '{}'::jsonb,
                           error_message = NULL,
                           attempt_count = 1,
                           created_at = NOW(),
                           last_seen_at = NOW(),
                           expires_at = $1
                       WHERE record_id = $2""",
                    expires_at, row["record_id"],
                )
                return IdempotencyHit(
                    cached=False,
                    record_id=row["record_id"],
                    response_payload={},
                    response_status="pending",
                    attempt_count=1,
                )
            # No existing row — INSERT placeholder.
            new = await conn.fetchrow(
                """INSERT INTO workflow_idempotency_records
                       (enterprise_id, idempotency_key, run_id, node_id,
                        side_effect_class, response_status, expires_at)
                   VALUES ($1, $2, $3, $4, $5, 'pending', $6)
                   ON CONFLICT (enterprise_id, idempotency_key) DO UPDATE
                       SET attempt_count = workflow_idempotency_records.attempt_count + 1,
                           last_seen_at  = NOW()
                   RETURNING record_id, response_payload, response_status,
                             attempt_count,
                             (xmax = 0) AS inserted""",
                enterprise_id, key, run_id, node_id, side_effect_class, expires_at,
            )
            if new["inserted"]:
                return IdempotencyHit(
                    cached=False,
                    record_id=new["record_id"],
                    response_payload={},
                    response_status="pending",
                    attempt_count=1,
                )
            # Race lost — concurrent retry won. Treat as cached even if
            # the winner hasn't recorded the outcome yet (its caller will).
            payload = new["response_payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload) if payload else {}
                except json.JSONDecodeError:
                    payload = {}
            return IdempotencyHit(
                cached=True,
                record_id=new["record_id"],
                response_payload=payload or {},
                response_status=new["response_status"],
                attempt_count=new["attempt_count"],
            )


async def record_outcome(
    *,
    enterprise_id:    UUID,
    key:              str,
    response_payload: dict[str, Any],
    response_status:  str = "completed",
    error_message:    Optional[str] = None,
) -> None:
    """Persist the side-effect result. Caller MUST call this after the
    side effect succeeds (or fails non-retriably) so future retries
    return the cached payload instead of re-firing.
    """
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        result = await conn.execute(
            """UPDATE workflow_idempotency_records
               SET response_payload = $1::jsonb,
                   response_status  = $2,
                   error_message    = $3,
                   last_seen_at     = NOW()
               WHERE enterprise_id = $4 AND idempotency_key = $5""",
            json.dumps(response_payload, default=str), response_status,
            error_message, enterprise_id, key,
        )
        if result.endswith(" 0"):
            log.warning("idempotency.record_outcome.missing",
                          key=key[:12], enterprise_id=str(enterprise_id))


async def sweep_expired(enterprise_id: UUID, limit: int = 5_000) -> int:
    """Background-job entry: delete rows past expires_at. Returns
    number of rows removed."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        result = await conn.execute(
            """DELETE FROM workflow_idempotency_records
               WHERE expires_at < NOW()
                 AND record_id IN (
                   SELECT record_id FROM workflow_idempotency_records
                   WHERE expires_at < NOW()
                   LIMIT $1
                 )""",
            limit,
        )
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0
