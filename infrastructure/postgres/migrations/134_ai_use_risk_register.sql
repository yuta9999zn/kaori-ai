-- =====================================================================
-- 134_ai_use_risk_register.sql — EU AI Act Layer 2 (ADR-0041, K-22)
--
-- Append-only classification of each AI-use / workflow into an EU AI Act
-- risk_tier. Re-classify writes a NEW row; readers take the latest per
-- workflow (mirror workflow_review mig 130). controls_required is the set
-- of Kaori controls (K-23/K-24/K-25/K-26/K-6) auto-derived from the tier.
--
-- Additive: new table only. K-21 (gen_uuid_v7 PK + gen_ulid external) +
-- RLS K-1 (enterprise isolation — mirror mig 130). Nullable workflow_id:
-- an AI-use may not map to a single workflow.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_use_risk_register (
    ai_use_id          UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    public_ref         TEXT         NOT NULL DEFAULT gen_ulid(),         -- K-21 external
    enterprise_id      UUID         NOT NULL,
    workflow_id        UUID         REFERENCES workflows(workflow_id) ON DELETE CASCADE,

    use_name           VARCHAR(160) NOT NULL,
    risk_tier          VARCHAR(16)  NOT NULL,   -- prohibited | high | limited | minimal
    annex_iii_category VARCHAR(80),             -- optional Annex III bucket
    rationale          TEXT,
    controls_required  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    status             VARCHAR(16)  NOT NULL DEFAULT 'active',  -- active | blocked

    classified_by      UUID,
    classified_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_airisk_tier   CHECK (risk_tier IN ('prohibited','high','limited','minimal')),
    CONSTRAINT chk_airisk_status CHECK (status IN ('active','blocked')),
    CONSTRAINT uq_airisk_public  UNIQUE (public_ref)
);

-- Latest classification per workflow (the prohibited-block reads this).
CREATE INDEX IF NOT EXISTS idx_airisk_latest
    ON ai_use_risk_register(enterprise_id, workflow_id, classified_at DESC);
CREATE INDEX IF NOT EXISTS idx_airisk_controls
    ON ai_use_risk_register USING GIN (controls_required);

-- ─── RLS (K-1) — mirror mig 130 isolation ────────────────────────────
ALTER TABLE ai_use_risk_register ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_airisk ON ai_use_risk_register;
CREATE POLICY isolation_airisk ON ai_use_risk_register
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ai_use_risk_register TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE ai_use_risk_register IS
    'ADR-0041 EU AI Act Layer 2 (K-22) — append-only risk classification per '
    'AI-use/workflow. risk_tier drives controls_required (K-23/24/25/26/6). '
    'prohibited => publish/run blocked. RLS K-1 per mig 130.';

COMMIT;
