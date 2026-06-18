# Temporal worker live cutover

> **Status:** Worker code ready since P15-S9 (commit `816fda71`); cluster + namespace bootstrap shipped at `infrastructure/temporal/`. `TEMPORAL_ENABLE_WORKER` defaults to `false` until a sprint explicitly flips it. This runbook is the cutover procedure.

## What's currently shipped

| Component | State | Where |
|---|---|---|
| Temporal cluster image | Ready (not started) | `infrastructure/temporal/docker-compose.yml` |
| Namespace bootstrap | Ready (idempotent) | bootstrap helper in same compose file |
| Worker code | Ready, no-op | `services/ai-orchestrator/workflow_runtime/worker.py` |
| Env flag | `TEMPORAL_ENABLE_WORKER=false` | `temporal_client.py` `_truthy()` parser |
| Workflows registered | 3 in `workflows.py` | memory_loop, distillation, reencrypt (skeleton) |

## When to flip the cutover

- Adoption signal cron load > 10 K events/day → in-process loop blocks event listener; offload to Temporal worker
- Multi-tenant memory L3 vector ingest > 5K rows/day → embedding worker via Temporal beats in-process queue
- Field-key re-encrypt for large tenants (>10K encrypted rows) starts blocking the request thread
- Audit / SLA: workflow audit history needs to survive ai-orchestrator restarts

If none of these apply at current scale, **keep the worker disabled** — every disabled feature is one less moving part to debug.

## First-time cutover procedure

```bash
# 1. Verify host has memory headroom (Temporal cluster ~1.5 GB +
#    auto-setup writes 4 schemas to Postgres).
docker stats --no-stream

# 2. Bring up the Temporal stack alongside main Kaori stack.
docker compose \
  -f docker-compose.yml \
  -f infrastructure/temporal/docker-compose.yml \
  up -d temporal temporal-ui temporal-bootstrap

# 3. Wait for namespace registration (bootstrap container exits cleanly
#    when 'kaori' namespace is registered).
docker logs -f kaori-temporal-bootstrap
# Expected last line: "kaori namespace ready"

# 4. Smoke-test the cluster.
docker exec kaori-temporal tctl --address temporal:7233 cluster health
# Expected: SERVING

# 5. Open Web UI to confirm namespace registered.
#    http://localhost:8088 — should show 'kaori' in the namespace dropdown.

# 6. Flip the worker flag for ai-orchestrator. Either:
#    a) Edit .env and add:
#         TEMPORAL_ENABLE_WORKER=true
#         TEMPORAL_ADDRESS=temporal:7233   # in-network name
#    b) Or pass via docker compose env override.

# 7. Recreate ai-orchestrator so the new env applies.
docker compose up -d --force-recreate --no-deps ai-orchestrator

# 8. Confirm worker connected. Logs should show:
docker logs kaorisystem-ai-orchestrator-1 2>&1 | grep -i temporal | head
# Expected: "temporal_worker.connected task_queue=kaori-default"
```

## Smoke verify worker picks up activities

The worker subscribes to the `kaori-default` task queue. Fire a test workflow:

```bash
docker exec kaori-temporal tctl --address temporal:7233 \
  workflow start \
    --taskqueue kaori-default \
    --workflow_type ReencryptTenantWorkflow \
    --workflowid smoke-test-1 \
    --execution_timeout 60s \
    --input '"<enterprise_id_uuid>"'

# Watch progress
docker exec kaori-temporal tctl --address temporal:7233 \
  workflow describe --workflowid smoke-test-1
```

Expected: workflow transitions through `WORKFLOW_TASK_SCHEDULED` →
`WORKFLOW_TASK_COMPLETED` → terminal state within 60s.

## Rollback

```bash
# 1. Unset / set false the worker flag.
#    Edit .env: TEMPORAL_ENABLE_WORKER=false
docker compose up -d --force-recreate --no-deps ai-orchestrator

# 2. (Optional) stop the cluster to free resources.
docker compose \
  -f docker-compose.yml \
  -f infrastructure/temporal/docker-compose.yml \
  stop temporal temporal-ui temporal-bootstrap

# 3. Confirm rollback. Worker startup log:
docker logs kaorisystem-ai-orchestrator-1 2>&1 | grep -i temporal | tail -1
# Expected: "temporal_worker.disabled reason=TEMPORAL_ENABLE_WORKER not truthy"
```

In-flight workflows: Temporal preserves them in the database. After `temporal stop` → restart, the worker picks up where it left off.

## Production deploy (Phase 3)

Current docker-compose deploy is dev-only:
- ❌ Single-node Temporal — no HA
- ❌ Postgres shared with Kaori main schema — cross-blast-radius
- ❌ No TLS between worker + Temporal frontend
- ❌ Schema auto-setup runs on every boot — slow + risky

Production deploy uses the Helm chart at `infrastructure/temporal/helm/` (skeleton — P15-S9 prep, not yet rendered). Requirements:
1. Dedicated Temporal Postgres cluster (3 nodes)
2. Cassandra or Elasticsearch for visibility store (Postgres visibility is dev-only)
3. mTLS between worker ↔ frontend ↔ history ↔ matching
4. KMS encryption-at-rest for workflow payloads
5. Multi-AZ rolling deploy for the 4 Temporal services

## Troubleshooting

### `temporal_worker.connection_refused`
- Cluster not started, or `TEMPORAL_ADDRESS` env points at wrong host.
- Verify: `docker ps | grep temporal` shows 3 healthy containers; ai-orchestrator can reach `temporal:7233` over the docker network.

### `namespace 'kaori' not found`
- Bootstrap helper didn't finish OR was skipped.
- Re-run: `docker compose -f infrastructure/temporal/docker-compose.yml up temporal-bootstrap`

### Postgres `temporal` schema creation slow
- Auto-setup runs SQL migrations on first boot — first start takes ~30 seconds.
- Restart speeds up after schemas exist.

### Workflow stuck in `WORKFLOW_TASK_SCHEDULED`
- No worker connected to the task queue. Check `TEMPORAL_ENABLE_WORKER=true` is set + ai-orchestrator restarted after flip.
- `docker logs kaorisystem-ai-orchestrator-1 | grep temporal_worker` for connection trace.

### `pidof` / `temporal-server` crash on dev mac
- Apple Silicon needs the linux/arm64 image variant. Edit
  `infrastructure/temporal/docker-compose.yml` and add `platform: linux/arm64`
  to the `temporal` service block.
