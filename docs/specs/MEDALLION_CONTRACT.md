# Medallion Layer Contract

> Updated: 2026-05-21 · Round 5 N3 sync với SRS §2 (8-step Silver pipeline) + 7-dim quality scorecard mig 065
> Source of truth: CLAUDE.md §5 + `docs/ba/3.1_SRS_Software_Requirements_Specification.md §2` (BA layer)
> Cross-ref: `docs/strategic/PIPELINE_UNIFIED.md` (12-stage pipeline) · `docs/ba/3.2_NFRS_Non_Functional_Requirements.md §11` (Data Quality NFRs)

This document pins the **responsibility boundary** between Bronze, Silver, and Gold so future changes don't slip work from one layer into another. The medallion model only delivers value when each layer trusts the next layer's contract — leaks ("I'll just add a fallback in Gold to fix Silver") rot the architecture.

---

## Layer responsibilities

| Layer | Owns | MUST NOT do | Engine (today) | Engine (Phase 2 target) |
|---|---|---|---|---|
| **Bronze (Đồng)** | Raw file ingest. SHA-256 dedup (K-8). Append-only rows (K-2). Replay capability. Magic-byte detect + spoof guard (P2.5). | Cleaning. Column normalization. PII masking. Aggregates. | PostgreSQL `bronze_files` + `bronze_rows` | MinIO/S3 (Parquet) |
| **Silver (Bạc)** | 8-step transformation pipeline (see §Silver Pipeline below). Canonical column names (per `config/language_dictionary.json`). PII masking before any external call (K-5). Partitioned by tenant + month. **Quality gate ≥80% pass to Gold.** | Per-customer features. Per-tenant aggregates. Business metrics. | PostgreSQL `silver_rows` (`clean_data` JSONB) + per-domain tables mig 051 | ClickHouse (columnar) |
| **Gold (Vàng)** | Per-customer feature engineering (`gold_features`). Per-tenant rollups (`gold_aggregates`). Dashboard-optimised reads. **Trusts Silver canonical schema. KHÔNG fallback Bronze/Silver direct** (memory `feedback_medallion_separation`). | Column rename / hint / fallback. Cleaning rules. PII work. Bronze replay. | PostgreSQL `gold_features` + `gold_aggregates` (mig 018) + Gold views (mig 052 — chỉ-từ-Silver, KHÔNG bronze_*/silver_rows/JSONB) | PostgreSQL MV + Redis |

---

## Silver Pipeline — 8-step transformation (canonical, per SRS §2)

> Every row crossing Bronze → Silver MUST pass these 8 steps in order. Module map: `services/data-pipeline/silver/`. Drift detection: shape tests in `tests/test_silver_pipeline.py` enforce step ordering.

| # | Step | Purpose | Module / file | K-rule | NFR target |
|---|---|---|---|---|---|
| 1 | **Schema validation** | Required columns present per `mapping_templates` (mig 048); enum values match domain dictionary | `silver/schema_validator.py` | K-9 NUMERIC(5,4)/(14,4) precision | NFR-DQ-02 reject rate ≤10% |
| 2 | **Type cast** | Source string → typed (NUMERIC, BIGINT, DATE, BOOLEAN). Coerce-fail rows flagged not dropped | `silver/type_coercer.py` | — | — |
| 3 | **Null handling** | Drop OR impute per rule (median/mean/forward-fill/business default); track null-rate dimension | `silver/null_handler.py` + `rule_catalog.py` Layer 1 Universal | — | NFR-DQ-01 ≥80% pass to Gold |
| 4 | **Dedup** | SHA-256 row fingerprint per business key. Keep first/last/longest_non_empty per `rule_catalog.py` | `silver/dedup.py` (P2.5 dedup_records VN-aware) | K-8 idempotency | NFR-DQ-03 track dedup rate per tenant |
| 5 | **PII masking VN** | Tên→`{{role:X}}`, SĐT→`{{phone:****1234}}`, CCCD→`{{cccd:hash:abc123}}`, email→hash, address→region only. F1 ≥0.95 on VN test corpus | `silver/pii_masker.py` (Vietnamese NER + regex hybrid) | K-5 PII redact | NFR-PR-01 F1 ≥0.95 · NFR-DQ-04 precision/recall ≥0.97/0.95 |
| 6 | **Normalize** | SĐT → +84 E.164; tiền → VND integer; ngày → ISO 8601; tên công ty → canonical via `vn_company_normalizer`; địa chỉ → 4-level (province/district/ward/street) | `silver/normalizer.py` + `config/language_dictionary.json` | — | — |
| 7 | **Outlier flag** | Z-score per-column (>3σ) + IQR (>1.5×) tag rows as `outlier_flag=true`. KHÔNG drop, chỉ flag — analyst quyết. | `silver/outlier_detector.py` | — | — |
| 8 | **Lineage tag** | Every silver row carries `bronze_file_id` (FK) + `pipeline_run_id` + `silver_pipeline_version` + `transformations_applied[]` (json array of step IDs 1-7) | `silver/lineage_tagger.py` + `data_lineage_edges` mig 097 | K-19 OTel `tenant_id` span | NFR-DQ-05 lineage tag mọi record |

