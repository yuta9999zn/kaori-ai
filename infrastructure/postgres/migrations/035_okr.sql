-- Migration 035: F-040 Strategy Builder — OKR canvas (Objectives + Key Results).
--
-- Why this exists
-- ===============
-- Phase 2 sprint 2.4 — Strategy Builder. Pilot enterprises set
-- quarterly Objectives with 3-5 measurable Key Results, track progress
-- weekly, and see auto-computed status (on_track / at_risk / off_track)
-- based on KR completion vs. quarter elapsed.
--
-- v0 ships OKR only. The other modules in BACKLOG.md F-040 row
-- (Timeline / Gantt — template 54 — and Review Meetings — template 55)
-- need their own entities and are deferred to v1. The strategy_plans
-- JSONB framework store from BACKLOG section 285 is also a v1 follow-up;
-- structured okr_objectives + okr_key_results give us typed columns for
-- progress aggregation without paying the JSONB query cost.
--
-- Schema
-- ======
-- okr_objectives: one row per Objective, scoped per tenant + quarter.
-- okr_key_results: child rows (one Objective has 1..N KRs, typically 3).
-- Soft-delete on objectives only — KRs cascade-delete with their parent;
-- the audit trail lives on the objective.
--
-- Status workflow (auto-computed by service layer, stored here for
-- index hot-path queries):
--   on_track   — KR avg progress within 5% of quarter elapsed
--   at_risk    — within 15% lag
--   off_track  — > 15% lag
-- The service rewrites status on every KR or objective update.
--
-- RLS
-- ===
-- Standard tenant_isolation + admin_bypass pattern (matches alerts
-- migration 028, decision_overrides 031, risk_items 033).
--
-- Reversibility
-- =============
--   DROP TABLE okr_key_results;
--   DROP TABLE okr_objectives;
-- Service rollback: removing the controller from auth-service reverts
-- the API surface; rows stay (DROP TABLE is the only path to wipe).
-- ============================================================

BEGIN;

-- =========================================================================
-- okr_objectives
-- =========================================================================
CREATE TABLE IF NOT EXISTS okr_objectives (
    objective_id    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Quarter label like "Q2 2026". CHECK keeps the format consistent so
    -- the FE filter dropdown gets a clean enum.
    quarter         VARCHAR(8)   NOT NULL
                                 CHECK (quarter ~ '^Q[1-4] \d{4}$'),
    title           VARCHAR(200) NOT NULL,

    -- ON DELETE SET NULL — losing the assignee should not cascade-delete
    -- the strategy artifact. FE renders "(no owner)" in that case.
    owner_user_id   UUID         REFERENCES enterprise_users(user_id) ON DELETE SET NULL,

    -- Computed by the service on every save. Indexed below for the rollup
    -- ("how many at-risk this quarter") tile query.
    status          VARCHAR(12)  NOT NULL DEFAULT 'on_track'
                                 CHECK (status IN ('on_track', 'at_risk', 'off_track')),

    -- Audit
    created_by_user UUID,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Soft delete
    deleted_at      TIMESTAMPTZ
);

-- Hot path: list endpoint scopes by tenant + filters by quarter most
-- of the time. (status DESC) so off_track sorts first within a quarter.
CREATE INDEX IF NOT EXISTS idx_okr_objectives_tenant_quarter
    ON okr_objectives (enterprise_id, quarter, status DESC, objective_id DESC)
    WHERE deleted_at IS NULL;

-- Owner workload — which objectives a manager owns this quarter.
CREATE INDEX IF NOT EXISTS idx_okr_objectives_owner
    ON okr_objectives (enterprise_id, owner_user_id, quarter)
    WHERE deleted_at IS NULL;

-- Status rollup tile — partial keeps it tiny ("X off_track this quarter").
CREATE INDEX IF NOT EXISTS idx_okr_objectives_status
    ON okr_objectives (enterprise_id, quarter, status)
    WHERE deleted_at IS NULL;


-- =========================================================================
-- okr_key_results
-- =========================================================================
CREATE TABLE IF NOT EXISTS okr_key_results (
    kr_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_id    UUID         NOT NULL REFERENCES okr_objectives(objective_id) ON DELETE CASCADE,
    -- Denormalised enterprise_id for RLS filtering at the row level.
    -- Application enforces the parent-child invariant on insert.
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    title           VARCHAR(200) NOT NULL,
    -- Free-text unit ("%", "VNĐ", "khách hàng", "form") so each KR can
    -- describe its own metric without a global enum. FE renders verbatim.
    unit            VARCHAR(40)  NOT NULL DEFAULT '',

    -- K-9 — never FLOAT for measured values. NUMERIC(14,4) covers money +
    -- counts + percentages without rounding drift.
    target          NUMERIC(14,4) NOT NULL CHECK (target > 0),
    current_value   NUMERIC(14,4) NOT NULL DEFAULT 0
                                  CHECK (current_value >= 0),

    -- FE displays KRs in the order the user authored them; explicit
    -- column instead of relying on insert order.
    display_order   INTEGER       NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- All KR queries go via objective_id; (display_order) keeps the FE list
-- stable.
CREATE INDEX IF NOT EXISTS idx_okr_key_results_objective
    ON okr_key_results (objective_id, display_order);

-- Defence-in-depth — even though we go via objective_id, RLS still
-- needs an enterprise_id index for its own filter.
CREATE INDEX IF NOT EXISTS idx_okr_key_results_enterprise
    ON okr_key_results (enterprise_id);

-- updated_at on UPDATE — same pattern as risk_items / pipeline_runs.
CREATE OR REPLACE FUNCTION okr_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_okr_objectives_touch ON okr_objectives;
CREATE TRIGGER trg_okr_objectives_touch
    BEFORE UPDATE ON okr_objectives
    FOR EACH ROW EXECUTE FUNCTION okr_touch_updated_at();

DROP TRIGGER IF EXISTS trg_okr_key_results_touch ON okr_key_results;
CREATE TRIGGER trg_okr_key_results_touch
    BEFORE UPDATE ON okr_key_results
    FOR EACH ROW EXECUTE FUNCTION okr_touch_updated_at();


-- =========================================================================
-- RLS — same pattern as risk_items (033)
-- =========================================================================

ALTER TABLE okr_objectives  ENABLE ROW LEVEL SECURITY;
ALTER TABLE okr_key_results ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    -- okr_objectives policies
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'okr_objectives' AND policyname = 'tenant_okr_objectives'
    ) THEN
        CREATE POLICY tenant_okr_objectives ON okr_objectives
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'okr_objectives' AND policyname = 'admin_bypass_okr_objectives'
    ) THEN
        CREATE POLICY admin_bypass_okr_objectives ON okr_objectives
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;

    -- okr_key_results policies
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'okr_key_results' AND policyname = 'tenant_okr_key_results'
    ) THEN
        CREATE POLICY tenant_okr_key_results ON okr_key_results
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'okr_key_results' AND policyname = 'admin_bypass_okr_key_results'
    ) THEN
        CREATE POLICY admin_bypass_okr_key_results ON okr_key_results
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON okr_objectives  TO kaori_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON okr_key_results TO kaori_app;
-- DELETE on okr_key_results because the service rewrites the KR set on
-- objective save (delete-then-insert is simpler than diff-and-merge for
-- a typically-3-row child collection). Objectives stay soft-delete only.

COMMIT;
