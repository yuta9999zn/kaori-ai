# Kaori AI — Architecture Review (Strict)

> **Reviewer:** senior architect + principal engineer
> **Date:** 2026-04-25
> **Scope:** Phase 1 services (`auth-service`, `api-gateway`, `data-pipeline`, `ai-orchestrator`, `notification-service`), Postgres migrations, Kafka topology, tenant-isolation model.
> **Evidence rule:** every claim points to a file + line or a topic name in the repo. No generic consulting language.

---

## 1. System Overview (as implemented, not as documented)

### 1.1 Services actually deployed (per `docker-compose.yml`)

| Service | Port | Language | Framework | Purpose |
|---|---|---|---|---|
| `api-gateway` | 8080 | Java 21 | Spring Cloud Gateway 3.2.5 | JWT filter, rate limit, path-based routing |
| `auth-service` | 8091 | Java 21 | Spring Boot 3.2.5 | Login/refresh/logout, workspace activation, platform keys, workspaces (new) |
| `data-pipeline` | 8092 | Python 3 | FastAPI 0.111 | Bronze ingest, canonical mapping, Silver cleaning |
| `ai-orchestrator` | 8093 | Python 3 | FastAPI 0.111 | Analytics runner, dashboard, LLM router, Kafka consumer |
| `notification-service` | 8094 | Python 3 | FastAPI | SMTP sender (F-NEW1) |
| `frontend` | 3000 | TypeScript | Next.js 16 | UI |
| Postgres 15 + pgvector, Redis 7, Kafka 7.5, Ollama (Qwen 2.5) | — | | | infra |

### 1.2 Data flow (actual, reconstructed from code)

```
Frontend
  │ POST /api/v1/upload      (JWT in header)
  ▼
api-gateway (JwtAuthFilter → RateLimitFilter → RouteConfig)
  │ injects X-User-ID / X-Enterprise-ID / X-User-Role / X-Trace-ID
  │ rewrites /api/v1/upload → /upload
  ▼
data-pipeline:8092
  POST /upload   (routers/upload.py)
    ingest_file()  (bronze/ingestor.py)
      SHA-256 → pipeline_runs (INSERT, status='uploading')
      asyncio.create_task(_parse_and_land)      ← background, no durability
      Kafka: pipeline.upload.received           ← actual topic
    _parse_and_land()
      bronze_files / bronze_rows                ← row-by-row INSERT loop
      pipeline_runs.status='bronze_complete'
      Kafka: pipeline.bronze.complete

  POST /schema   (routers/schema.py)
    map_columns()
    decision_audit_log INSERT (per column)      ← only path that honors K-6
    pipeline_runs.status='schema_review'

  POST /schema/confirm
    canonical_schemas UPSERT (per file × per override — see §2.3)
    pipeline_runs.status='cleaning_pending'

  POST /clean/apply
    DELETE silver_rows WHERE run_id=…           ← idempotent re-apply
    silver_rows row-by-row INSERT
    cleaning_rules_applied INSERT (per rule)
    pipeline_runs.status='silver_complete'
    Kafka: pipeline.silver.complete             ← also re-emitted by analyze.py:59

ai-orchestrator:8093  (consumers/pipeline_consumer.py)
  subscribes: pipeline.silver.complete, pipeline.analysis.complete
  auto_offset_reset='latest', enable_auto_commit=True, no DLQ
  On pipeline.silver.complete → run_analysis_for_run()
  analysis_results INSERT
  Kafka: pipeline.analysis.complete             (log-only)
```

### 1.3 Real Kafka topology

| Topic produced | Producer (file:line) | Consumed by |
|---|---|---|
| `pipeline.upload.received` | `data-pipeline/bronze/ingestor.py:97` | nobody |
| `pipeline.bronze.complete` | `data-pipeline/bronze/ingestor.py:168` | nobody |
| `pipeline.silver.complete` | `data-pipeline/routers/clean.py:236` AND `data-pipeline/routers/analyze.py:59` | `ai-orchestrator/consumers/pipeline_consumer.py:27` |
| `pipeline.analysis.complete` | `ai-orchestrator/analytics/runner.py:78` | `ai-orchestrator` (log-only) |

