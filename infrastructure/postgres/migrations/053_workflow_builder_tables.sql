-- 053_workflow_builder_tables.sql — P15-S11 Tuần 8 Step 5 (workflow pivot).
--
-- Anh's request 2026-05-15:
--   "Xây dựng tính năng workflow trước. Mỗi phòng ban có nhiều
--   workflow. Mỗi workflow có 5-7 bước (card). Mỗi card có note,
--   hashtags, loại tài liệu cần upload. Khi user upload, data lưu
--   theo sơ đồ tree workflow → step → docs."
--
-- Per docx 4Kaori_AI_Workflow_System v2.0 PART V Phần 16-18:
--   Drag-drop builder UX, 45 node-type catalog (Phase 1 ships type='step'
--   only — the document-collecting card), workflow lifecycle states.
--
-- Phase 1 scope (Build Week — what THIS migration ships):
--   ✓ workflows-as-data (CRUD via FE builder, no more code-only YAML)
--   ✓ workflow_nodes with the card schema (title + note + hashtags +
--     required_document_types + expected_mapping_template_id)
--   ✓ workflow_edges for step-to-step transitions
--   ✓ workflow_step_documents — link bronze_files ↔ (workflow, step)
--   ✓ workflow_templates (global library — 30 templates seeded mig 054)
--
-- Phase 2 (DEFERRED — NOT in this migration):
--   ✗ Process Mining auto-discovery (PART IV)
--   ✗ Temporal execution engine wiring (PART IX-X)
--   ✗ Versioning + diff (Phần 3) — single-version Phase 1
--   ✗ Adoption Intelligence (PART VIII), NOV per-workflow (PART XI)
--   ✗ 44 other node types — type='step' covers all Build Week cards
--
-- Medallion + RLS:
--   - workflows / workflow_nodes / workflow_edges / workflow_step_documents
--     all carry enterprise_id + RLS K-1 isolation.
--   - workflow_nodes + workflow_step_documents also carry department_id
--     for ABAC §16.4 (per-dept user only sees their dept's cards/uploads).
--   - workflow_templates is GLOBAL (no enterprise_id, no RLS — same as
--     kpi_definitions / industry_benchmarks per mig 049 pattern).

-- ─── 1. workflows ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id)   ON DELETE CASCADE,

    branch_id           UUID            REFERENCES branches(branch_id)                   ON DELETE SET NULL,
    department_id       UUID            NOT NULL REFERENCES departments(department_id)   ON DELETE RESTRICT,

    name                VARCHAR(200)    NOT NULL,
    name_vi             VARCHAR(200),
    description         TEXT,

    -- Categorization (docx Phần 1.1).
    category            VARCHAR(50),         -- 'campaign' | 'pipeline' | 'inventory' | 'reporting' | 'compliance' | 'onboarding' | ...
    business_function   VARCHAR(100),

    -- Lifecycle (docx Phần 5 — 8 states; Phase 1 uses 5 of them).
    state               VARCHAR(30)     NOT NULL DEFAULT 'DRAFT',
    version             INTEGER         NOT NULL DEFAULT 1,

    -- Provenance (docx Phần 1.1 v2.0 — Process Mining annotation).
    source              VARCHAR(50)     NOT NULL DEFAULT 'user_built',
    -- 'user_built' (started blank), 'template_based' (cloned), 'process_mining_discovered' (auto, Phase 2)
    cloned_from_template_id  UUID,
    mining_session_id   UUID,
    fidelity_to_discovered  NUMERIC(5,4),

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by          UUID,
    last_modified_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_modified_by    UUID,

    CONSTRAINT uq_workflow_name_per_enterprise UNIQUE (enterprise_id, department_id, name),
    CONSTRAINT chk_workflow_state CHECK (state IN (
        'DRAFT', 'TESTING', 'ACTIVE_BASELINE', 'ARCHIVED', 'BROKEN'
    )),
    CONSTRAINT chk_workflow_source CHECK (source IN (
        'user_built', 'template_based', 'process_mining_discovered'
    ))
);

CREATE INDEX IF NOT EXISTS idx_workflows_dept_state
    ON workflows (enterprise_id, department_id, state);
CREATE INDEX IF NOT EXISTS idx_workflows_branch
    ON workflows (enterprise_id, branch_id)
    WHERE branch_id IS NOT NULL;

-- ─── 2. workflow_nodes (= "cards") ───────────────────────────────────
--
-- Phase 1: every node has type='step'. Phase 2 unlocks the 45-type
-- catalog from docx Phần 2 (data_input/processing/decision/ai/action/output).

