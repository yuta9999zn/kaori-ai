-- =====================================================================
-- 133_bronze_file_embeddings.sql — stored embeddings for the RAG corpus
--
-- pgvector_real re-embedded every bronze doc on EVERY query (the engine
-- docstring's acknowledged Phase-2 debt → ~85s for tenants with docs). This
-- adds a write-through embedding cache so a doc is embedded ONCE.
--
-- K-2 compliant: bronze_files stays append-only/untouched — embeddings live in
-- a SEPARATE table (INSERT-only here; file_id is immutable so the cache never
-- needs UPDATE). K-1 RLS via enterprise_id. bge-m3 = VECTOR(1024) (mig 067 vector ext).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS bronze_file_embeddings (
    file_id         UUID         PRIMARY KEY REFERENCES bronze_files(file_id) ON DELETE CASCADE,
    enterprise_id   UUID         NOT NULL,
    embedding       VECTOR(1024) NOT NULL,
    embedding_model VARCHAR(40)  NOT NULL DEFAULT 'bge-m3',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bfe_enterprise ON bronze_file_embeddings(enterprise_id);

ALTER TABLE bronze_file_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_bfe ON bronze_file_embeddings;
CREATE POLICY isolation_bfe ON bronze_file_embeddings
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON bronze_file_embeddings TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE bronze_file_embeddings IS
    'Write-through embedding cache for the pgvector RAG corpus (bronze docsage '
    'text). Embed-once; file_id immutable (K-2). RLS K-1 per enterprise_id.';

COMMIT;
