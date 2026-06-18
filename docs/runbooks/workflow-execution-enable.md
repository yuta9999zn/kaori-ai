# Workflow Execution — Enable Runbook

> **Closes:** workflow-gap audit 2026-05-19 items "Templates are seed-only" + "Cron schedules pending Temporal worker"
> **Status:** Commit 1+2 ship in-process executors (POST /workflows/{id}/run live, no Temporal needed). Commit 3 adds Temporal cron workflows for adoption + nov. This runbook covers turning Temporal on.

---

## Current state (read first)

| Path | Engine | Trigger | Required env |
|---|---|---|---|
| **Custom workflow run** (built in Studio, 25 mig 069 templates) | **In-process runner** (commit 1+2) | `POST /workflows/{id}/run` user-driven | none — works today |
| Workflow approval resume | In-process | `POST /workflow-runs/{id}/approve` | none |
| Form submission ingest | In-process | `POST /workflow-form-submissions` | none |
| **NOV monthly digest** | Temporal cron | `temporal schedule create --cron "0 0 1 * *"` | `TEMPORAL_ENABLE_WORKER=true` |
| **Adoption hourly aggregator** | Temporal cron | `temporal schedule create --cron "0 * * * *"` | `TEMPORAL_ENABLE_WORKER=true` |
| Memory loop (consolidate/promote/forget/embed) | Temporal cron | per-task schedules | `TEMPORAL_ENABLE_WORKER=true` |
| Analyze pipeline | Temporal one-shot | invoked from `/analytics/runs` | `TEMPORAL_ENABLE_WORKER=true` |

**Today (2026-05-19):** in-process runner works, cron path waits for Temporal cluster. Templates RUN via in-process — no degraded UX.

---

## Step 1 — Verify Postgres migrations applied

The runner + cron path need migs 088, 089, 090:

```bash
docker compose exec postgres psql -U kaori -d kaori_dev -c \
  "SELECT version FROM schema_history WHERE version IN ('088','089','090') ORDER BY version;"
```

Expected: 3 rows. If any missing, Flyway will re-apply on next service restart.

---

## Step 2 — In-process execution (works without Temporal — already live)

### 2a. Create a workflow from template

```bash
curl -X POST http://localhost:8093/workflows/from-template \
  -H "X-Enterprise-ID: <UUID>" \
  -H "Content-Type: application/json" \
  -d '{"template_id": "<discount-approval-template-id>"}'
```

Returns `{workflow_id, name, status: "draft"}`.

### 2b. Activate the workflow

```bash
curl -X PUT http://localhost:8093/workflows/<workflow_id> \
  -H "X-Enterprise-ID: <UUID>" \
  -d '{"status": "active"}'
```

### 2c. Run it

```bash
curl -X POST http://localhost:8093/workflows/<workflow_id>/run \
  -H "X-Enterprise-ID: <UUID>" \
  -H "X-User-ID: <UUID>" \
  -H "Idempotency-Key: my-test-001" \
  -d '{"input_data": {"submission_id": "<form-uuid>"}, "trigger_source": "manual"}'
```

Returns 202 + `{run_id, status: "pending"}`. Poll:

```bash
curl http://localhost:8093/workflow-runs/<run_id> \
  -H "X-Enterprise-ID: <UUID>"
```

Status transitions: `pending → running → awaiting_approval` (if approval_gate fires) `→ completed` or `failed`.

### 2d. If 422 "Workflow has nodes without registered executors"

Response body lists `missing_node_types[]`. These nodes have catalog entries but no Python executor yet. As of commit 3:

**Registered (8/45):** `if_else`, `switch`, `aggregate`, `read_table`, `update_record`, `send_email`, `approval_gate`, `read_form_submission`

**Missing (37/45):** AI nodes (`classify_text`, `rag_query`, `call_insight_engine`, `call_risk_detection`, `call_forecasting`, `generate_narrative`, `extract_entities`, `call_recommendation_engine`), action nodes (`send_chat_message`, `send_sms`, `create_task`, `call_api`, `trigger_workflow`, `export_file`, `generate_report`), data nodes (`read_email`, `read_calendar`, `read_chat`, `read_webhook`, `read_api`, `read_file_upload`, `join`, `merge`, `sort`, `filter`, `transform`, `deduplicate`, `validate`, `enrich`, `data_input`, `decision`), output (`save_to_database`, `display_dashboard`, `publish_insight`, `publish_alert`, `log`), decision (`scheduled_trigger`, `wait_for_condition`).

P1 follow-up commit lands these — each is one executor class + a few tests.

### 2e. Resume an approval gate

