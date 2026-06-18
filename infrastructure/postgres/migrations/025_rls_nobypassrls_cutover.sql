-- Migration 025: NOBYPASSRLS cutover — make every dormant RLS policy real.
--
-- This is the SECOND half of the two-step cutover. Migration 024
-- (PR #106) prepared every code path that needed wiring. This migration:
--
--   1. Adds an ``admin_bypass_*`` policy on every tenant-scoped table so
--      cross-tenant aggregations can opt in via a session GUC.
--   2. Flips ``ALTER ROLE kaori_app NOBYPASSRLS`` — every dormant policy
--      is now real enforcement.
--
-- Why ``admin_bypass`` instead of ``SET LOCAL row_security = off``
-- ===============================================================
-- Postgres' ``row_security`` GUC isn't a bypass — when ``off`` it
-- ERRORS on any query that would be affected by an RLS policy. The
-- only legitimate ways to read every tenant's rows are:
--
--   a. Run as a role with ``BYPASSRLS`` (e.g., the ``kaori`` superuser
--      used by Flyway + IT), or
--   b. Have a permissive RLS policy that evaluates to true for the
--      caller's session state.
--
-- (a) defeats the goal of this PR. (b) is what we use: each tenant
-- table gets a sibling ``admin_bypass`` policy that returns true when
-- ``app.is_admin = 'true'`` is set on the session. Postgres applies
-- multiple permissive policies as OR, so a row is visible when EITHER
-- ``enterprise_id = app.enterprise_id`` (per-tenant) OR
-- ``app.is_admin = 'true'`` (cross-tenant aggregation). The default
-- (no GUC set) blocks both.
--
-- ``RlsBypassHelper.disableForTx()`` and ``acquire_cross_tenant()``
-- (the Python equivalent) are updated in this PR to ``SET LOCAL
-- app.is_admin = 'true'`` to match. ``pipeline_runs`` already had this
-- policy from 001_init.sql:347; this migration adds the same shape to
-- every other tenant table that's read cross-tenant today, plus the
-- ones the spec is likely to grow into (defence in depth — a future
-- platform-admin feature that adds a cross-tenant query won't need a
-- new migration).
--
-- After this point
-- ================
--   * Every read / write on a tenant-scoped table from kaori_app
--     either sets ``app.enterprise_id`` (per-tenant) or
--     ``app.is_admin='true'`` (cross-tenant). The PR #7 lint enforces
--     ``WHERE enterprise_id`` at the SQL string level; this migration
--     enforces the same at the database level.
--   * Migrations themselves run as the ``kaori`` superuser
--     (SPRING_FLYWAY_USER=kaori in docker-compose.yml), which still
--     bypasses RLS, so DDL is unaffected.
--   * IT Postgres also runs as ``kaori`` superuser (see
--     AbstractIntegrationIT), so the IT suite continues to pass.
--     Real RLS coverage comes from production / pilot where
--     auth-service connects as kaori_app.
--
-- Rollback
-- ========
-- If anything breaks at run-time (login fails, dashboards return zero
-- rows, etc.):
--   ALTER ROLE kaori_app BYPASSRLS;
-- One statement, instant. The policies stay in place; only the role's
-- bypass flag flips back.
--
-- Smoke test (run before merging this migration to any environment
-- that already has live tenants)
-- ============================================================
--   1. ``docker compose up -d`` (rebuild + restart everything).
--   2. Enterprise login at http://localhost:3000/login → success.
--   3. /pipeline upload a small CSV → bronze_files + bronze_rows
--      insert cleanly (no "row violates row-level security policy"
--      errors).
--   4. /decisions list + CSV export → returns rows (per-tenant via
--      acquire_for_tenant in the router).
--   5. /platform/login + /platform/billing/overview → numbers render
--      across all tenants (admin_bypass path).
--   6. Cron: trigger BillingAggregationService.aggregateCurrentMonth()
--      → unique_customers + alert flags update on every active tenant.
--
-- Reversibility
-- =============
-- Full revert:
--   ALTER ROLE kaori_app BYPASSRLS;
--   DROP POLICY admin_bypass_<each table> ON <each table>;
-- (See the DROP statements implicit in each CREATE below — easy to
--  reverse one-by-one.)
-- ============================================================

BEGIN;

-- =========================================================================
-- 1. admin_bypass policies on every tenant-scoped table.
--
--    Pattern: USING ( current_setting('app.is_admin', true) = 'true' ).
--    Permissive (default) so it ORs with the existing tenant_isolation
--    policy. Idempotent CREATE POLICY guard so re-running this migration
--    is safe.
-- =========================================================================
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN
        SELECT tablename FROM (VALUES
            -- Phase 1 base set (RLS introduced in 005_rls.sql)
            ('bronze_files'),
            ('bronze_rows'),
            ('canonical_schemas'),
            ('decision_audit_log'),
            ('silver_rows'),
            ('cleaning_rules_applied'),
            ('analysis_runs'),
            ('analysis_results'),
            ('enterprise_monthly_billing'),
            ('etl_run_log'),
            ('decision_outcomes'),
            -- Sprint 0.5 / 1 / 4-5 / 7 additions
            ('tenant_settings'),
            ('gold_features'),
            ('gold_aggregates'),
            ('decision_actions'),
            -- B3 PR #7 additions
            ('subscription_change_requests'),
            ('api_request_log')
            -- NOTE: pipeline_runs already has admin_bypass_pipeline_runs
            --       from 001_init.sql:347 — skipped here.
            -- NOTE: enterprise_users + event_outbox had RLS dropped in
            --       024_rls_pre_cutover_prep.sql — skipped here.
        ) AS x(tablename)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
             WHERE tablename = t
               AND policyname = 'admin_bypass_' || t
        ) THEN
            EXECUTE format(
                'CREATE POLICY admin_bypass_%I ON %I '
                'USING (current_setting(''app.is_admin'', true) = ''true'')',
                t, t);
        END IF;
    END LOOP;
END $$;

-- =========================================================================
-- 2. Flip kaori_app to NOBYPASSRLS — every policy above + every existing
--    tenant_isolation policy becomes real enforcement.
-- =========================================================================
ALTER ROLE kaori_app NOBYPASSRLS;

COMMIT;
