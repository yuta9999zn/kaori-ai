"""
Sprint 8 — Conversational Layer (Phase 1.5).

Intra-process chat tool registry for P2 Enterprise + P1 Platform
chatbots. Lives inside ai-orchestrator (Python) — NOT a standalone
MCP server. The MCP server scaffold is a Phase 2 goal (see
CLAUDE.md §2). The OpenAI-format tool definitions exposed here are
forward-compatible so a future MCP wrapper can re-export them.

Architecture (one-liner):
    User msg → POST /chat/{scope}/stream (SSE)
             → agent.run_tool_loop  (max 3 hops)
             → llm_router.complete  with tools field
             → providers (Ollama /api/chat with native Qwen 2.5 tool calling)
             → ToolRegistry.execute  (RLS-aware, audit per call)

Invariants this module enforces:
    K-1   Every DB tool wraps in acquire_for_tenant()
    K-3   All LLM calls still go through llm_router → llm-gateway
    K-4   Chat default consent_external=False (Qwen local only in v0)
    K-7   tenant_id, user_id, role come from gateway-trusted X-* headers
    K-12  tool args NEVER carry tenant_id — registry rejects if they do
    K-15  every tool invocation gets an audit row in decision_audit_log
"""
