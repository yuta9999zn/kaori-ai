# ADR-0024 — Mem0-inspired ports into Stage 7 Memory (don't replace, extend)

> **Status:** accepted
> **Date:** 2026-05-17
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0021 (T-Cube trace-augmented reasoning) · mem0ai/mem0 (Apache 2.0) · `services/ai-orchestrator/reasoning/{memory,trace_distiller}/`

## Context

Anh asked em to evaluate `mem0ai/mem0` (https://github.com/mem0ai/mem0) — popular Apache 2.0 universal memory layer for AI agents (~2M+ developers, sub-second p50 latency at 1M+ token contexts) — for inclusion in Kaori.

Honest audit (em vs mem0):

| Capability | mem0 | Kaori Stage 7 Memory (shipped P15-S11) |
|---|---|---|
| API | `memory.add(messages, user_id=)` + `memory.search(query, filters=)` | `MemoryService.write(tenant_id, memory_type, ...)` + `retrieve(...)` |
| Scope | user_id / session / agent (single-tenant SaaS style) | **tenant_id RLS (K-1)** + session_id + entity_id |
| Memory types | Flat — text + metadata | **5 typed:** EPISODIC / SEMANTIC / PROCEDURAL / OPERATIONAL / DECISION |
| Hierarchy | "Multi-level" implied | **4-tier explicit:** L1 Working / L2 Short / L3 Episodic / L4 Long |
| Default LLM | OpenAI GPT-5-mini | Qwen 2.5 14B local (K-4) |
| Storage | Qdrant + hybrid (vector + BM25 + entity) | Postgres+pgvector (mig 067) + Redis L2 + Neo4j Ontology Stage 5 |
| Importance/decay | Not explicit | Ebbinghaus decay formula (recency + appearance + flag + outcome) |
| Producer | LLM-based fact extraction (built-in) | T-Cube paper port (P2-S21) — thinking-trace specific |

Kaori Stage 7 is structurally **more** complete for B2B multi-tenant SaaS:
- Multi-tenant RLS isolation that mem0's `user_id` filter doesn't safely provide cross-tenant
- K-4 Qwen-first default (mem0 default OpenAI breaks privacy + cost for VN customers)
- 5 typed boundaries that mem0's flat memory needs custom code to mimic

But mem0 has 2 patterns Kaori was missing:
1. **Auto fact-extraction** (`memory.add(text)` → SPO triples → semantic memory). Kaori had T-Cube for thinking traces (PROCEDURAL) but no generic fact extraction for SEMANTIC memories from chat turns / documents.
2. **Entity-aware retrieval** (boost records linked to query entity). Kaori had Stage 5 Neo4j Ontology with entity nodes but never wired entity-linkage into MemoryService.retrieve().

Tension:
- **Adopt mem0 library:** add a third memory system in parallel → 2 sources of truth → violates "Explicit over implicit" tenet. mem0's single-tenant model would need wrapping to be safe.
- **Replace Stage 7 with mem0:** loses multi-tenant RLS + 4-tier hierarchy + Ebbinghaus decay + Vietnamese prompts. Strict regression.
- **Borrow patterns, not code:** port mem0's 2 missing-from-Kaori patterns into existing Stage 7 infrastructure. No new system, no new dependency, minimal surface area.

## Decision

We adopt **borrow-patterns-not-code** for mem0. Specifically:

### Port 1 — Auto fact-extraction into TCubeTransformer

`TCubeTransformer.extract_facts(text, tenant_id, context=)` runs a single LLM call with a structured-output prompt (`PROMPT_EXTRACT_FACTS`) that asks the model to return 0-5 `{subject, predicate, object, confidence}` JSON triples. The caller (chat agent end-of-turn, document chunk ingestor, decision rationale post-processor) then calls `extract_and_store_facts(...)` to persist each high-confidence fact as a `MemoryType.SEMANTIC` record. SEMANTIC type lands in L4 by default per `MemoryService._DEFAULT_TIER`.

Hard guards:
- Confidence < 0.5 → drop the fact (defensive — LLMs hallucinate facts)
- Max 10 facts per call (router cap, regardless of LLM output)
- Markdown code fences (`json`) stripped before JSON parse
- LLM error → return `[]` (opportunistic; don't crash the calling flow)
- PII guidance in the prompt — model instructed to drop or mask email/phone/CCCD

### Port 2 — Entity-aware retrieval boost in MemoryService.retrieve

`MemoryService.retrieve(tenant_id, query, entity_id=None, entity_boost=2.0)` adds 2 optional kwargs. When `entity_id` is set, records whose `r.entity_id == entity_id` get their text-match score multiplied by `entity_boost`. Records without the entity still surface (not filtered out), just ranked lower.

The actual entity resolution from query text stays in the **caller** (chat agent, RAG router, future Insight Panel) using Stage 5 Neo4j Ontology — not in MemoryService. Reason: entity resolution is a separate concern from memory retrieval, and the caller knows when entity-awareness matters.

K-1 tenant isolation: unchanged — entity boost composes with tenant filter via the existing `list_all(tenant_id)` per-tier walk.

## Consequences

### Positive

- Closes the "no auto fact extraction" gap from chat turns / documents into SEMANTIC memory — agents can now learn "user prefers email over chat" type facts automatically.
- Entity-aware retrieval makes chat queries like "what did Olist mention last month?" actually surface Olist-tagged records first.
- Zero new dependencies — no mem0 library, no new vector store, no new key concept to teach the team. Pure extension of existing modules.
- Multi-tenant RLS preserved — both ports inherit Kaori's K-1 invariant for free because they extend in-place.

### Negative / accepted trade-offs

- LLM call per fact-extraction batch adds latency to chat-turn-end. Mitigation: caller controls when to call; not on the hot response path.
- Entity boost is a heuristic (2.0× default). May need tuning per use case. Mitigation: `entity_boost` is a parameter; default surfaced in ADR for revisit.
- Fact extraction can hallucinate facts. Mitigation: confidence < 0.5 drop + PII guidance in prompt + caller can re-validate against decision_audit_log if needed.
- Not adopting mem0's hybrid BM25 search means our retrieval is still vector-only on pgvector. Future: add BM25 if precision drops below acceptable.

### Neutral / follow-ups

- Hybrid BM25 + vector + entity composite ranking — defer until production telemetry says retrieval precision is a problem.
- Temporal reasoning ("3 weeks ago") — defer; FE doesn't expose temporal filters yet.
- ColPali / image memory — defer; Kaori is text-first today.
- The chat agent end-of-turn should be wired to call `extract_and_store_facts(...)` after each user-assistant turn. That wiring is a follow-up commit; this ADR ships only the foundational extensions.

## Alternatives considered

- **Alt 1 — Pull mem0 library as parallel memory system.** Rejected. Two memory systems = two sources of truth. Operations + monitoring + debugging doubled. mem0's single-tenant assumption is the wrong abstraction for B2B multi-tenant.
- **Alt 2 — Replace Stage 7 with mem0.** Rejected. Loses K-1 RLS multi-tenant + K-4 Qwen-first + 4-tier explicit + Vietnamese prompts. Strict regression.
- **Alt 3 — Add hybrid BM25 retrieval now.** Deferred. No telemetry yet says vector-only is insufficient. Premature.

## References

- mem0ai/mem0 — https://github.com/mem0ai/mem0 (Apache 2.0)
- `services/ai-orchestrator/reasoning/trace_distiller/transformer.py` — `extract_facts()` + `extract_and_store_facts()`
- `services/ai-orchestrator/reasoning/trace_distiller/prompts.py` — `PROMPT_EXTRACT_FACTS`
- `services/ai-orchestrator/reasoning/memory/service.py` — `retrieve(entity_id=, entity_boost=)` extension
- `services/ai-orchestrator/tests/test_mem0_inspired_ports.py` — 21 tests, 8 sections
- ADR-0021 — T-Cube trace distillation (sibling pattern; PROCEDURAL not SEMANTIC)
