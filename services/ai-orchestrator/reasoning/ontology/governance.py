"""
Ontology governance — P2.2 lifecycle FSM + P2.3 edge taxonomy.

Closes anh's §4 concerns about Neo4j ontology research-project risk.

Two responsibilities:

  1. validate_lifecycle_transition() — gate customer/asset state moves
     against the lifecycle_state_transitions table (mig 096). Refuses
     `churned → lead` unless a registered recovery transition with
     `is_recovery=TRUE` matches.

  2. validate_edge_type() — gate ontology edge inserts against the
     ontology_edge_types table (mig 096). Refuses free-form edges
     introduced by AI nodes (extract_entities, etc.) before they land
     in the graph.

Pattern: validate-first. The Neo4j adapter (reasoning/ontology/
neo4j_store.py) and any service that UPDATEs lifecycle_state column
imports these functions + calls before write.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


# ─── Exceptions ──────────────────────────────────────────────────


class LifecycleTransitionDenied(Exception):
    """Raised when a (entity_type, from_state, to_state) tuple isn't
    in lifecycle_state_transitions OR a recovery transition is attempted
    without the required event/role."""

    def __init__(
        self,
        entity_type:  str,
        from_state:   str,
        to_state:     str,
        reason:       str,
    ):
        super().__init__(
            f"Lifecycle transition denied: {entity_type} "
            f"{from_state!r} → {to_state!r}. Reason: {reason}"
        )
        self.entity_type = entity_type
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason


class EdgeTypeNotAllowed(Exception):
    """Raised when an edge insert references an edge_type_key not in
    ontology_edge_types (or one whose deprecated_at is set)."""

    def __init__(self, edge_type_key: str, reason: str):
        super().__init__(
            f"Edge type {edge_type_key!r} not allowed: {reason}"
        )
        self.edge_type_key = edge_type_key
        self.reason = reason


# ─── Lifecycle FSM ───────────────────────────────────────────────


@dataclass(frozen=True)
class LifecycleRule:
    entity_type:    str
    from_state:     str
    to_state:       str
    requires_event: Optional[str]
    requires_role:  Optional[str]
    is_recovery:    bool
    description:    str


async def load_lifecycle_rules(enterprise_id: UUID) -> list[LifecycleRule]:
    """Read mig-096 seed. Called by validate_lifecycle_transition
    transparently — exposed for admin tools that want to display the
    full graph."""
    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT entity_type, from_state, to_state, requires_event, "
            "       requires_role, is_recovery, description "
            "FROM lifecycle_state_transitions"
        )
    return [LifecycleRule(**dict(r)) for r in rows]


async def validate_lifecycle_transition(
    *,
    enterprise_id:  UUID,
    entity_type:    str,
    from_state:     str,
    to_state:       str,
    event_name:     Optional[str] = None,
    actor_role:     Optional[str] = None,
) -> LifecycleRule:
    """Find the matching transition rule + enforce its prereqs.

    Returns the matched LifecycleRule on success. Raises
    LifecycleTransitionDenied otherwise.

    Idempotency: same `from_state == to_state` returns a synthetic rule
    without DB lookup (caller's UPDATE will no-op).
    """
    if from_state == to_state:
        return LifecycleRule(
            entity_type=entity_type, from_state=from_state, to_state=to_state,
            requires_event=None, requires_role=None,
            is_recovery=False, description="idempotent no-op",
        )

    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT entity_type, from_state, to_state, requires_event,
                      requires_role, is_recovery, description
               FROM lifecycle_state_transitions
               WHERE entity_type = $1 AND from_state = $2 AND to_state = $3""",
            entity_type, from_state, to_state,
        )

    if row is None:
        raise LifecycleTransitionDenied(
            entity_type, from_state, to_state,
            reason="no matching rule in lifecycle_state_transitions",
        )

    rule = LifecycleRule(**dict(row))

    if rule.requires_event and event_name != rule.requires_event:
        raise LifecycleTransitionDenied(
            entity_type, from_state, to_state,
            reason=(
                f"transition requires event {rule.requires_event!r} "
                f"(caller passed {event_name!r})"
            ),
        )

    if rule.requires_role and actor_role != rule.requires_role:
        raise LifecycleTransitionDenied(
            entity_type, from_state, to_state,
            reason=(
                f"transition requires role {rule.requires_role!r} "
                f"(caller has {actor_role!r})"
            ),
        )

    log.debug("lifecycle.transition_validated",
                entity_type=entity_type, from_state=from_state,
                to_state=to_state, recovery=rule.is_recovery)
    return rule


