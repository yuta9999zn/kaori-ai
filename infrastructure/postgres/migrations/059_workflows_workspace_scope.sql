-- 059_workflows_workspace_scope.sql — P15-S11 live-test fix 2026-05-15.
--
-- Anh's live test surfaced: a Vingroup HQ user (logged in as Vinhomes
-- MANAGER) cannot click "Tạo workflow" on a VinMart dept because the
-- POST handler's dept-in-caller-enterprise guard rejects: dept belongs
-- to VinMart, caller's enterprise = Vinhomes → 400.
--
-- Right semantics for Vingroup-class (mig 055/056): an HQ user manages
-- workflows ACROSS all subsidiaries within the same workspace. So:
--   - workflows tables move from enterprise-scoped RLS to workspace-
--     scoped RLS.
--   - POST /workflows derives the workflow's enterprise_id from the
--     dept_id (not from caller's JWT header) + verifies the dept's
--     workspace_id == caller's workspace_id.
--
-- Schema changes
--   1. workflows + workflow_nodes + workflow_edges +
--      workflow_step_documents + workflow_step_folders: ADD workspace_id
--      NOT NULL with backfill from enterprises join.
--   2. Replace existing isolation_* RLS policies with workspace-scoped
--      versions using `app.current_workspace_id` GUC (set by
--      shared/db.py acquire_for_tenant alongside the existing
--      enterprise_id GUCs).
--   3. ABAC dept_scope policies kept (still narrows to a single dept
--      when the GUC is set — orthogonal axis).
--
-- This stays K-1 compliant: workspace_id IS the outer tenant boundary
-- for SaaS subscribers; one workspace = one paying customer. Within
-- the workspace, enterprises (subsidiaries) share visibility — that's
-- the Vingroup-class feature.

BEGIN;

-- ─── 1. ALTER tables ─ ADD workspace_id ──────────────────────────────

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(workspace_id) ON DELETE CASCADE;
ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE workflow_edges
    ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE workflow_step_documents
    ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE workflow_step_folders
    ADD COLUMN IF NOT EXISTS workspace_id UUID;

-- ─── 2. Backfill from enterprises join ───────────────────────────────

UPDATE workflows w
SET    workspace_id = e.workspace_id
FROM   enterprises e
WHERE  e.enterprise_id = w.enterprise_id
  AND  w.workspace_id IS NULL;

UPDATE workflow_nodes n
SET    workspace_id = w.workspace_id
FROM   workflows w
WHERE  w.workflow_id = n.workflow_id
  AND  n.workspace_id IS NULL;

UPDATE workflow_edges ed
SET    workspace_id = w.workspace_id
FROM   workflows w
WHERE  w.workflow_id = ed.workflow_id
  AND  ed.workspace_id IS NULL;

UPDATE workflow_step_documents sd
SET    workspace_id = w.workspace_id
FROM   workflows w
WHERE  w.workflow_id = sd.workflow_id
  AND  sd.workspace_id IS NULL;

UPDATE workflow_step_folders sf
SET    workspace_id = w.workspace_id
FROM   workflows w
WHERE  w.workflow_id = sf.workflow_id
  AND  sf.workspace_id IS NULL;

-- ─── 3. NOT NULL constraint after backfill ───────────────────────────

ALTER TABLE workflows               ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE workflow_nodes          ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE workflow_edges          ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE workflow_step_documents ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE workflow_step_folders   ALTER COLUMN workspace_id SET NOT NULL;

-- ─── 4. Indexes on workspace_id ──────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_workflows_workspace
    ON workflows (workspace_id, state);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workspace
    ON workflow_nodes (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_edges_workspace
    ON workflow_edges (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_step_documents_workspace
    ON workflow_step_documents (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workflow_step_folders_workspace
    ON workflow_step_folders (workspace_id);

-- ─── 5. Replace RLS policies — workspace-scoped ──────────────────────

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'workflows', 'workflow_nodes', 'workflow_edges',
        'workflow_step_documents', 'workflow_step_folders'
    ]
    LOOP
        -- Drop old enterprise-scoped isolation policy.
        EXECUTE format('DROP POLICY IF EXISTS isolation_%I ON %I', tbl, tbl);

        -- New workspace-scoped policy.
        EXECUTE format($f$
            CREATE POLICY isolation_%I ON %I
                USING      (workspace_id::text = current_setting('app.current_workspace_id', true))
                WITH CHECK (workspace_id::text = current_setting('app.current_workspace_id', true))
        $f$, tbl, tbl);
    END LOOP;
END $$;

-- ABAC dept_scope policy on workflow_nodes / workflow_step_documents /
-- workflow_step_folders stays — same behaviour: narrow to one dept
-- when app.current_department_id GUC is set; show everything otherwise.

-- ─── 6. Relax departments / branches / enterprises / data_sources RLS to
--      workspace-aware (Vingroup HQ user reads any subsidiary's data) ─

-- departments — was enterprise-scoped only (mig 046). Add workspace path.
DROP POLICY IF EXISTS isolation_departments ON departments;
CREATE POLICY isolation_departments ON departments
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        OR EXISTS (
            SELECT 1 FROM enterprises e
            WHERE e.enterprise_id = departments.enterprise_id
              AND e.workspace_id::text = current_setting('app.current_workspace_id', true)
        )
    )
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

-- branches — same fix.
DROP POLICY IF EXISTS isolation_branches ON branches;
CREATE POLICY isolation_branches ON branches
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        OR EXISTS (
            SELECT 1 FROM enterprises e
            WHERE e.enterprise_id = branches.enterprise_id
              AND e.workspace_id::text = current_setting('app.current_workspace_id', true)
        )
    )
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

-- data_sources — same fix.
DROP POLICY IF EXISTS isolation_data_sources ON data_sources;
CREATE POLICY isolation_data_sources ON data_sources
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        OR EXISTS (
            SELECT 1 FROM enterprises e
            WHERE e.enterprise_id = data_sources.enterprise_id
              AND e.workspace_id::text = current_setting('app.current_workspace_id', true)
        )
    )
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

-- enterprises — workspace-aware read so an HQ user can resolve any
-- subsidiary's enterprise_id from a dept_id. WITH CHECK stays strict
-- (writes happen via separate /corporate-groups + /business-divisions
-- endpoints, not direct INSERTs into enterprises from app code).
ALTER TABLE enterprises ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS isolation_enterprises ON enterprises;
CREATE POLICY isolation_enterprises ON enterprises
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        OR workspace_id::text = current_setting('app.current_workspace_id', true)
    );

COMMIT;

-- ─── Comments ────────────────────────────────────────────────────────

COMMENT ON COLUMN workflows.workspace_id IS
    'P15-S11 mig 059 — denormalised from enterprises.workspace_id for '
    'workspace-scoped RLS. Allows a Vingroup HQ user (one workspace, many '
    'enterprises) to see + manage workflows across all subsidiaries.';
