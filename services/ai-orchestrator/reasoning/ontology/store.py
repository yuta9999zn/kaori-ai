"""OntologyStore — abstract base for the 7-primitive graph store.

Backends (in this commit and future):
  in_memory.py   — InMemoryOntologyStore (this commit)
  neo4j.py       — Neo4jOntologyStore (Phase 2)
  postgres.py    — PostgresOntologyStore over JSONB (alternate; Phase 2)

Every method takes `tenant_id` as the FIRST arg so the K-1 filter is
mechanical at the call site — no hidden context vars, no thread-local
gotchas. Implementations must enforce the filter inside the method.
"""
from __future__ import annotations

import abc
from typing import Optional
from uuid import UUID

from .types import (
    Action,
    Decision,
    Entity,
    Event,
    Insight,
    Outcome,
    Primitive,
    Relation,
)


class OntologyStore(abc.ABC):
    """Abstract typed graph store. Implementations enforce tenant_id
    isolation on every read + write."""

    # ─── Write ────────────────────────────────────────────────────

    @abc.abstractmethod
    async def add_entity(self, tenant_id: UUID, entity: Entity) -> Entity: ...

    @abc.abstractmethod
    async def add_event(self, tenant_id: UUID, event: Event) -> Event: ...

    @abc.abstractmethod
    async def add_decision(self, tenant_id: UUID, decision: Decision) -> Decision: ...

    @abc.abstractmethod
    async def add_insight(self, tenant_id: UUID, insight: Insight) -> Insight: ...

    @abc.abstractmethod
    async def add_action(self, tenant_id: UUID, action: Action) -> Action: ...

    @abc.abstractmethod
    async def add_outcome(self, tenant_id: UUID, outcome: Outcome) -> Outcome: ...

    @abc.abstractmethod
    async def add_relation(self, tenant_id: UUID, relation: Relation) -> Relation: ...

    # ─── Read ─────────────────────────────────────────────────────

    @abc.abstractmethod
    async def get(self, tenant_id: UUID, node_id: UUID) -> Optional[Primitive]:
        """Fetch any primitive by id. Returns None when not found OR
        when found-but-different-tenant (the same code path — never
        leak existence to a non-owning tenant)."""
        ...

    @abc.abstractmethod
    async def neighbours(
        self, tenant_id: UUID, node_id: UUID, *,
        relation_type: Optional[str] = None,
        direction: str = "out",   # "out" | "in" | "both"
    ) -> list[Primitive]:
        """Walk one hop from `node_id`. `relation_type=None` returns
        all relation kinds. Always tenant-filtered."""
        ...

    @abc.abstractmethod
    async def find_by_external_id(
        self, tenant_id: UUID, *,
        entity_type: str, external_id: str,
    ) -> Optional[Entity]:
        """Master-record lookup helper: find a Customer with
        external_id='KV12345' under this tenant."""
        ...

    @abc.abstractmethod
    async def decision_provenance(
        self, tenant_id: UUID, decision_id: UUID,
    ) -> dict[str, list[Primitive]]:
        """K-6 audit helper: return all entities BASED_ON, features
        USED_FEATURE'd, model PRODUCED_BY for a Decision. Returned dict
        is keyed by relation_type → list[neighbour]."""
        ...

    # ─── Maintenance ──────────────────────────────────────────────

    @abc.abstractmethod
    async def forget_tenant(self, tenant_id: UUID) -> int:
        """GDPR right-to-erasure entry point. Removes ALL primitives
        for the tenant; returns count of rows wiped. Caller is
        responsible for audit logging the action."""
        ...
