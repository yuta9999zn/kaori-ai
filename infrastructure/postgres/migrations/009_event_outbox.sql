-- Migration 009: Transactional outbox + consumer-side dedupe (G5).
--
-- Why this exists:
--   Today producers dual-write — INSERT into a business table AND
--   call kafka_producer.send_event() in two separate operations. If
--   the service crashes between them, the DB has the row but Kafka
--   never sees the event. The current send_event also logs-and-
--   swallows on Kafka error, so failures are silent.
--
-- The outbox flips this:
--   1. Producer writes a row into event_outbox in the SAME transaction
--      as the business write. Atomic — DB commit ⇒ event will eventually
--      reach Kafka; DB rollback ⇒ no event ever gets sent.
--   2. A separate publisher loop polls event_outbox WHERE published_at
--      IS NULL, sends to Kafka, marks published_at — all under
--      FOR UPDATE SKIP LOCKED so multiple service instances can share
--      the work without stepping on each other.
--
-- Delivery guarantee is at-least-once (relay can crash between Kafka
-- send and the published_at UPDATE → next poll re-sends the same row).
-- Consumers MUST dedupe by outbox_id; processed_events below provides
-- the primitive.
--
-- Reversibility:
--   DROP TABLE event_outbox;
--   DROP TABLE processed_events;
-- (Reverting also requires migrating any service code that uses these
-- back to the legacy direct send_event flow.)

-- ============================================================
-- 1. EVENT OUTBOX — produce side
-- ============================================================
CREATE TABLE IF NOT EXISTS event_outbox (
    outbox_id      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id  UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    topic          VARCHAR(200) NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        JSONB        NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    published_at   TIMESTAMPTZ,
    attempts       INTEGER      NOT NULL DEFAULT 0,
    last_error     TEXT
);

-- Pending-only partial index. Tiny in steady state because rows
-- transition to published_at IS NOT NULL within seconds. Matches the
-- relay's WHERE clause exactly (published_at IS NULL ORDER BY created_at).
CREATE INDEX IF NOT EXISTS idx_event_outbox_pending
    ON event_outbox(created_at)
    WHERE published_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_event_outbox_enterprise
    ON event_outbox(enterprise_id, created_at DESC);

ALTER TABLE event_outbox ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'event_outbox' AND policyname = 'tenant_event_outbox'
    ) THEN
        CREATE POLICY tenant_event_outbox ON event_outbox
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON event_outbox TO kaori_app;

-- The relay reads ALL tenants' rows. Today it relies on kaori_app
-- having BYPASSRLS=true (set by 008_kaori_app_grants.sql). When
-- BYPASSRLS is later flipped off (G4b step 2), the relay will need
-- a dedicated role with BYPASSRLS or set row_security=off per session.
-- Captured here so the constraint is not lost.

-- ============================================================
-- 2. PROCESSED EVENTS — consume-side dedupe
-- ============================================================
CREATE TABLE IF NOT EXISTS processed_events (
    event_id        UUID         NOT NULL,
    consumer_group  VARCHAR(100) NOT NULL,
    processed_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, consumer_group)
);

CREATE INDEX IF NOT EXISTS idx_processed_events_at
    ON processed_events(processed_at DESC);

GRANT SELECT, INSERT ON processed_events TO kaori_app;

-- No RLS on processed_events — it's a system bookkeeping table
-- shared across tenants (consumer groups are global). The PK enforces
-- "at most one row per (event_id, consumer_group)" which is the
-- dedupe invariant. INSERT inside the consumer's txn means: if the
-- INSERT raises UNIQUE violation, the consumer can be sure another
-- worker (or a prior delivery) already handled this event and SKIP
-- without doing the business work twice.
