"""
Connector base contract — every ingestion source extends this.

Phase 1 v4 (Sprint P1-S3): contract surface only. Concrete connectors
raise NotImplementedError until Sprint P1-S7 (Process Mining v1) ships
the real extraction logic.

Why a class instead of a function: connectors hold connection state
(DB connection pool, OAuth refresh tokens, file watchers) that need
explicit lifecycle. The Connector abstract class formalises start/stop/
extract — same shape as Spring's CommandLineRunner or Temporal's
ActivityImpl.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional
from uuid import UUID


@dataclass(frozen=True)
class NormalizedEvent:
    """The common event-log schema all connectors emit (PM-PII-009).

    Process Mining + adoption signal extractors consume this shape from
    Kafka. Adding a field is allowed (additive); renaming or removing
    requires a contract version bump (Phase 2 schema registry).

    Fields:
      tenant_id  — required; sourced from the connector config, not from
                   the event payload (K-1, K-12).
      event_id   — globally unique, deterministic per (source, raw_id);
                   used as Kafka message key + idempotency key.
      source     — connector identifier ('postgres_cdc' / 'excel_filesystem' / ...).
      event_type — semantic event name ('order.created', 'task.assigned').
      occurred_at— when the source recorded it (NOT when we ingested).
      actor      — natural-key actor ref (NOT system user_id; can be email,
                   employee_code, etc. — PII-aware downstream).
      case_id    — optional case grouping (Process Mining sequence
                   reconstruction). Often inferred not given.
      payload    — opaque dict; PII redaction happens before publish (K-5).
    """
    tenant_id: UUID
    event_id: str
    source: str
    event_type: str
    occurred_at: datetime
    actor: Optional[str] = None
    case_id: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)


class Connector(abc.ABC):
    """Abstract base for all ingestion connectors.

    Implementations live at ``ingestion/connectors/<source>/connector.py``.
    Each connector is instantiated once per (tenant, source-config) pair;
    the calling layer (P1-S7 Process Mining session runner) handles the
    fan-out + lifecycle.

    Subclasses must implement:
      * ``source``        class-level identifier (lowercase, snake_case)
      * ``extract_events`` async generator yielding ``NormalizedEvent``s

    Subclasses may override:
      * ``connect()`` / ``disconnect()`` lifecycle hooks (default no-op)
    """

    #: Lowercase source identifier — must match the connector folder name.
    source: str = ""

    def __init__(
        self,
        *,
        tenant_id: UUID,
        config: dict[str, Any],
    ) -> None:
        if not self.source:
            raise ValueError(
                f"{type(self).__name__} must declare a class-level 'source' identifier"
            )
        self.tenant_id = tenant_id
        self.config = config

    async def connect(self) -> None:
        """Open any persistent connections (DB pool, OAuth session,
        file watcher). Default: no-op for stateless connectors."""

    async def disconnect(self) -> None:
        """Close persistent connections. Default: no-op."""

    @abc.abstractmethod
    async def extract_events(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        """Yield normalized events in the [since, until) window.

        ``since`` / ``until`` are advisory — connectors that don't
        support range filtering yield everything (P1-S7 will scope
        per mining session). All emitted events MUST carry
        ``tenant_id`` matching ``self.tenant_id``.
        """
        raise NotImplementedError
        yield  # pragma: no cover — keeps async-generator typing happy
