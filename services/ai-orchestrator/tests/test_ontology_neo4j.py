"""Neo4j adapter tests for the 7-Primitives Ontology.

Mocks the neo4j AsyncDriver / AsyncSession; no live Neo4j cluster.
Validates the Cypher shape + tenant label discipline:
  * Per-tenant label `_T_<hash>` baked into every Cypher MATCH/MERGE
  * Cross-tenant write rejected at the Python layer (defence-in-depth)
  * Relation requires both endpoints to MATCH under the tenant label
  * neighbours/decision_provenance/find_by_external_id all use the label
  * forget_tenant DETACH DELETEs scoped by label
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.ontology import (
    Decision,
    Entity,
    Event,
    Insight,
    Relation,
)
from ai_orchestrator.reasoning.ontology.neo4j_store import (
    Neo4jOntologyStore,
    _tenant_label,
    _props_to_prim,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")


# ─── Helpers ────────────────────────────────────────────────────────


def _label_for(tid: UUID) -> str:
    return _tenant_label(tid)


def _entity_props(node_id, tenant_id=T1, entity_type="Customer", external_id=None):
    return {
        "node_id":    str(node_id),
        "tenant_id":  str(tenant_id),
        "kind":       "entity",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata":   "{}",
        "entity_type": entity_type,
        "external_id": external_id,
    }


def _decision_props(node_id, tenant_id=T1):
    return {
        "node_id":    str(node_id),
        "tenant_id":  str(tenant_id),
        "kind":       "decision",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata":   "{}",
        "decision_type": "approve_invoice",
        "chosen_value":  "yes",
        "confidence":    0.9,
        "actor":         "ai",
    }


def _make_session():
    """Make an AsyncSession mock that also supports `async with`."""
    sess = MagicMock()
    sess.run = AsyncMock()
    sess.close = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__  = AsyncMock(return_value=None)
    return sess


@pytest.fixture
def driver():
    d = MagicMock()
    d._sessions = []
    def _session():
        s = _make_session()
        d._sessions.append(s)
        return s
    d.session = _session
    d.close = AsyncMock()
    return d


@pytest.fixture
def store(driver):
    return Neo4jOntologyStore(driver=driver)


# ─── _tenant_label ──────────────────────────────────────────────────


class TestTenantLabel:
    def test_starts_with_underscore_T(self):
        assert _tenant_label(T1).startswith("_T_")

    def test_alphanumeric_only(self):
        label = _tenant_label(T1)
        # _T_ prefix + 16-hex-char hash
        assert len(label) == 3 + 16
        assert all(c.isalnum() or c == "_" for c in label)

    def test_different_tenants_different_labels(self):
        assert _tenant_label(T1) != _tenant_label(T2)

    def test_same_tenant_same_label_deterministic(self):
        assert _tenant_label(T1) == _tenant_label(T1)


# ─── add_entity ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_entity_uses_per_tenant_label(store, driver):
    e = Entity(tenant_id=T1, entity_type="Customer", external_id="KV-001")
    await store.add_entity(T1, e)
    # Pull the Cypher that ran on the session
    sess = driver._sessions[0]
    sess.run.assert_awaited_once()
    cypher = sess.run.await_args.args[0]
    assert _label_for(T1) in cypher
    assert "Entity" in cypher
    assert "MERGE" in cypher


@pytest.mark.asyncio
async def test_cross_tenant_write_rejected(store):
    e = Entity(tenant_id=T2, entity_type="Customer")
    with pytest.raises(ValueError, match="cross-tenant"):
        await store.add_entity(T1, e)


# ─── add_relation ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_relation_checks_both_endpoints_via_label(store, driver):
    """Relation MUST run a MATCH on the tenant-labelled endpoints
    BEFORE the MERGE. If either endpoint isn't under the tenant
    label, KeyError."""
    # First session: endpoint check returns None (endpoints missing)
    sess1 = _make_session()
    sess1.run = AsyncMock(return_value=AsyncMock(
        single=AsyncMock(return_value=None),
    ))
    driver._sessions = []
    driver.session = lambda: sess1

    rel = Relation(tenant_id=T1, relation_type="BOUGHT",
                    from_id=uuid4(), to_id=uuid4())
    with pytest.raises(KeyError, match="endpoints not found"):
        await store.add_relation(T1, rel)
    # The MATCH cypher must include the tenant label
    cypher = sess1.run.await_args.args[0]
    assert _label_for(T1) in cypher
    assert "MATCH" in cypher


@pytest.mark.asyncio
async def test_add_relation_rejects_cross_tenant(store):
    rel = Relation(tenant_id=T2, relation_type="BOUGHT",
                    from_id=uuid4(), to_id=uuid4())
    with pytest.raises(ValueError, match="cross-tenant"):
        await store.add_relation(T1, rel)


# ─── get ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_primitive(store, driver):
    rid = uuid4()
    props = _entity_props(rid)
    row = MagicMock()
    row.__getitem__ = lambda _s, k: {"n": props}[k]
    sess = _make_session()
    sess.run = AsyncMock(return_value=AsyncMock(
        single=AsyncMock(return_value=row),
    ))
    driver._sessions = []
    driver.session = lambda: sess

    got = await store.get(T1, rid)
    assert got is not None
    assert isinstance(got, Entity)
    assert got.entity_type == "Customer"
    cypher = sess.run.await_args.args[0]
    assert _label_for(T1) in cypher


@pytest.mark.asyncio
async def test_get_miss_returns_none(store, driver):
    sess = _make_session()
    sess.run = AsyncMock(return_value=AsyncMock(
        single=AsyncMock(return_value=None),
    ))
    driver._sessions = []
    driver.session = lambda: sess
    got = await store.get(T1, uuid4())
    assert got is None


# ─── neighbours ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_neighbours_out_direction_uses_arrow(store, driver):
    sess = _make_session()
    # Async iterator: yields no rows
    async def _empty_iter():
        if False:
            yield None
    sess.run = AsyncMock(return_value=_empty_iter())
    driver._sessions = []
    driver.session = lambda: sess
    await store.neighbours(T1, uuid4(), direction="out")
    cypher = sess.run.await_args.args[0]
    assert "-[" in cypher and "]->" in cypher


@pytest.mark.asyncio
async def test_neighbours_invalid_direction_raises(store):
    with pytest.raises(ValueError):
        await store.neighbours(T1, uuid4(), direction="sideways")


@pytest.mark.asyncio
async def test_neighbours_relation_filter_uppercased(store, driver):
    sess = _make_session()
    async def _empty_iter():
        if False:
            yield None
    sess.run = AsyncMock(return_value=_empty_iter())
    driver._sessions = []
    driver.session = lambda: sess
    await store.neighbours(T1, uuid4(), relation_type="bought", direction="out")
    cypher = sess.run.await_args.args[0]
    assert ":BOUGHT" in cypher


# ─── find_by_external_id ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_by_external_id_uses_entity_label_and_tenant_label(store, driver):
    sess = _make_session()
    sess.run = AsyncMock(return_value=AsyncMock(
        single=AsyncMock(return_value=None),
    ))
    driver._sessions = []
    driver.session = lambda: sess
    await store.find_by_external_id(T1, entity_type="Customer", external_id="KV-001")
    cypher = sess.run.await_args.args[0]
    assert "Entity" in cypher
    assert _label_for(T1) in cypher


# ─── decision_provenance ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_provenance_groups_by_relation_type(store, driver):
    sess = _make_session()
    cust_props = _entity_props(uuid4())
    feat_props = _entity_props(uuid4(), entity_type="Feature", external_id="churn")
    row1 = MagicMock()
    row1.__getitem__ = lambda _s, k: {"rtype": "BASED_ON", "m": cust_props}[k]
    row2 = MagicMock()
    row2.__getitem__ = lambda _s, k: {"rtype": "USED_FEATURE", "m": feat_props}[k]

    async def _rows():
        for r in (row1, row2):
            yield r

    sess.run = AsyncMock(return_value=_rows())
    driver._sessions = []
    driver.session = lambda: sess

    prov = await store.decision_provenance(T1, uuid4())
    assert set(prov.keys()) == {"BASED_ON", "USED_FEATURE"}
    assert isinstance(prov["BASED_ON"][0], Entity)


# ─── forget_tenant ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forget_tenant_detach_deletes_scoped_by_label(store, driver):
    sess = _make_session()
    row = MagicMock()
    row.__getitem__ = lambda _s, k: {"c": 42}[k]
    sess.run = AsyncMock(return_value=AsyncMock(
        single=AsyncMock(return_value=row),
    ))
    driver._sessions = []
    driver.session = lambda: sess
    n = await store.forget_tenant(T1)
    assert n == 42
    cypher = sess.run.await_args.args[0]
    assert "DETACH DELETE" in cypher
    assert _label_for(T1) in cypher


# ─── _props_to_prim ─────────────────────────────────────────────────


class TestPropsToPrim:

    def test_entity(self):
        rid = uuid4()
        out = _props_to_prim(_entity_props(rid))
        assert isinstance(out, Entity)
        assert out.node_id == rid

    def test_decision(self):
        out = _props_to_prim(_decision_props(uuid4()))
        assert isinstance(out, Decision)
        assert out.confidence == 0.9

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown kind"):
            _props_to_prim({
                "node_id": str(uuid4()), "tenant_id": str(T1),
                "kind": "alien", "created_at": datetime.now(timezone.utc).isoformat(),
            })
