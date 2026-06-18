"""
Sprint 8 — ToolRegistry contract tests.

Cover the four invariants the registry exists to enforce:
  K-12  tenant identifiers in tool args ⇒ refuse dispatch
  K-15  every successful or failed dispatch writes an audit row
  scope gate — P2 caller cannot reach a P1 tool, and vice versa
  role gate — non-platform-admin cannot reach platform tools

DB / audit are stubbed; nothing real runs.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ai_orchestrator.chat.registry import (
    PLATFORM_ROLES_ALLOWED,
    ToolDispatchError,
    ToolRegistry,
    _reset_registry_for_tests,
    get_default_registry,
)
from ai_orchestrator.chat.tools.base import BaseTool, ToolContext


class _OkEnterpriseTool(BaseTool):
    name = "ok_enterprise"
    description = "test"
    scope = "enterprise"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, args, ctx):
        return {"echo": args, "ctx_eid": ctx.enterprise_id}


class _FailingTool(BaseTool):
    name = "failing"
    description = "test"
    scope = "enterprise"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, args, ctx):
        raise RuntimeError("boom")


class _BadArgTool(BaseTool):
    name = "bad_arg"
    description = "test"
    scope = "enterprise"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, args, ctx):
        raise ValueError("days must be > 0")


class _PlatformTool(BaseTool):
    name = "platform_only"
    description = "test"
    scope = "platform"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, args, ctx):
        return {"ok": True}


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(_OkEnterpriseTool)
    reg.register(_FailingTool)
    reg.register(_BadArgTool)
    reg.register(_PlatformTool)
    return reg


@pytest.fixture(autouse=True)
def _reset_default():
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()


# =========================================================================
# Catalog basics
# =========================================================================

def test_default_registry_exposes_v0_tools():
    reg = get_default_registry()
    enterprise_names = {type(t).name for t in reg.list_for_scope("enterprise")}
    platform_names = {type(t).name for t in reg.list_for_scope("platform")}

    # v0 spec: 3 + 3. Names listed in chat/tools/__init__.py
    assert enterprise_names == {
        "summarize_recent_decisions",
        "get_top_at_risk_customers",
        "get_billing_quota_status",
    }
    assert platform_names == {
        "get_platform_summary",
        "count_recent_signups",
        "find_workspaces_in_alert",
    }


def test_openai_format_renders_function_block(registry):
    tools = registry.openai_tools_for_scope("enterprise")
    names = {t["function"]["name"] for t in tools}
    assert "ok_enterprise" in names
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "description" in t["function"]
        assert "parameters" in t["function"]


def test_register_collision_raises():
    reg = ToolRegistry()
    reg.register(_OkEnterpriseTool)
    with pytest.raises(ValueError, match="collision"):
        reg.register(_OkEnterpriseTool)


# =========================================================================
# K-12 — tenant identifiers in args refused
# =========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("leaked", [
    "enterprise_id",
    "tenant_id",
    "workspace_id",
    "user_id",
    "actor_id",
    "admin_id",
])
async def test_dispatch_refuses_tenant_args_k12(registry, leaked):
    ctx = ToolContext(scope="enterprise", enterprise_id="11111111-1111-1111-1111-111111111111")
    with pytest.raises(ToolDispatchError, match="tenant identifiers"):
        await registry.dispatch(
            name="ok_enterprise",
            args={leaked: "00000000-0000-0000-0000-000000000000"},
            ctx=ctx,
        )


# =========================================================================
# Scope + role gates
# =========================================================================

@pytest.mark.asyncio
async def test_scope_mismatch_refused(registry):
    """P2 caller cannot dispatch a P1 tool, even if they know the name."""
    ctx = ToolContext(
        scope="enterprise",
        enterprise_id="11111111-1111-1111-1111-111111111111",
        role="MANAGER",
    )
    with pytest.raises(ToolDispatchError, match="scope=platform"):
        await registry.dispatch(name="platform_only", args={}, ctx=ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["MANAGER", "OPERATOR", "VIEWER", None])
async def test_platform_tool_refuses_non_admin_role(registry, role):
    ctx = ToolContext(scope="platform", role=role)
    with pytest.raises(ToolDispatchError, match="not allowed"):
        await registry.dispatch(name="platform_only", args={}, ctx=ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", sorted(PLATFORM_ROLES_ALLOWED))
async def test_platform_tool_allows_admin_roles(registry, role):
    """SUPER_ADMIN, ADMIN, SUPPORT all allowed (CLAUDE.md §9)."""
    ctx = ToolContext(scope="platform", role=role)
    ok, payload = await registry.dispatch(name="platform_only", args={}, ctx=ctx)
    assert ok is True
    assert payload == {"ok": True}


# =========================================================================
# Error paths surface friendly messages
# =========================================================================

@pytest.mark.asyncio
async def test_value_error_returns_ok_false_with_hint(registry):
    """Tool raises ValueError ⇒ registry returns (False, '<hint>') so the
    LLM can self-correct on the next hop instead of crashing the stream."""
    ctx = ToolContext(scope="enterprise",
                      enterprise_id="11111111-1111-1111-1111-111111111111")
    with patch("ai_orchestrator.chat.registry.audit.log_decision",
               new=AsyncMock(return_value=None)):
        ok, payload = await registry.dispatch(name="bad_arg", args={}, ctx=ctx)
    assert ok is False
    assert "Tham số" in payload


@pytest.mark.asyncio
async def test_unknown_tool_returns_ok_false(registry):
    ctx = ToolContext(scope="enterprise",
                      enterprise_id="11111111-1111-1111-1111-111111111111")
    ok, payload = await registry.dispatch(name="nope", args={}, ctx=ctx)
    assert ok is False
    assert "không tồn tại" in payload


@pytest.mark.asyncio
async def test_unhandled_exception_returns_ok_false(registry):
    """Tool raises a non-ValueError ⇒ registry surfaces a sanitised
    message; the original exception is logged but not leaked."""
    ctx = ToolContext(scope="enterprise",
                      enterprise_id="11111111-1111-1111-1111-111111111111")
    with patch("ai_orchestrator.chat.registry.audit.log_decision",
               new=AsyncMock(return_value=None)):
        ok, payload = await registry.dispatch(name="failing", args={}, ctx=ctx)
    assert ok is False
    assert "Lỗi nội bộ" in payload


# =========================================================================
# K-15 — audit row written on every enterprise dispatch
# =========================================================================

@pytest.mark.asyncio
async def test_dispatch_writes_audit_row_for_enterprise_tool(registry):
    """K-15: every tool invocation must produce an audit row.
    Enterprise scope writes via shared.audit.log_decision → decision_audit_log.
    """
    ctx = ToolContext(scope="enterprise",
                      enterprise_id="11111111-1111-1111-1111-111111111111",
                      user_id="22222222-2222-2222-2222-222222222222")
    mock_audit = AsyncMock(return_value=None)
    with patch("ai_orchestrator.chat.registry.audit.log_decision", new=mock_audit):
        ok, _ = await registry.dispatch(
            name="ok_enterprise",
            args={"days": 7},
            ctx=ctx,
        )
    assert ok is True
    assert mock_audit.await_count == 1
    kwargs = mock_audit.await_args.kwargs
    assert kwargs["decision_type"] == "chat.tool_call"
    assert kwargs["subject"] == "ok_enterprise"
    assert kwargs["enterprise_id"] == ctx.enterprise_id


@pytest.mark.asyncio
async def test_dispatch_writes_audit_row_even_on_failure(registry):
    """K-15: failure must still leave a trail (so we can spot abuse)."""
    ctx = ToolContext(scope="enterprise",
                      enterprise_id="11111111-1111-1111-1111-111111111111")
    mock_audit = AsyncMock(return_value=None)
    with patch("ai_orchestrator.chat.registry.audit.log_decision", new=mock_audit):
        ok, _ = await registry.dispatch(name="failing", args={}, ctx=ctx)
    assert ok is False
    assert mock_audit.await_count == 1
    assert "ok=False" in mock_audit.await_args.kwargs["reasoning"]


@pytest.mark.asyncio
async def test_platform_dispatch_skips_decision_audit(registry):
    """Platform tools have no enterprise_id, so decision_audit_log (which
    NOT-NULLs that column) is intentionally skipped. The structured log
    line is the audit trail for now — Phase 2 should add a mirror table."""
    ctx = ToolContext(scope="platform", role="ADMIN")
    mock_audit = AsyncMock(return_value=None)
    with patch("ai_orchestrator.chat.registry.audit.log_decision", new=mock_audit):
        ok, _ = await registry.dispatch(name="platform_only", args={}, ctx=ctx)
    assert ok is True
    assert mock_audit.await_count == 0
