"""
ToolRegistry — register, list (per scope), and dispatch chat tools.

Why a registry instead of a flat dict:
  * tools are filtered per-scope before being sent to the LLM (a P2
    chat must never see ``find_workspaces_in_alert``)
  * dispatch is the single point that enforces K-12 (no tenant_id in
    args) and writes the K-15 audit row, so a future tool can't
    silently skip the audit
  * platform tools get an additional role gate here — registry checks
    ``ctx.role`` against an allow-list before calling ``execute``

The registry instance is process-global; tools have no per-request
state, so reusing them across concurrent SSE streams is safe.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

import structlog

from ..shared import audit
from .tools import ENTERPRISE_TOOLS, PLATFORM_TOOLS
from .tools.base import BaseTool, ToolContext

log = structlog.get_logger()

# Roles allowed to invoke any platform-scope tool. CLAUDE.md §9 lists
# SUPPORT separately; it currently has read-only platform access via
# F-008 / F-011 endpoints, so it's included here too. If later we want
# tighter gates (e.g. SUPPORT can call get_platform_summary but not
# find_workspaces_in_alert), promote this to a per-tool ACL.
PLATFORM_ROLES_ALLOWED = {"SUPER_ADMIN", "ADMIN", "SUPPORT"}

# Argument keys the LLM is forbidden from setting. tenant_id /
# enterprise_id MUST come from the JWT (K-12); seeing them in tool args
# is a strong signal of prompt injection or a buggy tool definition.
_FORBIDDEN_ARG_KEYS = frozenset({
    "enterprise_id", "tenant_id", "workspace_id",
    "user_id", "actor_id", "admin_id",
})


class ToolDispatchError(RuntimeError):
    """Raised when the registry refuses a dispatch (auth / arg shape)."""


class ToolRegistry:
    """Process-global tool catalog. One instance per service."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, cls: type[BaseTool]) -> None:
        if not cls.name:
            raise ValueError(f"{cls.__name__} missing name")
        if cls.name in self._tools:
            raise ValueError(f"tool name collision: {cls.name}")
        self._tools[cls.name] = cls()
        log.info("chat.tool.registered", name=cls.name, scope=cls.scope)

    def list_for_scope(self, scope: str) -> list[BaseTool]:
        return [t for t in self._tools.values() if t.scope == scope]

    def openai_tools_for_scope(self, scope: str) -> list[dict]:
        """Render the ``tools=[...]`` array the LLM expects."""
        return [type(t).to_openai_tool() for t in self.list_for_scope(scope)]

    async def dispatch(
        self,
        *,
        name: str,
        args: dict,
        ctx: ToolContext,
    ) -> tuple[bool, Any]:
        """Run one tool call and emit the audit row.

        Returns ``(ok, payload)``. On failure ``payload`` is a string
        error message that gets fed back to the LLM as the tool
        result, so the model can try a different tool or apologise.
        Never raises for tool-side errors — only for hard auth/arg
        violations that would amount to bypassing K-12 / K-15.
        """
        started = time.monotonic()

        tool = self._tools.get(name)
        if tool is None:
            return False, f"Tool '{name}' không tồn tại."

        # K-12: forbid tenant identifiers in args. The agent enforces
        # this too (it strips them before forwarding the LLM's call),
        # but defence-in-depth — if someone bypasses the agent, the
        # registry still refuses.
        leaked = _FORBIDDEN_ARG_KEYS.intersection(args.keys())
        if leaked:
            log.warning(
                "chat.tool.forbidden_args",
                tool=name,
                leaked=sorted(leaked),
                actor_user=ctx.user_id,
            )
            raise ToolDispatchError(
                f"Tool args may not include tenant identifiers: {sorted(leaked)}"
            )

        # Scope gate. P2 caller asking for a P1 tool, or vice versa,
        # is a programmer error — the agent should have filtered the
        # catalog by scope before passing it to the LLM, but we still
        # check on the way in.
        if tool.scope != ctx.scope:
            raise ToolDispatchError(
                f"Tool '{name}' is scope={tool.scope}, "
                f"caller is scope={ctx.scope}"
            )

        # P1 role gate. Platform tools cross tenant boundaries, so
        # only platform admins may call them. Enterprise tools are
        # tenant-scoped via RLS and don't need an extra gate (any
        # member of the tenant can ask).
        if tool.scope == "platform" and ctx.role not in PLATFORM_ROLES_ALLOWED:
            raise ToolDispatchError(
                f"Role '{ctx.role}' is not allowed to call platform tools."
            )

        try:
            result = await tool.execute(args, ctx)
            ok = True
            payload: Any = result
        except ValueError as exc:
            # Arg validation — return a friendly message to the LLM
            # so it can self-correct rather than crashing the stream.
            ok = False
            payload = f"Tham số không hợp lệ: {exc}"
        except Exception as exc:
            # Anything else (DB error, schema drift, ...). Log full,
            # surface a sanitised message to the LLM.
            log.exception("chat.tool.execute_failed",
                          tool=name, scope=tool.scope, error=str(exc))
            ok = False
            payload = "Lỗi nội bộ khi thực thi tool."

        latency_ms = int((time.monotonic() - started) * 1000)

        # K-15 audit. ``decision_audit_log.enterprise_id`` is NOT NULL
        # so platform tools (which run cross-tenant) can't write here
        # without an actor — we drop a debug log instead, and rely on
        # the gateway's own audit row for the LLM call. Phase 2 should
        # introduce a ``platform_audit_log`` mirror for chat tools.
        if ctx.enterprise_id:
            await audit.log_decision(
                enterprise_id=ctx.enterprise_id,
                decision_type="chat.tool_call",
                subject=name,
                chosen_value=_truncate_json(payload),
                method=tool.scope,
                reasoning=f"args={_truncate_json(args)} latency_ms={latency_ms} ok={ok}",
            )
        else:
            log.info("chat.tool.platform_call",
                     tool=name, ok=ok, latency_ms=latency_ms,
                     actor_user=ctx.user_id, role=ctx.role)

        return ok, payload


def _truncate_json(value: Any, limit: int = 1000) -> str:
    """Compact JSON repr, capped — fits in the audit row cleanly."""
    try:
        s = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"


_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Lazy-built process-global registry — populated on first access.

    Tests reset this with ``_reset_registry_for_tests`` rather than
    instantiating a fresh registry, so the production path always
    runs through the same singleton.
    """
    global _default_registry
    if _default_registry is None:
        reg = ToolRegistry()
        for cls in ENTERPRISE_TOOLS + PLATFORM_TOOLS:
            reg.register(cls)
        _default_registry = reg
    return _default_registry


def _reset_registry_for_tests() -> None:
    global _default_registry
    _default_registry = None
