# Kafka consumer lag spike

> **Severity:** P1 — pipeline appears stuck to users; data ingest still works.
> **Affects:** F-NEW2 (status SSE shows `silver_complete` but never advances), F-021 (results dashboard "still loading")
> **First responder:** anh

## Symptoms

- User uploads a CSV, schema confirm + cleaning succeed, but `/dashboard` keeps showing "đang phân tích".
- `pipeline_runs.status = 'silver_complete'` but no row in `analysis_runs` for that `run_id` after >2 minutes.
- Kafka UI (port 8085) shows `kaori.pipeline.events` consumer lag growing (`ai-orchestrator-pipeline-consumer` group).

## Quick triage (≤ 60 seconds)

- [ ] **Is `ai-orchestrator` running?** `docker compose ps ai-orchestrator` — if exited, **GOTO Mitigation step 1**.
- [ ] **Did Qwen / llm-gateway just OOM?** `docker logs kaori-ollama-1 --tail 50 | grep -i "out of memory\|oom"` — if yes, **GOTO `llm-gateway-down.md`** instead (analysis can't run when Ollama is dead).
- [ ] **Did the lag start after a restart?** Consumer is just catching up; if lag <500 messages, give it 60 s before escalating.
- [ ] **Is the lag a single-tenant runaway?** Check Kafka UI partition distribution — if one partition has 10× others, a tenant uploaded a huge file. Mitigation 3.

## Diagnosis

```bash
# 1. Confirm consumer is alive and registered.
docker exec kaori-kafka-1 kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group ai-orchestrator-pipeline-consumer

# 2. Check ai-orchestrator logs for the consumer task.
docker logs kaori-ai-orchestrator-1 --tail 100 | grep -E "pipeline_consumer|kaori.pipeline.events"

# 3. Look for handler exceptions inside ai-orchestrator (failed message → no commit → lag grows).
docker logs kaori-ai-orchestrator-1 --tail 200 | grep -iE "error|exception|traceback"

# 4. Heavy-tenant check — top messages per partition over the last hour.
docker exec kaori-kafka-1 kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic kaori.pipeline.events \
  --time -1
```

## Mitigation (fastest path)

1. **If consumer container exited or is restart-looping** — `docker compose up -d ai-orchestrator` and watch `docker logs -f` for steady consumer heartbeat (every 3 s).
2. **If a poisoned message is the cause** (handler raises on the same offset repeatedly) — bump the offset past it and triage the message offline:

   ```bash
   # First, identify the offset that's stuck (from logs / consumer group describe).
   # Then advance past it for that partition. ⚠ This drops the message — copy it first.
   docker exec kaori-kafka-1 kafka-consumer-groups.sh \
     --bootstrap-server localhost:9092 \
     --group ai-orchestrator-pipeline-consumer \
     --topic kaori.pipeline.events:N \
     --reset-offsets --to-offset $((STUCK_OFFSET + 1)) --execute
   ```

   Verify lag is decreasing: re-run `--describe`. The dropped message should be reproduced from `pipeline_runs` (we have idempotent re-derivation by design).
3. **If a single tenant is overwhelming** — temporarily pause that tenant's analytics: insert a row into `analytics_pause` (Phase 2; today, ack with the customer that the analysis is queued and will catch up overnight).

## Permanent fix

- Poisoned-message recurrence → add a DLQ topic `kaori.dlq.pipeline.events` (planned in `docs/archive/architecture-v3/SCALE_PLAN.md`). Consumer routes after-3-retry failures there instead of blocking the partition.
- Heavy-tenant fairness → partition by `enterprise_id` (already done) is a precondition; consumer concurrency per partition is the next lever.
- Add Prometheus alert: `kafka_consumer_lag{group="ai-orchestrator-pipeline-consumer"} > 500` for 5 min.

## Postmortem hooks

If lag spike fires twice in a week, capture:
- Did the message that broke the handler reproduce after restart? (Tells us if it's data-driven or transient.)
- Time-to-detect (when did monitoring notice vs when did anh notice).
- Customer impact (how many `pipeline_runs` stuck > 5 min during the window).
