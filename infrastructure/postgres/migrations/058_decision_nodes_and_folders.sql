-- 058_decision_nodes_and_folders.sql — P15-S11 Tuần 8 Phase 2 extension.
--
-- Per anh's Vingroup-class question 2026-05-15:
--
--   "Workflow có 10 bước với mũi tên if/else, switch key" +
--   "card có nội dung, văn bản đi kèm, sắp xếp ngăn nắp giống folder Win".
--
-- Mig 053 shipped only node_type='step'. This migration unlocks the
-- decision node subset of docx Phần 2's 45-type catalog needed for
-- branching workflows + folder-organised attachments per step.
--
-- Changes
--   1. workflow_nodes — keep node_type free-text (no CHECK constraint
--      today). Add `decision_config` JSONB column for if/else / switch
--      cases. Existing rows untouched (default NULL).
--   2. workflow_step_folders — new table. Each folder is a named bucket
--      under a workflow node. parent_folder_id self-ref enables nested
--      sub-folders Windows-style. Soft-delete via `status='archived'`.
--   3. workflow_step_documents — add `folder_id` FK NULLABLE so an
--      uploaded file can live at the step root OR inside a folder.
--
-- Backwards compatible — existing workflow_nodes (node_type='step') and
-- existing workflow_step_documents (folder_id=NULL) work unchanged.

-- ─── 1. workflow_nodes — decision_config column ──────────────────────

ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS decision_config JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN workflow_nodes.decision_config IS
    'P15-S11 mig 058 — config for decision nodes. Shape per node_type: '
    '  decision_if_else: {"condition": "expr", "true_target_id": "<node_id>", "false_target_id": "<node_id>"}. '
    '  decision_switch:  {"switch_field": "x", "cases": [{"value":"A","target_id":"..."}], "default_target_id":"..."}. '
    '  approval_gate:    {"approver_role": "MANAGER", "message": "...", "timeout_action": "auto_approve|reject"}. '
    'Phase 1 (step) ignores this column.';

-- ─── 2. workflow_step_folders ────────────────────────────────────────
--
-- Each card (workflow_node) can host a folder tree. A folder belongs to
-- exactly one node; sub-folders chain via parent_folder_id. Path is
-- materialised at app level (router walks parent_folder_id on read).

CREATE TABLE IF NOT EXISTS workflow_step_folders (
    folder_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID            NOT NULL REFERENCES workflows(workflow_id)        ON DELETE CASCADE,
    node_id             UUID            NOT NULL REFERENCES workflow_nodes(node_id)       ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL,
    department_id       UUID            NOT NULL,

    -- Folder identity within its parent (Windows-style: name unique among
    -- siblings in the same parent_folder_id under the same node).
    parent_folder_id    UUID            REFERENCES workflow_step_folders(folder_id) ON DELETE CASCADE,
    name                VARCHAR(200)    NOT NULL,
    sort_order          INTEGER         NOT NULL DEFAULT 0,

    status              VARCHAR(20)     NOT NULL DEFAULT 'active',

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by          UUID,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_folder_status CHECK (status IN ('active', 'archived'))
);

-- Name unique among siblings — partial unique index handles NULL
-- parent_folder_id correctly (sibling roots under the same node).
CREATE UNIQUE INDEX IF NOT EXISTS uq_folder_name_per_parent
    ON workflow_step_folders (node_id, COALESCE(parent_folder_id, '00000000-0000-0000-0000-000000000000'::uuid), name)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_folders_node
    ON workflow_step_folders (node_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_folders_parent
    ON workflow_step_folders (parent_folder_id)
    WHERE parent_folder_id IS NOT NULL;

-- ─── 3. workflow_step_documents.folder_id ────────────────────────────

ALTER TABLE workflow_step_documents
    ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES workflow_step_folders(folder_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_step_docs_folder
    ON workflow_step_documents (folder_id)
    WHERE folder_id IS NOT NULL;

-- ─── 4. RLS — same K-1 + ABAC pattern as workflow_nodes ──────────────

ALTER TABLE workflow_step_folders ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_workflow_step_folders ON workflow_step_folders;
CREATE POLICY isolation_workflow_step_folders ON workflow_step_folders
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DROP POLICY IF EXISTS abac_dept_scope_workflow_step_folders ON workflow_step_folders;
CREATE POLICY abac_dept_scope_workflow_step_folders ON workflow_step_folders
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        AND (
            current_setting('app.current_department_id', true) = ''
            OR current_setting('app.current_department_id', true) IS NULL
            OR department_id::text = current_setting('app.current_department_id', true)
        )
    );

-- ─── 5. Grants ───────────────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_step_folders TO kaori_app';
    END IF;
END $$;

-- ─── 6. Comments ─────────────────────────────────────────────────────

COMMENT ON TABLE workflow_step_folders IS
    'P15-S11 mig 058 — Windows-style folder tree under each workflow card. '
    'A card (workflow_node) can have any number of root folders; each root '
    'folder can have sub-folders via parent_folder_id self-ref. Uploaded '
    'files land at root (folder_id=NULL) or inside a folder. Phase 2 FE '
    'renders a collapsible folder tree above the flat file list.';
COMMENT ON COLUMN workflow_step_folders.parent_folder_id IS
    'Self-ref for nested sub-folders. NULL = root folder under the card. '
    'Cycle detection is app-layer responsibility (router rejects on POST).';
COMMENT ON COLUMN workflow_step_documents.folder_id IS
    'P15-S11 mig 058 — when set, the upload lives inside this folder under '
    'the workflow card. NULL = file lives at the card root (legacy + flat '
    'organisation).';
