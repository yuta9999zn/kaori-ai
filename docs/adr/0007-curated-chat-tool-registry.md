# ADR-0007 — Curated chat tool registry, no generic SQL executor

> **Status:** accepted
> **Date:** 2026-04-29
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0006 · `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` · `CLAUDE.md` K-1, K-12, K-16 · Sprint 8 PR A

## Context

The reference demo (`congdinh2008/chatbot-ai-mcp-demo`) ships 5 tools, including `execute_read_query` — a generic SELECT executor with a SQL keyword blacklist (`DROP`, `DELETE`, `UPDATE`, ...). Many "AI tool calling" demos do the same: give the AI a SQL escape hatch, blacklist destructive keywords.

This pattern has known failure modes:

- **Blacklist bypass.** `/* DELETE */ SELECT ...`, encoded keywords, comment tricks, second-statement injection — all known.
- **Multi-tenant leak.** A generic SELECT means *every* query needs to filter by `enterprise_id`. The AI cannot be trusted to remember; the executor cannot enforce K-1 without parsing arbitrary SQL.
- **No audit granularity.** Every "what did the AI look at?" question becomes "parse the SQL string and guess".

Two options:

1. **Curated tools only** — every tool is a Python class with a hand-written, parameterised query. The AI picks among ~6 tools and supplies typed args.
2. **Curated tools + escape hatch** — same as (1), but include `execute_read_query` for "edge cases".

## Decision

We ship **curated tools only**. There is no `execute_read_query`, no `run_arbitrary_sql`, no escape hatch.

The Sprint 8 catalog is six tools (3 P2 enterprise + 3 P1 platform). New tools are added by:

1. Subclassing `BaseTool` with explicit `name`, `description`, `parameters` (JSON-schema), `scope`.
2. Writing the SQL by hand inside `execute()`, wrapped in `acquire_for_tenant()` for enterprise scope (RLS).
3. Adding unit tests that mock the DB and assert SQL placeholders + projection shape.

The registry **refuses dispatch** if tool args contain any of: `enterprise_id`, `tenant_id`, `workspace_id`, `user_id`, `actor_id`, `admin_id` — invariant K-16, defence in depth against prompt injection that tries to override the tenant context.

## Consequences

### Positive

- **K-1 is enforceable per tool.** Every enterprise-scope tool wraps in `acquire_for_tenant()`; review pass = 6 tools, 6 wrappers.
- **K-12 / K-16 enforceable centrally.** One forbidden-keys set in `registry.py`; adding a tenant identifier to args is a test failure, not a code review catch.
- **K-15 audit granularity is exact.** Every `decision_audit_log` row has `decision_type='chat.tool_call'` + `subject=<tool_name>` + `args` snapshot. Reviewing what the AI looked at is a SQL filter on `subject`.
- **AI cannot be tricked into running the wrong query.** The worst it can do is choose the wrong tool — the SQL is dev-controlled.

### Negative / accepted trade-offs

- **Adding a new question for the chat to answer means a code change.** A user request like "show me orders from last week with total > 5M" requires either (a) extending an existing tool's args, or (b) adding a new tool. Acceptable; we'd rather force the conversation about "is this a primitive worth keeping?" than ship a SQL escape hatch.
- **No ad-hoc analyst exploration via the chatbot.** Power users who want raw SQL access use `/decisions` export (CSV) or the analytics dashboard. The chatbot is for guided answers, not Notebook-style exploration.
- **Six tools is a small surface.** Pilot UAT will surface which questions users actually ask; we expand the catalog when there's a pattern.

### Neutral / follow-ups

- **Trigger to revisit**: pilot UAT shows users routinely asking for data the catalog can't answer, AND adding a curated tool would require ≥10 tool variants. At that scale, a parameterised query builder (still curated, still tenant-scoped) is the next step — never an arbitrary SQL executor.
- **F-NEW4 catalog growth path** documented in `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` §2 "Adding a new tool".

## Alternatives considered

- **Generic `execute_read_query` with SQL keyword blacklist** — Rejected. See "Context" — the failure modes are well-documented and the multi-tenant context makes them worse.
- **`execute_read_query` with Postgres role + RLS** — Considered briefly. Even with RLS, the AI deciding the SELECT shape means we lose "is this a sensible query?" oversight. The cost of writing 6 hand-curated tools < the cost of one prompt-injection incident.
- **AI-generated SQL with manual approval before run** — Rejected for the chat UX. A "click to approve this query" step kills the conversational flow and pushes responsibility for SQL review to non-technical users.

## References

- `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md`
- ADR-0006 (MCP server deferred)
- `CLAUDE.md` K-12, K-16
- Sprint 8 PR A — `services/ai-orchestrator/chat/registry.py:_FORBIDDEN_ARG_KEYS`
