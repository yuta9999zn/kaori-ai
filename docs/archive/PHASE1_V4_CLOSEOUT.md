# Phase 1 v4 — Closeout Summary

> **Status:** ✅ **8/8 sprints complete 2026-05-08**
> **Tag:** `v4.0-phase1-complete`
> **Branch:** `feat/v4-p1-s8` (linear parent chain back to `docs/v4-reset` → branched off `feat/f-061-agent-framework`)

---

## Executive summary

Phase 1 v4 reset từ scratch trong **1 ngày** (2026-05-08): anh đưa 6 tài liệu mới (Feature Tree v4.0 + 5 strategic docs); em đọc + đánh giá gap + restructure docs + ship 8 sprint code + Phase B-2 lazy folder restructure cho 2 service chính + materialise 4 K-rules mới (K-17/K-18/K-19/K-20) + 3 module mới ⭐ NEW v2.0 (Process Mining, Adoption Intel, NOV/Economics) + 8 ADRs v4 + 1003 Python tests pass.

**Phase 1 v4 ship contract surface + skeleton + 1 baseline impl per moat module.** Không full runtime. Phase 1.5 P15-S9 + P15-S10 wires actual Temporal worker + connector real impl + DB persistence + cron + Telegram bot httpx + ClickHouse migration + K8s deploy on FPT Cloud.

---

## 9 commits on the v4 branch chain

```
* 76 (this commit)  feat(p1-s8): Telegram pluggable bot adapter + Phase 1 v4 closeout
* 5b7c153   feat(p1-s7): org_intel modules — Process Mining + Adoption Intel + NOV/Economics
* 62cd0b3   feat(p1-s6): K-17 side-effect taxonomy + idempotency framework + workflow YAML schema
* 104b05b   feat(p1-s5): K-20 LLM version pinning + OBS-008 metrics + reasoning/ scaffold
* 76a5b27   feat(p1-s4): silver+gold → data_plane move + Phase B-2 complete for data-pipeline
* c2799f6   feat(p1-s3): bronze → data_plane folder move + 3 connector skeletons (PM-EVT-001/002/003)
* 783a9ac   feat(p1-s2): RLS hardening (P1-MTNT-001/002) + Vault dev wrapper (K-18 prep)
* a465ca0   feat(p1-s1): OBS-012 structured logger + P2-M20-007 first-login force-change-pwd
* dae81d9   docs(v4): reset to Feature Tree v4.0 — strategic docs + 8 ADRs + Phase B-1 skeleton
| (parent: feat/f-061-agent-framework b898e7a — F-061 Agent Framework merged to main)
| main 9495565 (pilot Olist + F-061 already merged via PR #173)
```

---

## Sprint-by-sprint

