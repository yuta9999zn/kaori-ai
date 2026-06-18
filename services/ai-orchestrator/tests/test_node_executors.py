"""
Unit tests for the 6 first-wave node executors.

These pin per-executor behaviour with pure-Python mocks (no DB).
End-to-end runner+DB integration lives in test_workflow_run_e2e.py
(separate file because it needs Postgres).
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from workflow_runtime.node_executor import (
    NodeContext,
    NodeExecutorError,
    REGISTRY,
)
from workflow_runtime.executors import register_builtin_executors
from workflow_runtime.executors.pure import (
    AggregateExecutor,
    IfElseExecutor,
    SwitchExecutor,
    _eval_condition,
    _resolve,
)
from workflow_runtime.side_effect import SideEffectClass


# Ensure built-ins registered
register_builtin_executors()


def _ctx(prior_outputs=None, **overrides) -> NodeContext:
    defaults = dict(
        enterprise_id=uuid4(),
        workspace_id=None,
        workflow_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        user_id=None,
        input_data={},
        prior_outputs=prior_outputs or {},
    )
    defaults.update(overrides)
    return NodeContext(**defaults)


# ─── Registry ──────────────────────────────────────────────────────


class TestRegistry:
    def test_six_first_wave_executors_registered(self):
        for key in ("if_else", "switch", "aggregate",
                     "read_table", "update_record", "send_email"):
            assert REGISTRY.has(key), f"{key!r} missing from registry"

    def test_coverage_report(self):
        # Post wave 5 the catalog is 100% covered. Test contract is "report
        # correctly partitions registered vs missing" — pick a deliberate
        # non-existent key to verify the 'missing' bucket still works.
        catalog = ["if_else", "send_email", "deliberately_not_a_node"]
        report = REGISTRY.coverage_report(catalog)
        assert "if_else" in report["registered"]
        assert "send_email" in report["registered"]
        assert "deliberately_not_a_node" in report["missing"]

    def test_unknown_key_raises(self):
        with pytest.raises(NodeExecutorError):
            REGISTRY.get("nonexistent_node_type")


# ─── _resolve ──────────────────────────────────────────────────────


class TestResolve:
    def test_literal_passthrough(self):
        assert _resolve(42, _ctx()) == 42
        assert _resolve("hello", _ctx()) == "hello"
        assert _resolve(None, _ctx()) is None

    def test_node_path_lookup(self):
        ctx = _ctx(prior_outputs={"n1": {"amount": 50_000_000}})
        assert _resolve("$.n1.amount", ctx) == 50_000_000

    def test_missing_node_returns_none(self):
        assert _resolve("$.missing.field", _ctx()) is None

    def test_deep_path(self):
        ctx = _ctx(prior_outputs={"n1": {"user": {"name": "An"}}})
        assert _resolve("$.n1.user.name", ctx) == "An"

    def test_non_dollar_strings_passthrough(self):
        assert _resolve("plain string", _ctx()) == "plain string"


# ─── if_else ────────────────────────────────────────────────────────


class TestIfElse:
    @pytest.mark.asyncio
    async def test_true_branch(self):
        ex = IfElseExecutor()
        result = await ex.execute(_ctx(), {
            "condition": {"left": 10, "op": ">", "right": 5},
            "true_value": "yes",
            "false_value": "no",
        })
        assert result.status == "completed"
        assert result.output_data["branch"] == "true"
        assert result.output_data["value"] == "yes"

    @pytest.mark.asyncio
    async def test_false_branch(self):
        ex = IfElseExecutor()
        result = await ex.execute(_ctx(), {
            "condition": {"left": 3, "op": ">", "right": 5},
        })
        assert result.output_data["branch"] == "false"
        assert result.output_data["passed"] is False

    @pytest.mark.asyncio
    async def test_compound_and(self):
        ex = IfElseExecutor()
        cfg = {"condition": {"and": [
            {"left": 10, "op": ">", "right": 5},
            {"left": "abc", "op": "==", "right": "abc"},
        ]}}
        result = await ex.execute(_ctx(), cfg)
        assert result.output_data["branch"] == "true"

    @pytest.mark.asyncio
    async def test_compound_or(self):
        ex = IfElseExecutor()
        cfg = {"condition": {"or": [
            {"left": 1, "op": ">", "right": 100},
            {"left": "x", "op": "==", "right": "x"},
        ]}}
        result = await ex.execute(_ctx(), cfg)
        assert result.output_data["branch"] == "true"

    @pytest.mark.asyncio
    async def test_resolves_upstream_value(self):
        ex = IfElseExecutor()
        ctx = _ctx(prior_outputs={"upstream": {"amount": 200}})
        result = await ex.execute(ctx, {
            "condition": {"left": "$.upstream.amount", "op": ">", "right": 100},
        })
        assert result.output_data["branch"] == "true"

    @pytest.mark.asyncio
    async def test_missing_condition_raises(self):
        ex = IfElseExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_unknown_op_raises(self):
        ex = IfElseExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "condition": {"left": 1, "op": "approximately_equals", "right": 1},
            })

    @pytest.mark.asyncio
    async def test_type_mismatch_returns_false(self):
        # Comparing None > 5 — should NOT raise, just log + return False
        ex = IfElseExecutor()
        result = await ex.execute(_ctx(), {
            "condition": {"left": None, "op": ">", "right": 5},
        })
        assert result.output_data["passed"] is False


# ─── switch ─────────────────────────────────────────────────────────


class TestSwitch:
    @pytest.mark.asyncio
    async def test_match_case(self):
        ex = SwitchExecutor()
        result = await ex.execute(_ctx(), {
            "input": "high",
            "cases": [
                {"when": "low", "then": 10},
                {"when": "medium", "then": 50},
                {"when": "high", "then": 100},
            ],
            "default": 0,
        })
        assert result.output_data["matched"] is True
        assert result.output_data["value"] == 100
        assert result.output_data["matched_case"] == "high"

    @pytest.mark.asyncio
    async def test_default_when_no_match(self):
        ex = SwitchExecutor()
        result = await ex.execute(_ctx(), {
            "input": "unknown",
            "cases": [{"when": "x", "then": 1}],
            "default": 999,
        })
        assert result.output_data["matched"] is False
        assert result.output_data["value"] == 999

    @pytest.mark.asyncio
    async def test_resolves_input_from_upstream(self):
        ex = SwitchExecutor()
        ctx = _ctx(prior_outputs={"score_node": {"band": "high"}})
        result = await ex.execute(ctx, {
            "input": "$.score_node.band",
            "cases": [{"when": "high", "then": "escalate"}],
            "default": "ignore",
        })
        assert result.output_data["value"] == "escalate"

    @pytest.mark.asyncio
    async def test_invalid_cases_type_raises(self):
        ex = SwitchExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"input": "x", "cases": "not a list"})


# ─── aggregate ──────────────────────────────────────────────────────


class TestAggregate:
    @pytest.mark.asyncio
    async def test_sum_no_group(self):
        ex = AggregateExecutor()
        ctx = _ctx(prior_outputs={"u": {"rows": [
            {"amount": 100, "category": "food"},
            {"amount": 50, "category": "food"},
            {"amount": 200, "category": "fuel"},
        ]}})
        result = await ex.execute(ctx, {
            "rows": "$.u.rows", "fn": "sum", "metric": "amount",
        })
        assert result.output_data["groups"] == [{"key": None, "value": 350}]
        assert result.output_data["total_rows"] == 3

    @pytest.mark.asyncio
    async def test_count_grouped(self):
        ex = AggregateExecutor()
        ctx = _ctx(prior_outputs={"u": {"rows": [
            {"category": "a"}, {"category": "b"}, {"category": "a"},
        ]}})
        result = await ex.execute(ctx, {
            "rows": "$.u.rows", "fn": "count", "group_by": "category",
        })
        groups = {g["key"]: g["value"] for g in result.output_data["groups"]}
        assert groups == {"a": 2, "b": 1}

    @pytest.mark.asyncio
    async def test_avg_with_metric(self):
        ex = AggregateExecutor()
        ctx = _ctx(prior_outputs={"u": {"rows": [
            {"score": 80}, {"score": 90}, {"score": 70},
        ]}})
        result = await ex.execute(ctx, {
            "rows": "$.u.rows", "fn": "avg", "metric": "score",
        })
        assert result.output_data["groups"][0]["value"] == 80.0

    @pytest.mark.asyncio
    async def test_empty_rows(self):
        ex = AggregateExecutor()
        result = await ex.execute(_ctx(), {
            "rows": [], "fn": "sum", "metric": "amount",
        })
        assert result.output_data["total_rows"] == 0
        assert result.output_data["groups"][0]["value"] == 0

    @pytest.mark.asyncio
    async def test_unknown_fn_raises(self):
        ex = AggregateExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "rows": [], "fn": "stddev", "metric": "x",
            })

    @pytest.mark.asyncio
    async def test_metric_required_for_non_count(self):
        ex = AggregateExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"rows": [{"x": 1}], "fn": "sum"})


# ─── side_effect_class declarations ─────────────────────────────────


class TestSideEffectClass:
    def test_pure_executors(self):
        assert IfElseExecutor.side_effect_class == SideEffectClass.PURE
        assert SwitchExecutor.side_effect_class == SideEffectClass.PURE
        assert AggregateExecutor.side_effect_class == SideEffectClass.PURE

    def test_external_send_email(self):
        from workflow_runtime.executors.external import SendEmailExecutor
        assert SendEmailExecutor.side_effect_class == SideEffectClass.EXTERNAL

    def test_data_executors(self):
        from workflow_runtime.executors.data import (
            ReadTableExecutor, UpdateRecordExecutor,
        )
        assert ReadTableExecutor.side_effect_class == SideEffectClass.READ_ONLY
        assert UpdateRecordExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT


# ─── data executors: input validation (without DB) ──────────────────


class TestDataExecutorsValidation:
    @pytest.mark.asyncio
    async def test_read_table_rejects_unknown_table(self):
        from workflow_runtime.executors.data import ReadTableExecutor
        ex = ReadTableExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"table": "pg_admin_users"})

    @pytest.mark.asyncio
    async def test_read_table_rejects_bad_column_name(self):
        from workflow_runtime.executors.data import ReadTableExecutor
        ex = ReadTableExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "table": "silver_customers",
                "columns": ["valid_col", "bad; DROP TABLE"],
            })

    @pytest.mark.asyncio
    async def test_read_table_rejects_bad_limit(self):
        from workflow_runtime.executors.data import ReadTableExecutor
        ex = ReadTableExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "table": "silver_customers", "limit": 99999,
            })

    @pytest.mark.asyncio
    async def test_update_record_rejects_unknown_table(self):
        from workflow_runtime.executors.data import UpdateRecordExecutor
        ex = UpdateRecordExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "table": "silver_transactions",  # not in UPDATABLE_COLUMNS
                "pk_col": "id", "pk_value": "x", "set": {"x": 1},
            })

    @pytest.mark.asyncio
    async def test_update_record_rejects_disallowed_column(self):
        from workflow_runtime.executors.data import UpdateRecordExecutor
        ex = UpdateRecordExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "table": "tenant_interventions",
                "pk_col": "intervention_id",
                "pk_value": uuid4(),
                "set": {"password_hash": "leaked"},  # not in allowed cols
            })


class TestSendEmailValidation:
    @pytest.mark.asyncio
    async def test_invalid_email_raises(self):
        from workflow_runtime.executors.external import SendEmailExecutor
        ex = SendEmailExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "to": "not-an-email", "subject": "x", "body": "y",
            })

    @pytest.mark.asyncio
    async def test_empty_subject_raises(self):
        from workflow_runtime.executors.external import SendEmailExecutor
        ex = SendEmailExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "to": "a@b.com", "subject": "", "body": "y",
            })

    @pytest.mark.asyncio
    async def test_oversized_subject_raises(self):
        from workflow_runtime.executors.external import SendEmailExecutor
        ex = SendEmailExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "to": "a@b.com", "subject": "x" * 201, "body": "y",
            })
