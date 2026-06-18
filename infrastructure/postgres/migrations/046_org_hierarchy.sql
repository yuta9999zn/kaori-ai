-- 046_org_hierarchy.sql — P15-S11 Tuần 7 Build Week prep.
--
-- Adds the multi-branch / multi-department / data-source hierarchy that
-- Pipeline_Unified.docx §1.1 describes but the schema never modelled.
-- Anh chốt 3-cấp: enterprise → branch → department, with 6 default
-- department types (Marketing/Sales/CS/Warehouse/HR/Finance) plus
-- customer-defined custom departments.
--
-- Per spec §16.4 ABAC: data tables (bronze/silver/gold) gain a
-- department_id column in migration 047, and RLS extends to enforce
-- per-department scope where the policy requires it (Marketing Manager
-- sees Marketing data only).
--
-- One default branch per enterprise (`Trụ sở chính` / 'MAIN') is
-- auto-seeded so single-office SMEs don't have to think about branches.
-- The UI can hide the branch picker entirely when only the default
-- branch exists.

-- ─── 1. branches ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS branches (
    branch_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    name            VARCHAR(200)    NOT NULL,
    code            VARCHAR(50),                     -- short code, e.g. 'HN' / 'HCM' / 'DN'
    is_default      BOOLEAN         NOT NULL DEFAULT FALSE,
    timezone        VARCHAR(50)     NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    address         VARCHAR(500),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_branch_name_per_enterprise UNIQUE (enterprise_id, name),
    CONSTRAINT chk_branch_status CHECK (status IN ('active', 'suspended', 'closed'))
);

-- Only one default branch per enterprise — partial unique index avoids
-- accidentally having two "main" branches after migration.
CREATE UNIQUE INDEX IF NOT EXISTS uq_branches_one_default_per_enterprise
    ON branches (enterprise_id)
    WHERE is_default = TRUE;

CREATE INDEX IF NOT EXISTS idx_branches_enterprise_status
    ON branches (enterprise_id, status);

-- ─── 2. departments ──────────────────────────────────────────────────
--
-- 6 default types + 'custom' for tenant-defined departments (e.g.
-- 'Logistics', 'IT', 'Compliance'). Default reports key off dept_type;
-- custom departments get the universal Bronze/Silver/Gold view set but
-- not the per-dept Gold customisations.

CREATE TABLE IF NOT EXISTS departments (
    department_id   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    branch_id       UUID            REFERENCES branches(branch_id) ON DELETE SET NULL,
    name            VARCHAR(200)    NOT NULL,
    dept_type       VARCHAR(32)     NOT NULL,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    manager_user_id UUID,                            -- optional FK to enterprise_users — soft link
    pii_sensitivity VARCHAR(20)     NOT NULL DEFAULT 'normal',
    description     TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dept_name_per_branch UNIQUE (enterprise_id, branch_id, name),
    CONSTRAINT chk_dept_type CHECK (dept_type IN (
        'marketing', 'sales', 'customer_service',
        'warehouse', 'hr', 'finance', 'custom'
    )),
    CONSTRAINT chk_dept_status CHECK (status IN ('active', 'archived')),
    CONSTRAINT chk_dept_pii CHECK (pii_sensitivity IN ('low', 'normal', 'high', 'restricted'))
);

CREATE INDEX IF NOT EXISTS idx_departments_enterprise_type
    ON departments (enterprise_id, dept_type, status);

CREATE INDEX IF NOT EXISTS idx_departments_branch
    ON departments (branch_id)
    WHERE branch_id IS NOT NULL;

-- ─── 3. data_sources ─────────────────────────────────────────────────
--
-- Per spec §1.1: every department has 1+ data sources. Each source is
-- a logical container with its own mapping templates and quota.