# ─── Edge taxonomy ───────────────────────────────────────────────


@dataclass(frozen=True)
class EdgeTypeSpec:
    edge_type_key:    str
    source_primitive: str
    target_primitive: str
    cardinality:      str
    retention_days:   int
    governance_owner: str
    deprecated:       bool


# Module-level cache — edge types are platform config, change rarely;
# cache for the lifetime of the process + admin can force-refresh by
# restarting the service.
_EDGE_CACHE: Optional[dict[str, EdgeTypeSpec]] = None


async def load_edge_types(enterprise_id: UUID) -> dict[str, EdgeTypeSpec]:
    """Read mig-096 edge type registry. Cached after first call."""
    global _EDGE_CACHE
    if _EDGE_CACHE is not None:
        return _EDGE_CACHE

    from ai_orchestrator.shared.db import acquire_for_tenant

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch(
            "SELECT edge_type_key, source_primitive, target_primitive, "
            "       cardinality, retention_days, governance_owner, "
            "       deprecated_at "
            "FROM ontology_edge_types"
        )

    cache: dict[str, EdgeTypeSpec] = {}
    for r in rows:
        cache[r["edge_type_key"]] = EdgeTypeSpec(
            edge_type_key=r["edge_type_key"],
            source_primitive=r["source_primitive"],
            target_primitive=r["target_primitive"],
            cardinality=r["cardinality"],
            retention_days=r["retention_days"],
            governance_owner=r["governance_owner"],
            deprecated=r["deprecated_at"] is not None,
        )
    _EDGE_CACHE = cache
    return cache


def reset_edge_cache() -> None:
    """Test hook / admin force-reload after a manual mig 096 update."""
    global _EDGE_CACHE
    _EDGE_CACHE = None


async def validate_edge_type(
    *,
    enterprise_id:    UUID,
    edge_type_key:    str,
    source_primitive: str,
    target_primitive: str,
) -> EdgeTypeSpec:
    """Check (edge_type_key, source_primitive, target_primitive) is in
    the registry + not deprecated. Returns the matched spec on success.
    """
    if not isinstance(edge_type_key, str) or not edge_type_key:
        raise EdgeTypeNotAllowed(str(edge_type_key), reason="empty key")

    cache = await load_edge_types(enterprise_id)
    spec = cache.get(edge_type_key)
    if spec is None:
        raise EdgeTypeNotAllowed(
            edge_type_key,
            reason="not in ontology_edge_types registry (free-form edge blocked)",
        )
    if spec.deprecated:
        raise EdgeTypeNotAllowed(
            edge_type_key,
            reason="edge type marked deprecated",
        )
    if spec.source_primitive != source_primitive:
        raise EdgeTypeNotAllowed(
            edge_type_key,
            reason=(
                f"source primitive mismatch — registry says "
                f"{spec.source_primitive!r} but caller passed {source_primitive!r}"
            ),
        )
    if spec.target_primitive != target_primitive:
        raise EdgeTypeNotAllowed(
            edge_type_key,
            reason=(
                f"target primitive mismatch — registry says "
                f"{spec.target_primitive!r} but caller passed {target_primitive!r}"
            ),
        )
    return spec


def is_recovery_required(from_state: str, to_state: str) -> bool:
    """Pure helper for the ontology FSM concern — does this transition
    REQUIRE a recovery rule?

    True when the from_state is in the terminal-ish set (churned,
    archived, cancelled) — these are NOT supposed to flip back without
    an explicit recovery rule. The validator enforces via DB lookup;
    this helper is for caller's pre-check + UI rendering.
    """
    return from_state in ("churned", "archived", "cancelled", "expired")
