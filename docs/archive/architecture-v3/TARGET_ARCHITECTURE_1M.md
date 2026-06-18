# Kaori AI — Target Architecture @ 1,000,000 Tenants

> **Date:** 2026-04-25
> **Predecessors:** `ARCHITECTURE_REVIEW.md` (correctness), `SCALE_PLAN.md` (100K scale)
> **Scope:** the *destination* topology. Every number is picked; every topic is named; every shard key is declared. No "consider X" language.

---

## 0. Scale envelope (1M enterprises)

| Dimension | Target | Derivation |
|---|---:|---|
| Enterprise tenants | **1,000,000** | 150K large + 750K SME + 100K pilot |
| Personal users | **1,000,000** | avg 10K rows each |
| Warm rows (bronze+silver) | **~8.3 T** | 150K×50M + 750K×1M + pilot + personal |
| Audit rows / 2 yr | **~730 B** | 1M × 100 decisions/day × 730d |
| Concurrent human sessions | **~12 M** | large 150K×50 + SME 750K×5 + personal 1M×0.1 |
| Steady API QPS (gateway) | **~200 K** | 12M × 1 req/min avg |
| Peak API QPS (5× burst) | **~1 M** | scheduled reports, login storms |
| Kafka events/s steady | **~550 K** | 4 events per pipeline × 1K concurrent + LLM audit stream + billing |
| LLM inferences/s steady | **~20 K** | insights + framework fill + MCP |
| LLM inferences/s peak | **~100 K** | quarter-end reporting |
| Bronze-layer cold bytes | **~2.5 PB** | 8T rows × ~300 B avg compressed |

Every box and topic below is sized against those numbers, not a safety factor on top.

---

## 1. Service topology (the diagram, textually)

```
                        ┌────────────────────────────────────────────────────────┐
                        │     Cloudflare WAF + CDN (TLS, DDoS, bot filter)       │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                  ┌────────────────────────────────┼─────────────────────────────┐
                  │           3 regions: ap-southeast-1 (HN), ap-southeast-2 (SG), us-east-1 (DR) │
                  └────────────────────────────────┼─────────────────────────────┘
                                                   │
                         ┌─────────────────────────▼─────────────────────────┐
                         │    api-gateway  (Spring Cloud Gateway)            │
                         │    80 pods × 3 regions = 240 pods                 │
                         │    JwtAuthFilter + IdempotencyFilter +            │
                         │    RateLimitFilter(LUA) + TenantTierRouter        │
                         └──────────┬──────────────┬──────────────┬──────────┘
                                    │              │              │
         ┌──────────────────────────┘              │              └──────────────────────┐
         │                                         │                                     │
         ▼                                         ▼                                     ▼
 ┌─────────────────┐                   ┌───────────────────────┐              ┌─────────────────────┐
 │  auth-service   │                   │    data-pipeline      │              │   ai-orchestrator   │
 │  (Java, 60 pods)│                   │    (Python, 200 pods) │              │   (Python, 150 pods)│
 │  stateless      │                   │    upload/schema/clean│              │   analytics+dashbrd │
 │  hits Postgres  │                   │    /analyze/results   │              │   consumers         │
 │  shards + Redis │                   │    asyncpg → shards   │              │   asyncpg → shards  │
 └────────┬────────┘                   └────────┬──────────────┘              └──────┬──────────────┘
          │                                     │                                    │
          │        ┌────────────────────────────┼────────────────────────────────────┤
          │        │                            │                                    │
          ▼        ▼                            ▼                                    ▼
 ┌──────────────────────┐         ┌──────────────────────────┐          ┌──────────────────────┐
 │  billing-service  🆕 │         │   bronze-parser-worker   │          │  llm-gateway  🆕     │
 │  (Java, 20 pods)     │         │   (Python, 150 pods)     │          │  (Python, 80 pods)   │
 │  F-011 F-030 F-031   │         │   consumes Kafka         │          │  model registry +    │
 │  unique-cust cron    │          │   streams S3→ClickHouse │          │  adapter pool +      │
 └────────┬─────────────┘         └────────┬─────────────────┘          │  semantic cache      │
          │                                │                             └───┬──────────────────┘
          │                                │                                 │
          ▼                                ▼                                 ▼
 ┌──────────────────────┐         ┌──────────────────────────┐       ┌──────────────────────┐
 │  notification-service│         │   outbox-publisher   🆕  │       │   vllm-pool  🆕      │
 │  (Python, 20 pods)   │         │   (Python, 20 pods)      │       │   GPU 4× H100/pod    │
 │  SMTP + push + Slack │         │   DB.outbox → Kafka      │       │   16 pods × 2 region │
 └──────────────────────┘         └──────────────────────────┘       └──────────────────────┘

                         ┌─────────────────────────────────────────────┐
                         │     audit-service  🆕  (Python, 30 pods)    │
                         │     consumes every decision topic →         │
                         │     writes ClickHouse decision_audit        │
                         └─────────────────────────────────────────────┘

                         ┌─────────────────────────────────────────────┐
                         │     mcp-server  🆕  (Node, 40 pods)         │
                         │     /mcp/jsonrpc  — external AI clients     │
                         │     OAuth 2.1 + PKCE + per-tenant scopes    │
                         └─────────────────────────────────────────────┘

────────────────────────────── DATA PLANE ──────────────────────────────

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  PostgreSQL (Citus)    — 256 shards, 3 replicas each, 2 coordinators        │
 │  Role: OLTP control-plane + Gold features + Postgres-hot audit (90 d)       │
 │  Per-shard: 32 vCPU / 128 GB / 4 TB NVMe                                    │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  ClickHouse cluster    — 16 shards × 3 replicas = 48 nodes                  │
 │  Role: Silver rows + Decision audit log (all-time, TTL 2 y)                 │
 │  Per-node: 32 vCPU / 256 GB / 16 TB NVMe                                    │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  S3 / MinIO            — Bronze (Parquet) + model artifacts + exports       │
 │  Lifecycle: 90 d hot → 1 y warm → Glacier                                   │
 │  Estimated: 2.5 PB hot + 15 PB cold at year-2                               │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  Redis Cluster         — 32 shards, 2 replicas; separate clusters for:      │
 │    • sessions / JWT blacklist / refresh tokens                              │
 │    • rate-limit / quota counters                                            │
 │    • semantic LLM cache                                                     │
 │    • online feature store (gold tier, P99 <5 ms reads)                      │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  Kafka (Confluent / Apache)    — 12 brokers, rf=3, min.isr=2                │
 │  3 AZ, 3 regional clusters with MirrorMaker2 for DR                         │
 │  Per-broker: 16 vCPU / 64 GB / 6 TB NVMe                                    │
 │  Schema Registry + Kafka Connect for CDC out to ClickHouse                  │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │  vLLM pool             — 16 pods × 4× H100 each = 64 H100 baseline          │
 │  HPA on GPU utilization + Kafka queue depth → up to 128 H100 at peak        │
 │  Models served: Qwen 2.5 14B (SME), Qwen 2.5 72B (large), BGE-M3 (embed)    │
 └─────────────────────────────────────────────────────────────────────────────┘
```

