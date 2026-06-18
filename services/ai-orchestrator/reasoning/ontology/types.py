"""Pydantic shapes for the 7 ontology primitives + their relations.

All 7 primitives share a `node_id` (UUID) + `tenant_id` + `kind`
discriminator so the store can dispatch by type without a class
hierarchy on the wire.

Field naming follows PIPELINE_UNIFIED.md §5.1 graph schema. Where the
Cypher uses :Label syntax, the Pydantic shape uses `kind` + sub-type
(e.g. Entity.entity_type='Customer' mirrors the Cypher
`(:Entity:Customer)` multi-label).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ─── Base ───────────────────────────────────────────────────────────


class _PrimitiveBase(BaseModel):
    """Common fields every primitive carries.

    `node_id` is the only thing relations point at; `tenant_id` enforces
    K-1 at every query path."""
    node_id:    UUID            = Field(default_factory=uuid4)
    tenant_id:  UUID
    created_at: datetime        = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata:   dict[str, Any]  = Field(default_factory=dict)


# ─── 7 Primitives ───────────────────────────────────────────────────


class Entity(_PrimitiveBase):
    """Anything with persistent identity over time — customer, product,
    store, employee, … Sub-type via `entity_type` field."""
    kind:          Literal["entity"] = "entity"
    entity_type:   str               = Field(..., max_length=32)   # Customer / Product / Store / ...
    external_id:   Optional[str]     = Field(default=None, max_length=200)
    name_masked:   Optional[str]     = Field(default=None, max_length=200)   # K-5 — masked PII


class Event(_PrimitiveBase):
    """A timestamped occurrence. Purchase, Complaint, Login, …"""
    kind:        Literal["event"] = "event"
    event_type:  str              = Field(..., max_length=32)
    occurred_at: datetime
    payload:     dict[str, Any]   = Field(default_factory=dict)


class Decision(_PrimitiveBase):
    """An AI or human decision. Carries provenance via Relations:
        (:Decision)-[:BASED_ON]->(:Entity)
        (:Decision)-[:USED_FEATURE]->(:Feature)
        (:Decision)-[:PRODUCED_BY]->(:Model)
    """
    kind:           Literal["decision"] = "decision"
    decision_type:  str                 = Field(..., max_length=64)
    chosen_value:   str                 = Field(..., max_length=200)
    confidence:     float               = Field(..., ge=0.0, le=1.0)
    actor:          str                 = Field(..., max_length=64)   # 'ai' / 'user:<id>' / 'system'


class Insight(_PrimitiveBase):
    """Narrative derived from decisions; surfaced on dashboards.
    Cypher:
        (:Insight)-[:DERIVED_FROM]->(:Decision)
        (:Insight)-[:CITES]->(:Entity)
    """
    kind:        Literal["insight"] = "insight"
    title:       str                = Field(..., max_length=200)
    body:        str                = Field(..., max_length=4000)
    severity:    str                = Field(default="info", max_length=16)   # info / warning / critical


class Action(_PrimitiveBase):
    """Concrete step triggered by an insight. Sub-type via `action_type`.
    Cypher:
        (:Action)-[:TRIGGERED_BY]->(:Insight)
        (:Action)-[:AFFECTED]->(:Entity)
    """
    kind:         Literal["action"] = "action"
    action_type:  str               = Field(..., max_length=32)   # send_email / create_ticket / ...
    status:       str               = Field(default="pending", max_length=16)
    executed_at:  Optional[datetime] = None


class Outcome(_PrimitiveBase):
    """Measured effect of an action.
    Cypher:
        (:Outcome)-[:ATTRIBUTED_TO]->(:Action)
        (:Outcome)-[:MEASURED_ON]->(:Entity)
    """
    kind:                 Literal["outcome"] = "outcome"
    metric_name:          str                = Field(..., max_length=64)
    value:                float
    baseline:             Optional[float]    = None
    attributed_revenue:   Optional[float]    = None
    measured_at:          datetime           = Field(default_factory=lambda: datetime.now(timezone.utc))


class Relation(_PrimitiveBase):
    """Typed edge between two primitives. The 7th primitive — relations
    are first-class citizens, not implicit join keys.

    `from_id` and `to_id` reference Entity / Event / Decision / ... node_ids.
    `relation_type` is the Cypher edge label (BOUGHT / VISITED / SERVED /
    DERIVED_FROM / TRIGGERED_BY / ATTRIBUTED_TO / ...).
    """
    kind:          Literal["relation"] = "relation"
    relation_type: str                 = Field(..., max_length=32)
    from_id:       UUID
    to_id:         UUID
    properties:    dict[str, Any]      = Field(default_factory=dict)


Primitive = Union[Entity, Event, Decision, Insight, Action, Outcome, Relation]
