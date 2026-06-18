-- =====================================================================
-- 065_quality_dimensions.sql
--
-- P15-S11 — replace single null-rate quality_score with 7-dim scorecard
-- per PIPELINE_UNIFIED.md Stage 4 (Quality Scorecard Gate).
--
-- Adds:
--   pipeline_runs.quality_dimensions JSONB
--     Shape (computed in services/data-pipeline/data_plane/silver/quality.py):
--       {
--         "completeness":  0.0..1.0,   -- non-null on required cols
--         "validity":      0.0..1.0,   -- value matches expected pattern
--         "uniqueness":    0.0..1.0,   -- primary-key dedup
--         "consistency":   0.0..1.0,   -- cross-column rules
--         "timeliness":    0.0..1.0,   -- rows within freshness window
--         "accuracy":      0.0..1.0,   -- plausible range / outlier
--         "integrity":     0.0..1.0,   -- FK to master tables
--         "weights":       { … },
--         "issues":        [ { code, dim, severity, message, count }, … ]
--       }
--
-- The existing pipeline_runs.quality_score scalar is kept and now holds
-- the WEIGHTED overall (sum of dim_i * weight_i) — same 0-1 range but
-- meaningful instead of "fraction of non-null cells".
-- =====================================================================

BEGIN;

ALTER TABLE pipeline_runs
    ADD COLUMN IF NOT EXISTS quality_dimensions JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN pipeline_runs.quality_dimensions IS
    '7-dim quality scorecard per Stage 4 spec — completeness/validity/uniqueness/consistency/timeliness/accuracy/integrity. Issues array carries per-rule hits for the FE drill-down.';

-- Extend the status check constraint to allow 'unstructured_pending' —
-- the new state for uploads that take the Stage 6 placeholder branch
-- (PDF/DOCX/image accepted, parsing deferred to DocSage P15-S11+).
ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS chk_pipeline_status;
ALTER TABLE pipeline_runs ADD CONSTRAINT chk_pipeline_status
    CHECK (status IN (
        'uploading',
        'bronze_complete',
        'schema_review',
        'silver_complete',
        'analysis_complete',
        'unstructured_pending',
        'failed',
        'cancelled'
    ));

COMMIT;
