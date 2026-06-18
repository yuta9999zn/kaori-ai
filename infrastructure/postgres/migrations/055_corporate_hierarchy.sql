-- 055_corporate_hierarchy.sql — P15-S11 Tuần 8 corporate-tree extension.
--
-- Per anh's directive 2026-05-15 (Vingroup-class question):
--
--   "Doanh nghiệp = tập đoàn → mảng → công ty con → phòng ban. Khách
--   hàng kéo thả ra sơ đồ phả hệ từ cấp cao nhất xuống phòng ban nhỏ
--   nhất; click phòng ban → tạo workflow."
--
-- Schema additions (all NULLABLE — backwards compatible with the 1-cấp
-- enterprise tenants we have today like Olist):
--
--   corporate_groups       — top-level tập đoàn (Vingroup, FPT, …)
--                            One per workspace typically, but the FK is
--                            workspace-scoped to keep multi-corp tenants
--                            (consulting firms managing several groups)
--                            open.
--
--   business_divisions     — mảng kinh doanh under a corporate_group.
--                            Vingroup → BĐS / Bán lẻ / Công nghiệp / …
--
--   enterprises.ALTER      — adds:
--                              corporate_group_id     (which tập đoàn)
--                              business_division_id   (which mảng)
--                              parent_enterprise_id   (self-ref — for
--                                  sub-subsidiaries like VinFast Auto
--                                  under VinFast)
--
-- The 3 hierarchy levels (group, division, enterprise) are all RLS-K-1
-- scoped via the same `app.current_enterprise_id` GUC that already exists
-- — we layer through `workspace_id` joins.  Cross-cutting RLS via a new
-- `app.current_corporate_group_id` GUC is added BUT remains optional
-- (handler still sets app.current_enterprise_id as today); the new GUC
-- lets a corporate HQ user query the whole tree without per-subsidiary
-- enterprise-id switching.
--
-- Phase 2 (DEFERRED):
--   - Cross-subsidiary workflow sharing (a single workflow that spans
--     two enterprises under the same corporate_group)
--   - Subsidiary-level billing rollup
--   - Org-chart audit log for restructuring events

