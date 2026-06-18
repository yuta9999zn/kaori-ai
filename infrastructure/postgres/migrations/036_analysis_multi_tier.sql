-- Migration 036: F-033 Multi-tier Analysis (PR A — basic + intermediate).
--
-- Why this exists
-- ===============
-- Phase 1 `analysis_runs` was built for the wizard: 1 pipeline_run, N
-- templates, run on Silver of that one run. F-033 promotes analysis to
-- a tier × scope matrix:
--
--   tier   ∈ {basic, intermediate, advanced}
--   scope  ∈ {single, multi, cross}
--
--   basic        → 1 pipeline_run + 1 template (the wizard flow)
--   intermediate → 2-5 silver/gold sources + 1 framework (no pipeline_run)
--   advanced     → cross-workspace cohort + external AI (PR B — not now)
--
-- Backward-compat
-- ===============
-- Existing `analysis_runs` rows came from the wizard — exactly the basic
-- tier shape. Backfill them with tier='basic', scope='single'. The
-- wizard endpoint (`POST /api/v1/analytics/runs`) stays unchanged; the
-- new multi-tier endpoint (`POST /api/v1/analysis/runs`) writes the
-- richer column set. Two endpoints share one table.
--
-- DROP NOT NULL on run_id
-- =======================
-- Intermediate / advanced tiers don't anchor on a single pipeline_run.
-- They reference `source_ids` (a list of silver/gold dataset refs)
-- instead. CHECK constraint enforces the dependency:
--   tier='basic'         → run_id IS NOT NULL
--   tier IN ('intermediate','advanced') → run_id may be NULL
--
-- Why ALTER TABLE not new table
-- =============================
-- One row = one user-initiated analysis is the right grain regardless
-- of tier. A separate `tier_analysis_runs` would (a) duplicate the
-- status / overview / RLS plumbing, (b) force the chat tool registry
-- + audit log + insights feed to JOIN two tables, (c) splinter ops
-- queries ("how many analyses ran today" becomes UNION ALL). The
-- columns added here are sparse for basic-tier rows, which is fine —
-- a few NULLs are cheaper than a parallel table.
--
-- PR A scope
-- ==========
-- Columns + CHECK constraints + indexes added now even though PR A only
-- writes basic + intermediate rows. Approval workflow + advanced tier
-- (PR B) populates approved_by / approved_at / requires_approval +
-- workspace_ids — defining them here means PR B is a service-layer
-- change only, no second migration.
--
-- Reversibility
-- =============
--   ALTER TABLE analysis_runs DROP COLUMN tier, ... etc.
-- Wizard rows survive (the columns are nullable / defaulted).
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Add columns (idempotent — IF NOT EXISTS via DO block)
-- ------------------------------------------------------------

