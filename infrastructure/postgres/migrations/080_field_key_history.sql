-- =====================================================================
-- 076_field_key_history.sql
--
-- P2 retro defer item 6 — background re-encrypt worker prerequisite.
--
-- Before this migration, /p2/auth/field-key/rotate (P2-S25 D3)
-- overwrote tenant_field_keys.key_ref in-place: existing ciphertext
-- became permanently undecryptable on rotation (GCM auth tag mismatch
-- under new random key). The endpoint docstring claimed otherwise.
--
-- This migration fixes that by introducing a key-version history
-- table. Rotation now archives the prior key before bumping; the
-- re-encrypt worker walks ciphertext rows + rewrites them under the
-- current version, then marks old versions purged.
--
-- 1 new table + 4 new columns on tenant_field_keys:
--   tenant_field_key_versions   — append-only history of all keys ever
--                                  issued to a tenant (PK: enterprise_id+version)
--   tenant_field_keys.reencrypt_status       — idle | pending | running | completed | failed
--   tenant_field_keys.reencrypt_started_at   — when worker last began
--   tenant_field_keys.reencrypt_completed_at — when worker last finished
--   tenant_field_keys.reencrypt_error        — last error message (truncated)
--
-- Backfill: every existing tenant_field_keys row is mirrored into the
-- history table at its current (enterprise_id, version) so the new
-- decrypt-with-history path keeps working immediately after migration.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on the history table.
-- K-2 append-only: history rows are NEVER deleted by the application;
--      only purged_at flips once worker confirms no ciphertext uses
--      that key anymore. The row stays for audit.
-- K-18: key_ref keeps the same shape (Vault path prod / inline dev).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tenant_field_key_versions (
    enterprise_id  UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    version        INTEGER      NOT NULL,
    key_ref        TEXT         NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    superseded_at  TIMESTAMPTZ,
    purged_at      TIMESTAMPTZ,

    PRIMARY KEY (enterprise_id, version),

    CONSTRAINT chk_tfkv_version_pos CHECK (version > 0),
    CONSTRAINT chk_tfkv_purge_after_supersede CHECK (
        purged_at IS NULL OR superseded_at IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_tfkv_active
    ON tenant_field_key_versions(enterprise_id, version DESC)
    WHERE purged_at IS NULL;


ALTER TABLE tenant_field_keys
    ADD COLUMN IF NOT EXISTS reencrypt_status        TEXT          NOT NULL DEFAULT 'idle',
    ADD COLUMN IF NOT EXISTS reencrypt_started_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reencrypt_completed_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reencrypt_error         TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_tfk_reencrypt_status'
    ) THEN
        ALTER TABLE tenant_field_keys
            ADD CONSTRAINT chk_tfk_reencrypt_status CHECK (
                reencrypt_status IN ('idle', 'pending', 'running', 'completed', 'failed')
            );
    END IF;
END $$;


-- Backfill: mirror current rows into history at their current version.
-- ON CONFLICT NOTHING because re-running this migration must be idempotent.
INSERT INTO tenant_field_key_versions (enterprise_id, version, key_ref, created_at)
    SELECT enterprise_id, version, key_ref, created_at
    FROM tenant_field_keys
ON CONFLICT (enterprise_id, version) DO NOTHING;


COMMENT ON TABLE tenant_field_key_versions IS
    'P2 retro item 6 — append-only history of every field-encryption '
    'key version ever issued to a tenant. Decrypt-with-history fallback '
    'consults this table when the current key fails. purged_at flips '
    'after re-encrypt worker confirms no ciphertext still uses this key.';
COMMENT ON COLUMN tenant_field_key_versions.superseded_at IS
    'When this version stopped being current (next rotation bumped past it).';
COMMENT ON COLUMN tenant_field_key_versions.purged_at IS
    'When re-encrypt worker confirmed zero rows still need this key. '
    'Row STAYS for audit even after purge; the flag just tells worker '
    'to skip on future runs.';
COMMENT ON COLUMN tenant_field_keys.reencrypt_status IS
    'Worker state machine: idle (no rotation pending) -> pending (rotate '
    'just bumped version) -> running (worker walking rows) -> completed '
    '(all ciphertext now under current version) | failed (one+ row '
    'undecryptable with any historical key).';

COMMIT;
