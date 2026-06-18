# `infrastructure/clickhouse/` — ClickHouse cluster

> **Status:** Phase 1.5 P15-S9 D8 scaffold landed (Helm + docker-compose + 3 reference schemas); deploy + dual-write cutover happens P15-S10.
> **Decision:** ADR-0012 — Postgres + ClickHouse polyglot persistence.
> **Used by:** `services/data-pipeline/data_plane/silver/` (Silver tier columnar) + observability (OTel trace storage warm 90 days) + `services/economics/` (NOV time-series) + `services/adoption-intel/` (signal events aggregation).

## Why Phase 1.5, not Phase 1

Phase 1 dùng Postgres only cho mọi workload (giảm ops cost). ClickHouse onboard khi:
- Trace volume > 10M span/tháng (Phase 1.5 estimate)
- Workflow execution metrics > 10K row/giờ
- NOV time-series cần group-by aggregation nhanh

Phase 1 pilot Olist ~10K events → Postgres còn handle dễ.

## Layout

```
infrastructure/clickhouse/
├── README.md                          ← this file
├── docker-compose.yml                 ← landed P15-S9 D8 — 1-node dev with auto-applied schemas
├── users.xml                          ← landed P15-S9 D8 — kaori_ro + kaori_writer dev profiles
├── helm/                              ← landed P15-S9 D8 — Altinity Operator wrapper + ClickHouseInstallation CR
│   ├── Chart.yaml                     ← upstream altinity-clickhouse-operator dep
│   └── values.yaml                    ← 1-shard × 3-replica HA, OTel + ZooKeeper + MinIO backup wiring
├── schemas/                           ← landed P15-S9 D8 — 3 reference Silver tables
│   ├── 00_create_database.sql         ← bootstrap kaori_silver DB
│   ├── 01_silver_pipeline_rows.sql    ← partitioned by tenant_id + month, TTL 365d
│   ├── 02_otel_traces.sql             ← TTL 90d, K-19 service_name + tenant_id mandatory
│   └── 03_nov_time_series.sql         ← SummingMergeTree daily + monthly rollup MV
└── migrations/                        ← (Phase 1.5+) versioned DDL changes for schema evolution
```

To bring up dev locally (alongside the main Kaori stack):

```
docker compose -f docker-compose.yml \
               -f infrastructure/clickhouse/docker-compose.yml up -d
```

The schemas/ files run automatically on first boot via the
``/docker-entrypoint-initdb.d`` mount. Verify with:

```
docker exec kaori-clickhouse clickhouse-client \
    --user kaori_writer --password kaori_writer_dev \
    -q "SHOW TABLES FROM kaori_silver"
```

## Schema conventions (ADR-0013)

- Mọi bảng có `tenant_id` cột đầu tiên + `PARTITION BY tenant_id, toYYYYMM(ts)` + `ORDER BY (tenant_id, ts, ...)`.
- ClickHouse v23 chưa native RLS → service layer query rewriter ép `WHERE tenant_id = $1` khi build query (CI test `P1-MTNT-002` cover).
- Compression: `CODEC(ZSTD(3))` cho cột text dài; `CODEC(Delta, ZSTD)` cho timestamp.
- TTL native: `TTL ts + INTERVAL 90 DAY DELETE` cho trace; `TTL ts + INTERVAL 1 YEAR TO VOLUME 'cold'` cho NOV.

## Operational notes

- **Backup:** ClickHouse Operator backup tới MinIO daily, retention 30 ngày.
- **Replication:** ZooKeeper-coordinated (chia sẻ với Kafka ZK Phase 1, separate Phase 2).
- **Latency target:** P95 < 100ms cho query trên 100M-row table với good ORDER BY hit.

## Migration path từ Postgres

- Bảng v3 hiện đang Postgres (`silver_pipeline_rows`, etc.) → Phase 1.5 dual-write (Postgres + ClickHouse) → Phase 2 đọc từ ClickHouse only, retire Postgres bảng.
- Debezium connector (Postgres WAL → Kafka → ClickHouse) — option 1.
- Application-layer dual write — option 2 (đơn giản hơn cho 1 dev).

## References

- ADR-0012 (`docs/adr/0012-postgres-clickhouse-polyglot-persistence.md`)
- ADR-0013 (`docs/adr/0013-rls-multi-tenancy-formalize-v4.md`) — query rewriter requirement
- `docs/strategic/PIPELINE_UNIFIED.md` Phần 3.6 (Silver storage Apache Parquet) + Stage 8 (Gold)
- `docs/BACKLOG_V4.md` P15-S10 (Silver migration)
- Runbook (Phase 2): `docs/runbooks/clickhouse-replication-lag.md` (TBD)
