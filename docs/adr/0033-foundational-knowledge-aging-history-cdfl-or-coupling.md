# ADR-0033 — Foundational knowledge: aging, version history, CDFL |OR| coupling

> **Status:** proposed
> **Date:** 2026-05-28
> **Deciders:** Nguyen Truong An
> **Related:** mig 106 `knowledge_documents` + 107 retail/SME seed · `reasoning/knowledge/store.py` · `reasoning/rag/engines/pgvector_real.py` · ADR-0030 (memory trust) · ADR-0032 (memory palace maturation) · `reasoning/cdfl/hilbert_metric.py` (I(I:M) = |OR|) · supersedes the dropped ADR-0031 sketch

## Context

`knowledge_documents` (mig 106/107) already gives Kaori an authority-tiered, RLS-scoped, pgvector knowledge base seeded with Vietnamese retail/SME principles (RFM, Pareto, NOV, churn). `reasoning/knowledge/store.py` can `put` / `semantic_search` / `list` it. That is the *storage*. Three capabilities anh asked for are **not** yet there, and they are what turns a lookup table into a knowledge layer that *grows wiser*:

1. **Two distinct layers, treated differently.** anh (2026-05-27/28): the **foundational** knowledge (tier 1 regulatory, tier 2 Kaori-curated — definitions, formulas, invariants) is *persistent* — "những gì còn tồn tại lại", it should **age and mature** over time and the system should lean on it more as it accumulates. The **volatile** knowledge (tier 3 market/industry — churn windows, tactic ranges, benchmarks) *changes with the world* on a refresh cycle. Today the tiers exist but the system treats all rows identically (static rows, ranked by pure cosine, no aging, overwrite-in-place).

2. **History so the system can answer "vì sao lại vậy".** When a volatile figure changes (e.g. the retail churn window moves 120→90 days), the *old* value and the *reason* must remain queryable. `status='archived'` exists but there is no version chain (`supersedes`), no `change_reason` — so the system cannot explain *why* a past analysis used a different threshold. anh: "lịch sử bố cục vẫn còn ở trong hệ thống và hệ thống sẽ trả lời được vì sao lại vậy."

3. **CDFL |OR| coupling — the "học 1 hiểu 10" gate.** anh (2026-05-28): generalization ("học 1 hiểu 10") becomes reliable *when there is enough foundational knowledge that |OR| is sufficient*. `cdfl/hilbert_metric.py` already computes `I(I:M)` (the |OR| proxy, v11-verified to correlate with accuracy r=+0.796) but nothing feeds the **breadth of foundational knowledge covering a question** into that signal. Without it, a thin KB either blocks insight or invites hallucination; with it, coverage can *gate* generalization (generalize confidently when covered; say "kiến thức nền chưa đủ" when not).

Forces in tension: persistence vs freshness (foundational must not be churned by volatile refreshes; volatile must not go stale); growth vs drift (maturity should reward *validated* use, not mere age); and the anti-hallucination invariant (more generalization power must not mean more confident fabrication — it must be gated by measured coverage, K-3/|OR|).

## Decision

We extend `knowledge_documents` + `KnowledgeStore` + the retrieval path along three axes, reusing the memory maturation math (ADR-0032) and the existing |OR| metric. (Proposed mig **111** — additive, NOT executed in this ADR.)

**1. Persistence classes by tier (semantics, not new storage).**
- **Foundational** = tier 1 (regulatory) + tier 2 (curated). Persistent; **matures** (§2); refreshed only by deliberate curation; never auto-expired.
- **Volatile** = tier 3 (market). Refreshed on a cycle; a refresh **supersedes** (§3), never overwrites. Carries a `valid_until` hint; past `valid_until` it is flagged "cần cập nhật", not deleted.
- **Tenant** = tier 4. A tenant insight that proves durable can be **promoted** toward curated (the "kho tự nâng cấp basic→nâng cao" loop), gated by maturity (§2).

**2. Aging / maturation (port ADR-0032 to the KB).** Add `confidence NUMERIC(3,2)`, `use_count INT`, `last_reinforced_at TIMESTAMPTZ`. On every analysis that *cites* a doc in a grounded answer, `reinforce()` it — confidence climbs a per-tier ceiling learning-curve (curated > market), `use_count++`. A doc's effective weight = `confidence × 0.5^(age/half_life_for_tier)` — **but** foundational tiers get a long/effectively-infinite half-life (definitions don't decay), while volatile tier-3 decays on its refresh cadence. Net: the KB "knows more" as validated foundational mass accumulates ("càng nhiều tháng càng biết nhiều"), mirroring memory.

