-- Migration 004: ETL run logging + observability

-- ============================================================
-- ETL RUN LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS etl_run_log (
    id            BIGSERIAL    PRIMARY KEY,
    enterprise_id UUID         REFERENCES enterprises(enterprise_id) ON DELETE SET NULL,
    run_id        UUID         REFERENCES pipeline_runs(run_id) ON DELETE SET NULL,
    script_name   VARCHAR(200) NOT NULL,
    status        VARCHAR(20)  NOT NULL CHECK (status IN ('start','success','warning','error')),
    rows_inserted INT,
    rows_updated  INT,
    rows_skipped  INT,
    message       TEXT,
    duration_ms   INT,
    metadata      JSONB        NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_etl_run_log_enterprise ON etl_run_log(enterprise_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_etl_run_log_run        ON etl_run_log(run_id);
CREATE INDEX IF NOT EXISTS idx_etl_run_log_status     ON etl_run_log(status, created_at DESC);

-- ============================================================
-- API REQUEST LOG (partitioned by month)
-- ============================================================
CREATE TABLE IF NOT EXISTS api_request_log (
    request_id    UUID         NOT NULL DEFAULT uuid_generate_v4(),
    enterprise_id UUID         REFERENCES enterprises(enterprise_id) ON DELETE SET NULL,
    user_id       UUID         REFERENCES enterprise_users(user_id) ON DELETE SET NULL,
    trace_id      UUID,
    method        VARCHAR(10)  NOT NULL,
    path          VARCHAR(500) NOT NULL,
    status_code   INT          NOT NULL,
    duration_ms   INT,
    request_size  INT,
    response_size INT,
    ip_address    INET,
    user_agent    TEXT,
    logged_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (request_id, logged_at)
) PARTITION BY RANGE (logged_at);

CREATE TABLE IF NOT EXISTS api_request_log_2026_04 PARTITION OF api_request_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS api_request_log_2026_05 PARTITION OF api_request_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS api_request_log_2026_06 PARTITION OF api_request_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX IF NOT EXISTS idx_api_log_enterprise ON api_request_log(enterprise_id, logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_log_trace      ON api_request_log(trace_id);
