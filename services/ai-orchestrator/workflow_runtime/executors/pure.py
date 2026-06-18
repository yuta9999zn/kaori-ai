"""
Pure-compute executors — no I/O, no DB, no LLM.

K-17 side_effect_class = pure. Retry freely, no idempotency dedup,
no compensation needed. Deterministic over (input_data, config).

Executors:
  IfElseExecutor      — 2-way branch by condition
  SwitchExecutor      — N-way branch by case match
  AggregateExecutor   — group-by + sum/count/avg/min/max over a list
"""
from __future__ import annotations

import operator
from typing import Any, Optional

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass

log = structlog.get_logger()

# Marker the runner stores in prior_outputs for a node it SKIPPED (dead branch).
SKIPPED_MARKER = "__skipped__"


class _SkippedRef:
    """Sentinel _resolve returns when a $.ref points at a SKIPPED upstream node.
    Distinct from None (genuinely-null value / absent field) so a data executor
    can fail loud instead of silently treating a dead-branch input as empty."""
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "<skipped-upstream>"


SKIPPED = _SkippedRef()


def require_rows(value: Any, ctx: "NodeContext", field: str = "rows") -> list:
    """Resolve a $.ref expected to be a list of rows. Reading from a SKIPPED
    upstream node raises (fail loud); None/absent → [] (genuinely empty)."""
    v = _resolve(value, ctx)
    if v is SKIPPED:
        raise NodeExecutorError(
            f"{field} reads from an upstream node that was skipped (dead branch)")
    if v is None:
        return []
    if not isinstance(v, list):
        raise NodeExecutorError(f"{field} must resolve to a list")
    return v


def _resolve(value: Any, ctx: NodeContext) -> Any:
    """Resolve a value reference. ``$.nodeId.field`` pulls from a prior node's
    output; ``$.input.field`` pulls from the run input (so a gateway condition
    lifted from BPMN, e.g. left='$.input.score', resolves against the trigger
    payload). Non-'$.' values are returned as-is. Empty/None → None. If the
    referenced node was SKIPPED, returns the SKIPPED sentinel."""
    if not isinstance(value, str) or not value.startswith("$."):
        return value
    path = value[2:].split(".")
    if not path:
        return None
    node_id = path[0]
    if node_id == "input":
        cur: Any = ctx.input_data
    else:
        cur = ctx.prior_outputs.get(node_id)
        # A skipped node's output is the runner's skip marker — surface it as
        # the SKIPPED sentinel rather than letting callers read off a {}.
        if isinstance(cur, dict) and cur.get(SKIPPED_MARKER) is True:
            return SKIPPED
    for part in path[1:]:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _to_number(x: Any) -> Optional[float]:
    """int/float (not bool) → as-is; numeric string → number; else None."""
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return x
    if isinstance(x, str):
        s = x.strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None
    return None


def _coerce_numeric_pair(a: Any, b: Any) -> tuple[Any, Any]:
    """For ordering comparisons: if BOTH operands are numerically comparable and
    at least one is a string (e.g. JSONB returned '42'), compare as numbers.
    Leaves non-numeric operands untouched."""
    na, nb = _to_number(a), _to_number(b)
    if na is not None and nb is not None and (isinstance(a, str) or isinstance(b, str)):
        return na, nb
    return a, b


def _case_matches(when: Any, switch_on: Any) -> bool:
    """switch case match — case-insensitive for strings, numeric-aware for
    string↔number, so a 'Gold' case matches input 'gold' and a 5 case matches
    input '5'. Aligns the executor with the runner's branch-gating, which
    lowercases the edge token."""
    if isinstance(when, str) and isinstance(switch_on, str):
        return when.strip().lower() == switch_on.strip().lower()
    nw, ns = _to_number(when), _to_number(switch_on)
    if nw is not None and ns is not None and (isinstance(when, str) or isinstance(switch_on, str)):
        return nw == ns
    return when == switch_on


_OPS = {
    "==":   operator.eq,
    "!=":   operator.ne,
    ">":    operator.gt,
    ">=":   operator.ge,
    "<":    operator.lt,
    "<=":   operator.le,
    "in":   lambda a, b: a in b if b is not None else False,
    "notin": lambda a, b: a not in b if b is not None else True,
}