| Sprint | Commit | Net new tests | Goal | Key delivery |
|---|---|---|---|---|
| **Phase A** | dae81d9 | 0 (docs) | Documentation freeze + B-1 skeleton | 5 strategic MDs (20.5K dòng) + BACKLOG_V4 (1147 features) + API_CATALOG_V4 (169 endpoints) + GAPS_V4 + RESTRUCTURE_PROPOSAL + CLAUDE.md v3.0 + 8 ADRs v4 (0010-0017) + 4 service skeletons (process-mining, adoption-intel, economics, workflow-engine) + 8 infra READMEs (temporal, clickhouse, minio, vault, otel, k8s, loki, prometheus) + v3 trackers archived |
| **P1-S1** | a465ca0 | +10 Python +6 Java | Cluster ready, monorepo, CI/CD, basic auth | OBS-012 structured logger (Python middleware × 4 services + Java logback JSON encoder × 2) + P2-M20-007 first-login force-change-pwd (migration 039 + auth-service flow + endpoint) + Sprint acceptance doc |
| **P1-S2** | 783a9ac | +20 Python +3 Java IT | Multi-tenancy + RLS + Vault setup | P1-MTNT-001/002 RLS hardening (migration 040 + log_rls_attempt PL/pgSQL function + Python helper × 2 + Java IT) + Vault dev mode + kaori_vault.py wrapper × 4 services. Task C OBS-009/016/022 deferred. |
| **P1-S3** | c2799f6 | +19 Python | First 3 connectors + Bronze tier | Phase B-2 lazy move bronze/ → data_plane/bronze/ + 3 connector skeletons PM-EVT-001/002/003 (postgres_cdc, excel_filesystem, zalo_metadata) + Connector ABC + NormalizedEvent + normalizer + pii stubs |
| **P1-S4** | 76a5b27 | 0 | Silver + Gold tiers + data quality | silver/+gold/ → data_plane/ moves complete Phase B-2 for data-pipeline. P2-M25-011 cleaning + P2-M26-023 AI suggestions mapped to existing F-NEW3. P2-M25-020 Data Integration deferred. |
| **P1-S5** | 104b05b | +10 Python | Reasoning Layer + LLM integration | K-20 LLM version pinning (InferRequest +pinned_model +pinned_version + audit reasoning suffix) + OBS-008 Prometheus metrics (kaori_ai_calls_total + kaori_ai_tokens_total) + Phase B-2 ai-orchestrator/analytics → reasoning/legacy_analytics + 7 reasoning subfolder skeletons |
| **P1-S6** | 62cd0b3 | +24 Python | Workflow Engine (Temporal) + builder UI | K-17 5-class side-effect taxonomy (workflow_runtime/side_effect.py) + REL-002 workflow YAML JSONSchema validator + REL-004 derive_idempotency_key + REL-005 migration 041 idempotency_records table. 18 REL-* runtime defer P1.5+ (Temporal worker + saga + DLQ) |
| **P1-S7** | 5b7c153 | +47 Python | Process Mining v1 + Adoption + NOV basic | **Biggest sprint by feature count** — org_intel/ package + 3 subpackages: process_mining (Event/EventLog/HeuristicMiner/case_inference, PM-PII-009/012, PM-ALG-014/015/019), adoption (5/9 signals + composite health score + classification + linear-regression trend, AI-SIG-001/002/003/005/006 + AI-HSC-010..015), economics (revenue 2 methods + 4 cost components + monthly NOV + payback, NOV-REV-001/003/004/005, NOV-CST-007/008/009/010, NOV-CORE-013/014/016) |
| **P1-S8** | this | +16 Python | Zalo Bot → Telegram pluggable adapter (anh chốt mid-sprint) | Pluggable bot adapter package (BotAdapter ABC + TelegramBotAdapter impl + factory + dataclasses) + ADR-0018 (Telegram over Zalo + adapter pattern) + Phase 1 v4 closeout doc + tag |

**Sprint cadence:** ~30 minutes to 3 hours per sprint depending on scope. Avg ~1.5h with the P1-S2 Vault + P1-S7 org_intel sprints anchoring the upper end.

---

## Cumulative test counts

| Service | Pre-v4 baseline | Post-Phase 1 v4 | Delta |
|---|---|---|---|
| ai-orchestrator | 408 | **507** | +99 |
| data-pipeline | 348 | **367** | +19 |
| llm-gateway | 86 | **96** | +10 |
| notification-service | 17 | **33** | +16 |
| **Python total** | 859 | **1,003** | **+144** |
| auth-service Java (AuthServiceTest) | 25 | **31** | +6 |
| auth-service Java IT (CrossTenantAttemptIT) | 0 | **3** | +3 (compile OK; Docker required to run) |

**1003 Python pass milestone reached at Phase 1 v4 closeout.**

---

## K-rules added this Phase 1 v4

| K | Materialised in | Sprint |
|---|---|---|
| **K-17 ⭐ NEW** Workflow YAML — every node MUST declare `side_effect_class` ∈ 5 classes | `workflow_runtime/side_effect.py:SideEffectClass` enum + `yaml_schema.py:validate_workflow_yaml` enforces | P1-S6 (62cd0b3) |
| **K-18 ⭐ NEW** Phase 1.5+ — Vault is the only secret store | `kaori_vault.py` wrapper × 4 services + Vault docker-compose dev | P1-S2 (783a9ac) |
| **K-19 ⭐ NEW** OpenTelemetry mandatory; every span carries `tenant_id` | `log_context.py LogContextMiddleware` × 4 Python services binds tenant_id from gateway X-headers; Java tenant_id MDC defer P15-S9 | P1-S1 (a465ca0) |
| **K-20 ⭐ NEW** LLM version pinning per workflow | `llm-gateway models.py InferRequest +pinned_model +pinned_version` + audit reasoning suffix | P1-S5 (104b05b) |

K-1..K-16 from v3 all preserved. Em update CLAUDE.md §4 to track all K-rules in one table.

---

## Phase B-2 folder restructure progress

