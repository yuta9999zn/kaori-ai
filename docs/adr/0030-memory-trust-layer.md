# ADR-0030 — Memory trust layer (decay + verify + reinforce)

> **Status:** proposed
> **Date:** 2026-05-27
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0024 (mem0-inspired ports into Stage 7) · NNL-Harness `harness/memory.py` · `services/ai-orchestrator/reasoning/memory/` · mig 067 (memory_l3) · K-1 · K-6 · K-20

## Context

Stage 7 Memory (shipped P15-S11) already has an **importance** model — the Ebbinghaus-style score in `reasoning/memory/types.py::compute_importance` (recency + session appearance + user flag + linked outcome) that drives **retention**: promote > 0.7, forget < 0.3 after 90 days. ADR-0024 deliberately kept this and borrowed only fact-extraction + entity-recall from mem0.

Studying NNL-Harness (the local "kaori" harness, `harness/memory.py`) surfaces a capability importance does **not** cover: **trust** — *how much should the reasoning layer BELIEVE a memory when it injects it into a prompt?* These are different questions:

- **Importance** = should we KEEP this memory? (storage/retention)
- **Trust** = should we RELY on this memory right now? (believability / anti-hallucination)

A memory can be important (high outcome value, flagged) yet stale and unverified — exactly the "confident but unchecked" failure mode where a model parrots an old fact as current truth. NNL guards this with: a trust score that **decays by a per-type half-life**, a **"confident-but-unchecked" flag**, an explicit **`verify()`** that resets decay, and **reinforce-on-use** (a memory that demonstrably helped a good answer is re-verified, so "used" memories stay fresh and idle ones age out of trust).

The forces in tension:
- We want recalled memories to inform reasoning (the whole point of Stage 7) — pulling toward "trust what we retrieve".
- But the pilot runs on a local 7B/14B Qwen that hallucinates confidently; injecting a stale memory as fact is worse than omitting it — pulling toward "distrust the old".
- We must not silently delete (importance already handles forgetting); trust should **down-rank and flag**, leaving the audit trail intact (K-6).

## Decision

We add a **trust layer** to Stage 7 Memory, distinct from and complementary to importance. Trust is a per-record, time-decaying believability score that the retrieval ranker and the prompt-injection layer both consult; it never deletes, only down-ranks and flags.

**1. Trust fields per memory record** (proposed mig — NOT executed in this ADR):
```sql
ALTER TABLE memory_l3
  ADD COLUMN confidence       NUMERIC(3,2) NOT NULL DEFAULT 0.70,  -- 0..1 self-scored at write
  ADD COLUMN trust_source     VARCHAR(32),                          -- 'user' | 'consolidate' | 'rag' | 'derived' | ...
  ADD COLUMN last_verified_at TIMESTAMPTZ;                          -- NULL = never re-confirmed
-- created_at already exists; occurred_at is the event time.
```
`confidence` is self-scored by the LLM at consolidation (mirrors NNL's "tự chấm confidence, không bịa độ tin cao") or set by the writer (user-stated facts → high). `trust_source` is provenance.

**2. Trust score** (pure function, no DB — `reasoning/memory/trust.py`):
```
trust = confidence × 0.5 ^ (age_days / half_life)
age_days = now − COALESCE(last_verified_at, created_at)
```
Half-life per `memory_type` (config via env `KAORI_MEM_HALFLIFE_*`):
`SEMANTIC`/`PROCEDURAL` → long (≈365d, durable concepts) · `DECISION`/`OPERATIONAL` → medium (≈60d) · `EPISODIC` → short (≈30d).
Levels: `fresh ≥ 0.66 · aging ≥ 0.33 · stale` otherwise.

**3. "Confident-but-unchecked" flag:** `confidence ≥ 0.8 AND last_verified_at IS NULL AND age_days > half_life`. Flagged records are injected as **GỢI Ý (hint), nên xác minh** — never as asserted fact.

**4. `verify(record_id)`** stamps `last_verified_at = now()`, resetting decay. Exposed as `POST /memory/{id}/verify` (tenant-scoped via `acquire_for_tenant`, K-1; writes a K-6 decision-audit row).

**5. Reinforce-on-retrieve:** when a retrieved memory's content shares ≥2 whole words (Unicode-aware, not substring — cf. `principles.matched_topics`) with a successful answer, auto-`verify()`. Idle memories age out of trust; useful ones stay fresh.

**6. Ranking:** `retrieve()` multiplies its existing score by a trust factor `0.4 + 0.6 × trust` so low-trust/stale memories sink but strong keyword/semantic matches are never fully suppressed (NNL's `[0.4, 1]` band). Trust level + flag are returned in the record metadata so the prompt-injection layer can render the badge.

## Consequences

### Positive
- Anti-hallucination: stale "facts" are flagged/down-ranked before reaching a confident-but-weak local model.
- Self-maintaining freshness: used memories re-verify; abandoned ones decay — no manual curation.
- Additive: importance (retention) and trust (believability) coexist; no behaviour removed.
- Audit-complete: `verify` logged (K-6); nothing deleted by trust.

### Negative / accepted trade-offs
- One migration on the running pilot (3 nullable columns + backfill defaults — low risk, no data move; K-21: new columns, not new table, so no UUIDv7 concern).
- `confidence` quality depends on the consolidation LLM honestly self-scoring; a mis-scored 0.9 on a wrong fact still injects until it ages past half-life.
- Trust is decay + self-score + usage signal — it **flags** old/unchecked, it does **not** fact-check against the world (same honesty caveat as NNL).

### Neutral / follow-ups
- Backfill: existing rows get `confidence=0.7`, `last_verified_at=NULL`; their trust starts decaying from `created_at` — acceptable.
- L4_LONG records share `memory_l3` today; trust columns apply uniformly.
- Associative recall (follow ontology links on retrieve) is a sibling enhancement tracked separately (Phase 3 task) — not gated on this ADR.
- Builds toward [[feedback_teach_concept_generalize]]: principles (ADR-pending Phase 2 work, in code) + trusted memories + foundational KB (ADR-0033, superseded the dropped 0031 sketch) form the reasoning substrate.
