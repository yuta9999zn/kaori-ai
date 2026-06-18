-- Migration 030: F-034 Analysis Frameworks (SWOT / 6W / 2H / Fishbone).
--
-- Why this exists
-- ===============
-- Phase 2 unlocks structured analysis frameworks: SWOT, 6W (who/what/
-- when/where/why/how), 2H (how + how much), Fishbone (Ishikawa root
-- cause). Each one is a different LLM call shape — different system
-- prompt, different output_schema. K-10 enforced at the API surface:
-- one question = one framework (no parallel SWOT + 5Why).
--
-- Why not reuse F-038 report_templates
-- =====================================
-- F-038 templates are tenant-customisable (the FE has a "create your
-- own template" path). Frameworks are universal — SWOT means the same
-- thing in every domain — so the system_prompt + output_schema live in
-- Python (services/ai-orchestrator/frameworks/templates.py) and never
-- in the DB. A per-tenant DB row would force a seed step at every
-- onboarding, and a "tenant edited the SWOT prompt" footgun.
--
-- Schema
-- ======
-- framework_runs: one row per generated framework instance.
--   * framework_code is the only "template" pointer, validated by the
--     service against the Python registry. CHECK constraint here keeps
--     the DB authoritative even if the registry adds a code that
--     hasn't shipped yet.
--   * question + source_ref capture the user's intent at run time.
--     source_ref is opaque (gold feature id, analysis_run id, dataset
--     name) — the system_prompt formats it but the DB doesn't care.
--   * consent_external mirrors the K-4 surface: tenant must explicitly
--     opt in to external LLM per-call, default OFF (Qwen local).
--   * Status machine identical to reports.reports (queued → running →
--     ready (terminal) | failed (terminal)) so the FE can reuse
--     polling code.
--
-- RLS
-- ===
-- Standard tenant_isolation + admin_bypass pattern (matches migrations
-- 027 reports + 029 report_distributions). framework_runs is the only
-- table here so the policy block is short.
--
-- Reversibility
-- =============
--   DROP TABLE framework_runs;
-- Service rollback: removing the router include from main.py disables
-- the /api/v1/frameworks/* endpoints; the existing analytics flow is
-- untouched.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS framework_runs (
    run_id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id      UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Validated against the Python registry at the service layer; the
    -- CHECK list here is the DB-authoritative whitelist + extends
    -- additively as new frameworks ship. mom-yoy and custom are
    -- intentionally OUT of v0 scope (mom-yoy is a calculation, not
    -- an LLM call; custom needs a per-tenant prompt store).
    framework_code     VARCHAR(20)  NOT NULL
                                    CHECK (framework_code IN ('swot', '6w', '2h', 'fishbone')),

    -- The user's question / hypothesis the framework should structure.
    question           TEXT         NOT NULL,

    -- Optional reference into the data layer (gold_features.id,
    -- analysis_runs.id, dataset name). Free-form text — the system
    -- prompt picks it up + asks the LLM to ground its analysis.
    source_ref         VARCHAR(200),

    -- K-4 — must be explicit per-call. Default OFF (Qwen local).
    consent_external   BOOLEAN      NOT NULL DEFAULT FALSE,

    -- Status machine. Terminal: ready / failed.
    status             VARCHAR(20)  NOT NULL DEFAULT 'queued'
                                    CHECK (status IN ('queued', 'running', 'ready', 'failed')),

    -- Validated LLM output (matches the framework's output_schema in
    -- templates.py). NULL until status='ready'.
    content_json       JSONB,

    -- Free-text narrative summary the LLM produces alongside the
    -- structured payload. Used as the FE list-row preview.
    narrative          TEXT,

    -- Failure detail when status='failed'.
    last_error         TEXT,

    -- Who triggered the run. NULL for system / future automation
    -- (scheduled batch frameworks, etc.).
    created_by_user    UUID,

    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at       TIMESTAMPTZ
);

-- FE list endpoint hot path: "show me my recent framework runs".
CREATE INDEX IF NOT EXISTS idx_framework_runs_tenant_created
    ON framework_runs(enterprise_id, created_at DESC);

-- Background workers + ops dashboards filter by status.
CREATE INDEX IF NOT EXISTS idx_framework_runs_pending
    ON framework_runs(created_at)
    WHERE status IN ('queued', 'running');

ALTER TABLE framework_runs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'framework_runs' AND policyname = 'tenant_framework_runs'
    ) THEN
        CREATE POLICY tenant_framework_runs ON framework_runs
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'framework_runs' AND policyname = 'admin_bypass_framework_runs'
    ) THEN
        CREATE POLICY admin_bypass_framework_runs ON framework_runs
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON framework_runs TO kaori_app;

COMMIT;
