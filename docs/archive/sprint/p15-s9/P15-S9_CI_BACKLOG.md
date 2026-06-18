# P15-S9 CI Backlog — chờ GitHub Actions budget reset (1st June 2026)

> **Created:** 2026-05-10
> **Trigger to resume:** GitHub Actions monthly budget reset (cycle 1st of month, 3000 min/month exhausted)
> **Branch:** `feat/p15-s9-d1` (PR #179 OPEN, mergeable, REVIEW_REQUIRED)
> **Last push:** 2026-05-09 13:14 — 19/19 CI checks FAILURE, no further pushes until budget reset

---

## State snapshot (frozen 2026-05-10)

PR #179 commit head: `22571a0` (docs PR body). Branch up-to-date with origin. 11 commits total on branch since `main`:

```
22571a0  docs(p15-s9): PR body template for opening when CI budget resets
bf07758  docs(p15-s9): record 7/10 D-deliverables shipped + branch state
2892cfe  feat(p15-s9-d8): ClickHouse Helm + docker-compose + 3 reference schemas
088382b  feat(p15-s9-d4b): ExcelFilesystemConnector real impl (PM-EVT-002)
d7bc5f3  feat(p15-s9-d7): NOV monthly workflow + ROI dashboard endpoint
70f0d7f  feat(p15-s9-d6): adoption signals 4/7/8/9 (canonical names per Excel)
2e312a3  feat(p15-s9-d5): Telegram httpx wire + webhook receiver (REL-011)
0b9041a  feat(p15-s9-d3): Temporal cluster scaffold + worker + first workflow
4042096  feat(p15-s9-d2): close D2 — vault_import.py + get_or_env tests
7cbb904  feat(p15-s9-d2): Vault HA scaffold + K-18 get_or_env fallback chain (partial)
c2b2f85  feat(p15-s9-d1): K8s Helm umbrella chart + Kustomize overlays + Telegram bridge
```

---

## 19 CI checks ALL FAILURE (push 2026-05-09 13:24)

Run ID series: `25602222626..25602222637` (all six workflows triggered simultaneously, all failed within 10s of start — implies static guard / lint failures, not flake).

| # | Check name | Workflow | Job URL |
|---|---|---|---|
| 1 | architecture regression guards | arch-guards | [job/75157986356](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222637/job/75157986356) |
| 2 | tenant-filter lint | ci | [job/75157986349](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986349) |
| 3 | validate docker-compose.yml | docker-smoke | [job/75157986339](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986339) |
| 4 | gitleaks secret scan | gitleaks | [job/75157986330](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222626/job/75157986330) |
| 5 | schema drift check | migration-test | [job/75157986383](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222629/job/75157986383) |
| 6 | java / api-gateway | ci | [job/75157986365](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986365) |
| 7 | java / auth-service | ci | [job/75157986348](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986348) |
| 8 | python / data-pipeline | ci | [job/75157986371](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986371) |
| 9 | python / ai-orchestrator | ci | [job/75157986378](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986378) |
| 10 | python / llm-gateway | ci | [job/75157986368](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986368) |
| 11 | python / notification-service | ci | [job/75157986373](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986373) |
| 12 | openapi codegen (drift check) | ci | [job/75157986351](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986351) |
| 13 | frontend (next.js) | ci | [job/75157986347](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222634/job/75157986347) |
| 14 | build / services/auth-service | docker-smoke | [job/75157986366](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986366) |
| 15 | build / services/api-gateway | docker-smoke | [job/75157986358](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986358) |
| 16 | build / services/data-pipeline | docker-smoke | [job/75157986369](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986369) |
| 17 | build / services/ai-orchestrator | docker-smoke | [job/75157986364](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986364) |
| 18 | build / services/notification-service | docker-smoke | [job/75157986359](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986359) |
| 19 | build / frontend | docker-smoke | [job/75157986363](https://github.com/yuta9999zn/kaori-system/actions/runs/25602222630/job/75157986363) |

---

## Pre-flight BEFORE first re-push (June)

> Per memory `feedback_endpoint_addition_drift_checks.md` — D5 + D7 added endpoints + migrations. Refresh ALL 4 drift artefacts locally first to avoid burning re-runs:

1. **RouteConfigTest** (api-gateway) — list endpoint must include new D7 ROI dashboard route.
2. **schema_snapshot** — D7 migration adds `nov_monthly_*` table; bump snapshot.
3. **openapi spec** — `python scripts/dump_openapi.py` for ai-orchestrator (D7) + notification-service (D5 webhook).
4. **FE types** — codegen against new openapi (`npm run gen:api` or equivalent).

Then **local pytest sweep** before push:
```powershell
cd "D:\Kaori System\services\ai-orchestrator"     ; python -m pytest 2>&1 | Select-Object -Last 3
cd "D:\Kaori System\services\notification-service"; python -m pytest 2>&1 | Select-Object -Last 3
cd "D:\Kaori System\services\data-pipeline"       ; python -m pytest 2>&1 | Select-Object -Last 3
```
Expected: 571 / 53 / 380 (deltas from session). Anything else = drift caught locally, fix before push.

Java IT — local Win can't reproduce. Memory `feedback_auth_service_it_pattern.md` says: if endpoint added → bump 4 hardcodes in `FlywayMigrationIT` + `@MockBean` in `WorkspaceControllerIT`. Audit D5 + D7 against this rule.

---

## Pre-emptive fixes landed local 2026-05-10 (commit `339e3d8`)

4 cluster fixes verified local without CI; reduce expected red count from 19 → ~10 on next push:

| CI check | Fix | Local verify |
|---|---|---|
| #2 tenant-filter lint | analyze.py: 2 stub comments reworded to reference `input_.tenant_id` instead of bare table names | `scripts/check-tenant-filter.py` PASS (256 files) |
| #12 openapi codegen drift | `dump_openapi.py orchestrator` regenerated `docs/api-specs/orchestrator.openapi.json` (43 paths) | `dump_openapi.py --check` PASS |
| #13 frontend (next.js) — types portion | `npm run gen:api` regenerated `frontend/lib/api/types/orchestrator.d.ts` (3496 lines) | `gen-api-types.mjs --check` PASS |
| #11 python/notification-service + #18 build/notification-service | Added explicit `httpx==0.27.2` to `services/notification-service/requirements.txt` (D5 telegram.py imports it; was relying on transitive) | `python -c "from bot import telegram, webhook"` resolves |

**Also confirmed local (eliminate as cause):**
- ai-orchestrator pytest 571/571, notification 53/53, data-pipeline 380/380 → not Python logic bugs
- arch-guards hard-fail set (G1/G2/G3/G7/G9/G10) all PASS via manual grep
- kafka contracts: 9 schemas PASS additive
- docker-compose config: PASS with dummy env vars

## Failure-class hypotheses — REMAINING (verify when logs accessible)

Without burning budget on log fetch, likely classes per memory + visual scan of changes:

| Hypothesis | Affected checks (REMAINING) | Memory ref |
|---|---|---|
| Postgres-side: D7 NOV migration not in `infrastructure/postgres/migrations/` or `schema_snapshot.txt` not refreshed | #5 schema drift | `feedback_endpoint_addition_drift_checks` |
| Java auth-service IT class missing wiring for new entity/migration | #7 java/auth-service, #14 docker auth-service | `feedback_auth_service_it_pattern` |
| Java api-gateway RouteConfig missing entry for D7 ROI dashboard route | #6 java/api-gateway | `feedback_endpoint_addition_drift_checks` |
| K8s Helm template (D1 c2b2f85) parser issue or arch-guard rule fires on new infra/k8s/ paths | #1 arch-guards | none — investigate fresh; all hard-fail guards pass local, suspect step-level env / fetch-depth issue |
| docker-compose.yml additions (D3 Temporal, D8 ClickHouse) need new env-var names for `docker compose config` to interpolate | #3 docker-compose validate | local PASS with dummy POSTGRES_PASSWORD/JWT_*; CI may need additional dummy for Temporal/CK creds |
| gitleaks false-positive on Vault/Telegram test fixtures (D2/D5) | #4 gitleaks | binary not installed local; likely test fixture leak — review `services/notification-service/tests/test_webhook.py` + `scripts/test_vault_import.py` for accidentally-committed-looking secrets |
| Frontend Next.js build break unrelated to types (e.g. new component referencing dead import) | #13 frontend build, #19 build/frontend | local `npm run build` not run yet — defer to next session |
| Python builds in docker-smoke fail because Dockerfile copies requirements.txt then pip install — same deps issue caught for notification-service may exist for other services | #15-17 build/api-gateway, build/data-pipeline, build/ai-orchestrator | local pytest passes; docker build will only fail if Dockerfile FROM-image lacks system libs for new wheels (unlikely for httpx/temporalio) |

---

## Resume procedure (1st June 2026 or later)

```powershell
# 1. Confirm budget reset
gh api rate_limit | ConvertFrom-Json | Select-Object -ExpandProperty resources | Select-Object -ExpandProperty actions_runner_registration

# 2. Pull failure logs for ONE check per workflow to triage cluster
gh run view 25602222626 --log-failed | Select-String -Pattern "error|Error|FAIL" | Select-Object -First 30  # gitleaks
gh run view 25602222629 --log-failed | Select-String -Pattern "error|Error|FAIL" | Select-Object -First 30  # schema-drift
gh run view 25602222630 --log-failed --job 75157986339 | Select-String -Pattern "error|Error|FAIL" | Select-Object -First 30  # docker-compose validate
gh run view 25602222634 --log-failed --job 75157986378 | Select-String -Pattern "error|Error|FAIL" | Select-Object -First 30  # python ai-orch
gh run view 25602222637 --log-failed | Select-String -Pattern "error|Error|FAIL" | Select-Object -First 30  # arch-guards

# 3. Cluster fixes by class (drift / deps / Java IT / Helm / docker-compose / gitleaks)
# 4. ONE commit per cluster, push, watch single workflow rerun before next commit
# 5. Iterate until 19/19 green; request review on PR #179
```

---

## Three D-pieces still DEFERRED (separate from CI fix work)

External blockers, NOT touchable in June re-push session:

| | Blocker |
|---|---|
| **D4a** Postgres CDC connector real | Customer WAL config (PUBLICATION + REPLICATION SLOT + role grant) |
| **D4c** Zalo metadata connector real | Customer Zalo OA account + tax filing + creds |
| **D8** silver-tier dual-write cutover | K8s live (FPT Cloud account active) + ClickHouse cluster up |
| **D2** Java VaultClient.java | Java IT fixture rework — needs Linux/CI to repro |

These four are **NOT** part of the CI re-push scope. Address in separate sprints when blockers clear.

---

## Cross-reference

- Sprint plan: `docs/sprint/P15-S9_PLAN.md`
- PR body draft: `docs/sprint/P15-S9_PR_BODY.md`
- Branch state record: commit `bf07758` body
- Memory: `project_session_2026_05_08_p15_s9.md` (will be updated to reflect push happened + CI red)
