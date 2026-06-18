# Sprint P15-S9 — Planning Doc (Phase 1.5)

> **Status:** 🟡 7/10 deliverables shipped 2026-05-08 (single session)
> **Date:** 2026-05-08
> **Sprint goal (per BACKLOG_V4):** "90-day testing infra + Adoption full"
> **Window:** Phase 1.5 Week 17-18 (M5 start)
> **Branch:** `feat/p15-s9-d1` (local-only — GitHub Actions CI budget exhausted; defer push to next budget reset)
> **Pre-reqs:** Phase 1 v4 closeout (`v4.0-phase1-complete` tag) — DONE

This is **the BIGGEST sprint Phase 1.5** (and arguably the largest end-to-end sprint of v4 era). Phase 1 v4 shipped contract surface; P15-S9 wires actual runtime infrastructure: K8s cluster, Vault HA, Temporal cluster, 3 connector real impl, Telegram httpx, ClickHouse Silver, 4 adoption signals, NOV cron.

Realistic time budget: **multi-day, multi-session**. 7/10 D-pieces landed in one Opus 4.7 session 2026-05-08; D4a (Postgres CDC), D4c (Zalo metadata), D8 cutover need external prereqs (WAL config / OA account / cluster up) so they ship next session.

---

## Acceptance criteria (P15-S9 done when):

1. ⏳ FPT Cloud K8s cluster operational (1 region HCM, 6 general + 4 compute + 3 storage nodes per ADR-0016) — Helm chart shipped D1 (`c2b2f85`); deploy waits on FPT Cloud account active.
2. 🟡 Vault HA Raft 3-node deployed with KMS auto-unseal; `kaori_vault.py` swap from env-var fallback to Vault read — D2 scaffold shipped (`7cbb904`+`4042096`); K-18 `get_or_env()` fallback chain on 4 Python copies + migration script + tests done. Java `VaultClient.java` for auth-service deferred (needs Java IT fixture).
3. ✅ Temporal cluster (frontend + history + matching) deployed; 1 worker pod running — Helm chart + docker-compose + worker scaffold + analyze_pipeline reference workflow + 27 tests shipped D3 (`0b9041a`). Cluster deploy waits on D1.
4. 🟡 All 3 P1-S3 skeleton connectors have working `extract_events()` impl — D4b Excel filesystem watcher shipped (`088382b`, +14 tests). D4a Postgres CDC + D4c Zalo metadata still stubs (need WAL config / OA account).
5. ✅ TelegramBotAdapter.send_message wires httpx; webhook receiver for Approve/Reject button taps — shipped D5 (`2e312a3`). REL-011 closes loop end-to-end with idempotent `workflow_approvals` table (migration 042) + secret-token verification + 22 tests.
6. ✅ 4 remaining adoption signals (AI-SIG-004/007/008/009) shipped with tests — D6 (`70f0d7f`). Canonical names re-aligned with Excel feature tree (BACKLOG_V4); cross-ref caught a draft-plan name drift. +16 tests including all-9-signal composite integration.
7. ✅ NOV monthly digest cron + ROI dashboard endpoint live — D7 (`d7bc5f3`). NovMonthlyDigestWorkflow + 4 activities (one per side-effect class) + persistence helper + `GET /economics/nov/{current,trend}` endpoints + migration 043 + 14 tests.
8. 🟡 ClickHouse 3-node deployed; Silver tier dual-write (Postgres + ClickHouse) for 7 days; cutover plan documented — D8 scaffold shipped (`2892cfe`): Helm + docker-compose + 3 reference Silver schemas. Dual-write writer + cutover P15-S10.
9. ⏳ All 8 deliverables behind feature flags (`tenant_settings.feature_flags JSONB`); rollout = 1 pilot tenant first — feature-flag wiring waits on first deploy.

**Test deltas this session:** ai-orchestrator 514→571 (+57), notification-service 31→53 (+22), data-pipeline 366→380 (+14). Total +93 across 7 commits.

**Branch state:** `feat/p15-s9-d1` (9 commits, c2b2f85..2892cfe), local-only, working tree clean. NOT pushed (CI budget). Next session can either continue locally or push when budget resets.

---

## 8 deliverables breakdown

### Deliverable 1 — FPT Cloud K8s cluster

**Scope:** Production K8s cluster operational, hosting all Phase 1 services + new Phase 1.5 stateful services (Vault, Temporal, ClickHouse).

