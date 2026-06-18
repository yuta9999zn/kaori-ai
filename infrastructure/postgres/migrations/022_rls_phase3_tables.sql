-- Migration 022: RLS audit gap closure — Phase 2 error-handling B3 PR #7 (#9 multi-tenant leak).
--
-- Why
-- ===
-- The 005_rls.sql baseline enabled RLS on the original Phase 1 schema
-- (pipeline_runs, bronze_*, decision_audit_log, analysis_runs/results,
-- enterprise_users, enterprise_monthly_billing, etl_run_log). Later
-- migrations (009/015/018/019) all remembered to enable RLS on the new
-- tenant-scoped tables they introduced. Two slipped through:
--
--   * subscription_change_requests (017) — has enterprise_id NOT NULL
--     but no RLS. F-030 upgrade-request rows for tenant A would be
--     visible to tenant B if BYPASSRLS were ever lifted.
--
--   * api_request_log (004) — has enterprise_id (nullable, NULL on
--     pre-auth requests). Today it's only read by ops via direct DB
--     access, but any future per-tenant audit/observability surface
--     reading via kaori_app would leak cross-tenant request lines.
--
-- Why this matters even though kaori_app currently has BYPASSRLS=true
-- (set in 008): the migration prepares for the BYPASSRLS=false cutover
-- planned for the next Phase 2 hardening pass. Once that flips, the
-- policies below become the enforcement boundary. Adding them now is
-- safe (no behavior change today) and means the cutover is a one-line
-- ALTER ROLE instead of a "and one more migration" surprise.
--
-- Why FORCE ROW LEVEL SECURITY
-- ============================
-- ENABLE RLS alone exempts the table owner from the policy. FORCE makes
-- the policy apply to the owner too — matches the rest of the tenant-
-- scoped tables (005_rls.sql:110-120). The migration runs as `kaori`
-- which is the owner and currently has BYPASSRLS, so FORCE is
-- additionally a defence-in-depth: even a future role that owns the
-- table cannot bypass tenant isolation by accident.
--
-- Tables intentionally NOT covered
-- ================================
--   * workspace_audit_log (011) — keyed on workspace_id, not enterprise_id.
--     The /platform/workspaces/{id}/audit page reads it via session-bound
--     platform_admin tokens (BYPASSRLS path). A workspace_id-scoped policy
--     would need a JOIN to enterprises which is non-trivial; deferred until
--     the table is read from a non-platform path.
--   * job_leases (020), processed_events (009), llm_models /
--     llm_task_routing (010), platform_admins / platform_admin_audit_log
--     / admin_sessions (011/012/014), workspaces / enterprises /
--     workspace_keys / password_reset_tokens / subscription_plans (001) —
--     system-level / global / pre-tenant tables. Documented in each
--     migration. Skipped per spec ("project_next_session_queue.md":
--     "Skip platform-side system tables").
--
-- Reversibility
-- =============
--   ALTER TABLE subscription_change_requests NO FORCE ROW LEVEL SECURITY;
--   ALTER TABLE subscription_change_requests DISABLE ROW LEVEL SECURITY;
--   DROP POLICY tenant_subscription_change_requests ON subscription_change_requests;
--   ALTER TABLE api_request_log NO FORCE ROW LEVEL SECURITY;
--   ALTER TABLE api_request_log DISABLE ROW LEVEL SECURITY;
--   DROP POLICY tenant_api_request_log ON api_request_log;
-- ============================================================

BEGIN;

-- =========================================================================
-- 1. subscription_change_requests (017) — clear gap, enterprise_id NOT NULL
-- =========================================================================
ALTER TABLE subscription_change_requests ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'subscription_change_requests'
          AND policyname = 'tenant_subscription_change_requests'
    ) THEN
        CREATE POLICY tenant_subscription_change_requests ON subscription_change_requests
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE subscription_change_requests FORCE ROW LEVEL SECURITY;

-- =========================================================================
-- 2. api_request_log (004) — partitioned, enterprise_id NULLABLE
--    Mirrors etl_run_log policy from 005 (NULL row passes through; system
--    events without a tenant context are visible regardless of GUC).
--    Postgres ≥10: RLS on the parent partition auto-applies to all
--    partitions including the future ones in api_request_log_2026_*.
-- =========================================================================
ALTER TABLE api_request_log ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'api_request_log'
          AND policyname = 'tenant_api_request_log'
    ) THEN
        CREATE POLICY tenant_api_request_log ON api_request_log
            USING (enterprise_id IS NULL
                OR enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE api_request_log FORCE ROW LEVEL SECURITY;

-- kaori_app GRANTs come from DEFAULT PRIVILEGES set in 008_kaori_app_grants.sql.

COMMIT;