def _eval_condition(condition: dict[str, Any], ctx: NodeContext) -> bool:
    """Evaluate a leaf condition {left, op, right}. Compound expressions
    {and: [...], or: [...]} recurse.

    Raises NodeExecutorError on unknown op."""
    if "and" in condition:
        return all(_eval_condition(c, ctx) for c in condition["and"])
    if "or" in condition:
        return any(_eval_condition(c, ctx) for c in condition["or"])

    op = condition.get("op")
    if op not in _OPS:
        raise NodeExecutorError(f"Unknown op in condition: {op!r}")
    left = _resolve(condition.get("left"), ctx)
    right = _resolve(condition.get("right"), ctx)
    # A reference into a skipped branch is treated as None here (the condition
    # simply doesn't hold) rather than raising mid-evaluation.
    if left is SKIPPED:
        left = None
    if right is SKIPPED:
        right = None
    # Ordering comparisons: coerce numeric strings (e.g. JSONB-returned '42')
    # so `'42' >= 80` compares as numbers, not lexically / not a type error.
    if op in (">", ">=", "<", "<="):
        left, right = _coerce_numeric_pair(left, right)
    try:
        return bool(_OPS[op](left, right))
    except TypeError as e:
        # E.g. comparing None with int — return False, log for debugging.
        log.warning("condition.type_mismatch",
                    op=op, left_type=type(left).__name__,
                    right_type=type(right).__name__, error=str(e))
        return False


class IfElseExecutor(NodeExecutor):
    """if_else — 2-way branch.

    Config:
      condition: {left, op, right} or compound {and: [...]} / {or: [...]}
      true_value:  (optional) value to emit when condition truthy
      false_value: (optional) value to emit when condition falsy
    Output:
      {branch: 'true' | 'false', value: <emitted>}
    """
    node_type_key = "if_else"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        condition = config.get("condition")
        if not isinstance(condition, dict):
            raise NodeExecutorError("if_else.config.condition required (dict)")
        passed = _eval_condition(condition, ctx)
        branch = "true" if passed else "false"
        value = config.get("true_value") if passed else config.get("false_value")
        return NodeResult(
            status="completed",
            output_data={"branch": branch, "value": _resolve(value, ctx),
                          "passed": passed},
        )


class SwitchExecutor(NodeExecutor):
    """switch — N-way branch by case-value match.

    Config:
      input:  $.refOrLiteral  (value to switch on)
      cases:  [{when: <literal>, then: <value>}, ...]           exact match, OR
              [{label: <token>, min: <num>, max: <num>}, ...]   numeric range
              (range matches min <= value < max; either bound optional →
               open-ended. matched_case = label so the outgoing edge token
               'label' routes the run. First matching case wins — order cases
               narrow→wide.)
      default: <value>        (optional — used when no case matches)
    Output:
      {matched_case: <when|label or 'default'>, value: <then>, matched: bool}
    """
    node_type_key = "switch"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        switch_on = _resolve(config.get("input"), ctx)
        if switch_on is SKIPPED:
            switch_on = None
        cases = config.get("cases") or []
        if not isinstance(cases, list):
            raise NodeExecutorError("switch.config.cases must be a list")

        def _primitive(v: Any) -> Any:
            return v if isinstance(v, (str, int, float, bool)) else str(v)

        for case in cases:
            if not isinstance(case, dict):
                continue
            # Numeric range case: {label, min?, max?}.
            if "min" in case or "max" in case:
                val = _to_number(switch_on)
                lo = _to_number(case.get("min"))
                hi = _to_number(case.get("max"))
                if val is None:
                    continue
                if (lo is None or val >= lo) and (hi is None or val < hi):
                    label = case.get("label")
                    mc = label if label is not None else f"{case.get('min')}-{case.get('max')}"
                    return NodeResult(
                        status="completed",
                        output_data={"matched_case": _primitive(mc),
                                     "value": _resolve(case.get("then"), ctx),
                                     "matched": True},
                    )
                continue
            # Exact match case (label overrides `when` as the emitted token).
            when = _resolve(case.get("when"), ctx)
            if _case_matches(when, switch_on):
                token = case.get("label") if case.get("label") is not None else when
                return NodeResult(
                    status="completed",
                    output_data={
                        # primitive-safe matched_case so branch-gating's
                        # str(matched).lower() stays meaningful.
                        "matched_case": _primitive(token),
                        "value": _resolve(case.get("then"), ctx),
                        "matched": True,
                    },
                )
        return NodeResult(
            status="completed",
            output_data={
                "matched_case": "default",
                "value": _resolve(config.get("default"), ctx),
                "matched": False,
            },
        )


