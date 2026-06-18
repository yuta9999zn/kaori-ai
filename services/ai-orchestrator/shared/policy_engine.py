"""
Policy engine — declarative rule evaluator.

P3 of Phase 2.7 (per anh's review §3D "Policy engine"). Replaces ad-hoc
K-rule checks scattered across business code with a centralised
declarative rule registry.

API
---
  evaluate(context)         — evaluate ALL active rules against the
                                context, return the first match per
                                action priority. Returns PolicyDecision.
  list_rules(scope=...)     — admin tool to inspect active rules.
  reload_cache()            — force refresh after a manual mig 099 update.

Rule format (DB row):
  rule_key:        unique identifier (k4_consent_external_required)
  scope:           global | tenant | role
  priority:        int — lower = evaluated first
  condition_json:  {field, op, value} or compound {and/or: [...]}
  action:          allow | deny | require_approval | rate_limit | audit
  action_params:   action-specific config (reason / required_role / etc.)

The condition is evaluated against the caller-supplied context dict.
Supported ops: == != > >= < <= in notin. Compound: and / or.
"""
from __future__ import annotations

import asyncio
import json
import operator
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

log = structlog.get_logger()


# ─── Result shape ────────────────────────────────────────────────


@dataclass(frozen=True)
class PolicyDecision:
    """Evaluation outcome — caller acts on `action`."""
    matched:        bool
    action:         str           # 'allow' if no match
    rule_key:       Optional[str]  # which rule matched
    reason:         str
    action_params:  dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyRule:
    rule_id:         str
    rule_key:        str
    description:     str
    scope:           str
    priority:        int
    condition:       dict[str, Any]
    action:          str
    action_params:   dict[str, Any]
    metadata:        dict[str, Any]
    enabled:         bool


# ─── Condition evaluator (pure) ──────────────────────────────────


_OPS = {
    "==":    operator.eq,
    "!=":    operator.ne,
    ">":     operator.gt,
    ">=":    operator.ge,
    "<":     operator.lt,
    "<=":    operator.le,
    "in":    lambda a, b: a in b if b is not None else False,
    "notin": lambda a, b: a not in b if b is not None else True,
}


def evaluate_condition(condition: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Pure recursive condition evaluator. Same shape as workflow
    if_else conditions but reads from a flat context dict (no $.refs)."""
    if "and" in condition:
        return all(evaluate_condition(c, ctx) for c in condition["and"])
    if "or" in condition:
        return any(evaluate_condition(c, ctx) for c in condition["or"])

    field = condition.get("field")
    op = condition.get("op")
    value = condition.get("value")

    if field is None or op not in _OPS:
        return False

    left = ctx.get(field) if field != "value" else value
    if field is not None and op in _OPS:
        try:
            return bool(_OPS[op](left, value))
        except TypeError:
            return False
    return False


# ─── Cache + DB load ─────────────────────────────────────────────


_RULE_CACHE: Optional[list[PolicyRule]] = None
_CACHE_LOADED_AT: float = 0.0
_CACHE_TTL_S: float = 60.0


async def _load_rules_from_db() -> list[PolicyRule]:
    """Load enabled rules from policy_rules table, sorted by priority asc.
    Cached for _CACHE_TTL_S seconds — admins can force reload via
    reload_cache()."""
    from ai_orchestrator.shared.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT rule_id, rule_key, description, scope, priority,
                      condition_json, action, action_params, metadata, enabled
               FROM policy_rules
               WHERE enabled = TRUE
               ORDER BY priority ASC, rule_key"""
        )

    out: list[PolicyRule] = []
    for r in rows:
        cond = r["condition_json"]
        if isinstance(cond, str):
            try:
                cond = json.loads(cond) if cond else {}
            except json.JSONDecodeError:
                cond = {}
        ap = r["action_params"]
        if isinstance(ap, str):
            try:
                ap = json.loads(ap) if ap else {}
            except json.JSONDecodeError:
                ap = {}
        md = r["metadata"]
        if isinstance(md, str):
            try:
                md = json.loads(md) if md else {}
            except json.JSONDecodeError:
                md = {}
        out.append(PolicyRule(
            rule_id=str(r["rule_id"]),
            rule_key=r["rule_key"],
            description=r["description"],
            scope=r["scope"],
            priority=r["priority"],
            condition=cond or {},
            action=r["action"],
            action_params=ap or {},
            metadata=md or {},
            enabled=r["enabled"],
        ))
    return out


async def _get_rules() -> list[PolicyRule]:
    global _RULE_CACHE, _CACHE_LOADED_AT
    now = time.monotonic()
    if _RULE_CACHE is None or (now - _CACHE_LOADED_AT) > _CACHE_TTL_S:
        try:
            _RULE_CACHE = await _load_rules_from_db()
            _CACHE_LOADED_AT = now
        except Exception:  # noqa: BLE001
            log.exception("policy_engine.cache_reload_failed")
            if _RULE_CACHE is None:
                _RULE_CACHE = []
    return _RULE_CACHE


def reload_cache() -> None:
    """Test hook / admin force-reload after manual rule mutation."""
    global _RULE_CACHE, _CACHE_LOADED_AT
    _RULE_CACHE = None
    _CACHE_LOADED_AT = 0.0


def set_cache(rules: list[PolicyRule]) -> None:
    """Test hook — inject rules directly to bypass DB."""
    global _RULE_CACHE, _CACHE_LOADED_AT
    _RULE_CACHE = list(rules)
    _CACHE_LOADED_AT = time.monotonic()


# ─── Top-level API ──────────────────────────────────────────────


async def evaluate(context: dict[str, Any]) -> PolicyDecision:
    """Walk rules in priority order; return the first match.

    Context shape (caller fills what's relevant):
      enterprise_id, role, mfa_enabled, consent_external,
      department_type, node_type_key, amount_vnd, ...

    No-match → PolicyDecision(matched=False, action='allow', rule_key=None).
    """
    rules = await _get_rules()
    for rule in rules:
        # Scope filter: tenant/role rules need their metadata to match
        if rule.scope == "tenant":
            target = rule.metadata.get("enterprise_id")
            if target and str(context.get("enterprise_id")) != str(target):
                continue
        elif rule.scope == "role":
            target_role = rule.metadata.get("required_role")
            if target_role and context.get("role") != target_role:
                continue
        if evaluate_condition(rule.condition, context):
            log.info("policy.matched",
                      rule_key=rule.rule_key, action=rule.action,
                      enterprise_id=str(context.get("enterprise_id")))
            return PolicyDecision(
                matched=True,
                action=rule.action,
                rule_key=rule.rule_key,
                reason=rule.action_params.get("reason") or rule.description,
                action_params=rule.action_params,
            )
    return PolicyDecision(
        matched=False, action="allow", rule_key=None,
        reason="no rule matched",
    )


async def list_rules(scope: Optional[str] = None) -> list[PolicyRule]:
    """Admin introspection."""
    rules = await _get_rules()
    if scope is None:
        return list(rules)
    return [r for r in rules if r.scope == scope]
