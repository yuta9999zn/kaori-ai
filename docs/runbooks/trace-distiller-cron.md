# Runbook — TraceDistillerWorker ops

> **When to use:** monitoring + tuning the T-Cube background worker (P2-S21 ship 2026-05-17, ADR-0021).
> **Audience:** ops + data engineering.
> **Severity:** LOW — worker is opt-in via env, degrades gracefully (no impact if disabled).

## What the worker does

`services/ai-orchestrator/reasoning/trace_distiller/worker.py` polls `decision_audit_log` for rows where:
- `confidence >= 0.6` (default; tunable via `TRACE_DISTILLER_CONFIDENCE`)
- Not yet successfully distilled (no row in `distilled_decisions` table, mig 070, with `error_message IS NULL`)
- `retry_count < 3` (default; tunable via `TRACE_DISTILLER_MAX_RETRIES` — actually hardcoded constant in worker.py today)

For each candidate row, the worker calls `TCubeTransformer.transform_and_store()` which makes **3 parallel LLM calls** (Qwen 2.5 14B default per K-4) to produce Struct / Semantic / Reflect forms, then writes 3 records into Memory L4 PROCEDURAL tier.

## Enable the worker

Default: **OFF**. Set env var on ai-orchestrator service:

```bash
TRACE_DISTILLER_ENABLED=true
TRACE_DISTILLER_POLL_SECONDS=300       # 5 min between batches (default 300)
TRACE_DISTILLER_BATCH_SIZE=20          # rows per batch (default 20)
TRACE_DISTILLER_CONFIDENCE=0.6         # threshold for distillation (default 0.6)
LLM_GATEWAY_URL=http://llm-gateway:8095
LLM_GATEWAY_USE_STUB=false             # set true ONLY for dev / tests
```

Restart ai-orchestrator. Within 5 min you should see structured log lines:

```
trace_distiller.started poll_seconds=300 batch_size=20 confidence=0.6
trace_distiller.cycle    scanned=12 ok=11 failed=1 skipped_conf=3 skipped_retry=0
```

## Health checks

### Is the worker running?

```bash
# Check for cycle log lines in the last hour
kubectl logs -n kaori deployment/ai-orchestrator --since=1h | grep trace_distiller.cycle
```

Expected: at least 12 cycle lines in 1h (one per `TRACE_DISTILLER_POLL_SECONDS`).

### Is it making progress?

```sql
SELECT
  COUNT(*) FILTER (WHERE error_message IS NULL) AS distilled_ok,
  COUNT(*) FILTER (WHERE error_message IS NOT NULL) AS failed,
  AVG(retry_count) AS avg_retries
FROM distilled_decisions
WHERE distilled_at > NOW() - interval '24 hours';
```

Healthy signals:
- `distilled_ok` > 0 (worker is producing)
- `failed / (distilled_ok + failed)` < 5% (LLM gateway reasonably reliable)
- `avg_retries` close to 0 (most rows succeed first attempt)

### Is the L4 PROCEDURAL tier filling up?

```sql
-- Postgres adapter (mig 067 + memory_l3_pgvector)
SELECT
  metadata->>'tcube_form' AS form,
  COUNT(*)
FROM memory_l3
WHERE memory_type = 'PROCEDURAL'
  AND created_at > NOW() - interval '7 days'
GROUP BY 1;
```

Expected: 3 forms (struct / semantic / reflect) with roughly equal counts (every distillation writes all 3).

## Common failures

### "trace_distiller.failed" with LLM gateway 503

The LLM gateway is unhealthy or Ollama is down. Worker auto-retries up to `max_retries` (default 3) before giving up. Check:

```bash
curl http://llm-gateway:8095/health
docker ps | grep ollama
```

### `retry_count` climbing for the same `decision_id`

The row keeps failing. Worker stops retrying after 3 attempts. Investigate the source decision:

```sql
SELECT decision_id, decision_type, length(reasoning) AS reasoning_chars
FROM decision_audit_log
WHERE decision_id = '<uuid_from_distilled_decisions.error>';
```

If `reasoning` is extremely long (> 30K chars), the prompt truncation may corrupt context. Increase `TCubeTransformer.max_tokens_per_form` or pre-summarise.

### Empty L4 PROCEDURAL but worker is running

Check:
- `TRACE_DISTILLER_ENABLED=true` actually set + service restarted
- `LLM_GATEWAY_USE_STUB=false` in prod (stub returns canned text but doesn't fail; just useless)
- `MemoryService` is using the Postgres backend, not in-memory default (env var swap pending Phase 2)

## Performance tuning

| Tunable | Default | Rule of thumb |
|---|---|---|
| `TRACE_DISTILLER_POLL_SECONDS` | 300 | Drop to 60 when decision volume > 100/hour; raise to 900 when < 10/hour |
| `TRACE_DISTILLER_BATCH_SIZE` | 20 | Roughly poll_seconds / 15 — keep one batch's LLM calls finishing within a poll cycle |
| `TRACE_DISTILLER_CONFIDENCE` | 0.6 | Lower → more distillations + more noise; higher → only high-confidence decisions distilled |

## Disable (rollback)

```bash
TRACE_DISTILLER_ENABLED=false
# restart ai-orchestrator
```

Existing distilled traces stay in Memory L4. `distilled_decisions` table preserved for re-enable later.

## Related

- `services/ai-orchestrator/reasoning/trace_distiller/{worker.py,runner.py,transformer.py,prompts.py}`
- `infrastructure/postgres/migrations/070_distilled_decisions_cache.sql`
- ADR-0021 — Trace-augmented reasoning via T-Cube distillation
- ADR-0024 — Mem0-inspired ports (sibling pattern: extract_facts for SEMANTIC, T-Cube for PROCEDURAL)
- Paper: arXiv 2605.03344 (UC Berkeley)