```
services/data-pipeline/
├── data_plane/
│   ├── bronze/          ← P1-S3 ✅
│   ├── silver/          ← P1-S4 ✅
│   └── gold/            ← P1-S4 ✅
├── ingestion/
│   └── connectors/{postgres_cdc, excel_filesystem, zalo_metadata}/  ← P1-S3 ✅
├── routers/, shared/, tests/
└── (Phase B-2 COMPLETE for data-pipeline)

services/ai-orchestrator/
├── reasoning/
│   ├── legacy_analytics/                ← P1-S5 ✅ (moved from analytics/)
│   ├── insight_engine/, recommendation_engine/, constraint_engine/,
│   ├── formula_library/, criteria_registry/, rag/, profiling/  ← P1-S5 ✅ skeletons
├── workflow_runtime/                    ← P1-S6 ✅ (side_effect, idempotency, yaml_schema)
├── org_intel/
│   ├── process_mining/                  ← P1-S7 ✅ (types, case_inference, heuristic_miner)
│   ├── adoption/                        ← P1-S7 ✅ (signals, health_score)
│   └── economics/                       ← P1-S7 ✅ (revenue, cost, nov)
├── chat/                                ← stays (CHAT_TOOL_REGISTRY_V4 plan)
└── (frameworks/, explainability/, multi_tier/, reports/, agents/ stay — gradual)

services/notification-service/
└── bot/                                 ← P1-S8 ✅ (BotAdapter ABC + TelegramBotAdapter)
```

---

## ADRs added Phase 1 v4

| ADR | Title | Sprint |
|---|---|---|
| 0010 | Modular monolith Phase 1, selective microservices Phase 2+ | Phase A |
| 0011 | Temporal.io for workflow orchestration | Phase A |
| 0012 | Postgres + ClickHouse polyglot persistence | Phase A |
| 0013 | RLS multi-tenancy formalize v4 | Phase A |
| 0014 | At-least-once + idempotency, not exactly-once | Phase A |
| 0015 | Qwen-first LLM with pluggable vendor adapters (anh chốt) | Phase A |
| 0016 | FPT/Viettel VN hosting | Phase A |
| 0017 | Redis Streams Phase 1, Kafka Phase 2 | Phase A |
| **0018** | **Pluggable bot adapter (Telegram default Phase 1)** — anh chốt mid-P1-S8 | P1-S8 |

---

## Migrations added

| Migration | Title | Sprint |
|---|---|---|
| 039 | `enterprise_users.must_change_password` | P1-S1 |
| 040 | `cross_tenant_attempts` table + `log_rls_attempt` PL/pgSQL function | P1-S2 |
| 041 | `idempotency_records` table (RLS, 7-day TTL, side_effect_class CHECK) | P1-S6 |

---

## Deferred to Phase 1.5 (P15-S9 to P15-S12)

This list is the input for Phase 1.5 sprint planning. Each item already has a contract surface in Phase 1 — the runtime piece is what defers.

### Infrastructure / deploy
- K8s cluster on FPT Cloud (ADR-0016) — P15-S9
- Vault HA Raft 3-node prod + KMS auto-unseal (ADR-0010 + K-18) — P15-S9
- ClickHouse 3-node sharded + replicated (ADR-0012) — P15-S10
- MinIO distributed 4-node Bronze prod (ADR-0016) — P15-S9

### Workflow Engine runtime (REL-* deferred — see P1-S6 acceptance)
- Temporal cluster deploy (ADR-0011) — P15-S9
- Action Runtime activity wrapper (REL-003) — P15-S9
- Saga orchestrator (REL-013), DLQ + admin UI (REL-015..017), circuit breaker (REL-018), heartbeat (REL-021), per-tenant pool isolation (REL-022/023), Retry-After respect (REL-009), per-tenant retry rate-limit (REL-010), provider-side dedup (REL-007) — P15-S9 + P15-S11

### Process Mining runtime
- Real PM-EVT-001/002/003 connector impl (Postgres CDC + Excel revisions + Zalo metadata) — P15-S9
- VN-aware PII detection PM-PII-010/011 — P15-S9
- PM-OUT-029 workflow YAML auto-generation from MinedWorkflow — P15-S9
- PM-ALG-018 dedicated variant analysis function — P15-S9 (HeuristicMiner output already enables this)

### Adoption Intel runtime
- 4 remaining signals (AI-SIG-004 login frequency, AI-SIG-007 time-to-action, AI-SIG-008 feature usage skew, AI-SIG-009 feedback rate) — P15-S9
- AI-INT-018 CSM alert generation + endpoint — P15-S9
- adoption_signals DB persistence migration — P15-S9

### Economics / NOV runtime
- NOV-REV-002 A/B attribution method — P15-S10
- NOV-CORE-015/017/018 cumulative + per-dept + per-tenant rollups + DB persistence — P15-S9
- NOV-RPT-019 manager email digest cron — P15-S9
- NOV-RPT-021 ROI dashboard endpoint — P15-S9
- NOV-RPT-022 workflow ROI ranking — P15-S9
- nov_records DB persistence migration — P15-S9

