-- =====================================================================
-- 131_document_analysis.sql — Document analyzer (ADR-0040 follow-up / Option 1)
--
-- Stores the analysis of an uploaded business document (hợp đồng / hóa đơn):
-- deterministic risk-keyword flags + grounded Qwen summary + extracted key
-- fields. One row per analyze run (append-only history); FE reads the latest
-- per attachment. Bridges "tài liệu đã trích xuất → insight".
--
-- Additive: new table only. K-21 (gen_uuid_v7 PK) + RLS K-1 (mirror mig 130).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS document_analysis (
    analysis_id   UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    enterprise_id UUID         NOT NULL,
    attachment_id UUID         NOT NULL REFERENCES workflow_step_documents(attachment_id) ON DELETE CASCADE,

    model         VARCHAR(40)  NOT NULL DEFAULT 'rules-only',  -- rules-only | qwen2.5-local
    summary       TEXT,
    key_fields    JSONB        NOT NULL DEFAULT '[]'::jsonb,    -- [{label,value}]
    risks         JSONB        NOT NULL DEFAULT '[]'::jsonb,    -- [{keyword,severity,snippet}]

    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docanalysis_latest
    ON document_analysis(enterprise_id, attachment_id, created_at DESC);

-- ─── RLS (K-1) — mirror mig 130 ──────────────────────────────────────
ALTER TABLE document_analysis ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_docanalysis ON document_analysis;
CREATE POLICY isolation_docanalysis ON document_analysis
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON document_analysis TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE document_analysis IS
    'Document analyzer (Option 1) — per-attachment summary + key_fields + risks. '
    'risks deterministic (keyword scan, K-3); summary/key_fields grounded Qwen. '
    'RLS K-1 per mig 130.';

COMMIT;
