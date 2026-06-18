"""
Tool-call loop guardrail tests (DPEPO depth/width penalty pattern).

Validates `chat/tool_necessity.py` loop-guardrail section. Borrowed
from arXiv DPEPO 2026 (LePanda026/Code-for-DPEPO) — see ADR-0023 Alt 5
and the `Tool-call loop guardrail` block in tool_necessity.py for the
mapping rationale.

6-section template:
  1. args_fingerprint — stability + arg-order independence
  2. Depth dimension — consecutive same-tool revisits
  3. Width dimension — any-position same-tool-and-args duplicates
  4. Penalty formula — exponent decay correctness
  5. Abort threshold — should_abort behaviour
  6. Determinism + performance
"""
from __future__ import annotations

import time

import pytest

from ai_orchestrator.chat.tool_necessity import (
    DEPTH_ALPHA,
    LOOP_ABORT_THRESHOLD,
    WIDTH_OMEGA,
    LoopPenaltyAssessment,
    ToolCall,
    args_fingerprint,
    assess_tool_call_loop,
)


def _call(tool: str, args: dict, hop: int = 0) -> ToolCall:
    return ToolCall(
        tool_name=tool,
        args_fingerprint=args_fingerprint(args),
        hop=hop,
    )


# ═════════════════════════════════════════════════════════════════════
# 1. args_fingerprint
# ═════════════════════════════════════════════════════════════════════


class TestArgsFingerprint:

    def test_same_args_same_fingerprint(self):
        assert args_fingerprint({"a": 1}) == args_fingerprint({"a": 1})

    def test_key_order_irrelevant(self):
        assert args_fingerprint({"a": 1, "b": 2}) == args_fingerprint({"b": 2, "a": 1})

    def test_different_values_different_fingerprint(self):
        assert args_fingerprint({"a": 1}) != args_fingerprint({"a": 2})

    def test_empty_args_stable(self):
        fp = args_fingerprint({})
        assert isinstance(fp, str)
        assert len(fp) == 16
        assert fp == args_fingerprint({})

    def test_nonjsonable_args_dont_crash(self):
        # default=str handles dates / UUIDs / Decimals
        import datetime
        fp = args_fingerprint({"when": datetime.date(2026, 5, 21), "n": 42})
        assert isinstance(fp, str) and len(fp) == 16


# ═════════════════════════════════════════════════════════════════════
# 2. Depth dimension — consecutive revisits
# ═════════════════════════════════════════════════════════════════════


class TestDepthDimension:

    def test_empty_history_depth_zero(self):
        a = assess_tool_call_loop(
            tool_name="list_customers", args={}, history=[],
        )
        assert a.depth_count == 0
        assert a.depth_penalty == pytest.approx(1.0)

    def test_one_prior_same_tool_depth_one(self):
        history = [_call("list_customers", {"limit": 10})]
        a = assess_tool_call_loop(
            tool_name="list_customers", args={"limit": 20}, history=history,
        )
        assert a.depth_count == 1

    def test_three_consecutive_depth_three(self):
        history = [_call("list_customers", {"limit": i}) for i in (10, 20, 30)]
        a = assess_tool_call_loop(
            tool_name="list_customers", args={"limit": 40}, history=history,
        )
        assert a.depth_count == 3

    def test_intermediate_other_tool_breaks_depth_chain(self):
        history = [
            _call("list_customers", {"limit": 10}),
            _call("get_revenue", {}),                # breaks chain
            _call("list_customers", {"limit": 20}),
        ]
        a = assess_tool_call_loop(
            tool_name="list_customers", args={"limit": 30}, history=history,
        )
        # only the most-recent run counts — last 1 entry is same tool
        assert a.depth_count == 1


# ═════════════════════════════════════════════════════════════════════
# 3. Width dimension — any-position duplicates with identical args
# ═════════════════════════════════════════════════════════════════════


class TestWidthDimension:

    def test_no_duplicates_width_zero(self):
        history = [_call("list_customers", {"limit": 10})]
        a = assess_tool_call_loop(
            tool_name="list_customers", args={"limit": 20}, history=history,
        )
        assert a.width_count == 0

    def test_one_duplicate_width_one(self):
        history = [_call("list_customers", {"limit": 10})]
        a = assess_tool_call_loop(
            tool_name="list_customers", args={"limit": 10}, history=history,
        )
        assert a.width_count == 1

    def test_args_order_irrelevant_for_width(self):
        history = [_call("list_customers", {"limit": 10, "filter": "vip"})]
        a = assess_tool_call_loop(
            tool_name="list_customers",
            args={"filter": "vip", "limit": 10},  # same args, reordered
            history=history,
        )
        assert a.width_count == 1

    def test_different_tool_same_args_not_a_width_duplicate(self):
        history = [_call("get_revenue", {"month": "2026-05"})]
        a = assess_tool_call_loop(
            tool_name="get_costs", args={"month": "2026-05"}, history=history,
        )
        assert a.width_count == 0

    def test_width_counts_across_intervening_tools(self):
        history = [
            _call("list_customers", {"limit": 10}),
            _call("get_revenue", {}),
            _call("list_customers", {"limit": 10}),
        ]
        a = assess_tool_call_loop(
            tool_name="list_customers", args={"limit": 10}, history=history,
        )
        assert a.width_count == 2


