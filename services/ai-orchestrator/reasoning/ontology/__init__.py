"""
Stage 5 — 7-Primitives Ontology (Semantic Enrichment).

Per docs/strategic/PIPELINE_UNIFIED.md §5.1. The "knowledge graph" tier
of the Reasoning Layer — turns raw Bronze/Silver rows into typed
entities + events + relations + decision provenance.

7 Primitives:
  1. Entity   — Customer, Product, Transaction, Store, Employee, ...
  2. Event    — Purchase, Complaint, Login, ... (timestamped occurrence)
  3. Relation — typed edge between two primitives (BOUGHT, VISITED, ...)
  4. Decision — AI-or-human decision row with provenance
  5. Insight  — narrative derived from one or more decisions
  6. Action   — concrete step triggered by an insight
  7. Outcome  — measured effect of an action on an entity

This module ships:
  - Pydantic shapes for the 7 primitives + relations (types.py)
  - OntologyStore ABC (store.py)
  - InMemoryOntologyStore impl (in_memory.py) — production-correct
    for single-process use, no concurrent writers (good enough for
    Phase 1.5 tests + Pilot demo); Phase 2 Neo4j adapter lands as
    sibling class.

Out of scope of this commit (defer):
  - Real Neo4j cluster wiring (sibling adapter Phase 2)
  - Cross-tenant relation queries (L4b shared knowledge — review process)
  - Cypher-style query language (Phase 2; this commit ships a typed
    Python query API only)
  - Persistence to disk (in-memory only)

K-1 compliance: every Entity/Event/Decision/... carries tenant_id;
InMemoryOntologyStore.query filters by tenant_id on every access.
"""
from __future__ import annotations

from .in_memory import InMemoryOntologyStore
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

# Neo4j adapter is import-on-demand — neo4j driver is not a hard dep
# for every consumer (in-memory backend works without it). Tests +
# production callers explicitly `from .neo4j_store import …`.

__all__ = [
    "Action",
    "Decision",
    "Entity",
    "Event",
    "InMemoryOntologyStore",
    "Insight",
    "OntologyStore",
    "Outcome",
    "Primitive",
    "Relation",
]
