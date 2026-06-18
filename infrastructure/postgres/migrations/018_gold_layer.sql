-- Migration 018: Gold layer schema (F-032, Phase 1 close-out — Sprint 4-5)
--
-- Phase 1 ships the minimum viable Gold: a per-customer feature table
-- (gold_features) + a per-tenant rollup table (gold_aggregates). The
-- single business metric we compute is `revenue_at_risk` — the dollar
-- value of customers who haven't purchased in the last 90 days,
-- proxied by their historical average purchase value.
--
-- North Star alignment (CLAUDE.md §1):
--    SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)
--
-- Phase 1 ships the numerator only — `revenue_at_risk` measurement.
-- The `is_actioned` workflow that ties to the FE "I handled this customer"
-- button is **Phase 2 F-060** (per the locked scope decisions in
-- docs/PHASE1_CLOSEOUT_PLAN.md). The `is_actioned` column lives here in
-- 018 so Phase 2 doesn't need a follow-up migration; it just stays
-- DEFAULT FALSE through Phase 1.
--
-- Risk R1 (PHASE1_CLOSEOUT_PLAN §Risk register): silver_rows.clean_data
-- JSONB does NOT consistently expose `customer_external_id` across
-- pipelines today (verified 2026-04-27 — language_dictionary.json has no
-- such canonical key). The aggregator reads the JSONB key by name with
-- the default `customer_external_id` and falls through to a configurable
-- override; pilot tenants must map their customer-id column to that
-- canonical name during onboarding. Documented in
-- docs/specs/MEDALLION_CONTRACT.md (added in this PR).

BEGIN;

-- =========================================================================
-- gold_features — per-customer features for one tenant
-- =========================================================================
CREATE TABLE IF NOT EXISTS gold_features (
    enterprise_id           UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    customer_external_id    TEXT            NOT NULL,

    -- Features the Phase 1 aggregator writes
    revenue_at_risk         NUMERIC(14,4)   NOT NULL DEFAULT 0,   -- K-9 money precision
    last_purchase_at        TIMESTAMPTZ,
    total_purchases         NUMERIC(14,4),                          -- lifetime sum (≈ proxy for tenure value)
    purchase_count          INTEGER         NOT NULL DEFAULT 0,
    avg_purchase_value      NUMERIC(14,4),

    -- Phase 2 F-060 hook — present so the table doesn't need a
    -- follow-up migration when the FE "mark as actioned" button lands.
    is_actioned             BOOLEAN         NOT NULL DEFAULT FALSE,
    actioned_at             TIMESTAMPTZ,

    computed_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, customer_external_id)
);

-- Recent-aggregator queries (FE dashboard, Phase 2 ML training pulls).
CREATE INDEX IF NOT EXISTS idx_gold_features_recent
    ON gold_features(enterprise_id, computed_at DESC);

-- "All at-risk customers for this tenant" — partial index keeps it tiny;
-- the typical row has revenue_at_risk = 0.
CREATE INDEX IF NOT EXISTS idx_gold_features_at_risk
    ON gold_features(enterprise_id, revenue_at_risk DESC)
    WHERE revenue_at_risk > 0;

COMMENT ON TABLE gold_features IS
    'F-032 — per-customer feature row. revenue_at_risk is the only metric '
    'computed in Phase 1; is_actioned is reserved for Phase 2 F-060.';

COMMENT ON COLUMN gold_features.revenue_at_risk IS
    'Heuristic: 0 if last_purchase within 90d; else avg_purchase_value, '
    'capped at sum(purchases in last 12 months). NUMERIC(14,4) per K-9.';

-- =========================================================================
-- gold_aggregates — per-tenant rollups, written alongside gold_features
-- =========================================================================
CREATE TABLE IF NOT EXISTS gold_aggregates (
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    metric_key      TEXT            NOT NULL,
    metric_value    NUMERIC(14,4)   NOT NULL,                       -- K-9 precision
    computed_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, metric_key)
);

CREATE INDEX IF NOT EXISTS idx_gold_aggregates_recent
    ON gold_aggregates(enterprise_id, computed_at DESC);

COMMENT ON TABLE gold_aggregates IS
    'F-032 — per-tenant scalar metrics. Phase 1 writes total_revenue_at_risk '
    'and at_risk_customer_count; Phase 2 will add churn_risk_label rollups.';

-- =========================================================================
-- RLS — same pattern as 005_rls.sql. ai-orchestrator + data-pipeline
-- read these via acquire_for_tenant which sets app.enterprise_id; auth-
-- service (superuser) BYPASSRLS. Row-level filter applies the moment
-- kaori_app drops BYPASSRLS in a future migration.
-- =========================================================================
ALTER TABLE gold_features   ENABLE ROW LEVEL SECURITY;
ALTER TABLE gold_aggregates ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                    WHERE tablename = 'gold_features' AND policyname = 'tenant_gold_features') THEN
        CREATE POLICY tenant_gold_features ON gold_features
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies
                    WHERE tablename = 'gold_aggregates' AND policyname = 'tenant_gold_aggregates') THEN
        CREATE POLICY tenant_gold_aggregates ON gold_aggregates
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

ALTER TABLE gold_features   FORCE ROW LEVEL SECURITY;
ALTER TABLE gold_aggregates FORCE ROW LEVEL SECURITY;

-- kaori_app GRANTs come from DEFAULT PRIVILEGES in 008_kaori_app_grants.sql.

COMMIT;
