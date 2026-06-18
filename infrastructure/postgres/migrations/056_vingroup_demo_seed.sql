-- 056_vingroup_demo_seed.sql — P15-S11 Tuần 8 corporate-tree demo data.
--
-- Per anh's directive 2026-05-15: demo phải show được Vingroup-class
-- corporate hierarchy. This migration seeds:
--
--   1 workspace      "Vingroup Holdings" (PILOT plan — demo only)
--   1 corp_group     "Vingroup" (8 divisions per Corporate Profile 2018)
--   8 divisions      BĐS / Du lịch & Giải trí / Bán lẻ / Công nghiệp /
--                    Y tế / Giáo dục / Nông nghiệp / Công nghệ
--   ~13 subsidiaries Mini Vingroup tree — 1-3 enterprises per division,
--                    covering the brands mentioned in the 2018 profile
--                    (Vinhomes / Vincom Retail / VinMart / VinFast /
--                    Vinmec / VinSchool / VinEco / VinAI / …).
--   For each new enterprise:
--     - 1 default branch "Trụ sở chính"
--     - 6 default departments (mirrors mig 046 backfill)
--     - 1 Manual upload data source per department
--
-- Fully idempotent — every INSERT has ON CONFLICT DO NOTHING (unique
-- constraints from migs 046/055 prevent duplicates). Re-running the
-- migration is safe; existing Olist / pilot tenants untouched.
--
-- Why a separate seed migration (not a one-off script):
--   Flyway treats SQL migrations as ordered + replayable; this guarantees
--   every developer + CI environment ships the same demo dataset.
--   The Olist seed remains a script (scripts/seed_olist_into_kaori.py)
--   because it depends on local CSV files; Vingroup data is pure
--   metadata so it lives in SQL.

BEGIN;

-- ─── 1. Workspace + corporate_group ──────────────────────────────────
--
-- workspaces.name has NO UNIQUE constraint (mig 001), so we can't use
-- ON CONFLICT here — use NOT EXISTS guard instead. The migration is
-- still idempotent: re-runs skip when 'Vingroup Holdings' already exists.

-- plan_code: use whichever entry-tier plan exists in subscription_plans.
-- Mig 001 seeds TRIAL/STARTER/BUSINESS/ENTERPRISE; the CLAUDE.md §10
-- canonical names (PILOT/ENT BASIC/ENT MID/ENT MAX) haven't migrated
-- yet. Pick TRIAL — guaranteed-present and fine for demo.
INSERT INTO workspaces (name, plan_code, status)
SELECT 'Vingroup Holdings', 'TRIAL', 'active'
WHERE NOT EXISTS (
    SELECT 1 FROM workspaces WHERE name = 'Vingroup Holdings'
);

WITH ws AS (
    SELECT workspace_id FROM workspaces WHERE name = 'Vingroup Holdings'
    LIMIT 1
)
INSERT INTO corporate_groups
    (workspace_id, name, name_vi, description,
     founded_year, headquarters, website, status)
SELECT
    ws.workspace_id,
    'Vingroup',
    'Tập đoàn Vingroup',
    'Tập đoàn kinh tế tư nhân đa ngành hàng đầu Việt Nam, hệ sinh thái '
    'gồm bất động sản, bán lẻ, du lịch, công nghiệp, y tế, giáo dục, '
    'nông nghiệp và công nghệ.',
    1993,
    'Hà Nội',
    'https://www.vingroup.net',
    'active'
FROM ws
WHERE NOT EXISTS (
    SELECT 1 FROM corporate_groups WHERE workspace_id = ws.workspace_id AND name = 'Vingroup'
);

-- ─── 2. 8 Business divisions ─────────────────────────────────────────

INSERT INTO business_divisions
    (corporate_group_id, workspace_id, name, name_vi, description, industry_hint, sort_order)
SELECT
    cg.corporate_group_id,
    cg.workspace_id,
    v.name,
    v.name_vi,
    v.description,
    v.industry_hint,
    v.sort_order
FROM corporate_groups cg,
LATERAL (VALUES
    ('Real Estate',         'Bất động sản',
     'Vinhomes, Vincom Retail, Vincity, VinOffice — đô thị + TTTM + văn phòng.',
     'real_estate', 1),
    ('Hospitality',          'Du lịch & Giải trí',
     'Vinpearl, VinpearLand, VinTata — nghỉ dưỡng, vui chơi, giải trí.',
     'hospitality', 2),
    ('Retail',               'Bán lẻ',
     'VinMart, VinMart+, VinDS — chuỗi siêu thị, cửa hàng tiện lợi, hàng tiêu dùng.',
     'retail', 3),
    ('Manufacturing',        'Công nghiệp',
     'VinFast (ô tô / xe điện), VinSmart (điện tử thông minh).',
     'manufacturing', 4),
    ('Healthcare',           'Y tế',
     'Vinmec (bệnh viện quốc tế), VinFa (dược phẩm).',
     'healthcare', 5),
    ('Education',            'Giáo dục',
     'VinSchool, VinUni — phổ thông + đại học.',
     'education', 6),
    ('Agriculture',          'Nông nghiệp',
     'VinEco — nông sản công nghệ cao.',
     'agriculture', 7),
    ('Technology',           'Công nghệ',
     'VinTech, VinAI — R&D + nền tảng AI + sản phẩm số.',
     'technology', 8)
) AS v(name, name_vi, description, industry_hint, sort_order)
WHERE cg.name = 'Vingroup'
ON CONFLICT (corporate_group_id, name) DO NOTHING;

