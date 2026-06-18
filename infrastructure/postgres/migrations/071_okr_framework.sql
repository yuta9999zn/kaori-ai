-- =====================================================================
-- 071_okr_framework.sql
--
-- P2-S21 D5 — P2-M212-001 OKR (Objectives + Key Results) framework.
--
-- 3 tables:
--   okrs                — top-level objective per enterprise/dept/period
--   key_results         — measurable KRs under each OKR (1-N)
--   workflow_okr_links  — many-to-many: workflows contributing to OKRs
--
-- Design choices
-- --------------
-- - progress is denormalized on `okrs` (recalc from KRs on write). The
--   computation is a weighted sum of per-KR (current/target) clamped to
--   1.0. Avoids costly aggregations on read; the write path is the
--   bottleneck (KR updates are 1-N per quarter, not real-time).
-- - period_label is freeform (Q1 2026 / 2026-H1 / 2026 / FY26). The
--   start/end dates are the source-of-truth; the label is for display.
-- - workflow_okr_links allows N workflows per OKR + N OKRs per workflow.
--   contribution_weight ∈ (0, 1] signals how much workflow ROI matters
--   for the OKR — used by NOV-RPT-023 (mig 069's negative-NOV path) to
--   rank "which OKR is the bad workflow blocking?".
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on okrs + denormalized on key_results +
--          workflow_okr_links so RLS filter is direct (no join needed).
-- K-9: target_value/current_value/baseline_value NUMERIC(20,4) — large
--      range for revenue OKRs in VND ("doanh thu Q1 5,000,000,000 ₫").
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS okrs (
    okr_id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    workspace_id      UUID,
    department_id     UUID,
    objective_text    VARCHAR(500) NOT NULL,
    objective_text_vi VARCHAR(500),
    period_label      VARCHAR(32)  NOT NULL,
    period_start      DATE         NOT NULL,
    period_end        DATE         NOT NULL,
    owner_user_id     UUID,
    status            VARCHAR(16)  NOT NULL DEFAULT 'DRAFT',
    progress          NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    notes             TEXT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_okr_status CHECK (status IN (
        'DRAFT', 'ACTIVE', 'ACHIEVED', 'MISSED', 'CANCELLED'
    )),
    CONSTRAINT chk_okr_progress_range CHECK (progress >= 0 AND progress <= 1),
    CONSTRAINT chk_okr_period_order CHECK (period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS idx_okrs_enterprise_period
    ON okrs(enterprise_id, period_label)
    WHERE status IN ('DRAFT', 'ACTIVE');

CREATE INDEX IF NOT EXISTS idx_okrs_department
    ON okrs(department_id) WHERE department_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS key_results (
    kr_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    okr_id          UUID         NOT NULL REFERENCES okrs(okr_id) ON DELETE CASCADE,
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    kr_text         VARCHAR(500) NOT NULL,
    kr_text_vi      VARCHAR(500),
    metric_type     VARCHAR(32)  NOT NULL,
    target_value    NUMERIC(20,4) NOT NULL,
    current_value   NUMERIC(20,4) NOT NULL DEFAULT 0,
    baseline_value  NUMERIC(20,4) NOT NULL DEFAULT 0,
    weight          NUMERIC(5,4)  NOT NULL DEFAULT 0.25,
    unit            VARCHAR(32),
    sort_order      INTEGER       NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_kr_metric_type CHECK (metric_type IN (
        'count', 'percentage', 'currency', 'score', 'duration', 'binary'
    )),
    CONSTRAINT chk_kr_weight_range CHECK (weight > 0 AND weight <= 1)
);

CREATE INDEX IF NOT EXISTS idx_key_results_okr ON key_results(okr_id);
CREATE INDEX IF NOT EXISTS idx_key_results_enterprise ON key_results(enterprise_id);


CREATE TABLE IF NOT EXISTS workflow_okr_links (
    link_id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id          UUID         NOT NULL,
    okr_id               UUID         NOT NULL REFERENCES okrs(okr_id) ON DELETE CASCADE,
    enterprise_id        UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    contribution_weight  NUMERIC(5,4) NOT NULL DEFAULT 0.5,
    notes                TEXT,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_link_weight CHECK (contribution_weight > 0 AND contribution_weight <= 1),
    CONSTRAINT uq_workflow_okr UNIQUE(workflow_id, okr_id)
);

-- workflow_id FK declared without REFERENCES because workflows is in
-- the same schema but the existing mig 053 didn't reference it as PK
-- target for cross-table FK from this many-to-many table. We rely on
-- application-level integrity (router checks workflow exists before
-- linking) + ON DELETE CASCADE only on the okr_id side.

CREATE INDEX IF NOT EXISTS idx_workflow_okr_workflow ON workflow_okr_links(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_okr_okr ON workflow_okr_links(okr_id);


COMMENT ON TABLE okrs IS
    'P2-S21 D5 (P2-M212-001) — Top-level Objective per enterprise/dept/period. '
    'progress denormalized from key_results weighted sum on write.';
COMMENT ON COLUMN okrs.progress IS
    'NUMERIC(5,4) 0..1 — weighted aggregate from key_results. Recomputed '
    'on KR update via router. Stale data risk on direct SQL writes.';
COMMENT ON TABLE workflow_okr_links IS
    'Many-to-many: workflows contributing to OKRs. contribution_weight '
    'feeds NOV-RPT-023 ranking of blocked OKRs.';

COMMIT;
