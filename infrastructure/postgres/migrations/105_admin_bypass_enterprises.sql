-- =====================================================================
-- 105_admin_bypass_enterprises.sql — RLS drift fix
--
-- Migration 025 swept 17 tenant-scoped tables to add admin_bypass_<t>
-- policies for the NOBYPASSRLS cutover, but skipped `enterprises`
-- (which has its own isolation_enterprises policy using workspace_id
-- OR enterprise_id GUCs — neither set when platform admin INSERTs).
--
-- Symptom that surfaced this: POST /api/v1/platform/workspaces with a
-- non-empty `industry` triggers WorkspaceService.seedEnterprise() which
-- INSERTs into enterprises. RLS denies → SQLSTATE 42501 → Spring
-- maps to 403 with empty body (no JSON, because Postgres exception
-- propagated past the controller's typed-exception handlers).
--
-- Fix: mirror the mig 025 pattern. Permissive USING + WITH CHECK on
-- (app.is_admin = 'true'), idempotent guard. Caller must invoke
-- RlsBypassHelper.disableForTx() before cross-tenant INSERT/UPDATE.
--
-- Note: There are ~30 other RLS-enabled tables added since mig 025
-- (workflow_*, silver_*, customers, vendors, ...) that have the same
-- drift. They're inert until a cross-tenant path hits them — handled
-- in a follow-up sweep PR. This migration is the surgical fix for the
-- workspace-create-with-industry bug only.
-- =====================================================================

BEGIN;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE tablename = 'enterprises'
           AND policyname = 'admin_bypass_enterprises'
    ) THEN
        CREATE POLICY admin_bypass_enterprises ON enterprises
            USING       (current_setting('app.is_admin', true) = 'true')
            WITH CHECK  (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

COMMIT;