-- ─── 1. corporate_groups ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS corporate_groups (
    corporate_group_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID            NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,

    name                    VARCHAR(200)    NOT NULL,
    name_vi                 VARCHAR(200),
    description             TEXT,

    -- Optional metadata (Vingroup uses these — see demo seed mig 056).
    founded_year            SMALLINT,
    headquarters            VARCHAR(200),         -- "Hà Nội" / "TPHCM"
    logo_url                VARCHAR(500),
    website                 VARCHAR(200),

    -- Lifecycle. Active tập đoàn under management; archived = wound up.
    status                  VARCHAR(20)     NOT NULL DEFAULT 'active',

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by              UUID,
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_corp_group_name_per_workspace UNIQUE (workspace_id, name),
    CONSTRAINT chk_corp_group_status CHECK (status IN ('active', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_corp_groups_workspace
    ON corporate_groups (workspace_id, status);

-- ─── 2. business_divisions ───────────────────────────────────────────
--
-- Vingroup has 8 mảng per the corporate profile doc (BĐS, Du lịch,
-- Bán lẻ, Công nghiệp, Y tế, Giáo dục, Nông nghiệp, Công nghệ).
-- Each division has 1+ enterprises under it.

CREATE TABLE IF NOT EXISTS business_divisions (
    division_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    corporate_group_id      UUID            NOT NULL REFERENCES corporate_groups(corporate_group_id) ON DELETE CASCADE,
    workspace_id            UUID            NOT NULL,                       -- denormalised for RLS K-1 perf

    name                    VARCHAR(200)    NOT NULL,
    name_vi                 VARCHAR(200),
    description             TEXT,

    -- Industry keyword — drives the picker UI ("BĐS" / "Bán lẻ" / …).
    -- Loose taxonomy: enterprises themselves carry `industry` column so
    -- this is just a labelling hint at the division layer.
    industry_hint           VARCHAR(50),

    sort_order              INTEGER         NOT NULL DEFAULT 0,
    status                  VARCHAR(20)     NOT NULL DEFAULT 'active',

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_div_name_per_group UNIQUE (corporate_group_id, name),
    CONSTRAINT chk_div_status CHECK (status IN ('active', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_business_divisions_group
    ON business_divisions (corporate_group_id, sort_order)
    WHERE status = 'active';

-- ─── 3. enterprises ALTER ────────────────────────────────────────────
--
-- All three FKs NULLABLE so existing 1-cấp tenants (Olist) keep working
-- without backfill. New tenants opt into the hierarchy by setting these.
--
-- parent_enterprise_id: self-ref for sub-subsidiaries. E.g. VinFast Auto
-- is a child of VinFast which is a child of Vingroup's Công nghiệp
-- division. Phase 1 demo uses 2 levels (group → division → enterprise);
-- this column enables Phase 2 deeper trees without another migration.

ALTER TABLE enterprises
    ADD COLUMN IF NOT EXISTS corporate_group_id  UUID REFERENCES corporate_groups(corporate_group_id)   ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS business_division_id UUID REFERENCES business_divisions(division_id)       ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS parent_enterprise_id UUID REFERENCES enterprises(enterprise_id)            ON DELETE SET NULL;

-- Cycle prevention is enforced at app layer (recursive parent_enterprise_id
-- chains would corrupt the tree but a trigger here would prevent legitimate
-- re-parenting during a migration window). Router validate before UPDATE.

CREATE INDEX IF NOT EXISTS idx_enterprises_corp_group
    ON enterprises (corporate_group_id)
    WHERE corporate_group_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_enterprises_business_division
    ON enterprises (business_division_id)
    WHERE business_division_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_enterprises_parent
    ON enterprises (parent_enterprise_id)
    WHERE parent_enterprise_id IS NOT NULL;

-- ─── 4. RLS — K-1 scoping ────────────────────────────────────────────
--
-- corporate_groups is workspace-scoped (top of the tenant pyramid).
-- business_divisions inherits via corporate_group_id → workspace_id (we
-- denormalised it onto the row to avoid join-in-policy perf hit).
--
-- The new GUC `app.current_corporate_group_id` is OPTIONAL. When set,
-- queries can narrow to one tập đoàn for HQ users; when unset, regular
-- enterprise-scoped RLS applies. Same pattern as
-- `app.current_department_id` from mig 047.

ALTER TABLE corporate_groups    ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_divisions  ENABLE ROW LEVEL SECURITY;

-- The workspace_id GUC is set by the auth gateway from the JWT (the
-- same place that sets app.current_enterprise_id today — workspace lives
-- on the same token).  Falling back to NULL means policy evaluates the
-- enterprise-scoped path only.
--
-- We use `app.current_workspace_id` here. If your deployment hasn't
-- enabled that GUC yet, the policy returns no rows for these tables —
-- safe-default. Per anh's existing 2-GUC tech-debt (CLAUDE.md §14),
-- this stays consistent with the new-style `app.current_*` naming.

DROP POLICY IF EXISTS isolation_corporate_groups ON corporate_groups;
CREATE POLICY isolation_corporate_groups ON corporate_groups
    USING      (workspace_id::text = current_setting('app.current_workspace_id', true))
    WITH CHECK (workspace_id::text = current_setting('app.current_workspace_id', true));

DROP POLICY IF EXISTS isolation_business_divisions ON business_divisions;
CREATE POLICY isolation_business_divisions ON business_divisions
    USING      (workspace_id::text = current_setting('app.current_workspace_id', true))
    WITH CHECK (workspace_id::text = current_setting('app.current_workspace_id', true));

-- ─── 5. Recursive corporate tree view ────────────────────────────────
--
-- Single flat row per node in the tree, with depth + materialised path
-- for ergonomic FE rendering. Nodes are: group / division / enterprise
-- / sub-enterprise. Branch + department live below enterprise — the
-- router joins them on demand for the leaf level rather than blowing up
-- this view's row count.
--
-- View columns:
--   level        — 1 (group) | 2 (division) | 3 (enterprise) | 4+ (sub-enterprise)
--   node_type    — 'group' | 'division' | 'enterprise'
--   node_id      — UUID of the node
--   parent_id    — UUID of the parent node (NULL for group level)
--   workspace_id — for RLS join
--   name         — display name (Vietnamese if available, else English)
--   path         — array of UUIDs from root to this node (1, 2, ..., N)
--   sort_order   — for stable ordering within a level

-- The view is intentionally NON-recursive. Postgres parses UNION ALL
-- chains left-to-right, so WITH RECURSIVE + 3-way UNION ALL produces
-- "recursive reference must not appear in non-recursive term" because
-- the second + third branches both reference `tree`. Since the org
-- tree has a bounded depth (group → division → enterprise → sub-
-- enterprise = 4 levels max in Phase 1 Build Week), a plain UNION ALL
-- of 4 anchor SELECTs is simpler, deterministic, and 1 query.
--
-- Trade-off: no materialised `path[]` from root → leaf. The router
-- assembles `path` in Python by walking `parent_id` chains when needed
-- (corporate_tree.get_nested_tree builds a children map). FE doesn't
-- currently consume path, so this is OK.

CREATE OR REPLACE VIEW v_corporate_tree AS
-- Level 1: corporate_groups (roots)
SELECT
    1::integer                              AS level,
    'group'::varchar                        AS node_type,
    cg.corporate_group_id                   AS node_id,
    NULL::uuid                              AS parent_id,
    cg.workspace_id,
    COALESCE(cg.name_vi, cg.name)           AS display_name,
    cg.name                                 AS name,
    cg.status,
    0::integer                              AS sort_order
FROM corporate_groups cg

UNION ALL

-- Level 2: business_divisions under each group
SELECT
    2,
    'division',
    bd.division_id,
    bd.corporate_group_id,
    bd.workspace_id,
    COALESCE(bd.name_vi, bd.name),
    bd.name,
    bd.status,
    bd.sort_order
FROM business_divisions bd

UNION ALL

-- Level 3: enterprises attached to a division
SELECT
    3,
    'enterprise',
    e.enterprise_id,
    e.business_division_id,
    e.workspace_id,
    e.name,                                                          -- enterprises has no name_vi column
    e.name,
    e.status,
    0
FROM enterprises e
WHERE e.business_division_id IS NOT NULL
  AND e.parent_enterprise_id IS NULL

UNION ALL

-- Level 3 (alt): enterprises attached directly to a group (no division)
SELECT
    3,
    'enterprise',
    e.enterprise_id,
    e.corporate_group_id,
    e.workspace_id,
    e.name,
    e.name,
    e.status,
    0
FROM enterprises e
WHERE e.business_division_id IS NULL
  AND e.parent_enterprise_id IS NULL
  AND e.corporate_group_id IS NOT NULL

UNION ALL

-- Level 4: sub-enterprises (parent_enterprise_id chain — 1 hop)
-- Deeper hops (level 5+) are rare; router can walk parent_id chains
-- in Python if a tenant ever models > 4-level sub-subsidiaries.
SELECT
    4,
    'enterprise',
    e.enterprise_id,
    e.parent_enterprise_id,
    e.workspace_id,
    e.name,
    e.name,
    e.status,
    0
FROM enterprises e
WHERE e.parent_enterprise_id IS NOT NULL;

COMMENT ON VIEW v_corporate_tree IS
    'P15-S11 mig 055 — recursive flattening of corporate_groups → business_divisions → '
    'enterprises (with self-ref parent for sub-subsidiaries). Router /corporate-tree '
    'reads here. RLS inherits from underlying tables (workspace_id scoping).';

-- ─── 6. kaori_app grants ─────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON corporate_groups   TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON business_divisions TO kaori_app';
        EXECUTE 'GRANT SELECT                          ON v_corporate_tree  TO kaori_app';
    END IF;
END $$;

-- ─── 7. Comments ─────────────────────────────────────────────────────

COMMENT ON TABLE  corporate_groups IS
    'P15-S11 mig 055 — top-level tập đoàn (Vingroup-class). 1 workspace = 1 corp group '
    'typically. Backwards compatible: enterprises without a corporate_group_id keep '
    'working as 1-cấp tenants (Olist demo).';
COMMENT ON TABLE  business_divisions IS
    'P15-S11 mig 055 — mảng kinh doanh under a corporate_group. Vingroup ships with '
    '8 divisions (BĐS / Du lịch / Bán lẻ / Công nghiệp / Y tế / Giáo dục / Nông nghiệp / '
    'Công nghệ) via mig 056 demo seed.';
COMMENT ON COLUMN enterprises.parent_enterprise_id IS
    'Self-ref for sub-subsidiaries (VinFast Auto under VinFast). Phase 1 demo stays at '
    '2 levels (group → division → enterprise); deeper trees enabled here without follow-up migration.';
COMMENT ON COLUMN enterprises.business_division_id IS
    'P15-S11 mig 055 — which mảng kinh doanh this subsidiary belongs to (Vingroup BĐS, '
    'Vingroup Bán lẻ, …). NULL for flat-tenant deployments.';
