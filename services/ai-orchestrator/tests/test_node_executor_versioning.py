"""Tests for ADR-0034 B3 node type_version — registry version-aware lookup.

get_versioned resolves an exact (key, version) and falls back to the key's
registered executor when that version isn't present (the case until a real v2
ships). The existing key-only has()/get()/list_keys() are unchanged.
"""
import pytest

from ai_orchestrator.workflow_runtime.node_executor import (
    NodeExecutor,
    NodeExecutorRegistry,
    NodeResult,
)
from ai_orchestrator.workflow_runtime.side_effect import SideEffectClass


class _V1(NodeExecutor):
    node_type_key = "demo"
    side_effect_class = SideEffectClass.PURE
    type_version = 1

    async def execute(self, ctx, config):
        return NodeResult(status="completed", output_data={})


class _V2(NodeExecutor):
    node_type_key = "demo"
    side_effect_class = SideEffectClass.PURE
    type_version = 2

    async def execute(self, ctx, config):
        return NodeResult(status="completed", output_data={})


def test_type_version_defaults_to_one():
    class _NoVer(NodeExecutor):
        node_type_key = "x"
        side_effect_class = SideEffectClass.PURE

        async def execute(self, ctx, config):
            return NodeResult(status="completed", output_data={})

    assert _NoVer().type_version == 1          # default class attr


def test_get_versioned_falls_back_when_only_v1():
    reg = NodeExecutorRegistry()
    v1 = _V1()
    reg.register(v1)
    assert reg.get_versioned("demo", 1) is v1
    assert reg.get_versioned("demo", 2) is v1  # no v2 yet → fall back, never breaks


def test_get_versioned_exact_when_both_registered():
    reg = NodeExecutorRegistry()
    v1, v2 = _V1(), _V2()
    reg.register(v1)
    reg.register(v2)
    assert reg.get_versioned("demo", 1) is v1  # exact v1
    assert reg.get_versioned("demo", 2) is v2  # exact v2


def test_key_only_api_unchanged():
    reg = NodeExecutorRegistry()
    reg.register(_V1())
    assert reg.has("demo") is True
    assert reg.list_keys() == ["demo"]         # versioning didn't change key-only views
    assert reg.coverage_report(["demo", "other"]) == {
        "registered": ["demo"], "missing": ["other"],
    }