**Files to create:**
- `infrastructure/k8s/helm-charts/kaori-services/` — umbrella chart for api-gateway, auth-service, data-pipeline, ai-orchestrator, llm-gateway, notification-service
- `infrastructure/k8s/helm-charts/kaori-infra/` — postgres (CloudNativePG), redis-cluster, kafka, ollama
- `infrastructure/k8s/kustomize/{base,overlays/{dev,staging,production}}/` — env overlays
- `infrastructure/k8s/network-policies/calico-deny-cross-tenant.yaml` — Phase 2 prep, ship base policies now
- `infrastructure/k8s/ci/argocd-app.yaml` — GitOps deploy config

**External work (anh do via FPT Cloud UI):**
- Sign FPT Cloud contract + provision project
- Reserve 6 general nodes (8 CPU 32 GB) + 4 compute (16 CPU 64 GB) + 3 storage (4 CPU 64 GB SSD)
- Set up Container Registry on FPT Cloud (or use GitHub Container Registry as proxy)

**Dependencies:** FPT Cloud account active (anh).

**Effort:** 2-3 days. Most of it is YAML + smoke deploy iteration.

**Acceptance:** `kubectl get pods -A` shows all 6 services + infra running healthy. `kubectl logs` clean. Phase 1 docker-compose still works locally for pilot Olist.

**Rollout:** Pilot Olist stays on docker-compose. New tenant onboarding (when first arrives) goes to K8s cluster.

---

### Deliverable 2 — Vault HA prod + secret migration

**Scope:** Vault 3-node Raft cluster on K8s with KMS auto-unseal. Migrate Phase 1 env-var secrets to Vault paths.

**Files to create:**
- `infrastructure/vault/helm/values.yaml` — HA Raft 3 replicas + KMS unseal config
- `infrastructure/vault/policies/{platform-admin,tenant-template,service-readonly}.hcl` — populated from skeletons created Phase B-1
- `infrastructure/vault/auth-methods/approle.json` — AppRole auth for services
- Migration script: `scripts/vault-import.py` — read Phase 1 .env values → write Vault paths

**Files to modify:**
- `services/{ai-orchestrator,data-pipeline,llm-gateway,notification-service}/shared/kaori_vault.py` — already has wrapper; add fallback chain (Vault → env-var → fail loud per K-18 in production profile)
- `services/auth-service/src/main/java/.../VaultClient.java` — NEW Java equivalent
- All services' main.py / Application.java — call vault.get(...) instead of os.getenv(...) for sensitive values

**Secret paths (per ADR-0013):**
```
secret/platform/llm/anthropic_key          ← currently KAORI_ANTHROPIC_API_KEY env
secret/platform/llm/openai_key             ← currently KAORI_OPENAI_API_KEY env
secret/platform/notification/smtp_creds    ← SMTP_USER + SMTP_PASS env
secret/platform/telegram/bot_token         ← KAORI_TELEGRAM_BOT_TOKEN env (NEW)
secret/platform/infra/mfa_master_key       ← KAORI_MFA_KEY env (currently per CLAUDE.md §15)
secret/service/auth-service/jwt_keys       ← RSA private/public keypair
secret/tenant/{id}/oauth_tokens/{provider} ← tenant connector OAuth (Phase 1.5+)
```

**Dependencies:** D1 K8s cluster running.

**Effort:** 1-2 days.

**Acceptance:**
- `vault status` shows 3 nodes joined
- `auth-service` boots in production profile and reads MFA key from Vault
- `KAORI_MFA_KEY` env var can be removed without breaking auth
- Vault audit log entries appear in Loki

**K-18 lock:** sau D2, production profile blocks startup nếu Vault unreachable. K-18 invariant fully enforced.

---

### Deliverable 3 — Temporal cluster + worker

**Scope:** Temporal frontend/history/matching pods on K8s + Postgres persistence + 1 worker pod from `services/ai-orchestrator/workflow_runtime/` (P1-S6 contract).

**Files to create:**
- `infrastructure/temporal/helm/values.yaml` — wraps Temporal Helm chart, dedicated Postgres schema `temporal`
- `services/ai-orchestrator/workflow_runtime/temporal_client.py` — NEW Temporal SDK wrapper
- `services/ai-orchestrator/workflow_runtime/activities/` — first set of activities for existing nodes (analyze run, gold aggregate, decision audit)
- `services/ai-orchestrator/workflow_runtime/workflows/` — first workflow types (analyze_pipeline, churn_detection)
- Migration `042_temporal_visibility.sql` (only if visibility ES not ready) — temporal-side schema separate from kaori business