CREATE TABLE IF NOT EXISTS data_sources (
    source_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    department_id   UUID            NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE,
    name            VARCHAR(200)    NOT NULL,
    source_kind     VARCHAR(32)     NOT NULL,
    config          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_source_name_per_dept UNIQUE (enterprise_id, department_id, name),
    CONSTRAINT chk_source_kind CHECK (source_kind IN (
        'manual_upload', 'kiotviet', 'zalo_oa', 'google_calendar',
        'gmail', 'outlook', 'sapo', 'haravan', 'shopee', 'lazada',
        'custom_api', 'csv_sftp'
    )),
    CONSTRAINT chk_source_status CHECK (status IN ('active', 'paused', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_data_sources_dept_kind
    ON data_sources (department_id, source_kind);

CREATE INDEX IF NOT EXISTS idx_data_sources_enterprise_status
    ON data_sources (enterprise_id, status);

-- ─── 4. RLS — K-1 enterprise isolation ───────────────────────────────

ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_branches ON branches;
CREATE POLICY isolation_branches ON branches
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DROP POLICY IF EXISTS isolation_departments ON departments;
CREATE POLICY isolation_departments ON departments
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DROP POLICY IF EXISTS isolation_data_sources ON data_sources;
CREATE POLICY isolation_data_sources ON data_sources
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

-- ─── 5. Backfill — seed 1 default branch + 6 default departments per existing enterprise ─

-- Default branch ("Trụ sở chính" = main office). Idempotent via the
-- partial unique index on (enterprise_id, is_default=true).
INSERT INTO branches (enterprise_id, name, code, is_default, address)
SELECT e.enterprise_id, 'Trụ sở chính', 'MAIN', TRUE, NULL
FROM enterprises e
WHERE NOT EXISTS (
    SELECT 1 FROM branches b
    WHERE b.enterprise_id = e.enterprise_id AND b.is_default = TRUE
);

-- 6 default departments per enterprise, attached to the default branch.
INSERT INTO departments (enterprise_id, branch_id, name, dept_type, description)
SELECT
    e.enterprise_id,
    b.branch_id,
    dn.dept_name,
    dn.dept_type,
    dn.dept_desc
FROM enterprises e
JOIN branches b ON b.enterprise_id = e.enterprise_id AND b.is_default = TRUE
CROSS JOIN (
    VALUES
        ('Marketing',         'marketing',         'Tiếp thị + campaign + LTV'),
        ('Sales',             'sales',             'Bán hàng + pipeline + deal'),
        ('Customer Service',  'customer_service',  'CSKH + ticket + CSAT'),
        ('Warehouse',         'warehouse',         'Kho + tồn kho + xuất nhập'),
        ('HR',                'hr',                'Nhân sự + payroll'),
        ('Finance',           'finance',           'Tài chính + AR + cash flow')
) AS dn(dept_name, dept_type, dept_desc)
ON CONFLICT (enterprise_id, branch_id, name) DO NOTHING;

-- Default `Manual upload` data source per department so the existing
-- upload endpoint has a source_id to attribute uploads to.
INSERT INTO data_sources (enterprise_id, department_id, name, source_kind)
SELECT d.enterprise_id, d.department_id, 'Manual upload', 'manual_upload'
FROM departments d
ON CONFLICT (enterprise_id, department_id, name) DO NOTHING;

-- ─── 6. Comments — surfaces in psql \d+ and pgAdmin ──────────────────

COMMENT ON TABLE  branches IS
    'P15-S11 — chi nhánh under enterprise. 1 default per enterprise auto-seeded as "Trụ sở chính".';
COMMENT ON TABLE  departments IS
    'P15-S11 — phòng ban under branch (or directly under enterprise via branch_id=NULL). 6 default dept_types + custom per spec §1.1.';
COMMENT ON COLUMN departments.dept_type IS
    'Drives per-department Gold view routing (§8.3): marketing → gold.customer_360_marketing, etc. ''custom'' uses universal views only.';
COMMENT ON COLUMN departments.pii_sensitivity IS
    'ABAC §16.4 — restricted = only DEPT_MANAGER reads PII fields; high = MANAGER+ANALYST; normal = all dept members; low = no PII present.';
COMMENT ON TABLE  data_sources IS
    'P15-S11 — connector/source registry. 1 default ''Manual upload'' per dept; KiotViet/Zalo/etc populated by Connector wizard.';
