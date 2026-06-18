-- =====================================================================
-- 130_workflow_review.sql — Qwen Workflow Advisor (ADR-0040)
--
-- Append-only history of workflow self-evaluations. Each row = one advisor
-- run (static or runtime) producing an overall_health score + a findings[]
-- array (rule-detected, optionally narrated by Qwen — see ADR-0040). Re-run
-- writes a new row; the FE reads the latest per workflow.
--
-- Additive: new table only. K-21 (gen_uuid_v7 PK) + RLS K-1 (enterprise
-- isolation — mirror mig 119). Not dept-scoped: a review is workflow-level.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_review (
    review_id      UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    enterprise_id  UUID         NOT NULL,
    workflow_id    UUID         NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,

    run_mode       VARCHAR(16)  NOT NULL DEFAULT 'static',   -- static | runtime
    model          VARCHAR(40)  NOT NULL DEFAULT 'rules-only', -- rules-only | qwen2.5-local | ...
    overall_health NUMERIC(4,3),                              -- 0.000–1.000 (K-9 spirit: no FLOAT)
    findings       JSONB        NOT NULL DEFAULT '[]'::jsonb,  -- [{category,severity,step_id,title,detail,suggestion,confidence}]
    narrative      TEXT,                                       -- optional grounded Qwen executive summary

    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_wfreview_mode   CHECK (run_mode IN ('static', 'runtime')),
    CONSTRAINT chk_wfreview_health CHECK (overall_health IS NULL OR (overall_health >= 0 AND overall_health <= 1))
);

CREATE INDEX IF NOT EXISTS idx_wfreview_latest
    ON workflow_review(enterprise_id, workflow_id, created_at DESC);
-- JSONB containment queries ("workflows with a high-severity finding").
CREATE INDEX IF NOT EXISTS idx_wfreview_findings
    ON workflow_review USING GIN (findings);

-- ─── RLS (K-1) — mirror mig 119 isolation ────────────────────────────
ALTER TABLE workflow_review ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_wfreview ON workflow_review;
CREATE POLICY isolation_wfreview ON workflow_review
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_review TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE workflow_review IS
    'ADR-0040 Qwen Workflow Advisor — append-only workflow self-evaluation '
    '(static/runtime). findings[] are rule-detected (deterministic, no '
    'hallucination per K-3); narrative is optional grounded Qwen summary. '
    'RLS K-1 per mig 119.';

COMMIT;