```bash
curl -X POST http://localhost:8093/workflow-runs/<run_id>/approve \
  -H "X-Enterprise-ID: <UUID>" \
  -H "X-User-ID: <UUID>" \
  -H "X-User-Role: MANAGER" \
  -d '{"decision": "approve", "decision_note": "OK to proceed"}'
```

Or reject:

```bash
... -d '{"decision": "reject", "decision_note": "Margin too low"}'
```

K-13 authz: server rejects 403 if `X-User-Role` not in the gate's `approver_roles[]`, or `X-User-ID` ≠ pinned `approver_user_id`.

---

## Step 3 — Enable Temporal worker (for cron schedules)

### 3a. Start Temporal cluster (dev profile)

If not already running:

```bash
docker compose up -d temporal temporal-ui
```

Check namespace:

```bash
docker compose exec temporal tctl --namespace default namespace describe
```

### 3b. Flip the worker flag

In `.env` (dev) or your Helm values (prod):

```env
TEMPORAL_ENABLE_WORKER=true
TEMPORAL_TARGET_HOST=temporal:7233
TEMPORAL_TASK_QUEUE=kaori-default
TEMPORAL_NAMESPACE=default
```

Restart ai-orchestrator:

```bash
docker compose restart ai-orchestrator
```

Verify worker registered:

```bash
docker compose logs ai-orchestrator | grep -E "worker.started|workflows registered"
```

Expected log: `workflow_runtime.worker.started workflows=6 activities=18 task_queue=kaori-default`

### 3c. Register cron schedules

**Adoption hourly aggregator** (every hour at minute 0):

```bash
docker compose exec temporal temporal schedule create \
  --schedule-id adoption-hourly \
  --cron "0 * * * *" \
  --workflow-id adoption-hourly-aggregator \
  --task-queue kaori-default \
  --type adoption_hourly_aggregator
```

**NOV monthly digest** (1st of each month, 00:00):

```bash
docker compose exec temporal temporal schedule create \
  --schedule-id nov-monthly \
  --cron "0 0 1 * *" \
  --workflow-id nov-monthly-{enterprise} \
  --task-queue kaori-default \
  --type nov_monthly_digest
```

**Memory maintenance** (every 6 hours):

```bash
docker compose exec temporal temporal schedule create \
  --schedule-id memory-maintenance \
  --cron "0 */6 * * *" \
  --workflow-id memory-maintenance \
  --task-queue kaori-default \
  --type memory_maintenance
```

### 3d. Verify schedule fires

```bash
docker compose exec temporal temporal schedule list
```

Then check Postgres for first snapshot row (after the hour boundary):

```bash
docker compose exec postgres psql -U kaori -d kaori_dev -c \
  "SELECT enterprise_id, captured_at, health_score, classification
   FROM adoption_health_snapshots
   ORDER BY captured_at DESC LIMIT 10;"
```

---

## Step 4 — Holster (rollback)

If anything breaks:

```bash
# 1) Disable schedules
docker compose exec temporal temporal schedule delete --schedule-id adoption-hourly
docker compose exec temporal temporal schedule delete --schedule-id nov-monthly
docker compose exec temporal temporal schedule delete --schedule-id memory-maintenance

# 2) Disable worker
# Set TEMPORAL_ENABLE_WORKER=false in .env and restart
docker compose restart ai-orchestrator
```

In-process runner (commit 1+2) keeps working — it has zero Temporal dependency.

---

## Step 5 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `POST /workflows/{id}/run` returns 422 missing_node_types | Workflow has unregistered nodes | Implement executor for listed types OR remove those nodes from the workflow |
| Approval `POST /approve` returns 403 | Caller's `X-User-Role` not in `approver_roles` | Check JWT role claim + workflow_approvals.approver_roles |
| `adoption-hourly` schedule fires but 0 snapshots | `TEMPORAL_ENABLE_WORKER=false` OR worker can't reach Postgres | Check ai-orch logs for `worker.started`; verify mig 090 applied |
| Snapshot UPSERT fails — duplicate captured_at | Two workers running same schedule | `temporal schedule list` then delete duplicates |
| Run stuck in `running` for hours | Background task crashed | Check `workflow_runs.error_summary` + ai-orch logs for `workflow_run.background_crashed` |
| Form submission not picked up | `status != 'pending'` OR wrong `form_key` | `SELECT * FROM workflow_form_submissions WHERE form_key = ... ORDER BY submitted_at DESC LIMIT 5` |

---

## Out of scope (future commits)

- 37 remaining executors (AI nodes wrap existing services, action nodes wrap external integrations, data nodes wrap connectors).
- Per-tenant schedule registration UI (today schedules are global per workflow; add UI in P2-26 builder to register Temporal Schedule rows).
- Saga compensation runtime (REL-011/012 — declared in node config but not auto-fired today).
- Workflow versioning (immutable published version; today edits mutate in place).
