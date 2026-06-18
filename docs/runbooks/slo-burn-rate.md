# Runbook — SLO burn-rate alerts

> **Companion alert rules:** `infrastructure/prometheus/slo_alerts.yml`
> **Companion dashboard:** `infrastructure/grafana/dashboards/slo_burn_rate.json`
> **Companion ADR:** none yet — error budget policy lands when we sign
> the first SLA-backed contract.

## What just fired?

Three possible alerts, escalating severity:

| Alert | Window | Threshold | Severity | Meaning |
|---|---|---|---|---|
| `SLOErrorBudgetBurnFast` | 1h | burn ≥ 14.4 | page | Monthly budget exhausted in ~2.5 days at this rate |
| `SLOErrorBudgetBurnSlow` | 6h | burn ≥ 6 | warn | Sustained low-volume degradation |
| `SLOErrorBudgetExhausted` | 30d | error rate > 0.5% | page | Monthly SLA already breached |

Burn rate = `(error rate over window) / 0.005`. SLO is 99.5% availability per service (error budget = 0.5% of requests).

## First 5 minutes

1. Open the burn-rate dashboard: `Kaori — SLO Burn Rate` (uid `kaori-slo-burn`). Both windows should be glowing red if the regression is real.
2. Check `Kaori — SLI Overview` for which service is bleeding. The success-rate stat panel splits by service.
3. Look at the deploy log — anything in the last 2-6 hours? Roll back first, investigate after.

## Investigation tree

- **One service red, others fine** → application-layer regression. `git log` for that service over the burn window, look for the new query / call path. Check the LLM dispatch dashboard if the service is ai-orchestrator (vendor 5xx can swing it).
- **All services red simultaneously** → infrastructure. Check Postgres/Redis/Kafka health, Tempo for shared-dep latency spike, K8s node pressure.
- **One tenant only** → look at the tenant_id breakdown panel in the RAG Router Distribution dashboard. Sometimes a single tenant's bad upload starves the pool. Throttle the tenant + audit their workflow.
- **Only LLM dispatch red** (`LLMDispatchBurnFast` fired alone) → check vendor status pages (Anthropic, OpenAI, Ollama health endpoint). Vendor outage is OUTSIDE our SLO; clear the alert with a postmortem note.

## Common causes (in observed order)

1. **Bad migration deploy** — a NOT NULL column add broke an INSERT path. Catch via the green-vs-red contrast right after a deploy. Roll back, re-add as NULL, backfill, then add the constraint.
2. **Pool exhaustion** — `asyncpg` pool maxed out after a long-running query. Look at `kaori_db_pool_in_use` in the SLI overview if present; if not, `SELECT * FROM pg_stat_activity` to find the holder.
3. **Vendor outage** — Anthropic / OpenAI 5xx surge. K-4 fallback to Qwen local should engage automatically; if it doesn't, check the circuit breaker state at `services/llm-gateway/routing.py`.
4. **Ollama OOM** — Qwen 14B model evicted from VRAM. Check `nvidia-smi` on the Ollama host. Restart container if needed.

## If you can't find it in 30 minutes

1. Page senior engineer.
2. Open incident channel + start the running narrative.
3. Snapshot Grafana panels into the incident channel every 15 minutes.
4. Check error budget — if `SLOErrorBudgetExhausted` is firing, freeze non-critical deploys per the error budget policy.

## Closing the alert

- Burn rate drops below threshold for 30 minutes → alert auto-resolves.
- If the cause was a deploy rollback: tag the rollback commit, write postmortem in `docs/postmortems/YYYY-MM-DD-<slug>.md`.
- If the cause was vendor: acknowledge, note in incident log, no postmortem needed unless customer-visible (vendor outage = their SLO not ours).
