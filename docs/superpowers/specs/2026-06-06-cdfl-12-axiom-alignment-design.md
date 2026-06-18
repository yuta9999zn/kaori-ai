# CDFL ↔ 12-Axiom (NNL-NTHT) Alignment + Agent-Protection — Design Spec

> **Date:** 2026-06-06 · **Author:** Nguyen Truong An · **Status:** design
> **Touches:** `reasoning/cdfl/*` · `reasoning/grounding.py` · ADR-0033 coverage · workflow `oversight.py`/`side_effect` · ADR-0041
> **Superpowers:** spec → plan (`docs/superpowers/plans/`) → subagent-driven TDD.

## Context

Kaori already ports CDFL from the luận văn (NNL-NTHT). The thesis has since been
corrected to a **12-axiom** framing (see luận văn Phần IX + "12 tien de"). Three
corrections matter for code:

1. **DE is four-fold, not "MF unknown".** DE = the unknown across **không gian (X),
   thời gian (T), IF chưa biết, MF chưa biết**; `DE ≠ DE_IF + DE_MF`. The explicit
   quantity is `DE = S(ρ_MF ‖ σ_IF)` (relative entropy) — complementary to
   `|OR| = I(I:M)`.
2. **OR↔DE is the âm–dương pair, with two seeds (đốm).** Knowledge needs **two
   detectors**: Φ-vs-Φ (ensemble disagreement → "đốm trắng": representation gap) and
   **Φ-vs-REALITY** (prediction error → "đốm đen": *confidently wrong* / giả-dương).
   Disagreement alone is BLIND to đốm-đen (the luận văn neural-IF experiment showed
   ensemble disagreement *avoids* the hard region; only reality-comparison catches it).
3. **Continual / sàn DE.** In a changing world (volatile knowledge) DE re-grows;
   "hội tụ" is asymptotic, never a stop. The Hilbert dynamics decohere without an
   explicit learning term `∂_tσ_IF = −α∇_σ S(ρ_MF‖σ_IF)` (luận văn v13.1) — but Kaori
   only ports the **measurement** layer (v11 caveat), so decoherence is not a runtime
   risk here; the lesson is conceptual.

## How Kaori already maps (assessment — it is ~80% aligned)

| 12-axiom concept | Kaori component | Status |
|---|---|---|
| `\|OR\| = I(I:M)` | `cdfl/hilbert_metric.mutual_information` | ✅ present |
| `DE = S(ρ_MF‖σ_IF)` | `cdfl/hilbert_metric.relative_entropy` | ✅ **added (this spec, PR0)** |
| đốm-đen (Φ-vs-reality) | `reasoning/grounding.py` — claims vs measured facts, flags fabrication, never silently rewrites | ✅ **correct detector** |
| IF-face (representation breadth) | ADR-0033 `knowledge_coverage` → gate "học 1 hiểu 10" / refuse + "kiến thức nền chưa đủ" | ✅ present |
| T-face (knowledge ages) | ADR-0033 volatile half-life / maturation (ADR-0032) | ◑ at KB layer; NOT in `IGScorer` counts |
| X/MF-face (novelty) | `cdfl/IGScorer` `1/√N` | ✅ present (static) |
| Protect other agents (empowerment) | `side_effect_class` (reversible vs impactful) + K-23 oversight gate (ADR-0041) | ◑ **mechanism exists, framed as compliance not as OR-principle** |

**Verdict:** Kaori independently re-derived most of the corrected framework. The
gaps are (a) DE not exposed as a gauge [fixed], (b) the two detectors not named as a
pair, (c) T-face not in the CDFL novelty score, (d) agent-protection not grounded in
the OR/empowerment principle.

## Decisions

**D1 — DE primitive (DONE, PR0).** Added `relative_entropy(ρ,σ)` to `hilbert_metric.py`
+ 5 tests (20/20 pass). DE now a first-class gauge beside |OR|. Clipped-σ so
"confidently wrong" gives a large-but-finite DE (the giả-dương signal), not +∞.

**D2 — Name the two detectors (âm–dương).** Document `grounding.py` as the **đốm-đen**
detector (Φ-vs-reality) and `knowledge_coverage` (ADR-0033) as the **đốm-trắng**
detector (representation breadth). Add a one-paragraph module note to each + a shared
`reasoning/cdfl/four_fold_de.py` that assembles a **DE report** `{x, t, if_, mf}` from
the signals already computed (no new measurement; a typed envelope). Travels in the
grounding envelope for observability.

**D3 — T-face in IGScorer (optional, gated).** Add a recency-decayed count option to
`IGScorer`/`TransitionModel` (leaky `N`) so novelty re-grows for stale (s,a) — mirrors
ADR-0033 volatile aging at the algorithmic layer. Default OFF (decay=1.0) → exact
current behaviour; opt-in for continual/volatile contexts. Pure, unit-tested.

**D4 — Agent-protection = empowerment, grounded.** The OR/empowerment principle says:
*do not shrink another agent's option-space*. An **irreversible** side-effect
(`write_non_idempotent`/`external`) is exactly an OR-shrinking act on the human/other
agents; a **reversible** one preserves their options. Kaori's K-23 gate already pauses
on impactful actions for high-risk flows — **this IS empowerment-based protection**.
Re-frame + extend:
- Document the oversight gate as the **OR-preservation / empowerment gate** (the EU-AI
  -Act obligation is the legal face; option-preservation is the principled one).
- Add a pure `empowerment.py` helper: `option_preserving(side_effect_class) -> bool`
  and `protection_advice(...)` that, for an impactful action, prefers a reversible
  alternative when one exists / recommends the gate — the agent **defaults to the
  human-option-preserving action**, asks before the option-shrinking one.
- The human (and any sub-agent) is the "tác tử khác" whose OR we preserve. This mirrors
  the luận văn *sanctuary* result: a goal-seeking agent + an OR/empowerment term
  protects others at ≈0 task cost (Phần IX §2.5).

## Consequences

- Positive: CDFL gauges now include DE (not just |OR|); the anti-fabrication +
  coverage gates get a unifying name + envelope; agent-protection gains a principled,
  testable basis (empowerment) on top of the compliance basis — same mechanism, deeper
  justification, and a default-to-reversible nudge.
- Negative/accepted: D2/D3/D4 are additive (new pure modules + opt-in flags); no
  production path changes by default. The `four_fold_de` report is a *gauge*, not a
  proof (same honesty caveat as the grounding & |OR| docstrings).
- Out of scope (do NOT do): porting the v10 Lindblad action loop (v11: not better than
  random); silently auto-blocking actions (protection must surface + ask, never
  silently rewrite — BR-9 / K-23 human-in-the-loop).

## Honest limitations
- DE four-fold report bridges heterogeneous signals (entropy gauge + retrieval score +
  reversibility flag) — a coherent *dashboard*, not one number.
- Empowerment here = reversibility proxy (option count), not a full information-theoretic
  empowerment computation; sufficient for the gate, honest about being a proxy.

## Follow-up plan (→ `docs/superpowers/plans/2026-06-06-cdfl-12-axiom-alignment.md`)
- PR0 ✅ DE primitive + tests (done).
- PR1: `four_fold_de.py` envelope + detector docstrings (D2). TDD.
- PR2: `IGScorer` recency option (D3). TDD, default-off.
- PR3: `empowerment.py` + re-frame oversight as OR-preservation; wire `protection_advice`
  into the orchestrator advisory path (D4). TDD; gated behind the existing oversight seam.
