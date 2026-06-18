# Temporal cluster unreachable / worker can't connect

> **Severity:** P1 — workflow runs queue up; in-flight runs may hang
> **Affects:** all Temporal-orchestrated work (P15-S9 D3 onwards): `analyze_pipeline`, `nov_monthly_digest`, future Phase 2 workflows. Queued runs lost only if the worker queue overflows or pods die.
> **First responder:** anh (single dev). Future: rotation.
> **Related:** ADR-0011 (Temporal choice), `infrastructure/temporal/README.md`

## Symptoms

- ai-orchestrator startup logs show: `temporal.client.connecting` followed by repeated reconnect attempts; no `temporal.client.connected`.
- Workflow start API calls (e.g. internal `/internal/workflows/analyze/start`) return `RuntimeError: Temporal client not initialised` or `grpc.aio.AioRpcError: failed to connect`.
- Temporal Web UI (port 8233 dev / `temporal-web.temporal.svc` prod) returns 502 / 503 / connection refused.
- Cron-driven workflows (e.g. `nov_monthly_digest` monthly schedule) miss their fire time — no row in `nov_monthly_digests` for the expected month.

## Quick triage (≤ 60 seconds)

- [ ] **Is the Temporal frontend pod / container running?** `docker compose -f infrastructure/temporal/docker-compose.yml ps` (dev) or `kubectl -n temporal get pods` (prod). If not running → **GOTO Mitigation 1**.
- [ ] **Did Postgres for Temporal go down?** Temporal stores history + visibility in Postgres. `docker logs kaori-temporal-postgres-1 --tail 30` — look for `FATAL` / connection refused.
- [ ] **Is `TEMPORAL_ENABLE_WORKER` set in ai-orchestrator env?** Phase 1.5 default is `false` (intentional opt-in until verified stable). Check `docker compose exec ai-orchestrator env | grep TEMPORAL` — if false, worker isn't running by design, not an outage.
- [ ] **Did anh restart the Temporal cluster recently?** Frontend takes ~30s to register with history+matching after a cold start; client reconnect retries cover this.

## Diagnosis

```bash
# 1. Confirm Temporal cluster pod set state.
docker compose -f infrastructure/temporal/docker-compose.yml ps
# expect: temporal-frontend, temporal-history, temporal-matching, temporal-worker (Auto-Setup), temporal-postgres, temporal-web all "Up"

# 2. Check the Temporal frontend health endpoint.
curl -fsS localhost:7233/api/v1/cluster-info \
  || echo "FRONTEND DOWN — see step 3 for history/matching"

# 3. Tail history + matching logs for crash loops (most common Temporal-side cause).
docker logs kaori-temporal-history-1 --tail 100 | grep -iE "panic|fatal|connection refused"
docker logs kaori-temporal-matching-1 --tail 100 | grep -iE "panic|fatal|connection refused"

# 4. Check Temporal's Postgres backing store.
docker logs kaori-temporal-postgres-1 --tail 50

# 5. Confirm ai-orchestrator worker side — is it logging connect attempts?
docker logs kaori-ai-orchestrator-1 --tail 200 | grep -iE "temporal\.(client|worker|workflow)"

# 6. List active worker registrations against the namespace.
docker exec kaori-temporal-frontend-1 \
  tctl --address temporal-frontend:7233 --ns kaori taskqueue describe kaori-default
```

## Mitigation (fastest path)

1. **Temporal frontend / history / matching not running** — boot the cluster:

   ```bash
   docker compose -f infrastructure/temporal/docker-compose.yml up -d
   # wait ~30s for the auto-setup container to register the 'kaori' namespace
   sleep 30
   # verify
   curl -fsS localhost:7233/api/v1/cluster-info
   ```

   If a service crash-loops: `docker logs --tail 200` to read the panic. Most cold-start failures are Postgres-not-ready — Temporal services exit fast if the backing store is unreachable.

2. **Postgres for Temporal exited** — start it first then restart the Temporal services:

   ```bash
   docker compose -f infrastructure/temporal/docker-compose.yml up -d temporal-postgres
   # wait for ready
   docker exec kaori-temporal-postgres-1 pg_isready -U temporal
   docker compose -f infrastructure/temporal/docker-compose.yml restart \
     temporal-frontend temporal-history temporal-matching
   ```

3. **ai-orchestrator worker can't reach a healthy Temporal cluster** — DNS or env issue. Restart with explicit `TEMPORAL_ADDRESS`:

   ```bash
   docker compose restart ai-orchestrator
   # verify
   docker logs kaori-ai-orchestrator-1 --tail 50 | grep "temporal.client.connected"
   ```

4. **Worker is running but workflows aren't being picked up** — check the task queue is registered + the worker is polling:

   ```bash
   docker exec kaori-temporal-frontend-1 \
     tctl --address temporal-frontend:7233 --ns kaori taskqueue describe kaori-default
   # expect: at least one Pollers entry pointing at ai-orchestrator pod IP / hostname
   ```

   If no pollers despite `TEMPORAL_ENABLE_WORKER=true`, the worker thread crashed silently — restart ai-orchestrator + tail the worker startup line.

5. **Cluster down >5 min and customer-impacting** — communicate: enqueued workflows will resume on cluster recovery (Temporal persistence guarantees), but in-flight activity calls timed out and will retry per the activity's RetryPolicy. No data loss expected; manual nudge for cron schedules that missed their window (e.g. re-run `nov_monthly_digest` for the missed month manually).

## Permanent fix

- **Cold-start ordering** — `infrastructure/temporal/docker-compose.yml` should declare `depends_on: condition: service_healthy` on `temporal-postgres` for frontend/history/matching. Verify + add if missing.
- **Health check contract** — add `healthcheck:` block on each Temporal service in compose so cold-starts wait properly.
- **Prometheus alert** — `temporal_workflow_task_schedule_to_start_seconds` p99 > 5 min for 10 min = page. (P15-S9 D7 cron starts firing in a few weeks; need this alert before then.)
- **Worker pod auto-restart** — K8s deployment `restartPolicy: Always` (default); ensure liveness probe checks the worker is actually polling, not just that the FastAPI app is up.

## Postmortem hooks

If Temporal goes down >2× in a month:

- Capture cluster sizing: history shard count, Postgres connection count, memory used per service.
- Did a workflow recovery on cluster-up create activity-call thundering herd? Adjust per-activity rate limits.
- Time-to-detect vs time-to-mitigate — the Phase 1.5 worker-disabled-by-default makes "is this an outage" ambiguous; once `TEMPORAL_ENABLE_WORKER=true` is the default (Phase 2), define explicit alert.
