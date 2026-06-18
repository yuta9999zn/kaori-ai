# `infrastructure/prometheus/` — Prometheus metrics (P1-S2)

> **Status:** existing — `alerts.yml` đã có. **Sprint P1-S2** mở rộng custom metrics + Grafana dashboards + AlertManager.

## Stack

```
                          ┌─────────────────┐
   service pods ─────────→│  Prometheus     │
       ↑                   │  (15d retention)│
       └─/metrics endpoint └────────┬────────┘
                                    │
                              ┌─────┴─────┐
                              ▼           ▼
                          Grafana     AlertManager → PagerDuty (P1-S2 OBS-016)
                                                  → Slack/email
```

## Layout

```
infrastructure/prometheus/
├── README.md                     ← this file (NEW)
├── alerts.yml                    ← existing (P1 v3 alerts)
├── prometheus.yml                (P1-S2) — scrape config
└── rules/                        (P1-S2)
    ├── slo-availability.yml
    ├── slo-latency.yml
    ├── tenant-quota.yml
    └── workflow-reliability.yml
```

## Custom metrics (Phase 1, OBS-007..011)

| Metric | Type | Labels |
|---|---|---|
| `workflow_executions_total` | counter | workflow_id, tenant_id, status, side_effect_class |
| `workflow_duration_seconds` | histogram | workflow_id, tenant_id, status |
| `ai_calls_total` | counter | provider, model, tenant_id, task_type |
| `tokens_total` | counter | provider, model, tenant_id, direction |
| `tenant_quota_usage` | gauge | tenant_id, resource |
| `nov_per_workflow` | gauge | workflow_id, tenant_id (Phase 1.5+) |
| `adoption_score_per_workflow` | gauge | workflow_id, tenant_id (Phase 1.5+) |
| `idempotency_records_total` | counter | tenant_id, side_effect_class, hit/miss |
| `dlq_depth` | gauge | topic, tenant_id |

## Recording rules

Long-form aggregations precomputed (giảm load query Grafana):
- `kaori:workflow_success_rate_5m` (per workflow_id)
- `kaori:tenant_quota_pct` (per tenant)
- `kaori:llm_cost_per_tenant_daily` (USD/VND tracking)

## AlertManager → PagerDuty

OBS-016 + OBS-019. Severity routing:
- P1 critical (response 15 min): tenant data leak, auth-service down, workflow success rate <90%
- P2 high (1 hour): DLQ depth >100, ClickHouse replica lag >5min
- P3 medium (4 hour): tenant quota >95%, LLM provider degraded
- P4 low (24 hour): low NPS feedback, slow query alerts

Per-alert playbook at `docs/runbooks/<alert>.md` — OBS-019.

## References

- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.4 (Observability)
- CLAUDE.md K-19
- `docs/BACKLOG_V4.md` P1-S2 (OBS-006..011, OBS-016, OBS-019)
- `docs/_v4_extract/observability.json`
