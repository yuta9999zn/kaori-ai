# ADR-0032 — Memory Palace: consolidation + associative recall

> **Status:** proposed
> **Date:** 2026-05-27
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0024 (mem0-inspired ports) · ADR-0030 (memory trust layer) · NNL-Harness `harness/memory.py` (MemoryPalace) · Claude Code file-memory (`~/.claude/.../memory/`) · `services/ai-orchestrator/reasoning/memory/` + `reasoning/ontology/` · mig 067 (memory_l3, has `extra_metadata JSONB`) · K-1 · K-6

## Context

Stage 7 Memory ships a 4-tier hierarchy (L1-L4), 5 typed memories, importance scoring, a `consolidate(L2→L3)` skeleton, pgvector retrieval, and a *separate* Neo4j ontology. ADR-0030 adds a trust layer (believability). What's still missing is the **palace** shape anh asked for: short-term memories from a just-finished session **distilled and placed into the right "room" as durable long-term memories, then recalled associatively along links** — exactly the mechanism Claude Code's own file-memory uses (rooms = categorised files, `MEMORY.md` index, frontmatter `confidence/source/created/last_verified`, `[[links]]`, dedup-on-write) and NNL-Harness's `MemoryPalace`.

Today's `consolidate()` is a thin L2→L3 mover: it does not LLM-extract *distinct durable facts*, self-score their confidence, dedup against existing memories by name, or link them. And `retrieve()` ranks by similarity/importance but never **follows links** to pull in connected neighbours — so the ontology graph Kaori already maintains is unused at recall time. The result: memory is a flat bucket, not a navigable palace.

Forces in tension:
- A graph/palace is richer but Kaori already has a graph store (Neo4j ontology) — adding a *second* edge store would duplicate (violates "explicit over implicit", same caution as ADR-0024).
- We want the proven claude-mem / NNL consolidation behaviour, but it must be **per-tenant** (K-1) — NNL and claude-mem are single-subject; Kaori has one palace per enterprise.
- We want addressable "rooms" without a schema churn — `memory_l3` already carries `memory_type` and `extra_metadata JSONB`.

## Decision

We shape long-term memory as a **per-tenant palace** on top of the existing tables — no new table — with three mechanisms:

**1. Rooms + addressing (no new column).** A memory's **room** is its `memory_type` (the coarse category: `PROCEDURAL` = the "phương-pháp" room for recipes/principles, `DECISION`/`OPERATIONAL` = analysis decisions, `SEMANTIC` = learned domain facts, `EPISODIC` = events). Its **address** is `tenant_id / memory_type / name`, where `name` is a stable slug stored in `extra_metadata.name`. This mirrors NNL `room/name` and claude-mem's `room/file.md` without a migration.

