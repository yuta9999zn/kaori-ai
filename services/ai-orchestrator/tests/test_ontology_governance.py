"""
Tests for P2.2 lifecycle FSM + P2.3 edge taxonomy governance.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from reasoning.ontology.governance import (
    EdgeTypeNotAllowed,
    EdgeTypeSpec,
    LifecycleRule,
    LifecycleTransitionDenied,
    is_recovery_required,
    reset_edge_cache,
    validate_edge_type,
    validate_lifecycle_transition,
)


# ─── Pure helpers ────────────────────────────────────────────────


class TestIsRecoveryRequired:
    @pytest.mark.parametrize("from_state", [
        "churned", "archived", "cancelled", "expired",
    ])
    def test_terminal_states_require_recovery(self, from_state):
        assert is_recovery_required(from_state, "lead") is True

    @pytest.mark.parametrize("from_state", [
        "lead", "active_customer", "at_risk", "draft", "published",
    ])
    def test_non_terminal_states_no_recovery_needed(self, from_state):
        assert is_recovery_required(from_state, "active_customer") is False


# ─── Lifecycle transition validation (DB-mocked) ────────────────


@pytest.mark.asyncio
class TestValidateLifecycleTransition:
    async def test_idempotent_noop_no_db_call(self):
        """Same from_state == to_state returns synthetic rule without DB."""
        rule = await validate_lifecycle_transition(
            enterprise_id=uuid4(),
            entity_type="customer",
            from_state="active_customer",
            to_state="active_customer",
        )
        assert rule.description == "idempotent no-op"

    async def test_unknown_transition_raises(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(LifecycleTransitionDenied) as exc:
            await validate_lifecycle_transition(
                enterprise_id=uuid4(),
                entity_type="customer",
                from_state="lead",
                to_state="churned",  # not in seed
            )
        assert "no matching rule" in exc.value.reason

    async def test_missing_event_raises(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return {
                    "entity_type": "customer",
                    "from_state": "lead",
                    "to_state": "active_customer",
                    "requires_event": "first_purchase",
                    "requires_role": None,
                    "is_recovery": False,
                    "description": "",
                }

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(LifecycleTransitionDenied) as exc:
            await validate_lifecycle_transition(
                enterprise_id=uuid4(),
                entity_type="customer",
                from_state="lead",
                to_state="active_customer",
                event_name="signup",  # wrong event
            )
        assert "first_purchase" in exc.value.reason

    async def test_missing_role_raises(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return {
                    "entity_type": "customer",
                    "from_state": "churned",
                    "to_state": "lead",
                    "requires_event": "win_back",
                    "requires_role": "MANAGER",
                    "is_recovery": True,
                    "description": "",
                }

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(LifecycleTransitionDenied) as exc:
            await validate_lifecycle_transition(
                enterprise_id=uuid4(),
                entity_type="customer",
                from_state="churned",
                to_state="lead",
                event_name="win_back",
                actor_role="OPERATOR",   # wrong role
            )
        assert "MANAGER" in exc.value.reason

    async def test_valid_transition_passes(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return {
                    "entity_type": "customer",
                    "from_state": "lead",
                    "to_state": "active_customer",
                    "requires_event": "first_purchase",
                    "requires_role": None,
                    "is_recovery": False,
                    "description": "",
                }

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        rule = await validate_lifecycle_transition(
            enterprise_id=uuid4(),
            entity_type="customer",
            from_state="lead",
            to_state="active_customer",
            event_name="first_purchase",
        )
        assert rule.is_recovery is False
        assert rule.from_state == "lead"


# ─── Edge type validation ────────────────────────────────────────


def _fake_edge_db(monkeypatch, rows: list[dict]):
    """Helper — patch DB to return given edge_type rows."""
    class _Conn:
        async def fetch(self, *a, **k): return rows

    class _CM:
        async def __aenter__(self): return _Conn()
        async def __aexit__(self, *a): return False

    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())


@pytest.mark.asyncio
class TestValidateEdgeType:
    def setup_method(self):
        # Each test starts with a clean cache
        reset_edge_cache()

    async def test_empty_key_raises(self):
        with pytest.raises(EdgeTypeNotAllowed) as exc:
            await validate_edge_type(
                enterprise_id=uuid4(),
                edge_type_key="",
                source_primitive="customer",
                target_primitive="product",
            )
        assert "empty" in exc.value.reason

    async def test_unknown_edge_blocked(self, monkeypatch):
        _fake_edge_db(monkeypatch, rows=[])
        with pytest.raises(EdgeTypeNotAllowed) as exc:
            await validate_edge_type(
                enterprise_id=uuid4(),
                edge_type_key="CUSTOMER_LIKED_PRODUCT",  # not in registry
                source_primitive="customer",
                target_primitive="product",
            )
        assert "not in" in exc.value.reason or "free-form" in exc.value.reason

    async def test_known_edge_passes(self, monkeypatch):
        _fake_edge_db(monkeypatch, rows=[
            {"edge_type_key": "CUSTOMER_PURCHASED_PRODUCT",
              "source_primitive": "customer",
              "target_primitive": "product",
              "cardinality": "many_to_many",
              "retention_days": 730,
              "governance_owner": "platform",
              "deprecated_at": None},
        ])
        spec = await validate_edge_type(
            enterprise_id=uuid4(),
            edge_type_key="CUSTOMER_PURCHASED_PRODUCT",
            source_primitive="customer",
            target_primitive="product",
        )
        assert spec.cardinality == "many_to_many"
        assert spec.deprecated is False

    async def test_deprecated_edge_blocked(self, monkeypatch):
        from datetime import datetime, timezone
        _fake_edge_db(monkeypatch, rows=[
            {"edge_type_key": "OLD_EDGE",
              "source_primitive": "customer",
              "target_primitive": "product",
              "cardinality": "many_to_many",
              "retention_days": 0,
              "governance_owner": "platform",
              "deprecated_at": datetime.now(timezone.utc)},
        ])
        with pytest.raises(EdgeTypeNotAllowed) as exc:
            await validate_edge_type(
                enterprise_id=uuid4(),
                edge_type_key="OLD_EDGE",
                source_primitive="customer",
                target_primitive="product",
            )
        assert "deprecated" in exc.value.reason

    async def test_source_primitive_mismatch_blocked(self, monkeypatch):
        _fake_edge_db(monkeypatch, rows=[
            {"edge_type_key": "CUSTOMER_PURCHASED_PRODUCT",
              "source_primitive": "customer",
              "target_primitive": "product",
              "cardinality": "many_to_many",
              "retention_days": 730,
              "governance_owner": "platform",
              "deprecated_at": None},
        ])
        with pytest.raises(EdgeTypeNotAllowed) as exc:
            await validate_edge_type(
                enterprise_id=uuid4(),
                edge_type_key="CUSTOMER_PURCHASED_PRODUCT",
                source_primitive="product",   # wrong
                target_primitive="product",
            )
        assert "source primitive" in exc.value.reason

    async def test_target_primitive_mismatch_blocked(self, monkeypatch):
        _fake_edge_db(monkeypatch, rows=[
            {"edge_type_key": "TRANSACTION_FOR_CUSTOMER",
              "source_primitive": "transaction",
              "target_primitive": "customer",
              "cardinality": "many_to_one",
              "retention_days": 730,
              "governance_owner": "platform",
              "deprecated_at": None},
        ])
        with pytest.raises(EdgeTypeNotAllowed) as exc:
            await validate_edge_type(
                enterprise_id=uuid4(),
                edge_type_key="TRANSACTION_FOR_CUSTOMER",
                source_primitive="transaction",
                target_primitive="product",   # wrong
            )
        assert "target primitive" in exc.value.reason

    async def test_cache_avoids_repeated_db_calls(self, monkeypatch):
        """After load_edge_types caches, second call does NOT hit DB."""
        call_count = {"fetch": 0}

        class _Conn:
            async def fetch(self, *a, **k):
                call_count["fetch"] += 1
                return [
                    {"edge_type_key": "X_FOO_Y",
                      "source_primitive": "customer",
                      "target_primitive": "product",
                      "cardinality": "many_to_many",
                      "retention_days": 730,
                      "governance_owner": "platform",
                      "deprecated_at": None},
                ]

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        await validate_edge_type(
            enterprise_id=uuid4(),
            edge_type_key="X_FOO_Y",
            source_primitive="customer",
            target_primitive="product",
        )
        await validate_edge_type(
            enterprise_id=uuid4(),
            edge_type_key="X_FOO_Y",
            source_primitive="customer",
            target_primitive="product",
        )
        assert call_count["fetch"] == 1  # only the first call hits DB
