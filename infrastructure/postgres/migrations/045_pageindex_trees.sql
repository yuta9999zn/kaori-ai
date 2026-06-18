-- 045_pageindex_trees.sql — RAG-PAGEINDEX-001 P15-S11 persistence cache.
--
-- PageIndex hierarchical TOC trees are expensive to build (LLM-driven
-- traversal of the full document) so we cache them per
-- (tenant_id, doc_sha256, schema_version). A retry of the build
-- workflow keys on cache_key (SHA-256 of "tenant|doc|schema") and
-- hits the same row instead of regenerating.
--
-- This migration ships AHEAD of the real PageIndex wrap so the schema
-- is stable when FixturePageIndexTreeBuilder lands (P15-S11) and the
-- future UpstreamPageIndexTreeBuilder lands post-Build-Week (S12+).
--
-- Until either of those builders cuts over, the table stays empty —
-- StubPageIndexTreeBuilder builds in-memory on every call (cheap,
-- deterministic, no DB round-trip needed).

CREATE TABLE IF NOT EXISTS pageindex_trees (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cache identity
    tenant_id           UUID NOT NULL,                      -- K-1 tenant scope
    doc_sha256          TEXT NOT NULL,                      -- SHA-256 hex of source bytes
    schema_version      SMALLINT NOT NULL CHECK (schema_version > 0),
    cache_key           TEXT NOT NULL,                      -- SHA-256(tenant|doc|schema_version) — REL-005 idempotency
    doc_kind            TEXT NOT NULL CHECK (doc_kind IN ('pdf', 'markdown')),

    -- Tree payload (JSONB so the hierarchical PageIndexNode structure
    -- round-trips without a separate nodes table — Phase 1 simple).
    -- Shape mirrors PageIndexTree.root → PageIndexNode dataclass.
    tree_root           JSONB NOT NULL,

    -- Provenance / lineage — useful for audit + cache invalidation.
    builder_kind        TEXT NOT NULL CHECK (builder_kind IN ('stub', 'fixture', 'upstream')),
    builder_version     TEXT,                               -- e.g. 'pageindex==0.2.8' or 'fixture-tableau-v1'
    llm_model           TEXT,                               -- e.g. 'qwen2.5:14b' or 'gpt-4o-2024-08-06' — K-20
    doc_size_bytes      BIGINT CHECK (doc_size_bytes >= 0),
    node_count          INTEGER CHECK (node_count > 0),

    -- Lifecycle
    built_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ                         -- NULL = never expires; set on tenant config
);

-- Cache lookup — primary read path: "do I have a tree for this
-- (tenant, doc, schema) combination?" Hits the cache_key directly.
CREATE UNIQUE INDEX IF NOT EXISTS pageindex_trees_cache_key_uniq
    ON pageindex_trees (cache_key);

-- Tenant-scoped listing (admin / observability dashboard):
--   "show all PageIndex trees built for this tenant in last 30 days"
CREATE INDEX IF NOT EXISTS pageindex_trees_tenant_built_idx
    ON pageindex_trees (tenant_id, built_at DESC);

-- TTL sweep — Phase 2 job picks up rows where expires_at < now() and
-- DELETEs them. Index covers the WHERE clause.
CREATE INDEX IF NOT EXISTS pageindex_trees_expires_idx
    ON pageindex_trees (expires_at)
    WHERE expires_at IS NOT NULL;

-- RLS — K-1 tenant isolation per ADR-0013.
ALTER TABLE pageindex_trees ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pageindex_trees_tenant_isolation ON pageindex_trees;
CREATE POLICY pageindex_trees_tenant_isolation ON pageindex_trees
    USING      (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

COMMENT ON TABLE  pageindex_trees IS
    'P15-S11 RAG-PAGEINDEX-001 — hierarchical TOC tree cache per (tenant, doc, schema_version). Re-build on schema_version bump.';
COMMENT ON COLUMN pageindex_trees.cache_key IS
    'SHA-256 of "tenant_id|doc_sha256|schema_version". Hits same row on workflow retry — REL-005 idempotency invariant.';
COMMENT ON COLUMN pageindex_trees.tree_root IS
    'JSONB serialisation of PageIndexNode dataclass starting at root. Children nested in-place via "children" key.';
COMMENT ON COLUMN pageindex_trees.builder_kind IS
    'stub = StubPageIndexTreeBuilder (synthetic), fixture = FixturePageIndexTreeBuilder (offline pre-compute), upstream = UpstreamPageIndexTreeBuilder (PyPI live wrap). Operator filters by this to find stub/fixture leakage into prod.';
COMMENT ON COLUMN pageindex_trees.llm_model IS
    'LLM model identifier per K-20 — record which model built this tree so version drift triggers schema_version bump.';