**2. Consolidate short→long (the claude-mem mechanism).** Replace the thin mover with an LLM consolidation (Qwen, K-4) run at session end / 24h:
- Read recent L2 turns for the tenant.
- LLM extracts **each distinct durable fact as its own memory**, classifies it to a room (`memory_type`), and **self-scores `confidence`** (feeds ADR-0030 trust; "không bịa độ tin cao").
- **Dedup by address** — if a memory with the same `name` exists, update it (preserving `created_at`/trust per ADR-0030's `place`-keeps-metadata rule).
- **Link** the new memory to related existing ones (edges, see §3).
- Writes a K-6 audit row per consolidation.

**3. Associative recall (reuse the ontology, don't duplicate).** `retrieve()` keeps its hybrid (keyword + semantic + trust) ranking, then does a **1-hop link expansion**: for top hits, pull connected neighbours. Edges come from two sources, no new table:
- **Entity edges** — via the existing Neo4j ontology (`reasoning/ontology/`) when memories share an `entity_id` (customer/product node).
- **Memory-to-memory edges** — stored in `extra_metadata.links` (a list of addresses), set during consolidation. JSONB column already exists.

Expanded neighbours are tagged `via=<source address>` so the prompt layer shows the association path (NNL `recall` behaviour).

**4. Maturation — experience grows over time (the counterpart to decay).** ADR-0030's decay makes an *unused* memory fade; maturation makes a *used, validated* memory — and the tenant's competence as a whole — **grow**, like a person gaining experience over the years (anh, 2026-05-27). Two configurable mechanisms:

- **Confidence reinforcement (a learning curve).** On each validated reinforcement (reinforce-on-use, §2 link to ADR-0030 `verify`), confidence climbs toward a per-source ceiling asymptotically:
  `confidence ← confidence + LEARN_RATE × (ceiling − confidence)`.
  Ceilings: `user 0.98 > consolidate/rag 0.90 > derived 0.85` — **never 1.0** (epistemic humility), and a derived guess can never become as certain as a user-stated fact. Fast early gains, plateauing mastery — a fact confirmed many times is trusted more than one confirmed once. Knob: `KAORI_MEM_LEARN_RATE` (default 0.15).

- **Tenant experience level.** Derived, read-only:
  `experience = 1 − exp(−k × Σ trust_score)` over the tenant's still-trusted L4 memories. Saturating in [0,1): early learning is rapid, mastery asymptotic; knowledge that stops being used **decays out of the mass**, so the score reflects *maintained* competence — not a one-time high-water mark. Reported alongside `tenure_days` (time since the first memory — the literal "tuổi nghề") and a band: `mới → tập sự → thành thạo → dày dạn → chuyên gia`. Knob: `KAORI_MEM_EXPERIENCE_K` (default 0.15). Surfaces in the UI/report as e.g. "Kaori đã tích luỹ N insight đã kiểm chứng cho DN này".

Net: decay + maturation together model a practitioner — skills maintained grow and grow more certain; skills abandoned fade. Every parameter is env-configurable, so the maturation curve can be tuned per deployment.

## Consequences

### Positive
- Memory becomes a navigable palace (rooms + links), not a flat bucket — recall surfaces *related* context, not just lexically-near rows.
- Consolidation matches the proven claude-mem / NNL behaviour: distinct facts, right room, self-scored confidence, dedup, links — the "ngắn hạn → dài hạn" transfer anh described.
- Zero new tables: rooms = `memory_type`, addressing + links = `extra_metadata JSONB`, entity edges = existing ontology. Pairs with ADR-0030 (confidence/source/last_verified columns) — together they're the full palace.
- Per-tenant by construction (RLS on `memory_l3`, ontology already tenant-scoped) — K-1 safe, unlike single-subject claude-mem/NNL.

### Negative / accepted trade-offs
- Consolidation now calls the LLM (cost + latency) — bounded per [[feedback_llm_in_request_path_bound]]: runs async/batch (24h or session-end), never in the request path; gated off on the 7B pilot if needed.
- 1-hop expansion adds an ontology lookup per retrieve — capped (top-K hits, 1 hop) to bound fan-out.
- Self-scored confidence is only as honest as the consolidating model (same caveat as ADR-0030).
- `extra_metadata.links` holds addresses, not FKs — a forgotten/renamed target is a dangling link (tolerated: recall just skips unresolved addresses, as NNL does).

### Neutral / follow-ups
- Seeding the `PROCEDURAL` room with the Phase 2 principles/recipes (NNL `seed_principles`) is the natural bridge to ADR-0033's foundational KB (superseded the dropped 0031 sketch) — a learned, validated insight can later be promoted from a tenant memory into the `curated` KB tier (this is the "kho tự nâng cấp basic→nâng cao" loop anh described).
- A `MEMORY.md`-style per-tenant palace map (human-readable index) can be generated on demand for the UI — not required for the mechanism.
- Depends on ADR-0030's columns landing first (confidence/source/last_verified); these two ADRs ship as one Phase-3 migration.
