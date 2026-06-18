# Kaori AI — UAT Manifest

> Navigation manifest for `docs/uat/`. Grouped by area so you can find the right UAT script fast.
>
> **Total: 134 UAT docs** — 36 feature/flow scripts at top level + `screens/` (2 helpers + 21 Platform `p1/` + 75 Enterprise `p2/`).

The top-level docs are **feature- and flow-oriented** (one script per F-ID feature or cross-cutting flow). The `screens/` subtree is **per-screen** UAT (one script per UI screen, P1 Platform + P2 Enterprise).

---

## Top-level feature scripts (by area)

| Area | File(s) |
|---|---|
| **Decision intelligence (F-033..F-041, F-060)** | `F-033-multi-tier.md` · `F-034-frameworks.md` · `F-035-cohort.md` · `F-036-decision-override.md` · `F-037-alerts.md` · `F-038-reports.md` · `F-039-risks.md` · `F-041-explainability.md` · `F-060-north-star.md` |
| **Agent / chat** | `F-061-agent-insight-to-action.md` · `CHAT_PANEL.md` |
| **Workspace & identity** | `F-008-workspace.md` |
| **AI governance & audit** | `F-AI-DECISION-AUDIT.md` · `F-POLICY-ENGINE.md` · `F-QUOTA-429.md` · `K_RULE_INVARIANTS.md` |
| **Document / pipeline nodes (Phase 2.5)** | `F-CLASSIFY.md` · `F-EXTRACT.md` · `F-SUMMARISE.md` · `F-SENTIMENT.md` · `F-DEDUP.md` · `F-COMPARE.md` · `F-MINERU.md` |
| **Data plane & lineage** | `F-LINEAGE-WALK.md` · `F-ONTOLOGY-GOV.md` |
| **Workflow execution & reliability** | `F-WORKFLOW-EVENTS.md` · `F-WORKFLOW-EXEC-CLOSEOUT.md` · `F-IDEMPOTENCY-LEDGER.md` · `F-DLQ-CONSOLE.md` |
| **Security (P2-S25 MFA + field encryption)** | `P2-S25-mfa-field-encryption.md` · `P2-S25-session-marathon-overview.md` |
| **Cross-cutting flows & sweeps** | `CROSS_PORTAL_FLOW.md` · `HAPPY_PATH_SWEEP.md` · `PERFORMANCE_NFR.md` |
| **Pilot & sprint closeouts** | `PILOT_ROUND_2.md` · `SPRINT_2_1_CLOSEOUT.md` |

## Per-screen scripts — `screens/`

| Area | Location | Count |
|---|---|---|
| Setup + how-to | `screens/_README.md` · `screens/_SETUP.md` | 2 |
| **P1 Platform** (login/MFA, dashboard, workspaces, admins, billing, security) | `screens/p1/UAT-PL-001..021-*.md` | 21 |
| **P2 Enterprise** (dashboard, data explorer Bronze/Silver/Gold, pipelines wizard, insights, charts, decisions, users, analysis, frameworks, reports, strategy, risks, alerts, workflows, auto-db, authz, org-tree, branding, subscription, settings) | `screens/p2/UAT-EN-001..075-*.md` | 75 |

### P2 Enterprise screen ranges (quick jump)

| Range | Topic |
|---|---|
| EN-001..006 | Dashboard + Data explorer (Bronze/Silver/Gold) |
| EN-007..013 | Pipelines wizard (list → upload → columns → clean → analyze → results) |
| EN-014..019 | Insights + Knowledge base + Charts |
| EN-020..025 | Decisions log + Users |
| EN-026..032 | Customers-at-risk + Analysis hub (basic/intermediate/advance) |
| EN-033..039 | Frameworks (SWOT/6W/2H/Fishbone/MoM-YoY/custom) |
| EN-040..044 | Reports (auto/builder/template/distribution) |
| EN-045..053 | Strategy + Risks + Alerts |
| EN-054..060 | Workflows (list/hub/new/detail/test) + Departments |
| EN-061..064 | Auto-DB (schema/form/quality) |
| EN-065..069 | Authz (RBAC/custom-role/ABAC/simulate/audits) |
| EN-070..075 | Org-tree + Branding + Subscription + Settings |

---

> UAT acceptance criteria at the BA level live in `docs/ba/3.6_UAT_Test_Cases_and_Acceptance_Criteria.md`. Invariant-level checks: `K_RULE_INVARIANTS.md` (mirrors `CLAUDE.md` §4 / `docs/K_RULES_INDEX.md`).
