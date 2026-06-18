# ADR-0036 — Memory: tier/type axes cleanup, classic-4-type view, memory→KB promotion

> **Status:** accepted (shipped 2026-05-30)
> **Date:** 2026-05-30
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0030 (memory trust) · ADR-0032 (memory palace) · ADR-0033 (foundational KB + CDFL |OR| coupling) · NNL-NTHT thesis (`Phan_I/III/V`, "10 tiên đề gốc", `Phan_IV_Dong_hoc_CDFL`) · `reasoning/memory/{types,service}.py` · `reasoning/knowledge/store.py` · `reasoning/cdfl/hilbert_metric.py`

## Context

Reviewing the memory/knowledge/CDFL stack against the NNL-NTHT thesis (IF∩MF=OR, K=Φ(OR), DE≠∅, maximize |OR|) confirmed the implementation is a faithful operationalisation: `cdfl/hilbert_metric.py` measures |OR| (I(I:M), r=+0.796 vs accuracy); ADR-0033 gates generalisation ("học 1 hiểu 10") on measured foundational coverage and otherwise declines instead of fabricating (DE acknowledged, K-3); ADR-0032 shapes a per-tenant palace with consolidation, associative recall and maturation.

anh asked about the **four classic cognitive memory types** (working / semantic / procedural / episodic) — should Kaori custom-build them? Inspection shows Kaori **already covers them and more**: `MemoryType` has SEMANTIC, PROCEDURAL, EPISODIC (+ OPERATIONAL, DECISION); working memory is the **L1 tier**; per-type trust half-lives already encode the cognitive durability difference (semantic/procedural age slowly, episodic fast). So no new store is needed. Two genuine gaps remained:

1. **Axis overload.** `MemoryTier` (a LIFECYCLE axis) had a member `L3_EPISODIC` whose name collided with the EPISODIC *type* (a CONTENT axis) — conflating two orthogonal axes and obscuring the 4-type mapping.
2. **No memory→KB promotion loop.** ADR-0032/0033 describe "kho tự nâng cấp" (a mature tenant insight feeds the foundational KB that powers the coverage gate), but `promote()` only moved L3→L4 within memory; nothing fed a validated memory into the knowledge layer.

## Decision

**1. Separate the two axes (no migration — `tier` is not persisted, it is assigned by the store).**
- `MemoryTier` is the **lifecycle** axis only: `L1_WORKING → L2_SHORT → L3_CONSOLIDATED → L4_LONG`. Renamed `L3_EPISODIC → L3_CONSOLIDATED`.
- `MemoryType` is the **cognitive category** axis (unchanged: 5 types).

**2. Classic-4-type taxonomy as a documented VIEW (not a new build).** `classic_memory_class(MemoryType) → {episodic|semantic|procedural}` + `CLASSIC_MEMORY_CLASS`: EPISODIC/DECISION→episodic, SEMANTIC→semantic, PROCEDURAL/OPERATIONAL→procedural; **working = the L1 tier** (a lifecycle stage, not a type). The classic model is thus a lens over what already exists — no `cognitive_class` column, no churn.

**3. Memory → tenant-KB promotion loop (`MemoryService.promote_to_knowledge`).** A mature, validated PROCEDURAL/SEMANTIC/OPERATIONAL memory (trust ≥ 0.8, ≥2 validated appearances) is written into the tenant's **own tier-4** `knowledge_documents`, so it feeds ADR-0033's coverage gate. **Tenant-scoped only (K-1)** — elevation to global curated (tier 1-2) stays a human-gated step. Idempotent (deterministic `uuid5` doc id from the memory; memory flagged `promoted_to_kb` once). LLM-free + cheap → runs in the consolidate cron.

**4. PROCEDURAL room seed (`seed_procedural_from_kb`).** Bootstraps the "phương-pháp" room from the foundational KB (tier 1-2) with **thin pointer recipes** — content references the KB doc, it does NOT copy the principle body (no duplication, honouring ADR-0033's "no principles.py"). Idempotent via deterministic record id.

## Consequences

### Positive
- The 4 classic memory types are answered: already present (3 types + working=L1 tier), richer (trust + maturation + per-type half-life), and now an explicit `classic_memory_class()` view — no rebuild.
- Tier vs type are no longer conflated; `L3_CONSOLIDATED` reads as a lifecycle stage.
- The "kho tự nâng cấp" loop is closed tenant-side: validated memory → tenant KB → coverage gate → more "học 1 hiểu 10", measurably (ADR-0033 |OR|).
- Zero migration: rename is safe (`tier` not a stored column), promotion reuses `knowledge_documents` tier-4 path.

### Negative / accepted trade-offs
- `promote_to_knowledge` is heuristic on trust/appearance thresholds (env/knob-tunable later); same honesty caveat as ADR-0030 trust.
- Promotion stops at tenant tier-4; cross-tenant curation (tier 1-2) is deliberately NOT automated (K-1 + editorial judgement).
- `seed_procedural_from_kb` adds thin recipe memories — pointers, not content; a renamed KB doc leaves a dangling pointer (tolerated, same as ADR-0032 links).

### Neutral / follow-ups
- Wire `promote_to_knowledge` into the existing consolidate/maturation cron (after `consolidate` + `promote`).
- Knobs for the promotion thresholds via `ai_config` (mirrors `memory_promotion_threshold`).
- Tests: `test_memory_promotion.py` (classic view + promote idempotency/maturity gate + seed). Full suite 2797 pass.
