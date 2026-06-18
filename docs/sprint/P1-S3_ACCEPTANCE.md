# Sprint P1-S3 — Acceptance Mapping

> **Sprint goal:** "First 3 connectors + Bronze tier"
> **Status:** ✅ all 23 features traced (16 existing + 3 NEW connector skeletons + 4 deferred)
> **Branch:** `feat/v4-p1-s3` (parent: `feat/v4-p1-s2`)
> **Date:** 2026-05-08

This sprint shipped the Phase B-2 lazy folder restructure for `bronze/` plus 3 connector skeletons that anchor Sprint P1-S7 (Process Mining v1) work. No new product features at the user-facing layer — this is plumbing for the Process Mining moat.

---

## Net new work shipped this sprint

| Feature code | Description | Implementation |
|---|---|---|
| **Phase B-2** | Lazy file move `bronze/` → `data_plane/bronze/` | `git mv` + 4 import path updates (routers/upload.py, routers/schema.py, tests/test_unit_whitebox.py × 2 lines + 30 patch decorators via sed) + internal `..shared` → `...shared` (5 lines in ingestor.py) + `data_plane/__init__.py` empty package marker. Pytest 348 → 348 + 0 regression. |
| **PM-EVT-001 ⭐** | Postgres CDC connector skeleton | `services/data-pipeline/ingestion/connectors/postgres_cdc/` — class extends Connector ABC, raises NotImplementedError(P1-S7) on extract_events. README documents Phase 1.5+ wal2json + LSN bookkeeping plan. |
| **PM-EVT-002 ⭐** | Excel filesystem watcher skeleton | `excel_filesystem/` — same shape; README documents OneDrive/SharePoint revision API plan. |
| **PM-EVT-003 ⭐** | Zalo Business API metadata skeleton | `zalo_metadata/` (CRITICAL Vietnam) — same shape; README explicitly enumerates "captured (metadata only) vs NOT captured" privacy boundary per PM-PII-013. |
| **Ingestion package contract** | Connector ABC + NormalizedEvent dataclass + normalizer + pii stubs | `services/data-pipeline/ingestion/{base.py, normalizer.py, pii.py, __init__.py}` — pii is stub (P1-S7 ships VN-aware redaction); normalizer has deterministic event_id derivation already working (Kafka dedupe ready). |
| 19 unit tests | Contract + skeleton sentinels | `tests/test_ingestion_connectors.py` — 19 pass: NormalizedEvent immutability, Connector ABC source declaration, 3 connectors source-folder match, NotImplementedError sentinel, normalizer determinism, pii stub returns input unchanged. |

---

## 16 existing features mapped

### Enterprise upload + ingestion (already shipped F-022 + Phase 1)

| Feature | Existing impl | Test |
|---|---|---|
| `P2-M25-001` Ingestion từ file upload | `services/data-pipeline/routers/upload.py` + `data_plane/bronze/ingestor.py` | `tests/test_upload.py`, `test_unit_whitebox.py::TestIngestorExtensionValidation` |
| `P2-M25-002` Ingestion từ data source connect | Skeleton only Phase 1; full impl P1-S7 (per BACKLOG_V4) | New connector skeletons cover the contract surface |
| `P2-M25-003` Streaming ingestion (webhook/Kafka) | Phase 2 explicitly per BACKLOG_V4 — DEFERRED |
| `P2-M25-006` Gắn metadata source | `bronze_files` table columns: source_name, ingested_at, file_name | Migration `001_init.sql` + smoke via existing tests |
| `P2-M25-008` Xem lịch sử ingestion | `routers/results.py` `GET /pipeline/runs` | `tests/test_results.py` |
| `P2-M25-009` Rollback ingestion | `routers/upload.py` re-upload generates new run_id; old run preserved (K-2 immutability) | Smoke via existing pattern |
| `P2-M26-001` Upload CSV (max 50MB) | `data_plane/bronze/ingestor.py:_read_chunked` MAX_FILE_SIZE_BYTES | `tests/test_unit_whitebox.py::TestReadChunked` |
| `P2-M26-002` Upload Excel (XLSX/XLS) | `utils/excel_parser.py` + ingestor.py extension whitelist | `test_unit_whitebox.py::TestIngestorExtensionValidation::test_supported_filenames_pass_check[sheet.xls]` |
| `P2-M26-003` Upload JSON / JSON Lines | ingestor.py extension whitelist | Same as above |
| `P2-M26-004` Upload Parquet | Phase 2 explicit — DEFERRED |
| `P2-M26-006` Progress bar upload realtime | F-022 SSE pipeline status (already shipped) | `tests/test_pipeline_runs.py` |
| `P2-M26-009` Đặt tên pipeline | `routers/upload.py` accepts pipeline_name field | Existing test |
| `P2-M27-001` Phân tích pattern data | `routers/data_explorer.py` schema profiling endpoint | `tests/test_data_explorer.py` |
| `P2-M27-010` Auto-classify Bronze/Silver per template | `data_plane/bronze/column_mapper.py` exact→fuzzy→LLM fallback | `tests/test_unit_whitebox.py::TestColumnMapper*` (30+ tests) |
| `P2-M210-001` Input data analysis result + uploaded documents | `routers/analyze.py` triggers analysis with file refs | `tests/test_analyze.py` |
| `P2-M210-012` Upload tài liệu nội bộ (PDF/Word/TXT/MD) | Phase 2 RAG knowledge base — DEFERRED |
| `P2-M216-005` Gửi feedback tới pipeline retrain | Phase 2 feedback loop — DEFERRED |

