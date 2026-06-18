-- Migration 028: F-037 Alert Rules — first dispatcher of notification_outbox
-- for billing quota alerts, plus per-tenant custom rule storage.
--
-- Why this exists
-- ===============
-- F-031 (Sprint 3) shipped the billing aggregator with TRUE-only flag
-- flips on enterprise_monthly_billing.alert_80_fired / alert_95_fired
-- but explicitly deferred email dispatch to F-037 (see PHASE1_CLOSEOUT_PLAN
-- decision row #2). PR #110 (Issue #6) later landed notification_outbox
-- and the polling dispatcher in notification-service. F-037 closes the
-- loop: when the billing aggregator flips a flag for the first time in
-- a billing month, this migration's tables let us
--   (a) record the fire as a structured event (alert_events)
--   (b) rate-limit re-fires per-rule (default cooldown 300s)
--   (c) attach the outbox_id so support can trace "user said email
--       didn't arrive" → alert_events → outbox → SMTP attempts
-- and as a side-benefit lets MANAGER-role enterprise users CRUD their
-- own custom rules later (alert_rules).
--
-- Two tables
-- ==========
--   * alert_rules   — per-tenant CRUD. Pilot v0 metric_type = 'billing_quota_pct'.
--                     Future metrics (gold_revenue_at_risk, churn_rate, etc.)
--                     extend the CHECK list additively. Soft-delete via
--                     deleted_at timestamp; the FE never shows tombstones.
--   * alert_events  — append-only history. One row per dispatched fire
--                     (or one row per rate-limit-suppressed near-fire when
--                     suppressed=true). The (rule_id, fired_at) index is
--                     the cooldown lookup hot path.
--
-- Implicit defaults
-- =================
-- Billing 80% / 95% alerts fire for EVERY active enterprise even if the
-- tenant has no custom alert_rule row. The dispatcher in BillingAlertService
-- materialises an implicit "system" rule with stable sentinel rule_ids
-- (hardcoded UUIDs below) when looking up existing alert_events for cooldown.
-- This avoids per-enterprise seed bloat (~thousands of identical rows on
-- a healthy platform) and keeps "tenant has not configured anything" the
-- common path.
--
-- RLS
-- ===
-- Both tables follow the standard tenant_isolation + admin_bypass pattern
-- from migration 025. alert_rules is straight tenant-scoped. alert_events
-- is also tenant-scoped — the cooldown SELECT happens under the
-- BillingAggregationService transaction which already binds
-- ``app.enterprise_id`` (see BillingAggregationService line 135).
--
-- Reversibility
-- =============
--   DROP TABLE alert_events;
--   DROP TABLE alert_rules;
-- Service rollback: the dispatcher call from BillingAggregationService is
-- best-effort log+swallow (same pattern as NotificationOutboxRepository);
-- removing it leaves billing aggregation working as in Phase 1.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. alert_rules — per-tenant custom rules + (later) channel config
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_rules (
    rule_id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id      UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    name               VARCHAR(120) NOT NULL,
    description        TEXT,

    -- What metric the rule evaluates against. v0 ships 'billing_quota_pct'
    -- only — the only metric the F-031 aggregator emits. Future metrics
    -- (e.g., 'gold_revenue_at_risk_pct', 'pipeline_failure_count') extend
    -- this CHECK additively.
    metric_type        VARCHAR(50)  NOT NULL
                                    CHECK (metric_type IN ('billing_quota_pct')),

    -- Comparison operator. Evaluator computes (metric_value OP threshold_value).
    operator           VARCHAR(8)   NOT NULL
                                    CHECK (operator IN ('gt', 'gte', 'lt', 'lte', 'eq')),

    -- NUMERIC(14,4) per K-9 — same precision as money / rates elsewhere.
    -- For percentages, 80% is stored as 80.0000, not 0.8.
    threshold_value    NUMERIC(14, 4) NOT NULL,

    -- Delivery channel. v0 = 'email' only. Phase 2 follow-ups add 'slack'
    -- + 'webhook' (see F-037 Phase 2 follow-ups list in BACKLOG.md).
    channel            VARCHAR(40)  NOT NULL DEFAULT 'email'
                                    CHECK (channel IN ('email')),

    -- Optional override of the recipient. NULL falls back to the tenant's
    -- notification_email (tenant_settings) and then to all MANAGER users.
    target_email       VARCHAR(320),

    -- Cooldown in seconds — minimum gap between two fires of the same rule.
    -- Default 300s (5 min) matches the BACKLOG line "rate limit 1/5min".
    cooldown_seconds   INTEGER      NOT NULL DEFAULT 300
                                    CHECK (cooldown_seconds >= 0),

    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,

    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Soft delete — DELETE endpoint sets deleted_at instead of removing
    -- the row, so historical alert_events keep a readable rule reference.
    deleted_at         TIMESTAMPTZ
);

-- Hot path: dispatcher looks up active rules per enterprise + metric_type.
CREATE INDEX IF NOT EXISTS idx_alert_rules_tenant_metric
    ON alert_rules(enterprise_id, metric_type)
    WHERE deleted_at IS NULL AND is_active = TRUE;

-- List endpoint sorts by created_at DESC for the FE table.
CREATE INDEX IF NOT EXISTS idx_alert_rules_tenant_created
    ON alert_rules(enterprise_id, created_at DESC)
    WHERE deleted_at IS NULL;

ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'alert_rules' AND policyname = 'tenant_alert_rules'
    ) THEN
        CREATE POLICY tenant_alert_rules ON alert_rules
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'alert_rules' AND policyname = 'admin_bypass_alert_rules'
    ) THEN
        CREATE POLICY admin_bypass_alert_rules ON alert_rules
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON alert_rules TO kaori_app;