### Observability runtime
- Java tenant_id MDC propagation (K-19 Java side) — P15-S9
- OBS-009 tenant_quota_usage Prometheus gauge — P15-S9
- OBS-010 nov_per_workflow + OBS-011 adoption_score_per_workflow gauges — P15-S9
- OBS-016 PagerDuty AlertManager wiring — P15-S9
- OBS-022 Sentry SDK wire — P15-S9 (Sprint P1-S2 Task C deferred to here)

### Bot runtime (P15-S9)
- Telegram httpx send_message impl
- Telegram webhook receiver for callback button taps (FastAPI route)
- Vault-backed token + per-tenant chat allow-list
- Telegram BotFather setup + tenant chat opt-in flow
- Outbox channel='bot:telegram' dispatch

### Studio + Personal portals (Phase 2)
- All 91 Studio + Personal features — Phase 2 P2-S15+ when portals stand up

### Phase 2 explicit
- Custom subdomain (P2-M21-006) — Phase 2
- Streaming ingestion webhook/Kafka (P2-M25-003) — Phase 2
- Parquet upload (P2-M26-004) — Phase 2
- Multi-source Data Integration (P2-M25-020) — Phase 2 BI features
- Workflow Builder UI — Phase 2 (frontend paused)

---

## What this Phase 1 v4 deliberately did NOT touch

- **Frontend** — paused per anh's instruction at v4 reset.
- **Pilot Olist** on `main` — not regressed; drift Olist 12 .py files stashed `drift-olist-pre-p1-s3` since P1-S3.
- **F-061 Agent Framework** — already merged to main as deprecated experiment via PR #173.
- **Sprint 8 Conversational Layer code** — refactor option deferred per anh's choice (a) spec/doc only at session start.
- **CI cloud** — local-only per anh's chốt; not pushed to GitHub remote.

---

## Branching state at closeout

```
main             9495565  (pilot Olist + F-061 merged via PR #173)
└── docs/v4-reset      dae81d9  (Phase A docs + B-1 skeleton)
    └── feat/v4-p1-s1   a465ca0  (P1-S1)
        └── feat/v4-p1-s2   783a9ac  (P1-S2)
            └── feat/v4-p1-s3   c2799f6  (P1-S3)
                └── feat/v4-p1-s4   76a5b27  (P1-S4)
                    └── feat/v4-p1-s5   104b05b  (P1-S5)
                        └── feat/v4-p1-s6   62cd0b3  (P1-S6)
                            └── feat/v4-p1-s7   5b7c153  (P1-S7)
                                └── feat/v4-p1-s8 *<closeout>  (P1-S8 + tag v4.0-phase1-complete)

stash@{0}: drift-olist-pre-p1-s3 (12 .py files + docker-compose.yml)
```

---

## Recommended next steps for anh

1. **Review the chain** — `git log --oneline dae81d9~1..HEAD` shows 9 commits. Each acceptance doc in `docs/sprint/P1-S*_ACCEPTANCE.md` is a self-contained sprint summary.
2. **Decide on drift Olist** — `git stash pop` and commit on a branch from main (pilot fixes), then merge separately.
3. **Decide push timing** — anh chốt local-only; if anh wants GitHub backup, push branches without triggering CI workflow (rely on the pause until 1/6 budget reset).
4. **Phase 1.5 P15-S9 planning** — the deferred-to-Phase-1.5 list above is the input. K8s + Vault prod + Temporal cluster deploy is the heaviest pillar; recommend it as the first P15 sprint.
5. **Frontend restart** — when anh's ready, the v4 templates at `D:\Kaori Document\frontend template\` are the canonical source per anh's earlier feedback.
6. **Pilot continuity** — pilot Olist on main is unaffected. Onboard new tenant → still uses main; v4 bits land in production via Phase 1.5 deploy.

---

## References

- `docs/BACKLOG_V4.md` — sprint catalog (8 sprints × ~1147 features tổng)
- `docs/RESTRUCTURE_PROPOSAL.md` — Phase A/B/C strategy + 7 quyết định anh chốt
- `docs/GAPS_V4.md` — code hiện tại vs v4 architecture
- `docs/sprint/P1-S*_ACCEPTANCE.md` — 8 acceptance docs (one per sprint)
- `docs/strategic/{SAD_SKELETON_V2, PIPELINE_UNIFIED, REASONING_LAYER, WORKFLOW_SYSTEM, PLAYBOOK_90DAY}.md` — 5 strategic source docs
- `docs/adr/0010-0018-*.md` — 9 ADRs v4
- `CLAUDE.md` v3.0 — project instructions + K-1..K-20 invariants + sprint progress tracker
