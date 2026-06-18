"""
Build the agent-scope tool registry.

The chat module owns its own registry (``chat.registry.get_default_registry``)
populated with the 6 read-only chat tools. The agent loop needs a
SUPERSET — the same 6 chat tools PLUS the 2 action tools defined in
``agents.tools.actions``.

We deliberately use a SEPARATE ``ToolRegistry`` instance rather than
mutating the chat one. Reason: a chat caller must NEVER see
``draft_followup_email`` in its catalog (chat is read-only). Two
registries with overlapping membership is the simplest way to keep
that invariant tight.

Both registries enforce K-12 / K-15 / K-16 identically — they share
the same ``ToolRegistry`` class. Only the catalog differs.
"""
from __future__ import annotations

from typing import Optional

from ..chat.registry import ToolRegistry
from ..chat.tools import ENTERPRISE_TOOLS
from .tools import ENTERPRISE_AGENT_TOOLS


_agent_registry: Optional[ToolRegistry] = None


def get_agent_registry() -> ToolRegistry:
    """Lazy-built process-global agent registry.

    First access populates with chat-enterprise tools + agent action
    tools. Tests reset via ``_reset_agent_registry_for_tests``.
    """
    global _agent_registry
    if _agent_registry is None:
        reg = ToolRegistry()
        for cls in ENTERPRISE_TOOLS + ENTERPRISE_AGENT_TOOLS:
            reg.register(cls)
        _agent_registry = reg
    return _agent_registry


def _reset_agent_registry_for_tests() -> None:
    global _agent_registry
    _agent_registry = None
