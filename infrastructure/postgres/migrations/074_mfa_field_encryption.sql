-- =====================================================================
-- 074_mfa_field_encryption.sql
--
-- P2-S25 D1 — MFA TOTP + per-tenant field-level encryption tables.
--
-- 3 tables:
--   mfa_secrets         — per-user TOTP secret (AES-GCM encrypted at rest)
--   mfa_backup_codes    — one-time recovery codes (SHA-256 hashed)
--   tenant_field_keys   — per-tenant AES-256 key reference (Vault path
--                          in prod; env-key value in dev)
--
-- Design choices
-- --------------
-- - mfa_secrets.user_id is PK (no surrogate). One secret per user;
--   re-enroll overwrites. Avoids stale-secret accumulation.
-- - secret_enc is base64(IV(12B) || GCM_ciphertext(secret_bytes(20B))).
--   Same wire shape as auth-service TotpService for compatibility.
-- - enabled flag separates enrollment-in-progress (secret stored but
--   not yet verified) from active. UX flow:
--     POST /enroll → secret stored, enabled=FALSE
--     POST /verify  → if code OK, set enabled=TRUE
-- - mfa_backup_codes are pre-issued during /enroll. SHA-256 hash
--   stored (NOT plaintext). Each code single-use via used_at flip.
-- - tenant_field_keys: ONE active key per tenant + UNIQUE constraint.
--   key_ref is opaque to the DB — service-side wraps via
--   shared/crypto.unwrap_key(). version supports key rotation —
--   ciphertext columns carry the version they were encrypted with.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on all 3 tables.
-- K-5: secret_enc at REST is encrypted (defense-in-depth — RLS +
--      encryption both required for compliance audit).
-- K-18: tenant_field_keys.key_ref points to Vault path Phase 2+.
--       Dev profile uses inline key (insecure but transparent).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS mfa_secrets (
    user_id                  UUID         PRIMARY KEY,
    enterprise_id            UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    secret_enc               TEXT         NOT NULL,
    enabled                  BOOLEAN      NOT NULL DEFAULT FALSE,
    enrolled_at              TIMESTAMPTZ,
    last_verified_at         TIMESTAMPTZ,
    backup_codes_remaining   INTEGER      NOT NULL DEFAULT 0,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_mfa_backup_codes_nonneg CHECK (backup_codes_remaining >= 0)
);

CREATE INDEX IF NOT EXISTS idx_mfa_secrets_enabled
    ON mfa_secrets(enterprise_id, enabled)
    WHERE enabled = TRUE;


CREATE TABLE IF NOT EXISTS mfa_backup_codes (
    code_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID         NOT NULL REFERENCES mfa_secrets(user_id) ON DELETE CASCADE,
    enterprise_id  UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    code_hash      VARCHAR(128) NOT NULL,
    used_at        TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mfa_backup_user_active
    ON mfa_backup_codes(user_id)
    WHERE used_at IS NULL;


CREATE TABLE IF NOT EXISTS tenant_field_keys (
    key_id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id  UUID         NOT NULL UNIQUE REFERENCES enterprises(enterprise_id),
    key_ref        TEXT         NOT NULL,
    version        INTEGER      NOT NULL DEFAULT 1,
    rotated_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_tfk_version_pos CHECK (version > 0)
);


COMMENT ON TABLE mfa_secrets IS
    'P2-S25 D2 (P2-AUTH-002) — per-user TOTP secret. AES-GCM encrypted '
    'at rest. enabled=FALSE until first /verify succeeds.';
COMMENT ON COLUMN mfa_secrets.secret_enc IS
    'base64(IV(12B) || GCM_ciphertext(20-byte_secret)). Same wire shape '
    'as auth-service TotpService for cross-service interop.';
COMMENT ON TABLE mfa_backup_codes IS
    'P2-S25 D2 — single-use recovery codes. SHA-256 hashed; plaintext '
    'shown to user ONCE during /enroll. Mark used via used_at flip.';
COMMENT ON TABLE tenant_field_keys IS
    'P2-S25 D3 (P2-ENC-001) — per-tenant AES-256 key reference. '
    'key_ref is Vault path in prod (K-18); inline base64 key in dev.';

COMMIT;
