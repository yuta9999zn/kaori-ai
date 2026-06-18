# Sprint P1-S4 — Acceptance Mapping

> **Sprint goal:** "Silver + Gold tiers + data quality"
> **Status:** ✅ 5/7 features mapped (3 existing + 2 deferred to next sprint), Phase B-2 lazy move silver/+gold/ → data_plane/
> **Branch:** `feat/v4-p1-s4` (parent: `feat/v4-p1-s3`)
> **Date:** 2026-05-08

Plumbing + smoke sprint — completes the Phase B-2 folder restructure for `silver/` + `gold/` (now alongside `bronze/` under `data_plane/`). Existing rule catalog (F-NEW3) + gold aggregator (F-032) cover most P1-S4 enterprise features without new code; 2 features deferred (Studio portal not built yet).

---

## Net new work shipped this sprint

| Feature code | Description | Implementation |
|---|---|---|
| **Phase B-2** | Lazy file move `silver/` + `gold/` → `data_plane/silver/` + `data_plane/gold/` | `git mv` × 2 + 5 internal import updates (`..shared` → `...shared`) + 4 external import updates (main.py, routers/clean.py, tests/test_unit_whitebox.py, tests/test_gold_aggregator.py) — 367 → 367 pass, 0 regression. |
| **SH-M57-002 ⭐** | Silver layer storage (columnar DB) — architecture confirmed | ADR-0012 already documents ClickHouse columnar Phase 1.5 (P15-S10). Phase 1 stays Postgres `silver_pipeline_rows`. No code change Sprint P1-S4. |
| **SH-M57-003 ⭐** | Gold layer storage (views + materialized views) | Existing F-032 `gold_features` table + `gold_aggregator.py` aggregator + `data_plane/gold/consumer.py` Kafka consumer. Smoke test only. |

---

## 3 existing features mapped

### Enterprise (3)

| Feature | Existing impl | Acceptance test |
|---|---|---|
| `P2-M25-011` Data Cleaning (remove dups, trim, null) | `data_plane/silver/rule_catalog.py` UNIVERSAL rules: `TRIM_WHITESPACE`, `NORMALIZE_UNICODE`, `REMOVE_EMPTY_ROWS`, `REMOVE_HEADER_DUPES` + per-type rules (`PARSE_DATE`, `FILL_FORWARD_DATE`, etc.) + `routers/clean.py POST /clean/apply` | `tests/test_unit_whitebox.py::TestApplyRulesToDf` (10+ tests) + `tests/test_clean.py` (integration) |
| `P2-M25-020` Data Integration (join Silver tables → dimension) | **DEFERRED to Sprint P1-S5+** — Phase 1 v3 codebase doesn't have multi-source data modeling layer. Star schema work scoped for Phase 2 BI features. | — |
| `P2-M26-023` AI suggested cleaning rules list | `routers/clean.py POST /clean/suggestions` existing endpoint reads rule_catalog + auto-classifies based on column type/purpose | `tests/test_clean.py::test_clean_suggestions` (existing) |

### Studio (2 — DEFERRED)

| Feature | Reason |
|---|---|
| `P3-M33-007` Tab Datasets (Bronze/Silver/Gold snapshot) | Studio portal Phase 2 (P3 features start P2-S15+). When Studio lands, this just queries `data_plane/{bronze,silver,gold}` via existing Postgres tables — no new BE work needed. |
| `P3-M36-003` Insert chart/analysis from Gold layer | Studio portal Phase 2. Reuses existing `chart-registry` (FE) + `gold_features` table read. |

### Cross-cutting (2)

| Feature | Existing impl |
|---|---|
| `SH-M57-002` Silver layer storage (columnar DB) | ADR-0012 documents ClickHouse migration Phase 1.5+. Phase 1 stays Postgres `silver_pipeline_rows` table. |
| `SH-M57-003` Gold layer storage (views + materialized views) | F-032 `gold_features` table + `gold_aggregator.py` + Postgres MV pattern in migration `018_gold_layer.sql`. |

---

## Quick-run smoke command

