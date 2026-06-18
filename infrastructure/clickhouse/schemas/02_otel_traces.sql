-- OTel traces — warm-tier storage for observability spans.
--
-- Phase 1.5 P15-S9 D8 — Tempo's storage backend for the warm 90-day
-- window. Cold tier (>90 days) lands in MinIO via Tempo's S3 backend.
-- Phase 1 keeps everything in Tempo's local-disk + memory; Phase 1.5
-- shifts long-tail to ClickHouse so Tempo doesn't run out of disk on
-- a high-traffic day.
--
-- K-19 enforcement
-- ================
-- service_name + tenant_id are mandatory columns. The OTel collector
-- (services/.../tracing.py) tags every span with tenant_id; the
-- ClickHouse exporter rejects spans without that attribute. Querying
-- this table without WHERE tenant_id = ? is allowed for platform
-- staff (cross-tenant trace search during incident response) but
-- application code MUST scope; the rewriter enforces.

CREATE TABLE IF NOT EXISTS kaori_silver.otel_traces
(
    tenant_id        UUID,
    trace_id         FixedString(32),       -- OTel hex-encoded 16-byte
    span_id          FixedString(16),       -- OTel hex-encoded 8-byte
    parent_span_id   FixedString(16),
    name             LowCardinality(String),
    service_name     LowCardinality(String),
    span_kind        LowCardinality(String),  -- INTERNAL / SERVER / CLIENT / PRODUCER / CONSUMER
    ts               DateTime64(9, 'UTC') CODEC(Delta, ZSTD(3)),
    duration_ns      UInt64 CODEC(T64, ZSTD(3)),

    -- Status — 0=unset, 1=ok, 2=error
    status_code      UInt8,
    status_message   String CODEC(ZSTD(3)),

    -- Attributes / events / links — Map(LowCardinality(String), String)
    -- compresses well + lets ClickHouse Bloom-filter on common keys
    -- (tenant_id duplicated here for legacy span query paths).
    attributes_keys   Array(LowCardinality(String)),
    attributes_values Array(String) CODEC(ZSTD(3)),
    events_ts         Array(DateTime64(9, 'UTC')),
    events_names      Array(LowCardinality(String)),
    links_trace_ids   Array(FixedString(32))
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/otel_traces', '{replica}')
PARTITION BY (tenant_id, toYYYYMMDD(ts))
ORDER BY (tenant_id, service_name, ts, trace_id)
TTL ts + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192;

-- Trace-id lookup index — typical query is "give me all spans for
-- trace X within the last 24h". Bloom on trace_id + tenant_id prefix
-- in ORDER BY skips 99%+ of the data.
ALTER TABLE kaori_silver.otel_traces
    ADD INDEX IF NOT EXISTS idx_trace_id trace_id TYPE bloom_filter GRANULARITY 4;

COMMENT ON TABLE kaori_silver.otel_traces IS
    'P15-S9 D8 OTel warm-tier traces. K-19 — every span carries tenant_id. TTL 90 days; cold tier ships to MinIO via Tempo S3 backend.';
