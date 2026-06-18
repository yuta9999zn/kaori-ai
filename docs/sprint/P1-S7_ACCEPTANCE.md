# Sprint P1-S7 — Acceptance Mapping

> **Sprint goal:** "Process Mining v1 + Adoption + NOV basic"
> **Status:** ✅ 3 NEW org_intel modules shipped (process_mining, adoption, economics) — contract surface + 1 baseline impl per module + 47 unit tests
> **Branch:** `feat/v4-p1-s7` (parent: `feat/v4-p1-s6`)
> **Date:** 2026-05-08

This is the **biggest sprint Phase 1** (48 features). It materialises the v4 moat: the three L4.5 modules that differentiate Kaori from generic ETL+BI tools. Realistic Phase 1 scope = contract surface + 1 baseline impl per module; full algorithms + cron + endpoints land Phase 1.5 P15-S9 + P2-S13/S14 alongside the FPT Cloud K8s deploy and full 8 PM sources.

What ships isn't a working CSM dashboard yet — it's the data structures + algorithms the dashboard will consume. Same shape as P1-S6 (workflow contract before Temporal worker): get the contract right, ship the runtime later.

---

## Net new work shipped this sprint

### Process Mining (PM-* features)

| Feature code | Description | Implementation |
|---|---|---|
| **PM-PII-009 ⭐** | Common event log schema normalization | `org_intel/process_mining/types.py` — Event + EventLog + ProcessVariant frozen dataclasses. Mirrors ingestion.NormalizedEvent shape (data-pipeline writes Bronze; Process Mining reads back). |
| **PM-PII-012 ⭐** | Tenant_id stamping on every event | EventLog `__post_init__` rejects events with `tenant_id` ≠ EventLog scope; raises `PM-PII-012` ValueError. Tenant isolation enforced at the data structure layer (defense in depth on top of K-1 RLS). |
| **PM-ALG-014 ⭐** | Case inference (group events by case_id) | `org_intel/process_mining/case_inference.py:infer_cases` — explicit case_id wins, fallback to `actor:<id>`, last resort `unknown:<source>` so data quality issues stay visible. Sorts each case chronologically for downstream miners. |
| **PM-ALG-015 ⭐** | Heuristic Miner algorithm (Phase 1) | `org_intel/process_mining/heuristic_miner.py:HeuristicMiner` — bigram counter on direct-follow relations, frequency threshold filter, average duration per edge (PM-ALG-019 inline). Output: `MinedWorkflow` with direct_follows, event_counts, avg_durations, case_count. |
| **PM-ALG-019 ⭐** | Temporal pattern (avg duration per step) | Inline in HeuristicMiner — `avg_durations[(from, to)] = mean(elapsed_seconds)`. |

### Adoption Intelligence (AI-* features)

| Feature code | Description | Implementation |
|---|---|---|
| **AI-SIG-001 ⭐** | Workflow execution abandonment | `signals.py:AI_SIG_001_workflow_abandonment(starts, completions)` — score = completions/starts. |
| **AI-SIG-002 ⭐** | AI decision override rate tracking | `AI_SIG_002_ai_decision_override_rate(decisions, overrides)` — score = 1 - override_rate. |
| **AI-SIG-003 ⭐** | Side-channel detection (Vietnam-critical) | `AI_SIG_003_side_channel_detection(in_workflow, side_channel)` — score = in_workflow / total. Detects Zalo/Excel use post-deploy. |
| **AI-SIG-005 ⭐** | Manager intervention frequency | `AI_SIG_005_manager_intervention_frequency(completions, manager_interventions)`. |
| **AI-SIG-006 ⭐** | Workflow completion rate per user/dept | `AI_SIG_006_workflow_completion_rate(target, actual)` — capped at 1.0 to prevent inflation. |
| **AI-HSC-010..015 ⭐** | Composite health score + classification + trend | `health_score.py:compute_composite_score()` averages signals × 100, `classify_health()` buckets to EXCELLENT/HEALTHY/AT_RISK/STRUGGLING, `detect_trend()` linear-regression-based improving/declining/stable. |

### Economics / NOV (NOV-* features)

