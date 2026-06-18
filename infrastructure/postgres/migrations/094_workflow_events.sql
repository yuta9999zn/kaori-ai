-- =====================================================================
-- 094_workflow_events.sql
--
-- P0.1 of operational-correctness hardening (per anh's review 2026-05-19):
-- append-only event log for workflow runs. Replaces silent UPDATE-in-place
-- on workflow_run_nodes.status with explicit events.
--
-- Why
-- ---
-- Today workflow_run_nodes.status mutates via UPDATE — no history. If a
-- run crashes mid-execution we cannot:
--   - tell which event caused the failure
--   - replay deterministically
--   - audit a node's full state trajectory
--
-- workflow_events is the SOURCE OF TRUTH for run state. workflow_runs +
-- workflow_run_nodes become CACHED PROJECTIONS rebuildable from events.
-- mig 088 tables stay (existing queries keep working) — runner code is
-- updated to APPEND-then-PROJECT instead of UPDATE-in-place.
--
-- Event types (extensible via CHECK enum):
--   workflow_created        — POST /workflows/{id}/run
--   workflow_started        — runner picks up first node
--   node_started            — executor invocation begins
--   node_completed          — executor returned success
--   node_failed             — executor raised
--   node_skipped            — preloaded completed in resume
--   node_paused             — approval_gate emitted awaiting_approval
--   approval_resolved       — POST /workflow-runs/{id}/approve
--   workflow_paused         — at least one node awaiting_approval
--   workflow_resumed        — runner picked back up after pause
--   workflow_completed      — terminal success
--   workflow_failed         — terminal fail
--   workflow_cancelled      — user cancellation
--   compensation_started    — saga step fired (future P1.4)
--   compensation_completed  — compensation done (future P1.4)
--
-- Ordering: (run_id, sequence_no) is the canonical ordering. sequence_no
-- is monotonic per run via a sub-transaction sequence; ts may have
-- ties across events emitted in the same millisecond.
--
-- Immutability: no UPDATE, no DELETE — only INSERT. Trigger enforces.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_events (
    event_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    run_id          UUID            NOT NULL,
    node_id         UUID,
    sequence_no     BIGINT          NOT NULL,
    event_type      VARCHAR(40)     NOT NULL
                      CHECK (event_type IN (
                        'workflow_created','workflow_started',
                        'node_started','node_completed','node_failed','node_skipped',
                        'node_paused','approval_resolved',
                        'workflow_paused','workflow_resumed',
                        'workflow_completed','workflow_failed','workflow_cancelled',
                        'compensation_started','compensation_completed'
                      )),
    payload         JSONB           NOT NULL DEFAULT '{}'::jsonb,
    actor_user_id   UUID,
    occurred_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, sequence_no)
);

-- Read patterns:
--   1. Project run state: SELECT ... WHERE run_id=? ORDER BY sequence_no
--   2. Replay test fixture: SELECT WHERE run_id=? ORDER BY sequence_no
--   3. Tenant audit: SELECT WHERE enterprise_id=? AND event_type IN (...)
CREATE INDEX IF NOT EXISTS idx_workflow_events_run
    ON workflow_events(run_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_workflow_events_tenant_type
    ON workflow_events(enterprise_id, event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_events_node
    ON workflow_events(node_id, occurred_at)
    WHERE node_id IS NOT NULL;

-- ─── Immutability triggers ───────────────────────────────────────────
-- Hard-block UPDATE/DELETE so application bugs cannot retro-edit history.
CREATE OR REPLACE FUNCTION workflow_events_block_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'workflow_events is append-only (TG_OP=%); event_id=%',
        TG_OP, COALESCE(OLD.event_id, NEW.event_id);
END;
$$;

DROP TRIGGER IF EXISTS workflow_events_no_update ON workflow_events;
CREATE TRIGGER workflow_events_no_update
    BEFORE UPDATE ON workflow_events
    FOR EACH ROW EXECUTE FUNCTION workflow_events_block_mutation();

DROP TRIGGER IF EXISTS workflow_events_no_delete ON workflow_events;
CREATE TRIGGER workflow_events_no_delete
    BEFORE DELETE ON workflow_events
    FOR EACH ROW EXECUTE FUNCTION workflow_events_block_mutation();

-- ─── Sequence allocator ─────────────────────────────────────────────
-- Per-run monotonic sequence_no via SELECT FOR UPDATE on a sidecar
-- counter table. Cheap because we only contend per single run, and a
-- run executes serially in the in-process runner (P0.1 — P1.2 will
-- split workers; sequence stays per-run-correct under concurrency
-- thanks to FOR UPDATE).
CREATE TABLE IF NOT EXISTS workflow_event_sequencer (
    run_id          UUID    PRIMARY KEY,
    next_sequence_no BIGINT NOT NULL DEFAULT 1,
    enterprise_id   UUID    NOT NULL
);

CREATE OR REPLACE FUNCTION workflow_events_next_seq(p_run_id UUID, p_enterprise UUID)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    v_seq BIGINT;
BEGIN
    INSERT INTO workflow_event_sequencer (run_id, next_sequence_no, enterprise_id)
        VALUES (p_run_id, 1, p_enterprise)
        ON CONFLICT (run_id) DO NOTHING;
    UPDATE workflow_event_sequencer
        SET next_sequence_no = next_sequence_no + 1
        WHERE run_id = p_run_id
        RETURNING next_sequence_no - 1 INTO v_seq;
    RETURN v_seq;
END;
$$;

-- ─── RLS ────────────────────────────────────────────────────────────
ALTER TABLE workflow_events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_event_sequencer  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workflow_events_isolation     ON workflow_events;
DROP POLICY IF EXISTS workflow_event_seq_isolation  ON workflow_event_sequencer;
CREATE POLICY workflow_events_isolation ON workflow_events
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY workflow_event_seq_isolation ON workflow_event_sequencer
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