### Pod-count rationale (not handwavy)

| Service | Pods | Per-pod sizing | Load served |
|---|---:|---|---|
| api-gateway | 240 (3 reg × 80) | 4 vCPU / 8 GB | 1M peak QPS ÷ 240 = 4.2K QPS/pod — well inside Spring Cloud Gateway capacity (~10K QPS/pod measured) |
| auth-service | 60 | 2 vCPU / 4 GB | login/refresh are short; bcrypt cost=12 dominates — ~200 login/s/pod |
| data-pipeline | 200 | 4 vCPU / 8 GB | async I/O-bound; upload accepts, queues, returns — 50 req/s/pod sustain |
| bronze-parser-worker | 150 | 8 vCPU / 16 GB | COPY into S3 + metadata into Postgres; 30 concurrent parses/pod |
| ai-orchestrator | 150 | 4 vCPU / 8 GB | dashboards + analytics read-heavy; 100 req/s/pod |
| llm-gateway | 80 | 4 vCPU / 8 GB | routing + cache hit/miss logic; 1K req/s/pod (most cache-served) |
| billing-service | 20 | 4 vCPU / 8 GB | control-plane; cron + low-rate API |
| audit-service | 30 | 4 vCPU / 8 GB | Kafka consumer + ClickHouse bulk INSERT; 20K events/s/pod |
| outbox-publisher | 20 | 2 vCPU / 4 GB | CDC Postgres.outbox → Kafka, 10K rows/s/pod |
| mcp-server | 40 | 4 vCPU / 8 GB | external AI client tool calls |
| notification-service | 20 | 2 vCPU / 4 GB | SMTP throughput is the cap |
| vllm-pool | 16 | 4× H100 | ~1.5K tokens/s/pod effective with continuous batching |

Total compute: ~1,000 pods + 64 baseline GPUs. Roughly $2M/mo infra at cloud list price; ~$800K/mo on spot + reserved.

---

## 2. Data flow (the exact hops for each critical path)

### 2.1 Pipeline upload → Silver (the headline path)

