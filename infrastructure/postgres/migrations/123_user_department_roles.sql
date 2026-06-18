-- =====================================================================
-- 123_user_department_roles.sql — Tier-3 Phase 2 (ADR-0037): functional RBAC
--
-- The 4 global roles (MANAGER/OPERATOR/ANALYST/VIEWER) stay untouched. This adds
-- the per-department FUNCTIONAL role a user plays in workflows
-- (executor/reviewer/approver/dept_manager/admin) — N:M (a user can be approver
-- in Finance and reviewer in Legal). Plus a per-step assigned_role on nodes.
-- The permission matrix (role × action) lives in code (shared/doc_rbac.py), not
-- a table — it is policy, evaluated cheaply.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_department_roles (
    id              UUID        PRIMARY KEY DEFAULT gen_uuid_v7(),
    enterprise_id   UUID        NOT NULL,
    user_id         UUID        NOT NULL,
    department_id   UUID        NOT NULL,
    functional_role VARCHAR(20) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_udr_role CHECK (functional_role IN
        ('executor', 'reviewer', 'approver', 'dept_manager', 'admin')),
    CONSTRAINT uq_udr UNIQUE (user_id, department_id, functional_role)
);
CREATE INDEX IF NOT EXISTS idx_udr_user ON user_department_roles(enterprise_id, user_id);
CREATE INDEX IF NOT EXISTS idx_udr_dept ON user_department_roles(enterprise_id, department_id);

ALTER TABLE user_department_roles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS isolation_user_department_roles ON user_department_roles;
CREATE POLICY isolation_user_department_roles ON user_department_roles
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

-- Per-step functional role the executor/reviewer/approver who runs this node holds.
ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS assigned_role VARCHAR(20);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_node_assigned_role') THEN
        ALTER TABLE workflow_nodes ADD CONSTRAINT chk_node_assigned_role
            CHECK (assigned_role IS NULL OR assigned_role IN
                ('executor', 'reviewer', 'approver', 'dept_manager', 'admin'));
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON user_department_roles TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE user_department_roles IS
    'ADR-0037 Phase 2 — per-department functional role (executor/reviewer/approver/'
    'dept_manager/admin), N:M. Global 4 roles unchanged; matrix is code-side.';

COMMIT;
