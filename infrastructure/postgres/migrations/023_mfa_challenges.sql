-- Migration 023: mfa_challenges — Phase 2 error-handling B3 PR #8 (#10 auth security).
--
-- Why
-- ===
-- Today /auth/platform/login returns a full session JWT regardless of the
-- admin's mfa_enabled flag — the flag rides along on the response so the
-- FE knows "next time you should challenge", but no challenge is actually
-- issued (PlatformAuthService class doc explicitly flags this as a TODO
-- for the next hardening pass). That means a leaked password is enough
-- to access the platform even when MFA is enabled.
--
-- This migration adds the durable side of the 2-step flow:
--   1. POST /auth/platform/login (existing) — when admin.mfa_enabled=true,
--      create one row here, mint a short-lived `mfa_challenge_token` JWT
--      that carries challenge_id, return {mfa_required:true, ...}. NO
--      access/refresh tokens are issued at this step.
--   2. POST /auth/platform/mfa/verify (new) — accepts challenge_token + a
--      6-digit TOTP code. Look up the row by hash, check expires_at +
--      used_at, verify code via TotpService, on success flip used_at and
--      return the real {access_token, refresh_token, ...}.
--
-- Why a row instead of pure-JWT challenge state:
--   * One-time semantics — used_at is the source of truth that prevents
--     replay. The challenge JWT alone cannot enforce one-time without
--     external state (Redis SETNX would work but DB row gives a queryable
--     audit trail and is consistent with how MFA secrets already live in
--     Postgres).
--   * Per-challenge attempts counter — we lock at 5 invalid codes per
--     challenge, on top of the per-admin 15-minute lockout that
--     AdminSecurityService.verifyMfa already maintains in Redis.
--   * Forensics — `SELECT * FROM mfa_challenges WHERE admin_id=… ORDER BY
--     created_at DESC LIMIT 50` answers "what did this admin do at login
--     yesterday?" in one query.
--
-- Why challenge_token_hash, not the token itself:
--   The JWT is signed and short-lived; storing the raw token would leak
--   the credential on a DB dump. SHA-256(token) is enough — the verify
--   endpoint hashes the presented JWT and looks it up. Mirrors the
--   pattern already used by password_reset_tokens (001) and
--   platform_admin_password_resets (011).
--
-- Reversibility
-- =============
--   DROP TABLE mfa_challenges;
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mfa_challenges (
    challenge_id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id              UUID         NOT NULL REFERENCES platform_admins(admin_id) ON DELETE CASCADE,
    challenge_token_hash  VARCHAR(64)  NOT NULL UNIQUE,
    expires_at            TIMESTAMPTZ  NOT NULL,
    used_at               TIMESTAMPTZ,
    attempts              INTEGER      NOT NULL DEFAULT 0,
    ip_address            VARCHAR(64),
    user_agent            VARCHAR(500),
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_mfa_challenge_attempts_nonneg CHECK (attempts >= 0)
);

-- Verify endpoint hits the table by token-hash → unique-by-hash lookup
-- already covered by the UNIQUE constraint on challenge_token_hash.

-- Sweeper / "show me this admin's recent attempts" — partial DESC index.
CREATE INDEX IF NOT EXISTS idx_mfa_challenges_admin_recent
    ON mfa_challenges(admin_id, created_at DESC);

-- Find unused-and-not-yet-expired rows (cron cleanup, or duplicate-active
-- defence at insert). Partial keeps the index size O(active) regardless
-- of how much history accumulates.
CREATE INDEX IF NOT EXISTS idx_mfa_challenges_active
    ON mfa_challenges(expires_at)
    WHERE used_at IS NULL;

COMMENT ON TABLE mfa_challenges IS
    'B3 PR #8 — one-time MFA challenge rows for the 2-step platform admin login. '
    'Created on /auth/platform/login when admin.mfa_enabled=true; used_at is the '
    'one-time-use guard (verify endpoint flips it inside the same transaction as '
    'the success path).';

COMMENT ON COLUMN mfa_challenges.challenge_token_hash IS
    'SHA-256 hex of the challenge JWT presented at /auth/platform/mfa/verify. '
    'Storing the hash, not the token itself, keeps the DB dump safe.';

COMMENT ON COLUMN mfa_challenges.attempts IS
    'Per-challenge invalid-code counter. Distinct from the per-admin Redis '
    'lockout in AdminSecurityService — once attempts >= 5 the row is dead '
    '(used_at gets set with a sentinel so it cannot be retried) but the admin '
    'is still allowed to re-login from scratch (which mints a new challenge).';

-- kaori_app GRANTs come from DEFAULT PRIVILEGES set in 008_kaori_app_grants.sql.

COMMIT;
