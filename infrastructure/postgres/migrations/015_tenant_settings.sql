-- Migration 015: tenant_settings table — F-016 Enterprise Settings (Phase 1 close-out)
--
-- Per-enterprise opt-in flags + branding. 1:1 with `enterprises`, lazy-created
-- by TenantSettingsService on first GET so existing tenants don't need a backfill.
--
-- Why a separate table from `enterprises`:
--   * `enterprises` is owned by the platform-admin provisioning flow — fields
--     there (workspace_id, name, status, locale, timezone) are mostly read-only
--     for the enterprise MANAGER role.
--   * `tenant_settings` is owned by the enterprise MANAGER itself — consent
--     toggle (K-4), theme, notification opt-in, branding all change per-tenant
--     without rewriting the canonical enterprise record.
--   * Different update cadence + different RBAC owner ⇒ different table.
--
-- Why no `locale` column here:
--   `enterprises.locale VARCHAR(10) DEFAULT 'vi'` already exists (001_init.sql:43).
--   The settings page joins on it; locale changes go to `enterprises` directly via
--   a separate flow (LocalePicker) so there is no duplicate source of truth.
--
-- K-4 invariant: ai-orchestrator's llm_router reads `consent_external_ai`
--   per-call (cached 60s) and refuses to forward to llm-gateway with
--   consent=true unless this column is true. Default FALSE means a fresh
--   tenant CANNOT trigger an external LLM call until the MANAGER explicitly
--   opts in via the Settings page.

BEGIN;

CREATE TABLE IF NOT EXISTS tenant_settings (
    enterprise_id          UUID         PRIMARY KEY REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    theme                  VARCHAR(20)  NOT NULL DEFAULT 'light',
    consent_external_ai    BOOLEAN      NOT NULL DEFAULT FALSE,
    notification_email     BOOLEAN      NOT NULL DEFAULT FALSE,
    branding_logo_url      TEXT,
    branding_accent_color  VARCHAR(20),
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenant_settings_consent
    ON tenant_settings(enterprise_id) WHERE consent_external_ai = TRUE;

-- RLS: same pattern as 005_rls.sql. ai-orchestrator queries via
--   acquire_for_tenant() set the GUC; auth-service runs as superuser
--   (BYPASSRLS) so its queries pass through but MUST still explicit
--   WHERE enterprise_id = $1 (K-12 — never trust query string).
ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'tenant_settings' AND policyname = 'tenant_settings_isolation'
    ) THEN
        CREATE POLICY tenant_settings_isolation ON tenant_settings
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY;

-- GRANTs to kaori_app come from DEFAULT PRIVILEGES set in 008_kaori_app_grants.sql.
-- Verified: this migration runs as `kaori` (POSTGRES_USER), so 008's defaults
-- attach SELECT/INSERT/UPDATE on tenant_settings to kaori_app automatically.

COMMIT;
