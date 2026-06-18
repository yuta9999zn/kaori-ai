-- Migration 002: Pipeline Bronze layer
-- Generic file ingestion tables (no domain-specific columns)

-- ============================================================
-- PIPELINE RUNS (one per file upload)
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    enterprise_id       UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    uploaded_by         UUID         NOT NULL REFERENCES enterprise_users(user_id),
    filename            VARCHAR(500) NOT NULL,
    original_size_bytes BIGINT       NOT NULL,
    file_sha256         VARCHAR(64)  NOT NULL,
    mime_type           VARCHAR(100),
    status              VARCHAR(30)  NOT NULL DEFAULT 'uploading'
                        CHECK (status IN (
                            'uploading','bronze_complete','schema_review',
                            'silver_complete','analyzing','analysis_complete',
                            'failed','cancelled'
                        )),
    error_message       TEXT,
    detected_language   VARCHAR(10),
    sheet_count         INT          NOT NULL DEFAULT 1,
    row_count_bronze    INT,
    row_count_silver    INT,
    quality_score       NUMERIC(5,4),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_enterprise  ON pipeline_runs(enterprise_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_sha256      ON pipeline_runs(enterprise_id, file_sha256);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_runs_idempotent ON pipeline_runs(enterprise_id, file_sha256)
    WHERE status NOT IN ('failed','cancelled');

-- ============================================================
-- BRONZE FILES (per-sheet metadata)
-- ============================================================
CREATE TABLE IF NOT EXISTS bronze_files (
    file_id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id           UUID         NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    enterprise_id    UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    sheet_name       VARCHAR(200),
    sheet_index      INT          NOT NULL DEFAULT 0,
    detected_purpose VARCHAR(50),
    detected_language VARCHAR(10),
    header_row       INT          NOT NULL DEFAULT 0,
    row_count        INT          NOT NULL DEFAULT 0,
    col_count        INT          NOT NULL DEFAULT 0,
    file_format      VARCHAR(20)  NOT NULL,
    metadata         JSONB        NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bronze_files_run        ON bronze_files(run_id);
CREATE INDEX IF NOT EXISTS idx_bronze_files_enterprise ON bronze_files(enterprise_id);

-- ============================================================
-- BRONZE ROWS (raw data — append-only, never UPDATE/DELETE)
-- K-2: Immutable bronze layer
-- ============================================================
CREATE TABLE IF NOT EXISTS bronze_rows (
    row_id        BIGSERIAL    PRIMARY KEY,
    file_id       UUID         NOT NULL REFERENCES bronze_files(file_id) ON DELETE CASCADE,
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    row_index     INT          NOT NULL,
    raw_data      JSONB        NOT NULL,
    row_hash      VARCHAR(64),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'bronze_rows' AND rulename = 'bronze_rows_no_update'
    ) THEN
        CREATE RULE bronze_rows_no_update AS ON UPDATE TO bronze_rows DO INSTEAD NOTHING;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'bronze_rows' AND rulename = 'bronze_rows_no_delete'
    ) THEN
        CREATE RULE bronze_rows_no_delete AS ON DELETE TO bronze_rows DO INSTEAD NOTHING;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_bronze_rows_file       ON bronze_rows(file_id);
CREATE INDEX IF NOT EXISTS idx_bronze_rows_enterprise ON bronze_rows(enterprise_id, created_at DESC);

-- ============================================================
-- CANONICAL SCHEMA (column mapping results)
-- ============================================================
CREATE TABLE IF NOT EXISTS canonical_schemas (
    schema_id         UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id           UUID         NOT NULL REFERENCES bronze_files(file_id) ON DELETE CASCADE,
    enterprise_id     UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    source_column     VARCHAR(500) NOT NULL,
    canonical_name    VARCHAR(100) NOT NULL,
    data_type         VARCHAR(30)  NOT NULL DEFAULT 'text',
    confidence        NUMERIC(5,4) NOT NULL,
    method            VARCHAR(30)  NOT NULL,
    uncertainty_flags TEXT[]       NOT NULL DEFAULT '{}',
    user_confirmed    BOOLEAN      NOT NULL DEFAULT FALSE,
    user_override     VARCHAR(100),
    sample_values     TEXT[]       NOT NULL DEFAULT '{}',
    null_rate         NUMERIC(5,4),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_canonical_schemas_file       ON canonical_schemas(file_id);
CREATE INDEX IF NOT EXISTS idx_canonical_schemas_enterprise ON canonical_schemas(enterprise_id);

-- ============================================================
-- DECISION AUDIT LOG (K-6: every automated decision logged)
-- ============================================================
CREATE TABLE IF NOT EXISTS decision_audit_log (
    decision_id        UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    enterprise_id      UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id             UUID         REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    decision_type      VARCHAR(50)  NOT NULL,
    subject            TEXT         NOT NULL,
    chosen_value       TEXT         NOT NULL,
    confidence         NUMERIC(5,4) NOT NULL,
    method             VARCHAR(50)  NOT NULL,
    alternatives       JSONB        NOT NULL DEFAULT '[]',
    uncertainty_flags  TEXT[]       NOT NULL DEFAULT '{}',
    reasoning          TEXT,
    needs_user_confirm BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'decision_audit_log' AND rulename = 'decision_audit_no_update'
    ) THEN
        CREATE RULE decision_audit_no_update AS ON UPDATE TO decision_audit_log DO INSTEAD NOTHING;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'decision_audit_log' AND rulename = 'decision_audit_no_delete'
    ) THEN
        CREATE RULE decision_audit_no_delete AS ON DELETE TO decision_audit_log DO INSTEAD NOTHING;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_decision_audit_run        ON decision_audit_log(run_id);
CREATE INDEX IF NOT EXISTS idx_decision_audit_enterprise ON decision_audit_log(enterprise_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decision_audit_type       ON decision_audit_log(decision_type, created_at DESC);
