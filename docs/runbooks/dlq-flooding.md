# DLQ flooding — `kaori.dlq.*` (Kafka) or `dlq:*` (Redis Streams)

> **Severity:** P1 if depth > 1000 (per ADR-0017 escalation), P2 if 100-1000
> **Affects:** downstream consumers blocked by repeat-failing messages; tenant-facing surface (analysis stuck, NOV digest missing) when traceable to a specific tenant's events
> **First responder:** anh
> **Related:** ADR-0017 (event backbone), CLAUDE.md §7

## Symptoms

- PagerDuty alert: `kaori_dlq_depth{topic="kaori.dlq.pipeline.events"} > 1000` (or any `dlq:*` Redis Stream).
- Kafka UI (port 8085) shows `kaori.dlq.*` topic message count climbing fast.
- Redis CLI: `XLEN dlq:<stream_id>` returns >100.
- Consumer for the source topic (e.g. `ai-orchestrator-pipeline-consumer`) has no lag, but the matching feature isn't producing output for a specific tenant.
- structlog event `dlq.publish` appearing repeatedly in service logs.

## Quick triage (≤ 60 seconds)

- [ ] **Which topic / stream is flooding?** Check the alert label or `redis-cli SCAN MATCH 'dlq:*'` to enumerate. Knowing this picks the right consumer to look at.
- [ ] **Is the DLQ populated by ONE tenant or many?** Sample 10 messages — if all share an `enterprise_id` claim, this is tenant-data-driven; if mixed, infrastructure-driven.
- [ ] **Did this start after a deploy?** A code change that mishandles a previously-OK message shape is the classic cause. Roll back if recent.
- [ ] **Are downstream consumers still healthy?** A flooding DLQ doesn't block the source topic (DLQ is a side channel) — but if the source consumer is also lagging, that's a different problem (`kafka-lag-spike.md`).

## Diagnosis

```bash
# 1. Identify the flood source — Kafka.
docker exec kaori-kafka-1 kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic kaori.dlq.pipeline.events --time -1
# growing offset = active flood

# 2. Identify the flood source — Redis Streams.
docker exec kaori-redis-1 redis-cli --scan --pattern 'dlq:*' \
  | xargs -I{} docker exec kaori-redis-1 redis-cli XLEN {}

# 3. Sample DLQ messages to find the failure class.
docker exec kaori-kafka-1 kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic kaori.dlq.pipeline.events \
  --from-beginning --max-messages 5 \
  --property print.key=true --property print.headers=true
# read the headers — they include the original error class + retry count

# Redis Streams equivalent (last 5 entries with payload).
docker exec kaori-redis-1 redis-cli XRANGE dlq:<stream> - + COUNT 5

# 4. Tail the producing consumer's logs for the underlying error.
docker logs kaori-ai-orchestrator-1 --tail 500 | grep -iE "dlq\.publish|dispatch_failed|retry_exhausted"

# 5. Check whether the source topic is keyed by tenant — if yes, partition affinity tells you which tenant_id is flooding.
docker exec kaori-kafka-1 kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group ai-orchestrator-pipeline-consumer
```

## Mitigation (fastest path)

1. **Roll back the recent deploy** if DLQ flood started immediately after a deploy. The 5-retry policy means most DLQ flood is "code change broke a path on retry". Redeploy the previous tag, drain the DLQ separately:

   ```bash
   git log --oneline services/ai-orchestrator | head -5
   # identify the offending commit; roll back via your usual deploy path
   ```

2. **Single-tenant flood** — pause that tenant's processing, drain the DLQ, then re-enable:

   - For Kafka source: produce a sentinel `pause` event keyed to the tenant; consumer skip-loops on it.
   - For Redis Streams: delete the per-tenant stream entries with `XTRIM s:<tenant>:<event_type> MAXLEN 0` (drops everything queued; only safe if you can re-derive the events from source-of-truth tables).
   - Then patch the failing code path or add a tenant-specific config workaround.

3. **Replay DLQ messages after the fix lands** — DLQ is intentional retry storage:

   ```bash
   # Kafka — produce DLQ messages back to the source topic.
   docker exec kaori-kafka-1 kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 \
     --topic kaori.dlq.pipeline.events \
     --from-beginning --timeout-ms 10000 \
   | docker exec -i kaori-kafka-1 kafka-console-producer.sh \
     --bootstrap-server localhost:9092 \
     --topic kaori.pipeline.events
   ```

   For Redis Streams DLQ, the dispatcher script in `infrastructure/redis/dlq-replay.py` (P15-S10 deliverable — write if missing) reads `dlq:<stream>` and re-publishes to `s:<tenant>:<event_type>`.

4. **Drain the DLQ** if the fix made the failure class permanently obsolete (e.g. removed a deprecated event_type). Truncate the topic / stream — log the fact + tenant impact for postmortem.

## Permanent fix

- **DLQ admin UI** — P15-S10 D2 backlog item per `docs/archive/sprint/p15-s10/P15-S10_PLAN.md` open question 4. Manual replay should not require kafka CLI commands.
- **Per-error-class metrics** — current `dlq.publish` event lacks structured `error_class` label; add so Grafana can break down "what type of failure dominates DLQ".
- **Tenant-aware DLQ alerts** — escalate per-tenant (a single flooding tenant is a real customer issue) separately from infra-wide DLQ flood.
- **Idempotency-key dedup** — REL-005 idempotency_records cache prevents duplicate side-effects on replay; verify the replay path uses it (it should; spot-check after the next replay).

## Postmortem hooks

If DLQ flood >2× in a quarter:

- Total messages DLQ'd vs replayed vs dropped (numerator on data loss).
- Time-to-mitigate — was the per-tenant pause path used? If yes, fast (single-tenant scope); if no, the infra path was slower than ideal.
- Per-tenant breakdown — did one tenant dominate? Suggests their data quality / config needs proactive monitoring.
- Source-of-truth resilience — every DLQ flood that required re-derivation revealed a gap in idempotent-rebuild capability. Track these.