-- ============================================================
-- 2. alert_events — append-only fire history (also the cooldown table)
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_events (
    event_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id      UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- rule_id is NOT a FK so implicit-default fires (the seeded
    -- billing-80 / billing-95 sentinel UUIDs declared as constants in
    -- BillingAlertService) work without seeding alert_rules per
    -- enterprise. Custom-rule fires reference an alert_rules.rule_id;
    -- a CASCADE-delete of the rule deletes its event history via the
    -- explicit cleanup the soft-delete path doesn't trigger (deleted_at
    -- is null-safe, so events outlive soft-deleted rules — which is the
    -- intended forensics behaviour).
    rule_id            UUID         NOT NULL,

    -- Snapshot at fire time — kept here so the email body / FE history
    -- list doesn't need a JOIN to alert_rules (which may have been
    -- edited or soft-deleted between fire and read).
    metric_type        VARCHAR(50)  NOT NULL,
    metric_value       NUMERIC(14, 4) NOT NULL,
    threshold_value    NUMERIC(14, 4) NOT NULL,
    operator           VARCHAR(8)   NOT NULL,

    -- Free-form context the dispatcher passes to the email template
    -- (enterprise_name, plan, used, quota, upgrade_url, etc.). Same
    -- shape as notification_outbox.context.
    context            JSONB        NOT NULL DEFAULT '{}'::jsonb,

    -- Pointer to the outbox row created by this fire. NULL when the
    -- fire was suppressed by cooldown (suppressed=TRUE) or when channel
    -- dispatch is non-email (Phase 2). Lets support trace
    -- "alert fired" → "email delivered" in one query.
    outbox_id          UUID,

    -- Cooldown bookkeeping — the dispatcher writes a row even when the
    -- rule was suppressed by an earlier fire within cooldown_seconds.
    -- This makes "we've recently fired this rule" the single SELECT
    -- against alert_events; alert_rules itself has no last_fired_at
    -- column. Suppressed rows skip outbox enqueue but still appear in
    -- the FE history view (filterable).
    suppressed         BOOLEAN      NOT NULL DEFAULT FALSE,

    fired_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Cooldown lookup: "has this rule fired in the last N seconds?"
-- The dispatcher SELECTs MAX(fired_at) WHERE rule_id = :id AND suppressed = FALSE.
-- Partial index keeps it tiny because suppressed rows are append-only
-- forensic noise, not part of cooldown math.
CREATE INDEX IF NOT EXISTS idx_alert_events_rule_fired
    ON alert_events(rule_id, fired_at DESC)
    WHERE suppressed = FALSE;

-- FE history list ("my recent alerts").
CREATE INDEX IF NOT EXISTS idx_alert_events_tenant_fired
    ON alert_events(enterprise_id, fired_at DESC);

ALTER TABLE alert_events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'alert_events' AND policyname = 'tenant_alert_events'
    ) THEN
        CREATE POLICY tenant_alert_events ON alert_events
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'alert_events' AND policyname = 'admin_bypass_alert_events'
    ) THEN
        CREATE POLICY admin_bypass_alert_events ON alert_events
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT ON alert_events TO kaori_app;
-- No UPDATE / DELETE — alert_events is append-only by design (K-2 spirit).

COMMIT;