Topics listed in `CLAUDE.md §7` — `kaori.ingest.bronze`, `kaori.pipeline.events`, `kaori.decisions.log`, `kaori.feedback.actions`, `kaori.billing.events`, `kaori.alerts.fire`, `kaori.audit.internal`, `kaori.dlq.*` — **none of them exist in code**. Zero producers, zero consumers. The documented event backbone is fiction.

### 1.4 Hidden couplings / implicit dependencies

1. **`auth-service` → `notification-service` is direct HTTP** (`docker-compose.yml:138` sets `NOTIFICATION_SERVICE_URL`). The `kaori.alerts.fire` topic documented in CLAUDE.md is not used. Loss of `notification-service` = sync failure of password-reset / quota-alert, not a backlog on Kafka.
2. **`pipeline.silver.complete` is emitted from two semantically different places** — after cleaning (clean.py) and on analysis-run creation (analyze.py). Consumer treats them identically. Double-dispatch risk when both fire.
3. **`analysis_runs` table is created in both `001_init.sql:257` and later `006_analysis_tables.sql`** (tracker says F-020 schema evolved). `CREATE TABLE IF NOT EXISTS` makes the second a no-op — later columns are silently missing if 001 ran first.
4. **RLS session variable `app.enterprise_id`** — policies reference `current_setting('app.enterprise_id', TRUE)::UUID` (`001_init.sql:317, 327, 337`, `005_rls.sql`), but **nothing in the codebase ever sets it** (grep for `set_config`, `SET LOCAL app.`, `app.enterprise_id` in `services/` → zero hits).

### 1.5 Critical path — what breaks the system

| Break point | Cascading failure |
|---|---|
| `auth-service` `SecurityConfig` (see §2.1) | Entire `/api/v1/platform/**` and any future `/api/v1/enterprise/**` returns **403**. F-009, F-010, F-013, F-016, F-008 are all unreachable from the frontend. |
| `api-gateway` JWT filter | Whole product offline (single point, no HA in compose). |
| `ai-orchestrator` consumer offline even briefly | `pipeline.silver.complete` events lost forever (`auto_offset_reset=latest`, no retry, no DLQ). Analyses silently never run. |
| PostgreSQL | Everything dies. No read replicas. RLS policies exist but are bypassed. |
| Ollama | `llm_router._call_qwen` → `raise_for_status` → 500 propagates. No graceful degradation. |

---

## 2. Spec vs Implementation Gaps

### 2.1 Missing / broken endpoints claimed as ✅ in `phase_1_execution.md`

| Tracker claim | Reality | Evidence |
|---|---|---|
| **F-009** POST/GET/DELETE `/api/v1/platform/keys` = ✅ | Code exists (`PlatformController.java`) but is **unreachable** — SecurityConfig blocks it. | `auth-service/security/SecurityConfig.java:25-26`: only `/auth/**` and `/actuator/health` are permitAll; `anyRequest().authenticated()` is set with **no authentication mechanism configured** (no `httpBasic()`, no `oauth2ResourceServer()`, no JWT decoder, no custom filter that populates `SecurityContext`). Every non-/auth request → 403. |
| **F-010** Platform Admin CRUD `/api/v1/platform/admins` = ✅ | **No controller exists.** | `grep -l PlatformAdmin` in `auth-service/src/main/java` → zero hits. Only `AuthController`, `PlatformController` (keys only), `WorkspaceController` (just written) exist. |
| **F-013** Enterprise Onboarding `/enterprise/onboarding` = ✅ | `/auth/workspace/activate` exists (`AuthController.java:78`); `/enterprise/onboarding` does **not**. | Two different endpoints conflated. |
| **F-014** Enterprise RBAC middleware = ✅ | `JwtAuthFilter` validates signature + injects headers. **It does NOT check `role` claim** anywhere. | `gateway/filter/JwtAuthFilter.java:74-97` — only verifies token type=`access`, never inspects role. No gateway route has role predicate. |
| **F-016** `/api/v1/enterprise/settings` = ✅ | No `EnterpriseSettingsController` in any service. | grep-confirmed. |
| **F-027** `/api/v1/charts/render` = ✅ | No such handler in `ai-orchestrator/routers/` or `frontend`. | grep-confirmed. |

