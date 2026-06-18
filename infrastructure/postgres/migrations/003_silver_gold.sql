-- Migration 003: Silver layer + Analysis tables

-- ============================================================
-- SILVER ROWS (cleaned data)
-- ============================================================
CREATE TABLE IF NOT EXISTS silver_rows (
    row_id        BIGSERIAL    PRIMARY KEY,
    file_id       UUID         NOT NULL REFERENCES bronze_files(file_id) ON DELETE CASCADE,
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    bronze_row_id BIGINT       NOT NULL REFERENCES bronze_rows(row_id),
    row_index     INT          NOT NULL,
    clean_data    JSONB        NOT NULL,
    applied_rules TEXT[]       NOT NULL DEFAULT '{}',
    quality_score NUMERIC(5,4),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_silver_rows_file       ON silver_rows(file_id);
CREATE INDEX IF NOT EXISTS idx_silver_rows_enterprise ON silver_rows(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_silver_rows_bronze     ON silver_rows(bronze_row_id);

-- ============================================================
-- CLEANING RULES APPLIED
-- ============================================================
CREATE TABLE IF NOT EXISTS cleaning_rules_applied (
    id              BIGSERIAL    PRIMARY KEY,
    file_id         UUID         NOT NULL REFERENCES bronze_files(file_id) ON DELETE CASCADE,
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    rule_id         VARCHAR(100) NOT NULL,
    rule_category   VARCHAR(30)  NOT NULL,
    affected_column VARCHAR(100),
    rows_affected   INT          NOT NULL DEFAULT 0,
    user_approved   BOOLEAN      NOT NULL DEFAULT FALSE,
    applied_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cleaning_rules_file ON cleaning_rules_applied(file_id);

-- ============================================================
-- ANALYSIS RUNS (single-template; replaced by multi-template in 006)
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_runs (
    analysis_id   UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id        UUID         NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    template      VARCHAR(50)  NOT NULL,
    config        JSONB        NOT NULL DEFAULT '{}',
    status        VARCHAR(20)  NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','complete','failed')),
    model_used    VARCHAR(100),
    llm_provider  VARCHAR(30),
    cost_vnd      NUMERIC(14,4) NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_run        ON analysis_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_enterprise ON analysis_runs(enterprise_id, created_at DESC);

-- ============================================================
-- ANALYSIS RESULTS
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    result_id     UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id   UUID         NOT NULL REFERENCES analysis_runs(analysis_id) ON DELETE CASCADE,
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    result_type   VARCHAR(50)  NOT NULL,
    chart_kind    VARCHAR(30),
    data_shape    VARCHAR(50),
    payload       JSONB        NOT NULL,
    display_order INT          NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_analysis   ON analysis_results(analysis_id, display_order);
CREATE INDEX IF NOT EXISTS idx_analysis_results_enterprise ON analysis_results(enterprise_id, created_at DESC);

-- ============================================================
-- GOLD VIEWS
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
    COUNT(DISTINCT ar.analysis_id)                                          AS analysis_count,
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
    e.name                                                                       AS enterprise_name,
    COUNT(DISTINCT pr.run_id)                                                    AS total_pipeline_runs,
    COUNT(DISTINCT pr.run_id) FILTER (WHERE pr.created_at >= NOW() - INTERVAL '30 days') AS runs_last_30d,
    COUNT(DISTINCT ar.analysis_id)                                               AS total_analyses,
    AVG(pr.quality_score) FILTER (WHERE pr.quality_score IS NOT NULL)            AS avg_quality_score,
    MAX(pr.created_at)                                                           AS last_upload_at
FROM enterprises e
LEFT JOIN pipeline_runs pr ON pr.enterprise_id = e.enterprise_id
LEFT JOIN analysis_runs ar ON ar.run_id        = pr.run_id
GROUP BY e.enterprise_id, e.name;
