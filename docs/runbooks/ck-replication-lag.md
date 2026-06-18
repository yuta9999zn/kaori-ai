# ClickHouse — replication lag / cluster member down

> **Severity:** P1 if read traffic served from a lagging replica returns stale data; P2 if lag <60s and reads tolerated
> **Affects:** Silver tier reads (P15-S9 D8 onwards), OTel trace search (`02_otel_traces`), NOV time-series (`03_nov_time_series`). Phase 1+1.5 still has Postgres dual-write so this isn't customer-facing yet — degrades the tracing + analytics view.
> **First responder:** anh
> **Related:** ADR-0012 (Medallion → ClickHouse Silver), `infrastructure/clickhouse/`, P15-S10 D8 cutover plan

## Symptoms

- Grafana dashboard `ck_replicated_table_lag_seconds` > 60 for any table.
- `system.replication_queue` shows entries with `last_exception` populated.
- Alert: `ClickHouseReplicaIsReadOnly` — a replica entered read-only mode (Zookeeper / Keeper connection lost or replication stalled).
- Query against ClickHouse returns rows that don't match the expected count from Postgres dual-write tally (P15-S9 D8 dual-write window).
- Operator probe: `clickhouse-client --query "SELECT count() FROM silver.silver_pipeline_rows WHERE _partition_id = 'YYYYMM'"` returns a number lower than the same query on a different replica.

## Quick triage (≤ 60 seconds)

- [ ] **How many replicas are healthy?** `kubectl -n clickhouse get pods` (prod) or `docker compose ps clickhouse` (dev). 3-node Helm chart per P15-S9 D8 — losing 1 = degraded; losing 2 = quorum loss → reads still served, writes paused.
- [ ] **Is Zookeeper / Keeper healthy?** ClickHouse replication coordinates via ZooKeeper (or built-in Keeper). If ZK is down, replication stalls cluster-wide. Check ZK before assuming a CH issue.
- [ ] **Is this from D8 dual-write only?** P15-S9 ships dual-write to Postgres + ClickHouse. If lag is showing only on freshly-written rows, the dual-write writer is fine but CH replication is the issue.
- [ ] **Did anh deploy a new schema migration recently?** ALTER TABLE on a Replicated table requires Zookeeper coordination — slow or partial schema applies cause one replica to lag.

## Diagnosis

```bash
# 1. Cluster member states.
docker exec kaori-clickhouse-1 clickhouse-client --query \
  "SELECT host_name, host_address, port, is_local, replica_num, errors_count, slowdowns_count
   FROM system.clusters WHERE cluster='kaori_silver'"

# 2. Replicated table lag per replica per table.
docker exec kaori-clickhouse-1 clickhouse-client --query \
  "SELECT database, table, replica_name, queue_size, log_max_index, log_pointer,
          absolute_delay, total_replicas, active_replicas
   FROM system.replicas
   WHERE database = 'silver'
   FORMAT Vertical"
# absolute_delay > 60 = real lag; queue_size growing = backlog

# 3. Replication queue inspection — what's stuck?
docker exec kaori-clickhouse-1 clickhouse-client --query \
  "SELECT database, table, type, num_tries, last_exception, create_time
   FROM system.replication_queue
   WHERE last_exception != ''
   LIMIT 20
   FORMAT Vertical"

# 4. Zookeeper / Keeper health.
# Built-in Keeper:
docker exec kaori-clickhouse-keeper-1 echo ruok | nc localhost 9181
# Expect: imok

# External Zookeeper:
docker exec kaori-zookeeper-1 echo srvr | nc localhost 2181
# Expect: lines with 'Mode: leader' or 'Mode: follower'

# 5. Recent INSERT volume — was there a write spike?
docker exec kaori-clickhouse-1 clickhouse-client --query \
  "SELECT toStartOfMinute(event_time) AS m, count(), sum(rows)
   FROM system.query_log
   WHERE query_kind='Insert' AND event_time > now() - INTERVAL 1 HOUR
   GROUP BY m ORDER BY m DESC LIMIT 30"

# 6. Per-replica disk usage — full disk = read-only mode.
docker exec kaori-clickhouse-1 df -h /var/lib/clickhouse
```

