-- =====================================================================
-- 091_workflow_output_tables.sql
--
-- 5 output / sink tables for wave-3 workflow executors:
--   workflow_insights         publish_insight node sink
--   workflow_alerts           publish_alert node sink
--   workflow_tasks            create_task node sink (assigned to role/user)
--   workflow_dashboard_tiles  display_dashboard node sink (UPSERT by tile_key)
--   workflow_email_intake     read_email node source (webhook ingest queue)
--
-- All carry enterprise_id + RLS isolation policy mirroring mig 088/089/090.
-- write_idempotent tables (dashboard tiles + tasks) get a UNIQUE natural key
-- so retries collapse into a single row.
-- =====================================================================

BEGIN;

-- ─── workflow_insights ───────────────────────────────────────────────
-- publish_insight node sink. Each row = one piece of generated insight
-- visible in P2-19 Insights List / P2-20 Insight Detail screens.

CREATE TABLE IF NOT EXISTS workflow_insights (
    insight_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id            UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    node_id           UUID            REFERENCES workflow_nodes(node_id) ON DELETE SET NULL,
    title             VARCHAR(300)    NOT NULL,
    body              TEXT            NOT NULL,
    severity          VARCHAR(16)     NOT NULL DEFAULT 'info'
                        CHECK (severity IN ('info','warning','critical')),
    confidence        NUMERIC(5,4),
    source_data       JSONB           NOT NULL DEFAULT '{}'::jsonb,
    tags              TEXT[]          NOT NULL DEFAULT ARRAY[]::TEXT[],
    seen_at           TIMESTAMPTZ,
    seen_by_user_id   UUID,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_insights_recent
    ON workflow_insights(enterprise_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_insights_unseen
    ON workflow_insights(enterprise_id, severity, created_at DESC)
    WHERE seen_at IS NULL;


-- ─── workflow_alerts ─────────────────────────────────────────────────
-- publish_alert node sink. Different from alert_rules (mig 028) which is
-- billing-quota only. These are workflow-emitted alerts visible per role.

CREATE TABLE IF NOT EXISTS workflow_alerts (
    alert_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id              UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    node_id             UUID            REFERENCES workflow_nodes(node_id) ON DELETE SET NULL,
    code                VARCHAR(64)     NOT NULL,
    message             TEXT            NOT NULL,
    severity            VARCHAR(16)     NOT NULL DEFAULT 'warning'
                          CHECK (severity IN ('info','warning','critical')),
    target_role         VARCHAR(32),
    payload             JSONB           NOT NULL DEFAULT '{}'::jsonb,
    acknowledged_at     TIMESTAMPTZ,
    acknowledged_by_user_id UUID,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_alerts_open
    ON workflow_alerts(enterprise_id, target_role, created_at DESC)
    WHERE acknowledged_at IS NULL;


-- ─── workflow_tasks ──────────────────────────────────────────────────
-- create_task node sink. Natural-key UPSERT by task_key for write_idempotent
-- semantics — retries with the same task_key UPDATE in place.

CREATE TABLE IF NOT EXISTS workflow_tasks (
    task_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id              UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    node_id             UUID            REFERENCES workflow_nodes(node_id) ON DELETE SET NULL,
    task_key            VARCHAR(200)    NOT NULL,
    title               VARCHAR(300)    NOT NULL,
    description         TEXT,
    assignee_role       VARCHAR(32),
    assignee_user_id    UUID,
    due_at              TIMESTAMPTZ,
    priority            VARCHAR(16)     NOT NULL DEFAULT 'normal'
                          CHECK (priority IN ('low','normal','high','urgent')),
    status              VARCHAR(32)     NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','in_progress','done','cancelled','expired')),
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    completed_at        TIMESTAMPTZ,
    completed_by_user_id UUID,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, task_key)
);

CREATE INDEX IF NOT EXISTS idx_workflow_tasks_open_role
    ON workflow_tasks(enterprise_id, assignee_role, due_at)
    WHERE status IN ('open','in_progress');


-- ─── workflow_dashboard_tiles ───────────────────────────────────────
-- display_dashboard node sink. UPSERT by (dashboard_key, tile_key) keeps
-- dashboards stable — same workflow run on same tile updates the value
-- in place rather than spawning history rows.

CREATE TABLE IF NOT EXISTS workflow_dashboard_tiles (
    tile_id             UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    dashboard_key       VARCHAR(64)     NOT NULL,
    tile_key            VARCHAR(64)     NOT NULL,
    last_run_id         UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    last_node_id        UUID            REFERENCES workflow_nodes(node_id) ON DELETE SET NULL,
    payload             JSONB           NOT NULL DEFAULT '{}'::jsonb,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, dashboard_key, tile_key)
);

CREATE INDEX IF NOT EXISTS idx_workflow_dashboard_tiles_recent
    ON workflow_dashboard_tiles(enterprise_id, dashboard_key, updated_at DESC);


-- ─── workflow_email_intake ───────────────────────────────────────────
-- read_email node source. Webhook/IMAP fetcher INSERTs incoming emails
-- per (enterprise, queue_key); the read_email executor SELECTs the next
-- pending row + flips status to 'consumed' (write_idempotent via natural
-- claim).

CREATE TABLE IF NOT EXISTS workflow_email_intake (
    email_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    queue_key           VARCHAR(64)     NOT NULL,
    message_id          VARCHAR(320),
    sender              VARCHAR(320)    NOT NULL,
    recipients          TEXT[]          NOT NULL DEFAULT ARRAY[]::TEXT[],
    subject             VARCHAR(500)    NOT NULL DEFAULT '',
    body_text           TEXT,
    body_html           TEXT,
    attachments         JSONB           NOT NULL DEFAULT '[]'::jsonb,
    received_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status              VARCHAR(32)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','consumed','expired','rejected')),
    consumed_at         TIMESTAMPTZ,
    consumed_by_run_id  UUID            REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    UNIQUE (enterprise_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_email_intake_pending
    ON workflow_email_intake(enterprise_id, queue_key, received_at)
    WHERE status = 'pending';


-- ─── RLS policies ───────────────────────────────────────────────────

ALTER TABLE workflow_insights         ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_alerts           ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_tasks            ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_dashboard_tiles  ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_email_intake     ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workflow_insights_isolation        ON workflow_insights;
DROP POLICY IF EXISTS workflow_alerts_isolation          ON workflow_alerts;
DROP POLICY IF EXISTS workflow_tasks_isolation           ON workflow_tasks;
DROP POLICY IF EXISTS workflow_dashboard_tiles_isolation ON workflow_dashboard_tiles;
DROP POLICY IF EXISTS workflow_email_intake_isolation    ON workflow_email_intake;

CREATE POLICY workflow_insights_isolation ON workflow_insights
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_alerts_isolation ON workflow_alerts
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_tasks_isolation ON workflow_tasks
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_dashboard_tiles_isolation ON workflow_dashboard_tiles
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_email_intake_isolation ON workflow_email_intake
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
