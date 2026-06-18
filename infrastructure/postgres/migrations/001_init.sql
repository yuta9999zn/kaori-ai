-- ============================================================
-- Migration 001: Core auth + tenant tables
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Subscription plans
CREATE TABLE IF NOT EXISTS subscription_plans (
    plan_code           VARCHAR(20)     PRIMARY KEY,
    display_name        VARCHAR(100)    NOT NULL,
    monthly_quota       INTEGER         NOT NULL,
    price_vnd           NUMERIC(14,4)   NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

INSERT INTO subscription_plans (plan_code, display_name, monthly_quota, price_vnd)
VALUES
    ('TRIAL',      'Trial (free)',  100,        0),
    ('STARTER',    'Starter',       500,   490000),
    ('BUSINESS',   'Business',     2000,  1490000),
    ('ENTERPRISE', 'Enterprise',  10000,  4990000)
ON CONFLICT DO NOTHING;

-- Workspaces (top-level tenant container)
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200)    NOT NULL,
    plan_code       VARCHAR(20)     NOT NULL REFERENCES subscription_plans(plan_code) DEFAULT 'TRIAL',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Enterprises (organizations within a workspace)
CREATE TABLE IF NOT EXISTS enterprises (
    enterprise_id   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID            NOT NULL REFERENCES workspaces(workspace_id),
    name            VARCHAR(200)    NOT NULL,
    industry        VARCHAR(100),
    timezone        VARCHAR(50)     NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    locale          VARCHAR(10)     NOT NULL DEFAULT 'vi',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enterprises_workspace ON enterprises(workspace_id);

-- Users
CREATE TABLE IF NOT EXISTS enterprise_users (
    user_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id),
    email           VARCHAR(254)    NOT NULL,
    password_hash   VARCHAR(100)    NOT NULL,
    full_name       VARCHAR(200),
    role            VARCHAR(20)     NOT NULL DEFAULT 'VIEWER',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_email_enterprise UNIQUE (enterprise_id, email),
    CONSTRAINT chk_user_role CHECK (role IN ('MANAGER', 'OPERATOR', 'ANALYST', 'VIEWER'))
);