**3. Version history → explainability.** A change to a doc inserts a NEW row (`status='active'`) and sets the old row `status='archived'`, `superseded_by = <new id>`; the new row carries `supersedes = <old id>` + `change_reason TEXT`. Retrieval reads `active` only; an audit/why-query walks the chain. This is what lets the system answer "the analysis from March used a 120-day window because tier-3 doc v2 (source: …, archived 2026-04, reason: …) was active then" — provenance over time, not just provenance.

**4. Authority-boosted retrieval.** `semantic_search` ranks by `cosine_sim + W_authority × tier_rank + W_maturity × confidence` instead of pure cosine — a curated tier-2 principle outranks a tier-3 note at similar similarity (NNL `retrieve`). Returns `source · tier · confidence · sim` for citation.

**5. CDFL |OR| coupling — generalization gate.** Define `knowledge_coverage(query) → [0,1]`: aggregate the authority-/maturity-weighted retrieval scores of the foundational docs matching the question's concepts. Feed it as the IF-side breadth into the |OR| reporting (alongside the existing data-grounding |OR|):
- **High coverage** → the model may generalize from foundational principles to un-coded cases ("học 1 hiểu 10") and the insight carries "độ phủ tri thức nền: X%".
- **Low coverage** → the system declines to generalize, emits "kiến thức nền chưa đủ cho câu hỏi này — cần bổ sung [category]", and does NOT fabricate (K-3, anti-bịa). As the foundational KB ages and grows, coverage rises and more generalizations unlock — "nhiều thứ hay ho" emerges *measurably*, not by luck.

**6. Inject foundational knowledge into analysis (closes deferred Phase 2).** The analyze narrative (`legacy_analytics/runner.py`) and insight generation retrieve the top authority-boosted **foundational** docs for the active templates/metrics and inject them as the reasoning preamble — the DB KB *is* the "học 1 hiểu 10" source. The hardcoded `principles.py` (deferred in PR #292) is **not** revived; the curated tier-2 seed already holds those concepts, with provenance and aging the code constants never had.

## Consequences

### Positive
- One knowledge layer that genuinely matures: foundational principles get more trusted with validated use; volatile market data refreshes without losing history.
- The system can explain *why* a past analysis differed — version chains + change_reason make decisions auditable across time (anh's "vì sao lại vậy").
- Generalization is **gated by measured coverage** (|OR|), so a richer KB unlocks more "học 1 hiểu 10" *and* a thin KB fails safe (says "chưa đủ") instead of hallucinating.
- Kills the principles.py duplication — single DB source of truth, authority-tiered, cited.
- Reuses ADR-0032 maturation math + the existing I(I:M) metric — minimal new machinery.

### Negative / accepted trade-offs
- mig 111 adds 5 columns + a self-referential FK (`superseded_by`/`supersedes`) on `knowledge_documents` (additive, nullable; running pilot — low risk).
- Reinforce-on-cite adds a write per grounded analysis; batched/async per [[feedback_llm_in_request_path_bound]], never in the request path.
- `knowledge_coverage` → |OR| mapping is a heuristic bridge between a retrieval score and an information-theoretic quantity; it is a *gauge*, not a proof (same honesty caveat as ADR-0030 trust and the CDFL hilbert_metric docstring).
- Curating tier-1/2 + setting tier-3 refresh cadence is human editorial work.

### Neutral / follow-ups
- Splits into: mig 111 + `KnowledgeStore` aging/version methods (PR 1); authority-boost + coverage signal + analyze injection (PR 2). Each behind the existing RAG engine seam.
- `valid_until` refresh automation for tier-3 is a later job; manual re-curation works first.
- Coupling `knowledge_coverage` into the quantum `mutual_information` gauge vs a separate scalar signal is an implementation choice deferred to PR 2 (a separate scalar that travels in the grounding envelope is the low-risk start).
- The tenant→curated promotion loop (§1) reuses the memory consolidate/promote machinery; detailed in a follow-up once §2 maturity lands.
