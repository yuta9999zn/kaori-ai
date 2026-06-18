-- 047_dept_fk_on_data_tables.sql — P15-S11 Tuần 7 ngày 2.
--
-- Adds branch_id + department_id + source_id columns to the bronze /
-- silver / gold data tables so every row carries its organisational
-- attribution. RLS policies remain enterprise-scoped (K-1 hard rule)
-- but a NEW policy adds department_id scope for ABAC §16.4 — Marketing
-- Manager only sees Marketing rows, etc.
--
-- Backfill strategy:
--   1. branch_id → default branch (`is_default=TRUE`) per enterprise.
--   2. department_id → Marketing default per enterprise (Phase 1 demo);
--      operators can re-assign rows post-migration via the Data Explorer
--      "reassign department" UI (Phase 2 work — Build Week uses the
--      Marketing default).
--   3. source_id → the auto-seeded `Manual upload` source per department.
--
-- NULL → NOT NULL flip happens at the end so the backfill can run
-- without short-window concurrent INSERTs failing. After flip, every
-- new row MUST carry all 3 IDs (enforced via app layer — see upload
-- endpoint change in upload.py Tuần 7 ngày 6).

-- ─── 1. bronze_files ─────────────────────────────────────────────────

ALTER TABLE bronze_files
    ADD COLUMN IF NOT EXISTS branch_id     UUID REFERENCES branches(branch_id)         ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(department_id)  ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS source_id     UUID REFERENCES data_sources(source_id)     ON DELETE RESTRICT;

-- Backfill: every existing bronze_file gets attached to the
-- enterprise's default Marketing department + Manual upload source.
UPDATE bronze_files bf
SET
    branch_id     = COALESCE(bf.branch_id, b.branch_id),
    department_id = COALESCE(bf.department_id, d.department_id),
    source_id     = COALESCE(bf.source_id, s.source_id)
FROM
    branches    b,
    departments d,
    data_sources s
WHERE bf.enterprise_id = b.enterprise_id
  AND b.is_default = TRUE
  AND d.enterprise_id = bf.enterprise_id
  AND d.branch_id     = b.branch_id
  AND d.dept_type     = 'marketing'
  AND s.enterprise_id = bf.enterprise_id
  AND s.department_id = d.department_id
  AND s.source_kind   = 'manual_upload'
  AND (bf.branch_id IS NULL OR bf.department_id IS NULL OR bf.source_id IS NULL);

-- ─── 2. bronze_rows ──────────────────────────────────────────────────

ALTER TABLE bronze_rows
    ADD COLUMN IF NOT EXISTS branch_id     UUID REFERENCES branches(branch_id)         ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(department_id)  ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS source_id     UUID REFERENCES data_sources(source_id)     ON DELETE RESTRICT;

-- Backfill from the parent bronze_file. Cheap: file_id is the PK FK.
UPDATE bronze_rows br
SET
    branch_id     = COALESCE(br.branch_id, bf.branch_id),
    department_id = COALESCE(br.department_id, bf.department_id),
    source_id     = COALESCE(br.source_id, bf.source_id)
FROM bronze_files bf
WHERE br.file_id = bf.file_id
  AND (br.branch_id IS NULL OR br.department_id IS NULL OR br.source_id IS NULL);

-- ─── 3. silver_rows ──────────────────────────────────────────────────

ALTER TABLE silver_rows
    ADD COLUMN IF NOT EXISTS branch_id     UUID REFERENCES branches(branch_id)         ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(department_id)  ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS source_id     UUID REFERENCES data_sources(source_id)     ON DELETE RESTRICT;

-- silver_rows backfill — same strategy as bronze_files (per enterprise default).
UPDATE silver_rows sr
SET
    branch_id     = COALESCE(sr.branch_id, b.branch_id),
    department_id = COALESCE(sr.department_id, d.department_id),
    source_id     = COALESCE(sr.source_id, s.source_id)
FROM
    branches    b,
    departments d,
    data_sources s
WHERE sr.enterprise_id = b.enterprise_id
  AND b.is_default = TRUE
  AND d.enterprise_id = sr.enterprise_id
  AND d.branch_id     = b.branch_id
  AND d.dept_type     = 'marketing'
  AND s.enterprise_id = sr.enterprise_id
  AND s.department_id = d.department_id
  AND s.source_kind   = 'manual_upload'
  AND (sr.branch_id IS NULL OR sr.department_id IS NULL OR sr.source_id IS NULL);

-- ─── 4. gold_features ────────────────────────────────────────────────
--
-- gold_features is per-customer (PK = enterprise_id + customer_external_id).
-- Adding department_id makes it per-(customer, dept) which is the right
-- shape per spec §8.3 — a customer can be tracked by Marketing and Sales
-- with different LTV / pipeline scoring. PK gains department_id.