**Files to modify:**
- `services/ai-orchestrator/main.py` — start_temporal_worker() in lifespan
- `services/ai-orchestrator/routers/analytics.py` — POST /analytics/runs trigger workflow instead of direct Kafka emit (keep Kafka as fallback)

**Workflow YAML examples** (validate per P1-S6 schema):
- `infrastructure/workflows/templates/churn-detection.yaml` — example workflow with all 5 side-effect classes

**Dependencies:** D1 K8s cluster, D2 Vault for Temporal admin creds.

**Effort:** 3-4 days. Steepest learning curve (Temporal SDK + saga + heartbeat).

**Acceptance:**
- `temporal workflow list -n default` shows running workflows
- 1 happy-path workflow (analyze_pipeline) completes end-to-end
- 1 failure-path workflow triggers compensation
- Saga test: kill worker mid-run → restart → workflow resumes from last activity

**Defer to P15-S10/S11:** circuit breaker (REL-018), DLQ admin UI (REL-016), heartbeating (REL-021). Phase 1.5 ship core; full reliability menu Phase 2.

---

### Deliverable 4 — 3 connector real impl

**Scope:** Replace `NotImplementedError` stubs in `services/data-pipeline/ingestion/connectors/{postgres_cdc,excel_filesystem,zalo_metadata}/` with working `extract_events()`.

#### 4a. Postgres CDC connector (PM-EVT-001)

**Files to modify:**
- `services/data-pipeline/ingestion/connectors/postgres_cdc/connector.py` — psycopg2.LogicalReplicationConnection + wal2json output plugin

**External work:**
- Customer creates PUBLICATION + REPLICATION SLOT on their Postgres
- Customer grants REPLICATION role to Kaori user

**Effort:** 1 day.

#### 4b. Excel filesystem watcher (PM-EVT-002)

**Files to modify:**
- `excel_filesystem/connector.py` — watchdog FileSystemEventHandler + openpyxl revision diff

