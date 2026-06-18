-- Migration 011: Platform admin management (F-010) + workspace audit log (F-008 expansion)
--
-- Creates:
--   - platform_admins                    : SUPER_ADMIN / ADMIN / SUPPORT users (P1 portal).
--                                           Distinct from enterprise_users (P2) — no enterprise_id,
--                                           supports MFA, lifecycle: invited → activated.
--   - platform_admin_password_resets     : reset-token table mirroring password_reset_tokens
--                                           (which is FK-tied to enterprise_users and not reusable).
--   - workspace_audit_log                : append-only event log for workspace + member actions
--                                           shown on /platform/workspaces/{id}/audit. Distinct from
--                                           decision_audit_log (which is AI-decision specific, K-6).
--
-- Why a separate platform_admins table (not extending enterprise_users):
--   - enterprise_users.role CHECK constraint is locked to MANAGER/OPERATOR/ANALYST/VIEWER.
--   - enterprise_users.enterprise_id is NOT NULL — platform admins belong to no enterprise.
--   - MFA + invite flow lives only on P1; bolting fields onto enterprise_users would
--     pollute the enterprise (P2) data model.
--
-- Why a separate workspace_audit_log (not decision_audit_log):
--   - decision_audit_log mandates run_id (pipeline-scoped) and confidence/method (AI fields).
--   - workspace_audit_log captures admin actions that have no AI semantics.

BEGIN;

-- =========================================================================
-- 1. platform_admins
-- =========================================================================
CREATE TABLE IF NOT EXISTS platform_admins (
    admin_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(254)    NOT NULL UNIQUE,
    password_hash   VARCHAR(100),                                       -- nullable until first activate
    full_name       VARCHAR(200)    NOT NULL,
    role            VARCHAR(20)     NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    mfa_enabled     BOOLEAN         NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    invited_by      UUID            REFERENCES platform_admins(admin_id),
    invited_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    activated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_platform_role CHECK (role IN ('SUPER_ADMIN', 'ADMIN', 'SUPPORT'))
);

CREATE INDEX IF NOT EXISTS idx_platform_admins_email ON platform_admins(email);
CREATE INDEX IF NOT EXISTS idx_platform_admins_role  ON platform_admins(role);

-- =========================================================================
-- 2. platform_admin_password_resets
-- =========================================================================
CREATE TABLE IF NOT EXISTS platform_admin_password_resets (
    token_id     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id     UUID         NOT NULL REFERENCES platform_admins(admin_id),
    token_hash   VARCHAR(64)  NOT NULL UNIQUE,
    expires_at   TIMESTAMPTZ  NOT NULL,
    used_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_platform_reset_hash   ON platform_admin_password_resets(token_hash);
CREATE INDEX IF NOT EXISTS idx_platform_reset_expiry ON platform_admin_password_resets(expires_at) WHERE used_at IS NULL;

-- =========================================================================
-- 3. workspace_audit_log (append-only, K-2 spirit)
-- =========================================================================
CREATE TABLE IF NOT EXISTS workspace_audit_log (
    event_id     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID         NOT NULL REFERENCES workspaces(workspace_id),
    event_type   VARCHAR(80)  NOT NULL,                  -- e.g. 'workspace.updated', 'member.invited'
    actor_email  VARCHAR(254),                           -- nullable for system events
    actor_role   VARCHAR(40),                            -- platform OR enterprise role label
    resource     VARCHAR(200),                           -- short label (target email, plan code, etc.)
    detail       TEXT,                                   -- free-form
    ip_address   VARCHAR(64),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_audit_ws    ON workspace_audit_log(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workspace_audit_type  ON workspace_audit_log(event_type);

-- Append-only: block UPDATE/DELETE via PG rules (mirrors bronze_rows / decision_audit_log pattern).
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'workspace_audit_log' AND rulename = 'workspace_audit_no_update'
    ) THEN
        CREATE RULE workspace_audit_no_update AS ON UPDATE TO workspace_audit_log DO INSTEAD NOTHING;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'workspace_audit_log' AND rulename = 'workspace_audit_no_delete'
    ) THEN
        CREATE RULE workspace_audit_no_delete AS ON DELETE TO workspace_audit_log DO INSTEAD NOTHING;
    END IF;
END $$;

-- =========================================================================
-- Grants — defaults from migration 008 cover SELECT/INSERT/UPDATE.
-- platform_admins needs DELETE for hard-removes (F-010 doesn't soft-delete admins;
-- deactivate flips is_active=false instead, but DELETE is allowed for cleanup).
-- =========================================================================
GRANT DELETE ON platform_admins                  TO kaori_app;
GRANT DELETE ON platform_admin_password_resets   TO kaori_app;
-- workspace_audit_log: SELECT/INSERT only (UPDATE/DELETE blocked by rules above)

COMMIT;
