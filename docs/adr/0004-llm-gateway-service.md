# ADR-0004 — Centralised LLM gateway service

> **Status:** accepted
> **Date:** 2026-04-29 (originally landed Phase 1 P-1 cutover)
> **Deciders:** Nguyen Truong An
> **Related:** `services/llm-gateway/` · `services/ai-orchestrator/engine/llm_router.py` · `CLAUDE.md` K-3, K-4, K-5 · `infrastructure/postgres/migrations/010_llm_gateway.sql`

## Context

Before the P-1 cutover, every Python service that needed an LLM call imported the Anthropic SDK / OpenAI SDK / Ollama client directly. That meant:

- **PII redaction (K-5) was duplicated** across services. One copy fell behind and leaked an email to OpenAI in dev.
- **Tenant consent (K-4) was checked in 3 different places**, with 3 different cache strategies.
- **Cost accounting was impossible** — no single place to count tokens or attribute spend per tenant.
- **Provider rotation** (e.g., Anthropic outage → fall back to OpenAI) required code changes in every caller.

## Decision

We extract a single **LLM gateway service** at port 8095. Every other service calls it via `POST /v1/infer`:

- `ai-orchestrator/engine/llm_router.py` is reduced to an HTTP shim (~180 lines) — same import surface for callers, but routes through the gateway.
- The gateway owns: routing (Ollama vs Anthropic vs OpenAI), PII redaction (K-5, only when method=external), audit log writes (K-6), and the no-direct-SDK invariant (K-3).
- Single endpoint, two pipelines: single-prompt (Phase 1) + chat with tools (Sprint 8 — `messages` + `tools` + `tool_choice`).

## Consequences

### Positive

- **K-3, K-4, K-5 enforced at one boundary.** Reviewing those invariants = reading `services/llm-gateway/router.py`.
- **Adding a new provider** (e.g., DeepSeek) is one file in `providers.py`, no caller changes.
- **Sprint 8 chat tool calling** ships by extending the existing gateway, not threading provider clients through `ai-orchestrator/chat/`.
- **Cost / token accounting is one DB write per call** to `decision_audit_log` (K-6).

### Negative / accepted trade-offs

- **One more network hop.** ~5–10 ms added latency for every LLM call. Negligible vs LLM inference itself (Qwen 2.5 14B = 1–8 s).
- **Gateway is a SPOF for any LLM-backed feature.** Mitigated by: stateless pods (HPA scale-out trivial), provider-side fallback (external API key missing → falls back to internal Ollama), and degraded UX (chat shows error, app keeps working).
- **External AI Gateway full feature set (F-063)** — provider keys store, per-provider quotas, circuit breakers — is still Phase 2. The current gateway is a scaffold that owns the boundary but not the operational depth.

### Neutral / follow-ups

- F-063 expands this gateway with: provider quota tracking, semantic cache (Redis), circuit breaker, multi-model A/B routing.
- Phase 2 also adds external chat path (CLAUDE.md §8 Rule 7) behind a separate `consent_external_chat` flag.

## Alternatives considered

- **Library-based shared client** (Python package imported by every service) — Rejected. Library upgrades require redeploy of every consumer; gateway lets us roll out a routing change once.
- **Sidecar pattern** (gateway runs as a sidecar in every service pod) — Rejected for Phase 1. Adds k8s complexity; centralised service is simpler to operate while we have <10 callers.
- **Direct provider SDKs in each service** (the pre-cutover state) — Rejected. Already failed once with the K-5 duplication leak.

## References

- `services/llm-gateway/main.py` + `router.py`
- `services/ai-orchestrator/engine/llm_router.py` (the shim)
- `infrastructure/postgres/migrations/010_llm_gateway.sql` (`llm_task_routing` table)
- `CLAUDE.md` §2 LLM Gateway row + §8 LLM Routing Logic
