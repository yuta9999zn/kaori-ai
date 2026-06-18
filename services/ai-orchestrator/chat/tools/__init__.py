"""
Tool catalog — re-exported for ``registry.build_default_registry``.

Adding a new tool:
  1. Subclass BaseTool in either enterprise.py (P2 scope) or
     platform.py (P1 scope). Set ``name``, ``description`` (Vietnamese
     OK — tenet #7), and ``parameters`` (JSON-schema dict).
  2. Append the class to ``ENTERPRISE_TOOLS`` / ``PLATFORM_TOOLS``
     in this module.
  3. Add a unit test in tests/test_chat_tools_{enterprise,platform}.py
     that runs the tool against a tenant fixture and asserts the
     audit row landed.

Do NOT add a generic SELECT executor — see the Sprint 8 plan §2
(``execute_read_query`` is intentionally absent from this catalog).
"""
from __future__ import annotations

from .base import BaseTool, ToolContext  # re-export for callers
from .enterprise import (
    GetBillingQuotaStatusTool,
    GetTopAtRiskCustomersTool,
    SummarizeRecentDecisionsTool,
)
from .platform import (
    CountRecentSignupsTool,
    FindWorkspacesInAlertTool,
    GetPlatformSummaryTool,
)

ENTERPRISE_TOOLS: list[type[BaseTool]] = [
    SummarizeRecentDecisionsTool,
    GetTopAtRiskCustomersTool,
    GetBillingQuotaStatusTool,
]

PLATFORM_TOOLS: list[type[BaseTool]] = [
    GetPlatformSummaryTool,
    CountRecentSignupsTool,
    FindWorkspacesInAlertTool,
]

__all__ = [
    "BaseTool",
    "ToolContext",
    "ENTERPRISE_TOOLS",
    "PLATFORM_TOOLS",
]
