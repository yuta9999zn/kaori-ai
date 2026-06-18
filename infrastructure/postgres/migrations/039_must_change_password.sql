-- 039_must_change_password.sql
-- P1-S1 (P2-M20-007) — first-login force-change-password flow.
--
-- When EnterpriseUserService.invite() creates an invited user, it sets
-- this flag so the user MUST change their password on first login. The
-- flag is cleared on successful password change (via /auth/reset-password
-- using the email-token, or /auth/users/me/change-password while logged in).
--
-- Existing users get FALSE (default) — they don't suddenly need to rotate.
-- Only newly invited users from now on start with TRUE.
--
-- Why a column instead of a separate state machine: this is a single
-- boolean flip; a state machine table would be over-engineering. Future
-- password-policy work (mandatory rotation every N days) might reuse the
-- same flag — the consumer reads must_change_password=TRUE the same way
-- regardless of why it's set.

ALTER TABLE enterprise_users
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN enterprise_users.must_change_password IS
    'P1-S1 / P2-M20-007 — invited users start with TRUE; cleared to FALSE on first password change. Login response carries this flag so FE can route to a forced-change screen.';
