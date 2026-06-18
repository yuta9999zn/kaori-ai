-- Migration 029: F-038 Reports — manual distribution to additional recipients.
--
-- Why this exists
-- ===============
-- F-038 backend (PR #113) shipped the auto-generate path with a single
-- ``report-ready`` email enqueued for the report's ``owner_email`` after
-- status='ready'. Pilot UAT request (DEMO_RUNBOOK §7): the owner often
-- needs to forward the same report to other stakeholders without
-- regenerating it. F-037's notification_outbox + per-recipient enqueue
-- pattern (PR #116) makes this a natural one-table extension.
--
-- This migration adds report_distributions: one row per (report_id,
-- recipient_email, channel) attempt. The dispatcher in
-- services/ai-orchestrator/reports/service.py inserts a row + enqueues a
-- notification_outbox row in the same transaction; the outbox poller
-- then handles the actual SMTP send with retries.
--
-- Distribution status mirrors notification_outbox states by design:
--   pending  — outbox row enqueued, poller hasn't picked up yet
--   sent     — poller marked outbox sent='sent'; reflected here for FE
--   failed   — outbox went to 'dead' OR enqueue itself raised
-- The reflection is best-effort: the FE list query joins to
-- notification_outbox.status anyway, so this column is mostly a forensic
-- snapshot at distribute-time.
--
-- Why not a single ``recipients`` array column on reports
-- ========================================================
-- A JSONB list would lose per-recipient delivery tracking. Forensics is
-- the whole point of the F-037/F-038 outbox pattern — "user said they
-- didn't get the email" → joinable to notification_outbox via outbox_id.
-- One row per recipient also lets a future re-send only target the
-- failed subset.
--
-- Why no UNIQUE on (report_id, recipient_email, channel)
-- =======================================================
-- Re-distribution after a typo fix is a legitimate operation. The
-- service layer dedups within a single distribute() call but allows
-- two separate calls hours apart. Audit lives at the row level.
--
-- RLS
-- ===
-- Standard tenant_isolation + admin_bypass pattern (matches migration
-- 027 reports). ON DELETE CASCADE from reports so soft-deleting a
-- report (Phase 2 future) cleans the distribution audit trail too.
--
-- Reversibility
-- =============
--   DROP TABLE report_distributions;
-- Service rollback: distribute() is a separate endpoint; removing it
-- from the router doesn't affect the existing auto-generate flow.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS report_distributions (
    distribution_id    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id      UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    report_id          UUID         NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,

    recipient_email    VARCHAR(320) NOT NULL,                  -- RFC 5321 max
    channel            VARCHAR(40)  NOT NULL DEFAULT 'email'
                                    CHECK (channel IN ('email')),

    -- Pointer to the outbox row this distribution enqueued. NULL when
    -- enqueue itself failed (status will be 'failed' in that case).
    outbox_id          UUID,

    -- Snapshot at distribute-time. The FE can join notification_outbox
    -- via outbox_id for the live state; this column is the at-rest
    -- forensic "we tried" record.
    status             VARCHAR(20)  NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'sent', 'failed')),

    -- Optional sender-supplied message that gets rendered in the email
    -- above the standard "your report is ready" copy. Trimmed in the
    -- service to 500 chars; column allows up to 2000 to leave headroom
    -- for future longer attachments (cover letter, etc.).
    custom_message     VARCHAR(2000),

    -- Who triggered the distribution. NULL when triggered by an
    -- automated flow (scheduler — Phase 2 follow-up).
    triggered_by_user  UUID,

    -- last_error mirrors notification_outbox semantics for the rare
    -- case where the dispatcher recorded a failed enqueue (no outbox_id).
    last_error         TEXT,

    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- FE list endpoint hot path: "show me all sends for this report".
CREATE INDEX IF NOT EXISTS idx_report_distributions_report
    ON report_distributions(report_id, created_at DESC);

-- Tenant rollup ("show me everything sent in the last week").
CREATE INDEX IF NOT EXISTS idx_report_distributions_tenant
    ON report_distributions(enterprise_id, created_at DESC);

ALTER TABLE report_distributions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'report_distributions' AND policyname = 'tenant_report_distributions'
    ) THEN
        CREATE POLICY tenant_report_distributions ON report_distributions
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'report_distributions' AND policyname = 'admin_bypass_report_distributions'
    ) THEN
        CREATE POLICY admin_bypass_report_distributions ON report_distributions
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON report_distributions TO kaori_app;

COMMIT;
