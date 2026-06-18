-- Migration 013: Disambiguate admin_sessions revoke causes
--
-- Adds:
--   - admin_sessions.revoke_reason : enum-like text column populated when a
--     row is soft-revoked. Distinguishes manual revoke (Module 3 UI) from
--     the new automatic timeouts coming with Batch 3.1.a:
--
--       'logout'            — user pressed sign out
--       'manual'            — user clicked "Thu hồi" on /platform/security/sessions
--       'idle_timeout'      — no activity for 30 minutes (kaori.session.idle-timeout-seconds)
--       'absolute_timeout'  — session older than 24 hours (kaori.session.absolute-timeout-seconds)
--       'password_reset'    — admin reset their password (force re-auth)
--
-- Why a column instead of an event log: revoke is the soft-delete state.
-- Knowing *why* the row was revoked is part of the row's terminal state and
-- is read by the audit emitter + the UI ("Đã hết phiên do không hoạt động"
-- vs "Đã đăng xuất"). An event log would require a JOIN on every list call.

BEGIN;

ALTER TABLE admin_sessions
    ADD COLUMN IF NOT EXISTS revoke_reason VARCHAR(40);

COMMENT ON COLUMN admin_sessions.revoke_reason IS
    'NULL while session is active; one of logout/manual/idle_timeout/absolute_timeout/password_reset on revoke. '
    'Populated atomically with revoked_at by the revoking writer.';

COMMIT;
