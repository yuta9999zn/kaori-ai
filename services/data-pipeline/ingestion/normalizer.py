"""
Event normalization helpers (PM-PII-009 placeholder).

Phase 1 v4 ships a thin contract for converting source-specific records
to :class:`base.NormalizedEvent`. Each connector calls these helpers
inside its ``extract_events`` so the normalization logic stays out of
the connector body (testable in isolation).

Phase 1.5 / P1-S7 (Process Mining) fleshes this out with:
  * timestamp parsing across regional formats
  * actor identifier normalization (email lowercasing, phone formatting)
  * deterministic event_id derivation from (source, raw_id)
  * case_id inference heuristics
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from .base import NormalizedEvent


def derive_event_id(source: str, raw_id: str) -> str:
    """Stable, deterministic event_id for idempotency + Kafka message key.

    Same (source, raw_id) always yields the same event_id, so a connector
    re-running over the same source data produces identical events the
    consumer can dedupe on.

    Formula: SHA-256(source || ':' || raw_id), hex-encoded, prefixed
    with the source name so log lines remain greppable by source.
    """
    h = hashlib.sha256(f"{source}:{raw_id}".encode("utf-8")).hexdigest()
    return f"{source}:{h[:32]}"


def build_event(
    *,
    tenant_id: UUID,
    source: str,
    raw_id: str,
    event_type: str,
    occurred_at: datetime,
    actor: str | None = None,
    case_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> NormalizedEvent:
    """Convenience constructor — wraps :func:`derive_event_id` so
    connectors don't repeat the boilerplate."""
    return NormalizedEvent(
        tenant_id=tenant_id,
        event_id=derive_event_id(source, raw_id),
        source=source,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        case_id=case_id,
        payload=payload or {},
    )