-- ─── 3. Subsidiary enterprises ───────────────────────────────────────
--
-- Compact set covering the brands mentioned in the 2018 profile.
-- Status: 'active'. industry mapped to existing enterprise.industry
-- enum-ish column (free-text in current schema; loose values OK).

-- enterprises has NO UNIQUE on (workspace_id, name) (mig 001), so we
-- guard with NOT EXISTS for idempotency. The LEFT JOIN approach lets
-- us check existence in one statement.

WITH div AS (
    SELECT bd.division_id, bd.workspace_id, bd.corporate_group_id, bd.name AS div_name
    FROM   business_divisions bd
    JOIN   corporate_groups cg ON cg.corporate_group_id = bd.corporate_group_id
    WHERE  cg.name = 'Vingroup'
), subsidiaries(div_name, name, industry) AS (VALUES
    -- Real Estate (3 subsidiaries)
    ('Real Estate',   'Vinhomes',           'real_estate'),
    ('Real Estate',   'Vincom Retail',      'real_estate'),
    ('Real Estate',   'VinCity',            'real_estate'),
    -- Hospitality (2)
    ('Hospitality',   'Vinpearl',           'hospitality'),
    ('Hospitality',   'VinpearLand',        'hospitality'),
    -- Retail (2)
    ('Retail',        'VinMart',            'retail'),
    ('Retail',        'VinMart+',           'retail'),
    -- Manufacturing (2)
    ('Manufacturing', 'VinFast',            'manufacturing'),
    ('Manufacturing', 'VinSmart',           'manufacturing'),
    -- Healthcare (2)
    ('Healthcare',    'Vinmec',             'healthcare'),
    ('Healthcare',    'VinFa',              'healthcare'),
    -- Education (2)
    ('Education',     'VinSchool',          'education'),
    ('Education',     'VinUni',             'education'),
    -- Agriculture (1)
    ('Agriculture',   'VinEco',             'agriculture'),
    -- Technology (2)
    ('Technology',    'VinTech',            'technology'),
    ('Technology',    'VinAI',              'technology')
)
INSERT INTO enterprises
    (workspace_id, name, industry, timezone, locale, status,
     corporate_group_id, business_division_id)
SELECT
    div.workspace_id, s.name, s.industry,
    'Asia/Ho_Chi_Minh', 'vi', 'active',
    div.corporate_group_id, div.division_id
FROM   div
JOIN   subsidiaries s ON s.div_name = div.div_name
WHERE  NOT EXISTS (
    SELECT 1 FROM enterprises e
    WHERE e.workspace_id = div.workspace_id AND e.name = s.name
);

-- ─── 4. Auto-seed branch + 6 departments per new Vingroup enterprise ─
--
-- Mirrors the backfill in mig 046 §5 but scoped to our Vingroup
-- enterprises only (don't accidentally re-seed Olist or other existing).

INSERT INTO branches (enterprise_id, name, code, is_default, address)
SELECT e.enterprise_id, 'Trụ sở chính', 'MAIN', TRUE, NULL
FROM   enterprises e
JOIN   corporate_groups cg ON cg.corporate_group_id = e.corporate_group_id
WHERE  cg.name = 'Vingroup'
AND NOT EXISTS (
    SELECT 1 FROM branches b
    WHERE b.enterprise_id = e.enterprise_id AND b.is_default = TRUE
);

INSERT INTO departments (enterprise_id, branch_id, name, dept_type, description)
SELECT
    e.enterprise_id,
    b.branch_id,
    dn.dept_name,
    dn.dept_type,
    dn.dept_desc
FROM   enterprises e
JOIN   corporate_groups cg ON cg.corporate_group_id = e.corporate_group_id
JOIN   branches b ON b.enterprise_id = e.enterprise_id AND b.is_default = TRUE
CROSS JOIN (
    VALUES
        ('Marketing',         'marketing',         'Tiếp thị + campaign + LTV'),
        ('Sales',             'sales',             'Bán hàng + pipeline + deal'),
        ('Customer Service',  'customer_service',  'CSKH + ticket + CSAT'),
        ('Warehouse',         'warehouse',         'Kho + tồn kho + xuất nhập'),
        ('HR',                'hr',                'Nhân sự + payroll'),
        ('Finance',           'finance',           'Tài chính + AR + cash flow')
) AS dn(dept_name, dept_type, dept_desc)
WHERE cg.name = 'Vingroup'
ON CONFLICT (enterprise_id, branch_id, name) DO NOTHING;

INSERT INTO data_sources (enterprise_id, department_id, name, source_kind)
SELECT d.enterprise_id, d.department_id, 'Manual upload', 'manual_upload'
FROM   departments d
JOIN   enterprises e ON e.enterprise_id = d.enterprise_id
JOIN   corporate_groups cg ON cg.corporate_group_id = e.corporate_group_id
WHERE  cg.name = 'Vingroup'
ON CONFLICT (enterprise_id, department_id, name) DO NOTHING;

COMMIT;

-- Footer summary for psql trace.
-- Expected post-mig counts (for Vingroup workspace only):
--   corporate_groups   : 1
--   business_divisions : 8
--   enterprises        : 16
--   branches           : 16 (1 per enterprise)
--   departments        : 96 (6 per enterprise × 16)
--   data_sources       : 96 (1 Manual upload per dept × 96)
