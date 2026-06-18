-- =====================================================================
-- 136_ai_incident.sql — EU AI Act Layer 3 (ADR-0041, K-26)
--
-- Post-market monitoring (Art 72) + serious-incident register (Art 73).
-- Append-and-update register: one row per incident, lifecycle via `status`.
-- severity 'serious' = Art 73-reportable.
--
-- Number 136 (NOT 134/135): those are claimed by open PRs #347 (134) /
-- #348 (135). Gap-tolerant Flyway; avoids a merge collision.
--
-- K-21 (gen_uuid_v7 PK + gen_ulid external) + RLS K-1 (mirror mig 130).
-- Additive: new table only.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_incident (
    incident_id    UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    public_ref     TEXT         NOT NULL DEFAULT gen_ulid(),         -- K-21 external
    enterprise_id  UUID         NOT NULL,

    incident_type  VARCHAR(48)  NOT NULL,   -- wrong_decision | data_leak | model_drift | pipeline_failure | other
    severity       VARCHAR(12)  NOT NULL,   -- low | medium | high | serious
    status         VARCHAR(16)  NOT NULL DEFAULT 'open',  -- open | investigating | resolved
    title          VARCHAR(200) NOT NULL,
    description    TEXT,

    decision_id    UUID,
    run_id         UUID,
    workflow_id    UUID,
    detail         JSONB        NOT NULL DEFAULT '{}'::jsonb,

    reported_by    UUID,
    reported_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ,

    CONSTRAINT chk_incident_severity CHECK (severity IN ('low','medium','high','serious')),
    CONSTRAINT chk_incident_status   CHECK (status IN ('open','investigating','resolved')),
    CONSTRAINT uq_incident_public    UNIQUE (public_ref)
);

CREATE INDEX IF NOT EXISTS idx_incident_open
    ON ai_incident(enterprise_id, status, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_severity
    ON ai_incident(enterprise_id, severity);

-- ─── RLS (K-1) — mirror mig 130 isolation ────────────────────────────
ALTER TABLE ai_incident ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_incident ON ai_incident;
CREATE POLICY isolation_incident ON ai_incident
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ai_incident TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE ai_incident IS
    'ADR-0041 K-26 — EU AI Act post-market monitoring (Art 72) + serious-incident '
    'register (Art 73). severity=serious is reportable. RLS K-1 per mig 130.';

COMMIT;
