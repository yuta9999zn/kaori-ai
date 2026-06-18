-- 048_mapping_templates.sql — P15-S11 Tuần 7 ngày 3.
--
-- Re-usable schema mapping templates per Pipeline_Unified.docx §2.3.
-- Workflow:
--   1. User uploads file → Stage 2 detects schema → user confirms / fixes.
--   2. The confirmed (column_mapping, file_pattern, source_id) tuple
--      is saved as a mapping_template.
--   3. Next upload matching the file_pattern auto-loads the template
--      so the user only confirms changes (or accepts as-is).
--
-- Scope: department + source (anh chốt D3: dept-scope). Same source
-- under different departments can have different templates because
-- the columns map to different business domains.
--
-- The column_mapping JSONB shape mirrors the Stage 2C confirmation
-- payload from services/data-pipeline/routers/schema.py — so a future
-- /schema/save-template endpoint can write this row directly without
-- shape translation.

CREATE TABLE IF NOT EXISTS mapping_templates (
    template_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID            NOT NULL REFERENCES enterprises(enterprise_id)   ON DELETE CASCADE,
    department_id    UUID            NOT NULL REFERENCES departments(department_id)   ON DELETE CASCADE,
    source_id        UUID            NOT NULL REFERENCES data_sources(source_id)      ON DELETE CASCADE,

    -- Pattern matching: simple glob (customers_*.csv, transactions_*.xlsx).
    -- Multiple uploads matching the same pattern auto-apply this template.
    name             VARCHAR(200)    NOT NULL,
    file_pattern     VARCHAR(200)    NOT NULL,
    file_kind        VARCHAR(20)     NOT NULL,         -- 'csv' | 'xlsx' | 'xls' | 'json'

    -- Confirmed schema mapping. Shape:
    --   {
    --     "encoding": "utf-8",
    --     "delimiter": ",",
    --     "header_row": 1,
    --     "junk_rows_handling": "skip_summary_footer",
    --     "columns": [
    --       {
    --         "source_name": "ma_kh",
    --         "canonical_name": "customer_id",
    --         "data_type": "string",
    --         "required": true,
    --         "ai_confidence": 0.95,
    --         "user_confirmed": true,
    --         "transformations": ["trim", "uppercase"]
    --       },
    --       ...
    --     ]
    --   }
    column_mapping   JSONB           NOT NULL,

    -- Domain hint — Marketing's customer_id is the same customer as
    -- Sales's, but the column_mapping may differ because the source
    -- files differ.
    domain           VARCHAR(40),                      -- 'retail' | 'b2b' | 'service' | 'manufacturing' | 'ecommerce'

    -- Telemetry — used by recommendation engine ("90% of customers in
    -- your industry use this template for KiotViet customers").
    created_by_user  UUID,                             -- enterprise_users FK soft-link
    confirmed_count  INTEGER         NOT NULL DEFAULT 0,
    last_used_at     TIMESTAMPTZ,
    is_active        BOOLEAN         NOT NULL DEFAULT TRUE,

    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_template_name_per_source UNIQUE (enterprise_id, department_id, source_id, name),
    CONSTRAINT chk_template_file_kind CHECK (file_kind IN ('csv', 'xlsx', 'xls', 'json', 'tsv'))
);

-- Hot lookup: "on upload, find templates whose pattern matches this filename".
CREATE INDEX IF NOT EXISTS idx_mapping_templates_pattern_lookup
    ON mapping_templates (enterprise_id, source_id, is_active, file_pattern);

-- Recent-templates listing (FE Schema Mapping page sidebar).
CREATE INDEX IF NOT EXISTS idx_mapping_templates_recent
    ON mapping_templates (enterprise_id, department_id, last_used_at DESC NULLS LAST)
    WHERE is_active = TRUE;

-- RLS K-1 (sibling abac_dept_scope handled by middleware GUC).
ALTER TABLE mapping_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_mapping_templates ON mapping_templates;
CREATE POLICY isolation_mapping_templates ON mapping_templates
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        AND (
            current_setting('app.current_department_id', true) = ''
            OR current_setting('app.current_department_id', true) IS NULL
            OR department_id::text = current_setting('app.current_department_id', true)
        )
    )
    WITH CHECK (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
    );

COMMENT ON TABLE  mapping_templates IS
    'P15-S11 Tuần 7 — re-usable schema mapping templates per spec §2.3. Scope = enterprise × department × source.';
COMMENT ON COLUMN mapping_templates.file_pattern IS
    'Glob pattern (customers_*.csv). On upload, the schema endpoint matches filename against active templates and pre-fills the mapping confirmation form.';
COMMENT ON COLUMN mapping_templates.column_mapping IS
    'JSONB mirror of the Stage 2C user-confirmation payload — encoding, delimiter, header_row, columns[]. Shape matches /schema/confirm request body.';
COMMENT ON COLUMN mapping_templates.confirmed_count IS
    'Increments each time this template is auto-applied AND the user confirms without overrides. Drives the recommendation engine ("90% of retail SMEs use this template").';
