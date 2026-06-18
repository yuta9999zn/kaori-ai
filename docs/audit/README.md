# Kaori AI — Audits

> Point-in-time audits: independent verification of what actually runs (live-deep), coverage/calibration checks, and gap analysis. Each audit is a dated snapshot — it captures the system as it was on that date, not a living spec.

## What goes here

- **Live-deep audits** — run shipped features for real through the running stack (gateway + orchestrator + DB) and verify behavior, not just unit tests.
- **Coverage / calibration reviews** — e.g. whether the AI grounding gates (`|OR|`, coverage thresholds) are as tight as designed.
- **Gap analysis** snapshots that complement the canonical, living gap tracker.

These are **historical evidence**, not requirements. For the canonical, maintained gap list see [`../GAPS_V4.md`](../GAPS_V4.md).

## Current audits

| Date | Doc | Summary |
|---|---|---|
| 2026-06-02 | [`2026-06-02-feature-audit-live-deep.md`](2026-06-02-feature-audit-live-deep.md) | Live-deep audit of the PR #333–#338 cluster + Tier-3 epic. Verdict: features run for real (~85% "built"); reviewer's 60–65% was artificially low (gateway route gaps + fragmented data). Found 1 P1 finding in the CDFL `\|OR\|` grounding calibration (decline-branch nearly dead because mass = sum of similarities lets quantity offset quality) + several P2 robustness/hygiene items. |

> Related: gap tracker [`../GAPS_V4.md`](../GAPS_V4.md) · invariants [`../K_RULES_INDEX.md`](../K_RULES_INDEX.md) · ADRs [`../adr/`](../adr/).
