-- Migration 038: F-061 Agent Framework — sessions + transcripts.
--
-- Why this exists
-- ===============
-- Phase 2 Sprint 2.6 — first time the AI does more than answer
-- read-only chat questions. The Planner/Executor/Critic loop runs
-- pre-built workflows (v0: ``insight-to-action``) that may dispatch
-- *action* tools (draft email, mark customer for review) on top of
-- the read-only tools the Sprint 8 chat layer already exposes.
--
-- We persist the full run so:
--   * pilot enterprises can audit "what did Kaori try to do for me"
--   * the Critic can compare current run to prior runs (Phase 2.7)
--   * a side-effect failure (email send queue rejected) is replayable
--
-- Schema
-- ======
-- agent_sessions: ONE row per workflow invocation. Append-then-mutate:
-- INSERT in 'planning' state, UPDATE through executing → critiquing →
-- terminal state (completed | failed | escalated). The plan + verdict
-- columns are JSONB so we don't need a 1-row-per-step strict mirror;
-- agent_transcripts holds the per-step granular trail anyway.
--
-- agent_transcripts: append-only list of every step the orchestrator
-- ran for a session. Each row is one of:
--   * role='planner'   — the planner LLM produced the initial plan
--   * role='executor'  — the executor dispatched one tool
--   * role='critic'    — the critic LLM reviewed the final output
-- Reading session transcripts is the audit story: "for session X, here
-- are the N steps Kaori took, with arguments + results + reasoning".
--
-- Status workflow:
--     planning   → Planner LLM call in flight
--     executing  → Executor dispatching tool steps
--     critiquing → Critic LLM call in flight
--     completed  → Critic verdict='ok', terminal
--     failed     → Hard error (gateway down, no plan), terminal
--     escalated  → Critic asked for human review (or MAX_REPLAN hit),
--                  terminal — pilot dashboard surfaces these
--
-- dry_run defaults TRUE — action tools must see this flag and skip the
-- side-effect (just record what they WOULD have done). Setting it to
-- FALSE requires explicit caller intent + idempotency-key (enforced at
-- the application layer, not DB — see services/ai-orchestrator/agents/
-- router.py and tools/actions.py).
--
-- replan_count caps Critic's re-plan loop. Each time the Critic asks
-- to replan, the orchestrator increments this; at MAX_REPLAN=2 we
-- force-escalate so a hostile insight cannot trap the agent in a
-- planner→executor→critic→replan cycle.
--
-- tokens_used is the running sum across Planner + Executor (LLM calls
-- inside tool execution, if any) + Critic. Budget enforcement is
-- application-side (cap 6000 tokens / session in v0).
--
-- RLS
-- ===
-- Standard tenant_isolation + admin_bypass pattern (matches risk_items
-- migration 033, alerts migration 028, decision_overrides 031).
-- Transcripts inherit isolation through the FK cascade + their own
-- policy on enterprise_id (denormalised so the policy doesn't need to
-- JOIN sessions on every read — RLS evaluators don't optimise JOINs
-- well).
--
-- Reversibility
-- =============
--   DROP TABLE agent_transcripts;
--   DROP TABLE agent_sessions;
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Which built-in workflow was invoked. v0: 'insight-to-action'.
    -- Phase 2 follow-ups: 'data-quality-check', 'retention-campaign-draft'.
    -- Tenant-defined workflows are NOT supported in v0 — string lives
    -- in code (services/ai-orchestrator/agents/workflows.py) so the
    -- catalog can't be poisoned by a write to this column.
    workflow_id          VARCHAR(50)  NOT NULL,

    -- Workflow-specific input. ``insight-to-action`` expects
    -- ``{"insight_id": <uuid>}`` for example. Validated against the
    -- workflow's input_schema at the application layer.
    input                JSONB        NOT NULL DEFAULT '{}',

    -- Lifecycle. CHECK is the source of truth — application code reads
    -- this and renders status badges accordingly.
    status               VARCHAR(20)  NOT NULL DEFAULT 'planning'
                                      CHECK (status IN (
                                          'planning', 'executing', 'critiquing',
                                          'completed', 'failed', 'escalated'
                                      )),

    -- Outputs. Both nullable until the relevant phase completes.
    plan                 JSONB,        -- Planner output: { steps: [...], rationale }
    critic_verdict       JSONB,        -- Critic output: { ok, reason, replan_requested }

    -- Safety knobs (see header comment).
    dry_run              BOOLEAN      NOT NULL DEFAULT TRUE,
    replan_count         SMALLINT     NOT NULL DEFAULT 0
                                      CHECK (replan_count BETWEEN 0 AND 5),
    tokens_used          INT          NOT NULL DEFAULT 0,

    -- Failure surface (only populated on status='failed' / 'escalated').
    error_message        TEXT,

    -- Who initiated. UUID of the enterprise_users row at the moment of
    -- invocation. Nullable so a system trigger (e.g. Phase 2.7 alert
    -- auto-actioning) can also fire workflows.
    actor_user_id        UUID,

    -- Audit.
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at         TIMESTAMPTZ
);

