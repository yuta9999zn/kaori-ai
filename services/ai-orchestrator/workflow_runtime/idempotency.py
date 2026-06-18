"""
REL-004 + REL-005 (P1-S6) — workflow node idempotency framework.

Two layers:

  derive_idempotency_key()  — pure function, deterministic per
                              (workflow_id, node_id, run_id, input_hash).
                              Used by Action Runtime to look up
                              idempotency_records before firing side effects.

  IdempotencyStore (TBD P1-S7)  — async wrapper around
                              idempotency_records table. Ships when the
                              first real Temporal activity needs it.

Design choices:
  * sha256 hex (64 chars) — fits Postgres TEXT column (migration 041),
    greppable in logs, no ambiguity vs base64 encoding.
  * Inputs hashed in canonical JSON (sorted keys) so semantically equal
    inputs produce identical keys regardless of dict ordering.
  * Empty input dict accepted (some nodes have no input — pure compute
    over context); hash of {} is a stable baseline.

See:
  * docs/strategic/WORKFLOW_SYSTEM.md Phần 9 (Reliability)
  * docs/adr/0014-at-least-once-plus-idempotency.md
  * infrastructure/postgres/migrations/041_idempotency_records.sql
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def derive_idempotency_key(
    *,
    workflow_id: str,
    node_id: str,
    run_id: str | UUID,
    input_data: dict[str, Any] | None = None,
) -> str:
    """Deterministic SHA-256 of (workflow_id, node_id, run_id, sorted(input)).

    Same inputs → same key forever. Used by Action Runtime to:
      1. Look up idempotency_records BEFORE firing a side effect.
      2. INSERT the record AFTER the side effect succeeds.
    A retry of the same node-in-run hits the cache and returns the
    prior result — the side effect never fires twice.

    Why sorted-keys JSON instead of repr(): dict ordering in Python is
    insertion-ordered (3.7+) but caller might build the dict in
    different orders across retries. sort_keys=True makes that drift
    invisible to the hash.

    Args:
        workflow_id: stable workflow identifier (e.g. 'churn-detect')
        node_id: stable node identifier within the workflow
                 (e.g. 'send-zalo-alert')
        run_id: UUID of the workflow_run instance
        input_data: dict of inputs to the node — anything semantically
                    different per call (entity_id, computed payload).
                    Pass None or {} for nodes with no per-call input.

    Returns:
        64-char SHA-256 hex digest. Stable across processes, hosts,
        Python versions.
    """
    if isinstance(run_id, UUID):
        run_id_str = str(run_id)
    else:
        run_id_str = str(UUID(run_id))  # validates + canonicalises

    payload = {
        "workflow_id": workflow_id,
        "node_id": node_id,
        "run_id": run_id_str,
        "input": input_data or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
