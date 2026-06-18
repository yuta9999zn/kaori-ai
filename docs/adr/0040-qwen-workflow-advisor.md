# ADR-0040 — Qwen Workflow Advisor (đánh giá workflow: "bước nào ok / cần cải tiến")

> **Status:** accepted (building) — 2026-06-01
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0033 (CDFL |OR| coverage gate — no-hallucination) · ADR-0037 (doc requirements) · mig 094 (`workflow_events`) · mig 127 (approval gate binding) · `routers/workflow_builder.py` (`_check_dangling_branches` / `_check_approval_gates` / `dry_run_workflow`) · `reasoning/kpi_engine/` (sibling pattern) · K-3/K-6/K-21

## Context

UAT + external review surfaced a genuinely missing capability (reviewer scored it ~10%): the platform builds workflows but never **evaluates the workflow itself** — "các bước có ok / cần cải tiến không". The existing AI engines analyse *customer data* (`kpi_engine`, `insight_engine`); none analyses *the process model*. The bugs anh found by hand (6 empty steps on the default branch, a step wired to the wrong branch, required docs with no submit path) are exactly what an advisor should catch automatically.

The substrate already exists: static structure in `workflow_nodes`/`workflow_edges`/`workflow_step_document_requirements`; runtime history in **`workflow_events`** (mig 094 — `node_started`/`node_completed`/`node_failed` + `occurred_at` + `sequence_no`), and reusable static checks (`_check_dangling_branches`, `_check_approval_gates`, `dry_run_workflow`).

## Decision

Add engine **`reasoning/workflow_advisor/`** (sibling to `kpi_engine`) + table `workflow_review` (mig 130) + router endpoints + an FE card. Two evaluation modes:

- **static** — runs even with zero executions; reads the workflow structure.
- **runtime** — augments with `workflow_events` aggregates (visit counts, durations, failures, never-reached nodes).

**Rule-first, LLM-second (engineering tenet #1 + K-3 anti-hallucination).** The findings are produced by **deterministic detectors**, not by the LLM — so the advisor never invents a problem. Qwen is used only for a GROUNDED executive narrative over the already-computed findings (and never introduces a node_id the rules didn't flag). If Qwen is unavailable, findings still persist (fail-open narrative). This mirrors the CDFL |OR| coverage-gate stance (ADR-0033): generate only from grounded facts, else decline.

### Finding schema (fixed categories so we can aggregate)
`category ∈ {incomplete, branch_error, dead_branch, bottleneck, missing_doc, no_action_on_path, redundant, compliance}` · `severity ∈ {high, medium, low}` · `confidence 0–1` · `step_id` · `title` · `detail` · `suggestion`. Plus `overall_health 0–1` (1 − severity-weighted finding load, clamped).

| Detector | Mode | Category | Reuse |
|---|---|---|---|
| node has no action/executor (`step`, no `node_type_catalog_key`, not start/end) | static | incomplete | — |
| decision/switch/parallel with too few outgoing edges | static | branch_error | `_check_dangling_branches` |
| approval_gate with no chain/role | static | compliance | `_check_approval_gates` |
| required doc requirement with no `is_current` doc | static | missing_doc | doc-tree query |
| consecutive nodes with same action | static | redundant | — |
| node never reached across ≥N runs | runtime | dead_branch | `workflow_events` |
| node visited but has no action | runtime | no_action_on_path | events + structure |
| node avg duration / failure-rate outlier | runtime | bottleneck | `workflow_events` |

### Data model — `workflow_review` (mig 130, K-21 + RLS)
`review_id UUID PK DEFAULT gen_uuid_v7()` (K-21) · `enterprise_id UUID NOT NULL` (RLS K-1, mirror tenant isolation) · `workflow_id UUID NOT NULL` · `run_mode TEXT` (static/runtime) · `model TEXT` (e.g. `qwen2.5-local` or `rules-only`) · `overall_health NUMERIC(4,3)` · `findings JSONB NOT NULL` · `created_at TIMESTAMPTZ DEFAULT NOW()`. Index `(enterprise_id, workflow_id, created_at DESC)`. Append-only history (re-run = new row).

### API (under the already-routed `/api/v1/workflows/**`)
- `POST /workflows/{id}/advisor/run` → 202; runs the advisor in a BackgroundTask (LLM off the request path — [[feedback_llm_in_request_path_bound]]); writes a `workflow_review` row + a `decision_audit_log` entry (K-6).
- `GET /workflows/{id}/advisor` → latest review (overall_health + findings) or `{status: "never_run"}`.

No gateway change — `/api/v1/workflows/**` already lands on ai-orchestrator (corporate-tree route group).

### Frontend
Card **"Đánh giá workflow (Qwen)"** in the workflow report/detail tab next to the KPI engine slot: `overall_health` gauge, findings grouped by severity (đỏ/vàng/xanh), each with "Đi tới bước" → the node in the builder. Empty state "Chưa phân tích — bấm Đánh giá". Label it AI advice w/ confidence, not a verdict.

## Consequences
- **+** Auto-catches the design bugs anh found by hand; works pre-run (static); grounded (no hallucinated findings); reuses existing checks + events; additive (new table/engine/endpoints, nothing touched).
- **−** Runtime detectors need real run history to be useful (degrade gracefully to static). Bottleneck thresholds are heuristic (env-tunable `KAORI_ADVISOR_*`, no hardcode).
- **Open**: RAG-vs-industry comparison (reviewer item) is a *separate* follow-up (knowledge_documents/CDFL) — out of scope here.

## Alternatives considered
- **LLM-generates-findings** — rejected: hallucination risk (invents steps/issues); violates K-3 spirit + ADR-0033. Rules find, LLM narrates.
- **Fold into kpi_engine** — rejected: kpi_engine analyses customer data rows; this analyses the process graph — different input, different table.
