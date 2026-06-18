"""Stage 5 — 7-Primitives Ontology tests.

Pure Python — no Postgres, no Neo4j. Validates:
  * Each of the 7 primitives constructs + stores
  * Cross-tenant read returns None (K-1 isolation)
  * Cross-tenant write rejected (defence-in-depth)
  * Relation requires both endpoints to exist for same tenant
  * neighbours() walks all 3 directions
  * find_by_external_id locates by (entity_type, external_id)
  * decision_provenance groups by relation_type
  * forget_tenant wipes entire tenant footprint without touching others
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.ontology import (
    Action,
    Decision,
    Entity,
    Event,
    InMemoryOntologyStore,
    Insight,
    Outcome,
    Relation,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")


# ─── Construction shape ─────────────────────────────────────────────


class TestPrimitiveShapes:

    def test_entity_minimal(self):
        e = Entity(tenant_id=T1, entity_type="Customer")
        assert e.kind == "entity"
        assert e.entity_type == "Customer"
        assert e.node_id is not None

    def test_event_requires_occurred_at(self):
        with pytest.raises(Exception):
            Event(tenant_id=T1, event_type="Purchase")   # missing occurred_at

    def test_decision_confidence_bounded(self):
        with pytest.raises(Exception):
            Decision(tenant_id=T1, decision_type="approve", chosen_value="yes",
                      confidence=1.2, actor="ai")

    def test_relation_minimal(self):
        a, b = uuid4(), uuid4()
        r = Relation(tenant_id=T1, relation_type="BOUGHT", from_id=a, to_id=b)
        assert r.kind == "relation"
        assert r.relation_type == "BOUGHT"


# ─── Add + get ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_entity_then_get():
    store = InMemoryOntologyStore()
    e = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer",
                                            external_id="KV-001",
                                            name_masked="A***"))
    got = await store.get(T1, e.node_id)
    assert got is not None
    assert got.node_id == e.node_id
    assert isinstance(got, Entity)
    assert got.external_id == "KV-001"


@pytest.mark.asyncio
async def test_get_returns_none_for_wrong_tenant():
    """K-1: same node_id under T2 looks up empty when T1's record exists.
    Critical: must return None (not raise), so we don't leak existence."""
    store = InMemoryOntologyStore()
    e = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    got = await store.get(T2, e.node_id)
    assert got is None


@pytest.mark.asyncio
async def test_cross_tenant_write_rejected():
    """Defence-in-depth: if caller passes tenant_id=T1 but primitive
    .tenant_id=T2, the store rejects."""
    store = InMemoryOntologyStore()
    e = Entity(tenant_id=T2, entity_type="Customer")
    with pytest.raises(ValueError, match="cross-tenant"):
        await store.add_entity(T1, e)


# ─── Relations ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_relation_requires_both_endpoints_exist():
    store = InMemoryOntologyStore()
    e = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    other = uuid4()
    with pytest.raises(KeyError):
        await store.add_relation(T1, Relation(
            tenant_id=T1, relation_type="BOUGHT", from_id=e.node_id, to_id=other,
        ))


@pytest.mark.asyncio
async def test_relation_cross_tenant_endpoints_rejected():
    """If `to_id` belongs to T2 not T1, the relation must be rejected
    even though the relation itself carries tenant_id=T1."""
    store = InMemoryOntologyStore()
    e1 = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    e2 = await store.add_entity(T2, Entity(tenant_id=T2, entity_type="Product"))
    with pytest.raises(KeyError):
        await store.add_relation(T1, Relation(
            tenant_id=T1, relation_type="BOUGHT",
            from_id=e1.node_id, to_id=e2.node_id,
        ))


# ─── Neighbours ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_neighbours_out_in_both():
    store = InMemoryOntologyStore()
    cust = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    prod = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Product"))
    store_e = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Store"))

    await store.add_relation(T1, Relation(tenant_id=T1, relation_type="BOUGHT",
                                            from_id=cust.node_id, to_id=prod.node_id))
    await store.add_relation(T1, Relation(tenant_id=T1, relation_type="VISITED",
                                            from_id=cust.node_id, to_id=store_e.node_id))
    # Outgoing from customer
    out = await store.neighbours(T1, cust.node_id, direction="out")
    out_ids = {p.node_id for p in out}
    assert out_ids == {prod.node_id, store_e.node_id}

    # Incoming on product
    incoming = await store.neighbours(T1, prod.node_id, direction="in")
    assert {p.node_id for p in incoming} == {cust.node_id}

    # Filter by relation_type
    bought = await store.neighbours(T1, cust.node_id, relation_type="BOUGHT")
    assert {p.node_id for p in bought} == {prod.node_id}

    # Both directions
    both = await store.neighbours(T1, cust.node_id, direction="both")
    assert len(both) == 2


