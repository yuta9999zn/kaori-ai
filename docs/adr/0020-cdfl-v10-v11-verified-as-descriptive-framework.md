# ADR-0020 — Accept CDFL v10/v11 as the descriptive math framework for NNL-NTHT, port measurement primitives only

> **Status:** accepted
> **Date:** 2026-05-17
> **Deciders:** Nguyễn Trường An (anh)
> **Related:**
> - ADR-0019 — Vectorless tree retrieval + structured SQL RAG (PageIndex + DocSage)
> - `docs/strategic/REASONING_LAYER.md` PART V (CDFL section, Tuần 4-6 port)
> - `D:\Luận văn nhất nguyên 2 trường luận giao thoa\report CDFL v10.zip`
> - `D:\Luận văn nhất nguyên 2 trường luận giao thoa\report CDFL v11.zip`
> - `services/ai-orchestrator/reasoning/cdfl/` (existing v3 algorithmic port)

## Context

V3 of CDFL (Tuần 4-6 — commits `e8efb01`, `560266e`, `9296019`, `81da71d`) ported the 3-component algorithmic core (transition model + lookahead + information gain) into `services/ai-orchestrator/reasoning/cdfl/`. That port treated CDFL as an exploration algorithm and embedded it in Process Mining + Workflow Planner + RAG re-rank.

Versions 10 and 11 of the luận văn report something different:

- **Phase 10 (`report CDFL v10.zip` 2026-05-15)** implements the **full Hilbert-space formalism** end-to-end: ρ_{IM} density operator (Hermitian, positive, trace 1, 81×81), three Φ̂_α projection operators (pluralism), Hamiltonian Ĥ_total = Ĥ_I ⊗ I + I ⊗ Ĥ_M + Ĥ_int with Ĥ_int = Σ_α g_α (Â_α^I ⊗ B̂_α^M), Lindblad dynamics, M̂_int Kraus measurement operators, γ regulator function, and |OR| = I(I:M) via von Neumann mutual information. **Result:** the machinery works; I(I:M) reaches 2.74 of the theoretical ≈ 4.4 max.

- **Phase 11 (`report CDFL v11.zip` 2026-05-15)** runs the bridge test: does the formal metric `I(I:M)` correspond to actual environment understanding? **Result:** correlation r(I(I:M), prediction accuracy) = +0.796 across 3 seeds × 120 steps. Position confirmed: NNL-NTHT is a descriptive math framework that captures how interactional dynamics build internal representation. **Caveat from v11 ablation:** active vs random action selection both reach 100% prediction accuracy in 3 steps — the framework is **descriptive**, not **prescriptive**. There is no algorithmic advantage to "intelligent" action selection at the scale tested.

This ADR records the decision on what to **port** and what NOT to port.

## Decision

### Port the measurement primitives

Add `services/ai-orchestrator/reasoning/cdfl/hilbert_metric.py` exposing:

- `von_neumann_entropy(rho)` — S(ρ) = -tr(ρ log ρ)
- `partial_trace(rho, dim_keep, dim_trace, *, keep_first)` — tr_B or tr_A
- `mutual_information(rho_IM, dim_I, dim_M)` — I(I:M) = S(ρ_I) + S(ρ_M) - S(ρ_{IM})
- `make_random_hermitian(dim, scale, seed)` — Hermitian fixture for tests
- `make_pure_product_state(dim_I, dim_M)` — canonical |I_0⟩⟨I_0| ⊗ |M_0⟩⟨M_0| initial state

These are pure numpy, no scipy required. Test coverage: 15 cases in `tests/test_hilbert_metric.py` — pure state entropy = 0, maximally mixed = log d, partial trace product identity, Bell-pair I(I:M) = 2 log 2 (verified by H ⊗ I → CNOT construction), nonnegativity over random density operators, seed reproducibility.

### Do NOT port the action-selection loop

The v10 implementation includes:
- `FullFormalismCDFL.step_interaction(classical_action, observed_state)` — Hamiltonian evolution + Lindblad dissipation + weak observation conditioning
- Action selection: pick the action that maximises expected ΔI(I:M)

V11 ablation showed these don't beat random action selection at the scale tested (4-state cyclic env, deterministic transitions, ε = 0.15 observation strength, 3 seeds × 120 steps). Importing the loop would add a scipy.linalg dependency, ≈ 2 ms per step in 4×4 dim, and a fragile abstraction for **no measurable algorithmic gain**. We pay the cost of the metric (`mutual_information` is cheap on small ρ) without paying for the loop.

