# Road to "9 across the board" — Kaori Execution Roadmap

> **Status:** approved roadmap (anh, 2026-06-04). Master plan; each slice gets its own spec → plan → subagent build → PR.
> **Baseline (review 2026-06-04):** BE ~9 · FE ~5 · docs ~7.7. Biggest lever = **FE** (wire BE features that already exist into usable UI).

## Goal & "score 9" definitions

- **FE = 9:** core customer flows + moat features are **LIVE** (real API, full empty/loading/error states), i18n-ready (shared hooks layer + VN/EN catalog), coherent capability-based nav, no "mockup that looks live" left on primary flows; process-mining / NOV-ROI / adoption / EU AI Act compliance all have UI.
- **Docs = 9:** no stale refs; complete indices (ADR 0010–0041, `ba/`, `uat/`, `audit/`); BA folder cleaned of junk; K-rules index; PROJECT_STATUS consolidated.
- **BE = 9 (hold):** already there; only add K-25 model card when the compliance-UI slice lands.

## Confirmed decisions (anh, 2026-06-04)

1. **Thin-foundation-first** — build a minimal FE foundation (`lib/hooks/*` per-domain query hooks + i18n provider + VN/EN `messages.ts` split + a codified reference pattern) BEFORE wiring screens. NOT a big restructure (YAGNI) — just enough to stop copy-paste + avoid rework when English lands.
2. **Portal scope:** drive **P2 Enterprise + P1 Platform-core to 9**; **P3 Studio / P4 Personal / P5 Shared / P6 Billing = "frame only" (no-404 landing + must-haves), build out later.** Right focus for the pilot.

## Execution principle

Each slice runs the full superpowers loop: spec → `writing-plans` → `subagent-driven-development` (TDD; FE slices gate on `cd frontend && npm run build` typecheck + the existing dashboard test pattern; BE slices gate on pytest) → commit → PR (anh merges manually). Browser-verify is anh's step (or the `run` skill) where visual confirmation matters. Slices are mostly independent → separate branches/PRs; run continuously.

## Slice sequence

| # | Slice | Scope | Gate / done-when |
|---|---|---|---|
| **S0a** | **Docs quick-wins** | ADR `README` index 0010–0041; `docs/ba/README.md`, `docs/uat/README.md`, `docs/audit/README.md`; `docs/K_RULES_INDEX.md`; fix stale refs (CLAUDE.md mig phrasing, docs/README date); clean `D:\Tài liệu dự án` (move `.mp4`/`.png`/`.zip` out, archive old PROJECT_STATUS, add BA-folder index); write `PROJECT_STATUS_2026-06-04`. | docs review ≥9; indices exist; no junk in BA folder |
| **S0b** | **FE thin foundation** | `frontend/lib/hooks/` per-domain query hooks (wrap TanStack Query + `api<T>()`); i18n provider + `lib/i18n/messages.ts` VN/EN split + `useT()`; codify the `/p2/dashboard/overview` pattern as the reference; (light) capability-flag nav helper. | `npm run build` green; 1 screen refactored onto hooks as proof |
| **S1** | **Pipeline wizard Step 2–5** | Wire `/p2/pipelines/[id]/step-2-columns … step-5-results` to real BE (schema confirm → clean → analyze → results) using S0b hooks. | each step calls real endpoints; states complete; build green |
| **S2** | **Insights + Analysis** | Wire insights list/detail + analysis hub/runs to BE. | live; build green |
| **S3** | **Moat dashboards** | NOV/ROI dashboard + Adoption-intelligence UI (the selling points, currently invisible). | live; build green |
| **S4** | **Process Mining UI (P2-28)** | Scaffold `/p2/process-mining` route + wire to `routers/process_mining.py` (discovery + findings). | live; build green |
| **S5** | **EU AI Act UI + K-25** | risk-classify wizard (`/compliance/ai-uses`) + approval-inbox (K-23 oversight) + incident console (K-26); **K-25 model card** BE (mig + registry + UI read). | compliance visible/usable; K-25 enforced |
| **S6** | **Tier-3 finish** | Workflow Testing (P2-27) + Contracts e-sign UI + Approval Chains UI. | live; build green |
| **S7** | **i18n English (S23)** | Complete EN catalog on the S0b foundation; language toggle. | VN+EN switchable |
| **S8** | **Portal frames** | P3/P4/P5/P6 no-404 landing + must-haves; P1 platform-core gaps to 9. | no 404; P1 core ≥9 |

## Out of scope (this roadmap)

Phase-3 deferred items (multi-region, marketplace, 39 advanced analysis types, MCP ecosystem, ClickHouse/Temporal/K8s cutover) — those are Year-2. Full build-out of P3/P4/P5/P6 beyond frames. Full-conformity EU AI Act (Annex IV/CE) — only when entering EU.

## Risk / notes

- FE verification without a browser relies on `npm run build` typecheck + the dashboard test pattern; visual/UX confirmation is anh's loop (or `run` skill). Flag any slice that genuinely needs runtime data.
- Some BE endpoints may be missing/partial for a screen — each FE slice's plan first confirms the BE contract (read the router) before wiring; if a gap is found, that becomes a small BE sub-task in the slice.
- Keep the established conventions: FE canonical JWT key `kaori.access_token`; route components are `fnew*`/wired not numbered mockups; refresh drift artefacts when endpoints change; VND formatting; Vietnamese register.
