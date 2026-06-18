# Phase 2.6 Defer Queue — Infrastructure-gated items

> 2026-05-19 — three items from the Phase 2.6 P1/P2 plan need infrastructure em không có locally (Temporal cluster / Kafka+Debezium / ClickHouse / Flink ksqlDB). Em ship the contract / migration / runbook skeleton but full e2e wiring lands when infra is provisioned.

## Status

| Item | Code shipped | Infra blocker | Runbook |
|---|---|---|---|
| **P1.2 Worker pool isolation** | ✅ `queue_routing.py` + 24 tests | Temporal multi-worker K8s manifests | `docs/runbooks/workflow-execution-enable.md` §3c (extend with multi-queue commands) |
| **P1.3 Gold incremental** | ⏳ designed only | Kafka + Debezium CDC + ClickHouse cluster | TBD |
| **P2.1 ClickHouse cutover** | ⏳ designed only | ClickHouse 3-node cluster (already in `infrastructure/clickhouse/`) | TBD |
| **P2.4 Streaming pipeline** | ⏳ designed only | Flink or ksqlDB cluster | TBD |

P1.2 routing config + tests **ship today**. Activation requires only env config change (multi-worker deploy). Other three are pure design until infra provisioned.

---

## P1.2 Worker pool isolation — activation runbook (extend §3c)

### Step 1 — Set TEMPORAL_TASK_QUEUE per worker pool

3 K8s deployments, each pulling the same image with different env:

```yaml
# kaori-worker-critical-finance
env:
  TEMPORAL_ENABLE_WORKER: "true"
  TEMPORAL_TASK_QUEUE: "kaori-critical-finance"
  TEMPORAL_NAMESPACE: "default"
replicas: 2  # smaller pool, higher tier hardware

# kaori-worker-default
env:
  TEMPORAL_ENABLE_WORKER: "true"
  TEMPORAL_TASK_QUEUE: "kaori-default"
replicas: 4

# kaori-worker-low-priority
env:
  TEMPORAL_ENABLE_WORKER: "true"
  TEMPORAL_TASK_QUEUE: "kaori-low-priority"
replicas: 2  # CPU-bound batch work
```

### Step 2 — Verify routing via test workflow

```bash
# Trigger a finance approval workflow + verify it lands on critical queue
curl -X POST ".../workflows/{id}/run" -H "X-Enterprise-ID: <uuid>" \
     -d '{"input_data": {"amount": 100000000}}'

# Check Temporal UI: task queue for the run should be kaori-critical-finance
# not kaori-default.
```

### Step 3 — Hot/cold tiering metrics

Prometheus alerts (post-deploy):

```yaml
- alert: KaoriCriticalQueueLag
  expr: temporal_task_queue_oldest_pending_seconds{queue="kaori-critical-finance"} > 30
  for: 1m
  severity: critical

- alert: KaoriLowPriorityQueueStarved
  expr: temporal_task_queue_oldest_pending_seconds{queue="kaori-low-priority"} > 3600
  for: 30m
  severity: warning
```

---

## P1.3 Gold incremental — design sketch

**Goal:** replace `REFRESH MATERIALIZED VIEW` with append-only delta aggregates.

### Data flow

```
silver_transactions (insert)
  ↓ Debezium CDC
kaori.cdc.silver_transactions (Kafka)
  ↓ Stream processor (Flink/ksqlDB)
gold_incremental_aggregates (append-only)
  ↓ Materialized view refresh (CONCURRENTLY)
gold_features (existing read path)
```

### New tables (mig 097 — design, not shipped):

```sql
CREATE TABLE gold_incremental_aggregates (
    enterprise_id  UUID,
    aggregate_key  VARCHAR(64),       -- 'revenue_by_channel:online:2026-05'
    aggregate_at   TIMESTAMPTZ,
    delta          NUMERIC(14, 4),
    source_event_id UUID,
    PRIMARY KEY (enterprise_id, aggregate_key, aggregate_at)
);
```

Reader: a periodic `SELECT enterprise_id, aggregate_key, SUM(delta)` rebuilds the gold MV in seconds (vs hours full refresh).

### Cutover plan

1. Provision Kafka + Debezium connector (`postgres-source-connector.json`).
2. Deploy Flink or ksqlDB job.
3. Land mig 097 + start dual-write (existing MV refresh + new incremental).
4. Verify totals match for 7 days.
5. Cut reads to incremental, keep MV refresh as safety for 30 days.
6. Drop MV refresh.

---

## P2.1 ClickHouse cutover — design sketch

ClickHouse 3-node cluster spec already in `infrastructure/clickhouse/` (P15-S10 defer). Activation steps:

1. Helm install per existing chart.
2. Create per-tenant database `tenant_<hash>` with `MergeTree` engine.
3. Build CDC pipeline: `silver_*` (Postgres) → ClickHouse via Debezium + clickhouse-sinker.
4. Migrate read path for `gold_aggregates` to ClickHouse-backed queries.
5. Keep Postgres `gold_features` as failover for 30 days.

Performance target: p99 < 50ms for per-tenant rollups (vs current Postgres MV multi-minute refresh under load).

---

## P2.4 Streaming pipeline — design sketch

For real-time NOV signals + adoption signals + fraud detection (Phase 3 use cases).

Stack: Kafka (already shipped) + Flink (new).

Topics map:

```
kaori.events.transactions   (Bronze tail, immutable)
   → Flink window: 1h tumbling
   → kaori.aggregates.txn_per_hour
   → gold_incremental_aggregates write

kaori.events.adoption.raw   (existing P15-S9)
   → Flink stateful: per-tenant health score running computation
   → kaori.aggregates.adoption.snapshot
   → adoption_health_snapshots write (replaces current cron)
```

Watermarking: `event_time = transaction.created_at`, allowed lateness = 5min. Late events route to `kaori.events.late` for manual reconciliation.

---

## Why defer

All three items below need cluster infrastructure em không có local. Implementing without cluster = stub code that gives false confidence. The right move is:

1. Ship P1.2 + P2.2 + P2.3 + P0.* + P1.1 + P1.4 today — **code-only items that need NO new infra**.
2. Document P1.3 + P2.1 + P2.4 with explicit migration + runbook so when infra lands, implementation is mechanical not exploratory.
3. The 3 items above CAN be implemented in parallel with infra provisioning.

Total: 8 of 12 Phase 2.6 items shipped today. 3 deferred with explicit design. 1 partial (P1.2 — config ships, deployment requires K8s).