CREATE TABLE IF NOT EXISTS workflow_nodes (
    node_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL,                              -- denormalised for RLS
    department_id       UUID            NOT NULL,                              -- denormalised for ABAC

    -- Type taxonomy (docx Phần 2.1).
    node_type           VARCHAR(50)     NOT NULL DEFAULT 'step',
    category            VARCHAR(30)     NOT NULL DEFAULT 'data_input',
    side_effect_class   VARCHAR(30)     NOT NULL DEFAULT 'read_only',          -- K-17

    -- UX position on the canvas.
    position_x          NUMERIC(10,2)   NOT NULL DEFAULT 0,
    position_y          NUMERIC(10,2)   NOT NULL DEFAULT 0,

    -- Card content (anh's spec 2026-05-15).
    title               VARCHAR(200)    NOT NULL,
    title_vi            VARCHAR(200),
    note                TEXT,

    -- Hashtags — Postgres text[] so the FE can filter "show me all #q1_campaign cards".
    hashtags            TEXT[]          NOT NULL DEFAULT '{}',

    -- Expected documents at this step. Shape:
    --   [
    --     {"kind": "csv",  "name": "Lead list",        "required": true},
    --     {"kind": "docx", "name": "Quote template",   "required": false}
    --   ]
    required_document_types  JSONB      NOT NULL DEFAULT '[]'::jsonb,

    -- When user uploads into this card, the ingestor will skip the
    -- filename-glob template lookup and use THIS template instead
    -- (overrides the auto-match in shared/org_resolver.py).
    expected_mapping_template_id  UUID  REFERENCES mapping_templates(template_id) ON DELETE SET NULL,

    -- Phase 2 execution config (saved but not used Build Week).
    config              JSONB           NOT NULL DEFAULT '{}'::jsonb,
    retry               JSONB,
    timeout_ms          INTEGER,
    compensation        JSONB,                                                 -- REL-012 saga rollback
    lock_config         JSONB,                                                 -- REL-006 distributed lock

    -- Sort order within the workflow (for tree/list views).
    sequence_order      INTEGER         NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_node_side_effect CHECK (side_effect_class IN (
        'pure', 'read_only', 'write_idempotent', 'write_non_idempotent', 'external_irreversible'
    )),
    CONSTRAINT chk_node_category CHECK (category IN (
        'data_input', 'processing', 'decision', 'ai', 'action', 'output'
    ))
);

CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow_seq
    ON workflow_nodes (workflow_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_dept
    ON workflow_nodes (enterprise_id, department_id);
CREATE INDEX IF NOT EXISTS idx_workflow_nodes_hashtags
    ON workflow_nodes USING GIN (hashtags);

-- ─── 3. workflow_edges (step → step transitions) ─────────────────────

CREATE TABLE IF NOT EXISTS workflow_edges (
    edge_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL,

    source_node_id      UUID            NOT NULL REFERENCES workflow_nodes(node_id) ON DELETE CASCADE,
    target_node_id      UUID            NOT NULL REFERENCES workflow_nodes(node_id) ON DELETE CASCADE,

    -- Optional gating condition + UX label.
    condition           TEXT,
    label               VARCHAR(100),

    -- Edge semantics (docx Phần 1.3 v2.0).
    delivery_guarantee  VARCHAR(20)     NOT NULL DEFAULT 'best_effort',
    ordering            VARCHAR(20)     NOT NULL DEFAULT 'fifo',

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_edge_no_self_loop CHECK (source_node_id <> target_node_id),
    CONSTRAINT uq_edge_pair UNIQUE (workflow_id, source_node_id, target_node_id),
    CONSTRAINT chk_edge_delivery CHECK (delivery_guarantee IN ('best_effort', 'guaranteed', 'transactional')),
    CONSTRAINT chk_edge_ordering CHECK (ordering IN ('fifo', 'unordered'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_edges_workflow
    ON workflow_edges (workflow_id);

-- ─── 4. workflow_step_documents — bronze_file ↔ step linkage ─────────
--
-- This is the table that fulfils anh's "data sẽ được lưu theo sơ đồ
-- tree tương ứng" — every Bronze upload that went through a workflow
-- step gets attached here. Tree viewer joins workflow → nodes → these.

CREATE TABLE IF NOT EXISTS workflow_step_documents (
    attachment_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID            NOT NULL REFERENCES workflows(workflow_id)       ON DELETE CASCADE,
    node_id             UUID            NOT NULL REFERENCES workflow_nodes(node_id)      ON DELETE CASCADE,
    file_id             UUID            NOT NULL REFERENCES bronze_files(file_id)        ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL,
    department_id       UUID            NOT NULL,

    -- Auto-detected at upload from the node's required_document_types[].
    -- Helps the tree viewer label "Lead list (csv)" vs raw filename.
    document_kind       VARCHAR(50),

    uploaded_by         UUID,
    uploaded_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    notes               TEXT,

    -- Idempotent: same file can be re-attached without duplicating.
    CONSTRAINT uq_step_doc UNIQUE (workflow_id, node_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_step_docs_node
    ON workflow_step_documents (workflow_id, node_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_step_docs_file
    ON workflow_step_documents (file_id);
CREATE INDEX IF NOT EXISTS idx_workflow_step_docs_dept
    ON workflow_step_documents (enterprise_id, department_id);

-- ─── 5. workflow_templates — global library (docx Phần 17.1) ─────────
--
-- 30 templates seeded by mig 054 (5 per dept × 6 dept_types). Cloning
-- a template creates real workflows + nodes + edges rows; the
-- workflow.cloned_from_template_id keeps provenance.

CREATE TABLE IF NOT EXISTS workflow_templates (
    template_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    display_name        VARCHAR(200)    NOT NULL,
    display_name_vi     VARCHAR(200)    NOT NULL,
    description         TEXT,

    department_type     VARCHAR(32)     NOT NULL,
    category            VARCHAR(50),

    -- The pre-built nodes + edges. Shape:
    --   {
    --     "nodes": [
    --       {
    --         "client_id": "n1",   <-- referenced by edges; replaced with real UUID on clone
    --         "title": "Lead intake",
    --         "title_vi": "Tiếp nhận lead",
    --         "note": "Nhận lead từ web + Zalo OA",
    --         "hashtags": ["prospect_data"],
    --         "required_document_types": [{"kind":"csv","name":"Lead list","required":true}],
    --         "sequence_order": 1,
    --         "position_x": 100, "position_y": 100
    --       }, ...
    --     ],
    --     "edges": [
    --       {"source_client_id": "n1", "target_client_id": "n2", "label": "qualified"}
    --     ]
    --   }
    workflow_definition  JSONB          NOT NULL,

    estimated_setup_minutes  INTEGER    NOT NULL DEFAULT 5,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_workflow_template_dept CHECK (department_type IN (
        'marketing', 'sales', 'customer_service', 'warehouse', 'hr', 'finance', 'custom'
    ))
);

CREATE INDEX IF NOT EXISTS idx_workflow_templates_dept
    ON workflow_templates (department_type, is_active)
    WHERE is_active = TRUE;

-- ─── 6. RLS — K-1 + ABAC dept_scope ──────────────────────────────────

ALTER TABLE workflows                ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_nodes           ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_edges           ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_step_documents  ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'workflows', 'workflow_nodes', 'workflow_step_documents'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS isolation_%I ON %I', tbl, tbl);
        EXECUTE format($f$
            CREATE POLICY isolation_%I ON %I
                USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
                WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true))
        $f$, tbl, tbl);

        EXECUTE format('DROP POLICY IF EXISTS abac_dept_scope_%I ON %I', tbl, tbl);
        EXECUTE format($f$
            CREATE POLICY abac_dept_scope_%I ON %I
                USING (
                    enterprise_id::text = current_setting('app.current_enterprise_id', true)
                    AND (
                        current_setting('app.current_department_id', true) = ''
                        OR current_setting('app.current_department_id', true) IS NULL
                        OR department_id::text = current_setting('app.current_department_id', true)
                    )
                )
        $f$, tbl, tbl);
    END LOOP;
END $$;

-- workflow_edges policy (no department_id column — inherits via workflow_id).
DROP POLICY IF EXISTS isolation_workflow_edges ON workflow_edges;
CREATE POLICY isolation_workflow_edges ON workflow_edges
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

-- ─── 7. kaori_app grants ─────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflows               TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_nodes          TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_edges          TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_step_documents TO kaori_app';
        EXECUTE 'GRANT SELECT                          ON workflow_templates     TO kaori_app';
    END IF;
END $$;

-- ─── 8. Comments ─────────────────────────────────────────────────────

COMMENT ON TABLE workflows IS
    'P15-S11 mig 053 — workflow-as-data per docx 4Kaori_AI_Workflow_System v2.0 PART V. '
    'Each workflow = digital twin of a department process; user builds via drag-drop FE. '
    'Phase 1 = file-organizing shell over the existing Bronze/Silver/Gold pipeline; '
    'Phase 2 wires Temporal execution engine.';
COMMENT ON TABLE workflow_nodes IS
    'P15-S11 mig 053 — "card" in anh''s vocabulary. Phase 1 ships type=''step'' only '
    '(document-collecting card). Phase 2 unlocks the 45-node-type catalog from docx Phần 2.';
COMMENT ON COLUMN workflow_nodes.required_document_types IS
    'JSONB list of expected documents. Shape: [{"kind":"csv","name":"...","required":true}].';
COMMENT ON COLUMN workflow_nodes.expected_mapping_template_id IS
    'When user uploads into this card, Bronze ingestor uses THIS mapping_template '
    'instead of the filename-glob auto-match. Skips Stage 2C guessing.';
COMMENT ON TABLE workflow_step_documents IS
    'P15-S11 mig 053 — fulfils anh''s "data sẽ được lưu theo sơ đồ tree". Every Bronze '
    'upload through a workflow step gets a row here; FE tree viewer joins workflows → '
    'workflow_nodes → these.';
COMMENT ON TABLE workflow_templates IS
    'P15-S11 mig 053 — global template library per docx Phần 17.1. 30 templates '
    '(5 per dept × 6 dept_types) seeded by mig 054. Cloning creates real workflows '
    'rows with provenance via workflows.cloned_from_template_id.';
