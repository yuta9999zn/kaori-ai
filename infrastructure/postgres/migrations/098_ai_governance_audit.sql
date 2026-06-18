-- =====================================================================
-- 098_ai_governance_audit.sql
--
-- P3 of Phase 2.7 (per anh's review §3C "AI governance layer"). Records
-- every llm-gateway call with the governance fields enterprise regulators
-- expect: model_version, prompt_hash, context_refs, confidence, human
-- override.
--
-- Different from decision_audit_log (mig 002) — that captures
-- BUSINESS decisions (chosen action vs alternatives). This table
-- captures the AI CALL that fed any decision (model + prompt hash +
-- context referenced). Together they form the full AI governance trail.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_decision_audit (
    audit_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id       UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    request_id          UUID,
    decision_id         UUID,
    run_id              UUID,
    node_id             UUID,
    task_kind           VARCHAR(64)     NOT NULL,
    model_version       VARCHAR(128)    NOT NULL,
    model_provider      VARCHAR(64)     NOT NULL,
    prompt_hash         CHAR(64)        NOT NULL,
    prompt_size_bytes   INT             NOT NULL DEFAULT 0,
    context_refs        JSONB           NOT NULL DEFAULT '[]'::jsonb,
    confidence          NUMERIC(5,4),
    output_hash         CHAR(64),
    output_size_bytes   INT             NOT NULL DEFAULT 0,
    output_validated    BOOLEAN         NOT NULL DEFAULT FALSE,
    consent_external    BOOLEAN         NOT NULL DEFAULT FALSE,
    pii_redacted        BOOLEAN         NOT NULL DEFAULT FALSE,
    human_override_user_id UUID,
    human_override_at      TIMESTAMPTZ,
    human_override_note    TEXT,
    latency_ms          INT             NOT NULL DEFAULT 0,
    token_input_count   INT             NOT NULL DEFAULT 0,
    token_output_count  INT             NOT NULL DEFAULT 0,
    cost_cents          NUMERIC(14, 4)  NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Hot path: list AI calls for a tenant for compliance export
CREATE INDEX IF NOT EXISTS idx_ai_governance_tenant_recent
    ON ai_decision_audit(enterprise_id, created_at DESC);

-- Trace path: which AI calls fed a workflow run
CREATE INDEX IF NOT EXISTS idx_ai_governance_run
    ON ai_decision_audit(run_id, created_at)
    WHERE run_id IS NOT NULL;

-- Override path: surfaces AI calls where a human disagreed
CREATE INDEX IF NOT EXISTS idx_ai_governance_overrides
    ON ai_decision_audit(enterprise_id, human_override_at DESC)
    WHERE human_override_user_id IS NOT NULL;

-- Append-only — humans correct via override row, never edit history.
CREATE OR REPLACE FUNCTION ai_governance_block_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    -- Allow ONLY override field UPDATE (human_override_user_id/at/note);
    -- everything else immutable.
    IF TG_OP = 'UPDATE' THEN
        IF (OLD.audit_id <> NEW.audit_id) OR
           (OLD.enterprise_id <> NEW.enterprise_id) OR
           (OLD.task_kind <> NEW.task_kind) OR
           (OLD.model_version <> NEW.model_version) OR
           (OLD.prompt_hash <> NEW.prompt_hash) OR
           (OLD.created_at <> NEW.created_at)
        THEN
            RAISE EXCEPTION 'ai_decision_audit core fields are immutable (TG_OP=%); audit_id=%',
                TG_OP, OLD.audit_id;
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'ai_decision_audit rows are append-only (TG_OP=DELETE); audit_id=%', OLD.audit_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS ai_governance_immutability ON ai_decision_audit;
CREATE TRIGGER ai_governance_immutability
    BEFORE UPDATE OR DELETE ON ai_decision_audit
    FOR EACH ROW EXECUTE FUNCTION ai_governance_block_mutation();

ALTER TABLE ai_decision_audit ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_governance_isolation ON ai_decision_audit;
CREATE POLICY ai_governance_isolation ON ai_decision_audit
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