@pytest.mark.asyncio
async def test_neighbours_invalid_direction_raises():
    store = InMemoryOntologyStore()
    e = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    with pytest.raises(ValueError):
        await store.neighbours(T1, e.node_id, direction="sideways")


# ─── find_by_external_id ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_by_external_id():
    store = InMemoryOntologyStore()
    await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer",
                                        external_id="KV-001"))
    await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer",
                                        external_id="KV-002"))
    got = await store.find_by_external_id(T1, entity_type="Customer", external_id="KV-001")
    assert got is not None
    assert got.external_id == "KV-001"


@pytest.mark.asyncio
async def test_find_by_external_id_tenant_filtered():
    store = InMemoryOntologyStore()
    await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer", external_id="KV-001"))
    got = await store.find_by_external_id(T2, entity_type="Customer", external_id="KV-001")
    assert got is None


# ─── Decision provenance ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_provenance_groups_by_relation_type():
    store = InMemoryOntologyStore()
    cust = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    feat = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Feature",
                                                external_id="churn_score_30d"))
    dec  = await store.add_decision(T1, Decision(tenant_id=T1, decision_type="churn_risk",
                                                   chosen_value="HIGH", confidence=0.82,
                                                   actor="ai"))
    await store.add_relation(T1, Relation(tenant_id=T1, relation_type="BASED_ON",
                                            from_id=dec.node_id, to_id=cust.node_id))
    await store.add_relation(T1, Relation(tenant_id=T1, relation_type="USED_FEATURE",
                                            from_id=dec.node_id, to_id=feat.node_id))
    prov = await store.decision_provenance(T1, dec.node_id)
    assert set(prov.keys()) == {"BASED_ON", "USED_FEATURE"}
    assert prov["BASED_ON"][0].node_id == cust.node_id
    assert prov["USED_FEATURE"][0].node_id == feat.node_id


@pytest.mark.asyncio
async def test_decision_provenance_missing_decision_returns_empty():
    store = InMemoryOntologyStore()
    prov = await store.decision_provenance(T1, uuid4())
    assert prov == {}


# ─── 7 primitives — sanity round-trip ───────────────────────────────


@pytest.mark.asyncio
async def test_all_seven_primitives_store_and_retrieve():
    """Smoke: Entity / Event / Decision / Insight / Action / Outcome /
    Relation all round-trip through the store."""
    store = InMemoryOntologyStore()
    cust = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    evt  = await store.add_event(T1, Event(tenant_id=T1, event_type="Purchase",
                                              occurred_at=datetime.now(timezone.utc)))
    dec  = await store.add_decision(T1, Decision(tenant_id=T1, decision_type="approve",
                                                   chosen_value="yes", confidence=0.9,
                                                   actor="ai"))
    ins  = await store.add_insight(T1, Insight(tenant_id=T1, title="t", body="b"))
    act  = await store.add_action(T1, Action(tenant_id=T1, action_type="send_email"))
    outc = await store.add_outcome(T1, Outcome(tenant_id=T1, metric_name="opens", value=42.0))
    rel  = await store.add_relation(T1, Relation(tenant_id=T1, relation_type="TRIGGERED_BY",
                                                    from_id=act.node_id, to_id=ins.node_id))

    for prim in [cust, evt, dec, ins, act, outc, rel]:
        got = await store.get(T1, prim.node_id)
        assert got is not None, f"failed to round-trip {prim.kind}"
        assert got.node_id == prim.node_id


# ─── forget_tenant ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forget_tenant_removes_only_target_tenant():
    store = InMemoryOntologyStore()
    e1 = await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    e2 = await store.add_entity(T2, Entity(tenant_id=T2, entity_type="Customer"))
    await store.add_relation(T1, Relation(
        tenant_id=T1, relation_type="BOUGHT", from_id=e1.node_id, to_id=e1.node_id,
    ))

    wiped = await store.forget_tenant(T1)
    assert wiped >= 2   # entity + relation

    # T1 gone
    assert await store.get(T1, e1.node_id) is None
    # T2 intact
    assert await store.get(T2, e2.node_id) is not None


@pytest.mark.asyncio
async def test_forget_tenant_idempotent():
    store = InMemoryOntologyStore()
    await store.add_entity(T1, Entity(tenant_id=T1, entity_type="Customer"))
    first = await store.forget_tenant(T1)
    second = await store.forget_tenant(T1)
    assert first >= 1
    assert second == 0
