-- =====================================================================
-- 088_workflow_runs.sql
--
-- Workflow execution state — closes the "templates are seed-only" gap
-- raised in workflow-gap audit 2026-05-19.
--
-- Two tables:
--   workflow_runs       — one row per workflow execution request.
--   workflow_run_nodes  — one row per node execution within a run.
--
-- State machine on `workflow_runs.status`:
--   pending            → created, not yet picked up by runner
--   running            → at least one node executing
--   awaiting_approval  → paused at approval_gate node (resume via API)
--   completed          → terminal: all reachable nodes done
--   failed             → terminal: a node raised + retries exhausted
--   cancelled          → terminal: user cancelled before completion
--
-- K-1 / K-12 RLS: enterprise_id + tenant_id always carried; SELECT
--   policies on both tables filter by current_setting('app.enterprise_id').
--
-- K-13 idempotency: workflow_run.idempotency_key UNIQUE per tenant —
--   client POST /workflows/{id}/run with Idempotency-Key returns the
--   same run_id on retry.
--
-- K-17 audit: workflow_run_nodes.side_effect_class mirrors the node
--   catalog's class so post-mortem can grep saga compensations.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    workspace_id        UUID,
    status              VARCHAR(32)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','running','awaiting_approval',
                                            'completed','failed','cancelled')),
    triggered_by_user_id UUID,
    trigger_source      VARCHAR(32)     NOT NULL DEFAULT 'manual'
                          CHECK (trigger_source IN ('manual','schedule','webhook','event','api')),
    input_data          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    output_data         JSONB,
    error_summary       TEXT,
    idempotency_key     VARCHAR(128),
    started_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    UNIQUE (enterprise_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow
    ON workflow_runs(workflow_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
    ON workflow_runs(enterprise_id, status, started_at DESC)
    WHERE status IN ('pending','running','awaiting_approval');


CREATE TABLE IF NOT EXISTS workflow_run_nodes (
    run_node_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID            NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    node_id             UUID            NOT NULL REFERENCES workflow_nodes(node_id) ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    node_type_key       VARCHAR(64)     NOT NULL,
    side_effect_class   VARCHAR(32)     NOT NULL,
    sequence_order      INT             NOT NULL,
    status              VARCHAR(32)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','running','awaiting_approval',
                                            'completed','failed','skipped')),
    input_data          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    output_data         JSONB,
    error_message       TEXT,
    retry_count         INT             NOT NULL DEFAULT 0,
    idempotency_key     VARCHAR(128),
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    UNIQUE (run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_run_nodes_run
    ON workflow_run_nodes(run_id, sequence_order);

CREATE INDEX IF NOT EXISTS idx_workflow_run_nodes_awaiting
    ON workflow_run_nodes(enterprise_id, status)
    WHERE status = 'awaiting_approval';

-- RLS (mirror existing workflows table pattern)
ALTER TABLE workflow_runs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_run_nodes  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workflow_runs_isolation ON workflow_runs;
CREATE POLICY workflow_runs_isolation ON workflow_runs
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

DROP POLICY IF EXISTS workflow_run_nodes_isolation ON workflow_run_nodes;
CREATE POLICY workflow_run_nodes_isolation ON workflow_run_nodes
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
