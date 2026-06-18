# Chat Tool Registry — Sprint 8 Conversational Layer

> **Status:** ✅ shipped 2026-04-29 (Sprint 8, F-NEW4)
> **Scope:** Phase 1.5 — intra-process tool registry inside `ai-orchestrator`. Standalone MCP server is a Phase 2 goal (CLAUDE.md §2).
> **Inspired by:** `congdinh2008/chatbot-ai-mcp-demo` — adapted to multi-tenant Kaori (RLS, K-12, K-15, K-16).

This document is the contract surface for the chat backend. It explains:

1. The two endpoints and their wire format.
2. The tool catalog and how to add a new tool.
3. The four governance gates (K-3 / K-4 / K-12 / K-15 / K-16) and where each one fires.
4. The agent loop's hop budget and tool-call cap.
5. What is intentionally **not** in this PR (so reviewers don't ask).

If you're touching `services/ai-orchestrator/chat/**` you should read all five sections.

---

## 1. Endpoints

| Method | Path                                | Auth                                      | Body         | Response             |
|--------|-------------------------------------|-------------------------------------------|--------------|----------------------|
| POST   | `/api/v1/chat/enterprise/stream`    | JWT (any P2 role)                         | `ChatRequest`| `text/event-stream`  |
| POST   | `/api/v1/chat/platform/stream`      | JWT + role ∈ `{SUPER_ADMIN, ADMIN, SUPPORT}` | `ChatRequest`| `text/event-stream`  |

Why path-based scope: a hard URL boundary stops a leaked P2 token from hitting the platform tools, even if the body said `scope='platform'`. The role check sits at **both** the router (returns 403 RFC 7807) and the registry (raises `ToolDispatchError`).

### Request body (`ChatRequest`)

```json
{
  "message": "Top 5 khách hàng đang rủi ro?",
  "history": [
    { "role": "user",      "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

- `message` — 1 – 4 000 chars, required.
- `history` — caller-supplied visible history (≤ 20 turns). Stateless v0: the BE stores nothing; the FE keeps a session buffer. Phase 2 (F-NEW4) introduces `chat_conversations` + `chat_messages` tables.

### Response — Server-Sent Events

One JSON envelope per `data:` line, blank-line frame separator. **No** `event:` / `id:` lines (FE just decodes `data` and dispatches on `type`).

```text
data: {"type":"thinking"}

data: {"type":"tool_call","tool":"get_top_at_risk_customers","args":{"limit":5}}

data: {"type":"tool_result","tool":"get_top_at_risk_customers","ok":true,"preview":"{...}"}

data: {"type":"message","text":"Top 5 khách rủi ro: ..."}

data: {"type":"done"}
```

| `type`         | Fields populated                | Meaning                                        |
|----------------|---------------------------------|------------------------------------------------|
| `thinking`     | —                               | Stream open, FE shows typing indicator         |
| `tool_call`    | `tool`, `args`                  | Agent decided to invoke a tool                 |
| `tool_result`  | `tool`, `ok`, `preview`         | Tool finished (preview ≤ 200 chars)            |
| `message`      | `text`                          | Final assistant text                           |
| `error`        | `title`, `detail`               | Terminal — user-facing error                   |
| `done`         | —                               | Stream end sentinel                            |

### Headers expected

| Header             | When           | Source                          |
|--------------------|----------------|---------------------------------|
| `Authorization`    | always         | client → gateway                |
| `X-Enterprise-ID`  | enterprise scope only | gateway → orchestrator (from JWT)   |
| `X-User-ID`        | both scopes    | gateway → orchestrator (from JWT)   |
| `X-User-Role`      | both scopes    | gateway → orchestrator (from JWT) — RBAC role |

Defence-in-depth note: the FE never sets `X-Enterprise-ID` itself. The Gateway's `JwtAuthFilter` strips client-supplied `X-*` headers before forwarding (K-12).

---

## 2. Tool catalog (v0)

Six tools, three per scope. All are curated — there is **deliberately no** `execute_read_query` generic SQL executor. (See §5 below.)

### P2 Enterprise

| Tool                          | Args               | Read source                         | Notes |
|-------------------------------|--------------------|-------------------------------------|-------|
| `summarize_recent_decisions`  | `days?: 1–90`      | `decision_audit_log` group-by-type  | Default 7 days |
| `get_top_at_risk_customers`   | `limit?: 1–20`     | `gold_features` (F-032)             | Filters `revenue_at_risk > 0` |
| `get_billing_quota_status`    | —                  | `v_billing_summary` view + `enterprise_monthly_billing` | Returns `usage_pct`, `alert_80_fired`, `alert_95_fired` |

### P1 Platform

| Tool                          | Args                        | Read source                              | Notes |
|-------------------------------|-----------------------------|------------------------------------------|-------|
| `get_platform_summary`        | —                           | `workspaces` + `enterprises` + `enterprise_users` + `pipeline_runs` | One-shot multi-count |
| `count_recent_signups`        | `days?: 1–365`              | `enterprises`                            | Default 30 days |
| `find_workspaces_in_alert`    | `threshold?: '80'\|'95'\|'any'` | `enterprise_monthly_billing` JOIN `enterprises` | Sorted by usage_pct DESC, capped 50 |

### Adding a new tool

1. Subclass `BaseTool` in `chat/tools/{enterprise,platform}.py`. Set `name`, `description` (Vietnamese OK — tenet #7), `parameters` (JSON-schema), `scope`.
2. Append to `ENTERPRISE_TOOLS` / `PLATFORM_TOOLS` in `chat/tools/__init__.py`.
3. Add unit tests in `tests/test_chat_tools_{enterprise,platform}.py` (mock `acquire_for_tenant` or `get_pool`, assert SQL placeholders + projection shape).
4. **Do not** introduce arguments named `enterprise_id` / `tenant_id` / `workspace_id` / `user_id` / `actor_id` / `admin_id`. The registry refuses dispatch if they appear (K-12 / K-16).
5. Update the OpenAPI spec: `python scripts/dump_openapi.py orchestrator` then `cd frontend && node scripts/gen-api-types.mjs`.

---

## 3. Governance — where each invariant fires

| Invariant | Where enforced                                                                  |
|-----------|---------------------------------------------------------------------------------|
| **K-1**   | Enterprise tools wrap DB query in `acquire_for_tenant(ctx.enterprise_id)` so RLS policies (`005_rls.sql`, `018_gold_layer.sql`) filter by tenant. |
| **K-3**   | All LLM dispatch routes through `engine/llm_router.chat()` → `llm-gateway:8095`. The chat agent never imports an LLM SDK. |
| **K-4**   | Chat default `consent_external=False`. Agent passes this verbatim regardless of `tenant_settings.consent_external_ai`. CLAUDE.md §8 Rule 7. |
| **K-7**   | `ToolContext` is built in `chat/router.py` from the gateway-trusted `X-Enterprise-ID` / `X-User-ID` / `X-User-Role` headers. |
| **K-12**  | Forbidden args are `enterprise_id`, `tenant_id`, `workspace_id`, `user_id`, `actor_id`, `admin_id` — registry raises `ToolDispatchError` if any appear in `args`. |
| **K-15**  | Every enterprise dispatch writes a `decision_audit_log` row with `decision_type='chat.tool_call'`. Platform dispatch logs structured (no audit table — `decision_audit_log.enterprise_id` is NOT NULL). |
| **K-16**  | New invariant — see CLAUDE.md §4. The registry's `_FORBIDDEN_ARG_KEYS` set is the single point of enforcement. |

Defence-in-depth: even if a future endpoint refactor bypasses the router, the registry still enforces scope + role gates and forbidden-arg rejection. Belt + suspenders.

---

## 4. Agent loop

```
1. Build messages = [system, ...history, user]
2. POST llm-gateway with tools=registry.openai_tools_for_scope(scope)
3. If finish_reason='tool_calls':
     - For each tool_call: registry.dispatch (audit + RLS + role gate)
     - Append assistant tool-call turn + tool result messages
     - LOOP up to MAX_HOPS (3)
4. Else:
     - Emit ``message`` event with completion text
     - Emit ``done``
```

Hard caps:
- `MAX_HOPS = 3` — three round-trips of tool calling per turn. After that we surface whatever text the model produced (or a generic "đã chạy hết hop" if none).
- `MAX_TOOL_CALLS_PER_HOP = 4` — one hop can ask for at most four tools. Extras get a synthetic "exceeded limit" tool result so the model knows we dropped them.

System prompts are scope-specific and intentionally short (Qwen context budget):
- P2: "Bạn là Kaori — trợ lý AI cho doanh nghiệp..."
- P1: "Bạn là Kaori Ops — trợ lý nội bộ cho admin platform..."

---

## 5. Out of scope (do not ask why these aren't in PR1)

- **Standalone MCP server (Node.js).** CLAUDE.md §2 lists this as a Phase 2 goal. Re-exposing the same tools through `@modelcontextprotocol/sdk` is a thin wrapper once the registry is stable.
- **Conversation persistence.** No `chat_conversations` / `chat_messages` tables. F-NEW5 (Phase 2) will add RLS-scoped persistence + retention policy + PII review.
- **`execute_read_query` generic SELECT.** Every demo MCP server has one; we don't. Multi-tenant means every SELECT must filter by `enterprise_id` (K-1), and a keyword blacklist is bypassable. Adding a generic executor would push the security argument back into prompt engineering, which is the wrong layer.
- **Streaming token-by-token assistant text.** The gateway returns the full `completion` then the agent emits a single `message` event. Token streaming is a follow-up — the wire format already accommodates it (FE just appends to `text`).
- **External chat (Claude / GPT).** Plan §10 Q4 chose Phase 1.5 = Qwen-only. Phase 2 unlocks external chat behind a separate `consent_external_chat` tenant flag (so a tenant can opt into chat without opening the analytics-summary path, which has different PII surface).
- **Token / rate-limit budgets.** Redis token bucket is in the plan but not in v0. Today the only guard is `MAX_HOPS × MAX_TOOL_CALLS_PER_HOP × MAX_TOKENS = 3 × 4 × 1500` per turn.

---

## 6. Reference

- `services/ai-orchestrator/chat/__init__.py` — module-level docstring
- `services/ai-orchestrator/chat/registry.py:ToolRegistry` — dispatch + audit
- `services/ai-orchestrator/chat/agent.py:run_tool_loop` — main loop
- `services/ai-orchestrator/chat/router.py` — endpoint + SSE wiring
- `services/llm-gateway/providers.py:invoke_chat` — provider dispatch with tool calling
- `frontend/components/chat/useChatStream.ts` — FE consumer
