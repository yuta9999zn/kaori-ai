"""
PM-PII-009 (P1-S7) — common event log + variant types for Process Mining.

Mirrors the NormalizedEvent contract from
services/data-pipeline/ingestion/base.py. We re-declare here (not import)
because the two services are separate process boundaries Phase 2 — they
share the SHAPE not the class. A schema change to one MUST land in both
files (sentinel test in test_process_mining.py guards drift).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Event:
    """One observable event in a tenant's operational log.

    Mirror of services/data-pipeline/ingestion/base.NormalizedEvent —
    the data-pipeline writes these to Bronze; Process Mining reads them
    back from the bronze parquet via a session-scoped EventLog wrapper.
    """
    tenant_id: UUID
    event_id: str
    source: str
    event_type: str
    occurred_at: datetime
    actor: str | None = None
    case_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventLog:
    """Session-scoped slice of events for a single mining run.

    Wraps a list of Event instances + the tenant_id and time window
    that scope them. Frozen so accidental mutation in a downstream
    miner can't drift the input.

    PM-PII-012 — every event in the log MUST carry the same tenant_id
    matching the EventLog's tenant_id. Constructor enforces.
    """
    tenant_id: UUID
    events: tuple[Event, ...]
    window_start: datetime | None = None
    window_end: datetime | None = None

    def __post_init__(self) -> None:
        for ev in self.events:
            if ev.tenant_id != self.tenant_id:
                raise ValueError(
                    f"PM-PII-012: event {ev.event_id} carries tenant_id "
                    f"{ev.tenant_id} but EventLog scoped to {self.tenant_id}. "
                    "Tenant isolation breach — refusing to mine."
                )


@dataclass(frozen=True)
class ProcessVariant:
    """One discovered variant of a process — a path through event types
    that ``frequency`` cases followed.

    Output of variants.extract_variants() (PM-ALG-018). Multiple
    variants per workflow → main path + alternates ranked by frequency.
    """
    sequence: tuple[str, ...]   # event_type names in order
    case_count: int             # how many cases followed this path
    frequency_pct: float        # case_count / total cases (0.0-1.0)
    avg_duration_seconds: float | None = None  # PM-ALG-019