### 2.2 Wrong response shapes

| Spec | Actual | File |
|---|---|---|
| CLAUDE.md §6: success envelope `{ data, meta: { request_id, trace_id, server_time }, errors, warnings }` | `AuthController` returns raw DTO (`{accessToken, refreshToken, role, ...}`) with no envelope | `auth-service/controller/AuthController.java:24-35` |
| Same spec | `PlatformController` uses `{data, meta:{warning}}` — `meta` is a single-key warning string, not the prescribed trace fields | `auth-service/controller/PlatformController.java:39-47` |
| CLAUDE.md K-14: errors = RFC 7807 `application/problem+json` | `AuthController` returns `{error, message, status, lockoutRemainingSeconds}` (not Problem Details) | `auth-service/controller/AuthController.java:31-34` |
| Same K-14 | `PlatformController`, `WorkspaceController` return `{type, title, status, detail}` but **not** with `Content-Type: application/problem+json` — default `application/json` | every `problem(...)` helper |

### 2.3 Logical bugs in implemented code

1. **`data-pipeline/routers/schema.py:128-142`** — confirm-schema writes every override against every file. For (N files × M overrides), it runs N×M upserts and creates orphan `canonical_schemas` rows in files that don't contain that column. No existence check before upsert.
2. **`auth-service/service/AuthService.java:70-79`** — login-failure lockout: `redis.opsForValue().increment(countKey)` then `redis.expire(countKey, lockoutDurationSeconds, ...)` on every failed attempt. The expiry **resets on every failure** — an attacker pacing one attempt every 14 min never hits 5 within any single 15-min window → no lockout ever fires.
3. **`auth-service/service/AuthService.java:73-74`** — `increment(countKey)` returns the new count but the code ignores it and does a separate `.get(countKey)` → race window where two concurrent 5th attempts both read count=5 and both fire the lockout path (harmless here, but pattern is wrong).
4. **`data-pipeline/bronze/ingestor.py:145`** — `row_hash = hashlib.sha256(str(sorted(row.items())).encode()).hexdigest()`. Python `dict.items()` iteration ordering + `str()` representation are Python-version-dependent; hashes are not stable. K-8 idempotency at row level is therefore non-portable.
5. **`data-pipeline/routers/clean.py:186-208`** — inside a single transaction, deletes all prior silver rows then reinserts row-by-row with `await conn.execute(...)`. For 100k rows this is ~100k network round-trips and one giant transaction → massive WAL, long lock on silver table, OOM risk in Python workers (all silver records are materialised in memory first, lines 122-182).
6. **`ai-orchestrator/consumers/pipeline_consumer.py:33-34`** — `auto_offset_reset='latest'` + `enable_auto_commit=True` + single consumer group + **no DLQ / no retry loop**. Any downtime during a silver-complete event → event gone; any handler exception inside `_dispatch` is caught and logged (line 44-50) but offset still auto-commits. Silent data-loss by design.
7. **`data-pipeline/shared/kafka_producer.py:43-45`** — `send_event` swallows producer exceptions: "Don't raise — pipeline continues even if Kafka is unavailable". DB state advances (pipeline_runs.status updated) but downstream never hears. K-6 audit chain broken without surfacing.
8. **`gateway/filter/RateLimitFilter.java:48-62`** — sliding-window implemented as four non-atomic Redis ops (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`, `EXPIRE`). Concurrent requests can all see count < limit and pass. Should be a single LUA script.

### 2.4 Invariant status

| Invariant | Status | Evidence |
|---|---|---|
| K-1 tenant filter on every SELECT | **Partial** — enforced only in app-layer SQL strings; RLS exists in DDL but is bypassed (see §1.4). One missing `WHERE enterprise_id=$1` = tenant leak. |
| K-2 Bronze append-only | ✅ | DB-level `RULE … DO INSTEAD NOTHING` on `decision_audit_log`; bronze tables have no UPDATE/DELETE paths in code. |
| K-3 all LLM through router | ✅ | only `llm_router.py` imports anthropic/openai SDKs (via httpx). |
| K-4 external AI needs consent | ✅ | `llm_router.py:44-54` checks `consent_external`. |
| K-5 PII redaction before external | Partial | only 3 regexes: email, VN phone, long digit. No name masking despite doc claim of `<NAME_1>`. Redaction only before external — assumed safe if Qwen stays local. |
| **K-6 decision audit on every automated decision** | **BROKEN** | Only `schema.py:77-92` writes audit rows. Nothing in `llm_router.py`, `clean.py`, `analytics/runner.py`, `AuthService.java`, `PlatformKeyService.java` writes audit. Silent holes everywhere. |
| K-7 JWT claims forwarded as X-* | ✅ gateway injects; downstream **trusts without re-verification** — bypassing gateway would spoof tenant. |
| K-8 SHA-256 idempotency | ✅ file-level (`ingestor.py:54,65`); ❌ row-level (see §2.3 #4). |
| K-9 NUMERIC precision | ✅ all migrations use `NUMERIC(5,4)` / `NUMERIC(14,4)`; no FLOAT observed. |
| K-10 1 question = 1 framework | Not verifiable — F-025 router not wired to gateway. |
| K-11 billing = COUNT DISTINCT customer | **BROKEN** — F-031 not started; no cron exists; no write to `enterprise_monthly_billing` anywhere. |
| K-12 tenant_id never from query string | ✅ comes from JWT headers. |
| K-13 Idempotency-Key header | **BROKEN** — grep for `Idempotency-Key` → zero hits. POST mutations have no dedupe. |
| K-14 RFC 7807 error format | Partial & inconsistent (see §2.2). |

---

## 3. SWOT

### Strengths

| # | Strength | Evidence |
|---|---|---|
| S1 | **Kafka decouples `data-pipeline` from `ai-orchestrator`** for the silver→analysis hop. When it works, pipeline can write silver and return without blocking on LLM time. | `data-pipeline/routers/clean.py:236` + `ai-orchestrator/consumers/pipeline_consumer.py:27`. |
| S2 | **File-level idempotency via SHA-256 works.** Uploading the same file twice returns the original `run_id`. | `bronze/ingestor.py:63-74`. |
| S3 | **JWT blacklist on logout** via Redis `blacklist:{token}` key with TTL = token expiry. Prevents stolen-token replay until expiry. | `gateway/filter/JwtAuthFilter.java:66-72` + `auth-service/service/AuthService.java:117-123`. |
| S4 | **Anti-enumeration on forgot-password** — always 200 even for unknown email. | `auth-service/controller/AuthController.java:56-60`; `AuthService.java:165`. |
| S5 | **LLM PII redaction before external calls** (email, VN phone, ID number) — at least narrowly correct for Vietnamese data. | `ai-orchestrator/engine/llm_router.py:22-26, 45-51`. |
| S6 | **Medallion DDL is correct.** `NUMERIC(5,4)` / `NUMERIC(14,4)` consistently used; `bronze_rows` append-only rule in place. | `migrations/001_init.sql`, `003_silver_gold.sql`. |

### Weaknesses

| # | Weakness | Evidence |
|---|---|---|
| W1 | `auth-service` security posture blocks its own endpoints. | `SecurityConfig.java:25-26` — discussed in §2.1. |
| W2 | Kafka topology is documentation-only. Real topic names diverge completely. | §1.3 table. |
| W3 | RLS is decorative: policies exist, session variable never set, pool uses superuser. | §1.4 point 4. |
| W4 | No DLQ, no retry on the only working consumer. | `ai-orchestrator/consumers/pipeline_consumer.py:33-34`. |
| W5 | K-6 audit log is claimed universal but implemented in one file. | §2.4 K-6. |
| W6 | N+1 INSERT loops in Bronze and Silver landing. | `bronze/ingestor.py:144-156`, `clean.py:194-208`. |
| W7 | No Idempotency-Key, despite documented invariant K-13. | grep-confirmed. |
| W8 | Response envelope / error format not consistent across controllers. | §2.2. |
| W9 | Background `asyncio.create_task(_parse_and_land)` in upload — process crash between task spawn and completion leaves `pipeline_runs` stuck at `'uploading'` forever; re-upload is treated as duplicate and short-circuits. | `bronze/ingestor.py:92-105`. |
| W10 | No observability for Kafka lag, DLQ depth, queue depth. Prometheus is wired for HTTP metrics only (`Instrumentator().instrument(app).expose(app)`). | `data-pipeline/main.py:53`. |

### Opportunities

| # | What | Payoff |
|---|---|---|
| O1 | Replace per-row `INSERT` with `COPY FROM STDIN` or `executemany` — easy 50×+ throughput on bronze/silver landing. | Currently ingestion is the pipeline bottleneck above ~100K rows. |
| O2 | Introduce a Redis/Postgres-backed outbox table for Kafka publishes (transactional outbox pattern). Emit + DB commit atomic → no more silent event loss. | Unlocks real event-driven compaction for F-031, F-032. |
| O3 | Switch LLM Router to rule-based routing per CLAUDE.md §8 (task-based dispatch, privacy_mode, embedding split to BGE-M3). Today every call that doesn't explicitly opt in external → Qwen, regardless of task. | Matches documented architecture; enables swap of Qwen for smaller model on cheap tasks. |
| O4 | Move authorization into gateway's `RouteConfig` predicates (`predicates: [..., Role=SUPER_ADMIN]`) — fix the RBAC gap in one place. | Closes the privilege-escalation hole. |
| O5 | Batch `decision_audit_log` writes per request with a single `INSERT ... SELECT UNNEST(...)`. Today `schema.py:78-92` writes one row per column inside an open transaction. | Unblocks schema-review perf for large files. |
| O6 | Add materialized view for `v_billing_summary` (referenced in F-011 tracker) and TTL-refreshed by APScheduler. | F-011 ships without F-031 blocking it. |

### Threats

| # | Scenario | Concrete risk |
|---|---|---|
| T1 | Attacker with valid JWT (any role) hits `/api/v1/platform/keys/*`. | Today: gets 403 from auth-service's blanket deny (§2.1). Tomorrow, when SecurityConfig is fixed to permit these paths, without a role check in the gateway or a `@PreAuthorize` on the controller, any MANAGER can create/revoke workspace keys. **Privilege escalation.** |
| T2 | Cross-tenant data via missed `WHERE enterprise_id=$1`. | RLS can't catch it (bypass under superuser). Any new endpoint author forgets the filter once → tenant leak shipped. |
| T3 | `ai-orchestrator` container restart during a batch of uploads. | `pipeline.silver.complete` events between last commit and restart are lost (auto-commit + latest). Analyses silently never run; user sees "queued" forever. |
| T4 | Large file upload (50 MB, 200K rows). | `_read_chunked` materialises all chunks in a Python list (`ingestor.py:187-199`). Concurrent uploads → memory explosion. Row-by-row inserts → >5 min transaction → lock contention. |
| T5 | PII leak via the internal path. | K-5 redaction runs only before external calls. A compromised or logging-enabled Ollama forwards raw PII. No outbound DLP. |
| T6 | Billing (K-11) drift. | F-031 not started. When it is, writes to `enterprise_monthly_billing` will race the manual test endpoint (`POST /internal/billing/cron-run`) → double-counting unless the cron uses `ON CONFLICT DO UPDATE` with guard columns. Not yet designed. |
| T7 | Login timer-reset (§2.3 #2). | Brute force not blocked by the documented 5-in-15-min policy. Any leaked email becomes spray-able. |
| T8 | Frontend can't talk to new endpoints. | Gateway route for `/api/v1/platform/workspaces` is not in `RouteConfig.java` (T-F008-05 still `not_started`). The new controller is a black box from the frontend's perspective. |

---

## 4. Critical Issues — Top 10

| # | Sev | Issue | Impact | Root cause | Where |
|---|---|---|---|---|---|
| 1 | **P0** | `auth-service` blocks its own platform endpoints | `GET/POST /api/v1/platform/keys`, `/api/v1/platform/workspaces` etc. return 403 in prod; Phase 1 F-009 + F-008 are unshippable | `anyRequest().authenticated()` with no auth provider + no matcher added as new controllers landed | `auth-service/security/SecurityConfig.java:22-27` |
| 2 | **P0** | Kafka topics in code ≠ topics in docs | F-031 billing cron, F-025 decision stream, F-NEW1 alerts all designed against topics that don't exist; new features built on the doc will silently not flow | Doc drift; no validation between CLAUDE.md §7 and producer/consumer literals | `data-pipeline/bronze/ingestor.py:97,168`, `data-pipeline/routers/clean.py:236`, `ai-orchestrator/consumers/pipeline_consumer.py:27`, `CLAUDE.md §7` |
| 3 | **P0** | RBAC not enforced anywhere | Any JWT with role=VIEWER can hit platform admin endpoints once issue #1 is fixed. Claims in PlatformController comments are unbacked | Gateway JWT filter extracts role but no matcher uses it; no `@PreAuthorize` on controllers | `gateway/filter/JwtAuthFilter.java:86-97`, `auth-service/controller/PlatformController.java:28-31` (comment-only guarantee) |
| 4 | **P0** | RLS is decorative | Single missing `WHERE enterprise_id=$1` in any future endpoint = cross-tenant data leak; DB will not save you | `asyncpg` pool uses superuser `kaori`, code never calls `SET LOCAL app.enterprise_id` | `data-pipeline/shared/db.py:13-17`, `migrations/001_init.sql:316-339`, `migrations/005_rls.sql:27-114` |
| 5 | **P0** | Silent Kafka failure + lossy consumer | Pipeline state advances in DB; event stream silently drops. Any orchestrator downtime = analyses never run, no alarm | `send_event` catches & logs; consumer uses `auto_offset_reset='latest'` + `enable_auto_commit=True` + no DLQ | `data-pipeline/shared/kafka_producer.py:40-45`, `ai-orchestrator/consumers/pipeline_consumer.py:30-34` |
| 6 | **P0** | K-6 audit log implemented in exactly one place | Insights, LLM routing, cleaning rules, auth events are undecidable forensically; F-029 will have almost no data to show | Single-dev implementation of schema.py; no shared audit helper | everywhere **except** `data-pipeline/routers/schema.py:77-92` |
| 7 | **P1** | Tracker claims F-010, F-013, F-014, F-016, F-027 done — controllers / endpoints don't exist | Phase 1 "71% done" is inflated; Phase 2 planning based on false prerequisites | | `docs/phase_1_execution.md` vs `auth-service/src/main/java/…/controller/` (3 files only) |
| 8 | **P1** | N+1 row-level INSERTs in bronze + silver landing | 100k-row upload = >2 min just to persist; concurrent uploads contend on locks; OOM risk from full materialization | Naive `await conn.execute(INSERT …)` per row; entire bronze set read into Python before silver write | `bronze/ingestor.py:144-156`, `routers/clean.py:103-208` |
| 9 | **P1** | Login-lockout never fires under paced brute force | `Redis.expire()` resets on every failed attempt | pattern bug | `auth-service/service/AuthService.java:70-79` |
| 10 | **P1** | Background `asyncio.create_task(_parse_and_land)` has no durability | Process crash between task spawn and bronze write → `pipeline_runs` stuck at `'uploading'`; subsequent re-upload short-circuits as "duplicate" — permanent soft deadlock | No queue / no outbox / no resumable worker | `bronze/ingestor.py:92-105`, duplicate check at lines 63-74 |

---

## 5. Improvement Plan

### P0 (fix before any new Phase 1 feature ships)

| # | Change | Where | Effort | Priority |
|---|---|---|---|---|
| A | Add role-based matchers **and** a trusted-header authentication filter to `auth-service`. Introduce `TrustedGatewayAuthFilter` that reads `X-User-Role` from the authenticated gateway and populates `SecurityContext` with authorities; require `hasAnyRole("SUPER_ADMIN","ADMIN")` on `/api/v1/platform/**`. **Also** terminate TLS at the gateway and lock inter-service traffic to an internal network so header spoofing isn't an outside threat. | `auth-service/security/SecurityConfig.java`, new `TrustedGatewayAuthFilter.java` | M | P0 — issues 1, 3 |
| B | Rename all Kafka literals in code to match CLAUDE.md §7, or rewrite the doc to match code — pick one. Add a `kafka_topics.py` / `KafkaTopics.java` const module; lint-ban string literals elsewhere. Add a Kafka-UI smoke test at startup that asserts topics exist. | `data-pipeline/shared/kafka_topics.py` (new), `ai-orchestrator/shared/kafka_topics.py` (new), CLAUDE.md §7 | M | P0 — issue 2 |
| C | Implement transactional outbox: single `outbox` table, producer reads + publishes + deletes with retry. Kill the "Don't raise" swallow. | `data-pipeline/shared/outbox.py` (new), DB migration `008_outbox.sql`, `bronze/ingestor.py`, `routers/clean.py`, `routers/analyze.py` | L | P0 — issue 5 |
| D | Consumer: switch to `auto_offset_reset='earliest'` on first assignment, `enable_auto_commit=False`, manual commit after successful handler; add DLQ topic `pipeline.silver.complete.dlq` after N retries. | `ai-orchestrator/consumers/pipeline_consumer.py` | M | P0 — issue 5 |
| E | Enforce RLS: switch asyncpg DSN to `kaori_app` role, add `SET LOCAL app.enterprise_id = $1` in a helper that wraps `pool.acquire()` and extracts `x_enterprise_id` from the FastAPI Header dep. Reject handlers that don't use it via a custom dependency. | `data-pipeline/shared/db.py`, every router in `data-pipeline/routers/*.py`, `ai-orchestrator/shared/db.py` | L | P0 — issue 4 |
| F | Create shared `audit.log_decision()` helper in both Python services; **call it** in `llm_router.complete()`, `clean.apply`, `analytics/runner.run_analysis_for_run`, and on auth events (login success, MFA, key revoke, workspace deactivate). | `data-pipeline/shared/audit.py`, `ai-orchestrator/shared/audit.py`, each call site | M | P0 — issue 6 |

### P1 (fix within sprint 1.2–1.3)

| # | Change | Where | Effort | Priority |
|---|---|---|---|---|
| G | Replace `await conn.execute(INSERT ...)` loops with `asyncpg.copy_records_to_table` or `executemany` for bronze_rows + silver_rows writes. | `bronze/ingestor.py:144-156`, `routers/clean.py:194-208` | M | P1 — issue 8 |
| H | Fix login lockout: use atomic `INCR` return value; only `EXPIRE` on first increment (`count == 1`), never reset it. | `auth-service/service/AuthService.java:70-79` | S | P1 — issue 9 |
| I | Add `Idempotency-Key` header support: middleware that stores `sha256(idempotency_key + tenant_id + path)` in Redis (24h TTL) with the response body. Required on all POST mutations. | Gateway filter + service-level middleware | M | K-13 |
| J | Normalize response envelope: every controller returns `{data, meta:{request_id, trace_id, server_time}, errors, warnings}`; errors return `application/problem+json`. Introduce a `ResponseBodyAdvice` in Spring and a FastAPI middleware. | `auth-service/common/EnvelopeAdvice.java` (new), `data-pipeline/shared/envelope.py` (new) | M | issue in §2.2 |
| K | Add gateway route for `/api/v1/platform/workspaces` and role predicate. | `gateway/config/RouteConfig.java` (T-F008-05) | S | unblocks F-008 |
| L | Background `_parse_and_land` → replace `asyncio.create_task` with a durable job: either persist a row to a `parse_jobs` table and have a worker consume it, or publish `pipeline.bronze.pending` and make `_parse_and_land` a consumer. | `bronze/ingestor.py:92-105` | L | issue 10 |

### P2 (tech debt / next quarter)

| # | Change | Effort |
|---|---|---|
| M | Rewrite `RateLimitFilter` as an atomic LUA script in Redis. | S |
| N | Consolidate duplicate `CREATE TABLE` statements across 001/002 (`decision_audit_log`, `analysis_runs`). Use a single canonical migration and mark later ones as "alter only". | M |
| O | Replace clean.py's delete-reinsert with an idempotency key + partition swap. | M |
| P | Implement LLM Router rules 1–6 from CLAUDE.md §8 (task-based dispatch, privacy_mode). | M |
| Q | Add structured PII-detection (NER) before external calls — regex misses names, addresses, bank accounts. | L |

---

## 6. Final Verdict

**Is this system scalable to real SaaS?** Not yet. The architecture on paper (medallion + Kafka + RLS + JWT-at-gateway + local-first LLM) is sound; the implementation has three structural defects that independently break production:

1. **Tenant isolation is single-layer.** RLS is not active, so app-layer SQL is the only guard. One missed `WHERE enterprise_id=$1` ships a data breach. At Kaori's current complexity that probability is small; at 10× features it's near-certain.
2. **The event backbone is imaginary.** Documented topics don't exist; real topics have no DLQ, retry, or durable publish. F-031 billing (P0 for revenue) cannot be built on this without redesign. You don't find out it's broken until money goes missing.
3. **Authorization is comment-only.** `SecurityConfig.java` blocks its own endpoints today, and the moment it's "fixed" without also adding role checks at the gateway, every authenticated user becomes an admin.

**What will break first in production?** The `ai-orchestrator` consumer losing events during any brief restart. It looks like everything works in demo (same process, Kafka up the whole time); it fails quietly in production, and the symptom is "why is this one customer's analysis stuck at 'queued'?" — hard to diagnose because there's no DLQ and no per-event audit beyond a debug log line.

**The single biggest architectural mistake.** Treating the documented invariants (K-1, K-6, K-13, K-14) as contracts developers *implement* rather than *affordances the platform enforces*. K-1 lives in comments and SQL strings; K-6 lives in one file; K-13 lives nowhere. A platform is the set of things you cannot forget to do. This one forgets everything.

**Recommendation:** freeze new feature merges until items A–F (P0s) ship. None of them are research projects — they are 1–5 days of focused work each. The tracker's "71% complete" claim for Phase 1 is an inflation; true shippable completion is closer to **45–50%** once the five ghost-feature markers (F-010, F-013, F-014, F-016, F-027) are honestly recorded and the four P0 defects above are cleared.
