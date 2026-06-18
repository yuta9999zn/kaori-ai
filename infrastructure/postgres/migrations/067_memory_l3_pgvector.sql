-- =====================================================================
-- 067_memory_l3_pgvector.sql
--
-- P15-S11 Phase 2 wire — Postgres + pgvector backend for the Stage 7
-- Memory hierarchy L3 tier (per PIPELINE_UNIFIED.md §7.1).
--
-- The in-memory backend (services/ai-orchestrator/reasoning/memory/
-- stores.py InMemoryTierStore) covered Phase 1.5 tests + Pilot demo.
-- This migration adds the persistent L3 table that the production
-- PostgresTierStore (lands in same commit) reads from + writes to.
--
-- Schema design notes
-- -------------------
-- BGE-M3 produces 1024-dimensional vectors (see ADR-0015 +
-- services/llm-gateway/providers.py EMBEDDING_MODEL). pgvector's
-- VECTOR(1024) is the typed column; HNSW index is the high-recall
-- option for retrieval (per pgvector docs — IVFFlat needs training
-- data, HNSW does not).
--
-- Cosine ops `<=>` (cosine distance) is the right operator for
-- semantic similarity; smaller = more similar. SELECT … ORDER BY
-- embedding <=> $1 LIMIT k gives the top-k nearest neighbours.
--
-- K-1: RLS enabled — tenant_id filter on every read.
-- K-5: content_text is masked PII when memory_type ∈ {SEMANTIC,
--      PROCEDURAL} — caller's responsibility (this table just stores
--      what it's given).
-- K-19: tenant_id span attribute on every query — caller's job.
-- K-20: model_name pinned per row so embedding-model upgrade
--       evicts cache (downstream reads filter by model_name).
-- =====================================================================

BEGIN;

-- Enable pgvector — should already be present in the
-- pgvector/pgvector:pg15 docker image; idempotent.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_l3 (
    record_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    memory_type         VARCHAR(20)  NOT NULL,    -- EPISODIC / DECISION / OPERATIONAL primarily; SEMANTIC/PROCEDURAL when L4 promotes back
    content             TEXT         NOT NULL,

    -- The embedding. Nullable so a record can land before the bg
    -- embedding job processes it (the job sets the column).
    embedding           VECTOR(1024),

    -- K-20 — which model produced the embedding. Reads filter by
    -- this so upgrading EMBEDDING_MODEL doesn't return stale vectors.
    embedding_model     VARCHAR(64),

    -- Memory metadata mirrored from MemoryRecord
    session_id          VARCHAR(64),
    entity_id           UUID,
    occurred_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    user_flagged_important BOOLEAN   NOT NULL DEFAULT FALSE,
    linked_outcome_value NUMERIC(14,2) NOT NULL DEFAULT 0,
    session_appearance_count INTEGER NOT NULL DEFAULT 0,
    extra_metadata      JSONB        NOT NULL DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_memory_l3_type CHECK (memory_type IN
        ('EPISODIC', 'SEMANTIC', 'PROCEDURAL', 'OPERATIONAL', 'DECISION'))
);

CREATE INDEX IF NOT EXISTS idx_memory_l3_tenant
    ON memory_l3 (tenant_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_l3_session
    ON memory_l3 (tenant_id, session_id) WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_memory_l3_entity
    ON memory_l3 (tenant_id, entity_id) WHERE entity_id IS NOT NULL;

-- HNSW index for semantic search. m=16 + ef_construction=64 are
-- pgvector defaults; can be tuned per workload Phase 2+. Build is
-- cheap until row count crosses ~50k; we add the index up front so
-- queries don't fall back to sequential scan on day one.
CREATE INDEX IF NOT EXISTS idx_memory_l3_embedding_hnsw
    ON memory_l3 USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ─── RLS (K-1) ──────────────────────────────────────────────────────
ALTER TABLE memory_l3 ENABLE  ROW LEVEL SECURITY;
ALTER TABLE memory_l3 FORCE   ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'memory_l3' AND policyname = 'tenant_memory_l3'
    ) THEN
        CREATE POLICY tenant_memory_l3 ON memory_l3
            USING (tenant_id = (current_setting('app.enterprise_id', true))::uuid);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'memory_l3' AND policyname = 'admin_bypass_memory_l3'
    ) THEN
        CREATE POLICY admin_bypass_memory_l3 ON memory_l3
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;


GRANT SELECT, INSERT, UPDATE, DELETE ON memory_l3 TO kaori_app;
-- UPDATE granted here (unlike docsage_* tables) because the bg
-- embedding job sets the embedding column on an existing row — the
-- record lands before its vector is computed.

COMMIT;

COMMENT ON TABLE memory_l3 IS
    'P15-S11 Phase 2 — Stage 7 Memory L3 tier. Postgres + pgvector backend for episodic/decision/operational memory. BGE-M3 embedding via llm-gateway /v1/embed; cosine distance via pgvector <=> op. K-1 RLS; K-20 embedding_model pinned per row.';

COMMENT ON COLUMN memory_l3.embedding IS
    'BGE-M3 1024-dim vector. NULL until bg embedding job runs (records land before vector is computed).';
COMMENT ON COLUMN memory_l3.embedding_model IS
    'Model name that produced the embedding (e.g. "bge-m3"). Reads filter by this so model upgrade evicts the stale cache.';
