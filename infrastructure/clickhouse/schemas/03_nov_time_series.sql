-- NOV time-series — long-form ROI metrics for trend analysis.
--
-- Phase 1.5 P15-S9 D8 — complement to nov_monthly_digests (Postgres,
-- migration 043). The Postgres digest carries one row per (enterprise,
-- month); this ClickHouse table carries one row per (enterprise,
-- workflow_id, day) so the dashboard can render daily-resolution
-- trend charts without a heavy aggregate over the digest table.
--
-- Why a separate table:
--   * Daily granularity over 24 months = 24 × 30 × N_workflows rows
--     per tenant. Postgres BTree handles it but at noticeable cost
--     when 100 tenants × 50 workflows = 1.4M rows/year/tenant for
--     the dashboard tile read.
--   * ClickHouse SummingMergeTree on (enterprise, workflow_id, day)
--     auto-rolls up the daily writes into one row per partition tail
--     so the dashboard query reads one row per day with index access.
--
-- Write pattern
-- =============
-- The NOV monthly workflow (workflow_runtime/workflows/nov_monthly_
-- digest.py) writes one row per (workflow, day) for the closing
-- month. SummingMergeTree merges per-tenant inserts so a re-run on
-- the same day idempotently aggregates instead of double-counting.

CREATE TABLE IF NOT EXISTS kaori_silver.nov_time_series
(
    enterprise_id    UUID,
    workflow_id      String,
    day              Date,

    -- Metrics — Decimal(14, 4) per K-9. SummingMergeTree sums these
    -- on merge so a re-write idempotently aggregates.
    revenue_vnd      Decimal(14, 4),
    cost_vnd         Decimal(14, 4),
    nov_vnd          Decimal(14, 4),

    -- Cost breakdown for drill-down (4 components per cost.py).
    people_cost_vnd       Decimal(14, 4),
    ai_cost_vnd           Decimal(14, 4),
    infra_cost_vnd        Decimal(14, 4),
    integration_cost_vnd  Decimal(14, 4),

    -- Counters — useful for "workflow ran N times today" tile.
    runs_count       UInt32,
    failures_count   UInt32
)
ENGINE = ReplicatedSummingMergeTree(
    '/clickhouse/tables/{shard}/nov_time_series',
    '{replica}',
    -- SummingMergeTree merges rows with the same ORDER BY key — list
    -- the metric columns explicitly so the engine knows what to sum.
    (revenue_vnd, cost_vnd, nov_vnd,
     people_cost_vnd, ai_cost_vnd, infra_cost_vnd, integration_cost_vnd,
     runs_count, failures_count)
)
PARTITION BY (enterprise_id, toYYYYMM(day))
ORDER BY (enterprise_id, workflow_id, day)
TTL day + INTERVAL 730 DAY DELETE  -- 2-year retention; archive Phase 2
SETTINGS index_granularity = 8192;

-- Negative-NOV alert sweep — partial materialised view aggregates
-- daily into a per-month bucket so the ai-orchestrator alert job
-- queries one row per (tenant, month) instead of 30.
CREATE MATERIALIZED VIEW IF NOT EXISTS kaori_silver.nov_monthly_rollup_mv
ENGINE = ReplicatedSummingMergeTree(
    '/clickhouse/tables/{shard}/nov_monthly_rollup_mv',
    '{replica}',
    (revenue_vnd, cost_vnd, nov_vnd, runs_count, failures_count)
)
PARTITION BY (enterprise_id, toYYYYMM(month_start))
ORDER BY (enterprise_id, workflow_id, month_start)
AS SELECT
    enterprise_id,
    workflow_id,
    toStartOfMonth(day) AS month_start,
    sum(revenue_vnd)    AS revenue_vnd,
    sum(cost_vnd)       AS cost_vnd,
    sum(nov_vnd)        AS nov_vnd,
    sum(runs_count)     AS runs_count,
    sum(failures_count) AS failures_count
FROM kaori_silver.nov_time_series
GROUP BY enterprise_id, workflow_id, toStartOfMonth(day);

COMMENT ON TABLE kaori_silver.nov_time_series IS
    'P15-S9 D8 NOV daily time-series. SummingMergeTree merges idempotently. Companion to Postgres nov_monthly_digests for dashboard daily-resolution trend.';
