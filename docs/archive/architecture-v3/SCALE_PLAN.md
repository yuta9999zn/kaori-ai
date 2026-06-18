# Kaori AI — Scale Plan (100K tenants, 1M personal users)

> **Author:** Principal Engineer — distributed systems + SaaS
> **Date:** 2026-04-25
> **Companion:** `ARCHITECTURE_REVIEW.md` (correctness / security) — this doc covers **scale only**.
> **Rule:** every claim points to a real file, query, topic, or flow. No theory. No "consider using…".

---

## Scale envelope (the math we're designing for)

| Dimension | Target | Derivation |
|---|---:|---|
| Enterprise tenants | **100,000** | 15% large (15K × ~50M rows) + 75% SME (75K × ~1M rows) + 10% pilot |
| Bronze + Silver rows (all tenants) | **~825 B rows** | 15K×50M + 75K×1M |
| Personal users | 1,000,000 | ~10K rows each ⇒ +10B rows |
| Concurrent human sessions | **~1.2 M** | Large 15K×50 + SME 75K×5 + Personal 1M×0.1 |
| Steady-state API QPS (public) | **~20K** | 1.2M × 1 req/min avg |
| Peak API QPS (burst 5×) | **~100K** | login waves, scheduled reports |
| Concurrent data pipelines | **1000+** | 1% of enterprises running at once |
| LLM prompts / sec | **~2K steady / 10K peak** | insights + framework auto-fill + MCP |
| Kafka event volume | **~55K events/s steady** | 4 events/pipeline × 1000 + decision log stream |
| Audit log volume | **~73 B rows / 2 yr** | 100K × 100 decisions/day × 730 days |

Everything below is sized against those numbers.

---

## Part 1 — Scaling weaknesses that break in production

Five structural SPOFs. Each one kills the platform before 100K tenants.

### 1.1 Single Postgres instance — the first thing that dies

**Where:** `docker-compose.yml:9-19` — single `postgres:pgvector/pgvector:pg15` container; no replication, no shards.
**Concrete failure:**
- `bronze_rows` INSERT in `services/data-pipeline/bronze/ingestor.py:144-156` runs row-by-row via `await conn.execute("INSERT INTO bronze_rows …")` inside a Python `for` loop. 1000 concurrent pipelines × 100K rows × 1ms/insert = **100 million INSERTs/sec target against one Postgres**. Postgres single-primary tops out at ~50K INSERTs/sec with COPY, ~5K with single-row INSERT. **Breaks at first realistic production load.**
- Connection pool per Python pod: `asyncpg.create_pool(dsn, min_size=2, max_size=10)` (`data-pipeline/shared/db.py:16`). 200 pods → 2000 connections. Postgres default `max_connections=100`. **Pool exhaustion.**
- `bronze_rows`, `silver_rows`, `decision_audit_log` are all in one schema, one instance. At 825 B rows total, a query without partition pruning (e.g. `SELECT * FROM silver_rows WHERE enterprise_id=$1 AND created_at > NOW()-'7 days'`) scans the wrong shard.

**What breaks first:** `services/data-pipeline/routers/clean.py:104-111` loads **all** bronze rows for a run via a single `conn.fetch(...)` into Python memory, then builds a pandas DataFrame. For a 50M-row large-tenant silver refresh: ~25 GB in memory per worker → OOMKilled before Postgres even feels pressure.

### 1.2 Single Kafka broker — cluster-reboot storms

**Where:** `docker-compose.yml:46-66` — `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1`, one broker, no ZK HA, `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true`.
**Concrete failure:**
- Broker restart (upgrade, OOM, spot-instance kill) = 100% message loss during the gap. `replication.factor=1`. No ack from followers (there are none).
- Consumer group `kaori-orchestrator` (`ai-orchestrator/consumers/pipeline_consumer.py:20`) is single-process. Scaling to N pods means rebalance every pod restart; with `enable_auto_commit=True` + `auto_offset_reset='latest'` (lines 33-34), any consumer down-time = lost events forever.
- Topics are **not keyed by tenant**. In `data-pipeline/shared/kafka_producer.py:41`: `await _producer.send_and_wait(topic, payload)` — no `key=` argument. Result: messages for the same `enterprise_id` land on different partitions, **no per-tenant ordering guarantee**. At 55K events/s this causes out-of-order silver→analysis processing → stale dashboards.
- `pipeline.silver.complete` is emitted from **two different code sites**: `data-pipeline/routers/clean.py:236` (after cleaning) and `data-pipeline/routers/analyze.py:59` (on analysis-run creation). The consumer can't tell them apart; at scale it double-schedules analysis for the same run. See `ARCHITECTURE_REVIEW.md §1.3`.

### 1.3 Single Redis — the gateway hotspot

**Where:** `docker-compose.yml:26-36` — one Redis, one node, no cluster.
**Concrete failure (per-request cost at the gateway):**
- `JwtAuthFilter.java:67` does `redis.hasKey("blacklist:" + token)` on **every** authenticated request.
- `RateLimitFilter.java:48-62` does **four** non-atomic Redis ops per request: `ZADD` + `ZREMRANGEBYSCORE` + `ZCARD` + `EXPIRE`.
- Per-request cost: **5 Redis ops**. At 20K QPS steady → **100K Redis ops/s**. Peak 500K ops/s.
- Single Redis ceiling ≈ 100K ops/s (commodity box). **Breaks at steady state, not peak.**
- Additional load: `AuthService.java:99-100` writes `refresh:{userId}` on every login; `AuthService.java:117-120` blacklists every logout; `PlatformKeyService.java:42-50` rate-limits key generation per workspace. All on same Redis.
- No Redis persistence → single-node restart loses every JWT blacklist, every rate-limit window, every refresh token. **Forced mass-re-login across the platform.**

