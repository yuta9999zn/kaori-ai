"""
BaseTool + ToolContext — the contract every chat tool implements.

Tools are CLASSES (not functions) so the registry can introspect
``name``, ``description``, ``parameters`` without instantiating.
Execution is async and receives a ``ToolContext`` carrying the
tenant + actor identity that came from the gateway-trusted X-*
headers — never from the LLM's tool arguments (K-12).

The ``parameters`` dict is JSON-schema (OpenAI tool format). The
agent forwards it to the LLM unchanged. Keep it minimal — only
the args the model is allowed to set. ``enterprise_id`` /
``user_id`` / ``role`` MUST NOT appear here.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ToolContext(BaseModel):
    """Identity + scope for one chat turn. Built from the gateway
    X-Enterprise-ID / X-User-ID / X-Role headers — see chat/router.py.

    For the platform scope ``enterprise_id`` is None (cross-tenant
    queries). For the enterprise scope ``role`` is one of MANAGER /
    OPERATOR / ANALYST / VIEWER (CLAUDE.md §9).

    ``dry_run`` is consumed only by F-061 action tools (see
    services/ai-orchestrator/agents/tools/actions.py). Chat tools are
    read-only and ignore it. Default False so the existing chat path
    behaves identically; the orchestrator flips it TRUE when starting
    an agent session whose caller asked for a dry run.
    """

    scope: Literal["enterprise", "platform"]
    enterprise_id: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = None
    dry_run: bool = False


class BaseTool:
    """All chat tools subclass this. The four class attributes are
    inspected by the registry — instances never carry per-request
    state, so a tool can be reused across concurrent turns.

    Attributes:
        name:         Snake-case identifier. Becomes the OpenAI
                      ``function.name`` so the LLM sees it verbatim.
                      Must match ``[a-z][a-z0-9_]*``.
        description:  Vietnamese is fine (tenet #7). Keep it ≤200
                      chars; long descriptions blow the prompt budget.
        parameters:   JSON-schema dict. ``{}`` for no-arg tools.
        scope:        ``"enterprise"`` or ``"platform"``. The registry
                      filters by scope before exposing the catalog
                      to the LLM, so a P2 chat will never see a P1 tool.
    """

    name: str = ""
    description: str = ""
    parameters: dict = {}
    scope: Literal["enterprise", "platform"] = "enterprise"

    async def execute(self, args: dict, ctx: ToolContext) -> Any:
        """Run the tool. Return any JSON-serialisable value.

        Implementations should:
          * acquire DB connections via ``acquire_for_tenant`` (K-1 RLS)
          * raise ``ValueError`` for arg validation failures (the
            registry converts these into a tool_result with ok=False
            so the LLM can self-correct)
          * never call an LLM directly (the agent loop owns LLM dispatch)
        """
        raise NotImplementedError

    @classmethod
    def to_openai_tool(cls) -> dict:
        """Render the OpenAI ``tools[]`` entry the LLM expects.

        Same shape Anthropic accepts after ``input_schema`` ↔
        ``parameters`` rename, which the gateway's anthropic provider
        will handle on the way out.
        """
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters or {
                    "type": "object",
                    "properties": {},
                },
            },
        }