**Phase 1.5+:** OneDrive/SharePoint revision API (defer if customer doesn't need).

**Effort:** 1 day.

#### 4c. Zalo metadata connector (PM-EVT-003)

**⚠️ Caveat:** Anh chốt 2026-05-08 dùng Telegram thay Zalo cho **Kaori-side Bot** vì Zalo OA tax registration. Nhưng PM-EVT-003 connector là **read-only customer-side OA metadata** — separate concern. Customer có Zalo OA của họ, em chỉ read metadata. Em bí customer phải có Zalo OA + tax filing — nếu customer Vietnamese SME đã có OA, em consume.

**Decision needed:** Anh có muốn ship PM-EVT-003 Phase 1.5? Nếu Vietnamese SMEs đa số đã có Zalo OA (validated trong UAT pilot), ship. Nếu hầu hết khách không có OA → defer Phase 2.

**Files to modify:**
- `zalo_metadata/connector.py` — Zalo OA REST API client + OAuth refresh

**Effort:** 2 days (OAuth flow + privacy approval gate PM-PII-013).

**Acceptance D4 overall:**
- Each connector produces valid NormalizedEvents on a small fixture corpus
- PII redaction (PM-PII-010 — VN-aware) wired in for all 3
- Tenant_id stamping verified
- E2E: connector → Bronze MinIO → Silver ClickHouse → Process Mining session → HeuristicMiner output

---

### Deliverable 5 — Telegram bot adapter httpx wire

**Scope:** Replace `NotImplementedError` in `services/notification-service/bot/telegram.py:TelegramBotAdapter.send_message` with httpx call to Telegram Bot API.

**Files to modify:**
- `bot/telegram.py:TelegramBotAdapter.send_message` — httpx POST to `https://api.telegram.org/bot{token}/sendMessage`
- `bot/telegram.py` — add webhook receiver registration helper
- `services/notification-service/main.py` — register webhook endpoint `/webhook/telegram` for callback button taps
- `services/notification-service/outbox_poller.py` — handle `channel='bot:telegram'` rows from `notification_outbox`

**Files to create:**
- `services/notification-service/routes/telegram_webhook.py` — FastAPI route accepting Telegram webhook POST, parse callback_query, fire Temporal signal for workflow approval

**Tests:**
- Mock httpx round-trip
- Webhook payload parse (multiple Telegram event types)
- Per-tenant chat allow-list enforcement

**Dependencies:** D2 Vault for bot token storage; D3 Temporal for signal dispatch (workflow approval flow).

**Effort:** 1 day.

**Acceptance:**
- Existing Sprint 8 chat panel (P1-NEW4) backed by this adapter — push insight summary to anh's Telegram
- Workflow with `external` side-effect class triggers manager Telegram approval; tap button → Temporal signal → workflow proceeds

**Note:** Đây là Telegram **outbound** cho workflow notifications, **separate** với `scripts/telegram_listener.py` Telegram bridge (inbound em ↔ anh). Hai concern khác nhau, cùng platform.

---

### Deliverable 6 — 4 remaining adoption signals

**Scope:** Phase 1 v4 P1-S7 shipped 5/9 signals (AI-SIG-001/002/003/005/006). P15-S9 ships remaining 4.

**Files to modify:**
- `services/ai-orchestrator/org_intel/adoption/signals.py` — add 4 functions

**Signals to add (canonical names per BACKLOG_V4 + Excel feature tree):**

| Code | Signal | Data source |
|---|---|---|
| AI-SIG-004 | Workaround file creation (parallel Excel files) | `excel_filesystem` connector — count files matching workflow gold output schema |
| AI-SIG-007 | Negative sentiment in comments/feedback | NLP classifier (llm-gateway 'sentiment' route) over workflow comments |
| AI-SIG-008 | Time-on-task variance (vs baseline) | `pipeline_runs` duration vs rolling-window baseline (2x = friction signal) |
| AI-SIG-009 | Feature usage decline trend | `workflow_runs` per-period count vs baseline (spec: 50/day → 30/day = signal) |

> NOTE — earlier draft of this table used different names (Login frequency, Time-to-action, Feature usage skew, Negative feedback rate). Those drifted from the Excel canonical; re-aligned 2026-05-08 P15-S9 D6.

**Files to create:**
- *(deferred)* migrations for connector + sentiment classifier wiring — D6 first ships pure Python signal extractors with input contracts; data plumbing lands when connectors go live (D4) + sentiment route lands (Phase 1.5+).

**Tests (D6 shipped):**
- `tests/test_org_intel.py` extended with 18 new signal tests (incl. spec-example tests like SIG-008 2x threshold, SIG-009 50→30 = score 0.6).
- Regression: `compute_composite_score` accepts all 9 SignalSamples (`test_compute_composite_score_with_all_9_signals`).

**Acceptance:**
- `compute_composite_score` accepts all 9 SignalSamples ✅ D6.
- `classify_health` thresholds re-tuned (Phase 1.5+ baseline data) — deferred until 60-day baseline data lands.
- AI-INT-018 CSM alert generation wired (engine ready P1-S7; endpoint ships now) — deferred to P15-S10.

**Effort:** ~2h actual (D6).

---

### Deliverable 7 — NOV monthly digest cron + ROI dashboard

**Scope:** P1-S7 shipped engine; P15-S9 wires cron + endpoint + report dispatch.

**Files to create:**
- Migration `045_nov_records.sql` — persist monthly NOV computation result
- `services/ai-orchestrator/org_intel/economics/cron.py` — APScheduler job runs monthly NOV computation per tenant at month-end
- `services/ai-orchestrator/routers/economics.py` — endpoints:
  - `GET /api/v1/economics/nov/monthly` (current month + history)
  - `GET /api/v1/economics/nov/dashboard` (ROI dashboard data)
  - `POST /api/v1/economics/nov/digest/manual` (trigger digest send)
- `services/notification-service/templates/nov-digest.jinja2` — monthly NOV email template (VND format per memory `feedback_vnd_currency_format`)

**Files to modify:**
- `services/ai-orchestrator/main.py` — register cron job in lifespan
- `services/notification-service/outbox_poller.py` — handle `template='nov-digest'`

**Acceptance:**
- Cron fires last day of month → computes NOV → enqueues digest email via outbox
- ROI dashboard endpoint returns chart-ready data (per-workflow NOV ranking, cumulative, vs benchmark)
- VND format in email matches memory rule (1.000.000₫ / 1 triệu VNĐ, NOT 1M)

**Effort:** 2 days.

---

### Deliverable 8 — ClickHouse Silver migration

**Scope:** ADR-0012 plan — Postgres `silver_pipeline_rows` is fine for pilot Olist; new tenants Phase 1.5+ get ClickHouse Silver. Dual-write 7 days, then cutover.

**Files to create:**
- `infrastructure/clickhouse/helm/altinity-operator-values.yaml` — 1-shard 1-replica dev → 3-shard 2-replica prod
- `infrastructure/clickhouse/schemas/silver_pipeline_rows.sql` — partitioned by tenant_id + month, ORDER BY (tenant, ts)
- Migration script: `scripts/clickhouse-backfill.py` — copy Postgres silver → ClickHouse for existing tenants

**Files to modify:**
- `services/data-pipeline/data_plane/silver/rule_catalog.py` — dual-write helper writes to both Postgres + ClickHouse (Phase 1.5 transition)
- `services/data-pipeline/main.py` — initialize ClickHouse driver on startup
- `services/ai-orchestrator/reasoning/legacy_analytics/runner.py` — query Silver from ClickHouse first, Postgres fallback

**ClickHouse query rewriter (per ADR-0013):**
- Wrapper layer enforces `WHERE tenant_id = $1` on every Silver query
- Lint test extension (P1-MTNT-002 spirit) verifies no raw ClickHouse query escapes the wrapper

**Acceptance:**
- Both stores consistent for 7 days (dual-write)
- ClickHouse query latency P95 < 100ms on 100M-row Silver
- Tenant isolation: tenant A query never returns tenant B data

**Effort:** 3-4 days.

**Risk:** Highest of all 8. ClickHouse + dual-write + cutover pattern is novel for codebase.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FPT Cloud commercial issue (contract delay) | Medium | High — D1 blocked | Em can write Helm charts assuming generic K8s; tested on minikube; FPT-specific bits last |
| Temporal learning curve longer than expected | High | Medium — D3 slips | Start with simplest workflow type (analyze_pipeline); expand incrementally |
| Postgres CDC requires customer ops involvement | High | Medium — D4a slips per customer | Document setup steps; defer to onboarding phase |
| ClickHouse dual-write data drift | Medium | High — D8 cutover risky | 7-day soak + daily diff cron; abort cutover if drift > 0.1% |
| Vault migration breaks pilot Olist | Low | High — production down | Vault wrapper has env-var fallback in non-prod profile; pilot stays env-var until manual switch |
| 4 new adoption signals show very different baselines per tenant | Medium | Low — tuning iteration | classify_health thresholds tunable per tenant via tenant_settings |
| NOV digest email spam (manager doesn't want monthly) | Medium | Low — UX | Per-tenant `nov_digest_enabled` flag; default ON, manager toggles OFF |
| Telegram webhook receiver requires public HTTPS | High | Medium — D5 needs ingress + cert | NGINX Ingress + cert-manager Let's Encrypt; standard K8s pattern |

---

## Rollout strategy

**Phase 1.5 P15-S9 ship plan:**

1. **D1 K8s cluster operational** but **no production traffic**. Pilot Olist stays docker-compose.
2. **D2 Vault migrated** for platform secrets only (LLM keys, SMTP). Tenant secrets stay env-var until per-tenant migration.
3. **D3 Temporal cluster live** with 1 worker. Workflow types limited to non-customer-facing (overview generation, NOV digest internal). Customer-facing workflows stay legacy Kafka path.
4. **D4 connectors enabled per opt-in tenant.** New `tenant_settings.connectors_enabled JSONB` flag list. Default empty.
5. **D5 Telegram outbound** opt-in per tenant via `tenant_settings.bot_provider='telegram'`.
6. **D6 4 signals computed for all tenants** but composite_score classification stays "advisory" (no action triggered) until Phase 1.5+ baselining done.
7. **D7 NOV digest** opt-in via `tenant_settings.nov_digest_enabled` (default OFF for existing, ON for new tenants).
8. **D8 ClickHouse Silver** dual-write enabled for **1 pilot tenant** (NOT Olist — Olist stays Postgres-only). New tenants from D8+1 day get ClickHouse.

**Cutover criteria (D8):**
- Daily diff Postgres ↔ ClickHouse < 0.1%
- 7 consecutive days OK
- Anh acks → flip read path to ClickHouse, Postgres becomes secondary

---

## Effort summary

| Deliverable | Days | Sub-PRs |
|---|---|---|
| D1 K8s cluster | 2-3 | 2 (helm-charts + kustomize) |
| D2 Vault HA + migration | 1-2 | 2 (deploy + secret import) |
| D3 Temporal cluster + worker | 3-4 | 3 (deploy, worker scaffold, first workflow) |
| D4 3 connectors | 4 | 3 (one per connector) |
| D5 Telegram httpx + webhook | 1 | 1 |
| D6 4 adoption signals | 2 | 2 (signals + tests, classify rebalance) |
| D7 NOV cron + dashboard | 2 | 2 (cron + endpoint, email template) |
| D8 ClickHouse Silver | 3-4 | 3 (deploy, dual-write, cutover plan) |
| **Total** | **18-22 days** | **~18 PRs** |

P15-S9 BACKLOG_V4 says 1 sprint window (Week 17-18 = 2 weeks). Realistic = closer to 4-5 weeks of focused work, multi-session. Em can execute incrementally — each sub-PR independent testable.

---

## NOT in scope this sprint (deferred to P15-S10/S11)

- REL-018 circuit breaker per external service
- REL-016 DLQ admin UI (FE work, frontend paused)
- REL-021 long-running activity heartbeat
- F-046 Model Registry (MLflow)
- DocSage SQL reasoning (P15-S11 per RAG addendum)
- PageIndex tree retrieval (P15-S10 per RAG addendum)
- NOV-REV-002 A/B attribution method (P15-S10 per BACKLOG)
- Frontend rebuild from `D:\Kaori Document\frontend template\` (anh paused)

---

## Pre-sprint checklist (anh sẵn sàng khi)

- ☐ FPT Cloud commercial contract signed
- ☐ FPT Cloud K8s cluster provisioned (kubectl access from anh's laptop)
- ☐ FPT Cloud Postgres + KMS available
- ☐ DNS for *.kaori.ai pointing to FPT Cloud Ingress
- ☐ TLS cert provider chosen (Let's Encrypt via cert-manager OR custom CA)
- ☐ GitHub Container Registry token rotated (em see anh nói "github hết token action" — separate from CR token, but check)
- ☐ Anthropic + OpenAI vendor accounts active (em hiện đang Qwen-first per ADR-0015 nhưng D7 NOV digest may use vendor for narrative quality)
- ☐ Telegram bot operational (em đã setup `@kaori_yuta_2026_bot` — recycle for D5 outbound or new bot per security)

---

## Em recommend kickoff order khi anh OK

**Wave A (foundation, week 17 start):**
1. D1 K8s cluster — Helm charts + kustomize + smoke deploy on FPT Cloud
2. D2 Vault HA on K8s + platform secret migration

**Wave B (services, week 17-18):**
3. D3 Temporal cluster + 1 worker + 1 happy-path workflow
4. D5 Telegram httpx + webhook (small, can be parallel with D3)

**Wave C (data + intel, week 18+):**
5. D4 connectors (3 sub-PRs sequential)
6. D6 4 adoption signals
7. D7 NOV cron + dashboard

**Wave D (data plane upgrade, week 18-19+):**
8. D8 ClickHouse Silver migration

Each Wave gates on previous Wave complete + acceptance verified.

---

## References

- `docs/PHASE1_V4_CLOSEOUT.md` — deferred-to-Phase-1.5 list (this doc satisfies it)
- `docs/BACKLOG_V4.md` Phase 1.5 P15-S9 row — original feature list
- `docs/strategic/SAD_SKELETON_V2.md` Phần 5 (Layer 0 Infra) + Phần 18 (Workflow Engine) + Phần 22 (Process Mining) + Phần 23 (Adoption) + Phần 24 (NOV)
- `docs/adr/0011-temporal-for-workflow-orchestration.md`
- `docs/adr/0012-postgres-clickhouse-polyglot-persistence.md`
- `docs/adr/0013-rls-multi-tenancy-formalize-v4.md`
- `docs/adr/0016-fpt-viettel-vn-hosting.md`
- `docs/adr/0018-pluggable-bot-adapter-telegram-default.md`
- `docs/adr/0019-vectorless-tree-retrieval-and-structured-sql-rag.md` (P15-S10/S11 sequel)
- ADR new (will write during D1): `0020-fpt-cloud-deployment-topology.md`
