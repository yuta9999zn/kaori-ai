"""
F-061 action tools — extend the chat tool registry with write-side
operations the agent loop can dispatch.

The ``ENTERPRISE_AGENT_TOOLS`` list is consumed by ``register_agent_tools``
in registry_setup.py, which is called once at orchestrator startup. It
adds these tools to the existing chat ``ToolRegistry`` so the executor
goes through the same K-12 / K-15 / K-16 enforcement as the chat agent.

Action tools differ from chat tools in two ways:

  1. They MAY have side-effects (writes to ``decision_audit_log`` or
     ``notification_outbox``). Side-effects are gated on
     ``ToolContext.dry_run``: when TRUE the tool returns a preview of
     what it WOULD have done without writing anything.
  2. They are NOT exposed to the chat layer. Chat scope filters by the
     6 read-only chat tools; agent scope sees those + these. The
     workflow's ``allowed_tools`` set narrows further.
"""
from .actions import (
    DraftFollowupEmailTool,
    MarkCustomerForReviewTool,
)
from .knowledge_tools import (
    RetrieveEvidenceTool,
    RecallMemoryTool,
)

ENTERPRISE_AGENT_TOOLS = [
    # read-side (ground first)
    RetrieveEvidenceTool,
    RecallMemoryTool,
    # write-side (act)
    DraftFollowupEmailTool,
    MarkCustomerForReviewTool,
]

__all__ = [
    "ENTERPRISE_AGENT_TOOLS",
    "RetrieveEvidenceTool",
    "RecallMemoryTool",
    "DraftFollowupEmailTool",
    "MarkCustomerForReviewTool",
]