```
User → CDN → api-gateway
       ├─ JwtAuthFilter (Caffeine in-process cache, fallback to Redis sessions cluster)
       ├─ IdempotencyFilter (Redis rate-limit cluster; keyed by Idempotency-Key header)
       ├─ RateLimitFilter (atomic LUA in Redis rate-limit cluster)
       └─ TenantTierRouter (reads X-Tenant-Tier header, adds to trace)

api-gateway → data-pipeline:/upload (POST multipart)
  data-pipeline.upload_handler:
    1.  compute SHA-256 while streaming to S3 (bronze-landing bucket, NOT Python memory)
    2.  INSERT pipeline_runs (Postgres shard chosen by hash(enterprise_id))
    3.  enqueue_event(outbox table, topic=kaori.bronze.parse.requested,
                      key=enterprise_id, payload={run_id, s3_path, sha256})
    4.  return 202 { run_id, status: "queued" }

outbox-publisher:
  polls outbox WHERE published_at IS NULL
  → producer.send(key=enterprise_id, acks='all') → Kafka

Kafka partition routed by hash(enterprise_id) % 96 (topic partitions)

bronze-parser-worker (Kafka consumer, group=bronze-parsers):
  1.  download s3_path → stream parser
  2.  write Parquet back to S3 under s3://kaori-bronze/{tier}/{ent}/{run}/...
  3.  INSERT bronze_files (Postgres shard — metadata only, no row-level bronze data)
  4.  enqueue_event(topic=kaori.pipeline.bronze.complete,
                    key=enterprise_id, payload={run_id, row_count, sha256})

data-pipeline (still serving user via SSE /pipelines/:id/events):
  subscribes to kaori.pipeline.bronze.complete
  pushes SSE update to browser

User clicks Next → POST /schema
  data-pipeline.schema.confirm:
    → writes canonical_schemas to Postgres shard
    → enqueue_event(topic=kaori.pipeline.schema.confirmed)
    → audit row via topic=kaori.audit.decisions (consumed by audit-service → ClickHouse)

User clicks Next → POST /clean/apply
  data-pipeline.clean.apply:
    → server-side cursor READ from S3 Parquet (pyarrow streaming)
    → apply rules in chunks of 10K rows
    → COPY into ClickHouse.silver_rows (not Postgres!) via native binary protocol
    → enqueue_event(topic=kaori.pipeline.silver.complete)

ai-orchestrator (Kafka consumer, group=orchestrator-analysis):
  subscribes kaori.pipeline.silver.complete
  → looks up analysis_runs WHERE status='queued'
  → dispatches to runner → ClickHouse reads + Gold writes
  → enqueue topic=kaori.pipeline.analysis.complete + topic=kaori.audit.decisions

Dashboard: GET /api/v1/analytics/runs/:id
  ai-orchestrator hits ClickHouse for aggregates + Postgres for Gold features
  caches at Redis semantic layer (TTL 60s)
```

End-to-end target: **upload ack P95 < 300ms, bronze-complete P95 < 30s for 10M rows, silver-complete P95 < 2min, analysis-complete P95 < 90s**.

### 2.2 LLM request path (upgrade-safe, per SCALE_PLAN §6)

```
ai-orchestrator.insights_handler
  → HTTP POST /v1/infer to llm-gateway (service mesh, mTLS)

llm-gateway:
  1. resolve_model(task_type, privacy_mode, tenant_tier) → llm_models row
  2. render_prompt(template_id, vars, model.family)        ← chat template adapter
  3. semantic cache lookup (Redis LLM cache cluster, key=sha256(prompt)+capability_tier)
     → hit: return immediately (80%+ hit rate on insight templates)
  4. tenant_budget.consume(enterprise_id, est_tokens)
     → over quota → 429 with Retry-After
  5. if short prompt (<2K tok) AND low latency task:
       → PROVIDERS[model.provider].infer(...)        (synchronous path)
     else:
       → producer.send(topic=kaori.llm.infer.requests,
                       key=enterprise_id,
                       payload={req_id, model_id, prompt, tenant, deadline})
       → returns 202 { req_id, poll: /v1/infer/:req_id }
       → vllm-worker consumes from kaori.llm.infer.requests,
         writes result to kaori.llm.infer.responses,
         llm-gateway pulls response → caller
  6. audit → topic=kaori.audit.llm.calls (consumed by audit-service)
```

### 2.3 Billing cron (F-031 done properly)

