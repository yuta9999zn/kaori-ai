-- Migration 006: Replace analysis tables with multi-template orchestrator schema
-- + fix silver_rows column mismatch for runner.py

-- ============================================================
-- 1. DROP DEPENDENT VIEWS
-- ============================================================
DROP VIEW IF EXISTS v_pipeline_summary;
DROP VIEW IF EXISTS v_enterprise_kpis;

-- ============================================================
-- 2. RENAME OLD TABLES (only if not already renamed)
-- ============================================================
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analysis_runs' AND schemaname = 'public')
    AND NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analysis_runs_v1' AND schemaname = 'public')
    THEN
        ALTER TABLE analysis_runs RENAME TO analysis_runs_v1;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analysis_results' AND schemaname = 'public')
    AND NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'analysis_results_v1' AND schemaname = 'public')
    THEN
        ALTER TABLE analysis_results RENAME TO analysis_results_v1;
    END IF;
END $$;

-- Drop stale RLS policies on renamed tables (safe to run multiple times)
DROP POLICY IF EXISTS tenant_analysis_runs    ON analysis_runs_v1;
DROP POLICY IF EXISTS tenant_analysis_results ON analysis_results_v1;
DROP POLICY IF EXISTS enterprise_isolation_analysis_runs ON analysis_runs_v1;

-- ============================================================
-- 3. NEW analysis_runs — one row per user-initiated batch
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_runs (
    id            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id        UUID         NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    templates     TEXT[]       NOT NULL,
    config        JSONB        NOT NULL DEFAULT '{}',
    status        VARCHAR(20)  NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued','running','done','error')),
    overview      JSONB,
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_run        ON analysis_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_enterprise ON analysis_runs(enterprise_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_pending    ON analysis_runs(status, run_id)
    WHERE status IN ('queued', 'running');

-- ============================================================
-- 4. NEW analysis_results — one row per template per batch
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_run_id UUID         NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    template_id     VARCHAR(50)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','done','error')),
    results_payload JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_run        ON analysis_results(analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_analysis_results_enterprise ON analysis_results(enterprise_id, created_at DESC);

-- ============================================================
-- 5. RLS on new tables
-- ============================================================
ALTER TABLE analysis_runs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'analysis_runs' AND policyname = 'tenant_analysis_runs') THEN
        CREATE POLICY tenant_analysis_runs ON analysis_runs
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'analysis_results' AND policyname = 'tenant_analysis_results') THEN
        CREATE POLICY tenant_analysis_results ON analysis_results
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE analysis_runs    FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_results FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON analysis_runs    TO kaori_app;
GRANT SELECT, INSERT, UPDATE ON analysis_results TO kaori_app;

-- ============================================================
-- 6. silver_rows: rename clean_data → row_data (once only)
--    add run_id column (once only)
-- ============================================================
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'silver_rows' AND column_name = 'clean_data'
    ) THEN
        ALTER TABLE silver_rows RENAME COLUMN clean_data TO row_data;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'silver_rows' AND column_name = 'run_id'
    ) THEN
        ALTER TABLE silver_rows
            ADD COLUMN run_id UUID REFERENCES pipeline_runs(run_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Backfill run_id for pre-existing rows via bronze lineage
UPDATE silver_rows sr
SET    run_id = pr.run_id
FROM   bronze_rows  br
JOIN   bronze_files bf ON bf.file_id = br.file_id
JOIN   pipeline_runs pr ON pr.run_id = bf.run_id
WHERE  sr.bronze_row_id = br.row_id
  AND  sr.run_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_silver_rows_run ON silver_rows(run_id, enterprise_id);

-- ============================================================
-- 7. RECREATE VIEWS against new schema
-- ============================================================
CREATE OR REPLACE VIEW v_pipeline_summary AS
SELECT
    pr.run_id,
    pr.enterprise_id,
    pr.filename,
    pr.status,
    pr.detected_language,
    pr.sheet_count,
    pr.row_count_bronze,
    pr.row_count_silver,
    pr.quality_score,
    COUNT(DISTINCT cs.schema_id)                                            AS mapped_columns,
    COUNT(DISTINCT cs.schema_id) FILTER (WHERE cs.user_confirmed = TRUE)    AS confirmed_columns,
    COUNT(DISTINCT ar.id)                                                   AS analysis_run_count,
    COALESCE(BOOL_OR(ar.status IN ('queued','running')), FALSE)             AS analysis_in_progress,
    pr.created_at
FROM pipeline_runs pr
LEFT JOIN bronze_files      bf ON bf.run_id  = pr.run_id
LEFT JOIN canonical_schemas cs ON cs.file_id = bf.file_id
LEFT JOIN analysis_runs     ar ON ar.run_id  = pr.run_id
GROUP BY pr.run_id, pr.enterprise_id, pr.filename, pr.status,
         pr.detected_language, pr.sheet_count, pr.row_count_bronze,
         pr.row_count_silver, pr.quality_score, pr.created_at;

CREATE OR REPLACE VIEW v_enterprise_kpis AS
SELECT
    e.enterprise_id,
    e.name                                                                   AS enterprise_name,
    COUNT(DISTINCT pr.run_id)                                                AS total_pipeline_runs,
    COUNT(DISTINCT pr.run_id)
        FILTER (WHERE pr.created_at >= NOW() - INTERVAL '30 days')         AS runs_last_30d,
    COUNT(DISTINCT ar.id)                                                    AS total_analysis_runs,
    SUM(ARRAY_LENGTH(ar.templates, 1))                                       AS total_templates_run,
    AVG(pr.quality_score) FILTER (WHERE pr.quality_score IS NOT NULL)        AS avg_quality_score,
    MAX(pr.created_at)                                                       AS last_upload_at
FROM enterprises e
LEFT JOIN pipeline_runs pr ON pr.enterprise_id = e.enterprise_id
LEFT JOIN analysis_runs ar ON ar.run_id        = pr.run_id
GROUP BY e.enterprise_id, e.name;
