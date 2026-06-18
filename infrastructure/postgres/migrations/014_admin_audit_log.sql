-- Migration 014: Platform admin audit log + actor_id on workspace_audit_log
--
-- Adds:
--   - platform_admin_audit_log : append-only audit feed for events scoped to
--                                 a platform_admin (no workspace_id). Mirrors
--                                 the workspace_audit_log shape so the same
--                                 "actor / event_type / resource / detail /
--                                 ip_address" reading pattern works on both.
--                                 Surfaces the MFA lifecycle (initiated /
--                                 enabled / verified / verify_failed) and the
--                                 session revoke lifecycle (manual / logout /
--                                 idle_timeout / absolute_timeout / password_reset).
--
--   - workspace_audit_log.actor_id : nullable UUID column so we can record the
--                                 acting platform_admin's ID structurally
--                                 (instead of email-only). Backfill is not
--                                 attempted — historic rows stay NULL.
--
-- Why a separate table instead of expanding workspace_audit_log:
--   workspace_audit_log.workspace_id is NOT NULL with an FK. Platform-scoped
--   events have no workspace context, so we either (a) make workspace_id
--   nullable + add an admin_id column + a CHECK constraint — invasive, alters
--   queries silently — or (b) duplicate the table shape and key on admin_id.
--   Option (b) is what F-008 reads stay safe with: the workspace audit page
--   continues to read from a single, fully-populated `workspace_id` column.
--
-- Why append-only rules: same reasoning as workspace_audit_log (migration 011)
--   and bronze_rows — a tampered audit log is worthless. UPDATE / DELETE are
--   blocked at the RDBMS layer so a future bug or rogue admin cannot rewrite
--   history.

BEGIN;

-- =========================================================================
-- 1. workspace_audit_log.actor_id  (additive — column nullable)
-- =========================================================================
ALTER TABLE workspace_audit_log
    ADD COLUMN IF NOT EXISTS actor_id UUID;

COMMENT ON COLUMN workspace_audit_log.actor_id IS
    'UUID of the acting principal (platform_admin.admin_id or enterprise_users.user_id). '
    'Nullable for system events and for historic rows written before migration 014.';

-- =========================================================================
-- 2. platform_admin_audit_log
-- =========================================================================
CREATE TABLE IF NOT EXISTS platform_admin_audit_log (
    event_id     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id     UUID         NOT NULL REFERENCES platform_admins(admin_id),
    event_type   VARCHAR(80)  NOT NULL,                  -- e.g. admin.mfa.enabled
    actor_id     UUID,                                   -- nullable; usually = admin_id, but
                                                          -- another admin's invite-driven action
                                                          -- targets a different admin row.
    actor_email  VARCHAR(254),
    actor_role   VARCHAR(40),
    resource     VARCHAR(200),                           -- short label (session_id, label, etc.)
    detail       TEXT,                                   -- free-form: "reason=idle_timeout",
                                                          -- "rate_limited=true", etc.
    ip_address   VARCHAR(64),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pa_audit_admin    ON platform_admin_audit_log(admin_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pa_audit_type     ON platform_admin_audit_log(event_type);

-- Append-only: block UPDATE / DELETE at the rule layer. Mirrors
-- workspace_audit_log (migration 011) and bronze_rows (migration 001).
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules
        WHERE tablename = 'platform_admin_audit_log' AND rulename = 'pa_audit_no_update'
    ) THEN
        CREATE RULE pa_audit_no_update AS ON UPDATE TO platform_admin_audit_log DO INSTEAD NOTHING;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules
        WHERE tablename = 'platform_admin_audit_log' AND rulename = 'pa_audit_no_delete'
    ) THEN
        CREATE RULE pa_audit_no_delete AS ON DELETE TO platform_admin_audit_log DO INSTEAD NOTHING;
    END IF;
END $$;

COMMIT;
