-- Migration 019: decision_actions — Sprint 7 PR D (North Star manual toggle)
--
-- Purpose
-- =======
-- Half-closes the Phase 1 limitation that the North Star metric only
-- measures `revenue_at_risk` numerator without the `is_actioned`
-- predicate that the formula requires:
--
--    SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)
--
-- The full Phase 2 workflow (F-060) ships a per-customer "I handled
-- this" surface tied to gold_features. Until then, pilot CS team
-- tracks actioned customers in a spreadsheet — this migration moves
-- that tracking *into the product* by attaching an `is_actioned`
-- toggle to each row in `decision_audit_log` (the AI-decision detail
-- the /decisions page surfaces).
--
-- Why a side table instead of an UPDATE column on decision_audit_log:
--   * K-2 invariant — decision_audit_log is append-only at the rule
--     layer (001/002 `decision_audit_no_update` / `no_delete`). An
--     UPDATE would require dropping that rule, weakening the audit
--     guarantee everywhere.
--   * The action is a *separate* fact (CS reached out / customer
--     responded), distinct from the AI decision itself. Storing it
--     orthogonally keeps the two facts decoupled.
--
-- Why not gold_features.is_actioned (Phase 2 home of the canonical
-- column):
--   * gold_features rows are per-customer; decision_audit_log rows
--     are per-AI-decision. Decisions don't currently carry a
--     customer_external_id linkage strong enough to join 1:1.
--   * gold_features.is_actioned will land in F-060 with the proper
--     per-customer UI. Pilot CS using /decisions toggle is a
--     stop-gap; the table named below makes the stop-gap nature
--     obvious and easy to drop later.
--
-- One row per (decision_id) — UPSERT semantics on toggle.
-- Tenant isolation via RLS, mirroring tenant_settings.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS decision_actions (
    decision_id     UUID            PRIMARY KEY
                                    REFERENCES decision_audit_log(decision_id)
                                    ON DELETE CASCADE,
    enterprise_id   UUID            NOT NULL
                                    REFERENCES enterprises(enterprise_id)
                                    ON DELETE CASCADE,
    is_actioned     BOOLEAN         NOT NULL DEFAULT FALSE,
    actioned_at     TIMESTAMPTZ,
    actioned_by     UUID            REFERENCES enterprise_users(user_id)
                                    ON DELETE SET NULL,
    notes           TEXT            CHECK (notes IS NULL OR length(notes) <= 2000),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Filter index for the rolled-up "actioned this month" query that the
-- North Star metric will read once F-060 wires this column into the
-- top-of-dashboard tile. Cheap; the table will stay small (one row
-- per actioned decision per tenant per month).
CREATE INDEX IF NOT EXISTS idx_decision_actions_tenant_actioned
    ON decision_actions(enterprise_id, actioned_at DESC)
    WHERE is_actioned = TRUE;

-- Auto-update updated_at on every UPSERT.
CREATE OR REPLACE FUNCTION decision_actions_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_decision_actions_touch ON decision_actions;
CREATE TRIGGER trg_decision_actions_touch
    BEFORE UPDATE ON decision_actions
    FOR EACH ROW
    EXECUTE FUNCTION decision_actions_touch_updated_at();

-- RLS: same pattern as tenant_settings.
ALTER TABLE decision_actions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'decision_actions' AND policyname = 'decision_actions_isolation'
    ) THEN
        CREATE POLICY decision_actions_isolation ON decision_actions
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE decision_actions FORCE ROW LEVEL SECURITY;

COMMIT;