_AGG_FNS = {
    "sum":   sum,
    "count": len,
    "avg":   lambda xs: (sum(xs) / len(xs)) if xs else 0,
    "min":   lambda xs: min(xs) if xs else None,
    "max":   lambda xs: max(xs) if xs else None,
}


class AggregateExecutor(NodeExecutor):
    """aggregate — group-by + sum/count/avg/min/max.

    Config:
      rows:    $.upstreamNode.rows  (list of dicts to aggregate)
      group_by: 'column_name'       (optional — None = whole list)
      metric:   'column_name'        (column to aggregate; required unless fn=count)
      fn:       'sum'|'count'|'avg'|'min'|'max'
    Output:
      {groups: [{key: <group_value>, value: <agg>}, ...],
       total_rows: int}
    """
    node_type_key = "aggregate"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        rows = require_rows(config.get("rows"), ctx, "aggregate.rows")
        fn_name = config.get("fn", "count")
        if fn_name not in _AGG_FNS:
            raise NodeExecutorError(
                f"aggregate.config.fn={fn_name!r} not in {sorted(_AGG_FNS.keys())}"
            )
        metric = config.get("metric")
        group_by = config.get("group_by")
        fn = _AGG_FNS[fn_name]

        if group_by is None:
            values = self._extract_values(rows, metric, fn_name)
            return NodeResult(
                status="completed",
                output_data={
                    "groups": [{"key": None, "value": fn(values)}],
                    "total_rows": len(rows),
                    "fn": fn_name,
                },
            )

        buckets: dict[Any, list[Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = row.get(group_by)
            buckets.setdefault(key, []).append(row)
        groups = []
        for key, group_rows in buckets.items():
            values = self._extract_values(group_rows, metric, fn_name)
            groups.append({"key": key, "value": fn(values)})
        return NodeResult(
            status="completed",
            output_data={
                "groups": sorted(groups, key=lambda g: (g["key"] is None, str(g["key"]))),
                "total_rows": len(rows),
                "fn": fn_name,
            },
        )

    @staticmethod
    def _extract_values(rows: list[Any], metric: Any, fn_name: str) -> list[Any]:
        if fn_name == "count":
            return list(rows)
        if not metric:
            raise NodeExecutorError(f"aggregate.config.metric required for fn={fn_name}")
        out, dropped = [], 0
        for row in rows:
            if isinstance(row, dict) and metric in row:
                # Coerce numeric strings (e.g. JSONB-returned '100') so a sum
                # over '100','200' is 300, not silently 0.
                n = _to_number(row.get(metric))
                if n is not None:
                    out.append(n)
                else:
                    dropped += 1
        if dropped and not out:
            # All values were non-numeric — surface it; sum([])→0 would mask it.
            log.warning("aggregate.all_values_non_numeric",
                        metric=metric, fn=fn_name, dropped=dropped)
        elif dropped:
            log.warning("aggregate.some_values_dropped",
                        metric=metric, fn=fn_name, dropped=dropped, kept=len(out))
        return out


class NoopExecutor(NodeExecutor):
    """noop — pure pass-through for BPMN flow markers (start/end/intermediate/
    boundary events) that carry no Kaori action. Lets a BPMN-authored workflow
    run end-to-end instead of failing 'No executor for None' on its start event.

    Output: {noop: True} (+ echoes config 'value' if provided).
    """
    node_type_key = "noop"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        return NodeResult(
            status="completed",
            output_data={"noop": True, "value": _resolve(config.get("value"), ctx)},
        )


class LoopForeachExecutor(NodeExecutor):
    """loop_foreach — the runner intercepts this node and runs the body region
    (between it and loop_end) once per item, so execute() is normally never
    called. Registered only so the run pre-flight (REGISTRY.has) passes; the
    fallback is a harmless no-op (e.g. a loop with no body)."""
    node_type_key = "loop_foreach"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        return NodeResult(status="completed", output_data={"iterations": 0})


class LoopEndExecutor(NodeExecutor):
    """loop_end — a marker closing a loop region. The runner skips it (the loop
    owns it); the no-op covers an orphan loop_end."""
    node_type_key = "loop_end"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        return NodeResult(status="completed", output_data={"loop_end": True})