**Date direction (step 6, no hard-coded locale):** `rule_parse_date` (`silver/rule_catalog.py`) does NOT assume a region's D/M/Y vs M/D/Y order. It **measures** the column with `_infer_dayfirst`: a value whose first part is >12 (e.g. `27/12`) proves day-first; a second part >12 (e.g. `12/27`) proves month-first. The column is sampled **randomly** (not the head) so rows that happen to cluster early in a month don't mislead it, and **every row in a column is parsed the same way**. Only a column with no disambiguating value (all parts ≤12) falls back to the documented default `KAORI_DATE_DAYFIRST_DEFAULT` (day-first, VN/ISO-region convention; env-overridable) — measured evidence always wins over the default. Year-first ISO values are unambiguous and never vote. Tests: `tests/test_unit_whitebox.py::TestInferDayfirstHelper` + `::TestRuleParseDateDirectionInference`.

**Gate ≥80%:** Weighted average of 7 quality dimensions (mig 065 + `silver/quality.py`) must ≥ tenant target threshold (default 0.80) before promote to Gold. If fail → batch DỪNG ở Silver, hiện scorecard, user duyệt cleaning rule tweaks. KHÔNG auto-skip to Gold.

### 7-Dimension Quality Scorecard (mig 065 + `silver/quality.py`)

Replaces single null-rate scalar (mig 003 `quality_score NUMERIC(5,4)` kept for backward compat). Each dimension scored 0..1, weighted average against tenant target:

| Dim | Definition | Default weight |
|---|---|---|
| Completeness | 1 - (null cells / total cells), weighted by column importance | 0.20 |
| Validity | % rows passing schema validation (step 1) | 0.20 |
| Uniqueness | 1 - (dup rows / total rows) per business key | 0.15 |
| Consistency | Cross-column rule pass rate (e.g. end_date > start_date) | 0.15 |
| Timeliness | % rows with `event_ts` within expected freshness window | 0.10 |
| Accuracy | Sample-audited correctness (manual scoring or domain-rule pass) | 0.10 |
| Conformity | % values matching canonical formats (VN phone, ID, address) | 0.10 |

Per-tenant weight override via `tenant_quality_config.dimension_weights` JSONB. Tenant target default 0.80 per NFR-DQ-01.

---

## Silver schema fields (canonical)

Mandatory columns on every `silver_rows` row (per SRS §2 invariant):

| Field | Type | Purpose |
|---|---|---|
| `silver_row_id` | UUID PK | Stable identifier |
| `tenant_id` | UUID | K-1 RLS partition key |
| `bronze_file_id` | UUID FK | Lineage upstream — points to `bronze_files.id` (mig 097 ObjectKind = `silver_row` upstream walks to `bronze_file`) |
| `pipeline_run_id` | UUID FK | Which pipeline run produced this row |
| `silver_pipeline_version` | TEXT | Code version applied (e.g. `silver_v2.3.1`) — replay reproducibility |
| `clean_data` | JSONB | Canonical column names + values post-transformation |
| `transformations_applied` | JSONB array | Step IDs 1-7 applied (audit which steps fired) |
| `pii_masked_fields` | JSONB array | Which fields were masked at step 5 (audit + un-mask path for compliance request) |
| `outlier_flag` | BOOLEAN | Step 7 output |
| `quality_score` | NUMERIC(5,4) | Aggregate 7-dim weighted score |
| `quality_dimensions` | JSONB | Per-dim breakdown (Completeness/Validity/.../Conformity) |
| `created_at` | TIMESTAMPTZ | Append timestamp |
| `partition_key` | TEXT GENERATED | `tenant_id || '_' || date_trunc('month', created_at)` for partitioning |

