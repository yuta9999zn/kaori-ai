# Runbooks

Operational playbooks for typical pilot incidents. **Goal: anh on-call should be able to triage in under 5 minutes, even at 2 AM.**

Each runbook follows the same shape so finding info under stress is muscle memory:

```
# {{Symptom}}

## Symptoms          ← what the user / monitor sees
## Quick triage      ← the 60-second decision tree
## Diagnosis         ← commands to confirm root cause
## Mitigation        ← fastest path back to "users not blocked"
## Permanent fix     ← what we do after the page closes
## Postmortem hooks  ← what to capture if this becomes recurring
```

## Active runbooks

| Topic                                        | When to read it                                        |
|----------------------------------------------|--------------------------------------------------------|
| [Kafka consumer lag spike](kafka-lag-spike.md) | Pipeline stuck at `silver_complete`, analysis never starts |
| [Redis OOM / eviction storm](redis-oom.md)   | Login latency jumps, idempotency-key dedup misses      |
| [LLM gateway down](llm-gateway-down.md)      | Chat returns "LLM Gateway lỗi" or analysis fails       |
| [AI cost overrun](ai-cost-overrun.md)        | External LLM bill spike, runaway tool loop suspected   |
| [Telegram bridge down](telegram-bridge.md)   | REL-011 approval taps not landing in workflow_approvals |
| [Temporal cluster down](temporal-down.md)    | Workflow runs queue up; cron schedules miss fire time   |
| [DLQ flooding](dlq-flooding.md)              | `kaori.dlq.*` or `dlq:*` Redis Stream depth alerting    |
| [Vault rotation / unsealed](vault-rotation.md) | Sealed Vault P0; routine secret rotation P2          |
| [ClickHouse replication lag](ck-replication-lag.md) | Silver-tier reads stale; replica read-only mode  |

## Adding a new runbook

Trigger to write one: anh just spent >30 min debugging an issue that *will recur*. Use the template:

```bash
cp docs/runbooks/_template.md docs/runbooks/{slug}.md
# fill in. Append to the table above.
```

Don't write a runbook for an issue that happened once and was a typo. Write it when the problem class is real and repeating.
