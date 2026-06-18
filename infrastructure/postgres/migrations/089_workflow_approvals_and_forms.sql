-- =====================================================================
-- 089_workflow_approvals_and_forms.sql
--
-- Two tables supporting commit 2 of the workflow-gap closeout:
--   workflow_approvals         — pending + resolved approval gates
--   workflow_form_submissions  — form-driven workflow triggers
--
-- approval_gate executor INSERTs into workflow_approvals when paused;
-- POST /workflow-runs/{run_id}/approve UPDATES status='approved' (or
-- 'rejected') and the resume endpoint fires the runner from the paused
-- node onward.
--
-- read_form_submission executor SELECTs from workflow_form_submissions.
-- Caller (FE form OR webhook ingest) INSERTs the row before triggering
-- the workflow run; status='pending' rows are eligible for pick-up.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_approvals (
    approval_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID            NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    node_id             UUID            NOT NULL REFERENCES workflow_nodes(node_id) ON DELETE CASCADE,
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    approver_roles      TEXT[]          NOT NULL,
    approver_user_id    UUID,
    sla_minutes         INT             NOT NULL DEFAULT 240,
    reason_prompt       TEXT            DEFAULT '',
    status              VARCHAR(32)     NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','approved','rejected','expired','cancelled')),
    resolved_by_user_id UUID,
    resolved_at         TIMESTAMPTZ,
    decision_note       TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    UNIQUE (run_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_approvals_pending
    ON workflow_approvals(enterprise_id, status, created_at DESC)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_workflow_approvals_user
    ON workflow_approvals(approver_user_id, status)
    WHERE status = 'pending' AND approver_user_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS workflow_form_submissions (
    submission_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id         UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    form_key              VARCHAR(64)     NOT NULL,
    payload               JSONB           NOT NULL DEFAULT '{}'::jsonb,
    submitted_by_user_id  UUID,
    submitted_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    status                VARCHAR(32)     NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','consumed','expired','rejected')),
    consumed_at           TIMESTAMPTZ,
    consumed_by_run_id    UUID REFERENCES workflow_runs(run_id) ON DELETE SET NULL,
    source_channel        VARCHAR(32)     NOT NULL DEFAULT 'web'
                            CHECK (source_channel IN ('web','mobile','webhook','email','zalo','api'))
);

CREATE INDEX IF NOT EXISTS idx_form_submissions_pending
    ON workflow_form_submissions(enterprise_id, form_key, submitted_at)
    WHERE status = 'pending';

ALTER TABLE workflow_approvals          ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_form_submissions   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS workflow_approvals_isolation ON workflow_approvals;
CREATE POLICY workflow_approvals_isolation ON workflow_approvals
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

DROP POLICY IF EXISTS workflow_form_submissions_isolation ON workflow_form_submissions;
CREATE POLICY workflow_form_submissions_isolation ON workflow_form_submissions
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