### 1.4 Single Ollama/Qwen — GPU serializes every insight

**Where:** `docker-compose.yml:78-96` — `ollama/ollama:latest` single container, default single-replica, no GPU autoscale, no batching layer.
**Concrete failure:**
- `llm_router._call_qwen` (`ai-orchestrator/engine/llm_router.py:56-69`) makes direct `POST {OLLAMA_HOST}/api/generate` with `"stream": false`. Ollama with Qwen2.5:14B on one A100 does **~3-10 req/s** (token-streaming aside); without continuous batching, requests queue serially.
- At 2K LLM req/s steady (insights + framework auto-fill + MCP), queue depth at 10 req/s throughput = **200 seconds wait per request**. P95 >3 minutes. SLA target (<5s) violated by 40×.
- No semantic cache: same prompt from 10 tenants → 10 LLM calls. Insight text "explain this churn result" is highly cacheable at class level, never cached.
- `httpx.AsyncClient(timeout=120.0)` — at 10 concurrent callers above 10 req/s Ollama throughput, all 10 time out simultaneously, return 500 to frontend.
- Model IDs hardcoded at call sites (`"claude-sonnet-4-6"` at `llm_router.py:82`). Upgrading model = code change + redeploy of `ai-orchestrator`. See Part 6 for the upgrade-safe redesign.

### 1.5 Application-layer tenant isolation — one bad query = multi-tenant breach

**Where:** `services/data-pipeline/shared/db.py:13-17` — asyncpg pool with superuser DSN; no `SET LOCAL app.enterprise_id` is ever called anywhere in the codebase (grep `set_config` + `SET LOCAL app.` → zero hits).
**Concrete failure:**
- `migrations/001_init.sql:316-339` + `005_rls.sql:27-114` define RLS policies using `current_setting('app.enterprise_id', TRUE)::UUID`. Because the pool connects as superuser and the variable is never set, **RLS is bypassed** — tenant isolation depends 100% on application-layer `WHERE enterprise_id=$1` strings.
- At 100K tenants × dozens of endpoint authors over time, one missed filter = **multi-tenant data exfil**.
- Example: if someone adds `GET /api/v1/silver-rows/stats` and writes `SELECT COUNT(*) FROM silver_rows WHERE created_at > $1` (no enterprise_id filter), the endpoint returns the platform-wide count — indistinguishable from an authorization bug in code review.

---

## Part 2 — Code-level issues that scale-kill

Concrete file:line → failure at scale → fix.

### 2.1 `bronze/ingestor.py:144-156` — row-by-row INSERT in a Python loop

```python
for row_idx, row in enumerate(rows):
    row_hash = hashlib.sha256(str(sorted(row.items())).encode()).hexdigest()
    await conn.execute(
        """INSERT INTO bronze_rows (file_id, enterprise_id, row_index, raw_data, row_hash)
           VALUES ($1, $2, $3, $4::jsonb, $5)""",
        ...
    )
```

- 100K rows = 100K round-trips. At 1ms RTT = 100s per pipeline.
- 1000 concurrent pipelines × 100K rows = **100M INSERTs/s target**. Impossible with `INSERT`.

