"""Robustness regression tests (audit §12 follow-up, 2026-05-30).

Covers the silent-wrong-result / fail-loud hardening:
  • _resolve returns a SKIPPED sentinel for refs into a skipped node; data
    executors fail loud instead of silently treating it as [].
  • numeric-string coercion in ordering conditions + aggregate (JSONB-as-string).
  • switch case-insensitive + numeric-aware matching.
  • filter logs (and counts) rows dropped on a bad predicate.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from ai_orchestrator.workflow_runtime.node_executor import (
    NodeContext, NodeExecutorError,
)
from ai_orchestrator.workflow_runtime.executors.pure import (
    SKIPPED, AggregateExecutor, IfElseExecutor, SwitchExecutor,
    _case_matches, _coerce_numeric_pair, _resolve, _to_number, require_rows,
)
from ai_orchestrator.workflow_runtime.executors.utility import FilterExecutor


def _ctx(prior=None, inp=None):
    return NodeContext(
        enterprise_id=uuid4(), workspace_id=uuid4(), workflow_id=uuid4(),
        run_id=uuid4(), node_id=uuid4(), user_id=None,
        input_data=inp or {}, prior_outputs=prior or {},
    )


# ── _resolve skipped sentinel ────────────────────────────────────────────────

class TestSkippedSentinel:

    def test_resolve_returns_sentinel_for_skipped_node(self):
        ctx = _ctx(prior={"X": {"__skipped__": True}})
        assert _resolve("$.X.rows", ctx) is SKIPPED
        assert _resolve("$.X", ctx) is SKIPPED

    def test_resolve_none_for_absent_node(self):
        ctx = _ctx(prior={})
        assert _resolve("$.X.rows", ctx) is None      # absent ≠ skipped

    def test_require_rows_raises_on_skipped(self):
        ctx = _ctx(prior={"X": {"__skipped__": True}})
        with pytest.raises(NodeExecutorError):
            require_rows("$.X.rows", ctx, "agg.rows")

    def test_require_rows_empty_for_none(self):
        ctx = _ctx(prior={})
        assert require_rows("$.X.rows", ctx) == []

    @pytest.mark.asyncio
    async def test_aggregate_reading_skipped_fails_loud(self):
        ctx = _ctx(prior={"Dead": {"__skipped__": True}})
        with pytest.raises(NodeExecutorError):
            await AggregateExecutor().execute(
                ctx, {"rows": "$.Dead.rows", "metric": "amount", "fn": "sum"})


# ── numeric-string coercion ──────────────────────────────────────────────────

class TestNumericCoercion:

    def test_to_number(self):
        assert _to_number("42") == 42
        assert _to_number("3.5") == 3.5
        assert _to_number(7) == 7
        assert _to_number(True) is None     # bool is not a number here
        assert _to_number("abc") is None

    def test_coerce_pair_only_when_string_present(self):
        assert _coerce_numeric_pair("42", 80) == (42, 80)
        assert _coerce_numeric_pair(100, "80") == (100, 80)
        assert _coerce_numeric_pair(1, 2) == (1, 2)          # both numeric → untouched
        assert _coerce_numeric_pair("a", 2) == ("a", 2)      # non-numeric → untouched

    @pytest.mark.asyncio
    async def test_if_else_string_score_compares_numerically(self):
        ctx = _ctx(inp={"score": "90"})           # JSONB-style string
        r = await IfElseExecutor().execute(
            ctx, {"condition": {"left": "$.input.score", "op": ">=", "right": 80}})
        assert r.output_data["branch"] == "true"  # '90' >= 80 numerically

    @pytest.mark.asyncio
    async def test_aggregate_sums_numeric_strings(self):
        ctx = _ctx(inp={"rows": [{"amount": "100"}, {"amount": "200"}]})
        r = await AggregateExecutor().execute(
            ctx, {"rows": "$.input.rows", "metric": "amount", "fn": "sum"})
        assert r.output_data["groups"][0]["value"] == 300   # not silently 0


# ── switch case-insensitive / numeric ────────────────────────────────────────

class TestSwitchMatching:

    def test_case_matches_helper(self):
        assert _case_matches("Gold", "gold") is True
        assert _case_matches(5, "5") is True
        assert _case_matches("a", "b") is False

    @pytest.mark.asyncio
    async def test_switch_case_insensitive(self):
        ctx = _ctx(inp={"tier": "GOLD"})
        r = await SwitchExecutor().execute(ctx, {
            "input": "$.input.tier",
            "cases": [{"when": "gold", "then": 1}], "default": 0})
        assert r.output_data["matched"] is True
        assert r.output_data["value"] == 1


# ── filter logs + counts dropped on bad predicate ────────────────────────────

class TestFilterObservability:

    @pytest.mark.asyncio
    async def test_filter_drops_and_counts_bad_predicate(self):
        ctx = _ctx(inp={"rows": [{"a": 1}, {"a": 2}]})
        r = await FilterExecutor().execute(ctx, {
            "rows": "$.input.rows",
            "condition": {"left": "$._row.a", "op": "BOGUS", "right": 1}})
        # unknown op → every row dropped (counted), run doesn't crash
        assert r.output_data["dropped"] == 2
        assert r.output_data["rows"] == []

    @pytest.mark.asyncio
    async def test_filter_reading_skipped_fails_loud(self):
        ctx = _ctx(prior={"Dead": {"__skipped__": True}})
        with pytest.raises(NodeExecutorError):
            await FilterExecutor().execute(
                ctx, {"rows": "$.Dead.rows",
                       "condition": {"left": "$._row.a", "op": ">", "right": 0}})