-- Hot path: list endpoint shows latest sessions per tenant by status.
CREATE INDEX IF NOT EXISTS idx_agent_sessions_tenant_status
    ON agent_sessions(enterprise_id, status, created_at DESC);

-- "How many escalations open right now" rollup.
CREATE INDEX IF NOT EXISTS idx_agent_sessions_escalated
    ON agent_sessions(enterprise_id, created_at DESC)
    WHERE status = 'escalated';

-- updated_at touch trigger — same shape as risk_items.
CREATE OR REPLACE FUNCTION agent_sessions_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_sessions_touch ON agent_sessions;
CREATE TRIGGER trg_agent_sessions_touch
    BEFORE UPDATE ON agent_sessions
    FOR EACH ROW EXECUTE FUNCTION agent_sessions_touch_updated_at();


CREATE TABLE IF NOT EXISTS agent_transcripts (
    transcript_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id           UUID         NOT NULL REFERENCES agent_sessions(session_id) ON DELETE CASCADE,

    -- Denormalised for RLS — see header. Always equals
    -- (SELECT enterprise_id FROM agent_sessions WHERE session_id = ...).
    enterprise_id        UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- Order within the session. 0 = planner output, 1..N = executor steps,
    -- N+1 = critic verdict. Unique per session so transcripts ORDER BY
    -- step_index renders deterministically even after replan.
    step_index           SMALLINT     NOT NULL CHECK (step_index >= 0),

    -- Which agent role produced this transcript row.
    role                 VARCHAR(20)  NOT NULL
                                      CHECK (role IN ('planner', 'executor', 'critic')),

    -- Executor-only fields (NULL for planner/critic rows).
    tool_name            VARCHAR(100),
    tool_args            JSONB,
    tool_result          JSONB,
    tool_ok              BOOLEAN,

    -- LLM accounting. tokens=0 for executor rows where the tool didn't
    -- itself call an LLM; latency captures the dispatch wall time.
    llm_tokens           INT          NOT NULL DEFAULT 0,
    latency_ms           INT          NOT NULL DEFAULT 0,

    -- Free-text trail. For planner/critic rows this holds the role's
    -- own reasoning; for executor rows it carries the tool's status
    -- ("dispatched OK" / "blocked: dry_run=true so email skipped").
    reasoning            TEXT,

    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_agent_transcript_step UNIQUE (session_id, step_index)
);

-- Read path: load full transcript ordered by step.
CREATE INDEX IF NOT EXISTS idx_agent_transcripts_session
    ON agent_transcripts(session_id, step_index);

-- Append-only — no UPDATE / DELETE. Same pattern as bronze_rows
-- (002_pipeline.sql) and decision_audit_log.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'agent_transcripts' AND rulename = 'agent_transcripts_no_update'
    ) THEN
        CREATE RULE agent_transcripts_no_update AS ON UPDATE TO agent_transcripts DO INSTEAD NOTHING;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_rules WHERE tablename = 'agent_transcripts' AND rulename = 'agent_transcripts_no_delete'
    ) THEN
        CREATE RULE agent_transcripts_no_delete AS ON DELETE TO agent_transcripts DO INSTEAD NOTHING;
    END IF;
END $$;


-- RLS — tenant isolation + admin bypass for both tables.
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_transcripts ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'agent_sessions' AND policyname = 'tenant_agent_sessions'
    ) THEN
        CREATE POLICY tenant_agent_sessions ON agent_sessions
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'agent_sessions' AND policyname = 'admin_bypass_agent_sessions'
    ) THEN
        CREATE POLICY admin_bypass_agent_sessions ON agent_sessions
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'agent_transcripts' AND policyname = 'tenant_agent_transcripts'
    ) THEN
        CREATE POLICY tenant_agent_transcripts ON agent_transcripts
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'agent_transcripts' AND policyname = 'admin_bypass_agent_transcripts'
    ) THEN
        CREATE POLICY admin_bypass_agent_transcripts ON agent_transcripts
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON agent_sessions     TO kaori_app;
GRANT SELECT, INSERT          ON agent_transcripts TO kaori_app;
-- agent_transcripts has no UPDATE grant (rule blocks it anyway, but the
-- absent grant is the belt to the rule's suspenders).

COMMIT;
