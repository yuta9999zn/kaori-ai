-- =====================================================================
-- 101_industry_templates.sql — Phase 2.8 D1 — Industry Template Foundation
--
-- Anh's request 2026-05-20:
--   "Workflow chưa rõ vật thể, card và nhánh chưa rõ. Tạo template
--   theo phòng ban. Có cấu hình chuẩn cho doanh nghiệp theo mảng/
--   ngành (Industry → Department → Workflow Template). 3-tier:
--   chọn ngành → sinh phòng ban mẫu → sinh workflow mẫu → user chỉnh."
--
-- Existing baseline (Phase 1 + 2):
--   • mig 053 — workflows / workflow_nodes / workflow_edges (per-card
--     schema: title + note + hashtags + required_document_types +
--     expected_mapping_template_id).
--   • mig 054 — 18 workflow_templates seeded per department_type.
--   • mig 068 — 45-row node_type_catalog (side_effect_class K-17).
--   • mig 069 — 25 production templates × industry_vertical tag.
--   • mig 061 — department_role_templates (dept_type × seniority).
--
-- What THIS mig adds (the missing top tier — INDUSTRY):
--   • industry_templates — 8 industries (Retail / F&B / Logistics /
--     Finance / Healthcare / Manufacturing / Education / Generic SME)
--     each with default branding + KPI focus + AI confidence threshold.
--   • industry_department_templates — per-industry default depts (e.g.
--     Retail → Sales, Marketing, Warehouse, Finance, CS, Mgmt).
--   • industry_workflow_links — which workflow_templates belong to which
--     (industry, department) pair. Lets ONE template serve multiple
--     industries (e.g. "Invoice Processing" works for Retail + Finance).
--   • industry_kpi_templates — per (industry, department) KPI suggestion
--     (revenue / margin / churn / stockout risk / payment delay / etc).
--   • industry_data_schema_templates — per (industry, department) data
--     source expectation (CSV columns, file kinds, upload required-list).
--   • industry_role_permission_templates — per industry default
--     permission matrix (extends mig 061 role taxonomy).
--
-- Design decision: NO RLS on industry_* tables.
--   These are PLATFORM-SHARED reference data (same pattern as
--   department_role_templates mig 061, node_type_catalog mig 068,
--   workflow_templates mig 053). Every tenant reads the same catalog.
--   Tenant-specific customization lives in customer_workflow_versions
--   + workflow_customizations (mig 102).
--
-- K-rule compliance:
--   K-1 RLS: not applicable — platform reference.
--   K-17 side_effect_class: industry_workflow_links has no executors;
--                            workflow_templates already declare it.
--   K-19 OpenTelemetry: industry bootstrap router emits tenant_id span.
-- =====================================================================

-- ─── 1. industry_templates (top tier — 8 industries) ─────────────────

CREATE TABLE IF NOT EXISTS industry_templates (
    industry_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    industry_key             VARCHAR(32)     NOT NULL UNIQUE,         -- 'retail', 'fnb', 'logistics', ...

    display_name             VARCHAR(100)    NOT NULL,
    display_name_vi          VARCHAR(100)    NOT NULL,
    description              TEXT,
    description_vi           TEXT,

    -- Visual hint for FE picker (industry chooser screen).
    icon_key                 VARCHAR(50),                              -- 'shopping-bag', 'utensils', ...
    accent_color             VARCHAR(7),                               -- '#FF6B6B' for FE branding chip

    -- KPI focus (top 3-5 KPIs this industry usually tracks; FE shows them
    -- on the bootstrap confirmation screen).
    primary_kpis             TEXT[]          NOT NULL DEFAULT '{}',    -- ['revenue', 'gross_margin', 'churn_rate', ...]

    -- AI defaults for this industry. Confidence threshold tuned per
    -- vertical — e.g. healthcare needs higher threshold than retail.
    ai_confidence_threshold  NUMERIC(5,4)    NOT NULL DEFAULT 0.7000,
    ai_consent_external_default BOOLEAN      NOT NULL DEFAULT FALSE,   -- K-4: opt-in even per industry

    -- NOV / billing tier hint (which plan most customers in this
    -- industry choose). FE uses this for upsell recommendation.
    suggested_pricing_plan   VARCHAR(20),                              -- 'PILOT' | 'ENT_BASIC' | 'ENT_MID' | 'ENT_MAX'

    -- Compliance hint — Healthcare needs HIPAA-equiv, Finance needs
    -- audit retention 7y, etc. Free text, FE renders as warning chip.
    compliance_notes_vi      TEXT,

    is_active                BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_industry_pricing CHECK (
        suggested_pricing_plan IS NULL OR
        suggested_pricing_plan IN ('PILOT', 'ENT_BASIC', 'ENT_MID', 'ENT_MAX')
    ),
    CONSTRAINT chk_industry_conf_range CHECK (
        ai_confidence_threshold >= 0 AND ai_confidence_threshold <= 1
    )
);

