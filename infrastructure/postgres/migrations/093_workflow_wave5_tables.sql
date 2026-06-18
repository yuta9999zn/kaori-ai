-- =====================================================================
-- 093_workflow_wave5_tables.sql
--
-- Wave-5 closeout: add 3 new sink/source tables + extend the chat outbox
-- channel enum to cover SMS (reuses the same outbox infrastructure).
--
--   workflow_calendar_intake — read_calendar source (per-tenant event queue)
--   workflow_chat_intake     — read_chat source (inbound messages, opposite
--                               of workflow_chat_outbox)
--   workflow_export_files    — export_file sink (file render tracking)
--   ALTER workflow_chat_outbox.channel — add 'sms' value
--
-- All tables RLS-isolated per tenant.
-- =====================================================================

BEGIN;

-- ─── workflow_calendar_intake ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workflow_calendar_intake (
    event_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id         UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    queue_key             VARCHAR(64)     NOT NULL,
    calendar_source       VARCHAR(64),
    external_event_id     VARCHAR(200),
    organizer             VARCHAR(320),
    attendees             TEXT[]          NOT NULL DEFAULT ARRAY[]::TEXT[],
    summary               VARCHAR(500)    NOT NULL DEFAULT '',
    description           TEXT,
    location              VARCHAR(500),
    start_at              TIMESTAMPTZ     NOT NULL,
    end_at                TIMESTAMPTZ,
    payload               JSONB           NOT NULL DEFAULT '{}'::jsonb,
    received_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status                VARCHAR(32)     NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','consumed','expired','rejected')),
    consumed_at           TIMESTAMPTZ,
    consumed_by_run_id    UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    UNIQUE (enterprise_id, calendar_source, external_event_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_calendar_intake_pending
    ON workflow_calendar_intake(enterprise_id, queue_key, start_at)
    WHERE status = 'pending';


-- ─── workflow_chat_intake ────────────────────────────────────────────
-- Inbound chat counterpart to workflow_chat_outbox. Slack/Telegram/Zalo
-- bots POST here; read_chat executor claims.
CREATE TABLE IF NOT EXISTS workflow_chat_intake (
    message_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id         UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    queue_key             VARCHAR(64)     NOT NULL,
    channel               VARCHAR(32)     NOT NULL
                            CHECK (channel IN ('slack','telegram','zalo','teams','generic')),
    external_message_id   VARCHAR(200),
    sender                VARCHAR(320)    NOT NULL,
    sender_display_name   VARCHAR(200),
    target                VARCHAR(320),
    message               TEXT            NOT NULL,
    attachments           JSONB           NOT NULL DEFAULT '[]'::jsonb,
    received_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status                VARCHAR(32)     NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','consumed','expired','rejected')),
    consumed_at           TIMESTAMPTZ,
    consumed_by_run_id    UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    UNIQUE (enterprise_id, channel, external_message_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_chat_intake_pending
    ON workflow_chat_intake(enterprise_id, queue_key, received_at)
    WHERE status = 'pending';


-- ─── workflow_export_files ───────────────────────────────────────────
-- export_file sink. Caller specifies format + filename + source rows;
-- v0 records the request; future renderer + MinIO writer poll + fill
-- minio_object_path. Same pattern as generate_report sink.
CREATE TABLE IF NOT EXISTS workflow_export_files (
    export_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id         UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id                UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    node_id               UUID            REFERENCES workflow_nodes(node_id) ON DELETE SET NULL,
    export_key            VARCHAR(200)    NOT NULL,
    file_format           VARCHAR(16)     NOT NULL
                            CHECK (file_format IN ('csv','xlsx','json','pdf','txt','parquet')),
    filename              VARCHAR(300)    NOT NULL,
    metadata              JSONB           NOT NULL DEFAULT '{}'::jsonb,
    row_count             INT,
    byte_size             BIGINT,
    minio_object_path     VARCHAR(500),
    status                VARCHAR(32)     NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued','rendering','ready','failed','expired')),
    error_message         TEXT,
    created_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rendered_at           TIMESTAMPTZ,
    UNIQUE (enterprise_id, export_key)
);

CREATE INDEX IF NOT EXISTS idx_workflow_export_files_queue
    ON workflow_export_files(status, created_at)
    WHERE status IN ('queued','rendering');


-- ─── ALTER workflow_chat_outbox: add 'sms' channel ───────────────────
ALTER TABLE workflow_chat_outbox DROP CONSTRAINT IF EXISTS workflow_chat_outbox_channel_check;
ALTER TABLE workflow_chat_outbox
    ADD CONSTRAINT workflow_chat_outbox_channel_check
    CHECK (channel IN ('slack','telegram','zalo','teams','generic','sms'));


-- ─── RLS policies ────────────────────────────────────────────────────

ALTER TABLE workflow_calendar_intake  ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_chat_intake      ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_export_files     ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workflow_calendar_intake_isolation ON workflow_calendar_intake;
DROP POLICY IF EXISTS workflow_chat_intake_isolation     ON workflow_chat_intake;
DROP POLICY IF EXISTS workflow_export_files_isolation    ON workflow_export_files;

CREATE POLICY workflow_calendar_intake_isolation ON workflow_calendar_intake
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_chat_intake_isolation ON workflow_chat_intake
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_export_files_isolation ON workflow_export_files
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
