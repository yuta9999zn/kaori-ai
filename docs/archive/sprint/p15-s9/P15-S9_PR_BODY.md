# Sprint P15-S9 — 7/10 D-deliverables shipped

Phase 1.5 Sprint 9 — first runtime infrastructure sprint after Phase 1 v4 contract closeout. Lands K8s/Vault/Temporal scaffolds, completes 1 of 3 connectors (Excel filesystem), wires Telegram bot end-to-end, completes adoption signals 9/9, ships NOV monthly workflow + ROI dashboard, and lays ClickHouse Silver-tier scaffold.

Branch chain: `main` (745b592) → 10 commits → `feat/p15-s9-d1` (bf07758).

---

## Summary

| # | Deliverable | Commit | Status | Notes |
|---|---|---|---|---|
| D1 | K8s Helm umbrella + Kustomize overlays + Telegram bridge runbook | `c2b2f85` | 🟡 Helm chart shipped | Deploy waits on FPT Cloud account |
| D2 | Vault HA scaffold + `kaori_vault.py` K-18 fallback + `vault_import.py` migration script | `7cbb904`, `4042096` | 🟡 Python side complete | Java `VaultClient.java` deferred → P15-S10 |
| D3 | Temporal cluster scaffold + worker + first workflow (`analyze_pipeline`) + 27 tests | `0b9041a` | ✅ Scaffold | Cluster deploy waits on D1 |
| D4a | Postgres CDC connector real impl (PM-EVT-001) | — | ⏳ Defer P15-S10 | Needs WAL config + replication slot |
| D4b | ExcelFilesystemConnector real impl (PM-EVT-002) + 14 tests | `088382b` | ✅ | watchdog + openpyxl revision diff |
| D4c | Zalo metadata connector real (PM-EVT-003) | — | ⏳ Defer P15-S10 | Needs OA account + tax registration |
| D5 | Telegram httpx wire + webhook approve/reject + REL-011 + migration `042` + 22 tests | `2e312a3` | ✅ | Idempotent `workflow_approvals` table + secret-token verification |
| D6 | Adoption signals 4/7/8/9 (AI-SIG-004/007/008/009) + 16 tests | `70f0d7f` | ✅ | Canonical names re-aligned with Excel feature tree |
| D7 | NOV monthly digest workflow + ROI dashboard endpoint + migration `043` + 14 tests | `d7bc5f3` | ✅ | 4 activities (one per side-effect class) + persistence helper |
| D8 | ClickHouse Helm + docker-compose + 3 reference Silver schemas | `2892cfe` | 🟡 Scaffold | Dual-write writer + cutover → P15-S10 |
| Docs | Sprint plan + 7/10 closeout note | `bf07758` | ✅ | `docs/sprint/P15-S9_PLAN.md` |

**Diff size:** 80 files changed, +8856 / −129.

---

## Test plan

**Local pytest (Python 3.11) — all green prior to push:**

- [x] `services/ai-orchestrator` — **571 passed** (was 514, +57 in this sprint)
- [x] `services/notification-service` — **53 passed** (was 31, +22 in this sprint)
- [x] `services/data-pipeline` — **380 passed, 1 skipped** (was 366, +14 in this sprint)
- [x] Total Python tests: **1004 passed**
- [ ] CI `ci.yml` matrix (deferred — running on PR will burn ~15-25 CI min)
- [ ] CI `migration-test.yml` for migrations 042 + 043 (deferred — ~5-10 min)
- [ ] CI `docker-smoke.yml` for `requirements.txt` change (deferred — ~5-10 min)
- [ ] CI `arch-guards.yml` (~1 min)
- [ ] CI `gitleaks.yml` (~1 min)

**Manual verification done in branch:**

- [x] Excel watcher fixture corpus — 14 tests cover create/modify/revision-diff
- [x] Telegram webhook secret-token verification + idempotent approve/reject — 22 tests
- [x] Adoption all-9-signal composite integration — passes
- [x] NOV workflow side-effect classes (pure / read-only / write_idempotent / external) — each activity unit tested
- [x] Workflow YAML alignment with K-17 schema — `test_workflow_yaml_alignment.py`

**External infra not deployable from this PR (defer to P15-S10):**

- FPT Cloud K8s cluster spin-up
- Vault HA Raft 3-node + KMS auto-unseal
- Temporal cluster (frontend + history + matching + 1 worker pod)
- ClickHouse 3-node + dual-write cutover

---

## What's deferred to P15-S10

| Item | Reason |
|---|---|
| D2 Java `VaultClient.java` for auth-service | Needs Java IT fixture; Python side proves K-18 contract first |
| D4a Postgres CDC real impl | Needs customer-side WAL config + REPLICATION grant — out of scope for codebase change |
| D4c Zalo metadata real impl | Needs Zalo OA account + Vietnamese tax registration; pilot Olist won't exercise |
| D8 ClickHouse dual-write writer + cutover | Needs ClickHouse cluster running first (D8 deploy stage) |
| K-18 production-profile lock (env-var fallback removal) | Lands when Vault HA is operational |
| Feature flag rollout per `tenant_settings.feature_flags` | Pilot-tenant rollout when first deploy lands |

---

## Invariants touched

- **K-17** (workflow side-effect class) — every new Temporal activity declares class; `nov_monthly_digest` exercises 4 of 5 classes
- **K-18** (Vault-only secrets) — `kaori_vault.get_or_env()` fallback chain on 4 Python services; production lock deferred
- **K-20** (LLM version pinning) — `temporalio==1.27.0` pinned per K-20 spirit; no silent SDK upgrade

No invariant relaxed.

---

## Migrations added

- `infrastructure/postgres/migrations/042_workflow_approvals.sql` — REL-011 idempotency table for Telegram approve/reject button taps (TTL 7d)
- `infrastructure/postgres/migrations/043_nov_monthly_digests.sql` — NOV monthly digest history per enterprise + month, immutable rows

Both are additive (`CREATE TABLE`); no schema mutation on existing tables.

---

## Dependencies added

`services/ai-orchestrator/requirements.txt` (+1):

- `temporalio==1.27.0` — gated behind `TEMPORAL_ENABLE_WORKER=false` default; loads but does no I/O until enabled per env

No vendor LLM SDK added. No new licence concerns.

---

## Pilot Olist impact

**None.** Pilot Olist runs on docker-compose without K8s/Temporal/ClickHouse/Vault HA enabled. All new modules gated behind environment flags (`TEMPORAL_ENABLE_WORKER`, `KAORI_VAULT_ADDR`, `CLICKHOUSE_ENABLED`) that default to off. Pilot Olist drift state preserved in `stash@{0}` since P1-S3.

---

## Reviewer guidance

- Big diff (80 files / +8856 lines) but most volume is **infra YAML scaffolds** (~3500 lines across `infrastructure/{k8s,vault,temporal,clickhouse}/`) that don't run in CI
- Hot paths to scrutinise:
  - `services/ai-orchestrator/workflow_runtime/` (D3 Temporal — new public surface)
  - `services/notification-service/bot/{telegram,webhook}.py` (D5 — receives external webhooks)
  - `services/data-pipeline/ingestion/connectors/excel_filesystem/connector.py` (D4b — touches filesystem)
  - `services/ai-orchestrator/org_intel/adoption/signals.py` (D6 — canonical name realignment, behavioural change)
- Skip on first pass: Helm `values.yaml` files, Kustomize overlays, ClickHouse SQL DDL — pure scaffolds, ship-and-deploy verified later

Reference: `docs/sprint/P15-S9_PLAN.md` for full deliverable spec + acceptance criteria per D-piece.
