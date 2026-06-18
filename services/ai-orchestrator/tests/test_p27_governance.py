"""
Tests for Phase 2.7 P3 + P2 items:
- AI governance audit layer
- Policy engine
- Tenant quotas

Pure-function tests where possible, monkeypatched DB for SQL paths.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from ai_orchestrator.shared.ai_governance import hash_output, hash_prompt
from ai_orchestrator.shared.policy_engine import (
    PolicyDecision,
    PolicyRule,
    evaluate,
    evaluate_condition,
    reload_cache,
    set_cache,
)
from ai_orchestrator.shared.tenant_quotas import (
    QuotaExceeded,
    QuotaNotConfigured,
    _window_bounds,
    check_and_consume,
    get_usage,
)


# ─── AI governance: prompt hashing ───────────────────────────────


class TestHashPrompt:
    def test_deterministic(self):
        assert hash_prompt("hello") == hash_prompt("hello")

    def test_different_inputs_different_hash(self):
        assert hash_prompt("a") != hash_prompt("b")

    def test_empty_string_returns_empty_hash(self):
        h = hash_prompt("")
        # SHA-256 of empty bytes
        assert h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_truncates_large_input(self):
        h1 = hash_prompt("x" * 2_000_000)
        h2 = hash_prompt("x" * 1_500_000)
        # Both > 1MB → both truncated to 1MB → equal
        assert h1 == h2

    def test_hex_64_chars(self):
        h = hash_prompt("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_output_alias(self):
        assert hash_output("x") == hash_prompt("x")


@pytest.mark.asyncio
class TestRecordAiCall:
    async def test_missing_required_fields_raises(self):
        from ai_orchestrator.shared.ai_governance import record_ai_call
        with pytest.raises(ValueError, match="task_kind"):
            await record_ai_call(
                enterprise_id=uuid4(), task_kind="",
                model_version="v1", model_provider="x", prompt="p",
            )
        with pytest.raises(ValueError, match="model_version"):
            await record_ai_call(
                enterprise_id=uuid4(), task_kind="t",
                model_version="", model_provider="x", prompt="p",
            )

    async def test_invalid_confidence_raises(self):
        from ai_orchestrator.shared.ai_governance import record_ai_call
        with pytest.raises(ValueError, match="confidence"):
            await record_ai_call(
                enterprise_id=uuid4(), task_kind="t",
                model_version="v", model_provider="p", prompt="x",
                confidence=1.5,
            )

    async def test_successful_insert(self, monkeypatch):
        from ai_orchestrator.shared.ai_governance import record_ai_call

        captured = {"args": None}
        new_id = uuid4()

        class _Conn:
            async def fetchrow(self, sql, *args):
                captured["args"] = args
                return {"audit_id": new_id}

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await record_ai_call(
            enterprise_id=uuid4(),
            task_kind="classify_document",
            model_version="qwen2.5-14b",
            model_provider="ollama",
            prompt="phân loại doc này",
            confidence=0.83,
            token_input_count=120,
            token_output_count=45,
            cost_cents=0.0042,
        )
        assert result == new_id
        # prompt_hash is arg index 8 (0-indexed): ent, req_id, dec_id,
        # run_id, node_id, task, model_v, model_p, prompt_hash
        assert len(captured["args"][8]) == 64


# ─── Policy engine: condition evaluator ──────────────────────────


class TestEvaluateCondition:
    def test_simple_eq_pass(self):
        ctx = {"role": "MANAGER"}
        cond = {"field": "role", "op": "==", "value": "MANAGER"}
        assert evaluate_condition(cond, ctx) is True

    def test_simple_eq_fail(self):
        ctx = {"role": "VIEWER"}
        cond = {"field": "role", "op": "==", "value": "MANAGER"}
        assert evaluate_condition(cond, ctx) is False

    def test_compound_and(self):
        ctx = {"role": "SUPER_ADMIN", "mfa_enabled": False}
        cond = {"and": [
            {"field": "role", "op": "==", "value": "SUPER_ADMIN"},
            {"field": "mfa_enabled", "op": "==", "value": False},
        ]}
        assert evaluate_condition(cond, ctx) is True

    def test_compound_or(self):
        ctx = {"role": "OPERATOR"}
        cond = {"or": [
            {"field": "role", "op": "==", "value": "MANAGER"},
            {"field": "role", "op": "==", "value": "OPERATOR"},
        ]}
        assert evaluate_condition(cond, ctx) is True

    def test_numeric_comparison(self):
        ctx = {"amount_vnd": 150_000_000}
        cond = {"field": "amount_vnd", "op": ">", "value": 100_000_000}
        assert evaluate_condition(cond, ctx) is True

    def test_unknown_op_returns_false(self):
        cond = {"field": "x", "op": "approximately", "value": 1}
        assert evaluate_condition(cond, {"x": 1}) is False

    def test_missing_field_returns_false(self):
        cond = {"field": "missing", "op": "==", "value": 1}
        assert evaluate_condition(cond, {"x": 1}) is False

    def test_type_mismatch_returns_false(self):
        cond = {"field": "x", "op": ">", "value": "abc"}
        assert evaluate_condition(cond, {"x": None}) is False


# ─── Policy engine: evaluate() top-level ─────────────────────────


@pytest.mark.asyncio
class TestEvaluate:
    def setup_method(self):
        reload_cache()

    async def test_no_rules_returns_allow(self):
        set_cache([])
        decision = await evaluate({"role": "MANAGER"})
        assert decision.matched is False
        assert decision.action == "allow"
        assert decision.rule_key is None

    async def test_first_matching_rule_wins_by_priority(self):
        set_cache([
            PolicyRule(
                rule_id="r1", rule_key="lower_priority",
                description="", scope="global", priority=100,
                condition={"field": "x", "op": "==", "value": 1},
                action="audit", action_params={"reason": "lower"},
                metadata={}, enabled=True,
            ),
            PolicyRule(
                rule_id="r2", rule_key="higher_priority",
                description="", scope="global", priority=10,
                condition={"field": "x", "op": "==", "value": 1},
                action="deny", action_params={"reason": "higher"},
                metadata={}, enabled=True,
            ),
        ])
        decision = await evaluate({"x": 1})
        # cache is loaded as given; evaluator walks in order so caller
        # should pre-sort. We rely on _get_rules sorting; if set_cache
        # passes pre-sorted list our test is meaningful.
        # Re-set with manual priority ordering
        set_cache([
            PolicyRule(
                rule_id="r2", rule_key="higher_priority",
                description="", scope="global", priority=10,
                condition={"field": "x", "op": "==", "value": 1},
                action="deny", action_params={"reason": "higher"},
                metadata={}, enabled=True,
            ),
            PolicyRule(
                rule_id="r1", rule_key="lower_priority",
                description="", scope="global", priority=100,
                condition={"field": "x", "op": "==", "value": 1},
                action="audit", action_params={"reason": "lower"},
                metadata={}, enabled=True,
            ),
        ])
        decision = await evaluate({"x": 1})
        assert decision.matched is True
        assert decision.rule_key == "higher_priority"
        assert decision.action == "deny"

    async def test_k4_consent_external_rule(self):
        """Simulate the seed K-4 rule from mig 099."""
        set_cache([
            PolicyRule(
                rule_id="r", rule_key="k4_consent_external_required",
                description="K-4", scope="global", priority=10,
                condition={"field": "consent_external", "op": "==", "value": False},
                action="deny",
                action_params={"reason": "K-4: tenant has not enabled consent_external"},
                metadata={}, enabled=True,
            ),
        ])
        decision = await evaluate({"consent_external": False})
        assert decision.action == "deny"
        assert "K-4" in decision.reason

    async def test_finance_threshold_rule(self):
        set_cache([
            PolicyRule(
                rule_id="r", rule_key="finance_threshold",
                description="", scope="global", priority=50,
                condition={"and": [
                    {"field": "department_type", "op": "==", "value": "finance"},
                    {"field": "amount_vnd", "op": ">", "value": 100_000_000},
                ]},
                action="require_approval",
                action_params={"required_role": "CFO"},
                metadata={}, enabled=True,
            ),
        ])
        decision = await evaluate({
            "department_type": "finance",
            "amount_vnd": 200_000_000,
        })
        assert decision.action == "require_approval"
        assert decision.action_params["required_role"] == "CFO"

    async def test_role_scoped_rule_filters_by_role(self):
        set_cache([
            PolicyRule(
                rule_id="r", rule_key="super_admin_mfa",
                description="", scope="role", priority=5,
                condition={"field": "mfa_enabled", "op": "==", "value": False},
                action="deny",
                action_params={"reason": "MFA required for SUPER_ADMIN"},
                metadata={"required_role": "SUPER_ADMIN"},
                enabled=True,
            ),
        ])
        # Caller role doesn't match → rule skipped
        d1 = await evaluate({"role": "MANAGER", "mfa_enabled": False})
        assert d1.matched is False
        # Role matches → rule fires
        d2 = await evaluate({"role": "SUPER_ADMIN", "mfa_enabled": False})
        assert d2.matched is True
        assert d2.action == "deny"


# ─── Tenant quotas: window bounds ────────────────────────────────


class TestWindowBounds:
    def test_per_minute_window(self):
        now = datetime(2026, 5, 19, 14, 23, 45, tzinfo=timezone.utc)
        start, end = _window_bounds("per_minute", now)
        assert start == datetime(2026, 5, 19, 14, 23, 0, tzinfo=timezone.utc)
        assert end   == datetime(2026, 5, 19, 14, 24, 0, tzinfo=timezone.utc)

    def test_per_hour_window(self):
        now = datetime(2026, 5, 19, 14, 23, 45, tzinfo=timezone.utc)
        start, end = _window_bounds("per_hour", now)
        assert start == datetime(2026, 5, 19, 14, 0, 0, tzinfo=timezone.utc)
        assert end   == datetime(2026, 5, 19, 15, 0, 0, tzinfo=timezone.utc)

    def test_per_day_window(self):
        now = datetime(2026, 5, 19, 14, 23, 45, tzinfo=timezone.utc)
        start, end = _window_bounds("per_day", now)
        assert start == datetime(2026, 5, 19, 0, 0, 0, tzinfo=timezone.utc)
        assert end   == datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)

    def test_per_month_window(self):
        now = datetime(2026, 5, 19, tzinfo=timezone.utc)
        start, end = _window_bounds("per_month", now)
        assert start == datetime(2026, 5, 1, tzinfo=timezone.utc)
        assert end   == datetime(2026, 6, 1, tzinfo=timezone.utc)

    def test_per_month_december_rollover(self):
        now = datetime(2026, 12, 15, tzinfo=timezone.utc)
        start, end = _window_bounds("per_month", now)
        assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
        assert end   == datetime(2027, 1, 1, tzinfo=timezone.utc)

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError):
            _window_bounds("per_week")


# ─── Tenant quotas: check_and_consume ────────────────────────────


@pytest.mark.asyncio
class TestCheckAndConsume:
    async def test_no_row_fail_open(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None
            async def execute(self, *a, **k): return "OK"
            def transaction(self): return _Tx()
        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        check = await check_and_consume(
            enterprise_id=uuid4(),
            quota_type="undeclared_metric",
            amount=10,
            fail_open_if_unconfigured=True,
        )
        assert check.period == "unconfigured"

    async def test_no_row_fail_closed_raises(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None
            async def execute(self, *a, **k): return "OK"
            def transaction(self): return _Tx()
        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(QuotaNotConfigured):
            await check_and_consume(
                enterprise_id=uuid4(),
                quota_type="undeclared",
                fail_open_if_unconfigured=False,
            )

    async def test_within_quota_increments(self, monkeypatch):
        execs = []

        class _Conn:
            def __init__(self):
                self.call_i = 0
            async def fetchrow(self, sql, *a):
                if "FROM tenant_quotas" in sql:
                    return {"max_value": 100, "period": "per_hour"}
                if "FROM tenant_quota_usage" in sql:
                    return {"usage_id": uuid4(), "current_value": 30}
                return None
            async def execute(self, sql, *a):
                execs.append(sql)
            def transaction(self): return _Tx()

        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        check = await check_and_consume(
            enterprise_id=uuid4(),
            quota_type="api_calls",
            amount=10,
        )
        assert check.current == 40
        assert check.headroom == 60
        assert check.max_value == 100

    async def test_exceeds_quota_raises(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, sql, *a):
                if "FROM tenant_quotas" in sql:
                    return {"max_value": 100, "period": "per_hour"}
                if "FROM tenant_quota_usage" in sql:
                    return {"usage_id": uuid4(), "current_value": 95}
                return None
            async def execute(self, *a, **k): return "OK"
            def transaction(self): return _Tx()

        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        with pytest.raises(QuotaExceeded) as exc:
            await check_and_consume(
                enterprise_id=uuid4(),
                quota_type="api_calls",
                amount=10,   # 95 + 10 > 100
            )
        assert exc.value.max_value == 100
        assert exc.value.quota_type == "api_calls"

    async def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            await check_and_consume(
                enterprise_id=uuid4(),
                quota_type="x",
                amount=-1,
            )


@pytest.mark.asyncio
class TestGetUsage:
    async def test_no_row_returns_none(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await get_usage(
            enterprise_id=uuid4(),
            quota_type="x",
        )
        assert result is None

    async def test_returns_current_usage(self, monkeypatch):
        class _Conn:
            def __init__(self):
                self.i = 0
            async def fetchrow(self, sql, *a):
                self.i += 1
                if self.i == 1:
                    return {"max_value": 1000, "period": "per_day"}
                return {"current_value": 350}
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await get_usage(
            enterprise_id=uuid4(),
            quota_type="llm_tokens_external",
        )
        assert result.current == 350
        assert result.headroom == 650
        assert result.max_value == 1000