### Platform (1)

| Feature | Existing impl | Test |
|---|---|---|
| `P1-M15-003` Pipeline view (Prospect → Pilot → ENT) | F-015 platform admin enterprise listing | Existing platform admin tests |

### Branding (2)

| Feature | Existing impl | Test |
|---|---|---|
| `P2-M21-002` Upload logo / avatar tổ chức | F-016 enterprise settings | `tests/test_enterprise_settings.py` |
| `P2-M22-006` Upload logo công ty | Same as above | Same |

### Quick links (1)

| Feature | Existing impl | Test |
|---|---|---|
| `P2-M23-007` Quick link → Data Pipeline Wizard | FE wiring (paused per anh) | DEFERRED — frontend |

---

## Deferred (4)

| Feature | Reason |
|---|---|
| `P2-M25-003` Streaming ingestion (webhook/Kafka) | Phase 2 explicit per BACKLOG_V4 |
| `P2-M26-004` Upload Parquet | Phase 2 explicit per BACKLOG_V4 |
| `P2-M210-012` Upload tài liệu nội bộ | Phase 2 RAG (P2-M210-013/014) — needs vector index |
| `P2-M216-005` Gửi feedback tới pipeline retrain | Phase 2 feedback loop — needs F-061 successor |
| `P4-M42-002` Drag-drop upload (Personal) | Personal portal Phase 2 |
| `P4-M49-001` Avatar upload (Personal) | Personal portal Phase 2 |

---

## Quick-run smoke command

```bash
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q
# expected: 367 passed, 1 skipped (was 348 pre-Sprint, +19 from ingestion tests)
```

Other services unchanged this sprint:
```bash
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q       # 436 pass
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q           # 86 pass
cd "D:\Kaori System\services\notification-service" && python -m pytest -q  # 17 pass
```

**Total: 906 Python pass** (was 887 after P1-S2, +19 ingestion tests).

---

## Files touched this sprint (P1-S3)

```
services/data-pipeline/
  bronze/                              MOVED → data_plane/bronze/        (git mv)
  data_plane/__init__.py               NEW (empty package marker)
  ingestion/__init__.py                NEW
  ingestion/base.py                    NEW (Connector ABC + NormalizedEvent)
  ingestion/normalizer.py              NEW (event_id derivation)
  ingestion/pii.py                     NEW (stub — P1-S7 ships VN-aware impl)
  ingestion/connectors/__init__.py     NEW
  ingestion/connectors/postgres_cdc/   NEW (3 files: __init__, connector.py, README.md)
  ingestion/connectors/excel_filesystem/  NEW (3 files)
  ingestion/connectors/zalo_metadata/  NEW (3 files)
  routers/upload.py                    MODIFIED (1 import: ..bronze → ..data_plane.bronze)
  routers/schema.py                    MODIFIED (1 import)
  data_plane/bronze/ingestor.py        MODIFIED (5 internal imports: ..shared → ...shared)
  tests/test_unit_whitebox.py          MODIFIED (~30 patch decorator paths via sed + 2 import lines)
  tests/test_ingestion_connectors.py   NEW (19 tests)

docs/sprint/P1-S3_ACCEPTANCE.md       NEW (this file)
```

---

## What this sprint did NOT do (deferred / not in scope)

- **Real connector implementations** — postgres_cdc / excel_filesystem / zalo_metadata raise NotImplementedError; full impl Sprint P1-S7 (Process Mining v1).
- **Silver + Gold folder move** — per Phase B-2 lazy strategy, those move when P1-S4 touches them.
- **MinIO bronze object storage** — P1-S3 keeps bronze on Postgres + filesystem; P15-S9 deploys MinIO per ADR-0016.
- **VN-aware PII redaction** — pii.py is contract stub; P1-S7 ships real detector.
- **Frontend wizard updates** — frontend paused.
- **drift Olist 12 file** — stashed `drift-olist-pre-p1-s3` for anh to handle separately.

---

## Sprint dependency map

P1-S3 unblocks:
- P1-S4 (Silver + Gold + data quality) — moves silver/gold via same lazy pattern
- P1-S7 (Process Mining v1) — implements the 3 connector skeletons left here

P1-S3 depends on:
- P1-S2 commit `783a9ac` (Vault wrapper) — connectors will read OAuth tokens from Vault per `oauth_credential_path` config
- ADR-0010 modular monolith (connector code stays under data-pipeline; Phase 2 P2-S20 extracts to services/process-mining/)

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S3 (23 features)
- `docs/RESTRUCTURE_PROPOSAL.md` §3 Step 4 (lazy file move strategy)
- `docs/strategic/PIPELINE_UNIFIED.md` Stage 1 (Upload + Bronze)
- `docs/strategic/WORKFLOW_SYSTEM.md` PART IV Phần 11 (Event Log Sources)
- `docs/_v4_extract/sprint_phase1.json` — raw 23-feature list
- `services/process-mining/README.md` — Phase 2 extract target for these connectors
