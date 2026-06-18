# ADR-0022 — Org-tree first, workflow second, data third onboarding order

> **Status:** accepted
> **Date:** 2026-05-17
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0010 (modular monolith) · `docs/strategic/PLAYBOOK_90DAY.md` §2 · mig 053-069 (workflow builder + templates + node catalog) · mig 055-057 (corporate tree)

## Context

Original PLAYBOOK_90DAY.md v3.0 sequenced Week 1 (D1-D7) as:

```
D1   Workspace + first login
D2-3 Department setup (flat list)
D4-5 First data upload
D6-7 Bronze validation + quality scorecard
```

Customers like Vingroup-class conglomerates (1 group × 8 divisions × 16 subsidiaries × many depts) don't have a "flat department list". Their org tree is the FIRST thing to model — and ignoring it forces them to either (a) flatten the structure prematurely (loses information) or (b) wait to upload data because they don't know which folder yet.

Separately, Phase 2 P2-S15 shipped (2026-05-17):
- Mig 055/056/057: `corporate_groups` + `business_divisions` + enterprises FK + `workflow_cross_links` workspace-scoped (Vingroup demo 1 group × 8 div × 16 sub).
- Mig 068: `node_type_catalog` 45-row.
- Mig 069: 25 production templates × `industry_vertical` tag (marketing/sales/CS/warehouse/finance × 5 each).
- Mig 053: `workflow_step_documents` linking each workflow step to required_document_types — meaning **data upload can be workflow-step-aware**.

The infrastructure now supports reversing the onboarding order: **build the org tree first → design workflows for the smallest dept → upload data into the workflow step that needs it**. Upload becomes a consequence of a step needing a document, not a free-form action.

Tension:
- **Pro reverse:** Vingroup-class clients onboard faster — they already have a mental model of org tree + workflows; data upload is the LAST step where Kaori meets their existing systems.
- **Pro reverse:** Workflow-aware upload guarantees data lands in the right Silver table for the step that needs it (Stage 4 quality whitelist checked, no orphan data).
- **Con reverse:** Cold-start "no data yet" delays seeing Bronze/Silver pipeline working — CSM loses the dramatic "first insight by D7" demo moment.
- **Con reverse:** Discovery questionnaire (Phần 1.2) must capture more org tree detail BEFORE D1, which front-loads sales effort.

Anh's directive 2026-05-17: "thay vì upload data ta sẽ xây sơ đồ phả hệ - sơ đồ tổ chức mức độ tập đoàn trước, sau khi xây xong đến phòng ban bộ phận nhỏ nhất như vin đã xây, sau đó tạo các workflow cho các phòng ban từ nhỏ nhất, rồi upload data theo các workflow đó".

## Decision

We re-sequence PLAYBOOK_90DAY.md §2 Week 1 (D1-D7) Foundation phase from `workspace → flat departments → upload → validate` to `workspace → corporate hierarchy → smallest dept → workflow design → workflow-driven upload`:

```
D1    Workspace creation + first login (unchanged)
D2    Corporate hierarchy setup (group → divisions → subsidiaries → enterprise root)
D3    Drill down — departments + sub-departments per smallest enterprise unit
D4-5  Workflow design for ONE smallest department first (template-driven, mig 069 catalog)
D6    Workflow-step-aware data upload — each step's required_document_types triggers an upload prompt
D7    Validate Bronze + Silver landed correctly per workflow step + quality scorecard
```

Implications on the rest of the playbook:
- §1.2 Discovery Questionnaire (D-7) expanded to capture corporate tree depth + most-painful smallest dept (the wedge candidate).
- §2.2 rewritten — "Department setup flow" becomes "Corporate hierarchy + smallest-dept setup flow" using mig 055-057 `corporate_tree` endpoints.
- §2.3 rewritten — "First Data Upload" becomes "Workflow design for smallest dept" using mig 069 production templates filtered by `industry_vertical` (newly added P2-S15).
- §2.4 rewritten — "Bronze validation" becomes "Workflow-driven upload + per-step Bronze landing".
- §3.1 Silver Layer lead-in adjusted: silver builds happen per-workflow-step rather than per-department file dump.
- The 5 Customer Archetypes (§0.4): "Simple SME" archetype keeps a simplified flat path; org-tree-first only kicks in for Mid-Enterprise + Conglomerate archetypes.

We keep §2.4's quality scorecard gate — it just runs per workflow step instead of per file.

## Consequences

### Positive

- Vingroup-class clients ("Tập đoàn" archetype) onboard naturally: their org tree is the conversation opener, not an afterthought.
- Workflow-driven upload eliminates orphan data — every uploaded file is tied to a workflow step that needs it (Stage 4 quality whitelist already enforces this since mig 065).
- Smaller cognitive load on customer in D4-5: pick ONE smallest dept, pick ONE workflow template, configure it. The 25-template catalog (mig 069) does the heavy lifting.
- 90-day Loop (Stage 12) starts earlier — workflow runs from D6 onwards generate decision_audit_log rows → T-Cube distillation (ADR-0021) gets producer signal from week 1.

### Negative / accepted trade-offs

- "Simple SME" archetype (no real hierarchy) gets a slightly heavier D2 step — they must skip past the corporate tree screen with a "single-enterprise flat mode" toggle.
- CSM team retraining: handover docs + scripts updated to reflect new order. Estimate ~2 days of CSM team alignment.
- Sales Discovery effort shifts left — AE now responsible for capturing org tree depth in the questionnaire, not the CSM at D2.
- M3 gate (end of D5) changes meaning: was "≥1 file uploaded successfully"; now becomes "≥1 workflow designed for smallest dept". Quality dashboard tile names update.

### Neutral / follow-ups

- Monitor: archetype-tagged metric "time-to-first-workflow" — target ≤ 5 days. If "Simple SME" hits ≤ 2 days but "Conglomerate" hits ≤ 7 days, the new order is healthier than the old "≥1 file uploaded by D5" gate.
- Reconsider trigger: if 30+ Conglomerate-archetype clients onboard and median time-to-first-data > 14 days, revert M3 gate to original "upload first" sequence for that archetype.
- Sales playbook update (out-of-scope for this ADR): adjust discovery script + onboarding kit slides.

## Alternatives considered

- **Alt 1: Keep upload-first; add a corporate-hierarchy wizard as an OPTIONAL D8-14 step.** Rejected — Vingroup-class clients already model their org tree externally; deferring it to D8-14 forces them to upload first under an artificial flat structure, then re-map data. Sunk cost.
- **Alt 2: Make corporate hierarchy required for all archetypes.** Rejected — "Simple SME" with 1 office + 5 employees gets a UX penalty. Conditional flow per archetype is the right balance.
- **Alt 3: Workflow-first, hierarchy-second.** Rejected — workflows naturally belong to a department; without org tree, the workflow has no parent. The dependency order is hierarchy → dept → workflow → data.

## References

- `docs/strategic/PLAYBOOK_90DAY.md` §2 (updated in same commit)
- `infrastructure/postgres/migrations/055_corporate_groups.sql` + 056 + 057 (Vingroup demo)
- `infrastructure/postgres/migrations/068_node_type_catalog.sql` (45 node types)
- `infrastructure/postgres/migrations/069_production_templates_seed.sql` (25 templates × industry_vertical)
- `services/ai-orchestrator/routers/corporate_tree.py` (10 endpoints — group/division/enterprise CRUD)
- `services/ai-orchestrator/routers/workflow_builder.py` (13 + 1 endpoints — workflow + node-types catalog)
- `feedback_rbac_a_b_decision` memory (RBAC roadmap that influenced legal review timing)