# ═════════════════════════════════════════════════════════════════════
# 4. Penalty formula — geometric decay
# ═════════════════════════════════════════════════════════════════════


class TestPenaltyFormula:

    def test_zero_counts_full_penalty_one(self):
        a = assess_tool_call_loop(tool_name="t", args={}, history=[])
        assert a.depth_penalty == pytest.approx(1.0)
        assert a.width_penalty == pytest.approx(1.0)
        assert a.combined_penalty == pytest.approx(1.0)

    def test_depth_penalty_decays_geometrically(self):
        history = [_call("t", {"i": i}) for i in range(3)]
        a = assess_tool_call_loop(tool_name="t", args={"i": 99}, history=history)
        # depth=3, width=0
        assert a.depth_penalty == pytest.approx(DEPTH_ALPHA ** 3)
        assert a.width_penalty == pytest.approx(1.0)

    def test_width_penalty_decays_geometrically(self):
        history = [_call("t", {"i": 1}), _call("u", {}), _call("t", {"i": 1})]
        a = assess_tool_call_loop(tool_name="t", args={"i": 1}, history=history)
        # width=2 (two priors with same tool+args)
        # depth=1 (the most-recent entry is also "t")
        assert a.width_penalty == pytest.approx(WIDTH_OMEGA ** 2)

    def test_combined_is_product(self):
        history = [
            _call("t", {"i": 1}),
            _call("t", {"i": 1}),
            _call("t", {"i": 1}),
        ]
        a = assess_tool_call_loop(tool_name="t", args={"i": 1}, history=history)
        assert a.combined_penalty == pytest.approx(a.depth_penalty * a.width_penalty)

    def test_custom_alpha_omega_overrides(self):
        history = [_call("t", {}), _call("t", {})]
        a = assess_tool_call_loop(
            tool_name="t", args={}, history=history,
            depth_alpha=0.5, width_omega=0.5,
        )
        # depth=2 → 0.25; width=2 → 0.25; combined = 0.0625
        assert a.depth_penalty == pytest.approx(0.25)
        assert a.width_penalty == pytest.approx(0.25)


# ═════════════════════════════════════════════════════════════════════
# 5. Abort threshold
# ═════════════════════════════════════════════════════════════════════


class TestAbortThreshold:

    def test_clean_call_does_not_abort(self):
        a = assess_tool_call_loop(tool_name="t", args={}, history=[])
        assert a.should_abort is False
        assert "OK" in a.reason

    def test_three_consecutive_revisits_trips_abort(self):
        # depth=3 with default α=0.7 → 0.343 < 0.3? actually 0.343 > 0.3
        # but 4 revisits = 0.2401 < 0.3 → abort
        history = [_call("t", {"i": i}) for i in range(4)]
        a = assess_tool_call_loop(tool_name="t", args={"i": 99}, history=history)
        assert a.depth_count == 4
        assert a.combined_penalty < LOOP_ABORT_THRESHOLD
        assert a.should_abort is True
        assert "loop guardrail tripped" in a.reason

    def test_width_alone_can_trip_abort(self):
        # 6 same-tool-same-args duplicates with intervening: width=6,
        # depth=1 because only the most-recent matches; combined =
        # 0.7 * 0.8^6 = 0.183 < 0.3
        history = []
        for _ in range(6):
            history.append(_call("t", {"i": 1}))
            history.append(_call("other", {}))
        a = assess_tool_call_loop(tool_name="t", args={"i": 1}, history=history)
        assert a.width_count == 6
        assert a.depth_count == 0  # last entry is "other"
        assert a.should_abort is True

    def test_custom_threshold(self):
        # depth=1 → 0.7. Default doesn't abort. Custom threshold=0.8 aborts.
        history = [_call("t", {})]
        a = assess_tool_call_loop(
            tool_name="t", args={"k": 1}, history=history,
            abort_threshold=0.8,
        )
        assert a.should_abort is True


# ═════════════════════════════════════════════════════════════════════
# 6. Determinism + performance
# ═════════════════════════════════════════════════════════════════════


class TestDeterminismAndPerformance:

    def test_same_input_same_output(self):
        history = [_call("t", {"i": 1}), _call("t", {"i": 2})]
        a1 = assess_tool_call_loop(tool_name="t", args={"i": 3}, history=history)
        a2 = assess_tool_call_loop(tool_name="t", args={"i": 3}, history=history)
        assert a1 == a2

    def test_returns_frozen_dataclass(self):
        a = assess_tool_call_loop(tool_name="t", args={}, history=[])
        assert isinstance(a, LoopPenaltyAssessment)
        with pytest.raises((AttributeError, Exception)):
            a.depth_count = 99  # type: ignore[misc]

    def test_1000_assessments_under_100ms(self):
        history = [_call("t", {"i": i}) for i in range(20)]
        t0 = time.perf_counter()
        for _ in range(1000):
            assess_tool_call_loop(tool_name="t", args={"i": 999}, history=history)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"1000 assessments took {elapsed*1000:.1f}ms"