**Fix (concrete):**
```python
await conn.copy_records_to_table(
    "bronze_rows",
    records=[(file_id, ent_id, idx, json.dumps(row), row_hash) for idx, row in enumerate(rows)],
    columns=["file_id", "enterprise_id", "row_index", "raw_data", "row_hash"],
)
```
COPY is ~100× faster than single INSERTs; also pushes per-row hash logic to the producer side or removes it (it's non-portable — see `ARCHITECTURE_REVIEW.md §2.3 #4`).

### 2.2 `routers/clean.py:103-111` — full materialization of bronze into memory

```python
bronze_rows = await conn.fetch(
    """SELECT br.row_id, br.file_id, br.row_index, br.raw_data
       FROM bronze_rows br JOIN bronze_files bf ON bf.file_id = br.file_id
       WHERE bf.run_id = $1 AND br.enterprise_id = $2
       ORDER BY br.file_id, br.row_index""",
    run_uuid, enterprise_uuid
)
```

- `fetch` loads the full result into a Python list. For 50M rows × ~500 bytes/row = **25 GB Python memory per worker**.
- Then it builds a pandas DataFrame (line 143), then iterates to reinsert row-by-row (line 194).

**Fix:** use asyncpg server-side cursor + chunked COPY:
```python
async with conn.transaction():
    cursor = await conn.cursor("SELECT row_id, raw_data FROM bronze_rows WHERE run_id=$1 ORDER BY row_index", run_uuid)
    while batch := await cursor.fetch(10_000):
        cleaned = apply_rules_batch(batch)         # pure function, no state
        await conn.copy_records_to_table("silver_rows", records=cleaned, columns=[...])
```
Memory: O(10K rows) not O(50M).

### 2.3 `schema.py:78-92` — N+1 INSERT into `decision_audit_log`

```python
for m in mappings:
    await conn.execute(
        "INSERT INTO decision_audit_log (enterprise_id, run_id, decision_type, subject, chosen_value, confidence, method, alternatives, uncertainty_flags) VALUES (...)",
        ...
    )
```

- 100-column file × 1000 concurrent schema reviews = **100K INSERTs serialised per tenant action**.
- Under RLS + FORCE ROW LEVEL SECURITY (when enabled), every INSERT does a policy re-evaluation. Latency compounds.

**Fix:** single `INSERT ... SELECT UNNEST($1, $2, $3, ...)` with array params, or `copy_records_to_table`.

### 2.4 `gateway/filter/RateLimitFilter.java:48-62` — 4 non-atomic Redis ops

Concrete race at 20K QPS: 100 concurrent requests all execute `ZADD → ZREMRANGE → ZCARD → EXPIRE` in parallel; each sees `count < limit` and passes. Real rate = 4× intended.

**Fix:** single LUA script, atomic on Redis:
```
-- KEYS[1] = ratelimit:jwt:{user}
-- ARGV[1] = now_ms, ARGV[2] = window_ms, ARGV[3] = limit
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1] - ARGV[2])
local count = redis.call('ZCARD', KEYS[1])
redis.call('EXPIRE', KEYS[1], math.ceil(ARGV[2]/1000) + 10)
if count > tonumber(ARGV[3]) then return 1 else return 0 end
```
One RTT instead of four. Atomic.

### 2.5 `gateway/filter/JwtAuthFilter.java:67` — Redis lookup per request

`redis.hasKey("blacklist:" + token)` on every authenticated request = 20K Redis GETs/s steady.

**Fix (tiered):** in-process Caffeine cache (per-pod, 10K entries, TTL=60s) in front of Redis. A logout-invalidated token will be seen as still valid for up to 60s — acceptable per the spec (access tokens are 15 min already). Reduces Redis blacklist hits by ~95%.

### 2.6 `AuthService.java:70-79` — lockout counter timer reset

Already in `ARCHITECTURE_REVIEW.md §2.3 #2`. At scale the spray attack is cheap: 1 attempt / 14 min per email × 100K stolen emails = 7K req/s brute force with no detection.

---

## Part 3 — Data architecture rewrite

### 3.1 Bronze / Silver / Gold storage reality at this scale

| Layer | Today (broken at scale) | Target | Why |
|---|---|---|---|
| Bronze | Postgres `bronze_rows` JSONB | **MinIO/S3 as Parquet files** partitioned by `enterprise_id/yyyy-mm-dd/`; metadata in Postgres | Postgres row-store is the worst possible fit for append-only immutable raw rows. Parquet+S3 is 10× cheaper and designed for this. |
| Silver | Postgres `silver_rows` JSONB | **ClickHouse** with `PARTITION BY (tenant_shard, toYYYYMM(created_at))` + `ORDER BY (enterprise_id, created_at)` | Silver is read-heavy OLAP (analytics over cleaned rows). Postgres can't scan 10M rows / tenant without partitioning; ClickHouse does 100M rows/s per core. CLAUDE.md §5 already mentions ClickHouse as target — it's not wired. |
| Gold | Postgres `gold_features` + Redis cache | **Postgres MV partitioned by enterprise_id** + Redis feature store | Small cardinality (per-customer RFM / churn), low-latency read; Postgres is fine if partitioned. |

### 3.2 Partitioning DDL (concrete)

Silver in ClickHouse:
```sql
CREATE TABLE silver_rows
(
    enterprise_id UUID,
    run_id        UUID,
    row_id        UUID,
    row_data      String,            -- JSON
    quality_score Decimal(5,4),
    created_at    DateTime64(3)
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/silver_rows/{shard}', '{replica}')
PARTITION BY (intHash32(enterprise_id) % 64, toYYYYMM(created_at))
ORDER BY (enterprise_id, run_id, created_at)
TTL created_at + INTERVAL 2 YEAR DELETE;
```

Bronze in S3:
```
s3://kaori-bronze/
   ent={enterprise_id}/
   year=2026/month=04/day=25/
   run={run_id}/
   part-{uuid}.parquet
```
Metadata index in Postgres (`bronze_files`) already has `file_id`, `enterprise_id`, `run_id` — add `s3_path` column; drop `bronze_rows` entirely from Postgres.

### 3.3 Decision audit at 73 B rows

`decision_audit_log` is in Postgres (`migrations/001_init.sql:218`) with `RULE … DO INSTEAD NOTHING` for UPDATE/DELETE — append-only. At 73 B rows over 2 years, Postgres will need ~40 TB + index. Postgres **can't index that.**

**Move to ClickHouse** with the same immutability contract:
```sql
CREATE TABLE decision_audit_log
ENGINE = ReplicatedMergeTree('/clickhouse/tables/decision_audit/{shard}', '{replica}')
PARTITION BY (intHash32(enterprise_id) % 64, toYYYYMM(created_at))
ORDER BY (enterprise_id, created_at, decision_id)
TTL created_at + INTERVAL 2 YEAR DELETE;   -- matches CLAUDE.md §7 retention
```
Postgres keeps a small 90-day hot window for "why denied" lookups (F-029).

### 3.4 Materialized view for P1 billing — today referenced but not created

`BACKLOG.md` references `v_billing_summary` (F-011 reads it). **Not in any migration.** At 100K tenants the summary cannot be computed live on each dashboard hit. Required DDL:

```sql
CREATE MATERIALIZED VIEW v_billing_summary AS
SELECT enterprise_id, billing_month,
       SUM(unique_customers) AS unique_customers,
       SUM(overage_cost_vnd) AS overage_cost_vnd,
       MAX(updated_at)       AS refreshed_at
FROM enterprise_monthly_billing
GROUP BY enterprise_id, billing_month;

CREATE UNIQUE INDEX ON v_billing_summary (enterprise_id, billing_month);

-- refreshed nightly by F-031 cron
```

### 3.5 Hot/cold separation

Bronze older than 90 days → S3 Glacier (1/10 the cost of standard S3). Today: nothing. At 100K tenants × 50M rows × ~500 bytes retained indefinitely = **25 PB hot data**. Add lifecycle rules at S3 side; Bronze access pattern (re-play on ingestion failure) is fine with Glacier restore.

---

## Part 4 — Distributed system fixes

### 4.1 Kafka: partition by tenant, manual commit, DLQ

Concrete diff in `data-pipeline/shared/kafka_producer.py:41`:
```python
# Before
await _producer.send_and_wait(topic, payload)
# After
await _producer.send_and_wait(topic, payload, key=payload["enterprise_id"].encode("utf-8"))
```

This change alone unlocks:
- Per-tenant ordering (same partition every time).
- Horizontal consumer scaling: N consumers split partitions; one tenant's traffic stays on one partition so the consumer gets sticky work.

Consumer (`ai-orchestrator/consumers/pipeline_consumer.py:26-34`):
```python
consumer = AIOKafkaConsumer(
    "pipeline.silver.complete", "pipeline.analysis.complete",
    bootstrap_servers=KAFKA_BOOTSTRAP,
    group_id=CONSUMER_GROUP,
    value_deserializer=...,
    auto_offset_reset="earliest",   # ← was 'latest' — had to be changed to not lose events
    enable_auto_commit=False,       # ← was True — had to be changed for exactly-once semantics
    max_poll_records=100,
    session_timeout_ms=30000,
)
...
try:
    await _dispatch(msg.topic, msg.value)
    await consumer.commit()
except Exception as exc:
    await _send_to_dlq(msg, exc)
    await consumer.commit()  # advance past poison pill
```

DLQ pattern — add topic `{original_topic}.dlq`; a separate "dlq-replayer" service drains it with exponential backoff (1s, 2s, 4s, 8s, 16s) then sends to `{original_topic}.dlq.final` for manual review.

### 4.2 Transactional outbox (kill the silent Kafka swallow)

Today `send_event` catches errors and returns (`data-pipeline/shared/kafka_producer.py:43-45`). At 55K events/s × 0.1% failure = 55 lost events/s. Over a week: ~30M lost events. Billing and audit chains drift invisibly.

Concrete outbox:
```sql
CREATE TABLE outbox (
    id            BIGSERIAL PRIMARY KEY,
    topic         TEXT NOT NULL,
    key           TEXT NOT NULL,
    payload       JSONB NOT NULL,
    enterprise_id UUID NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    published_at  TIMESTAMPTZ
);
CREATE INDEX ON outbox (published_at) WHERE published_at IS NULL;
```

Producer API:
```python
async def enqueue_event(conn, topic, payload):
    await conn.execute(
        "INSERT INTO outbox (topic, key, payload, enterprise_id) VALUES ($1,$2,$3::jsonb,$4)",
        topic, payload["enterprise_id"], json.dumps(payload), payload["enterprise_id"]
    )
    # commits with the rest of the business transaction
```

Separate `outbox-publisher` service does:
```
LOOP:
  rows = SELECT ... FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT 1000
  FOR row: producer.send(topic, key=row.enterprise_id, value=row.payload, acks='all')
  UPDATE outbox SET published_at=NOW() WHERE id = ANY($ids)
```
Gives **at-least-once** delivery with no lost events. Consumers must already be idempotent (key on `run_id` or `decision_id`).

### 4.3 Idempotency-Key on all mutations

Gateway adds filter `IdempotencyFilter` before `RateLimitFilter`:
```
Header Idempotency-Key: {uuid-v4}  (required on POST/PATCH/DELETE mutations)
```
At gateway: `GET idempotency:{tenant}:{sha256(key+path)}` in Redis. If present → return cached response. Else: forward + cache response (TTL 24h).

Without this, at 20K QPS steady, any retry storm (client network blip) doubles business-critical writes: duplicated billing events, duplicated user invites, duplicated workspace creations. K-13 is a hard requirement at this scale, not an optional invariant.

### 4.4 Backpressure

Today `routers/upload.py:26` does:
```python
asyncio.create_task(_parse_and_land(...))
```
Fire-and-forget. 1000 concurrent uploads = 1000 asyncio tasks inside one Python worker. Event loop starves. No visibility into queue depth.

**Replace with** an explicit job queue (Redis Streams or Temporal):
```python
await job_queue.enqueue("parse_bronze", {run_id, enterprise_id, file_path})
return {"run_id": run_id, "status": "queued"}
```
Separate `bronze-parser` worker pool reads the queue; horizontal autoscale on queue depth. The `pipeline_runs.status` stays accurate (`queued` → `parsing` → `bronze_complete`) and survives pod restarts.

---

## Part 5 — Multi-tenant at 100K

### 5.1 Tier enterprises physically

Three isolation tiers, routed by `tenant_tier` column on `workspaces`:

| Tier | % of tenants | Physical isolation | Postgres | Kafka | Ollama |
|---|---:|---|---|---|---|
| **Pilot** | ~10K | Shared everything | Shared DB (RLS) | Shared topic, low priority | Shared Qwen pool |
| **SME** | ~75K | Shared shard, strict RLS | 1 of 16 DB shards by `hash(enterprise_id) % 16` | Shared topic, per-tenant quota | Shared Qwen pool |
| **Large** | ~15K | Dedicated schema or dedicated DB | Dedicated schema in a shard (top 1K get dedicated DB) | Dedicated topic for heavy enterprises | Reserved GPU slice |

Routing logic: gateway injects `X-Tenant-Tier` header based on `workspaces.tier`; downstream services use it to pick the right pool / topic / quota. Concrete change: add `tier` column to `workspaces`, populate from `subscription_plans.tier`, expose in JWT claims.

### 5.2 Tenant sharding key

**Shard key: `hash(enterprise_id) → shard_id`** (consistent hash, 16 shards day-one, 128 ceiling).

Why not by region? Kaori is VN-first but multi-region is Phase 2 concern; consistent-hash on tenant avoids hot-shard if one region grows faster.

Concrete connection routing in `data-pipeline/shared/db.py`:
```python
def get_pool_for_tenant(enterprise_id: str) -> asyncpg.Pool:
    shard = crc32(enterprise_id.encode()) % SHARD_COUNT
    return _pools[shard]
```
And require callers to pass `enterprise_id` (they always have it from the JWT header already).

### 5.3 Noisy-neighbor fences (per-tenant quotas)

Three quotas, cheap to enforce, mandatory at this scale:

| Quota | Where | Enforcement |
|---|---|---|
| **Pipeline runs/day** | Gateway | Redis `INCR quota:pipelines:{tenant}:{yyyy-mm-dd}` with TTL 48h; 429 when over. Plan-based limit (PILOT=10, ENT_BASIC=50, ENT_MAX=∞). |
| **LLM tokens/day** | LLM Gateway (Part 6) | Same pattern, Redis counter + 429. Hard cap per plan. |
| **Kafka produce rate** | Broker quota (`client.quotas`) | Kafka supports per-client-id byte-rate quota; set client-id = `enterprise_id`. |

Without these, one large enterprise's 50M-row reprocess starves the LLM queue and Kafka lag spikes for every other tenant.

### 5.4 The RLS fix is still mandatory

Pool must switch from superuser to `kaori_app` role; every handler must do:
```python
async with pool.acquire() as conn:
    await conn.execute("SET LOCAL app.enterprise_id = $1::text", enterprise_id)
    # ... rest of the work
```
Or (cleaner) wrap `acquire()` in a context manager that auto-sets on entry. See `ARCHITECTURE_REVIEW.md §5 item E`.

At 100K tenants, RLS is your only defense against application-layer bugs; it will not save you unless the session variable is set on every query.

---

## Part 6 — LLM scaling **and** the upgrade-safe design

This is the user's direct question: *design so a stronger future model makes the system stronger, not breaks it.*

### 6.1 Today — why an upgrade breaks

- `ai-orchestrator/engine/llm_router.py` makes direct HTTP calls with **provider-specific request shapes** at call sites (Ollama `/api/generate`, Anthropic `/v1/messages`, OpenAI `/v1/chat/completions`). Each backend has a different shape; every caller indirectly depends on Ollama's prompt format.
- Model string hardcoded inline: `"model": "qwen2.5:14b"` (env var) and `"model": "claude-sonnet-4-6"` (literal line 82). Swapping Qwen 14B → 72B is an env-var change; but swapping to vLLM-served model or to a completely different family (Llama 3.3 70B) is a code change because the request body differs (`num_predict` vs `max_tokens`, `options` vs top-level, `stream` default, etc.).
- No queue, no batching, no cache, no per-tenant budget. Upgrading the model doesn't make any of these structural problems go away.
- No versioning. There's no way to shadow-traffic a new model or roll back on regression.
- Caller passes a raw `prompt` string; upgrading a model whose optimal prompt format is different (chat template vs completion, system message support, tool-use JSON) requires touching every call site.

### 6.2 Target — LLM Gateway as a separate service

A new microservice `llm-gateway:8095` that exposes one contract and hides everything else:

```http
POST /v1/infer
Content-Type: application/json
X-Enterprise-ID: ...
X-User-ID: ...
X-Task-Type: INSIGHT_GEN | SUMMARIZE | EMBED | REASON | CODE | CLASSIFY
X-Privacy-Mode: strict | standard | permissive
Idempotency-Key: ...

{
  "prompt_template_id": "insight.three_panel.v2",
  "variables": { "analysis_run_id": "...", "context": "..." },
  "max_tokens": 2000,
  "temperature": 0.1,
  "stream": false
}
```

Response:
```json
{
  "request_id": "uuid",
  "text": "...",
  "model_id": "qwen2.5:14b@v12",
  "model_family": "qwen2.5",
  "tokens_in": 1203, "tokens_out": 482,
  "latency_ms": 1820,
  "cache_hit": false,
  "cost_vnd": 0
}
```

Every caller in `ai-orchestrator` (insights, frameworks, MCP) stops importing `llm_router` and calls this HTTP endpoint. **The caller never names a model.** Upgrading the model is a registry change in `llm-gateway` — no caller redeploys.

### 6.3 Model registry (source of truth)

```sql
CREATE TABLE llm_models (
    model_id          TEXT PRIMARY KEY,        -- e.g. 'qwen2.5:14b@v12', 'llama3.3:70b@v1'
    provider          TEXT NOT NULL,           -- 'ollama' | 'vllm' | 'anthropic' | 'openai'
    family            TEXT NOT NULL,           -- 'qwen2.5', 'llama3.3', 'claude', 'gpt-4'
    endpoint_url      TEXT NOT NULL,
    capabilities      TEXT[] NOT NULL,         -- ['CHAT','REASON','CODE'] or ['EMBED']
    max_context_tokens INTEGER NOT NULL,
    cost_per_1k_in_vnd  NUMERIC(14,4) NOT NULL DEFAULT 0,
    cost_per_1k_out_vnd NUMERIC(14,4) NOT NULL DEFAULT 0,
    status            TEXT NOT NULL,           -- 'shadow' | 'canary' | 'active' | 'deprecated' | 'retired'
    traffic_pct       INTEGER NOT NULL DEFAULT 0,
    deployed_at       TIMESTAMPTZ DEFAULT NOW(),
    deprecated_at     TIMESTAMPTZ,
    replaced_by       TEXT REFERENCES llm_models(model_id),
    notes             TEXT
);

CREATE TABLE llm_task_routing (
    task_type      TEXT NOT NULL,                 -- 'INSIGHT_GEN', 'EMBED', 'CODE', etc.
    privacy_mode   TEXT NOT NULL,                 -- 'strict', 'standard', 'permissive'
    model_id       TEXT NOT NULL REFERENCES llm_models(model_id),
    priority       INTEGER NOT NULL DEFAULT 100,  -- pick lowest available
    PRIMARY KEY (task_type, privacy_mode, priority)
);
```

Example rows:
```
qwen2.5:14b@v12    ollama   qwen2.5      http://ollama:11434  {CHAT,REASON}  32768  0  0   active      100
qwen2.5:72b@v1     vllm     qwen2.5      http://vllm-pool:8000 {CHAT,REASON} 131072 0  0   shadow        0
bge-m3:v3          ollama   bge          http://ollama:11434  {EMBED}         8192  0  0   active      100
claude-sonnet-4-7  anthropic claude      https://api.anthropic.com/v1/messages {CHAT,REASON,CODE} 200000 3000 15000 active  100
```

Routing table example:
```
INSIGHT_GEN   strict        qwen2.5:14b@v12     10
INSIGHT_GEN   standard      qwen2.5:14b@v12     10
INSIGHT_GEN   standard      claude-sonnet-4-7   20   (fallback if Qwen over quota)
INSIGHT_GEN   permissive    claude-sonnet-4-7   10
EMBED         strict        bge-m3:v3           10
CODE          standard      claude-sonnet-4-7   10
```

### 6.4 Provider adapter pattern

Inside `llm-gateway`:
```python
class LLMProvider(Protocol):
    async def infer(self, req: InferenceRequest) -> InferenceResponse: ...

class OllamaProvider(LLMProvider): ...    # today
class VLLMProvider(LLMProvider): ...      # stronger local model tomorrow
class AnthropicProvider(LLMProvider): ...
class OpenAIProvider(LLMProvider): ...
class OpenAIChatProvider(LLMProvider): ...  # for OpenAI-compatible servers incl. vLLM

PROVIDERS = {
    "ollama": OllamaProvider(),
    "vllm":   OpenAIChatProvider(base_url=...),   # vLLM exposes OpenAI-compatible API
    "anthropic": AnthropicProvider(),
    "openai": OpenAIProvider(),
}
```

The router logic becomes:
```python
async def infer(req):
    # 1. resolve model from routing table
    model = await resolve_model(task=req.task_type, privacy=req.privacy_mode)
    # 2. render prompt from template (variables interpolated, chat template applied per provider)
    prompt = render_prompt(req.prompt_template_id, req.variables, model.family)
    # 3. cache lookup (semantic key)
    if (hit := await semantic_cache.get(prompt, model.id)): return hit
    # 4. enforce per-tenant budget
    await tenant_budget.consume(req.enterprise_id, estimated_tokens)
    # 5. send through adapter
    resp = await PROVIDERS[model.provider].infer(req_for(model, prompt))
    # 6. audit (K-6) — this is where llm_router today MISSES
    await audit.log_decision(req.enterprise_id, decision_type="llm_call", model_id=model.id, ...)
    # 7. cache + return
    await semantic_cache.put(prompt, model.id, resp)
    return resp
```

Every step is backend-independent. Swapping Qwen 14B → vLLM-served Qwen 72B means: insert row in `llm_models`, flip `traffic_pct`, done.

### 6.5 Upgrade flow (the "doesn't break anything" part)

New model onboarding, four stages:

```
Stage 1 — Dark deploy                | status='shadow', traffic_pct=0
                                     | every prod request is mirrored (fire-and-forget); response
                                     | discarded; log cost, latency, output into `llm_shadow_runs`.
                                     | Duration: 48-72h. Validator runs auto-regression tests.

Stage 2 — Canary                     | status='canary', traffic_pct=5
                                     | 5% of real traffic routed to new model; rollback trigger:
                                     | error_rate(new) > 2× error_rate(prod-30m-baseline)
                                     |   OR latency_p95(new) > 1.5× p95(prod).
                                     | Auto-rollback rewrites the routing table row to 0%.

Stage 3 — Gradual ramp               | 5% → 25% → 50% → 100% over 7 days
                                     | Each step gated on: quality score (LLM-judge eval on
                                     | 200-prompt golden set), cost delta acceptable.

Stage 4 — Retire old                 | old model status='deprecated', replaced_by=new.model_id
                                     | Drain period 30 days (cache expiry).
                                     | Final status='retired'; instances deallocated.
```

All controlled from a `POST /admin/models/{id}/ramp` endpoint; no `ai-orchestrator` redeploy.

### 6.6 Inference infrastructure upgrade path

| Stage | Today | Target when stronger model deployed |
|---|---|---|
| Serving | Ollama single-replica, no batching | **vLLM pool, 4–8 replicas**, continuous batching, PagedAttention (5–10× throughput vs Ollama at same GPU) |
| Topology | Direct `POST /api/generate` | **Kafka-backed request queue** for long prompts (>4K tokens) — request goes to `llm.infer.requests`, workers reply to `llm.infer.responses`; API caller awaits on Redis Stream or SSE. Short prompts still synchronous. |
| Scaling | 1 GPU, no autoscale | **HPA on GPU utilization + queue depth**; Kubernetes NodePool with taints for GPU |
| Quantization | None documented | **FP8 / AWQ quantization** in vLLM; halves VRAM; 72B model fits on 2× H100 instead of 4× |
| Routing | No cache | **Semantic cache**: `sha256(normalized_prompt)` + `model_capability_tier`; upgrade invalidates cache for the **same tier** not globally (so upgrading reasoning model doesn't blow the embed cache) |

### 6.7 Non-negotiable boundaries the upgrade plan preserves

These four properties are the contract between `llm-gateway` and every caller. If a new model breaks any of them, don't ship.

1. **Same response envelope** — `{request_id, text, model_id, tokens_in, tokens_out, latency_ms, cache_hit, cost_vnd}`. New model gets a new `model_id`; callers never parse it.
2. **Same privacy guarantees** — `privacy_mode='strict'` still routes only to on-prem. Registry row for new model must declare `provider∈{ollama,vllm}` to be eligible for strict mode.
3. **Same K-5 PII redaction** before any external provider. Adapter responsibility, not caller's.
4. **Same K-6 audit log** row written. Stronger model ⇒ richer reasoning field, but the row exists.

### 6.8 What the caller code stays looking like — forever

From today's insights engine:
```python
text = await llm_router.complete(prompt, task="insight", consent_external=False, enterprise_id=eid)
```
becomes tomorrow's:
```python
resp = await llm_gw.infer(
    task_type="INSIGHT_GEN",
    prompt_template_id="insight.three_panel.v2",
    variables={"analysis_run_id": run_id, "context": summary},
    max_tokens=2000,
)
text = resp.text
```
From that moment on, **we can swap Qwen 14B → 72B → Llama 3.3 → a future open-source model → an internal fine-tune — without changing this line**. Every caller in `ai-orchestrator` becomes backend-agnostic.

---

## Part 7 — Performance targets and violators

### 7.1 API latency (gateway-visible)

| Endpoint class | Target P50 | Target P95 | Target P99 | Violator today |
|---|---:|---:|---:|---|
| Login (`POST /auth/login`) | 80 ms | 250 ms | 500 ms | `BCryptPasswordEncoder(12)` = ~280ms per attempt (`SecurityConfig.java:33`). At cost=12 on a commodity CPU. |
| JWT-auth'd read (`GET /api/v1/...`) | 30 ms | 100 ms | 250 ms | `JwtAuthFilter` + `RateLimitFilter` = 5 Redis RTTs = ~5ms P50, ~50ms tail under load |
| Workspace CRUD | 40 ms | 120 ms | 300 ms | Unreachable today (SecurityConfig) |
| Pipeline upload ack | 100 ms | 250 ms | 500 ms | OK — async task |
| Dashboard load (`GET /dashboard/state`) | 300 ms | 800 ms | 1500 ms | Today: full Postgres scan of `analysis_results` — no MV; will violate at 10K tenants |
| LLM insight (`POST /insights/generate`) | 1500 ms | 4000 ms | 8000 ms | Today: Ollama queue serializes → >60s at 50 concurrent callers |

### 7.2 Pipeline SLA (end-to-end bronze)

| File size | Row count | Target P95 | Today P95 | Gap |
|---|---:|---:|---:|---|
| 1 MB | 10K rows | 5 s | ~12 s | row-by-row INSERT |
| 10 MB | 100K rows | 30 s | ~120 s | same |
| 100 MB | 1M rows | 3 min | ~20 min | same + single-Postgres backpressure |
| 1 GB | 10M rows | 20 min | OOMKilled | full materialisation in `clean.py` |

### 7.3 Kafka lag SLO

| Topic | Target lag | Today |
|---|---:|---|
| `pipeline.silver.complete` | < 5 s | unmeasured; any orchestrator restart loses events |
| `llm.infer.requests` (proposed) | < 500 ms | n/a |
| `kaori.billing.events` (doc-only) | < 60 s | **topic doesn't exist** |

---

## Part 8 — Top 10 fixes (scaling-specific, P0 first)

Each fix: priority, what breaks if skipped, effort (S/M/L), concrete location.

| # | Pri | Fix | What breaks without it | Effort | Where |
|---:|:---:|---|---|:---:|---|
| 1 | **P0** | **Stop storing Bronze in Postgres**. Move to S3 Parquet; keep only metadata in `bronze_files`. Retire `bronze_rows` table. | Postgres dies at first large-enterprise ingest (>10M rows) | L | `bronze/ingestor.py`, new `bronze/s3_writer.py`, migration `008_drop_bronze_rows.sql`, clean.py reader rewrite |
| 2 | **P0** | **Replace row-by-row INSERT with `copy_records_to_table`** for bronze and silver landings. Stream reads with asyncpg server cursors. | 100K-row pipelines take 100+ s each; concurrent pipelines starve connections | M | `bronze/ingestor.py:144-156`, `routers/clean.py:103-208` |
| 3 | **P0** | **Kafka: partition by `enterprise_id`, manual commit, DLQ topic per stream, replication.factor=3, 3-broker cluster.** | Any consumer restart = lost events; per-tenant ordering broken; outage on any broker | M | `data-pipeline/shared/kafka_producer.py:41`, `ai-orchestrator/consumers/pipeline_consumer.py:26-34`, `docker-compose.yml:46-66` |
| 4 | **P0** | **Transactional outbox** — add `outbox` table + publisher worker; kill silent `send_event` swallow. | Billing and audit diverge from event stream; drift is silent | L | new `data-pipeline/shared/outbox.py`, migration `008_outbox.sql` |
| 5 | **P0** | **LLM Gateway service + model registry + provider adapters** (Part 6). Replace direct Ollama calls. | Any model upgrade is a code change + redeploy; GPU serialization kills insights SLA | L | new `services/llm-gateway/`, migrations `009_llm_models.sql`, delete `ai-orchestrator/engine/llm_router.py` |
| 6 | **P0** | **Redis cluster** (3 shards min, RDB + AOF). Route blacklist/rate-limit/refresh tokens by tenant-hashed key. Add Caffeine in-process cache layer at gateway. | Redis single-node dies at 100K ops/s; forced mass re-login on reboot | M | `docker-compose.yml:26-36`, `gateway/filter/*Filter.java`, `auth-service/AuthService.java` |
| 7 | **P0** | **Enforce RLS**: switch pool to `kaori_app` role + pool wrapper that `SET LOCAL app.enterprise_id` per tenant-scoped query. | One missed `WHERE enterprise_id=$1` = cross-tenant leak | L | `data-pipeline/shared/db.py`, every router, `ai-orchestrator/shared/db.py` |
| 8 | **P1** | **Silver in ClickHouse** partitioned by `(tenant_shard, yyyymm)`. Postgres keeps Gold only. | Silver queries over 10M rows unusable on Postgres | L | new `infrastructure/clickhouse/`, `clean.py` write path, reader endpoints |
| 9 | **P1** | **Per-tenant quotas**: pipeline runs/day, LLM tokens/day, Kafka produce rate. Redis counters + plan-based caps. | Noisy-neighbor: one enterprise starves the GPU and Kafka for everyone | M | `gateway`, `llm-gateway`, Kafka broker quota config |
| 10 | **P1** | **Tenant tier routing**: Pilot / SME / Large. Shard Postgres 16-way by `hash(enterprise_id)`; dedicated DB for top 1K large tenants. | Single-Postgres reliance doesn't survive past 30-50K tenants even with the above fixes | L | connection routing layer, migration scripts, deployment topology |

(Also applies: items A–L in `ARCHITECTURE_REVIEW.md §5` — the security/correctness P0s must also land; this table is additional.)

---

## Part 9 — Verdict

**Can this system scale to 100,000 tenants?** No — not in its current topology. The structural ceilings are single Postgres, single Kafka broker, single Redis, single Ollama. **Each hits its limit well under 100K tenants** (Postgres dies at the first 10M-row ingest, Ollama at 100 concurrent insights, Redis at 20K QPS steady).

**What breaks first?** The LLM path. `ai-orchestrator/engine/llm_router.py → Ollama single-replica → Qwen 14B` serializes every insight request. At ~10 req/s throughput with 2K req/s demand the P99 is literal minutes. Users will see timeouts before anyone complains about data volume.

**The single biggest architectural mistake.** LLM calls are embedded directly in `ai-orchestrator`. That makes the inference path a compile-time dependency of the insights engine; model version, request shape, provider identity, and batching strategy all leak into business code. Every scaling choice (queue, batch, cache, route, version, quota) is impossible to add without surgery on the insights engine. Extracting **LLM Gateway** (Part 6) is the single change that unlocks the most downstream scaling work — and it's also the change the user explicitly asked for: a stronger model should strengthen the system, not break it. With the gateway in place, the new model is a registry row. Without it, every model upgrade is an `ai-orchestrator` redeploy.

**What MUST be fixed before scaling.**
1. Move Bronze out of Postgres.
2. LLM Gateway + model registry + vLLM pool (Part 6).
3. Kafka cluster + partition-by-tenant + DLQ + outbox.
4. Redis cluster + Caffeine front-cache.
5. RLS actually enforced.
6. Per-tenant quotas.

Everything else (ClickHouse migration, tenant sharding, Gold MV) is a Phase-2 follow-up once the above six land. The six P0s above are weeks of work, not quarters. The order matters: do #2 (LLM Gateway) and #3 (Kafka cluster) first because every other fix depends on knowing the inference and event backbone are not the bottleneck.
