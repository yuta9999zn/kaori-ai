-- =====================================================================
-- 061_department_role_templates.sql
--
-- P15-S11 — Hướng A: RBAC tĩnh per (dept_type × seniority_level).
-- Anh's decision 2026-05-16: ship A first (1.5-2 ngày), defer B
-- (RBAC + ABAC + PDP per SAD v2 Phần 6) to Phase 2 P2-S13+.
--
-- Purpose
-- -------
-- When an HR onboarding workflow approves a new employee, the system
-- needs to assign them a P2 role (MANAGER / OPERATOR / ANALYST /
-- VIEWER) WITHOUT requiring the approver to pick it manually. This
-- table maps `(dept_type, seniority_level) → default_role` so the
-- approval handler can derive the right role.
--
-- Schema
-- ------
-- * `enterprise_id NULL` = global default (35 seed rows for 7 dept_types
--   × 5 seniority levels). The lookup falls back to this when no
--   enterprise-specific override exists.
-- * `enterprise_id IS NOT NULL` = enterprise-level override. Future
--   capability — pilot doesn't seed any; left in the schema so we don't
--   need a follow-up migration when the first enterprise asks "we want
--   our finance entry to start as ANALYST, not OPERATOR".
--
-- Out-of-scope for A (deferred to Hướng B / Phase 2):
--   • Per-permission granularity (just maps to 4 existing role codes —
--     no fine-grained `approve_invoices` / `view_payroll` toggles).
--   • Cross-branch scoping ("user can approve only own branch").
--   • Time-bound roles ("temporary acting MANAGER during vacation").
--   • Delegation.
--
-- K-1 / K-19 compliance
-- ---------------------
-- This is platform-shared reference data, not tenant-scoped. RLS is
-- NOT enabled — every enterprise sees the same global defaults. When
-- enterprise overrides are added, RLS will be enabled at that point
-- (next migration; not today).
--
-- Tests
-- -----
-- * `tests/test_mig_061_role_templates_shape.py` (data-pipeline) —
--   asserts 35 global rows seeded, all CHECK constraints fire, lookup
--   query (enterprise-first then global) returns expected row.
-- =====================================================================

CREATE TABLE IF NOT EXISTS department_role_templates (
    template_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- NULL = global default. Non-null = enterprise-specific override
    -- shadowing the global row with the same (dept_type, seniority).
    enterprise_id    UUID            REFERENCES enterprises(enterprise_id)
                                     ON DELETE CASCADE,

    dept_type        VARCHAR(32)     NOT NULL,
    seniority_level  VARCHAR(20)     NOT NULL,
    default_role     VARCHAR(20)     NOT NULL,

    -- Manager-overridable: when false, the approval workflow won't show
    -- the "đổi role" link to the approver — they get the templated role
    -- and that's it. For sensitive depts (finance / hr executive) we
    -- DO want manager override available, so this stays TRUE by default.
    overridable      BOOLEAN         NOT NULL DEFAULT TRUE,

    description_vi   TEXT,
    is_active        BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_drt_dept_type CHECK (dept_type IN (
        'marketing', 'sales', 'customer_service',
        'warehouse', 'hr', 'finance', 'custom'
    )),
    CONSTRAINT chk_drt_seniority CHECK (seniority_level IN (
        'entry', 'junior', 'mid', 'senior', 'executive'
    )),
    -- Mirror enterprise_users.chk_user_role exactly — if 001_init adds
    -- a role, this constraint must move too.
    CONSTRAINT chk_drt_role CHECK (default_role IN (
        'MANAGER', 'OPERATOR', 'ANALYST', 'VIEWER'
    ))
);

-- One row per (dept_type, seniority) at the global tier, and one per
-- (enterprise, dept_type, seniority) at the override tier. Postgres
-- treats multiple NULL enterprise_ids as distinct under a plain UNIQUE,
-- so split into two partial indexes.
CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_global
    ON department_role_templates (dept_type, seniority_level)
    WHERE enterprise_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_drt_per_enterprise
    ON department_role_templates (enterprise_id, dept_type, seniority_level)
    WHERE enterprise_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_drt_lookup
    ON department_role_templates (dept_type, seniority_level, is_active);


-- =====================================================================
-- Global seed defaults (7 dept_types × 5 seniority = 35 rows)
-- ---------------------------------------------------------------------
-- Reasoning per role:
--   VIEWER   = read-only, lowest scope
--   OPERATOR = day-to-day ops, can write
--   ANALYST  = read + analysis across own dept's data
--   MANAGER  = full dept admin (people + write paths)
-- Executive is always MANAGER (department head).
-- Entry/junior in customer-facing depts (marketing/sales/CS) start
-- conservative; finance entry stays OPERATOR (not VIEWER) because
-- A/R clerks need write to log payments.
-- =====================================================================

INSERT INTO department_role_templates
    (enterprise_id, dept_type, seniority_level, default_role, description_vi)
