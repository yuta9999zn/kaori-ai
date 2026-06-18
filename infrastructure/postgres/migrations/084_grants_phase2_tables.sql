-- =====================================================================
-- 084_grants_phase2_tables.sql
--
-- Grants kaori_app role SELECT/INSERT/UPDATE/DELETE on the Phase 2 +
-- 2026-05-18 session tables that were missing from the original mig
-- 008 grants block (and from migs 074/075/080/081/082/083 individual
-- table creates — em was applying them via the kaori superuser which
-- bypassed the GRANT statements).
--
-- Closes the InsufficientPrivilegeError that surfaced when the
-- Vault-wired MFA enroll endpoint tried to INSERT into mfa_backup_codes
-- as the runtime kaori_app role.
--
-- K-1 RLS: grants don't bypass RLS — every SELECT/UPDATE still must
-- filter by enterprise_id. This migration only opens the table
-- channel to kaori_app.
-- =====================================================================

BEGIN;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    -- mig 074 — MFA + field encryption
    mfa_secrets,
    mfa_backup_codes,
    tenant_field_keys,
    -- mig 075 — LLM ops
    llm_providers,
    tenant_llm_api_keys,
    llm_token_usage_daily,
    llm_upgrade_tests,
    -- mig 080 — field-key rotation history
    tenant_field_key_versions,
    -- mig 081 — ROI billing
    enterprise_roi_subscriptions,
    enterprise_roi_billing_lines,
    -- mig 082 — guardrail violations (partitioned parent)
    guardrail_violations,
    -- mig 083 — SSO identities + state + exchange codes
    sso_identities,
    sso_oauth_state,
    sso_exchange_codes
TO kaori_app;

-- Sequences (so DEFAULT gen_random_uuid() / serial PKs work)
-- gen_random_uuid() doesn't use sequences; no GRANT USAGE ON SEQUENCE
-- needed for these tables. Adjust if Phase 3 introduces serial PKs.

COMMIT;