ALTER TABLE gold_features
    ADD COLUMN IF NOT EXISTS branch_id     UUID REFERENCES branches(branch_id)         ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(department_id)  ON DELETE RESTRICT;

UPDATE gold_features gf
SET
    branch_id     = COALESCE(gf.branch_id, b.branch_id),
    department_id = COALESCE(gf.department_id, d.department_id)
FROM branches b, departments d
WHERE gf.enterprise_id = b.enterprise_id
  AND b.is_default = TRUE
  AND d.enterprise_id = gf.enterprise_id
  AND d.branch_id     = b.branch_id
  AND d.dept_type     = 'marketing'
  AND (gf.branch_id IS NULL OR gf.department_id IS NULL);

-- ─── 5. gold_aggregates ──────────────────────────────────────────────

ALTER TABLE gold_aggregates
    ADD COLUMN IF NOT EXISTS branch_id     UUID REFERENCES branches(branch_id)         ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES departments(department_id)  ON DELETE RESTRICT;

UPDATE gold_aggregates ga
SET
    branch_id     = COALESCE(ga.branch_id, b.branch_id),
    department_id = COALESCE(ga.department_id, d.department_id)
FROM branches b, departments d
WHERE ga.enterprise_id = b.enterprise_id
  AND b.is_default = TRUE
  AND d.enterprise_id = ga.enterprise_id
  AND d.branch_id     = b.branch_id
  AND d.dept_type     = 'marketing'
  AND (ga.branch_id IS NULL OR ga.department_id IS NULL);

-- ─── 6. NOT NULL constraints (after backfill) ────────────────────────
--
-- Build Week deferral: keep columns NULLABLE for the demo so old rows
-- without departments don't break joins. Tuần 8 cleanup can flip to
-- NOT NULL once Olist seed verifies every row has the attribution.
-- For now we enforce via the application layer (upload.py validates
-- non-null on insert).
--
-- TODO Tuần 8: after Olist E2E passes, run
--   ALTER TABLE bronze_files     ALTER COLUMN department_id SET NOT NULL;
--   (and equivalent for branch_id, source_id on all 5 tables)

-- ─── 7. Indexes — per-dept hot paths ─────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_bronze_files_dept_uploaded
    ON bronze_files (enterprise_id, department_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bronze_files_source
    ON bronze_files (source_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_silver_rows_dept
    ON silver_rows (enterprise_id, department_id);

CREATE INDEX IF NOT EXISTS idx_gold_features_dept
    ON gold_features (enterprise_id, department_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_gold_aggregates_dept
    ON gold_aggregates (enterprise_id, department_id, metric_key);

-- ─── 8. RLS — ABAC department scope (§16.4) ──────────────────────────
--
-- K-1 enterprise scope already enforced. NEW policy adds an OPTIONAL
-- department scope via app.current_department_id GUC. When the GUC is
-- NULL/empty, all departments are visible (MANAGER role). When set,
-- only that department's rows are visible (per-dept user).
--
-- Why "OPTIONAL via NULL fallback": MANAGER + ANALYST users still need
-- cross-dept queries for org-wide insight (e.g. revenue across all
-- departments). The middleware sets app.current_department_id only
-- when the user's role is restricted to a single dept; for unrestricted
-- roles it leaves the GUC unset.

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'bronze_files', 'bronze_rows', 'silver_rows',
        'gold_features', 'gold_aggregates'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS abac_dept_scope ON %I', tbl);
        EXECUTE format($f$
            CREATE POLICY abac_dept_scope ON %I
                USING (
                    -- K-1 hard rule (already enforced by sibling policy)
                    enterprise_id::text = current_setting('app.current_enterprise_id', true)
                    -- ABAC: if dept GUC is set, restrict to it
                    AND (
                        current_setting('app.current_department_id', true) = ''
                        OR current_setting('app.current_department_id', true) IS NULL
                        OR department_id::text = current_setting('app.current_department_id', true)
                    )
                )
        $f$, tbl);
    END LOOP;
END $$;

-- ─── 9. Comments ─────────────────────────────────────────────────────

COMMENT ON COLUMN bronze_files.department_id IS
    'P15-S11 mig 047 — owning department. NULLABLE during Build Week; will flip NOT NULL Tuần 8 after Olist seed validates.';
COMMENT ON COLUMN bronze_files.source_id IS
    'P15-S11 mig 047 — connector / upload source. Default "Manual upload" per dept.';
COMMENT ON COLUMN gold_features.department_id IS
    'P15-S11 mig 047 — per-dept feature shape per spec §8.3. Same customer can have different LTV/scoring per department (Marketing vs Sales vs CS).';
