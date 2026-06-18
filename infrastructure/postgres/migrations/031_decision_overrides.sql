-- Migration 031: F-036 Decision Override — append-only override history.
--
-- Why this exists
-- ===============
-- F-029 (Sprint 2) shipped read-only ``/api/v1/decisions`` (list + CSV).
-- Sprint 7 PR D added ``decision_actions`` (per-decision is_actioned
-- toggle — half-closing the North Star formula in CLAUDE.md §14).
-- F-036 closes the loop: when a domain expert disagrees with an AI
-- decision, they record an explicit override + reason, and the
-- ``kaori.feedback.actions`` Kafka topic publishes the event so future
-- F-074 fine-tuning + F-060 ROI rollup pick it up.
--
-- Schema
-- ======
-- decision_overrides: append-only history. Every override creates a
-- new row — no UPDATE/DELETE on the row itself. Soft-revoke uses
-- ``revoked_at`` + ``revoked_by_user`` + ``revoke_reason`` so the
-- audit trail keeps the original action visible. Latest non-revoked
-- override per decision_id is the "current" override the FE renders.
--
-- Why not augment decision_audit_log directly
-- =============================================
-- Same reason decision_actions is a side table (migration 019 header):
-- decision_audit_log is append-only at the rule layer
-- (decision_audit_no_update + no_delete) — an UPDATE column would
-- need dropping those rules and lose K-2's strict no-mutation
-- guarantee. Override is a *separate* event by a *human*; storing it
-- alongside but in its own table keeps both stories clean.
--
-- Why allow multiple overrides per decision
-- ===========================================
-- A user might override → realise mistake → revoke → override again
-- with a corrected value. Each step deserves its own row for forensics.
-- The FE join "latest WHERE revoked_at IS NULL" picks the current
-- effective override; the rest are audit history.
--
-- RLS
-- ===
-- Standard tenant_isolation + admin_bypass pattern (matches
-- decision_actions migration 019 + reports migration 027). The
-- decision_audit_log FK enforces the override row references only
-- visible decisions; combined with RLS that means a cross-tenant
-- override is impossible at both the FK level and the SELECT level.
--
-- Reversibility
-- =============
--   DROP TABLE decision_overrides;
-- Service rollback: removing the POST/{id}/override + GET /{id}
-- handlers from routers/decisions.py disables override; the existing
-- list + action toggle keep working untouched.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS decision_overrides (
    override_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id      UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Which decision row is being overridden. CASCADE on delete so
    -- if a tenant ever purges its decision_audit_log (rare; the rule
    -- layer blocks it but admin maintenance scripts can bypass) the
    -- override history goes with it.
    decision_id        UUID         NOT NULL REFERENCES decision_audit_log(decision_id) ON DELETE CASCADE,

    -- Snapshot of the AI's chosen_value at override time. The audit
    -- log row itself is immutable so this is "redundant by design"
    -- — readers can confirm the override was against THIS choice
    -- even if the audit log row was somehow rotated/archived.
    original_chosen_value VARCHAR(500),

    -- The human-supplied correct value. VARCHAR(500) matches
    -- decision_audit_log.chosen_value width.
    override_value     VARCHAR(500) NOT NULL,

    -- Why the user disagreed. Required — an override without a
    -- reason is just noise to ML retraining downstream. 2000 chars
    -- mirrors the existing notes column on decision_actions so the
    -- two side tables stay shape-compatible for unioned audit views.
    reason             TEXT         NOT NULL CHECK (length(reason) <= 2000),

    -- Who pressed the button. NULL only when an automated flow
    -- writes (rare; today every override is human).
    overridden_by_user UUID,

    overridden_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Soft revoke. The override stays in history; the FE filters by
    -- ``revoked_at IS NULL`` for the active override.
    revoked_at         TIMESTAMPTZ,
    revoked_by_user    UUID,
    revoke_reason      TEXT
);

-- Hot path: FE detail page shows override history for one decision.
CREATE INDEX IF NOT EXISTS idx_decision_overrides_decision
    ON decision_overrides(decision_id, overridden_at DESC);

-- Tenant rollup: "show me everything my team has overridden in the last week".
CREATE INDEX IF NOT EXISTS idx_decision_overrides_tenant
    ON decision_overrides(enterprise_id, overridden_at DESC);

-- "Currently effective" override per decision — partial index on
-- non-revoked rows is the FE's typical join target.
CREATE INDEX IF NOT EXISTS idx_decision_overrides_active
    ON decision_overrides(decision_id, overridden_at DESC)
    WHERE revoked_at IS NULL;

ALTER TABLE decision_overrides ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'decision_overrides' AND policyname = 'tenant_decision_overrides'
    ) THEN
        CREATE POLICY tenant_decision_overrides ON decision_overrides
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'decision_overrides' AND policyname = 'admin_bypass_decision_overrides'
    ) THEN
        CREATE POLICY admin_bypass_decision_overrides ON decision_overrides
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON decision_overrides TO kaori_app;
-- UPDATE is needed for the soft-revoke endpoint; the column-level
-- audit story is preserved because revoke writes to revoked_* only,
-- never the original override_value/reason fields.

COMMIT;