### Use I(I:M) as observability metric, not as decision signal

Where the metric could land in Kaori (Phase 2+, deferred — this ADR does not ship integration, just the primitives):

- **DocSage observability** — after Schema Discovery + Extraction completes, compute I(I:M) over a small (dim_I, dim_M) representation of (schema-discovered concepts, doc-derived rows). Track `kaori_docsage_iim` gauge. Tenants whose DocSage queries grow this metric over a 14-day baseline are "building understanding"; those who don't, aren't. Not a kill switch — observability only.
- **Adoption signals** — adoption signal 7 ("structured understanding growth") could be defined as Δ I(I:M) over a 30-day window of accumulated session traces.

Neither integration ships in this ADR. The decision is to **port the primitive** so future ADRs can wire it without scope-creeping today's commits.

## Why not port everything

Three reasons.

1. **V11 honesty.** v11 explicitly says the framework is descriptive, not prescriptive. Importing the action-selection loop sells a capability we don't actually have. The honest version of "use CDFL v10/v11" is: import the measurement, leave the loop in the research repo.

2. **Cost.** Lindblad evolution on 81×81 complex matrices takes scipy.linalg.expm; the random Hermitian Hamiltonians per restart are 200+ lines of init. Production code carrying that for a metric that doesn't beat `count(distinct state)` would be misallocated complexity.

3. **Future flexibility.** Once we have telemetry on I(I:M) in real tenant traffic (P15-S11+ telemetry hook lands separately) we'll know whether the prescriptive direction (action-selection on top of I(I:M)) deserves another look at larger scales. Premature import locks us in.

## Consequences

### Positive

- Researchers / paper-writers (anh) can now `from reasoning.cdfl.hilbert_metric import mutual_information` and reproduce v11's correlation result inside the production codebase, not in a separate research zip.
- The reasoning layer's CDFL module advertises both layers (v3 algorithmic + v10/v11 measurement) in its docstring — future contributors see the full provenance.
- Tests in `tests/test_hilbert_metric.py` lock the four identities (pure state entropy = 0; product state I(I:M) = 0; Bell pair I(I:M) = 2 log 2; nonneg) — regression catches in CI.

### Negative

- Doc updates needed in `REASONING_LAYER.md` PART V — currently references v3 only. Follow-up commit.
- The naming `cdfl/` now contains both algorithmic and measurement layers; some users might expect a unified `CDFLAgent.compute_iim()` method. The split is intentional and documented in `__init__.py` — but a future refactor might lift `hilbert_metric` to a sibling `reasoning/iim/` if confusion is reported.

### Neutral

- ai-orchestrator pytest count: +15 (hilbert_metric). No production code path uses the new functions today — pure addition.

## Decision drivers

- Anh's directive 2026-05-17: "report CDFL v10 và v11 đã được kiểm chứng là một frameword toán học giúp AI hiểu môi trường dễ dàng học tập hơn — hãy update lại và sử dụng nó".
- v11 final position statement (verbatim): "NNL-NTHT là một descriptive mathematical framework đem ra cấu trúc cho understanding-building qua interaction. Their entanglement (measured by I(I:M)) grows monotonically during interaction; growth correlates với prediction accuracy."
- The ablation finding from v11 §Test 2: action selection redundant at scale tested → port metric, skip loop.

## Open questions (defer to next ADR if needed)

1. When telemetry on tenant DocSage queries lands, what is the empirical correlation between I(I:M) growth and DocSage answer accuracy on real corpora? V11 used 4-state synthetic env; real corpora are 100+ entities.
2. Does CDFL v12+ propose an algorithmic advantage that beats random? If yes, re-evaluate the "skip loop" half of this decision.
3. Should `hilbert_metric` move out of `cdfl/` into a sibling `reasoning/iim/`? Defer until 2+ non-CDFL callers materialise.

---

*Provenance:* `D:\Luận văn nhất nguyên 2 trường luận giao thoa\report CDFL v10.zip` and `report CDFL v11.zip` (Phase 10 + 11 reports, Claude-authored, 2026-05-15). Authoritative copies of the reports are NOT vendored into the repo — license unknown; reference the luận văn source path.