| Feature code | Description | Implementation |
|---|---|---|
| **NOV-REV-001 ⭐** | Pre/Post comparison method | `economics/revenue.py:estimate_revenue_pre_post` — Δrevenue (30d before vs after). Confidence 0.7. Negative delta returns 0 (don't claim losses as gains). |
| **NOV-REV-003 ⭐** | Industry benchmark fallback | `estimate_revenue_industry_benchmark` — INDUSTRY_BENCHMARKS dict per industry uplift rate. Confidence 0.4 (we're guessing). |
| **NOV-REV-004 ⭐** | KPI-to-revenue mapper (per industry) | `INDUSTRY_BENCHMARKS` dict — RETAIL/F&B/FMCG/FINANCE/LOGISTICS/EDUCATION/HEALTHCARE/MANUFACTURING/REAL_ESTATE/ECOMMERCE/BEAUTY/FASHION. |
| **NOV-REV-005 ⭐** | Confidence scoring on revenue estimates | `RevenueEstimate.confidence: Decimal` (NUMERIC(5,4)) returned from both methods. |
| **NOV-CST-007 ⭐** | People cost (time × rate) | `cost.py:estimate_people_cost`. |
| **NOV-CST-008 ⭐** | Infrastructure cost calculator | `estimate_infrastructure_cost(compute_hours, storage_gb_month)`. |
| **NOV-CST-009 ⭐** | AI call cost (token-based) | `estimate_ai_token_cost` — per-1k pricing. Phase 1.5+ swaps OBS-008 char-proxy → real tokens. |
| **NOV-CST-010 ⭐** | Integration cost (3rd-party API) | `estimate_integration_cost(api_calls, cost_per_call)`. |
| **NOV-CORE-013 ⭐** | NOV monthly computation | `nov.py:compute_monthly_nov(revenue, cost) → NOVResult`. |
| **NOV-CORE-014 ⭐** | Time-to-payback projection | `time_to_payback_months(upfront_cost, monthly_savings)`. Round up; None when savings ≤ 0. |
| **NOV-CORE-016 ⭐** | Negative NOV alerts | `NOVResult.is_negative()` helper for caller's escalation logic. |

---

## 47 new unit tests (`tests/test_org_intel.py`)

Bundled in one file Phase 1 (split into 3 files when each section grows past ~15 tests):

  * **Process Mining (8):** EventLog tenant rejection (PM-PII-012), case inference paths (explicit/actor/unknown), chronological sorting, Heuristic Miner direct-follow + durations, frequency threshold dropping, min_frequency validation.
  * **Adoption (16):** SignalSample range validation, all 5 signals (zero-input neutral, partial-rate scoring, override-rate inverse, side-channel inverse, intervention inverse, target-cap), composite score averaging, empty-input default, classification boundaries (parametrized), trend detection (improving/declining/stable/empty).
  * **Economics (23):** pre/post positive/negative/zero-baseline, industry benchmark known/normalised/unknown, INDUSTRY_BENCHMARKS uppercase invariant, people cost negative-hours-zero, AI token per-1k pricing, integration zero-calls-zero, monthly NOV positive/negative + is_negative() alert helper, time-to-payback normal/partial-month-rounds-up/zero-savings-None.

---

## 4 Platform features mapped (existing)

| Feature | Existing impl | Note |
|---|---|---|
| `P1-BIL-001` Tổng quan billing theo tháng (MRR + breakdown) | F-031 BillingMath + `enterprise_monthly_billing` | Existing |
| `P1-BIL-002` Alert khi enterprise >80% quota | F-037 BillingAlertService quota dispatcher | Existing — already shipped Phase 1 v3 |
| `P1-BIL-003` Tính overage cost tự động | F-031 BillingAggregationService overage calc | Existing |
| `P1-PILOT-001` Pipeline view (Prospect → Pilot → ENT) | F-015 platform admin enterprise listing | Existing |
| `P1-PILOT-002` Auto-trigger D25/D30 prompt | F-013 onboarding pilot countdown | Existing |
| `P1-CSM-001 ⭐` Customer health overview | NEW endpoint stub deferred to Sprint P1-S8 (uses adoption.compute_composite_score + economics.compute_monthly_nov this sprint shipped) | Contract ready |

---

## Quick-run smoke command

```bash
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q       # 507 pass (+47 new)
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q          # 367 pass + 1 skip
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q            # 96 pass
cd "D:\Kaori System\services\notification-service" && python -m pytest -q   # 17 pass
```

**Total: 987 Python pass** (was 940 after P1-S6, +47 from org_intel tests).

---

## Files touched this sprint (P1-S7)

```
services/ai-orchestrator/
  org_intel/__init__.py                            NEW (package marker)
  org_intel/process_mining/
    __init__.py                                    NEW (re-exports)
    types.py                                       NEW (Event, EventLog, ProcessVariant)
    case_inference.py                              NEW (PM-ALG-014)
    heuristic_miner.py                             NEW (PM-ALG-015 + 019)
  org_intel/adoption/
    __init__.py                                    NEW (re-exports)
    signals.py                                     NEW (AI-SIG-001/002/003/005/006)
    health_score.py                                NEW (AI-HSC-010..015)
  org_intel/economics/
    __init__.py                                    NEW (re-exports)
    revenue.py                                     NEW (NOV-REV-001/003/004/005)
    cost.py                                        NEW (NOV-CST-007/008/009/010)
    nov.py                                         NEW (NOV-CORE-013/014/016)
  tests/test_org_intel.py                          NEW (47 tests — 8 PM + 16 adoption + 23 NOV)

docs/sprint/P1-S7_ACCEPTANCE.md                    NEW (this file)
```

13 NEW Python files + 1 acceptance doc. **Largest functional sprint** by feature count (40+ ⭐ features) but smallest by infrastructure footprint — pure contract surface in one repo subtree.

---

## What this sprint did NOT do (deferred / not in scope)

- **Real connector implementations** (PM-EVT-001/002/003 Postgres CDC + Excel + Zalo) — connectors live in services/data-pipeline/ingestion/connectors/ (skeleton P1-S3); full Phase 1.5+ when Vault credentials + Bronze MinIO ready.
- **PII detection (Vietnamese-aware)** PM-PII-010/011 — services/data-pipeline/ingestion/pii.py is stub from P1-S3; full impl P1.5 alongside connector real impl.
- **PM-ALG-018 Variant analysis + PM-ANM-021 Bottleneck detection** — Heuristic Miner's `direct_follows + avg_durations` already enable these; ship dedicated function calls when first dashboard needs them (probably P1-S8 polish).
- **AI-INT-018 CSM alert generation** — adoption health score classification ready; CSM endpoint + Slack/PagerDuty wire P15-S9.
- **NOV-RPT-019 Manager email digest + NOV-RPT-021 ROI Dashboard** — engine ready; FE pieces frontend-paused; backend cron P15-S9.
- **OBS-010 nov_per_workflow + OBS-011 adoption_score_per_workflow** Prometheus gauges — register in P15-S9 alongside the OBS-009 quota gauge.
- **adoption_signals + nov_records DB tables** — pure compute Phase 1 (caller persists results); migrations P15-S9 when CSM dashboard reads them.
- **drift Olist 12 file** — still stashed.

---

## Phase B-2 progress after Sprint P1-S7

```
services/ai-orchestrator/
├── reasoning/                           ← P1-S5 ✅
├── workflow_runtime/                    ← P1-S6 ✅
├── org_intel/                           ← P1-S7 ✅ (this sprint)
│   ├── process_mining/                  ← types + case_inference + heuristic_miner
│   ├── adoption/                        ← signals + health_score
│   └── economics/                       ← revenue + cost + nov
├── chat/                                ← stays (CHAT_TOOL_REGISTRY_V4 plan)
└── (frameworks/, explainability/, multi_tier/, reports/, agents/ — stay)
```

Phase B-2 for `services/ai-orchestrator/` substantially complete for the v4-required modules. Remaining (frameworks, explainability, multi_tier, reports, agents) stay in their current location — they map to existing F-IDs (F-034, F-041, F-033, F-038, F-061) and gradually move to reasoning/ subfolders only when refactor brings clear value.

---

## Sprint dependency map

P1-S7 unblocks:
- **P1-S8 final polish** — beta launch endpoints can call compute_composite_score + compute_monthly_nov without writing the implementation
- **Phase 1.5 P15-S9** — Customer Health Dashboard (P1-CSM-001) + 4 more adoption signals + cron jobs read these data structures
- **Phase 2 P2-S13/S14** — Process Mining full 8 sources extends HeuristicMiner with Inductive + Fuzzy variants

P1-S7 depends on:
- Decimal arithmetic standard (K-9)
- Vietnamese industry list (defaults in INDUSTRY_BENCHMARKS — Phase 1 hand-tuned, Phase 2 customer-tuned)
- Tenant isolation invariant (K-1) — EventLog enforces at data structure layer

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S7 (48 features)
- `docs/strategic/WORKFLOW_SYSTEM.md` PART IV (Process Mining) + PART VIII (Adoption Intelligence) + PART XI (Operational Economics)
- `docs/_v4_extract/process_mining.json` + `adoption_intelligence.json` + `operational_economics.json` — raw 80+70+60 feature dumps from Excel
- `services/process-mining/`, `services/adoption-intel/`, `services/economics/` — Phase 2 extract targets (Phase B-1 skeletons)