```bash
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q
# expected: 367 passed, 1 skipped (unchanged from P1-S3 — pure folder move + smoke)
```

Other services unchanged this sprint:
```bash
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q       # 436 pass
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q           # 86 pass
cd "D:\Kaori System\services\notification-service" && python -m pytest -q  # 17 pass
```

**Total: 906 Python pass** (unchanged from P1-S3 — Sprint P1-S4 is restructure + smoke only).

---

## Files touched this sprint (P1-S4)

```
services/data-pipeline/
  silver/                              MOVED → data_plane/silver/        (git mv)
  gold/                                MOVED → data_plane/gold/          (git mv)
  data_plane/silver/rule_catalog.py    MODIFIED (1 internal import: ..shared → ...shared)
  data_plane/gold/aggregator.py        MODIFIED (1 internal import)
  data_plane/gold/consumer.py          MODIFIED (4 internal imports)
  main.py                              MODIFIED (.gold.consumer → .data_plane.gold.consumer)
  routers/clean.py                     MODIFIED (..silver.rule_catalog → ..data_plane.silver.rule_catalog)
  tests/test_unit_whitebox.py          MODIFIED (silver.rule_catalog → data_plane.silver.rule_catalog)
  tests/test_gold_aggregator.py        MODIFIED (data_pipeline.gold/silver → data_pipeline.data_plane.gold/silver)

docs/sprint/P1-S4_ACCEPTANCE.md       NEW (this file)
```

---

## What this sprint did NOT do (deferred / not in scope)

- **P2-M25-020 Data Integration** (join Silver tables → dimension) — needs star schema modeling layer + multi-source dependencies. Scoped for Phase 2 BI features when customer use case emerges (Phase 1 pilot Olist hasn't requested).
- **ClickHouse Silver migration** — P15-S10 per ADR-0012. Phase 1 keeps Postgres `silver_pipeline_rows`.
- **Studio portal features** — Phase 2 (P3-M33-007, P3-M36-003). When Studio lands, the queries are simple reads on already-materialized tables.
- **Frontend wizard updates** — frontend paused.
- **drift Olist 12 file** — still stashed `stash@{0}` from P1-S3 (anh xử khi sẵn sàng).

---

## Phase B-2 progress after Sprint P1-S4

```
services/data-pipeline/
├── data_plane/
│   ├── __init__.py
│   ├── bronze/        ← moved P1-S3 ✅
│   ├── silver/        ← moved P1-S4 ✅ (this sprint)
│   └── gold/          ← moved P1-S4 ✅ (this sprint)
├── ingestion/         ← created P1-S3 ✅
│   └── connectors/
│       ├── postgres_cdc/
│       ├── excel_filesystem/
│       └── zalo_metadata/
├── routers/
├── shared/
└── tests/
```

Phase B-2 for `data-pipeline/` now COMPLETE. Next module to restructure (per RESTRUCTURE_PROPOSAL §3 Step 4) is `services/ai-orchestrator/`:
- P1-S5 will tách `analytics/` → `reasoning/` (or gather under `reasoning/legacy_analytics/`)
- P1-S6 sẽ tạo `workflow_runtime/` (Temporal worker)
- P1-S7 sẽ tạo `org_intel/{process_mining, adoption, economics}/`

---

## Sprint dependency map

P1-S4 unblocks:
- P1-S5 Reasoning Layer + LLM integration (depends on stable data_plane/silver+gold paths)
- Phase 2 P3 Studio features (P3-M33-007, P3-M36-003 — read data_plane tables)

P1-S4 depends on:
- P1-S3 commit `c2799f6` (bronze move + ingestion package; silver/gold movement reuses same lazy pattern)

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S4 (7 features)
- `docs/RESTRUCTURE_PROPOSAL.md` §3 Step 4 (lazy file move strategy)
- `docs/strategic/PIPELINE_UNIFIED.md` Stage 3 (Cleaning → Silver) + Stage 8 (Gold Layer)
- `docs/adr/0012-postgres-clickhouse-polyglot-persistence.md` (ClickHouse migration plan)
- `docs/_v4_extract/sprint_phase1.json` — raw 7-feature list
