-- Migration 016: alert flags + last-aggregated marker on enterprise_monthly_billing
--                 (F-031 — Unique Billing Cron, Phase 1 close-out)
--
-- The cron job (BillingAggregationJob, daily 02:00 ICT) needs three things
-- the original 001 schema doesn't have:
--
--   * alert_80_fired       — set TRUE the first time usage crosses 80% of
--                            quota in the current billing_month. Idempotent:
--                            the cron only flips it FALSE→TRUE, never the
--                            other way, so the in-app banner doesn't blink
--                            on/off as a noisy tenant flutters around the
--                            threshold. Reset once a new billing_month row
--                            is created (DEFAULT FALSE on insert).
--   * alert_95_fired       — same shape, 95% threshold. Drives the upgrade-
--                            suggestion banner (CLAUDE.md §10).
--   * last_aggregated_at   — wall-clock of the most recent successful cron
--                            pass for this enterprise+month. Acts as a
--                            lightweight audit trail (we don't write to
--                            platform_admin_audit_log because admin_id is
--                            NOT NULL there, and the cron is a system actor
--                            with no admin row to point at).
--
-- Why no email column / no notification_sent_at: F-031 ships option (a) per
-- PHASE1_CLOSEOUT_PLAN — DB threshold flags only, no email dispatch. Phase 2
-- F-037 (Alert Rules) wires the actual delivery channel.

BEGIN;

ALTER TABLE enterprise_monthly_billing
    ADD COLUMN IF NOT EXISTS alert_80_fired      BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS alert_95_fired      BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS last_aggregated_at  TIMESTAMPTZ;

COMMENT ON COLUMN enterprise_monthly_billing.alert_80_fired IS
    'F-031 — set TRUE on first cron pass where unique_customers ≥ 80% of quota '
    'within this billing_month. Idempotent (only flipped FALSE→TRUE).';

COMMENT ON COLUMN enterprise_monthly_billing.alert_95_fired IS
    'F-031 — same shape as alert_80_fired, 95% threshold. Drives upgrade banner.';

COMMENT ON COLUMN enterprise_monthly_billing.last_aggregated_at IS
    'F-031 — wall-clock of the last successful BillingAggregationJob pass. '
    'Lightweight audit trail (we cannot write to platform_admin_audit_log '
    'because admin_id is NOT NULL and the cron is a system actor).';

-- Index for the F-030 FE banner query — \"any tenant currently in alert?\".
-- Partial index keeps it tiny because almost no rows have either flag set.
CREATE INDEX IF NOT EXISTS idx_emb_alert_active
    ON enterprise_monthly_billing(enterprise_id, billing_month)
    WHERE alert_80_fired = TRUE OR alert_95_fired = TRUE;

COMMIT;
