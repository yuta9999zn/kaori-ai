-- Migration 026: notification_outbox — durable transactional outbox for emails.
--
-- Why this exists
-- ===============
-- Today auth-service calls notification-service over HTTP for password-reset
-- and invite emails (see services/auth-service/.../service/NotificationClient.java).
-- The call is best-effort log+swallow — a transient SMTP outage at the
-- notification-service end means the email is permanently lost. The user
-- sees "we sent you a reset link" + 200 OK and waits forever. Pilot CS
-- has flagged this as a real lock-out source.
--
-- This migration introduces a notification_outbox table that auth-service
-- writes into in the SAME DB transaction as the trigger event (creating
-- the password reset row, creating the invited user, etc.). After commit,
-- the notification is durable. notification-service runs a poller that
-- picks up pending rows, attempts SMTP delivery, and retries with
-- exponential backoff. If max_attempts is exhausted the row goes to
-- ``status = 'dead'`` and an alert can fire.
--
-- Why a separate table from event_outbox
-- ======================================
-- event_outbox (migration 009) carries Kafka events with at-least-once
-- delivery and a relay that simply "send to Kafka, mark published".
-- notification_outbox carries SMTP sends with multi-attempt retry,
-- per-attempt error tracking, and a dead-letter terminal state. Coupling
-- them would force one schema to grow retry semantics it doesn't need
-- (event_outbox) and force the other to live with semantics it can't use
-- (notification dedupe by Kafka offset). Different lifecycles → different
-- tables. They share the outbox-pattern principle (write durably in the
-- producer txn) but nothing else.
--
-- RLS
-- ===
-- notification_outbox carries multi-tenant rows but is read by a
-- cross-tenant poller (notification-service polls every tenant's pending
-- rows). Same trade-off as event_outbox in migration 024 — we drop RLS
-- here rather than make the poller juggle the ``app.is_admin`` GUC for
-- every read. The ``enterprise_id`` column stays for forensics + per-
-- tenant queries. Application-level filters (auth-service writes are
-- always tenant-scoped) prevent cross-tenant write leakage.
--
-- Reversibility
-- =============
-- Full rollback: ``DROP TABLE notification_outbox;``
-- Service rollback: revert auth-service NotificationClient back to the
-- direct-HTTP path; notification-service poller will see the empty
-- table and idle harmlessly.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. notification_outbox — produce side
-- ============================================================
CREATE TABLE IF NOT EXISTS notification_outbox (
    outbox_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- enterprise_id is nullable so future system-wide notifications
    -- (e.g., a Kaori-staff broadcast to all platform admins) can reuse
    -- the same outbox without faking a tenant. Today every row is
    -- tenant-scoped — pilot defence by NOT NULL would lock that down,
    -- but the cost of tightening later is a single ALTER COLUMN if
    -- the system-broadcast use case never materialises.
    enterprise_id    UUID         REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    template         VARCHAR(50)  NOT NULL,                    -- matches notification-service TemplateType enum
    recipient_email  VARCHAR(320) NOT NULL,                    -- 320 = max RFC 5321 email length
    context          JSONB        NOT NULL DEFAULT '{}'::jsonb, -- template render variables

    -- State machine: pending → sent (terminal) | dead (terminal, max attempts).
    -- 'failed' is NOT a state — every failed attempt stays in 'pending'
    -- with attempts++ until either success or attempts = max. Keeping a
    -- single non-terminal state keeps the poller's WHERE clause minimal
    -- (status='pending' AND attempts<max).
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'sent', 'dead')),

    attempts         INTEGER      NOT NULL DEFAULT 0,
    max_attempts     INTEGER      NOT NULL DEFAULT 5,           -- per-row override; default 5
    last_error       TEXT,                                       -- last SMTP/exception message; NULL on success
    last_attempt_at  TIMESTAMPTZ,                                -- NULL until first attempt

    sent_at          TIMESTAMPTZ,                                -- non-NULL when status='sent'
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Phase 2 #2/#5 — W3C trace context captured at enqueue time so the
    -- poller can continue the trace started at the HTTP edge. Same
    -- pattern as event_outbox.trace_context (migration 021).
    trace_context    JSONB,

    -- Cheap forensics: caller can stash an opaque correlation id (e.g.,
    -- the password_reset row id, the user_invitation id) so support can
    -- trace "this user said they didn't get an email" → outbox row →
    -- attempts + last_error in one query.
    source_ref       VARCHAR(200)
);

-- Pending rows are the only set the poller cares about. Partial index
-- stays tiny in steady state because rows transition out of 'pending'
-- within seconds (success) or minutes (dead). Order by created_at so
-- FIFO across tenants is the natural read order.
CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending
    ON notification_outbox(created_at)
    WHERE status = 'pending';

-- Per-tenant query (support: "show me this customer's recent emails").
CREATE INDEX IF NOT EXISTS idx_notification_outbox_enterprise
    ON notification_outbox(enterprise_id, created_at DESC);

-- Dead-letter triage view: ops grep dead rows by template to spot
-- pattern outages ("every reset-password died at 3am → SMTP smarthost
-- maintenance window"). Partial keeps it tiny.
CREATE INDEX IF NOT EXISTS idx_notification_outbox_dead
    ON notification_outbox(template, created_at DESC)
    WHERE status = 'dead';

-- ============================================================
-- 2. Grants
-- ============================================================
-- kaori_app needs SELECT (poller read), INSERT (auth-service writer),
-- UPDATE (poller marks sent/dead + increments attempts). No DELETE —
-- rows are kept indefinitely for forensics; cleanup is a separate
-- retention policy (not in this migration; expected to land alongside
-- F-037 quota-alert email work when notification volume picks up).
GRANT SELECT, INSERT, UPDATE ON notification_outbox TO kaori_app;

-- No RLS on notification_outbox — see header comment. The cross-tenant
-- poller is the read consumer, and writers always supply
-- enterprise_id explicitly from authenticated session context.

COMMIT;
