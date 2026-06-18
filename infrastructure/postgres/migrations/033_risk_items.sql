-- Migration 033: F-039 Risk Management — per-tenant risk register.
--
-- Why this exists
-- ===============
-- Phase 2 sprint 2.2 — pilot enterprises maintain a risk register
-- (operational, financial, compliance, market) and want to track
-- mitigation progress + alert when a risk crosses a severity
-- threshold. v0 is a manual CRUD: a MANAGER creates risk_items,
-- assigns an owner, sets likelihood/impact, fills mitigation plan.
-- Auto-detection from data (anomaly detection, drift, threshold
-- breach) is a v1 follow-up that needs an analysis layer.
--
-- Schema
-- ======
-- risk_items: one row per risk. Soft-delete via deleted_at so the
-- audit trail outlives a "wrong entry" cleanup. Score is computed
-- column-style at write time (likelihood × impact, 1-25 range)
-- because the FE heat map sorts by it constantly; computing once
-- avoids expensive ORDER BY.
--
--   likelihood × impact = score (1..25)
--   severity tier:
--     score >= 15 → 'critical'      (red)
--     score >=  9 → 'high'          (orange)
--     score >=  5 → 'medium'        (yellow)
--     score >=  1 → 'low'           (green)
--
-- Status workflow:
--     open       → not yet being worked on
--     mitigating → owner is actively reducing it
--     closed     → resolved (still readable for audit)
--
-- mitigation_progress is an integer 0-100 the FE renders as a bar.
-- The owner is an enterprise_users.user_id; FK enforces visibility,
-- ON DELETE SET NULL so deleting a user soft-orphans the risk row
-- rather than cascading away a load-bearing audit record.
--
-- RLS
-- ===
-- Standard tenant_isolation + admin_bypass pattern (matches alerts
-- migration 028, decision_overrides migration 031).
--
-- Reversibility
-- =============
--   DROP TABLE risk_items;
-- Service rollback: removing the controller from auth-service reverts
-- the API surface; existing rows stay (DROP TABLE is the only path
-- to wipe them, by design — risks are audit data).
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS risk_items (
    risk_id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Identity
    title                VARCHAR(200) NOT NULL,
    description          TEXT,

    -- Heat map axes — both 1..5 with CHECK so the score arithmetic
    -- below stays sane (1..25). FE sliders enforce client-side too.
    likelihood           SMALLINT     NOT NULL
                                      CHECK (likelihood BETWEEN 1 AND 5),
    impact               SMALLINT     NOT NULL
                                      CHECK (impact BETWEEN 1 AND 5),

    -- Computed at INSERT/UPDATE time (see triggers below). The
    -- generated-column form would be cleaner but Postgres 15
    -- requires the expression be IMMUTABLE; we keep the trigger
    -- approach for portability with future enriched scoring (e.g.
    -- decay over time when no progress).
    score                SMALLINT     NOT NULL DEFAULT 0
                                      CHECK (score BETWEEN 0 AND 25),

    -- Severity is the bucketed score the FE renders as a coloured
    -- badge. Always computed by the trigger; no client-side write.
    severity             VARCHAR(10)  NOT NULL DEFAULT 'low'
                                      CHECK (severity IN ('low', 'medium', 'high', 'critical')),

    -- Workflow status
    status               VARCHAR(20)  NOT NULL DEFAULT 'open'
                                      CHECK (status IN ('open', 'mitigating', 'closed')),

    -- Mitigation
    mitigation_plan      TEXT,
    mitigation_progress  SMALLINT     NOT NULL DEFAULT 0
                                      CHECK (mitigation_progress BETWEEN 0 AND 100),

    -- Ownership
    -- ON DELETE SET NULL — losing an enterprise_users row should not
    -- cascade-delete the risk audit trail. The FE renders "(no owner)"
    -- for orphaned rows.
    owner_user_id        UUID         REFERENCES enterprise_users(user_id) ON DELETE SET NULL,
    due_date             DATE,

    -- Source: 'manual' for v0; v1 will add 'auto' for anomaly-detected
    -- risks. CHECK keeps the DB authoritative.
    source               VARCHAR(20)  NOT NULL DEFAULT 'manual'
                                      CHECK (source IN ('manual', 'auto')),

    -- Audit
    created_by_user      UUID,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Soft delete
    deleted_at           TIMESTAMPTZ
);

-- Hot path: heat map / list endpoint sort by score DESC for the calling tenant.
CREATE INDEX IF NOT EXISTS idx_risk_items_tenant_score
    ON risk_items(enterprise_id, score DESC, risk_id DESC)
    WHERE deleted_at IS NULL;

-- "Open risks per owner" support query.
CREATE INDEX IF NOT EXISTS idx_risk_items_owner_open
    ON risk_items(enterprise_id, owner_user_id, status)
    WHERE deleted_at IS NULL AND status != 'closed';

-- Severity rollup ("how many critical right now") — partial keeps it tiny.
CREATE INDEX IF NOT EXISTS idx_risk_items_severity_open
    ON risk_items(enterprise_id, severity)
    WHERE deleted_at IS NULL AND status != 'closed';

-- Trigger: keep score + severity in sync on every insert/update.
-- IMMUTABLE-friendly logic kept inline so the index above can use the
-- computed columns. Updating likelihood OR impact recomputes both;
-- updating other fields leaves the cached values alone.
CREATE OR REPLACE FUNCTION risk_items_score_severity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.score := NEW.likelihood * NEW.impact;
    NEW.severity := CASE
        WHEN NEW.score >= 15 THEN 'critical'
        WHEN NEW.score >=  9 THEN 'high'
        WHEN NEW.score >=  5 THEN 'medium'
        ELSE                       'low'
    END;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_risk_items_score_severity ON risk_items;
CREATE TRIGGER trg_risk_items_score_severity
    BEFORE INSERT OR UPDATE OF likelihood, impact
    ON risk_items
    FOR EACH ROW EXECUTE FUNCTION risk_items_score_severity();

-- Lighter trigger: bump updated_at on every UPDATE so the FE can
-- show "edited X minutes ago" without trusting client clocks.
CREATE OR REPLACE FUNCTION risk_items_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_risk_items_touch ON risk_items;
CREATE TRIGGER trg_risk_items_touch
    BEFORE UPDATE
    ON risk_items
    FOR EACH ROW
    -- Skip when the score trigger already touched updated_at (avoids
    -- double-bump in a single statement).
    WHEN (NEW.likelihood IS NOT DISTINCT FROM OLD.likelihood
      AND NEW.impact     IS NOT DISTINCT FROM OLD.impact)
    EXECUTE FUNCTION risk_items_touch_updated_at();

ALTER TABLE risk_items ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'risk_items' AND policyname = 'tenant_risk_items'
    ) THEN
        CREATE POLICY tenant_risk_items ON risk_items
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'risk_items' AND policyname = 'admin_bypass_risk_items'
    ) THEN
        CREATE POLICY admin_bypass_risk_items ON risk_items
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON risk_items TO kaori_app;
-- No DELETE — soft-delete only via deleted_at column.

COMMIT;