## Mitigation (fastest path)

1. **Single replica down + 2 healthy** — cluster keeps serving reads + writes from healthy replicas. Fix the down replica:

   ```bash
   # Restart the pod / container; replication will catch up automatically.
   docker compose restart clickhouse-2
   # Watch absolute_delay decrease; expect a few minutes per GB of backlog.
   docker exec kaori-clickhouse-1 clickhouse-client --query \
     "SELECT replica_name, absolute_delay FROM system.replicas WHERE table='silver_pipeline_rows'"
   ```

2. **Replica in read-only mode (queue stuck)** — usually because of a `MergeTreePartChecksumsMismatchException` or similar. Force re-fetch the affected part from a healthy replica:

   ```bash
   # First identify the bad part from system.replication_queue last_exception.
   docker exec kaori-clickhouse-1 clickhouse-client --query \
     "SYSTEM RESTART REPLICA silver.silver_pipeline_rows ON CLUSTER kaori_silver"
   ```

3. **Zookeeper / Keeper down** — replication halts entirely until ZK is back. Recover ZK first:

   ```bash
   docker compose restart clickhouse-keeper
   # CH replicas reconnect automatically; queue resumes drain.
   ```

4. **Disk full on a replica** — emergency cleanup:

   ```bash
   docker exec kaori-clickhouse-1 clickhouse-client --query \
     "OPTIMIZE TABLE silver.silver_pipeline_rows FINAL"
   # If still tight, drop oldest partition (verify TTL config first):
   docker exec kaori-clickhouse-1 clickhouse-client --query \
     "ALTER TABLE silver.silver_pipeline_rows DROP PARTITION '202504'"
   ```

5. **Quorum loss (2/3 down)** — writes pause to preserve consistency. Reads still served from the surviving replica. Get one of the down replicas back ASAP; do NOT bypass replication by writing directly to a local table (creates split-brain).

6. **Customer-facing impact** — Phase 1.5 D8 dual-write means Postgres still has the data. If ClickHouse is unrecoverable in <30 min and reads are tenant-facing, route silver-tier read traffic back to Postgres temporarily via the feature flag `tenant_settings.silver_read_source = "postgres"`. This is the fallback the dual-write window is designed to cover.

## Permanent fix

- **Helm chart resource sizing** — P15-S9 D8 ships conservative replica resource limits. Production (Phase 2) needs CPU/memory tuning per workload. Track in `infrastructure/clickhouse/helm/values.yaml` overrides per env.
- **Disk quota alerts** — Prometheus rule: `ck_disk_usage_percent > 80` for 30 min. Add when D8 cutover lands.
- **Schema change procedure** — ALTER TABLE on Replicated tables must use `ON CLUSTER` + wait for completion before next migration. Document in `infrastructure/clickhouse/README.md`.
- **Backup cadence** — `clickhouse-backup` (or equivalent) nightly to MinIO `s3://kaori-backups/clickhouse/`. Phase 1.5 = no backup (dual-write Postgres is the safety net); Phase 2 cutover = daily backups required.
- **Replication factor decision** — 3 replicas per the Helm default. Phase 2 may need to drop to 2 in non-critical envs (cost) or push to 5 in production (resilience). Track decision in ADR-0012 update.

## Postmortem hooks

If replication lag spikes >2× in a month:

- Was it always the same replica? Indicates a host-level issue (slow disk, noisy neighbour pod).
- Time-to-detect — alert thresholds tuned right? `> 60s lag for 5 min` is the suggested rule but may need adjustment per workload.
- Did the dual-write fallback fire (read traffic routed back to Postgres)? Tells us whether the mitigation playbook is well-rehearsed.
- Track INSERT volume vs replication catch-up rate — if catch-up consistently slower than write rate, the cluster is undersized for the workload.
