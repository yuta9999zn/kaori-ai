-- =====================================================================
-- 090_adoption_snapshots.sql
--
-- adoption_health_snapshots — per-tenant per-hour rolling history of
-- composite health score + classification, populated by the
-- adoption_hourly_aggregator Temporal cron (commit 3 of workflow-gap
-- closeout).
--
-- Captured_at always truncated to hour for natural-key dedup. UPSERT
-- by (enterprise_id, captured_at) keeps the table at bounded size.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS adoption_health_snapshots (
    snapshot_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    captured_at       TIMESTAMPTZ     NOT NULL,
    health_score      NUMERIC(5,4)    NOT NULL,
    classification    VARCHAR(32)     NOT NULL
                        CHECK (classification IN
                          ('healthy','stable','stretched','at_risk',
                            'churn_imminent','unknown')),
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, captured_at)
);

CREATE INDEX IF NOT EXISTS idx_adoption_snapshots_enterprise
    ON adoption_health_snapshots(enterprise_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_adoption_snapshots_at_risk
    ON adoption_health_snapshots(enterprise_id, captured_at DESC)
    WHERE classification IN ('at_risk','churn_imminent');

ALTER TABLE adoption_health_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS adoption_health_snapshots_isolation ON adoption_health_snapshots;
CREATE POLICY adoption_health_snapshots_isolation ON adoption_health_snapshots
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
