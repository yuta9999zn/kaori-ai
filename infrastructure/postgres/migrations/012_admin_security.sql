-- Migration 012: Platform admin security — TOTP MFA + active session tracking
--
-- Adds:
--   - platform_admins.mfa_secret_enc : AES-GCM ciphertext of the TOTP secret
--                                       (Base64). Null until the admin starts
--                                       the enable flow. mfa_enabled (already
--                                       in 011) is flipped to true only after
--                                       the verify step succeeds.
--   - admin_sessions                 : one row per active P1 sign-in. Soft-
--                                       revoked via revoked_at; never deleted.
--                                       Surface for the /security/sessions UI.
--
-- Why a new table for sessions (instead of a JWT denylist):
--   The platform JWT path is short-lived; what UX requires is "see and kick out
--   other tabs / devices", which needs a per-admin server-side row. Pure JWT
--   denylists store only revocation, not the inventory.

BEGIN;

-- =========================================================================
-- 1. platform_admins.mfa_secret_enc
-- =========================================================================
ALTER TABLE platform_admins
    ADD COLUMN IF NOT EXISTS mfa_secret_enc VARCHAR(400);

COMMENT ON COLUMN platform_admins.mfa_secret_enc IS
    'Base64 of (12-byte IV || AES-256-GCM ciphertext of the TOTP secret). '
    'Key from KAORI_MFA_KEY env var (Base64-encoded 32 bytes). '
    'Null until /security/mfa/enable is called. Cleared on disable.';

-- =========================================================================
-- 2. admin_sessions
-- =========================================================================
CREATE TABLE IF NOT EXISTS admin_sessions (
    session_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id       UUID            NOT NULL REFERENCES platform_admins(admin_id) ON DELETE CASCADE,
    ip_address     VARCHAR(64),
    user_agent     VARCHAR(500),
    device_label   VARCHAR(120),                 -- best-effort UA → "Chrome on macOS"
    created_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    revoked_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_admin_active
    ON admin_sessions (admin_id, last_active_at DESC)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_admin_sessions_admin
    ON admin_sessions (admin_id);

-- =========================================================================
-- Grants — kaori_app needs the same SELECT/INSERT/UPDATE the other admin
-- tables already have (default from migration 008 covers DML). DELETE not
-- granted: sessions are soft-revoked, never hard-deleted.
-- =========================================================================
-- (no explicit GRANTs needed — covered by migration 008's blanket grant)

COMMIT;
