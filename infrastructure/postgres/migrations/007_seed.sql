-- Migration 007: Seed data + decision_outcomes table

-- ============================================================
-- DECISION OUTCOMES (calibration feedback for audit decisions)
-- ============================================================
CREATE TABLE IF NOT EXISTS decision_outcomes (
    outcome_id    UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id   UUID         NOT NULL REFERENCES decision_audit_log(decision_id) ON DELETE CASCADE,
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    was_correct   BOOLEAN      NOT NULL,
    actual_value  TEXT,
    feedback_by   UUID         REFERENCES enterprise_users(user_id) ON DELETE SET NULL,
    feedback_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_outcomes_decision   ON decision_outcomes(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_enterprise ON decision_outcomes(enterprise_id, feedback_at DESC);

ALTER TABLE decision_outcomes ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'decision_outcomes' AND policyname = 'tenant_decision_outcomes') THEN
        CREATE POLICY tenant_decision_outcomes ON decision_outcomes
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE decision_outcomes FORCE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON decision_outcomes TO kaori_app;

-- ============================================================
-- SEED: Default workspace + enterprise + admin user
-- Safe to re-run (ON CONFLICT DO NOTHING throughout)
-- ============================================================
DO $$
DECLARE
    v_workspace_id  UUID := '00000000-0000-0000-0000-000000000010';
    v_enterprise_id UUID := '00000000-0000-0000-0000-000000000001';
    v_user_id       UUID := '00000000-0000-0000-0000-000000000002';
BEGIN
    -- Ensure plan exists (uses actual columns from 001_init.sql schema)
    INSERT INTO subscription_plans (plan_code, display_name, monthly_quota, price_vnd)
    VALUES ('TRIAL', 'Trial (free)', 100, 0)
    ON CONFLICT (plan_code) DO NOTHING;

    -- Default workspace
    INSERT INTO workspaces (workspace_id, name, plan_code, status)
    VALUES (v_workspace_id, 'Kaori Dev Workspace', 'TRIAL', 'active')
    ON CONFLICT (workspace_id) DO NOTHING;

    -- Default enterprise
    INSERT INTO enterprises (enterprise_id, workspace_id, name, status)
    VALUES (v_enterprise_id, v_workspace_id, 'Kaori Dev', 'active')
    ON CONFLICT (enterprise_id) DO NOTHING;

    -- Default admin user
    -- Password: Admin@kaori1 → bcrypt hash (cost 12)
    -- IMPORTANT: Change on first login in production
    INSERT INTO enterprise_users
        (user_id, enterprise_id, email, full_name, password_hash, role, status)
    VALUES (
        v_user_id,
        v_enterprise_id,
        'admin@kaori.local',
        'Kaori Admin',
        '$2a$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQyCjfNrqh.W7RQkXJ5TgMf7G',
        'MANAGER',
        'active'
    )
    ON CONFLICT (enterprise_id, email) DO NOTHING;
END $$;
