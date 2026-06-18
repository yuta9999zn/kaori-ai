# UAT — F-035 Cohort Retention

> **Function:** F-035 — Cohort Retention. Engine + chart đã ship từ Phase 1 inside the wizard analytics path. F-033 PR C surfaces the same template through the multi-tier basic surface; this UAT covers both paths.
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role can run via either path.
> **Service:** ai-orchestrator analytics engine (`StatisticalEngine._cohort`)
> **DB:** writes a row to `analysis_results` per run (per-template), reads `silver_rows` of the chosen pipeline.
> **Owner:** anh (test) + em (standby fix)
> **Prepared:** 2026-05-04

---

## 0. What ships

| Component | Where | Notes |
|---|---|---|
| Template registry | `services/ai-orchestrator/analytics/template_registry.py` | `cohort` template — requires `date` type + `customer_master`/`transaction_list` purpose, min 100 rows |
| Engine | `services/ai-orchestrator/analytics/engines/statistical.py:_cohort` | pandas pivot — cohort_month × period_num matrix; 8 unit tests |
| Chart renderer | `frontend/components/charts/chart-registry.tsx:RHeatmap` | `scatter_2d` shape + `heatmap` chart kind; reads `meta.x_axis`/`y_axis`/`value` |
| Multi-tier surface | `/p2/analysis/basic` (template list) | F-033 PR C surfaced via the basic-tier picker; pick `Cohort Retention` template + run |
| Wizard surface | `/p2/pipelines/{id}/step-4-analyze` | Phase-1 path — choose multiple templates including `cohort` |
| Result page | `/p2/analysis/runs/[id]` (multi-tier) or `/p2/pipelines/{id}/step-5-results` (wizard) | Both render the heatmap + summary card via the same chart-registry component |

Engine output (per call) — 2 ChartBlocks:

```json
[
  {
    "id": "cohort_heatmap",
    "type": "chart",
    "data_shape": "scatter_2d",
    "default_chart": "heatmap",
    "data": [
      { "cohort": "2026-01", "period": 0, "retention": 1.0  },
      { "cohort": "2026-01", "period": 1, "retention": 0.62 },
      ...
    ],
    "meta": { "x_axis": "period", "y_axis": "cohort", "value": "retention" }
  },
  {
    "id": "cohort_summary",
    "type": "stats_card",
    "data": { "cohorts_analysed": 4, "avg_month1_retention": 0.69 }
  }
]
```

---

## 1. Pre-flight checks

| # | Check | Expected |
|---|---|---|
| A1 | Engine registered: `python -m pytest services/ai-orchestrator/tests/test_engines.py -k cohort -v` | 8 passed |
| A2 | Template appears in registry: `grep -A 5 'template_id="cohort"' services/ai-orchestrator/analytics/template_registry.py` | shows the AnalysisTemplate row |
| A3 | Pilot tenant has a pipeline with ≥ 1 silver dataset that has `customer_id` + a date column AND ≥ 100 rows | required for the engine to actually compute retention |
| A4 | If A3 fails | The engine returns a `ValueError` ("Cần cột customer_id và date") — UAT validates the friendly error path instead |

---

## 2. Test scenarios

### SCN-1 — Multi-tier basic path

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open `/p2/analysis/basic` | Pipeline picker + multi-select template list including **"Cohort Retention"** |
| 2 | Pick a pipeline that has customer + date columns | Form ready |
| 3 | Tick **"Cohort Retention"** template; optionally add `summary_stats` for context | Run button enables |
| 4 | Submit → redirect to `/p2/analysis/runs/{id}` | 202 + result page mounted |
| 5 | Wait 10–30s (real BE) or ~3s (MSW dev) | Status `queued → running → done` via 2s poll |
| 6 | Detail page renders | 2 blocks visible: **heatmap** (rows = cohort tháng, cols = M0/M1/M2/...) + **stats card** with `cohorts_analysed` + `avg_month1_retention` |
| 7 | Hover heatmap cells | Numeric retention shown; period 0 always = 100% (anchor) |

### SCN-2 — Phase-1 wizard path (legacy, still works)

| Step | Action | Expected |
|------|--------|----------|
| 1 | `/p2/pipelines` → click an existing pipeline → step-4 | Template multi-select |
| 2 | Tick `Cohort Retention` | Eligibility check passes only if pipeline detected `customer_master`/`transaction_list` purpose |
| 3 | Submit → step-5 results | `analysis_results` row written with the 2 ChartBlocks; FE renders heatmap |

### SCN-3 — Engine validation paths

| Step | Action | Expected |
|------|--------|----------|
| 1 | Pipeline missing customer column (only date) | Engine raises `ValueError("Cần cột customer_id và date cho Cohort.")`; result page shows "Phân tích thất bại" with the error |
| 2 | Pipeline missing date column | Same `ValueError` |
| 3 | Pipeline with < 100 rows | Eligibility check skips the template upstream — won't appear in the picker for that pipeline |
| 4 | Period 0 in output | Always 1.0 across all cohorts (definitional) — covered by `test_retention_period_0_always_1` |

### SCN-4 — Heatmap rendering correctness

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open a completed cohort run | Heatmap row labels = cohort months (e.g. "2026-01", "2026-02") |
| 2 | Column labels | "M0", "M1", "M2", … in ascending order |
| 3 | Cell colors | Heatmap gradient `#C24747` (low) → `#477FC2` (high); 100% retention = bluest |
| 4 | Triangular shape | Younger cohorts have fewer columns (data not yet collected for future months) — should render correctly without empty-cell artefacts |

### SCN-5 — Audit trail

| Step | Action | Expected |
|------|--------|----------|
| 1 | After completed run, query `decision_audit_log WHERE decision_type LIKE 'analysis%' ORDER BY created_at DESC LIMIT 5` | Row(s) tagged with `method='statistical'` (basic path) — the engine itself is statistical, not LLM |
| 2 | Cross-tenant `GET /api/v1/analysis/runs/{other tenant id}` | 404 — RLS scoped on `analysis_runs` |

---

## 3. Known gaps (intentional)

- **No dedicated `/p2/analysis/cohort` quick-launch page** — F-035 is reachable via the basic tier picker. Adding a single-template page would duplicate the basic-tier form for marginal UX gain. Reconsider if pilot users repeatedly ask for it.
- **Heatmap legend** — RHeatmap renders the gradient but no explicit legend strip. Add when multiple users have run cohort + asked what the colors mean.
- **Cohort export** — no CSV export specifically for the cohort matrix today. Users can copy from the heatmap or fall back to F-038 reports for a structured roll-up.

---

## 4. Rollback

F-035 is template-only. Disable by removing the registry entry:

```py
# Comment out in services/ai-orchestrator/analytics/template_registry.py
# AnalysisTemplate(template_id="cohort", ...)
```

The engine method `_cohort` stays harmless — it's never called without the template entry. Restart ai-orchestrator picks up the change.

---

*Last updated: 2026-05-04 — F-035 surfaced via F-033 PR C basic-tier picker; engine + chart shipped Phase 1.*
