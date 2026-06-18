-- =====================================================================
-- 066_docsage_cache.sql
--
-- P15-S11 D1 (per docs/sprint/P15-S11_DOCSAGE_PLAN.md §3 D1).
-- DocSage cache tables for the 3-module structured-SQL RAG engine.
--
-- DocSage flow per ADR-0019:
--   1. Schema Discovery (LLM) → SchemaDefinition cached here per
--      (enterprise_id, corpus_hash, question_class).
--   2. Structured Extraction (LLM per doc) → rows cached here per
--      (enterprise_id, schema_id, doc_id).
--   3. SQL Reasoning runs against ephemeral CREATE TEMP TABLE — no
--      persistent storage here (temp tables die at txn commit).
--
-- Why two tables not one
-- ----------------------
-- Schema is per-question-class; extraction is per-doc within a schema.
-- A 50-doc corpus + 4 question classes = 1 schema row + 50 extraction
-- rows; 4 question classes asked twice = 4 schema cache hits + 200
-- extraction cache hits. Two-table layout maximises cache reuse.
--
-- K-1 / K-19 compliance
-- ---------------------
-- Both tables RLS-enabled. Reads/writes via acquire_for_tenant; SET LOCAL
-- app.enterprise_id gates rows. Snapshot regen (scripts/schema-drift.py
-- --write) MUST run after this migration lands.
--
-- K-20 compliance
-- ---------------
-- Each cached row records (llm_model, llm_version). Cache miss when
-- the routing tier upgrades the model — drift control per K-20.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS docsage_schemas (
    schema_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    -- sha256 of the corpus titles (or file_ids, sorted). Stable across
    -- the same corpus regardless of ordering; changes when a doc is
    -- added or removed, forcing re-discovery.
    corpus_hash      TEXT            NOT NULL,

    -- One of: 'comparison', 'aggregation', 'relationship', 'ranking'.
    -- Bounded vocab keeps cache reuse high — same intent → same row.
    question_class   VARCHAR(20)     NOT NULL,

    -- The discovered minimal joinable schema. Shape matches the
    -- SchemaDefinition Pydantic model in reasoning/rag/engines/docsage/
    -- types.py (P15-S11 D3).
    schema_json      JSONB           NOT NULL,

    -- K-20 — record which model produced this schema. Cache miss on
    -- version upgrade keeps everyone honest about drift.
    llm_model        VARCHAR(64)     NOT NULL,
    llm_version      VARCHAR(32)     NOT NULL,

    -- NOV-CST-009 input — sum input + output tokens.
    token_count      INTEGER         NOT NULL DEFAULT 0,

    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_docsage_question_class CHECK (question_class IN
        ('comparison', 'aggregation', 'relationship', 'ranking')),
    CONSTRAINT uq_docsage_schemas_cache
        UNIQUE (enterprise_id, corpus_hash, question_class)
);

CREATE INDEX IF NOT EXISTS idx_docsage_schemas_lookup
    ON docsage_schemas (enterprise_id, corpus_hash, question_class);


CREATE TABLE IF NOT EXISTS docsage_extractions (
    extraction_id    UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    schema_id        UUID            NOT NULL REFERENCES docsage_schemas(schema_id) ON DELETE CASCADE,

    -- bronze_files.file_id::text in practice. TEXT (not UUID) so non-
    -- bronze sources (Markdown notes, web archives) can also be
    -- cached under a synthetic doc_id.
    doc_id           TEXT            NOT NULL,

    -- list[Row] per P15-S11 plan §3 D4 — each item shape:
    --   { "table": "branches", "values": {...}, "source_segment": [3, 5] }
    rows_json        JSONB           NOT NULL,

    -- Per-doc outcome. 'partial' = exceeded 8K token cap + split-merge
    -- recovered some rows but not all. 'failed' = unrecoverable error
    -- (caller may still proceed with the rest of the corpus).
    extraction_status VARCHAR(20)    NOT NULL DEFAULT 'ok',
    error_message    TEXT,

    token_count      INTEGER         NOT NULL DEFAULT 0,

    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_docsage_extract_status CHECK (extraction_status IN
        ('ok', 'partial', 'failed')),
    CONSTRAINT uq_docsage_extractions_cache
        UNIQUE (enterprise_id, schema_id, doc_id)
);

CREATE INDEX IF NOT EXISTS idx_docsage_extractions_lookup
    ON docsage_extractions (enterprise_id, schema_id);


-- ─── RLS (K-1) ───────────────────────────────────────────────────────
ALTER TABLE docsage_schemas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE docsage_schemas      FORCE ROW LEVEL SECURITY;
ALTER TABLE docsage_extractions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE docsage_extractions  FORCE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'docsage_schemas'
          AND policyname = 'tenant_docsage_schemas'
    ) THEN
        CREATE POLICY tenant_docsage_schemas ON docsage_schemas
            USING (enterprise_id = (current_setting('app.enterprise_id', true))::uuid);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'docsage_schemas'
          AND policyname = 'admin_bypass_docsage_schemas'
    ) THEN
        CREATE POLICY admin_bypass_docsage_schemas ON docsage_schemas
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'docsage_extractions'
          AND policyname = 'tenant_docsage_extractions'
    ) THEN
        CREATE POLICY tenant_docsage_extractions ON docsage_extractions
            USING (enterprise_id = (current_setting('app.enterprise_id', true))::uuid);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'docsage_extractions'
          AND policyname = 'admin_bypass_docsage_extractions'
    ) THEN
        CREATE POLICY admin_bypass_docsage_extractions ON docsage_extractions
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;


-- ─── Grants ──────────────────────────────────────────────────────────
GRANT SELECT, INSERT, DELETE ON docsage_schemas      TO kaori_app;
GRANT SELECT, INSERT, DELETE ON docsage_extractions  TO kaori_app;

-- DELETE allowed so cache eviction (LRU / model-upgrade flush) can run
-- under kaori_app without superuser escalation. UPDATE intentionally
-- NOT granted — cache is write-once + delete-on-evict.

COMMIT;

COMMENT ON TABLE docsage_schemas IS
    'P15-S11 D1 — cached SchemaDefinition per (enterprise, corpus_hash, question_class). K-20 model+version pinned.';
COMMENT ON TABLE docsage_extractions IS
    'P15-S11 D1 — cached per-doc rows extracted under a schema. Idempotent — extraction deterministic for same (schema, doc).';