CREATE INDEX IF NOT EXISTS idx_industry_templates_active
    ON industry_templates (is_active)
    WHERE is_active = TRUE;


-- ─── 2. industry_department_templates ────────────────────────────────
--
-- Per-industry default department list. When bootstrap-from-industry
-- runs, these dept records are CLONED into the enterprise's
-- departments table (with the enterprise_id stamped).

CREATE TABLE IF NOT EXISTS industry_department_templates (
    template_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    industry_id          UUID            NOT NULL REFERENCES industry_templates(industry_id) ON DELETE CASCADE,

    dept_key             VARCHAR(50)     NOT NULL,                    -- 'sales', 'warehouse', 'finance', 'cs', ...
    dept_type            VARCHAR(32)     NOT NULL,                    -- matches department_role_templates.dept_type

    display_name         VARCHAR(100)    NOT NULL,
    display_name_vi      VARCHAR(100)    NOT NULL,
    description_vi       TEXT,

    -- Display order in FE org-chart picker.
    sequence_order       INTEGER         NOT NULL DEFAULT 0,

    -- Is this dept REQUIRED for the industry, or OPTIONAL?
    -- Bootstrap auto-creates REQUIRED; OPTIONAL = checkbox in wizard.
    is_required          BOOLEAN         NOT NULL DEFAULT TRUE,

    -- Default seniority distribution hint (FE shows "this dept usually
-- has 1 manager + 2-5 operators + 1-2 analysts").
    suggested_headcount  JSONB           NOT NULL DEFAULT '{}'::jsonb,

    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_industry_dept_key UNIQUE (industry_id, dept_key)
);

CREATE INDEX IF NOT EXISTS idx_industry_dept_industry
    ON industry_department_templates (industry_id, sequence_order);


-- ─── 3. industry_workflow_links ──────────────────────────────────────
--
-- Many-to-many bridge: which workflow_template belongs to which
-- (industry, department) pair. ONE template can serve multiple
-- industries — e.g. "Invoice Processing" appears in BOTH Retail/Finance
-- and Generic-SME/Finance.

CREATE TABLE IF NOT EXISTS industry_workflow_links (
    link_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    industry_id          UUID            NOT NULL REFERENCES industry_templates(industry_id)          ON DELETE CASCADE,
    industry_dept_id     UUID            NOT NULL REFERENCES industry_department_templates(template_id) ON DELETE CASCADE,
    workflow_template_id UUID            NOT NULL REFERENCES workflow_templates(template_id)         ON DELETE CASCADE,

    -- Recommendation level (controls FE ordering on the workflow picker).
    -- 'core'      = ship this on bootstrap automatically
    -- 'suggested' = show with checkbox, default unchecked
    -- 'advanced'  = hide behind "Show all" toggle
    recommendation_level VARCHAR(20)     NOT NULL DEFAULT 'core',

    sequence_order       INTEGER         NOT NULL DEFAULT 0,

    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_iw_recommendation CHECK (
        recommendation_level IN ('core', 'suggested', 'advanced')
    ),
    CONSTRAINT uq_industry_workflow UNIQUE (industry_id, industry_dept_id, workflow_template_id)
);

CREATE INDEX IF NOT EXISTS idx_industry_workflow_industry
    ON industry_workflow_links (industry_id, recommendation_level, sequence_order);


-- ─── 4. industry_kpi_templates ───────────────────────────────────────
--
-- Per (industry, department) KPI catalog. FE renders these on the
-- department dashboard after bootstrap. Each KPI carries a default
-- threshold so AI alerts can fire from day-1 without per-tenant tuning.

CREATE TABLE IF NOT EXISTS industry_kpi_templates (
    kpi_template_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    industry_id          UUID            NOT NULL REFERENCES industry_templates(industry_id)            ON DELETE CASCADE,
    industry_dept_id     UUID            REFERENCES industry_department_templates(template_id)          ON DELETE CASCADE,
    -- dept NULL = industry-wide KPI (revenue, churn) shared across depts.

    kpi_key              VARCHAR(64)     NOT NULL,                    -- 'revenue_monthly', 'churn_rate', ...
    display_name         VARCHAR(100)    NOT NULL,
    display_name_vi      VARCHAR(100)    NOT NULL,
    description_vi       TEXT,

    -- Computation hint (free text — Stage 9 KPI engine reads this).
    computation_hint     TEXT,                                         -- 'SUM(sales.amount) WHERE month = current'

    unit                 VARCHAR(20)     NOT NULL,                    -- 'VND', 'pct', 'count', 'days', ...

    -- Default alert thresholds (FE shows as suggestion; analyst tunes).
    threshold_warning    NUMERIC(20,4),
    threshold_critical   NUMERIC(20,4),
    higher_is_better     BOOLEAN         NOT NULL DEFAULT TRUE,

    sequence_order       INTEGER         NOT NULL DEFAULT 0,
    is_primary           BOOLEAN         NOT NULL DEFAULT FALSE,      -- "top 3" highlighted KPIs

    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_industry_kpi_key UNIQUE (industry_id, industry_dept_id, kpi_key)
);

CREATE INDEX IF NOT EXISTS idx_industry_kpi_industry
    ON industry_kpi_templates (industry_id, industry_dept_id, sequence_order);


-- ─── 5. industry_data_schema_templates ───────────────────────────────
--
-- Per (industry, department) data source expectation. Tells the FE:
-- "to make this workflow useful, you'll need to upload these files".
-- Pipeline ingestor (Stage 1) cross-checks the upload against this
-- template to know what to expect.

CREATE TABLE IF NOT EXISTS industry_data_schema_templates (
    schema_template_id   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    industry_id          UUID            NOT NULL REFERENCES industry_templates(industry_id)            ON DELETE CASCADE,
    industry_dept_id     UUID            REFERENCES industry_department_templates(template_id)          ON DELETE CASCADE,

    schema_key           VARCHAR(64)     NOT NULL,                    -- 'customers', 'orders', 'inventory', ...
    display_name_vi      VARCHAR(100)    NOT NULL,
    description_vi       TEXT,

    -- Required columns (schema validation hint). Shape:
    --   [{"name": "customer_id", "type": "string", "required": true},
    --    {"name": "amount",      "type": "numeric", "required": true},
    --    {"name": "order_date",  "type": "date",    "required": false}]
    column_schema        JSONB           NOT NULL DEFAULT '[]'::jsonb,

    -- File kinds the user should upload (csv / xlsx / json).
    expected_file_kinds  TEXT[]          NOT NULL DEFAULT ARRAY['csv'],

    -- Path to a sample file the user can download to see the format.
    sample_file_path     TEXT,                                         -- 'samples/retail/customers.csv'

    is_required          BOOLEAN         NOT NULL DEFAULT TRUE,
    sequence_order       INTEGER         NOT NULL DEFAULT 0,

    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_industry_schema_key UNIQUE (industry_id, industry_dept_id, schema_key)
);

CREATE INDEX IF NOT EXISTS idx_industry_schema_industry
    ON industry_data_schema_templates (industry_id, industry_dept_id, sequence_order);


-- ─── 6. industry_role_permission_templates ───────────────────────────
--
-- Per (industry, dept_type, seniority) → role + permissions. Extends
-- mig 061 department_role_templates which only maps (dept_type ×
-- seniority → P2 role); this layer adds per-industry tuning of which
-- permissions that role gets.
--
-- Out-of-scope: per-permission granularity full ABAC (Hướng B Phase 2).
-- This v0 stores the suggested permission BITMASK as a TEXT array
-- (cfg['permissions']) — Phase 2 PDP will read these as ABAC inputs.

CREATE TABLE IF NOT EXISTS industry_role_permission_templates (
    permission_template_id  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    industry_id          UUID            NOT NULL REFERENCES industry_templates(industry_id) ON DELETE CASCADE,

    dept_type            VARCHAR(32)     NOT NULL,                    -- 'sales', 'finance', 'hr', ...
    seniority_level      VARCHAR(20)     NOT NULL,                    -- 'entry', 'junior', 'mid', 'senior', 'executive'
    default_role         VARCHAR(20)     NOT NULL,                    -- 'MANAGER', 'OPERATOR', 'ANALYST', 'VIEWER'

    -- Suggested permission keys for this role in this industry.
    -- FE renders as checkbox list during onboarding wizard.
    permission_keys      TEXT[]          NOT NULL DEFAULT '{}',       -- ['approve_invoices', 'view_payroll', ...]

    -- Override hint: can the manager change this binding from the UI?
    overridable          BOOLEAN         NOT NULL DEFAULT TRUE,

    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_industry_perm UNIQUE (industry_id, dept_type, seniority_level),
    CONSTRAINT chk_industry_role CHECK (
        default_role IN ('MANAGER', 'OPERATOR', 'ANALYST', 'VIEWER')
    )
);

CREATE INDEX IF NOT EXISTS idx_industry_role_industry
    ON industry_role_permission_templates (industry_id, dept_type);


-- ─── Convenience view: industry overview ─────────────────────────────

CREATE OR REPLACE VIEW v_industry_overview AS
SELECT
    i.industry_id,
    i.industry_key,
    i.display_name_vi,
    i.primary_kpis,
    i.suggested_pricing_plan,
    (SELECT COUNT(*) FROM industry_department_templates d WHERE d.industry_id = i.industry_id) AS dept_count,
    (SELECT COUNT(*) FROM industry_workflow_links l WHERE l.industry_id = i.industry_id AND l.recommendation_level = 'core') AS core_workflow_count,
    (SELECT COUNT(*) FROM industry_workflow_links l WHERE l.industry_id = i.industry_id) AS total_workflow_count,
    (SELECT COUNT(*) FROM industry_kpi_templates k WHERE k.industry_id = i.industry_id) AS kpi_count,
    (SELECT COUNT(*) FROM industry_data_schema_templates s WHERE s.industry_id = i.industry_id) AS schema_count
FROM industry_templates i
WHERE i.is_active = TRUE
ORDER BY i.industry_key;


COMMENT ON TABLE industry_templates                  IS 'Phase 2.8 — 8-industry catalog (top tier of Industry → Dept → Workflow). Platform-shared reference, no RLS.';
COMMENT ON TABLE industry_department_templates       IS 'Phase 2.8 — Per-industry default department list. Cloned into enterprise.departments on bootstrap.';
COMMENT ON TABLE industry_workflow_links             IS 'Phase 2.8 — Many-to-many bridge industry × dept × workflow_template.';
COMMENT ON TABLE industry_kpi_templates              IS 'Phase 2.8 — Per (industry, dept) KPI suggestion with default thresholds.';
COMMENT ON TABLE industry_data_schema_templates      IS 'Phase 2.8 — Per (industry, dept) expected data sources / column schema / sample file.';
COMMENT ON TABLE industry_role_permission_templates  IS 'Phase 2.8 — Per (industry, dept_type, seniority) → role + permission keys. Extends mig 061.';
