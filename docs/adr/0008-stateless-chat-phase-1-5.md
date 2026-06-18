# ADR-0008 — Stateless chat in Phase 1.5

> **Status:** accepted
> **Date:** 2026-04-29
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0007 · `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` · Sprint 8 PR B

## Context

Sprint 8 ships the conversational layer. Two options for conversation history:

1. **Persist conversations** — `chat_conversations` + `chat_messages` tables, RLS-scoped, retention policy, FE loads history on panel open.
2. **Stateless** — no BE storage; FE keeps a session-local rolling buffer; BE receives the visible history per turn.

Forces in tension:

- **UX.** Persisting means refresh + reopen = same chat. Stateless means refresh = blank.
- **Privacy / retention.** Persisting chat content creates a new PII surface (user typed messages may contain customer names, emails, IDs). Retention policy + GDPR right-to-be-forgotten + audit access controls all need design.
- **Velocity.** Persisting needs a migration, RLS policies, retention cron, FE load API, plus a privacy review with the team. Stateless needs none of those.

Pilot UAT timeline is ~1 week from Sprint 8 merge. The persistence design alone would burn 2–3 days.

## Decision

Phase 1.5 chat is **stateless**. The BE has no `chat_conversations` / `chat_messages` tables. Each `POST /chat/{scope}/stream` call carries the visible history in the request body (≤ 20 turns, schema-validated by Pydantic).

Persistence ships as **F-NEW5 in Phase 2** with the full spec: RLS policies, retention policy, PII review, FE load API, audit access controls.

## Consequences

### Positive

- **Sprint 8 ships in 2 days** instead of a week. Pilot UAT runs on time.
- **No new PII surface.** User messages live in browser sessionStorage + transient HTTP body only. K-15 audit captures tool dispatches, not raw user prompts (only tool args + result preview).
- **Refresh = clean slate** is the right default for an exploratory pilot. Pilot users won't accidentally show old conversations to colleagues over their shoulder.

### Negative / accepted trade-offs

- **Refresh loses history.** A user who closes the panel by accident and reopens loses context. Mitigated by: history is in `useState`, drawer close ≠ unmount; only a full page reload clears state.
- **No analytics on chat usage.** Until F-NEW5 lands, we can't aggregate "what do users ask?" — we only see tool dispatch frequencies in `decision_audit_log`. Acceptable; tool dispatch is a strong proxy.
- **No multi-device sync.** A user who started a chat on laptop can't pick it up on phone. Acceptable; pilot is laptop-only.

### Neutral / follow-ups

- **F-NEW5 trigger**: pilot UAT consistently lists "I lost my chat" or "I want to share this conversation" as a top-3 complaint, OR a paying customer requests it.
- **F-NEW5 scope**: persist user + assistant turns only (NOT tool dispatch — that's already in `decision_audit_log`). RLS by `enterprise_id`. Retention 90 days hot, archived 1 year. PII review on stored content (likely auto-redact emails/phones in stored copy, full text in audit DB only).

## Alternatives considered

- **Persist now with a minimal schema** — Rejected. Even minimal persistence triggers privacy review + GDPR retention design + FE load endpoint + RLS policy. Once we ship persistence, removing it later is a customer-visible regression; better to delay until pilot signals demand.
- **Persist on FE only (localStorage)** — Considered. Same security profile as sessionStorage but survives reload. Rejected because: (a) localStorage is shared across tabs and we don't want chat history visible in a colleague's tab on a shared workstation; (b) cleanup story (clear on logout) requires the same plumbing as sessionStorage so no win.

## References

- `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` §5 "Out of scope" — Conversation persistence
- `frontend/components/chat/useChatStream.ts` — sessionStorage-only history
- ADR-0007 (curated tool registry — chat scope)
