"""In-memory OntologyStore — reference impl for Phase 1.5 tests + demo.

Single-process; not thread-safe (no concurrent writers expected at
this layer in Phase 1.5). Phase 2 Neo4j adapter lands as sibling.

Storage layout:
  _by_id    : { (tenant_id, node_id) → Primitive }
  _by_kind  : { (tenant_id, kind) → set[node_id] }
  _out      : { (tenant_id, from_id, relation_type) → set[to_id] }
  _in       : { (tenant_id, to_id,   relation_type) → set[from_id] }
  _relations: { (tenant_id, relation_id) → Relation }   for direct lookup

Indexes are kept consistent inside each add_* method — there's no
async lock because Python's GIL protects dict mutation under the
no-concurrent-writers assumption.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional
from uuid import UUID

from .store import OntologyStore
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


class InMemoryOntologyStore(OntologyStore):
    """In-memory graph store. RLS-style isolation enforced per-method."""

    def __init__(self) -> None:
        self._by_id:     dict[tuple[UUID, UUID], Primitive]                  = {}
        self._by_kind:   dict[tuple[UUID, str], set[UUID]]                   = defaultdict(set)
        self._out:       dict[tuple[UUID, UUID, str], set[UUID]]             = defaultdict(set)
        self._in:        dict[tuple[UUID, UUID, str], set[UUID]]             = defaultdict(set)
        self._relations: dict[tuple[UUID, UUID], Relation]                   = {}

    # ─── Write helpers ────────────────────────────────────────────

    def _store(self, tenant_id: UUID, prim: Primitive) -> None:
        """Defence-in-depth: refuse cross-tenant write attempts."""
        if prim.tenant_id != tenant_id:
            raise ValueError(
                f"cross-tenant write rejected: prim.tenant_id={prim.tenant_id} "
                f"!= argument tenant_id={tenant_id}"
            )
        self._by_id[(tenant_id, prim.node_id)] = prim
        self._by_kind[(tenant_id, prim.kind)].add(prim.node_id)

    async def add_entity(self, tenant_id: UUID, entity: Entity) -> Entity:
        self._store(tenant_id, entity)
        return entity

    async def add_event(self, tenant_id: UUID, event: Event) -> Event:
        self._store(tenant_id, event)
        return event

    async def add_decision(self, tenant_id: UUID, decision: Decision) -> Decision:
        self._store(tenant_id, decision)
        return decision

    async def add_insight(self, tenant_id: UUID, insight: Insight) -> Insight:
        self._store(tenant_id, insight)
        return insight

    async def add_action(self, tenant_id: UUID, action: Action) -> Action:
        self._store(tenant_id, action)
        return action

    async def add_outcome(self, tenant_id: UUID, outcome: Outcome) -> Outcome:
        self._store(tenant_id, outcome)
        return outcome

    async def add_relation(self, tenant_id: UUID, relation: Relation) -> Relation:
        # Both endpoints must exist for THIS tenant — guards against
        # dangling edges + cross-tenant pointer leaks.
        if (tenant_id, relation.from_id) not in self._by_id:
            raise KeyError(f"from_id {relation.from_id} not found for tenant {tenant_id}")
        if (tenant_id, relation.to_id) not in self._by_id:
            raise KeyError(f"to_id {relation.to_id} not found for tenant {tenant_id}")
        self._store(tenant_id, relation)
        self._relations[(tenant_id, relation.node_id)] = relation
        self._out[(tenant_id, relation.from_id, relation.relation_type)].add(relation.to_id)
        self._in[(tenant_id, relation.to_id,   relation.relation_type)].add(relation.from_id)
        return relation

    # ─── Read ─────────────────────────────────────────────────────

    async def get(self, tenant_id: UUID, node_id: UUID) -> Optional[Primitive]:
        return self._by_id.get((tenant_id, node_id))

    async def neighbours(
        self, tenant_id: UUID, node_id: UUID, *,
        relation_type: Optional[str] = None, direction: str = "out",
    ) -> list[Primitive]:
        if direction not in ("out", "in", "both"):
            raise ValueError(f"direction must be one of out/in/both; got {direction!r}")

        out_targets: set[UUID] = set()
        if direction in ("out", "both"):
            if relation_type:
                out_targets |= self._out.get((tenant_id, node_id, relation_type), set())
            else:
                for (t_id, src, _r_type), targets in self._out.items():
                    if t_id == tenant_id and src == node_id:
                        out_targets |= targets

        in_sources: set[UUID] = set()
        if direction in ("in", "both"):
            if relation_type:
                in_sources |= self._in.get((tenant_id, node_id, relation_type), set())
            else:
                for (t_id, dst, _r_type), sources in self._in.items():
                    if t_id == tenant_id and dst == node_id:
                        in_sources |= sources

        ids = out_targets | in_sources
        return [self._by_id[(tenant_id, nid)] for nid in ids
                 if (tenant_id, nid) in self._by_id]

    async def find_by_external_id(
        self, tenant_id: UUID, *, entity_type: str, external_id: str,
    ) -> Optional[Entity]:
        for nid in self._by_kind.get((tenant_id, "entity"), set()):
            prim = self._by_id[(tenant_id, nid)]
            if (isinstance(prim, Entity)
                and prim.entity_type == entity_type
                and prim.external_id == external_id):
                return prim
        return None

    async def decision_provenance(
        self, tenant_id: UUID, decision_id: UUID,
    ) -> dict[str, list[Primitive]]:
        d = await self.get(tenant_id, decision_id)
        if d is None or d.kind != "decision":
            return {}
        out: dict[str, list[Primitive]] = {}
        # All outgoing edges from this decision.
        for (t_id, src, r_type), targets in self._out.items():
            if t_id != tenant_id or src != decision_id:
                continue
            neighbours = [self._by_id[(tenant_id, tid)] for tid in targets
                           if (tenant_id, tid) in self._by_id]
            if neighbours:
                out.setdefault(r_type, []).extend(neighbours)
        return out

    # ─── Maintenance ──────────────────────────────────────────────

    async def forget_tenant(self, tenant_id: UUID) -> int:
        """GDPR — remove every primitive for `tenant_id`."""
        keys_by_id  = [k for k in self._by_id      if k[0] == tenant_id]
        keys_kind   = [k for k in self._by_kind    if k[0] == tenant_id]
        keys_out    = [k for k in self._out        if k[0] == tenant_id]
        keys_in     = [k for k in self._in         if k[0] == tenant_id]
        keys_rel    = [k for k in self._relations  if k[0] == tenant_id]
        count = len(keys_by_id)
        for k in keys_by_id:  self._by_id.pop(k, None)
        for k in keys_kind:   self._by_kind.pop(k, None)
        for k in keys_out:    self._out.pop(k, None)
        for k in keys_in:     self._in.pop(k, None)
        for k in keys_rel:    self._relations.pop(k, None)
        return count
