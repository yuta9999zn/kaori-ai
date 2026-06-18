-- =====================================================================
-- 106_knowledge_documents.sql — Domain knowledge base (CR-0017)
--
-- The RAG corpus today (pgvector_real.py _load_corpus) is per-tenant text
-- pulled from bronze_files (the customer's own uploaded data). There is NO
-- store for DOMAIN/INDUSTRY knowledge — the churn benchmarks, RFM segmentation,
-- retention playbooks, NOV/ROI rules that let the AI reason "học 1 hiểu 10".
-- This migration adds that store.
--
-- 4-tier source authority (per docs/strategic/REASONING_LAYER.md Phần 10):
--   tier 1 REGULATORY      — SBV/Basel/IFRS … (absolute)
--   tier 2 KAORI CURATED   — validated domain knowledge (high)
--   tier 3 MARKET/INDUSTRY — McKinsey/BCG/academic (advisory)
--   tier 4 TENANT-SPECIFIC — a tenant's own SOPs/targets (high for them only)
--
-- tenant_id semantics:
--   NULL      → GLOBAL knowledge (tier 1-3), readable by every tenant. Curated
--               by the platform (seeded via migration / admin path, is_admin).
--   non-NULL  → TENANT-SPECIFIC (tier 4). A tenant writes/reads only its own.
--
-- Embedding: VECTOR(1024) BGE-M3 (same as memory_l3 mig 067). Nullable so a row
-- can land before it is embedded; semantic_search filters embedding IS NOT NULL
-- + embedding_model (K-20 — model upgrade evicts stale vectors).
-- =====================================================================

BEGIN;

-- pgvector already enabled by mig 067; idempotent guard regardless.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- NULL = global (tier 1-3) · non-NULL = tenant-specific (tier 4)
    tenant_id        UUID         REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    tier             SMALLINT     NOT NULL,
    category         VARCHAR(64),                 -- 'churn' | 'rfm' | 'retention' | 'nov' | …
    title            TEXT         NOT NULL,
    content          TEXT         NOT NULL,

    source           VARCHAR(255),                -- provenance label (file/paper/circular)
    source_url       TEXT,
    lang             VARCHAR(8)   NOT NULL DEFAULT 'vi',

    status           VARCHAR(16)  NOT NULL DEFAULT 'active',

    -- BGE-M3 1024-dim; nullable until embedded (K-20 model pin)
    embedding        VECTOR(1024),
    embedding_model  VARCHAR(64),

    tags             JSONB        NOT NULL DEFAULT '[]'::jsonb,

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_knowledge_tier   CHECK (tier IN (1, 2, 3, 4)),
    CONSTRAINT chk_knowledge_status CHECK (status IN ('proposed', 'active', 'archived')),
    -- tier 4 MUST be tenant-scoped; tiers 1-3 MUST be global. Keeps the
    -- authority model honest (a tenant can't masquerade its SOP as regulatory).
    CONSTRAINT chk_knowledge_tier_scope CHECK (
        (tier = 4 AND tenant_id IS NOT NULL) OR
        (tier IN (1, 2, 3) AND tenant_id IS NULL)
    )
);

-- Read paths: list by tenant+status, filter by category, semantic search.
CREATE INDEX IF NOT EXISTS idx_knowledge_tenant_status
    ON knowledge_documents (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON knowledge_documents (category) WHERE category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_knowledge_global
    ON knowledge_documents (status) WHERE tenant_id IS NULL;

-- HNSW pgvector cosine index (mirrors mig 067 memory_l3).
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_hnsw
    ON knowledge_documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── RLS (K-1) ────────────────────────────────────────────────────────
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_documents FORCE ROW LEVEL SECURITY;

-- A tenant SEES global knowledge (tenant_id IS NULL) + its own rows, but may
-- only WRITE its own (WITH CHECK pins tenant_id to the GUC). NULLIF guards the
-- empty-GUC case so the cast never raises in a non-tenant context.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE tablename = 'knowledge_documents' AND policyname = 'tenant_knowledge_documents'
    ) THEN
        CREATE POLICY tenant_knowledge_documents ON knowledge_documents
            USING (
                tenant_id IS NULL
                OR tenant_id = NULLIF(current_setting('app.enterprise_id', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.enterprise_id', true), '')::uuid
            );
    END IF;
END $$;

-- Platform admin manages global tier 1-3 (seed / curation), bypassing the
-- tenant pin. Caller sets app.is_admin (mirrors mig 105 / mig 025 pattern).
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
         WHERE tablename = 'knowledge_documents' AND policyname = 'admin_bypass_knowledge_documents'
    ) THEN
        CREATE POLICY admin_bypass_knowledge_documents ON knowledge_documents
            USING       (current_setting('app.is_admin', true) = 'true')
            WITH CHECK  (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_documents TO kaori_app;

COMMIT;
