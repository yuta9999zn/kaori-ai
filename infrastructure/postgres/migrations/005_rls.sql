-- Migration 005: Row-Level Security (K-1: multi-tenant isolation)

ALTER TABLE pipeline_runs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE bronze_files           ENABLE ROW LEVEL SECURITY;
ALTER TABLE bronze_rows            ENABLE ROW LEVEL SECURITY;
ALTER TABLE canonical_schemas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_audit_log     ENABLE ROW LEVEL SECURITY;
ALTER TABLE silver_rows            ENABLE ROW LEVEL SECURITY;
ALTER TABLE cleaning_rules_applied ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results       ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_users       ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_monthly_billing ENABLE ROW LEVEL SECURITY;
ALTER TABLE etl_run_log            ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kaori_app') THEN
        CREATE ROLE kaori_app LOGIN PASSWORD 'kaori_app_password';
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO kaori_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO kaori_app;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'pipeline_runs' AND policyname = 'tenant_pipeline_runs') THEN
        CREATE POLICY tenant_pipeline_runs ON pipeline_runs
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'bronze_files' AND policyname = 'tenant_bronze_files') THEN
        CREATE POLICY tenant_bronze_files ON bronze_files
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'bronze_rows' AND policyname = 'tenant_bronze_rows') THEN
        CREATE POLICY tenant_bronze_rows ON bronze_rows
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'canonical_schemas' AND policyname = 'tenant_canonical_schemas') THEN
        CREATE POLICY tenant_canonical_schemas ON canonical_schemas
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'decision_audit_log' AND policyname = 'tenant_decision_audit') THEN
        CREATE POLICY tenant_decision_audit ON decision_audit_log
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'silver_rows' AND policyname = 'tenant_silver_rows') THEN
        CREATE POLICY tenant_silver_rows ON silver_rows
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'cleaning_rules_applied' AND policyname = 'tenant_cleaning_rules') THEN
        CREATE POLICY tenant_cleaning_rules ON cleaning_rules_applied
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

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

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'enterprise_users' AND policyname = 'tenant_enterprise_users') THEN
        CREATE POLICY tenant_enterprise_users ON enterprise_users
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'enterprise_monthly_billing' AND policyname = 'tenant_billing') THEN
        CREATE POLICY tenant_billing ON enterprise_monthly_billing
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'etl_run_log' AND policyname = 'tenant_etl_log') THEN
        CREATE POLICY tenant_etl_log ON etl_run_log
            USING (enterprise_id IS NULL
                OR enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE pipeline_runs          FORCE ROW LEVEL SECURITY;
ALTER TABLE bronze_files           FORCE ROW LEVEL SECURITY;
ALTER TABLE bronze_rows            FORCE ROW LEVEL SECURITY;
ALTER TABLE canonical_schemas      FORCE ROW LEVEL SECURITY;
ALTER TABLE decision_audit_log     FORCE ROW LEVEL SECURITY;
ALTER TABLE silver_rows            FORCE ROW LEVEL SECURITY;
ALTER TABLE cleaning_rules_applied FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs          FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_results       FORCE ROW LEVEL SECURITY;
ALTER TABLE enterprise_users       FORCE ROW LEVEL SECURITY;
ALTER TABLE enterprise_monthly_billing FORCE ROW LEVEL SECURITY;
