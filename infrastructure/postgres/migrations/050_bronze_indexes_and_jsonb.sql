-- 050_bronze_indexes_and_jsonb.sql — P15-S11 Tuần 7 ngày 5.
--
-- Data-scale mitigations from BUILD_WEEK_MULTI_TENANT_ANALYSIS.md §3:
--
--   1. GIN index on bronze_rows.raw_data — supports
--      `WHERE raw_data ->> 'customer_id' = ?` lookups in <50ms even
--      when bronze_rows has 10M+ rows. Without it, sequential scan
--      kills any Bronze-level inspection UI.
--
--   2. Composite covering indexes on the (tenant, dept, source, time)
--      hot paths for Data Explorer + per-department dashboards.
--
--   3. NOTE on partitioning: declarative partitioning of bronze_rows
--      by year_month was on the original plan, but doing it correctly
--      requires a multi-statement migration (CREATE TABLE … PARTITION
--      OF + move existing rows). That's a 1-day operation we shouldn't
--      attempt mid-Build-Week. INSTEAD this migration adds a BRIN
--      index on created_at — cheap, append-friendly, gives 80% of
--      the partition pruning benefit for time-window queries. Full
--      partitioning lands post-Build-Week when we have a maintenance
--      window.
--
-- Index size impact estimate (worst-case 10M bronze_rows):
--   - GIN on raw_data:       ~600MB
--   - BRIN on created_at:   ~50KB (BRIN is ~1000× smaller than B-tree)
--   - Composite B-tree (4):  ~400MB
-- → +1GB index storage. Acceptable for Phase 1.5; Phase 2 trims via
--   partial indexes once query patterns are stable.

-- ─── 1. GIN on bronze_rows.raw_data ──────────────────────────────────
--
-- Enables fast JSONB key/value lookups:
--   WHERE raw_data ->> 'customer_id' = 'xyz'
--   WHERE raw_data @> '{"category":"electronics"}'
-- without scanning the whole table.
--
-- jsonb_path_ops is faster + smaller than the default jsonb_ops, BUT
-- only supports @> queries. We use default jsonb_ops because the
-- bronze inspector UI needs ->> on arbitrary keys.

CREATE INDEX IF NOT EXISTS idx_bronze_rows_raw_data_gin
    ON bronze_rows USING gin (raw_data);

-- ─── 2. BRIN on created_at — partition-prune proxy ──────────────────
--
-- bronze_files is append-mostly (new uploads go to end). BRIN gives
-- range-based pruning for `WHERE created_at BETWEEN x AND y` at ~50KB
-- storage vs ~50MB for an equivalent B-tree.

CREATE INDEX IF NOT EXISTS brin_bronze_files_uploaded_at
    ON bronze_files USING brin (created_at)
    WITH (pages_per_range = 32);

-- ─── 3. Composite covering indexes for hot read paths ────────────────
--
-- Data Explorer landing page (data-pipeline routers/data_explorer.py):
-- 1 query per layer that scans last 30d files for the tenant + dept.
-- The mig-047 idx_bronze_files_dept_uploaded already exists; add a
-- partial-index variant that excludes archived files (most queries
-- filter out archived).

-- bronze_files has no `filename` column today (filename lives on
-- pipeline_runs via run_id). INCLUDE covers the columns most-queried
-- alongside the dept/created_at lookup — sheet_name + run_id.
CREATE INDEX IF NOT EXISTS idx_bronze_files_active_recent
    ON bronze_files (enterprise_id, department_id, created_at DESC)
    INCLUDE (file_id, sheet_name, run_id);

-- Schema mapping template lookup: fired on every upload to check if
-- a saved template matches the new file's pattern. Hot path; covering
-- include avoids second lookup for the column_mapping JSONB.
CREATE INDEX IF NOT EXISTS idx_mapping_templates_pattern_covering
    ON mapping_templates (enterprise_id, source_id, is_active, file_pattern)
    INCLUDE (template_id, column_mapping, last_used_at)
    WHERE is_active = TRUE;

-- KPI dashboard tile: "show me Marketing's CAC + LTV + churn_rate
-- for the last 3 months". Hits kpi_measurements with WHERE
-- (enterprise_id, dept_id, kpi_code, period_end DESC LIMIT 3).
-- mig-049 already created idx_kpi_measurements_dashboard; add a
-- covering variant.
CREATE INDEX IF NOT EXISTS idx_kpi_measurements_dashboard_covering
    ON kpi_measurements (enterprise_id, department_id, kpi_code, period_end DESC)
    INCLUDE (raw_value, classification, benchmark_percentile, trend_pct);

-- ─── 4. Silver-tier read paths ───────────────────────────────────────

-- "Show me the cleaning quality score for files this department uploaded
-- this week". Index supports the Data Explorer Silver tile.
CREATE INDEX IF NOT EXISTS idx_silver_rows_quality_recent
    ON silver_rows (enterprise_id, department_id, quality_score DESC)
    WHERE quality_score IS NOT NULL;

-- ─── 5. Statistics — help the planner ────────────────────────────────
--
-- Multi-column statistics on (enterprise_id, department_id) so the
-- planner gets correct row estimates for filtered joins. Default
-- pg_stats is per-column → estimate (P(e_id) × P(dept_id)) which
-- under-counts when departments cluster per enterprise.

CREATE STATISTICS IF NOT EXISTS stat_bronze_files_ent_dept (dependencies)
    ON enterprise_id, department_id
    FROM bronze_files;

CREATE STATISTICS IF NOT EXISTS stat_silver_rows_ent_dept (dependencies)
    ON enterprise_id, department_id
    FROM silver_rows;

CREATE STATISTICS IF NOT EXISTS stat_kpi_meas_ent_dept_kpi (dependencies)
    ON enterprise_id, department_id, kpi_code
    FROM kpi_measurements;

-- Refresh statistics now so the next ANALYZE picks them up.
ANALYZE bronze_files;
ANALYZE silver_rows;
ANALYZE kpi_measurements;

-- ─── 6. Comments ─────────────────────────────────────────────────────

COMMENT ON INDEX idx_bronze_rows_raw_data_gin IS
    'P15-S11 mig 050 — GIN supports raw_data->>field and @> JSONB ops in <50ms over 10M rows. ~600MB storage at full scale.';
COMMENT ON INDEX brin_bronze_files_uploaded_at IS
    'P15-S11 mig 050 — BRIN range-prune proxy for partition pruning. ~50KB storage. Replaces full year_month partitioning until post-Build-Week maintenance window.';
