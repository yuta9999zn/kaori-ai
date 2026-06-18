-- Silver tier — pipeline rows (cleaned + typed + PII-masked).
--
-- Phase 1.5 P15-S9 D8 — replicates services/data-pipeline/data_plane/
-- silver/ Postgres table into ClickHouse columnar storage. Phase 1.5+
-- runs both stores via dual-write for 7 days; Phase 2 retires the
-- Postgres copy (read path migrates first → ClickHouse-only writes).
--
-- Why columnar for Silver:
--   * Aggregate queries on Silver (group-by tenant, sum revenue, count
--     events) are 50-100x faster on MergeTree vs Postgres BTree on
--     >10M rows.
--   * Compression: ZSTD on text columns gives ~5x size reduction vs
--     uncompressed Postgres TEXT, important when Silver covers months
--     of pilot history.
--
-- Tenant isolation (ADR-0013):
--   * tenant_id is the FIRST column of ORDER BY → every query scans
--     a contiguous block per tenant; cross-tenant scans are O(N) of
--     ALL data which the query rewriter (Phase 1.5+) refuses.
--   * PARTITION BY (tenant_id, toYYYYMM(occurred_at)) bounds part
--     count + lets DROP PARTITION evict a tenant's month cheaply
--     (used by GDPR right-to-erasure flow Phase 2).

CREATE TABLE IF NOT EXISTS kaori_silver.silver_pipeline_rows
(
    tenant_id        UUID,
    enterprise_id    UUID,
    run_id           UUID,
    row_id           UInt64,
    occurred_at      DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),
    written_at       DateTime64(3, 'UTC') DEFAULT now64() CODEC(Delta, ZSTD(3)),

    -- Cleaned + typed columns. Money is Decimal(14, 4) per K-9.
    customer_external_id  String CODEC(ZSTD(3)),
    revenue_vnd           Decimal(14, 4),
    cost_vnd              Decimal(14, 4),
    is_actioned           UInt8,                  -- 0 / 1

    -- Provenance — PII flag set by the redactor (K-5)
    pii_flag              UInt8 DEFAULT 0,
    -- Source connector identifier (postgres_cdc / excel_filesystem / ...)
    source                LowCardinality(String),

    -- Free-form payload kept for drill-down. ZSTD(3) keeps Silver
    -- compact while preserving the original text for the Gold layer
    -- to re-read.
    payload_json          String CODEC(ZSTD(3))
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/silver_pipeline_rows', '{replica}')
PARTITION BY (tenant_id, toYYYYMM(occurred_at))
ORDER BY (tenant_id, occurred_at, customer_external_id)
TTL occurred_at + INTERVAL 365 DAY DELETE
SETTINGS index_granularity = 8192;

-- Skip indexes — accelerate per-customer + per-source queries without
-- duplicating data into a secondary index. Phase 1.5+ tunes these
-- after the first month of pilot query patterns is observed.
ALTER TABLE kaori_silver.silver_pipeline_rows
    ADD INDEX IF NOT EXISTS idx_customer customer_external_id TYPE bloom_filter GRANULARITY 4,
    ADD INDEX IF NOT EXISTS idx_source   source                TYPE set(8)        GRANULARITY 4;

COMMENT ON TABLE kaori_silver.silver_pipeline_rows IS
    'P15-S9 D8 Silver tier — replicates services/data-pipeline silver Postgres rows. Phase 1.5+ dual-write for 7 days then Phase 2 cutover.';