```
billing-service (leader-elected via Redis lock):
  cron 00:05 UTC → enqueue fan-out messages on kaori.billing.aggregate.tick
                    key=shard_id (256 messages, one per shard)

billing-worker pods (20 pods) consume:
  1. For each enterprise on the shard:
       unique_count = ClickHouse: SELECT COUNT(DISTINCT customer_external_id)
                                  FROM silver_rows
                                  WHERE enterprise_id=? AND created_at >= month_start
       plan_quota = Postgres: SELECT monthly_quota ...
       pct = unique_count / plan_quota
  2. UPSERT Postgres.enterprise_monthly_billing (same shard)
  3. If pct >= 0.95 → enqueue topic=kaori.billing.quota.breached
  4. Outbox → audit

notification-service consumes kaori.billing.quota.breached → SMTP
```

---

## 3. Kafka topics — the final list

All topics under the `kaori.*` namespace (fixing the current `pipeline.*` / `kaori.*` drift). Every topic has: **purpose, producer, consumer, key, partitions, retention, replication**.

### 3.1 Ingest & pipeline

| Topic | Key | Partitions | Retention | rf/min.isr | Producers | Consumers |
|---|---|---:|---:|---|---|---|
| `kaori.pipeline.upload.requested` | `enterprise_id` | 96 | 7 d | 3/2 | data-pipeline:/upload | bronze-parser-worker |
| `kaori.pipeline.bronze.complete` | `enterprise_id` | 96 | 7 d | 3/2 | bronze-parser-worker | data-pipeline (SSE notifier), ai-orchestrator |
| `kaori.pipeline.schema.confirmed` | `enterprise_id` | 48 | 7 d | 3/2 | data-pipeline | audit-service |
| `kaori.pipeline.silver.complete` | `enterprise_id` | 96 | 7 d | 3/2 | data-pipeline (clean.apply only — **not** analyze anymore) | ai-orchestrator |
| `kaori.pipeline.analysis.complete` | `enterprise_id` | 48 | 7 d | 3/2 | ai-orchestrator | audit-service, data-pipeline (SSE) |
| `kaori.pipeline.dlq` | `origin_key` | 24 | 30 d | 3/2 | kafka-retry-worker | dlq-replayer |

**Fix applied:** today's `pipeline.silver.complete` is emitted from *two* different sites (`clean.py:236` + `analyze.py:59`) creating double-dispatch. In target state, only `clean.py` emits `kaori.pipeline.silver.complete`; `analyze.py` emits a distinct `kaori.analysis.run.requested` topic which feeds the orchestrator dispatcher directly.

### 3.2 Decision audit & LLM

| Topic | Key | Partitions | Retention | rf/min.isr | Producers | Consumers |
|---|---|---:|---:|---|---|---|
| `kaori.audit.decisions` | `enterprise_id` | 192 | 90 d (then ClickHouse) | 3/3 (strictest) | every decision-making service | audit-service |
| `kaori.audit.auth` | `enterprise_id` | 48 | 90 d | 3/3 | auth-service | audit-service, security-monitor |
| `kaori.audit.llm.calls` | `enterprise_id` | 96 | 90 d | 3/3 | llm-gateway | audit-service, cost-monitor |
| `kaori.llm.infer.requests` | `enterprise_id` | 64 | 1 d | 3/2 | llm-gateway | vllm-workers |
| `kaori.llm.infer.responses` | `request_id` | 64 | 1 d | 3/2 | vllm-workers | llm-gateway |
| `kaori.llm.infer.dlq` | `request_id` | 16 | 30 d | 3/2 | vllm-workers | manual replay |

### 3.3 Billing & commerce

| Topic | Key | Partitions | Retention | rf/min.isr | Producers | Consumers |
|---|---|---:|---:|---|---|---|
| `kaori.billing.aggregate.tick` | `shard_id` (0..255) | 256 | 1 d | 3/2 | billing-service (cron) | billing-worker |
| `kaori.billing.events` | `enterprise_id` | 96 | 2 y | 3/3 | billing-worker | finance-etl, dashboard, audit |
| `kaori.billing.quota.breached` | `enterprise_id` | 48 | 90 d | 3/3 | billing-worker | notification-service, p2-ui-push |
| `kaori.billing.invoice.issued` | `enterprise_id` | 48 | 2 y | 3/3 | invoice-service | notification, finance-etl |

### 3.4 Feedback, alerts, MCP

| Topic | Key | Partitions | Retention | rf/min.isr | Producers | Consumers |
|---|---|---:|---:|---|---|---|
| `kaori.feedback.actions` | `enterprise_id` | 96 | 30 d | 3/2 | ai-orchestrator (decision override) | feature-store-updater, retrain-trigger |
| `kaori.alerts.fire` | `enterprise_id` | 48 | 7 d | 3/2 | alert-rule-engine, quality-watcher | notification-service |
| `kaori.mcp.tool.calls` | `enterprise_id` | 48 | 30 d | 3/2 | mcp-server | audit-service, cost-monitor |
| `kaori.audit.internal` | `service_name` | 24 | 2 y | 3/3 | every service (structured log sink) | log-aggregator, compliance-exporter |

