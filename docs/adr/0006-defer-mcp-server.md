# ADR-0006 — Defer standalone MCP server to Phase 2

> **Status:** accepted
> **Date:** 2026-04-29
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0007 · `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` · `CLAUDE.md` §2 MCP Server row · K-15

## Context

Sprint 8 added a chatbot with curated tool calling. The reference repo (`congdinh2008/chatbot-ai-mcp-demo`) implements this with a standalone Node.js process running `@modelcontextprotocol/sdk`, exposing tools over stdio + HTTP. CLAUDE.md §2 lists "MCP Server (Node.js, JSON-RPC 2.0)" as a Phase 2 service.

Two options for Sprint 8:

1. **Build the MCP server now** alongside the chat agent — full pattern, future-proof for 3rd-party agents (Claude Desktop, Cursor, etc.) to call our tools.
2. **Build the tool registry intra-process inside `ai-orchestrator`** — only Kaori's own chat agent uses it, no separate Node.js service.

The pull toward (1) is "future-proof". The pull toward (2) is "ship pilot UAT this sprint".

## Decision

We build the tool registry **intra-process inside `ai-orchestrator/chat/`** for Sprint 8. Standalone MCP server stays a Phase 2 goal (CLAUDE.md §2 unchanged).

The tool definitions use OpenAI tool format (`{type: "function", function: {...}}`). Anthropic/Ollama mappings already exist in `services/llm-gateway/providers.py`. When Phase 2 wraps these tools as MCP, the conversion is mechanical — `BaseTool.to_openai_tool()` becomes `BaseTool.to_mcp_tool()` in the same registry.

## Consequences

### Positive

- **Sprint 8 ships in 2 days** instead of a week. Pilot UAT runs on time.
- **K-15 audit + RLS happen in Python** alongside `acquire_for_tenant` and `decision_audit_log` — no cross-process boundary to authenticate.
- **One stack to debug.** Every chat turn is one Python process; no Node.js + Python interop.

### Negative / accepted trade-offs

- **Third-party MCP clients (Claude Desktop, Cursor) cannot call Kaori tools today.** Acceptable — pilot users only access tools through the Kaori chat panel. No external integration on the roadmap before Phase 2.
- **The OpenAI tool-call format is duplicated** — Python registry knows it, future MCP wrapper will know it. Mechanical conversion makes this OK.
- **K-15 invariant text in CLAUDE.md mentions MCP explicitly** ("MCP tool calls: authz check per tenant_id + audit log every call"). The intra-process registry already enforces this — Sprint 8 added K-16 to make the chat-tool-specific spirit explicit.

### Neutral / follow-ups

- **Trigger to build the MCP server**: a customer (or partner) asks to call Kaori tools from outside our chat panel — typical motivators are Claude Desktop integration, custom agent frameworks, or tools-as-a-service for downstream apps.
- **Migration plan**: extract `services/ai-orchestrator/chat/tools/` into a thin wrapper Node.js service that imports the same Python registry over HTTP, OR re-implement tool definitions in TS with shared OpenAPI schema. Decide at trigger time.

## Alternatives considered

- **Build standalone MCP server now** — Rejected. Forces a Node.js service into Phase 1 stack just to satisfy a future use case. Phase 2 timeline can absorb it; Phase 1 timeline cannot.
- **Use a Python MCP SDK** (`mcp-python`) — Considered briefly. Mature MCP SDKs are TypeScript-first; Python ones lag the spec. Better to wait for Node.js if we're going to commit to MCP at all.

## References

- ADR-0007 — Curated chat tool registry (the registry being deferred-from-MCP'd)
- `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` §5 "Out of scope"
- `CLAUDE.md` §2 row "MCP Server (Node.js, JSON-RPC 2.0) — Phase 2"
