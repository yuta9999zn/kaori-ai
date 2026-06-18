-- =====================================================================
-- 126_abac_dept_restrictive.sql — Tier-3 (ADR-0037): make ABAC dept-scope ENFORCE
--
-- RLS gotcha: multiple PERMISSIVE policies are OR'd. The isolation_* (enterprise
-- only) + abac_dept_scope_* (enterprise AND dept) policies were BOTH permissive,
-- so the enterprise-only one always passed → the dept clause never restricted
-- anything. Recreate the dept policy AS RESTRICTIVE so it AND-combines: an empty
-- app.current_department_id GUC still allows all (enterprise-wide), but a set GUC
-- now genuinely limits the read to that department.
--
-- Applies to the Tier-3 tables that carry department_id (contracts +
-- doc-requirements). The mig-053 tables (workflows/nodes) share the same latent
-- pattern — a separate fix.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['contracts', 'workflow_step_document_requirements'] LOOP
        -- drop the permissive dept policy
        EXECUTE format('DROP POLICY IF EXISTS abac_dept_scope_%I ON %I', tbl, tbl);
        -- recreate it RESTRICTIVE so it AND-combines with isolation_*
        EXECUTE format($f$
            CREATE POLICY abac_dept_scope_%I ON %I AS RESTRICTIVE
                USING (
                    current_setting('app.current_department_id', true) = ''
                    OR current_setting('app.current_department_id', true) IS NULL
                    OR department_id::text = current_setting('app.current_department_id', true)
                )
        $f$, tbl, tbl);
    END LOOP;
END $$;

COMMIT;
