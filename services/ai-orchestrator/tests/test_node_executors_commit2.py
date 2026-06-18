"""
Unit tests for commit-2 executors:
  ApprovalGateExecutor   (write_idempotent, pause/resume)
  ReadFormSubmissionExecutor (read_only)
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from workflow_runtime.node_executor import (
    NodeContext,
    NodeExecutorError,
    REGISTRY,
)
from workflow_runtime.executors.approval import (
    ApprovalGateExecutor,
    ReadFormSubmissionExecutor,
    _eval_threshold,
)
from workflow_runtime.side_effect import SideEffectClass


def _ctx(prior_outputs=None, input_data=None, **overrides) -> NodeContext:
    defaults = dict(
        enterprise_id=uuid4(),
        workspace_id=None,
        workflow_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        user_id=None,
        input_data=input_data or {},
        prior_outputs=prior_outputs or {},
    )
    defaults.update(overrides)
    return NodeContext(**defaults)


# ─── Registry check ────────────────────────────────────────────────


class TestCommit2Registry:
    def test_approval_gate_registered(self):
        assert REGISTRY.has("approval_gate")

    def test_read_form_submission_registered(self):
        assert REGISTRY.has("read_form_submission")

    def test_total_first_wave_count(self):
        # commit 1 = 6, commit 2 = +2 = 8 first-wave executors
        first_wave = [
            "if_else", "switch", "aggregate",
            "read_table", "update_record", "send_email",
            "approval_gate", "read_form_submission",
        ]
        for k in first_wave:
            assert REGISTRY.has(k), f"{k} missing"


# ─── _eval_threshold ──────────────────────────────────────────────


class TestEvalThreshold:
    def test_less_than(self):
        assert _eval_threshold(5, "<", 10) is True
        assert _eval_threshold(15, "<", 10) is False

    def test_greater_or_equal(self):
        assert _eval_threshold(10, ">=", 10) is True
        assert _eval_threshold(9, ">=", 10) is False

    def test_equality(self):
        assert _eval_threshold("APPROVE", "==", "APPROVE") is True

    def test_type_mismatch_returns_false(self):
        assert _eval_threshold(None, "<", 10) is False
        assert _eval_threshold("abc", ">", 100) is False

    def test_unknown_op_returns_false(self):
        assert _eval_threshold(1, "near", 1) is False


# ─── ApprovalGate validation (no DB calls) ────────────────────────


class TestApprovalGateValidation:
    @pytest.mark.asyncio
    async def test_missing_approver_role_raises(self):
        ex = ApprovalGateExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_invalid_role_type_raises(self):
        ex = ApprovalGateExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"approver_role": 12345})

    @pytest.mark.asyncio
    async def test_empty_role_list_raises(self):
        ex = ApprovalGateExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"approver_role": []})

    @pytest.mark.asyncio
    async def test_auto_threshold_below_skips_approval(self, monkeypatch):
        """When auto_threshold condition is true, executor returns
        'completed' status without touching DB."""
        ex = ApprovalGateExecutor()
        ctx = _ctx(prior_outputs={"upstream": {"amount": 5_000_000}})
        result = await ex.execute(ctx, {
            "approver_role": "MANAGER",
            "auto_threshold": {
                "field": "$.upstream.amount",
                "op": "<",
                "value": 10_000_000,
            },
        })
        assert result.status == "completed"
        assert result.output_data["auto_approved"] is True
        assert result.output_data["paused"] is False
        assert result.output_data["reason"] == "threshold_below"

    @pytest.mark.asyncio
    async def test_auto_threshold_not_met_falls_to_paused(self, monkeypatch):
        """When threshold not met, executor would normally INSERT into
        workflow_approvals + return awaiting_approval. We monkeypatch
        the DB call to verify control-flow without a real connection."""
        ex = ApprovalGateExecutor()
        ctx = _ctx(prior_outputs={"upstream": {"amount": 50_000_000}})

        from datetime import datetime
        from uuid import uuid4 as _u

        class _FakeRow(dict):
            def __getitem__(self, key):
                if key == "approval_id":
                    return _u()
                if key == "created_at":
                    return datetime.utcnow()
                return super().__getitem__(key)

        class _FakeConn:
            async def fetchrow(self, *a, **k):
                return _FakeRow()
            async def execute(self, *a, **k):
                return "INSERT 0 1"

        class _FakeCM:
            async def __aenter__(self):
                return _FakeConn()
            async def __aexit__(self, *a):
                return False

        def _fake_acquire(_eid):
            return _FakeCM()

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", _fake_acquire)

        result = await ex.execute(ctx, {
            "approver_role": ["MANAGER", "DIRECTOR"],
            "auto_threshold": {
                "field": "$.upstream.amount",
                "op": "<",
                "value": 10_000_000,
            },
            "sla_minutes": 120,
            "reason_prompt": "Vui lòng duyệt khoản chi này.",
        })
        assert result.status == "awaiting_approval"
        assert result.output_data["paused"] is True
        assert result.output_data["approver_roles"] == ["MANAGER", "DIRECTOR"]
        assert result.output_data["sla_minutes"] == 120


# ─── ReadFormSubmission validation ────────────────────────────────


class TestReadFormSubmissionValidation:
    @pytest.mark.asyncio
    async def test_missing_form_key_raises(self):
        ex = ReadFormSubmissionExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_form_key_must_be_string(self):
        ex = ReadFormSubmissionExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"form_key": 12345})

    @pytest.mark.asyncio
    async def test_requires_submission_id_or_latest_flag(self):
        ex = ReadFormSubmissionExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"form_key": "refund_request"})

    @pytest.mark.asyncio
    async def test_bad_submission_id_uuid_raises(self, monkeypatch):
        """Passing a non-UUID submission_id should raise before any DB call."""
        ex = ReadFormSubmissionExecutor()
        ctx = _ctx(input_data={"submission_id": "not-a-uuid"})
        with pytest.raises(NodeExecutorError):
            await ex.execute(ctx, {"form_key": "refund_request"})

    @pytest.mark.asyncio
    async def test_no_row_returns_found_false(self, monkeypatch):
        """When DB returns None, executor returns found=False payload."""
        ex = ReadFormSubmissionExecutor()

        class _FakeConn:
            async def fetchrow(self, *a, **k):
                return None

        class _FakeCM:
            async def __aenter__(self):
                return _FakeConn()
            async def __aexit__(self, *a):
                return False

        def _fake_acquire(_eid):
            return _FakeCM()

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", _fake_acquire)

        result = await ex.execute(_ctx(), {
            "form_key": "refund_request",
            "latest_for_form": True,
        })
        assert result.status == "completed"
        assert result.output_data["found"] is False
        assert result.output_data["submission_id"] is None


# ─── side_effect_class ────────────────────────────────────────────


class TestCommit2SideEffectClass:
    def test_approval_gate_is_write_idempotent(self):
        assert ApprovalGateExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT

    def test_read_form_submission_is_read_only(self):
        assert ReadFormSubmissionExecutor.side_effect_class == SideEffectClass.READ_ONLY


# ─── Phase 2.7 P3 — Policy engine override at approval_gate ─────────


class TestApprovalGatePolicyOverride:
    """The seeded finance_invoice_cfo_threshold rule must override
    config when amount > 100M VND + department_type=finance. Other
    cases fall through to config's auto_threshold + approver_role.

    We bypass the DB by injecting rules via policy_engine.set_cache().
    """

    @pytest.fixture(autouse=True)
    def _reset_policy_cache(self):
        from ai_orchestrator.shared.policy_engine import reload_cache
        reload_cache()  # clear stale rules from earlier tests
        yield
        reload_cache()

    @pytest.mark.asyncio
    async def test_finance_threshold_forces_cfo_role_overriding_config(
        self, monkeypatch,
    ):
        """When amount=200M + department=finance, the seeded rule
        forces approver_roles=['CFO'] regardless of what config said.
        Auto-threshold is SKIPPED because policy forces approval."""
        from ai_orchestrator.shared.policy_engine import (
            PolicyRule, set_cache,
        )
        set_cache([
            PolicyRule(
                rule_id="r1",
                rule_key="finance_invoice_cfo_threshold",
                description="invoice > 100M needs CFO",
                scope="global",
                priority=50,
                condition={
                    "and": [
                        {"field": "department_type", "op": "==", "value": "finance"},
                        {"field": "node_type_key",   "op": "==", "value": "approval_gate"},
                        {"field": "amount_vnd",      "op": ">",  "value": 100_000_000},
                    ],
                },
                action="require_approval",
                action_params={"required_role": "CFO", "sla_minutes": 1440},
                metadata={},
                enabled=True,
            ),
        ])

        # Patch DB so approval row INSERT doesn't need a pool.
        from datetime import datetime
        from uuid import uuid4 as _u
        class _FakeRow(dict):
            def __getitem__(self, key):
                if key == "approval_id":  return _u()
                if key == "created_at":   return datetime.utcnow()
                return super().__getitem__(key)
        class _FakeConn:
            async def fetchrow(self, *a, **k): return _FakeRow()
            async def execute(self, *a, **k):  return "INSERT 0 1"
        class _FakeCM:
            async def __aenter__(self): return _FakeConn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _e: _FakeCM())

        ex = ApprovalGateExecutor()
        # Upstream amount = 200M, department = finance → rule matches.
        # Config tries to auto-approve <10M; policy MUST overrule.
        ctx = _ctx(prior_outputs={"upstream": {
            "amount_vnd":      200_000_000,
            "department_type": "finance",
            "role":            "MANAGER",
        }})
        result = await ex.execute(ctx, {
            "approver_role":   "MANAGER",   # ← config says MANAGER
            "auto_threshold": {              # ← config says auto-approve <10M
                "field": "$.upstream.amount_vnd",
                "op":    "<",
                "value": 10_000_000,
            },
            "sla_minutes":    120,            # ← config 120
        })
        # Policy override: paused=True with CFO role + 1440 SLA.
        assert result.status == "awaiting_approval"
        assert result.output_data["paused"] is True
        assert result.output_data["approver_roles"] == ["CFO"]
        assert result.output_data["sla_minutes"] == 1440

    @pytest.mark.asyncio
    async def test_amount_below_threshold_falls_through_to_auto_approve(
        self, monkeypatch,
    ):
        """Same rule in cache, but amount=5M (below 100M) → rule doesn't
        match → auto_threshold short-circuit runs as configured."""
        from ai_orchestrator.shared.policy_engine import (
            PolicyRule, set_cache,
        )
        set_cache([
            PolicyRule(
                rule_id="r1",
                rule_key="finance_invoice_cfo_threshold",
                description="invoice > 100M needs CFO",
                scope="global",
                priority=50,
                condition={
                    "and": [
                        {"field": "department_type", "op": "==", "value": "finance"},
                        {"field": "node_type_key",   "op": "==", "value": "approval_gate"},
                        {"field": "amount_vnd",      "op": ">",  "value": 100_000_000},
                    ],
                },
                action="require_approval",
                action_params={"required_role": "CFO", "sla_minutes": 1440},
                metadata={},
                enabled=True,
            ),
        ])

        ex = ApprovalGateExecutor()
        ctx = _ctx(prior_outputs={"upstream": {
            "amount_vnd":      5_000_000,
            "department_type": "finance",
        }})
        result = await ex.execute(ctx, {
            "approver_role": "MANAGER",
            "auto_threshold": {
                "field": "$.upstream.amount_vnd",
                "op":    "<",
                "value": 10_000_000,
            },
        })
        # Policy didn't fire (amount too low) → auto-threshold runs.
        assert result.status == "completed"
        assert result.output_data["auto_approved"] is True

    @pytest.mark.asyncio
    async def test_deny_action_raises_node_executor_error(self):
        """If a future rule has action='deny' for this node, the
        executor must raise NodeExecutorError — no pause, no DB row."""
        from ai_orchestrator.shared.policy_engine import (
            PolicyRule, set_cache,
        )
        set_cache([
            PolicyRule(
                rule_id="r2",
                rule_key="blacklist_node",
                description="block this approval node",
                scope="global", priority=1,
                condition={
                    "field": "department_type", "op": "==", "value": "compliance",
                },
                action="deny",
                action_params={"reason": "compliance lockout"},
                metadata={}, enabled=True,
            ),
        ])

        ex = ApprovalGateExecutor()
        ctx = _ctx(prior_outputs={"upstream": {
            "department_type": "compliance",
            "amount_vnd":      1_000,
        }})
        with pytest.raises(NodeExecutorError):
            await ex.execute(ctx, {"approver_role": "MANAGER"})
