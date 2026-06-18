-- 044_intervention_outcomes.sql — AI-INT-021 P15-S10 D3.
--
-- Pre/post adoption-score telemetry for interventions. Two checkpoints
-- per intervention (14 days + 30 days post-trigger) — each becomes a row
-- via the write_non_idempotent log_outcome activity (REL-005 dedup key
-- on (intervention_id, checkpoint_days) prevents duplicate rows on
-- workflow retry).
--
-- The capture_baseline activity (write_idempotent) UPSERTs into the
-- separate intervention_baselines columns of the same row; the workflow
-- writes baseline first then 2 checkpoint rows so the operator sees the
-- intervention lifecycle one row per checkpoint with the baseline
-- denormalised in.

CREATE TABLE IF NOT EXISTS intervention_outcomes (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Intervention identity
    intervention_id             TEXT NOT NULL,
    workflow_id                 TEXT NOT NULL,
    enterprise_id               UUID NOT NULL,                    -- K-1
    intervention_type           TEXT NOT NULL,                    -- 'csm_email' / 'manager_alert' / etc.

    -- Baseline (UPSERTed at trigger time per capture_baseline)
    triggered_at                TIMESTAMPTZ NOT NULL,
    pre_score                   NUMERIC(5, 2) NOT NULL,           -- composite 0-100
    pre_signals                 JSONB,                            -- snapshot of per-signal samples

    -- Checkpoint (this row's evaluation point)
    checkpoint_days             SMALLINT NOT NULL CHECK (checkpoint_days IN (14, 30)),
    evaluated_at                TIMESTAMPTZ NOT NULL,
    post_score                  NUMERIC(5, 2) NOT NULL,
    improvement                 NUMERIC(5, 2) NOT NULL,           -- post - pre
    classification              TEXT NOT NULL CHECK (classification IN ('effective', 'neutral', 'regression')),
    side_effects                JSONB DEFAULT '[]'::jsonb,        -- detected adjacent regressions

    -- Lifecycle
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    workflow_run_id             TEXT                              -- temporal workflow_run for traceability
);

-- Idempotency dedup — one row per (intervention, checkpoint).
-- Workflow retry hits the same row instead of duplicating telemetry.
CREATE UNIQUE INDEX IF NOT EXISTS intervention_outcomes_intervention_checkpoint_uniq
    ON intervention_outcomes (intervention_id, checkpoint_days);

-- Read paths:
--   1. Recent interventions for a tenant (admin dashboard)
CREATE INDEX IF NOT EXISTS intervention_outcomes_tenant_triggered_idx
    ON intervention_outcomes (enterprise_id, triggered_at DESC);

--   2. Effectiveness rate per intervention_type (recommendation engine
--      training query)
CREATE INDEX IF NOT EXISTS intervention_outcomes_type_classification_idx
    ON intervention_outcomes (intervention_type, classification);

-- RLS — tenant isolation per K-1 / ADR-0013.
ALTER TABLE intervention_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS intervention_outcomes_tenant_isolation ON intervention_outcomes;
CREATE POLICY intervention_outcomes_tenant_isolation ON intervention_outcomes
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

COMMENT ON TABLE  intervention_outcomes IS
    'P15-S10 D3 AI-INT-021 — pre/post adoption-score telemetry per intervention checkpoint (14d + 30d).';
COMMENT ON COLUMN intervention_outcomes.improvement IS
    'post_score - pre_score. >5 = effective per WORKFLOW_SYSTEM.md §31.4; <-5 = regression; in between = neutral.';
COMMENT ON COLUMN intervention_outcomes.side_effects IS
    'JSON array of detected regressions in adjacent signals (intervention fixed X but spiked Y).';