VALUES
    -- Marketing
    (NULL, 'marketing',       'entry',     'VIEWER',   'Thực tập / mới vào — chỉ xem.'),
    (NULL, 'marketing',       'junior',    'VIEWER',   'Nhân viên junior — chỉ xem báo cáo.'),
    (NULL, 'marketing',       'mid',       'ANALYST',  'Chuyên viên — xem + chạy phân tích.'),
    (NULL, 'marketing',       'senior',    'ANALYST',  'Chuyên viên cấp cao — phân tích sâu.'),
    (NULL, 'marketing',       'executive', 'MANAGER',  'Trưởng phòng / Giám đốc — quản lý toàn phòng.'),

    -- Sales
    (NULL, 'sales',           'entry',     'OPERATOR', 'Nhân viên mới — nhập deal, ghi note.'),
    (NULL, 'sales',           'junior',    'OPERATOR', 'Nhân viên junior — chăm sóc KH.'),
    (NULL, 'sales',           'mid',       'ANALYST',  'Account Manager — phân tích pipeline.'),
    (NULL, 'sales',           'senior',    'ANALYST',  'Senior AM — phân tích + forecast.'),
    (NULL, 'sales',           'executive', 'MANAGER',  'Giám đốc Sales — quản lý team.'),

    -- Customer Service
    (NULL, 'customer_service','entry',     'OPERATOR', 'CSKH mới — xử lý ticket.'),
    (NULL, 'customer_service','junior',    'OPERATOR', 'CSKH junior — xử lý ticket.'),
    (NULL, 'customer_service','mid',       'OPERATOR', 'CSKH mid — xử lý ticket + escalate.'),
    (NULL, 'customer_service','senior',    'ANALYST',  'CSKH lead — phân tích SLA, NPS.'),
    (NULL, 'customer_service','executive', 'MANAGER',  'Trưởng CSKH — quản lý team + SLA.'),

    -- Warehouse / Kho vận
    (NULL, 'warehouse',       'entry',     'OPERATOR', 'Nhân viên kho — nhập/xuất.'),
    (NULL, 'warehouse',       'junior',    'OPERATOR', 'Nhân viên kho junior.'),
    (NULL, 'warehouse',       'mid',       'OPERATOR', 'Tổ trưởng — điều phối kho.'),
    (NULL, 'warehouse',       'senior',    'OPERATOR', 'Trưởng ca — điều phối ca.'),
    (NULL, 'warehouse',       'executive', 'MANAGER',  'Giám đốc kho vận.'),

    -- HR (sensitive — bump up faster)
    (NULL, 'hr',              'entry',     'OPERATOR', 'Nhân sự mới — cập nhật hồ sơ.'),
    (NULL, 'hr',              'junior',    'OPERATOR', 'Chuyên viên junior — onboarding.'),
    (NULL, 'hr',              'mid',       'ANALYST',  'Chuyên viên — phân tích headcount.'),
    (NULL, 'hr',              'senior',    'MANAGER',  'Chuyên viên cấp cao — đã có quyền duyệt.'),
    (NULL, 'hr',              'executive', 'MANAGER',  'HR Director — quản lý toàn nhân sự.'),

    -- Finance (sensitive — bump up faster)
    (NULL, 'finance',         'entry',     'OPERATOR', 'Kế toán viên — ghi sổ A/R, A/P.'),
    (NULL, 'finance',         'junior',    'ANALYST',  'Kế toán junior — phân tích báo cáo.'),
    (NULL, 'finance',         'mid',       'ANALYST',  'Chuyên viên Tài chính — phân tích.'),
    (NULL, 'finance',         'senior',    'MANAGER',  'Senior Finance — duyệt chi.'),
    (NULL, 'finance',         'executive', 'MANAGER',  'CFO / Trưởng phòng Tài chính.'),

    -- Custom — defaults conservatively to VIEWER; manager forced to
    -- explicit-grant. Prevents "we made a custom dept and now everyone
    -- got MANAGER by accident".
    (NULL, 'custom',          'entry',     'VIEWER',   'Phòng ban tùy chỉnh — yêu cầu quản lý gán quyền cụ thể.'),
    (NULL, 'custom',          'junior',    'VIEWER',   'Phòng ban tùy chỉnh — chỉ xem.'),
    (NULL, 'custom',          'mid',       'VIEWER',   'Phòng ban tùy chỉnh — chỉ xem.'),
    (NULL, 'custom',          'senior',    'ANALYST',  'Phòng ban tùy chỉnh — senior được phân tích.'),
    (NULL, 'custom',          'executive', 'MANAGER',  'Trưởng phòng ban tùy chỉnh.')
ON CONFLICT DO NOTHING;


-- =====================================================================
-- Documentation
-- =====================================================================

COMMENT ON TABLE department_role_templates IS
    'P15-S11 Hướng A — RBAC tĩnh per (dept_type × seniority_level). Anh chốt 2026-05-16; B (RBAC+ABAC+PDP) deferred Phase 2.';
COMMENT ON COLUMN department_role_templates.enterprise_id IS
    'NULL = global default; non-null = enterprise-level override shadowing the global row.';
COMMENT ON COLUMN department_role_templates.default_role IS
    'P2 role to assign when onboarding approval handler resolves to this template. Mirrors enterprise_users.role constraint.';
COMMENT ON COLUMN department_role_templates.overridable IS
    'TRUE = approver can swap the templated role to a different one (with audit). FALSE = templated role is mandatory.';
