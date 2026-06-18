-- =====================================================================
-- 092_workflow_chat_and_webhook.sql
--
-- 2 new sink/source tables for wave-4 workflow executors:
--   workflow_chat_outbox      send_chat_message node sink (bot adapter
--                              reads pending rows + dispatches to
--                              Slack/Telegram/Zalo per channel)
--   workflow_webhook_intake   read_webhook node source (webhook HTTP
--                              endpoint stashes payloads keyed by queue)
--
-- Both follow the K-12 RLS pattern from prior migs.
-- =====================================================================

BEGIN;

-- ─── workflow_chat_outbox ────────────────────────────────────────────
-- send_chat_message node sink. The bot adapter (Slack/Telegram/Zalo)
-- consumes pending rows + flips status to 'sent' or 'dead'.

CREATE TABLE IF NOT EXISTS workflow_chat_outbox (
    outbox_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id              UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    node_id             UUID            REFERENCES workflow_nodes(node_id) ON DELETE SET NULL,
    channel             VARCHAR(32)     NOT NULL
                          CHECK (channel IN ('slack','telegram','zalo','teams','generic')),
    target              VARCHAR(320)    NOT NULL,
    message             TEXT            NOT NULL,
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    source_ref          VARCHAR(128),
    status              VARCHAR(20)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','sent','dead')),
    attempts            INT             NOT NULL DEFAULT 0,
    last_error          TEXT,
    last_attempt_at     TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, source_ref)
);

CREATE INDEX IF NOT EXISTS idx_workflow_chat_outbox_pending
    ON workflow_chat_outbox(channel, created_at)
    WHERE status = 'pending';

-- ─── workflow_webhook_intake ─────────────────────────────────────────
-- read_webhook node source. Webhook receiver POSTs into here keyed by
-- queue_key (e.g. 'stripe_events', 'lead_form_zapier'). Same pattern as
-- workflow_email_intake (mig 091) — pending rows claimed by read_webhook
-- via SELECT FOR UPDATE SKIP LOCKED.

CREATE TABLE IF NOT EXISTS workflow_webhook_intake (
    webhook_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    queue_key           VARCHAR(64)     NOT NULL,
    source              VARCHAR(64),
    external_event_id   VARCHAR(200),
    headers             JSONB           NOT NULL DEFAULT '{}'::jsonb,
    payload             JSONB           NOT NULL DEFAULT '{}'::jsonb,
    received_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status              VARCHAR(32)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','consumed','expired','rejected')),
    consumed_at         TIMESTAMPTZ,
    consumed_by_run_id  UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    UNIQUE (enterprise_id, queue_key, external_event_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_webhook_intake_pending
    ON workflow_webhook_intake(enterprise_id, queue_key, received_at)
    WHERE status = 'pending';

-- RLS
ALTER TABLE workflow_chat_outbox     ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_webhook_intake  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workflow_chat_outbox_isolation    ON workflow_chat_outbox;
DROP POLICY IF EXISTS workflow_webhook_intake_isolation ON workflow_webhook_intake;

CREATE POLICY workflow_chat_outbox_isolation ON workflow_chat_outbox
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_webhook_intake_isolation ON workflow_webhook_intake
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