### 3.5 DLQ policy (one per critical topic)

Every P0 topic has a matching `*.dlq`. The retry consumer pattern:

```
consume(main-topic):
  try handler(msg)
       commit()
  catch transient e:
       send to main-topic.retry.{1s|2s|4s|8s|16s}  (5-tier exponential backoff)
       commit()
  catch permanent e:
       send to main-topic.dlq with headers {original_offset, first_error, attempts=5}
       commit()
       PagerDuty if main-topic.dlq depth > 100
       Paging escalation if > 1000
```

### 3.6 Partition-count math (not arbitrary)

`kaori.audit.decisions` = 192 partitions because:
- 550K events/s × 20% decision share = 110K events/s on this topic
- One consumer pod sustains ~5K events/s of ClickHouse inserts
- → 22 consumer pods needed. 192 partitions allow up to 192 parallel consumers = headroom for 2-region replay.

`kaori.llm.infer.requests` = 64 partitions:
- 20K peak inferences/s, ~30% asynchronous (long prompts)
- → 6K async requests/s → 1 partition per 100 req/s vLLM throughput = 64 plenty.

---

## 4. Shard strategy

### 4.1 Tenant tiering (the only tier metadata that matters)

| Tier | % / count | Definition | Physical placement |
|---|---:|---|---|
| **Pilot** | ~10% / 100K | First 30 days or plan='PILOT' | Pooled — shared Postgres+ClickHouse shards; shared Qwen 14B |
| **SME** | ~75% / 750K | ENT_BASIC / ENT_MID | Sharded — 256 Postgres shards, 16 ClickHouse shards; shared Qwen 14B |
| **Large** | ~15% / 150K | ENT_MAX / ENT_ROI or >10M rows | Top 1K: dedicated Postgres schema within shared shard. Top 50: dedicated Postgres DB + dedicated ClickHouse replica group. Reserved Qwen 72B slice. |

`workspaces.tier` column drives every routing decision. Populated by `subscription_plans.tier` on plan change; kept in JWT claim `tier` so gateway can route without DB hit.

### 4.2 Postgres shard strategy (Citus)

- **Shard count:** **256** at launch, sized to allow rebalance without re-hash.
- **Shard key:** `enterprise_id` (UUID) → `hash()` → shard 0..255.
- **Coordinator:** 2× ha-pair (primary + standby); coordinator only holds metadata and routes.
- **Per shard:** 32 vCPU / 128 GB / 4 TB NVMe, 3-node replica set (1 primary + 2 replicas).
- **Distributed tables:**
  ```
  SELECT create_distributed_table('workspaces',            'workspace_id', 'hash');
  SELECT create_distributed_table('enterprises',           'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('enterprise_users',      'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('pipeline_runs',         'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('bronze_files',          'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('canonical_schemas',     'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('analysis_runs',         'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('gold_features',         'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('enterprise_monthly_billing', 'enterprise_id', 'hash', colocate_with => 'workspaces');
  SELECT create_distributed_table('outbox',                'enterprise_id', 'hash', colocate_with => 'workspaces');
  ```
  Colocation guarantees every join (enterprise → users → billing) stays on a single shard. No cross-shard joins at the hot path.
- **Reference tables (replicated to every shard):** `subscription_plans`, `platform_admins`, `workspace_keys` (by workspace_id). These never grow beyond tens of thousands; safe to replicate.
- **Bronze rows — removed from Postgres entirely.** Bronze lives in S3+ClickHouse only; Postgres keeps `bronze_files` metadata.

### 4.3 ClickHouse shard strategy

- **Cluster:** 16 shards × 3 replicas = **48 nodes**.
- **Shard key (for distribution):** `cityHash64(enterprise_id) % 16`.
- **Sorting key (for MergeTree):** `(enterprise_id, run_id, created_at)` — makes all tenant-scoped queries range-scans.
- **Silver table:**
  ```sql
  CREATE TABLE silver_rows ON CLUSTER kaori_ch
  (
      enterprise_id UUID,
      run_id        UUID,
      row_id        UUID,
      row_data      String CODEC(ZSTD(3)),
      quality_score Decimal(5,4),
      applied_rules Array(String),
      created_at    DateTime64(3)
  )
  ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/silver_rows', '{replica}')
  PARTITION BY (toYYYYMM(created_at))
  ORDER BY (enterprise_id, run_id, created_at)
  TTL created_at + INTERVAL 2 YEAR
  SETTINGS index_granularity = 8192;

  CREATE TABLE silver_rows_distributed ON CLUSTER kaori_ch AS silver_rows
  ENGINE = Distributed('kaori_ch', 'default', 'silver_rows', cityHash64(enterprise_id));
  ```
