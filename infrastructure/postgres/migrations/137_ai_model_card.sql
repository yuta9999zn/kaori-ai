-- =====================================================================
-- 137_ai_model_card.sql — EU AI Act Layer 2 (ADR-0041, K-25)
--
-- Annex IV-lite technical documentation (model card) per (model, version)
-- of the K-20 LLM-pinning registry. Satisfies the K-25_MODEL_CARD control
-- that `risk_tier = high` auto-requires (reasoning/compliance_controls.py).
--
-- Append-only: re-authoring a card writes a NEW row; readers take the latest
-- per (enterprise_id, model, version) — mirror ai_use_risk_register (mig 134).
-- `completeness` snapshots {complete, missing[]} at author time so a reader can
-- tell whether the Annex IV-lite sections were all filled without re-deriving.
--
-- K-21 (gen_uuid_v7 PK + gen_ulid external) + RLS K-1 (mirror mig 130/134).
-- Additive: new table only. Max migration number was 136 → this is 137.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_model_card (
    model_card_id          UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    public_ref             TEXT         NOT NULL DEFAULT gen_ulid(),         -- K-21 external
    enterprise_id          UUID         NOT NULL,

    model                  VARCHAR(120) NOT NULL,   -- K-20 model id, e.g. qwen2.5:14b / claude-opus-4-8
    version                VARCHAR(40)  NOT NULL,    -- K-20 pinned version, e.g. "2026-01-01"
    provider               VARCHAR(40),             -- ollama | anthropic | openai | ...

    -- Annex IV-lite sections (Art 11 technical documentation):
    intended_purpose       TEXT         NOT NULL,   -- Annex IV §1 — what the system is for
    capabilities           TEXT,                    -- Annex IV §1 — what it can do
    limitations            TEXT,                    -- Art 13 / Annex IV §3 — known limits
    training_data_summary  TEXT,                    -- Annex IV §2(d) — data provenance summary
    evaluation_summary     TEXT,                    -- Annex IV §2(g) — metrics / accuracy
    risk_mitigations       TEXT,                    -- Annex IV §2(e) — human oversight / guardrails
    foreseeable_misuse     TEXT,                    -- reasonably-foreseeable misuse

    annex_iv               JSONB        NOT NULL DEFAULT '{}'::jsonb,   -- extensible structured doc
    completeness           JSONB        NOT NULL DEFAULT '{}'::jsonb,   -- {complete, missing[]} snapshot
    status                 VARCHAR(16)  NOT NULL DEFAULT 'active',      -- active | archived

    authored_by            UUID,
    authored_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_modelcard_status CHECK (status IN ('active','archived')),
    CONSTRAINT uq_modelcard_public  UNIQUE (public_ref)
);

-- Latest card per (model, version) — the K-25 satisfaction lookup reads this.
CREATE INDEX IF NOT EXISTS idx_modelcard_latest
    ON ai_model_card(enterprise_id, model, version, authored_at DESC);

-- ─── RLS (K-1) — mirror mig 130/134 isolation ────────────────────────
ALTER TABLE ai_model_card ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_modelcard ON ai_model_card;
CREATE POLICY isolation_modelcard ON ai_model_card
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ai_model_card TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE ai_model_card IS
    'ADR-0041 K-25 — EU AI Act Annex IV-lite model card per (model, version) of '
    'the K-20 registry. Satisfies the K-25_MODEL_CARD control required by '
    'risk_tier=high. Append-only (latest per model+version). RLS K-1 per mig 130.';

COMMIT;