DO $$ BEGIN
    -- Tier — defaults to 'basic' so wizard rows stay valid after backfill.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'tier') THEN
        ALTER TABLE analysis_runs
            ADD COLUMN tier VARCHAR(20) NOT NULL DEFAULT 'basic'
                CHECK (tier IN ('basic', 'intermediate', 'advanced'));
    END IF;

    -- Scope — single (1 pipeline), multi (N within workspace), cross (N workspaces).
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'scope') THEN
        ALTER TABLE analysis_runs
            ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'single'
                CHECK (scope IN ('single', 'multi', 'cross'));
    END IF;

    -- Free-form question the user asked. Wizard runs don't capture this
    -- (the templates are the question), so NULL-able.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'question') THEN
        ALTER TABLE analysis_runs ADD COLUMN question TEXT;
    END IF;

    -- Framework code for intermediate tier. Validated against
    -- frameworks/templates.py registry at the service layer; CHECK list
    -- here matches migration 030 framework_runs.framework_code.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'framework') THEN
        ALTER TABLE analysis_runs
            ADD COLUMN framework VARCHAR(20)
                CHECK (framework IS NULL OR framework IN ('swot', '6w', '2h', 'fishbone'));
    END IF;

    -- source_ids: opaque references to silver/gold datasets the
    -- intermediate tier should JOIN. JSONB instead of UUID[] because the
    -- service mixes silver dataset uuids with gold feature names — it's
    -- a heterogeneous list, not a clean FK array. Format:
    --   [{"layer": "silver", "id": "<uuid>"}, {"layer": "gold", "feature": "rfm_score"}]
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'source_ids') THEN
        ALTER TABLE analysis_runs ADD COLUMN source_ids JSONB;
    END IF;

    -- workspace_ids: cross-tier only (PR B). Stored even in PR A so the
    -- migration is one-shot.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'workspace_ids') THEN
        ALTER TABLE analysis_runs ADD COLUMN workspace_ids UUID[];
    END IF;

    -- K-4 — explicit per-call. Default OFF for backward-compat with
    -- wizard rows (which never set this). Service enforces:
    --   advanced tier requires consent_external = true.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'consent_external') THEN
        ALTER TABLE analysis_runs
            ADD COLUMN consent_external BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;

    -- Approval workflow — PR B populates these for advanced runs in
    -- workspaces with privacy=strict. PR A always leaves them NULL.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'requires_approval') THEN
        ALTER TABLE analysis_runs
            ADD COLUMN requires_approval BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'approved_by') THEN
        ALTER TABLE analysis_runs ADD COLUMN approved_by UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'approved_at') THEN
        ALTER TABLE analysis_runs ADD COLUMN approved_at TIMESTAMPTZ;
    END IF;

    -- Issue #3 audit footprint: did the gateway repair the LLM output?
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'output_schema_repaired') THEN
        ALTER TABLE analysis_runs ADD COLUMN output_schema_repaired BOOLEAN;
    END IF;

    -- Free-text narrative the LLM produces alongside structured output.
    -- Used as the FE list-row preview. Mirrors framework_runs.narrative.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'narrative') THEN
        ALTER TABLE analysis_runs ADD COLUMN narrative TEXT;
    END IF;

    -- Created_by_user — wizard never tracked this (the run_id JWT was
    -- enough). New endpoint stamps it for the audit feed.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'analysis_runs' AND column_name = 'created_by_user') THEN
        ALTER TABLE analysis_runs ADD COLUMN created_by_user UUID;
    END IF;
END $$;

-- ------------------------------------------------------------
-- 2. Drop NOT NULL from run_id (intermediate/advanced rows have
--    no anchoring pipeline_run).
-- ------------------------------------------------------------

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'analysis_runs'
                 AND column_name = 'run_id'
                 AND is_nullable = 'NO') THEN
        ALTER TABLE analysis_runs ALTER COLUMN run_id DROP NOT NULL;
    END IF;
END $$;

-- ------------------------------------------------------------
-- 3. CHECK: tier-vs-required-fields integrity.
--    Wrapped in DO block so the migration is idempotent.
-- ------------------------------------------------------------

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'analysis_runs_tier_anchor_check'
    ) THEN
        ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_tier_anchor_check
            CHECK (
                -- Basic must anchor on a pipeline_run.
                (tier = 'basic' AND run_id IS NOT NULL)
                -- Intermediate needs at least 2 sources.
                OR (tier = 'intermediate' AND source_ids IS NOT NULL
                    AND jsonb_array_length(source_ids) BETWEEN 2 AND 5)
                -- Advanced — PR B will tighten further; for now allow
                -- consent_external + workspace_ids to be NULL until PR B
                -- writes those rows.
                OR tier = 'advanced'
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'analysis_runs_advanced_consent_check'
    ) THEN
        ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_advanced_consent_check
            CHECK (
                -- Advanced tier MUST have consent_external = true. K-4
                -- enforced at DB level so a service bug can't sneak a
                -- non-consenting external call in.
                tier <> 'advanced' OR consent_external = TRUE
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'analysis_runs_intermediate_framework_check'
    ) THEN
        ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_intermediate_framework_check
            CHECK (
                -- Intermediate must pick exactly one framework. K-10:
                -- 1 question = 1 framework.
                tier <> 'intermediate' OR framework IS NOT NULL
            );
    END IF;
END $$;

-- ------------------------------------------------------------
-- 4. Indexes for the new query patterns.
-- ------------------------------------------------------------

-- Hub list endpoint: "recent runs across all tiers".
CREATE INDEX IF NOT EXISTS idx_analysis_runs_tier_created
    ON analysis_runs(enterprise_id, tier, created_at DESC);

-- Approval queue (PR B): "pending approval runs for this workspace".
CREATE INDEX IF NOT EXISTS idx_analysis_runs_pending_approval
    ON analysis_runs(enterprise_id, created_at)
    WHERE requires_approval = TRUE AND approved_at IS NULL;

COMMIT;
