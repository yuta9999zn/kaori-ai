"""
Neo4jOntologyStore — production-grade adapter for Stage 5 ontology.

Drop-in replacement for InMemoryOntologyStore. Same OntologyStore ABC;
caller swaps at app construction. The Cypher schema mirrors
PIPELINE_UNIFIED.md §5.1 — primitives are graph nodes with multi-label
(:Entity:Customer + per-tenant label), relations are typed edges.

Tenant isolation pattern (per §7.7 L4a — Neo4j tenant per label):
  Every node carries a per-tenant label `_T_<short_hash>` in addition
  to its kind/type labels. Reads MATCH on that label so cross-tenant
  reads are physically impossible at the storage level. Writes MERGE
  with the label baked in.

Why a hash, not the raw UUID:
  Neo4j label names must be alphanumeric + underscore; UUIDs contain
  dashes. A 16-char SHA-256 prefix gives 64 bits of namespace — more
  than enough for hundreds of tenants with no collision concern.

Out of scope (defer)
--------------------
- Cypher query language exposure (typed Python API only; same as
  in-memory backend)
- L4b shared cross-tenant ontology (review-gated content; Phase 2+)
- Real APOC procedures for complex traversals (Phase 2+)
- Authentication via Kubernetes secrets (uses env-var URL + auth
  for now; Vault wiring lands when K8s does per ADR-0016)
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional
from uuid import UUID

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase

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

log = structlog.get_logger()


NEO4J_URL  = os.getenv("NEO4J_URL",  "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "neo4j_dev_password")


def _tenant_label(tenant_id: UUID) -> str:
    """Per-tenant Cypher label. Neo4j labels are alphanumeric + _ only,
    so we hash the UUID to a short stable token."""
    h = hashlib.sha256(str(tenant_id).encode()).hexdigest()[:16]
    return f"_T_{h}"


# Map kind discriminator → Cypher type label (mirrors §5.1).
_KIND_LABEL = {
    "entity":   "Entity",
    "event":    "Event",
    "decision": "Decision",
    "insight":  "Insight",
    "action":   "Action",
    "outcome":  "Outcome",
    "relation": "Relation",   # Relation is also a node in our model (the 7th primitive)
}


class Neo4jOntologyStore(OntologyStore):
    """Neo4j adapter. Accepts an injected `driver` so tests can pass
    a mock. Production callers build the driver from the NEO4J_* env."""

    def __init__(self, *, driver: AsyncDriver):
        self._driver = driver

    @classmethod
    def from_env(cls) -> "Neo4jOntologyStore":
        driver = AsyncGraphDatabase.driver(
            NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASS),
        )
        return cls(driver=driver)

    async def close(self) -> None:
        await self._driver.close()

    # ─── Write helpers ────────────────────────────────────────────

    def _prim_props(self, p: Primitive) -> dict[str, Any]:
        """Serialize a primitive to a flat property map Cypher accepts."""
        base = {
            "node_id":    str(p.node_id),
            "tenant_id":  str(p.tenant_id),
            "kind":       p.kind,
            "created_at": p.created_at.isoformat(),
            "metadata":   json.dumps(p.metadata, ensure_ascii=False),
        }
        # Per-kind extra props.
        if isinstance(p, Entity):
            base["entity_type"] = p.entity_type
            if p.external_id: base["external_id"] = p.external_id
            if p.name_masked: base["name_masked"] = p.name_masked
        elif isinstance(p, Event):
            base["event_type"]  = p.event_type
            base["occurred_at"] = p.occurred_at.isoformat()
            base["payload"]     = json.dumps(p.payload, ensure_ascii=False)
        elif isinstance(p, Decision):
            base["decision_type"] = p.decision_type
            base["chosen_value"]  = p.chosen_value
            base["confidence"]    = float(p.confidence)
            base["actor"]         = p.actor
        elif isinstance(p, Insight):
            base["title"]    = p.title
            base["body"]     = p.body
            base["severity"] = p.severity
        elif isinstance(p, Action):
            base["action_type"] = p.action_type
            base["status"]      = p.status
            if p.executed_at: base["executed_at"] = p.executed_at.isoformat()
        elif isinstance(p, Outcome):
            base["metric_name"]        = p.metric_name
            base["value"]              = float(p.value)
            if p.baseline is not None:           base["baseline"] = float(p.baseline)
            if p.attributed_revenue is not None: base["attributed_revenue"] = float(p.attributed_revenue)
            base["measured_at"] = p.measured_at.isoformat()
        elif isinstance(p, Relation):
            base["relation_type"] = p.relation_type
            base["from_id"]       = str(p.from_id)
            base["to_id"]         = str(p.to_id)
            base["properties"]    = json.dumps(p.properties, ensure_ascii=False)
        return base

    async def _merge_node(self, tenant_id: UUID, p: Primitive) -> None:
        if p.tenant_id != tenant_id:
            raise ValueError(
                f"cross-tenant write rejected: prim.tenant_id={p.tenant_id} "
                f"!= argument tenant_id={tenant_id}"
            )
        labels = f"{_KIND_LABEL[p.kind]}:{_tenant_label(tenant_id)}"
        cypher = (
            f"MERGE (n:{labels} {{node_id: $props.node_id}}) "
            "SET n += $props"
        )
        async with self._driver.session() as session:
            await session.run(cypher, props=self._prim_props(p))

    async def add_entity(self, tenant_id: UUID, entity: Entity) -> Entity:
        await self._merge_node(tenant_id, entity)
        return entity

    async def add_event(self, tenant_id: UUID, event: Event) -> Event:
        await self._merge_node(tenant_id, event)
        return event

    async def add_decision(self, tenant_id: UUID, decision: Decision) -> Decision:
        await self._merge_node(tenant_id, decision)
        return decision

    async def add_insight(self, tenant_id: UUID, insight: Insight) -> Insight:
        await self._merge_node(tenant_id, insight)
        return insight

    async def add_action(self, tenant_id: UUID, action: Action) -> Action:
        await self._merge_node(tenant_id, action)
        return action

    async def add_outcome(self, tenant_id: UUID, outcome: Outcome) -> Outcome:
        await self._merge_node(tenant_id, outcome)
        return outcome

    async def add_relation(self, tenant_id: UUID, relation: Relation) -> Relation:
        if relation.tenant_id != tenant_id:
            raise ValueError("cross-tenant relation rejected")
        tlabel = _tenant_label(tenant_id)
        # Verify both endpoints belong to this tenant (label MATCH).
        async with self._driver.session() as session:
            check = await session.run(
                f"MATCH (a:{tlabel} {{node_id: $a}}), (b:{tlabel} {{node_id: $b}}) "
                "RETURN a.node_id AS aid, b.node_id AS bid",
                a=str(relation.from_id), b=str(relation.to_id),
            )
            row = await check.single()
            if row is None:
                raise KeyError(
                    f"relation endpoints not found for tenant {tenant_id}: "
                    f"from={relation.from_id} to={relation.to_id}"
                )
            # Store relation as both a node (the 7th primitive) AND a
            # Cypher edge for traversal. Edge type = the relation_type
            # so Cypher MATCH (a)-[:BOUGHT]->(b) works directly.
            rel_type = relation.relation_type.upper().replace(" ", "_")
            await session.run(
                f"MATCH (a:{tlabel} {{node_id: $a}}), (b:{tlabel} {{node_id: $b}}) "
                f"MERGE (a)-[r:{rel_type} {{node_id: $rid}}]->(b) "
                "SET r += $props",
                a=str(relation.from_id), b=str(relation.to_id),
                rid=str(relation.node_id),
                props={
                    "relation_node_id": str(relation.node_id),
                    "tenant_id":        str(tenant_id),
                    "properties":       json.dumps(relation.properties, ensure_ascii=False),
                },
            )
        # Also store the relation as a node for primitive-style get/forget.
        await self._merge_node(tenant_id, relation)
        return relation

    # ─── Read ─────────────────────────────────────────────────────

    async def get(self, tenant_id: UUID, node_id: UUID) -> Optional[Primitive]:
        tlabel = _tenant_label(tenant_id)
        async with self._driver.session() as session:
            result = await session.run(
                f"MATCH (n:{tlabel} {{node_id: $node_id}}) RETURN n LIMIT 1",
                node_id=str(node_id),
            )
            row = await result.single()
        if row is None:
            return None
        n = dict(row["n"])
        return _props_to_prim(n)

    async def neighbours(
        self, tenant_id: UUID, node_id: UUID, *,
        relation_type: Optional[str] = None,
        direction: str = "out",
    ) -> list[Primitive]:
        if direction not in ("out", "in", "both"):
            raise ValueError(f"direction must be one of out/in/both; got {direction!r}")
        tlabel = _tenant_label(tenant_id)
        rel_filter = f":{relation_type.upper()}" if relation_type else ""
        if direction == "out":
            pattern = f"-[{rel_filter}]->"
        elif direction == "in":
            pattern = f"<-[{rel_filter}]-"
        else:
            pattern = f"-[{rel_filter}]-"
        cypher = (
            f"MATCH (n:{tlabel} {{node_id: $node_id}}){pattern}(m:{tlabel}) "
            "RETURN DISTINCT m"
        )
        async with self._driver.session() as session:
            result = await session.run(cypher, node_id=str(node_id))
            rows = [r async for r in result]
        return [_props_to_prim(dict(r["m"])) for r in rows]

    async def find_by_external_id(
        self, tenant_id: UUID, *,
        entity_type: str, external_id: str,
    ) -> Optional[Entity]:
        tlabel = _tenant_label(tenant_id)
        async with self._driver.session() as session:
            result = await session.run(
                f"MATCH (n:Entity:{tlabel} {{entity_type: $et, external_id: $ex}}) "
                "RETURN n LIMIT 1",
                et=entity_type, ex=external_id,
            )
            row = await result.single()
        if row is None:
            return None
        prim = _props_to_prim(dict(row["n"]))
        return prim if isinstance(prim, Entity) else None

    async def decision_provenance(
        self, tenant_id: UUID, decision_id: UUID,
    ) -> dict[str, list[Primitive]]:
        tlabel = _tenant_label(tenant_id)
        async with self._driver.session() as session:
            result = await session.run(
                f"MATCH (d:Decision:{tlabel} {{node_id: $did}})-[r]->(m:{tlabel}) "
                "RETURN type(r) AS rtype, m",
                did=str(decision_id),
            )
            rows = [r async for r in result]
        out: dict[str, list[Primitive]] = {}
        for r in rows:
            out.setdefault(r["rtype"], []).append(_props_to_prim(dict(r["m"])))
        return out

    # ─── Maintenance ──────────────────────────────────────────────

    async def forget_tenant(self, tenant_id: UUID) -> int:
        tlabel = _tenant_label(tenant_id)
        async with self._driver.session() as session:
            result = await session.run(
                f"MATCH (n:{tlabel}) DETACH DELETE n RETURN COUNT(*) AS c",
            )
            row = await result.single()
        return int(row["c"]) if row else 0


# ─── Deserialisation ───────────────────────────────────────────────


def _props_to_prim(props: dict) -> Primitive:
    """Cypher row → Pydantic primitive."""
    from datetime import datetime

    kind = props.get("kind") or "entity"
    common = {
        "node_id":    UUID(props["node_id"]),
        "tenant_id":  UUID(props["tenant_id"]),
        "created_at": datetime.fromisoformat(props["created_at"]),
        "metadata":   json.loads(props.get("metadata") or "{}"),
    }
    if kind == "entity":
        return Entity(**common, entity_type=props.get("entity_type", "Unknown"),
                       external_id=props.get("external_id"),
                       name_masked=props.get("name_masked"))
    if kind == "event":
        return Event(**common, event_type=props.get("event_type", "Unknown"),
                      occurred_at=datetime.fromisoformat(props["occurred_at"]),
                      payload=json.loads(props.get("payload") or "{}"))
    if kind == "decision":
        return Decision(**common, decision_type=props["decision_type"],
                         chosen_value=props["chosen_value"],
                         confidence=float(props["confidence"]),
                         actor=props["actor"])
    if kind == "insight":
        return Insight(**common, title=props["title"], body=props["body"],
                        severity=props.get("severity", "info"))
    if kind == "action":
        action = Action(**common, action_type=props["action_type"],
                         status=props.get("status", "pending"))
        if props.get("executed_at"):
            action = Action(**{**common,
                                 "action_type": props["action_type"],
                                 "status": props.get("status", "pending"),
                                 "executed_at": datetime.fromisoformat(props["executed_at"])})
        return action
    if kind == "outcome":
        return Outcome(**common, metric_name=props["metric_name"],
                        value=float(props["value"]),
                        baseline=float(props["baseline"]) if "baseline" in props else None,
                        attributed_revenue=float(props["attributed_revenue"])
                                            if "attributed_revenue" in props else None,
                        measured_at=datetime.fromisoformat(props["measured_at"]))
    if kind == "relation":
        return Relation(**common, relation_type=props["relation_type"],
                         from_id=UUID(props["from_id"]),
                         to_id=UUID(props["to_id"]),
                         properties=json.loads(props.get("properties") or "{}"))
    raise ValueError(f"Unknown kind: {kind!r}")