RLS policy: `WHERE tenant_id = current_setting('app.tenant_id')::uuid`. Mig 005 (RLS) + mig 084 (Vault grants for read/write roles).

---

## Canonical Silver schema (read by Gold)

The Gold layer reads `silver_rows.clean_data` JSONB **strictly by canonical key name**. Source columns are mapped to canonical names by `bronze/column_mapper.py` against `config/language_dictionary.json` and confirmed by the user via `POST /api/v1/schema/confirm`.

The canonical names Gold relies on (Phase 1):

| Canonical key | Type in `clean_data` | Used by | Required for |
|---|---|---|---|
| `customer_external_id` | string | F-032 aggregator (Gold), F-031 billing cron | `revenue_at_risk` computation, `COUNT(DISTINCT)` billing |
| `date` | ISO 8601 string | F-032 aggregator (last_purchase_at) | 90-day churn cutoff |
| `revenue` *or* `amount` | numeric (BigDecimal-safe) | F-032 aggregator (avg_purchase_value) | `revenue_at_risk` ceiling |

If a tenant's data does not include any of these canonical keys, the Gold aggregator **logs and skips** that tenant — it never falls back to a different column name. Pilot onboarding (Customer Success team) is responsible for mapping the source columns to the canonical names during the schema-confirm step.

---

## What "canonical" means in practice

A canonical name lives in `config/language_dictionary.json` under `fields.{canonical_name}` with multilingual aliases for VI / EN / JA / KO / ZH. The `bronze/column_mapper.py` cascade matches source columns against those aliases:

1. Exact match → confidence 1.0
2. Fuzzy substring (rapidfuzz) → 0.65–0.95
3. LLM semantic (Qwen) → 0.4–0.7

When you need a new canonical (say a new Gold metric needs a field Silver doesn't expose):

1. Add the canonical entry to `config/language_dictionary.json` with VI/EN/JA(/KO/ZH) aliases.
2. The next pipeline run picks it up automatically — no code change in `column_mapper.py`.
3. Verify the user-confirm flow surfaces the new canonical in the FE schema-review step.
4. **Then** write the Gold consumer — it reads the canonical key by name with no fallback logic.

---

## F-032 in this contract

Gold Layer F-032 (Sprint 4-5) is the first concrete consumer of the Silver canonical contract. It introduces:

- `gold_features` (per `(enterprise_id, customer_external_id)`) — `revenue_at_risk` + `last_purchase_at` + `total_purchases` + `purchase_count` + `avg_purchase_value` + `is_actioned` (Phase 2 hook).
- `gold_aggregates` (per `(enterprise_id, metric_key)`) — Phase 1 writes `total_revenue_at_risk` and `at_risk_customer_count`.

The aggregator reads `silver_rows.clean_data` JSONB by canonical name strictly. If `customer_external_id` is missing from a tenant's data, the aggregator logs `gold.skip.no_customer_id` and produces no rows for that tenant. It does NOT try `customer_id`, `customer_name`, or any other key as a fallback — that would be Silver's job.

The Phase 1 limitation around the North Star metric (`is_actioned` workflow) is documented in `docs/PHASE1_CLOSEOUT_PLAN.md` Sign-off section + `DEMO_RUNBOOK.md` (added in Sprint 6).

---

## Test pyramid by layer

| Layer | Unit | Integration | E2E |
|---|---|---|---|
| Bronze | `bronze/ingestor.py` SHA-256, file format detection | `/upload` POST → `bronze_rows` rows persisted | full upload-to-status workflow via FE |
| Silver | `silver/rule_catalog.py` rule application on DataFrames | `/clean/apply` → `silver_rows.clean_data` shape | wizard step 3 |
| Gold | `gold/aggregator.py` `revenue_at_risk` math | Kafka `silver.complete` event → `gold_features` upsert | dashboard read |

When a test breaks because a layer started doing the wrong layer's work, **fix the architecture, not the test**. Add the canonical, normalize at Silver, keep Gold strict.
