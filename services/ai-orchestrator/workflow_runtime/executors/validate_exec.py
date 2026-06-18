"""
validate executor — pure JSON Schema validation node.

K-17: PURE. No I/O, no LLM. Deterministic over (data, schema).

Use cases (mig 069):
  C.4 Discount Approval — validate ceiling 0..50%
  D.4 Refund Approval   — policy check (<30 days, valid reason)
  E.5 Warranty Claim    — schema + warranty period check
  F.1 Invoice Approval  — amount ± 5% tolerance
  F.2 Expense Reimburse — per-category caps
  F.5 Budget Approval   — schema + variance vs prior year

Pattern: caller declares schema (subset of JSON Schema draft-07); executor
returns {valid: bool, errors: [...], warnings: [...]}. Branching
downstream uses if_else or switch on `valid`.
"""
from __future__ import annotations

from typing import Any

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


class ValidateExecutor(NodeExecutor):
    """validate — pure JSON Schema validator + extra business rules.

    Config:
      data:        $.upstream.row  (the value to validate — dict or scalar)
      schema:      JSON Schema (object form; supports type/required/
                                enum/minimum/maximum/minLength/maxLength/
                                properties/pattern)
      strict:      True  (default — errors block; False = errors → warnings)
    Output:
      {valid: bool, errors: list[str], warnings: list[str],
       passed_rules: list[str]}
    """
    node_type_key = "validate"
    side_effect_class = SideEffectClass.PURE

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        data = _resolve(config.get("data"), ctx)
        schema = config.get("schema")
        if not isinstance(schema, dict):
            raise NodeExecutorError("validate.schema required (dict)")
        strict = bool(config.get("strict", True))

        errors: list[str] = []
        warnings: list[str] = []
        passed_rules: list[str] = []

        self._validate_value(data, schema, "$", errors, passed_rules)

        if not strict:
            warnings.extend(errors)
            errors = []

        valid = len(errors) == 0
        log.info("validate.done",
                  valid=valid, error_count=len(errors),
                  warning_count=len(warnings),
                  rule_count=len(passed_rules))

        return NodeResult(
            status="completed",
            output_data={
                "valid":         valid,
                "errors":        errors,
                "warnings":      warnings,
                "passed_rules":  passed_rules,
            },
        )

    @classmethod
    def _validate_value(
        cls,
        value: Any,
        schema: dict[str, Any],
        path: str,
        errors: list[str],
        passed: list[str],
    ) -> None:
        """Recursive validator. Pre-emptive returns on errors to keep
        the error list short + actionable."""
        # type
        expected_type = schema.get("type")
        if expected_type:
            if not cls._type_match(value, expected_type):
                errors.append(f"{path}: expected type {expected_type}, "
                               f"got {type(value).__name__}")
                return
            passed.append(f"{path}: type={expected_type}")

        # enum
        enum_vals = schema.get("enum")
        if enum_vals is not None:
            if value not in enum_vals:
                errors.append(f"{path}: value {value!r} not in enum {enum_vals}")
                return
            passed.append(f"{path}: enum-match")

        # numeric range
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minv = schema.get("minimum")
            maxv = schema.get("maximum")
            excl_min = schema.get("exclusiveMinimum")
            excl_max = schema.get("exclusiveMaximum")
            if minv is not None and value < minv:
                errors.append(f"{path}: value {value} < minimum {minv}")
            if maxv is not None and value > maxv:
                errors.append(f"{path}: value {value} > maximum {maxv}")
            if excl_min is not None and value <= excl_min:
                errors.append(f"{path}: value {value} <= exclusiveMinimum {excl_min}")
            if excl_max is not None and value >= excl_max:
                errors.append(f"{path}: value {value} >= exclusiveMaximum {excl_max}")

        # string constraints
        if isinstance(value, str):
            min_len = schema.get("minLength")
            max_len = schema.get("maxLength")
            pattern = schema.get("pattern")
            if min_len is not None and len(value) < min_len:
                errors.append(f"{path}: length {len(value)} < minLength {min_len}")
            if max_len is not None and len(value) > max_len:
                errors.append(f"{path}: length {len(value)} > maxLength {max_len}")
            if pattern is not None:
                import re
                try:
                    if re.search(pattern, value) is None:
                        errors.append(f"{path}: does not match pattern {pattern!r}")
                except re.error as exc:
                    errors.append(f"{path}: pattern {pattern!r} invalid regex: {exc}")

        # array constraints
        if isinstance(value, list):
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if min_items is not None and len(value) < min_items:
                errors.append(f"{path}: length {len(value)} < minItems {min_items}")
            if max_items is not None and len(value) > max_items:
                errors.append(f"{path}: length {len(value)} > maxItems {max_items}")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, item in enumerate(value):
                    cls._validate_value(item, item_schema,
                                         f"{path}[{i}]", errors, passed)

        # object constraints
        if isinstance(value, dict):
            required = schema.get("required") or []
            for key in required:
                if key not in value:
                    errors.append(f"{path}.{key}: required field missing")
            properties = schema.get("properties") or {}
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue
                if prop_name in value:
                    cls._validate_value(
                        value[prop_name], prop_schema,
                        f"{path}.{prop_name}", errors, passed,
                    )

    @staticmethod
    def _type_match(value: Any, expected: str | list[str]) -> bool:
        """JSON Schema type check. Booleans aren't ints in our model."""
        if isinstance(expected, list):
            return any(ValidateExecutor._type_match(value, t) for t in expected)
        if expected == "null":
            return value is None
        if expected == "boolean":
            return isinstance(value, bool)
        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected == "string":
            return isinstance(value, str)
        if expected == "array":
            return isinstance(value, list)
        if expected == "object":
            return isinstance(value, dict)
        return False