- **Decision audit:**
  ```sql
  CREATE TABLE decision_audit ON CLUSTER kaori_ch
  (
      enterprise_id     UUID,
      decision_id       UUID,
      decision_type     LowCardinality(String),
      subject           String,
      chosen_value      String,
      confidence        Decimal(5,4),
      method            LowCardinality(String),
      llm_provider      LowCardinality(String),
      model_id          LowCardinality(String),
      alternatives      String CODEC(ZSTD(3)),       -- JSON
      uncertainty_flags Array(String),
      reasoning         String CODEC(ZSTD(3)),
      created_at        DateTime64(3)
  )
  ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/decision_audit', '{replica}')
  PARTITION BY (toYYYYMM(created_at))
  ORDER BY (enterprise_id, created_at, decision_id)
  TTL created_at + INTERVAL 2 YEAR
  SETTINGS index_granularity = 8192;
  ```
  At 730B rows, ZSTD keeps per-shard size around ~3 TB — fits in a single NVMe.

### 4.4 S3 bronze layout

```
s3://kaori-bronze-prod/
├── tier=pilot/
│   └── ent={enterprise_id}/
│       └── year=2026/month=04/day=25/
│           └── run={run_id}/
│               ├── part-00000-{uuid}.parquet
│               └── part-00001-{uuid}.parquet
├── tier=sme/      (same layout)
└── tier=large/    (same layout; plus lifecycle pinned to Intelligent-Tiering)
```

Lifecycle rules:
- `tier=pilot/**`: 30 d → Glacier Instant, 90 d → Glacier Deep Archive, 1 y → delete.
- `tier=sme/**`: 90 d → Intelligent-Tiering, 2 y → Glacier Instant.
- `tier=large/**`: always Intelligent-Tiering; contractual retention set per enterprise.

### 4.5 Redis cluster split (4 separate clusters, by workload)

| Cluster | Shards | Role | TTL profile | Persistence |
|---|---:|---|---|---|
| **rc-sessions** | 32 | JWT blacklist, refresh tokens | 24 h – 7 d | AOF fsync everysec |
| **rc-ratelimit** | 16 | Rate-limit counters, quota counters, Idempotency-Key | 60 s – 24 h | RDB daily (data is fine to lose) |
| **rc-llm-cache** | 16 | Semantic prompt cache | 1 h – 7 d | RDB hourly |
| **rc-feature-store** | 32 | Online gold features (per-customer RFM, churn prob) | no TTL (refreshed by ETL) | AOF fsync everysec |

Separate clusters so a LLM cache flood can't evict active sessions.

---

## 5. API surface (the exact contract at 1M scale)

### 5.1 Response envelope (non-negotiable from Day 1)

Success:
```json
{
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "trace_id": "otel-traceparent-value",
    "server_time": "2026-04-25T10:00:00.000Z",
    "cursor": "...",
    "total": 1234
  },
  "errors": [],
  "warnings": []
}
```

Error (RFC 7807, `Content-Type: application/problem+json`):
```json
{
  "type":   "https://docs.kaori.ai/errors/workspace-not-found",
  "title":  "Workspace not found",
  "status": 404,
  "detail": "Workspace 6c8e…-f31 does not exist or is inactive.",
  "instance": "/api/v1/platform/workspaces/6c8e…-f31",
  "request_id": "uuid",
  "trace_id":   "otel-traceparent-value"
}
```

### 5.2 Required headers — every mutation

```
Authorization:    Bearer {jwt}
Idempotency-Key:  {uuid-v4}   ← enforced at gateway, 24 h TTL in rc-ratelimit
X-Trace-ID:       {otel-tp}   ← gateway sets if absent
```

### 5.3 Routing rules (gateway to backing service)

| Path prefix | Backend | Special filter |
|---|---|---|
| `/auth/**` | auth-service | public for subpaths `login` / `forgot-password` / `reset-password`; everything else JWT-authed |
| `/api/v1/platform/**` | auth-service | require JWT role in {SUPER_ADMIN, ADMIN, SUPPORT}; SUPER_ADMIN also requires MFA claim |
| `/api/v1/enterprise/**` | auth-service (users/settings) OR data-pipeline (pipelines, schema) | role MANAGER/OPERATOR/ANALYST/VIEWER |
| `/api/v1/analytics/**` | ai-orchestrator | read-mostly; cache 30s at gateway (`Vary: X-Enterprise-ID`) |
| `/api/v1/insights/**` | ai-orchestrator | delegates to llm-gateway internally |
| `/api/v1/billing/**` | billing-service | MANAGER only for upgrade; SUPPORT for read |
| `/api/v2/**` | portal-prefixed routes (Phase 2) | |
| `/mcp/**` | mcp-server | OAuth 2.1 + PKCE; per-tenant scopes |
| `/v1/infer` | llm-gateway | internal only (mTLS service mesh); blocked at public edge |

