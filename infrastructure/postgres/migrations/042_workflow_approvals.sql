-- 042_workflow_approvals.sql — REL-011 approval gate persistence (bot callback path).
--
-- Phase 1.5 P15-S9 D5 — when a Telegram callback_query arrives at the
-- /webhook/telegram endpoint, the receiver writes a row here. The
-- workflow worker (ai-orchestrator/workflow_runtime) polls this table
-- to discover decisions + resume the matching workflow.
--
-- The split (notification-service writes, ai-orchestrator reads) keeps
-- the webhook fast: we record + ack inside Telegram's 10s SLA and let
-- a separate cron pick up the work without coupling the two services.
--
-- Idempotency (REL-011 + Phần 6.2 — approval_gate is write_idempotent):
-- the unique index on (provider, callback_query_id) means a duplicate
-- delivery (Telegram retries unanswered webhooks for ~24h) lands on the
-- same row instead of creating a second decision. ON CONFLICT DO
-- NOTHING in the receiver gives us idempotent inserts without a SELECT
-- round-trip.
--
-- Naming note (2026-05-22 CI fix): originally named `workflow_approvals`,
-- but mig 089 introduces a different table with the same name for the
-- approval_gate executor's pause/resume state (status pending/approved/
-- rejected/expired/cancelled). To resolve the name clash without
-- destructive renames, this table is now `bot_approval_callbacks`
-- (provider-agnostic — Telegram today, Zalo/Slack future). The newer
-- `workflow_approvals` is the canonical approval-gate state table.

CREATE TABLE IF NOT EXISTS bot_approval_callbacks (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity — what got decided
    workflow_id          TEXT NOT NULL,
    run_id               TEXT NOT NULL,
    node_id              TEXT NOT NULL,
    decision             TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),

    -- Provider trail — used by the dedup index + audit
    provider             TEXT NOT NULL DEFAULT 'telegram',
    callback_query_id    TEXT NOT NULL,
    chat_id              TEXT,
    user_id_external     TEXT,
    user_display_name    TEXT,

    -- Tenancy (K-1) — every row carries enterprise_id so RLS can scope
    enterprise_id        UUID NOT NULL,

    -- Lifecycle
    decided_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    consumed_at          TIMESTAMPTZ,           -- set when worker picks it up
    consumer_workflow_run UUID,                 -- temporal workflow_run_id

    raw_callback_data    TEXT NOT NULL,
    raw_payload          JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Idempotency dedup — same provider + callback_query_id is the same
-- decision Telegram is retrying. INSERT ON CONFLICT DO NOTHING.
CREATE UNIQUE INDEX IF NOT EXISTS bot_approval_callbacks_provider_callback_uniq
    ON bot_approval_callbacks (provider, callback_query_id);

-- Worker poll path — find pending decisions per tenant.
CREATE INDEX IF NOT EXISTS bot_approval_callbacks_pending_idx
    ON bot_approval_callbacks (enterprise_id, decided_at)
    WHERE consumed_at IS NULL;

-- RLS — every read MUST scope by enterprise_id (K-1 / ADR-0013).
ALTER TABLE bot_approval_callbacks ENABLE ROW LEVEL SECURITY;

-- Policy uses the GUC `app.current_enterprise_id` populated by
-- shared.db.acquire_for_tenant() (matches every other RLS-aligned
-- table). Direct SELECT without the GUC returns zero rows.
DROP POLICY IF EXISTS bot_approval_callbacks_tenant_isolation ON bot_approval_callbacks;
CREATE POLICY bot_approval_callbacks_tenant_isolation ON bot_approval_callbacks
    USING (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

COMMENT ON TABLE bot_approval_callbacks IS
    'P15-S9 D5 — REL-011 approval gate decisions inbound from chat bots (Telegram today). Bot webhook writes; ai-orchestrator workflow worker reads + resumes.';
COMMENT ON COLUMN bot_approval_callbacks.callback_query_id IS
    'Provider-supplied id for dedup. Telegram retries unanswered webhooks for ~24h; UNIQUE index makes the retry a no-op.';
COMMENT ON COLUMN bot_approval_callbacks.consumed_at IS
    'Set by the worker after the matching workflow has been resumed. NULL = pending pickup.';
