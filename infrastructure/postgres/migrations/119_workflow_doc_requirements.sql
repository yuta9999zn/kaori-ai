-- =====================================================================
-- 119_workflow_doc_requirements.sql — Tier-3 Document Tree, Phase 1 (ADR-0037)
--
-- Per-step document TEMPLATE configured in the builder: declares which
-- documents a workflow step needs, classified as input (📥 nộp lên) /
-- output (📤 sinh ra) / reference (📎 tham chiếu). The runtime instances live
-- in workflow_step_documents (extended in mig 120); this table is the design-
-- time requirement a step's executor/UI checks against ("0/3 tài liệu đã nộp").
--
-- Additive: new table, mirrors the mig 053 RLS (K-1) + ABAC dept-scope + grant
-- pattern exactly. No change to existing tables.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_step_document_requirements (
    requirement_id   UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),  -- K-21
    workflow_id      UUID         NOT NULL REFERENCES workflows(workflow_id)  ON DELETE CASCADE,
    node_id          UUID         NOT NULL REFERENCES workflow_nodes(node_id) ON DELETE CASCADE,
    enterprise_id    UUID         NOT NULL,
    department_id    UUID         NOT NULL,

    -- The 3 classes drive color + icon + display logic in the tree.
    doc_class        VARCHAR(16)  NOT NULL,
    name_vi          VARCHAR(200) NOT NULL,
    description      TEXT,
    is_required      BOOLEAN      NOT NULL DEFAULT TRUE,
    allowed_formats  TEXT[]       NOT NULL DEFAULT ARRAY['pdf','docx','xlsx','csv','jpg','png'],

    -- For output blanks / reference docs: a template file the step issues or the
    -- guideline the executor reads (points at bronze_files; nullable for inputs).
    template_file_id UUID         REFERENCES bronze_files(file_id) ON DELETE SET NULL,

    sort_order       INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_wsdr_class CHECK (doc_class IN ('input', 'output', 'reference')),
    -- A reference/output template requirement may not repeat the same name per node.
    CONSTRAINT uq_wsdr UNIQUE (node_id, doc_class, name_vi)
);

CREATE INDEX IF NOT EXISTS idx_wsdr_node       ON workflow_step_document_requirements(node_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_wsdr_workflow   ON workflow_step_document_requirements(workflow_id);
CREATE INDEX IF NOT EXISTS idx_wsdr_enterprise ON workflow_step_document_requirements(enterprise_id, department_id);

-- ─── RLS (K-1) + ABAC dept-scope — mirror mig 053 ────────────────────
ALTER TABLE workflow_step_document_requirements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_wsdr ON workflow_step_document_requirements;
CREATE POLICY isolation_wsdr ON workflow_step_document_requirements
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DROP POLICY IF EXISTS abac_dept_scope_wsdr ON workflow_step_document_requirements;
CREATE POLICY abac_dept_scope_wsdr ON workflow_step_document_requirements
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        AND (
            current_setting('app.current_department_id', true) = ''
            OR current_setting('app.current_department_id', true) IS NULL
            OR department_id::text = current_setting('app.current_department_id', true)
        )
    );

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_step_document_requirements TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE workflow_step_document_requirements IS
    'ADR-0037 Tier-3 Phase 1 — per-step document template: declares input/output/'
    'reference documents a workflow step needs. Runtime instances live in '
    'workflow_step_documents (mig 120). RLS K-1 + ABAC dept-scope per mig 053.';

COMMIT;