### 5.4 SLOs (attached to each path prefix)

| Path | Target P95 | Error budget |
|---|---:|---|
| `POST /auth/login` | 250 ms | 0.5% 5xx / 99.95% availability |
| `GET /api/v1/analytics/runs/:id` | 500 ms | 0.1% 5xx / 99.99% availability (cacheable) |
| `POST /api/v1/insights/generate` | 4000 ms | 1% 5xx / 99.9% availability (LLM-bound) |
| `POST /api/v1/upload` (ack) | 300 ms | 0.1% 5xx (fire-and-forget) |
| `GET /api/v1/dashboard/state` | 800 ms | 0.1% 5xx / 99.95% (materialized + cached) |

---

## 6. Auth / authz at 1M scale

- **JWTs are RS256**, 15-min access / 7-day refresh. Already in spec, confirmed in target.
- **Blacklist:** short-lived (same as access TTL) in `rc-sessions` with **in-process Caffeine** cache at the gateway (60s TTL). Revocation propagates fully within 60s, acceptable given 15-min access TTL.
- **RBAC:** gateway applies role predicate on path match (see §5.3). Every decision is also re-checked server-side via `@PreAuthorize` (defense in depth).
- **ABAC/PDP:** Phase-2 addition; current gateway check is sufficient for 1M tenants' RBAC-only policies.
- **Tenant isolation:**
  1. JWT carries `enterprise_id` + `tier`; gateway injects `X-Enterprise-ID` + `X-Tenant-Tier`.
  2. Backend services connect to DB pool as `kaori_app` role, NOT superuser.
  3. Every pool-acquire wrapper runs `SET LOCAL app.enterprise_id = $1` before the caller gets the connection.
  4. RLS policies (already defined in `migrations/001_init.sql:316-339`) now actually enforce.
  5. Citus adds another layer: the shard key IS the enterprise_id, so cross-tenant queries cross shards and fail fast.
- **MFA:** SUPER_ADMIN requires TOTP; step-up for destructive actions (revoke key, change plan, delete admin).

---

## 7. Observability (what you must measure to survive 1M tenants)

- **Tracing:** OpenTelemetry end-to-end; trace IDs propagate header → Kafka headers → DB `set_config('app.trace_id')` → logs. Target: every request traceable in <30s.
- **Metrics:** Prometheus scrape; per-tenant cardinality caps (do not label per-enterprise — use per-tier bucketing + exemplars).
- **Logs:** structured JSON to Loki; ship to S3 after 30 d.
- **SLO dashboards:** per path SLO violations surface as PagerDuty; per-tenant anomaly detection runs as a streaming job on `kaori.audit.internal`.
- **Kafka lag:** Burrow cluster; alert on consumer group lag >5 min; DLQ depth >100.
- **ClickHouse health:** Altinity Operator dashboards; replica divergence, merge lag, disk free.
- **vLLM:** queue depth on `kaori.llm.infer.requests`, GPU util per pod, tokens/sec.

---

## 8. Disaster recovery

- **Kafka MM2** mirrors all `kaori.*` topics across 2 regions. RPO < 30 s.
- **Postgres (Citus):** cross-region streaming replica + WAL archive to S3. RPO < 10 s; RTO ~15 min.
- **ClickHouse:** cross-region replica pair per shard; RPO < 60 s.
- **S3:** cross-region replication on `kaori-bronze-prod`. RPO < 5 min; RTO near-zero for reads.
- **Redis:** data in rc-sessions/rc-ratelimit is OK to lose in DR; rc-feature-store has S3 snapshot hourly for rebuild from Gold.
- **Chaos drills:** quarterly region-kill exercise; annual full cutover.

---

## 9. Deployment topology (the physical placement)

