-- =====================================================================
-- 077_roi_billing.sql
--
-- P2-S23 cross-cutting SH-M59 — ROI-Hybrid billing for ENT MAX opt-in
-- tier. Closes 5 features (SH-M59-001..005) per BACKLOG_V4:
--   001 — Cron monthly aggregate
--   002 — 0.015 × SUM(revenue_at_risk WHERE is_actioned=true)
--   003 — Cap 20M VND/tháng
--   004 — Chỉ áp dụng ENT MAX opt-in
--   005 — Yêu cầu ≥3 tháng data
--
-- 2 new tables:
--   enterprise_roi_subscriptions  — per-tenant opt-in state machine
--   enterprise_roi_billing_lines  — immutable monthly billing lines
--
-- Design choices
-- --------------
-- - Pricing model from CLAUDE.md §10: ENT ROI = 8M base + 1.5% revenue
--   saved (cap 20M). The 8M base lives in subscription_plans already;
--   THIS migration tracks ONLY the +1.5% add-on, computed monthly.
--
-- - 1.5% = 0.0150 stored as NUMERIC(5,4) per K-9.
--
-- - Cap 20,000,000 VND/month stored per-line so future cap changes
--   leave a paper trail. SH-M59-003.
--
-- - "≥3 tháng data" SH-M59-005 = the tenant must have ≥3 rows in
--   enterprise_monthly_billing prior to the billing month. Checked at
--   compute time; eligibility_met=FALSE lines preserved for audit
--   (capped_roi_addon_vnd=0) so anh can see why a tenant wasn't
--   charged.
--
-- - All inputs snapshotted into the line at compute time. Re-running
--   the cron does NOT modify a closed line — it skips months that
--   already have a row (idempotent K-13 spirit). Use the `notes`
--   column to mark recompute cases.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on both tables.
-- K-2 immutable billing: enterprise_roi_billing_lines is append-only;
--      uq_roi_enterprise_month prevents duplicates; no UPDATE path.
-- K-9 money precision: rate NUMERIC(5,4), cap + raw + capped
--      NUMERIC(18,4) (giant tenants might book 100M+ revenue_at_risk).
-- K-11 billing unit: revenue_at_risk pulled from gold_features (per
--      customer); SUM is per-enterprise-per-month with is_actioned=TRUE.
-- =====================================================================

BEGIN;

-- ─── ROI opt-in state machine ────────────────────────────────────────


CREATE TABLE IF NOT EXISTS enterprise_roi_subscriptions (
    enterprise_id              UUID         PRIMARY KEY
                                            REFERENCES enterprises(enterprise_id),
    opted_in_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    opted_out_at               TIMESTAMPTZ,
    -- Eligibility confirmed when cron first sees ≥3 closed billing
    -- months. opted_in_at is user intent; this is the "billing-active"
    -- date.
    eligibility_confirmed_at   TIMESTAMPTZ,
    notes                      TEXT,

    CONSTRAINT chk_roi_sub_optout_after_optin CHECK (
        opted_out_at IS NULL OR opted_out_at >= opted_in_at
    )
);

CREATE INDEX IF NOT EXISTS idx_roi_sub_active
    ON enterprise_roi_subscriptions(enterprise_id)
    WHERE opted_out_at IS NULL;


-- ─── Immutable monthly billing lines ─────────────────────────────────


CREATE TABLE IF NOT EXISTS enterprise_roi_billing_lines (
    line_id                       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id                 UUID          NOT NULL
                                                REFERENCES enterprises(enterprise_id),
    billing_month                 DATE          NOT NULL,

    -- Snapshot inputs at compute time (audit trail)
    actioned_revenue_at_risk_vnd  NUMERIC(18,4) NOT NULL,
    rate                          NUMERIC(5,4)  NOT NULL DEFAULT 0.0150,
    cap_threshold_vnd             NUMERIC(14,4) NOT NULL DEFAULT 20000000.0000,

    -- Outputs
    raw_roi_addon_vnd             NUMERIC(18,4) NOT NULL,
    capped_roi_addon_vnd          NUMERIC(18,4) NOT NULL,
    cap_applied                   BOOLEAN       NOT NULL,

    -- Eligibility check at compute time (SH-M59-005)
    months_of_data                INTEGER       NOT NULL,
    eligibility_met               BOOLEAN       NOT NULL,

    -- Audit
    computed_at                   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    computed_by_run_id            UUID,
    notes                         TEXT,

    CONSTRAINT uq_roi_enterprise_month UNIQUE (enterprise_id, billing_month),
    CONSTRAINT chk_roi_rate_positive
        CHECK (rate > 0 AND rate < 1),
    CONSTRAINT chk_roi_cap_positive
        CHECK (cap_threshold_vnd > 0),
    CONSTRAINT chk_roi_months_nonneg
        CHECK (months_of_data >= 0),
    CONSTRAINT chk_roi_revenue_nonneg
        CHECK (actioned_revenue_at_risk_vnd >= 0),
    CONSTRAINT chk_roi_addon_nonneg
        CHECK (raw_roi_addon_vnd >= 0 AND capped_roi_addon_vnd >= 0),
    CONSTRAINT chk_roi_capped_le_raw
        CHECK (capped_roi_addon_vnd <= raw_roi_addon_vnd),
    -- If capped, capped value equals cap exactly. If not capped, capped=raw.
    CONSTRAINT chk_roi_cap_consistency CHECK (
        (cap_applied = TRUE  AND capped_roi_addon_vnd = cap_threshold_vnd) OR
        (cap_applied = FALSE AND capped_roi_addon_vnd = raw_roi_addon_vnd)
    )
);

CREATE INDEX IF NOT EXISTS idx_roi_lines_enterprise_month
    ON enterprise_roi_billing_lines(enterprise_id, billing_month DESC);
CREATE INDEX IF NOT EXISTS idx_roi_lines_month
    ON enterprise_roi_billing_lines(billing_month DESC);


COMMENT ON TABLE enterprise_roi_subscriptions IS
    'SH-M59 — per-tenant opt-in for ROI-Hybrid pricing tier (ENT ROI). '
    'Opt-in is user intent; cron confirms eligibility (≥3 months of '
    'billing data, SH-M59-005) before charging.';
COMMENT ON TABLE enterprise_roi_billing_lines IS
    'SH-M59 — monthly ROI billing add-on lines. K-2 immutable: '
    'uq_roi_enterprise_month prevents duplicate runs; cron skips months '
    'already lined.';
COMMENT ON COLUMN enterprise_roi_billing_lines.raw_roi_addon_vnd IS
    'rate × actioned_revenue_at_risk_vnd, pre-cap. SH-M59-002.';
COMMENT ON COLUMN enterprise_roi_billing_lines.capped_roi_addon_vnd IS
    'min(raw, cap_threshold_vnd). What actually gets billed. SH-M59-003.';
COMMENT ON COLUMN enterprise_roi_billing_lines.eligibility_met IS
    'TRUE iff tenant has ≥3 prior closed billing months at compute time. '
    'FALSE lines preserved with capped_roi_addon_vnd=0 for audit.';

COMMIT;
