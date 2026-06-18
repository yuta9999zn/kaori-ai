# CDFL 12-Axiom Alignment — Implementation Plan (D3 + PR3)

> **For agentic workers:** use superpowers:subagent-driven-development (or executing-plans) — task-by-task TDD, checkbox tracking.
> **Spec:** `docs/superpowers/specs/2026-06-06-cdfl-12-axiom-alignment-design.md`. PR0 (DE primitive `relative_entropy`), D2 (`four_fold_de.py`), D4-core (`empowerment.py`) are DONE + tested (30 green). This plan covers **D3** (T-face recency in CDFL novelty) and **PR3** (wire empowerment advice into the action path + re-frame oversight as OR-preservation).

**Tech Stack:** Python 3.11, ai-orchestrator, pytest. Pure modules + one additive field on agent action-tool results. No migration, no production control-flow change (advisory only — BR-9 / K-23 keep the human in the loop).

**Branch:** `feat/cdfl-12-axiom-alignment`.

**Invariants:** K-3 anti-hallucination (advice never fabricates), K-6 audit unaffected, BR-9 disclaimer-not-rewrite (empowerment ADVISES, never auto-blocks), K-17 side_effect taxonomy reused.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `reasoning/cdfl/transition_model.py` | optional recency decay on visit counts (T-face) | Modify |
| `reasoning/cdfl/information_gain.py` | novelty re-grows for stale (s,a) when decay enabled | Modify |
| `tests/test_information_gain_recency.py` | T-face unit tests | Create |
| `chat/tools/base.py` (or action tools) | declare `option_impact` per tool | Modify |
| `reasoning/cdfl/empowerment.py` | `advise_for_result(...)` envelope helper | Modify |
| `agents/tools/actions.py` | attach `protection` advisory to tool result | Modify |
| `tests/test_action_empowerment.py` | action result carries protection advice | Create |
| `workflow_runtime/oversight.py` | docstring: gate = OR-preservation (empowerment) | Modify |

---

## Task 1 (D3): T-face recency in CDFL novelty

**Why:** Tiên đề 10/11 — in a changing world knowledge ages; novelty must re-grow for stale (s,a). Mirrors ADR-0033 volatile aging at the algorithm layer. Default OFF (decay=1.0 → identical to today).

- [ ] **Step 1 — failing test.** Create `tests/test_information_gain_recency.py`:
```python
from ai_orchestrator.reasoning.cdfl.transition_model import TransitionModel
from ai_orchestrator.reasoning.cdfl.information_gain import IGScorer

def test_decay_off_is_current_behaviour():
    m = TransitionModel(recency_decay=1.0)
    s, a = ("s0",), "look"
    for _ in range(4): m.record(s, a, ("s1",))
    ig = IGScorer()
    # 4 visits → novelty = 1/sqrt(5) regardless of time
    assert abs(ig.novelty(m, ("s1",)) - 1/ (5 ** 0.5)) < 1e-9

def test_recency_decay_regrows_novelty():
    m = TransitionModel(recency_decay=0.5)
    s, a = ("s0",), "look"
    for _ in range(4): m.record(s, a, ("s1",))
    base = m.state_visit_count(("s1",))
    for _ in range(20): m.tick()          # time passes, no re-visit
    assert m.state_visit_count(("s1",)) < base   # effective count decayed
```
- [ ] **Step 2 — run, expect FAIL** (`recency_decay`/`tick` missing).
- [ ] **Step 3 — implement.** Add `recency_decay: float = 1.0` to `TransitionModel`; store visit counts as floats; `tick()` multiplies all counts by `recency_decay`; `record()` increments by 1. When `recency_decay == 1.0`, behaviour is exactly today's integer counting. `IGScorer` is unchanged (reads `state_visit_count`). Document: decay<1 = T-face (DE re-grows); 1.0 = static (default).
- [ ] **Step 4 — run, expect PASS.** Plus run `tests/test_information_gain.py` (if present) + `test_hilbert_metric.py` for no regression.
- [ ] **Step 5 — commit** `feat(cdfl): optional recency decay (T-face) in novelty, default-off`.

---

## Task 2 (PR3): empowerment advice on action results

**Why:** D4 — surface OR-preservation advice on every agent action so the human sees whether it preserves their option-space. Advisory only (BR-9). The v0 tools are already option-preserving (draft/flag for review, never auto-send) — make that explicit + machine-checked.

- [ ] **Step 1 — declare option impact.** In each action tool (`DraftFollowupEmailTool`, `MarkCustomerForReviewTool`) add a class attr `option_impact = "preserving"` (they record a reviewable artifact; the human still decides → preserve the human's OR). A future auto-send tool would declare `"shrinking"`. (Keep separate from `side_effect_class`: idempotency ≠ option-impact; a non-idempotent audit INSERT can still be option-PRESERVING for the human.)

- [ ] **Step 2 — helper.** In `reasoning/cdfl/empowerment.py` add:
```python
def advise_for_result(option_impact: str, *, reversible_alternative_exists: bool = False) -> dict:
    """Map an action's option_impact → a small advisory dict for the tool result."""
    preserving = option_impact == "preserving"
    adv = protection_advice(
        "read_only" if preserving else "external",
        reversible_alternative_exists=reversible_alternative_exists,
    )
    return {"preserves_options": adv.preserves_options,
            "needs_consent": adv.needs_consent,
            "note": adv.rationale}
```
- [ ] **Step 3 — failing test.** Create `tests/test_action_empowerment.py`: a `draft_followup_email` dry-run result contains `protection.preserves_options is True` and `needs_consent is False`; assert a hypothetical `option_impact="shrinking"` → `needs_consent True` via `advise_for_result` directly.
- [ ] **Step 4 — wire.** In each action tool `execute`, add `"protection": advise_for_result(self.option_impact)` to the returned dict (both dry-run and side-effect branches). Pure-additive field; no control-flow change.
- [ ] **Step 5 — run tests, expect PASS;** run `tests/ -k "action or tool"` for no regression.
- [ ] **Step 6 — commit** `feat(cdfl): empowerment advice on agent action results (OR-preservation)`.

---

## Task 3 (PR3): re-frame oversight as OR-preservation (docs only)

- [ ] **Step 1.** In `workflow_runtime/oversight.py` docstring, add a paragraph: the K-23 gate on impactful (`write_non_idempotent`/`external`) side-effects IS the empowerment / OR-preservation gate — it pauses exactly the actions that shrink other agents' option-space; the EU-AI-Act obligation and the NNL-NTHT OR-principle coincide. Cross-link `reasoning/cdfl/empowerment.py`. No logic change.
- [ ] **Step 2 — commit** `docs(cdfl): frame K-23 oversight as OR-preservation (empowerment)`.

---

## Self-Review
- D3 default-off → zero behaviour change unless opted in; T-face available for continual/volatile contexts.
- PR3 advisory-only → never blocks/auto-acts (BR-9, K-23 human-in-the-loop preserved); makes the existing option-preserving design machine-checked + visible.
- Honest: `option_impact` is a per-tool declaration (a proxy), not a derived guarantee; the gate remains the hard control.
- Scope: pure modules + one additive result field + docs. No migration, no endpoint, no control-flow change.