- **Kubernetes:** 3 clusters — `prod-ap-hn` (primary), `prod-ap-sg` (active-active for P2 reads), `prod-us-east` (DR/cold).
- **Service mesh:** Istio; mTLS between every service pair.
- **Ingress:** AWS ALB / GCP GLB in front of each cluster, Cloudflare at edge.
- **Node pools per cluster:**
  | Pool | Nodes | Taint | Pods |
  |---|---:|---|---|
  | `gen-pool` | 120 × 16 vCPU / 64 GB | default | gateway, auth, data-pipeline, ai-orch, llm-gw, billing, audit, mcp |
  | `io-pool` | 40 × 32 vCPU / 128 GB / NVMe | `io=true` | bronze-parser-worker (streams Parquet) |
  | `gpu-pool` | 16 × 4×H100 | `gpu=h100` | vllm-pool only |
  | `db-pool` (bare-metal/AWS RDS) | — | — | Citus nodes, ClickHouse nodes (NOT on k8s) |

---

## 10. What this target costs, honestly

At list prices, this is a ~$2M/mo infrastructure footprint at steady-state 1M tenants. Realistic:

| Component | Monthly, list | Monthly, optimized (spot+reserved) |
|---|---:|---:|
| Kubernetes compute (1000 pods) | $250K | $90K |
| Citus Postgres (256 shards × 3) | $380K | $150K |
| ClickHouse (48 nodes) | $180K | $80K |
| S3 (2.5 PB hot + 15 PB cold) | $95K | $50K |
| Redis Cluster (4 clusters × ~40 nodes) | $60K | $30K |
| Kafka (12 brokers × 3 regions) | $75K | $35K |
| vLLM GPU pool (64 H100 baseline) | $850K | $280K (spot + 1-yr reserved) |
| Bandwidth / egress | $60K | $35K |
| Observability stack | $40K | $20K |
| **Total** | **~$2.0M** | **~$770K** |

At 1M tenants × avg ARPU $40/mo (blended SME+large), revenue ~$40M/mo. Infra-to-revenue ratio ~2%. Healthy.

---

## 11. Migration path from current → target (phased)

Not a big-bang. Six phases, each independently shippable:

| Phase | Duration | Scope | Exit criteria |
|---|---|---|---|
| **P-0** | 2 wk | Fix the 6 P0s from `ARCHITECTURE_REVIEW.md` (SecurityConfig, Kafka topic naming, RBAC, RLS, silent Kafka, K-6) | All new ✅'s are honest; no ghost features in tracker |
| **P-1** | 4 wk | LLM Gateway + model registry + semantic cache (still on Ollama) | `llm_router.py` deleted from ai-orchestrator; every LLM call goes through gateway |
| **P-2** | 6 wk | Outbox pattern + Kafka partitioned-by-tenant + DLQ per topic | Zero silent event loss in 30-d soak; Kafka lag <5 s p99 |
| **P-3** | 8 wk | Bronze → S3 Parquet; Silver → ClickHouse; retire `bronze_rows` table | Pipeline P95 <30 s for 10M rows; Postgres row count drops by 99% |
| **P-4** | 8 wk | Citus shard rollout (256 shards); dual-write + cutover | Every table colocated by `enterprise_id`; RLS enforced |
| **P-5** | 6 wk | vLLM pool replaces Ollama; 72B model via canary per §6.5 of SCALE_PLAN | P95 insight <4 s at peak; GPU util >60% sustained |
| **P-6** | ongoing | Per-tenant quotas + tiering + DR drills | Noisy-neighbor eliminated; quarterly chaos drills pass |

Total: ~34 weeks (~8 months) from a team that's shipping in parallel. P-0 and P-1 unblock everything else and can run concurrently after week 1.

---

## 12. What this design explicitly rejects

- **Multi-region active-active writes** — at 1M tenants the complexity payoff isn't there yet. Primary-secondary with hot standby is sufficient; go active-active in Phase 3+.
- **Sidecar-per-pod LLM** — cute, ungovernable at scale. Centralized `llm-gateway` is the only sane choice.
- **Per-tenant dedicated K8s namespace** — tenant quotas are enough; namespace-per-tenant at 1M = explosion of control-plane objects.
- **Global Postgres (no sharding)** — AWS Aurora Limitless or Yugabyte could in theory do this; Citus is boring and known, and Aurora Limitless at this scale is ~3× the cost.
- **Event sourcing everywhere** — CQRS is good for Kafka audit; applying it to every service's state is unneeded complexity. Keep Postgres as the current state of truth; let Kafka stream changes.
- **Replacing SMTP with SES-only** — use SES as primary, but keep provider-agnostic `notification-service` because enterprise customers demand custom SMTP relay for compliance.

---

## 13. The one-line answer to "will it scale?"

**Yes, exactly once you do these three things in order: (1) extract the LLM Gateway so the inference path is independently scalable, (2) partition Kafka by `enterprise_id` and add an outbox — because the event backbone is the circulatory system, (3) put Bronze on S3 + Silver on ClickHouse + shard Postgres with Citus — because the warm-data layer determines the ceiling.** Everything else is refinement.