CREATE INDEX IF NOT EXISTS idx_users_enterprise ON enterprise_users(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON enterprise_users(email);

-- Workspace activation keys
CREATE TABLE IF NOT EXISTS workspace_keys (
    key_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID            NOT NULL REFERENCES workspaces(workspace_id),
    key_hash        VARCHAR(64)     NOT NULL UNIQUE,
    label           VARCHAR(100),
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Password reset tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES enterprise_users(user_id),
    token_hash      VARCHAR(64)     NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ     NOT NULL,
    used_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash   ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expiry ON password_reset_tokens(expires_at) WHERE used_at IS NULL;

-- Monthly billing
CREATE TABLE IF NOT EXISTS enterprise_monthly_billing (
    billing_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID            NOT NULL REFERENCES enterprises(enterprise_id),
    billing_month    DATE            NOT NULL,
    unique_customers INTEGER         NOT NULL DEFAULT 0,
    quota            INTEGER         NOT NULL,
    overage_count    INTEGER         NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_billing_enterprise_month UNIQUE (enterprise_id, billing_month)
);

-- Billing summary view
CREATE OR REPLACE VIEW v_billing_summary AS
SELECT
    e.enterprise_id,
    e.name AS enterprise_name,
    sp.plan_code,
    sp.monthly_quota AS quota,
    COALESCE(b.unique_customers, 0) AS current_month_usage,
    ROUND(COALESCE(b.unique_customers, 0)::NUMERIC / NULLIF(sp.monthly_quota, 0) * 100, 2) AS usage_pct
FROM enterprises e
JOIN workspaces w ON w.workspace_id = e.workspace_id
JOIN subscription_plans sp ON sp.plan_code = w.plan_code
LEFT JOIN enterprise_monthly_billing b
    ON b.enterprise_id = e.enterprise_id
    AND b.billing_month = DATE_TRUNC('month', NOW())::DATE;

-- ============================================================
-- Pipeline tables (kept here so foreign keys resolve on init)
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id),
    uploaded_by         UUID            REFERENCES enterprise_users(user_id),
    filename            VARCHAR(500),
    original_size_bytes BIGINT,
    file_sha256         CHAR(64),
    mime_type           VARCHAR(100),
    detected_language   VARCHAR(10),
    sheet_count         INTEGER,
    row_count_bronze    INTEGER,
    row_count_silver    INTEGER,
    quality_score       NUMERIC(5,4),
    status              VARCHAR(30)     NOT NULL DEFAULT 'uploading',
    error_message       TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pipeline_status CHECK (
        status IN ('uploading','bronze_complete','schema_review',
                   'silver_complete','analysis_complete','failed','cancelled')
    )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_enterprise ON pipeline_runs(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_sha256     ON pipeline_runs(enterprise_id, file_sha256);

CREATE TABLE IF NOT EXISTS bronze_files (
    file_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID            NOT NULL REFERENCES pipeline_runs(run_id),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id),
    sheet_name          VARCHAR(200),
    sheet_index         INTEGER         NOT NULL DEFAULT 0,
    detected_purpose    VARCHAR(50),
    detected_language   VARCHAR(10),
    header_row          INTEGER         NOT NULL DEFAULT 0,
    row_count           INTEGER,
    col_count           INTEGER,
    file_format         VARCHAR(20),
    metadata            JSONB           NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- K-2: Bronze rows are append-only (never UPDATE/DELETE)
CREATE TABLE IF NOT EXISTS bronze_rows (
    row_id          BIGSERIAL       PRIMARY KEY,
    file_id         UUID            NOT NULL REFERENCES bronze_files(file_id),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id),
    row_index       INTEGER         NOT NULL,
    raw_data        JSONB           NOT NULL,
    row_hash        CHAR(64),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
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

CREATE INDEX IF NOT EXISTS idx_bronze_rows_file ON bronze_rows(file_id);

-- ============================================================
-- Canonical schema + decision audit
-- ============================================================

CREATE TABLE IF NOT EXISTS canonical_schemas (
    schema_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id         UUID            NOT NULL REFERENCES bronze_files(file_id),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id),
    source_column   VARCHAR(200)    NOT NULL,
    canonical_name  VARCHAR(100)    NOT NULL,
    data_type       VARCHAR(30)     NOT NULL DEFAULT 'text',
    confidence      NUMERIC(5,4)    NOT NULL DEFAULT 0,
    method          VARCHAR(30),
    user_confirmed  BOOLEAN         NOT NULL DEFAULT FALSE,
    user_override   VARCHAR(100),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_canonical_file_col UNIQUE (file_id, source_column)
);

-- K-6: Decision audit log (append-only)
CREATE TABLE IF NOT EXISTS decision_audit_log (
    decision_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID        NOT NULL REFERENCES enterprises(enterprise_id),
    run_id              UUID        REFERENCES pipeline_runs(run_id),
    decision_type       VARCHAR(50) NOT NULL,
    subject             TEXT        NOT NULL,
    chosen_value        TEXT,
    confidence          NUMERIC(5,4),
    method              VARCHAR(50),
    alternatives        JSONB,
    uncertainty_flags   TEXT[],
    llm_provider        VARCHAR(30),
    reasoning           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
CREATE INDEX IF NOT EXISTS idx_decision_audit_enterprise ON decision_audit_log(enterprise_id);

-- ============================================================
-- Analysis runs + results (single-template schema; replaced by 006)
-- ============================================================

CREATE TABLE IF NOT EXISTS analysis_runs (
    analysis_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        NOT NULL REFERENCES pipeline_runs(run_id),
    enterprise_id   UUID        NOT NULL REFERENCES enterprises(enterprise_id),
    template        VARCHAR(50) NOT NULL,
    config          JSONB       NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    model_used      VARCHAR(100),
    llm_provider    VARCHAR(30),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_analysis_status CHECK (
        status IN ('pending','running','complete','failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_run ON analysis_runs(run_id);

CREATE TABLE IF NOT EXISTS analysis_results (
    result_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID        NOT NULL REFERENCES analysis_runs(analysis_id),
    enterprise_id   UUID        NOT NULL REFERENCES enterprises(enterprise_id),
    result_type     VARCHAR(50) NOT NULL,
    chart_kind      VARCHAR(30),
    data_shape      VARCHAR(30),
    payload         JSONB       NOT NULL,
    display_order   INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_analysis ON analysis_results(analysis_id);

-- ============================================================
-- RLS + app role (subset; full policies in 005_rls.sql)
-- ============================================================

ALTER TABLE pipeline_runs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE bronze_files       ENABLE ROW LEVEL SECURITY;
ALTER TABLE bronze_rows        ENABLE ROW LEVEL SECURITY;
ALTER TABLE canonical_schemas  ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results   ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kaori_app') THEN
        CREATE ROLE kaori_app LOGIN PASSWORD 'kaori_app_password';
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO kaori_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kaori_app;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'pipeline_runs' AND policyname = 'enterprise_isolation_pipeline_runs'
    ) THEN
        CREATE POLICY enterprise_isolation_pipeline_runs ON pipeline_runs
            USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'bronze_files' AND policyname = 'enterprise_isolation_bronze_files'
    ) THEN
        CREATE POLICY enterprise_isolation_bronze_files ON bronze_files
            USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'analysis_runs' AND policyname = 'enterprise_isolation_analysis_runs'
    ) THEN
        CREATE POLICY enterprise_isolation_analysis_runs ON analysis_runs
            USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'pipeline_runs' AND policyname = 'admin_bypass_pipeline_runs'
    ) THEN
        CREATE POLICY admin_bypass_pipeline_runs ON pipeline_runs
            USING (current_setting('app.is_admin', TRUE) = 'true');
    END IF;
END $$;

-- ============================================================
-- Observability: ETL run log
-- ============================================================

CREATE TABLE IF NOT EXISTS etl_run_log (
    log_id          BIGSERIAL   PRIMARY KEY,
    enterprise_id   UUID        REFERENCES enterprises(enterprise_id),
    run_id          UUID        REFERENCES pipeline_runs(run_id),
    stage           VARCHAR(30),
    status          VARCHAR(20),
    message         TEXT,
    rows_processed  INTEGER,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_etl_log_run ON etl_run_log(run_id);
