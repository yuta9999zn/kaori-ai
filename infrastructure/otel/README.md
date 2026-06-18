# `infrastructure/otel/` — OpenTelemetry Collector (P1-S2)

> **Status:** skeleton folder. **Sprint P1-S2** deploys.
> **Invariant:** K-19 (OpenTelemetry mandatory; every span MUST carry attribute `tenant_id`).

## Stack

```
                          ┌────────────────────┐
   service pods ──OTel──→ │  OTel Collector    │ ──→ Jaeger (traces, 30d hot)
                          │  (otelcol-contrib) │ ──→ Tempo  (traces, 90d warm — Phase 1.5)
                          │                    │ ──→ Prometheus (metrics, 15d hot)
                          │                    │ ──→ Loki   (logs, 14d hot)
                          └────────────────────┘ ──→ ClickHouse (Phase 1.5+ for long warm)
```

## Phase 1 layout (P1-S2)

```
infrastructure/otel/
├── README.md                     ← this file
├── collector.yaml                (P1-S2) — receivers + processors + exporters
├── jaeger.yaml                   (P1-S2) — Jaeger all-in-one dev
└── helm/                         (P15-S9) — production Collector + Jaeger backend ClickHouse
```

## Service instrumentation

| Service | SDK | Status |
|---|---|---|
| api-gateway (Java) | OTel Java agent (auto-instrument Spring) | 🔵 P1-S2 |
| auth-service (Java) | OTel Java agent | 🔵 P1-S2 |
| data-pipeline (Python) | `opentelemetry-instrumentation-fastapi` | 🔵 P1-S2 |
| ai-orchestrator (Python) | `opentelemetry-instrumentation-fastapi` + manual span cho chat agent loop | 🔵 P1-S2 |
| llm-gateway (Python) | OTel Python | 🔵 P1-S2 |
| notification-service (Python) | OTel Python | 🔵 P1-S2 |

## Span attribute conventions (K-19)

Mọi span PHẢI có:
- `tenant_id` (từ JWT claim hoặc workflow context)
- `service.name`
- `deployment.environment` (`dev` / `staging` / `prod`)

Nên có:
- `workflow_id` (nếu trong workflow context)
- `pipeline_run_id` (nếu trong pipeline)
- `user_id` (cho user-initiated request)

KHÔNG được có:
- PII (email, phone, name, ID number) — masking trước khi set attribute.

## Sampling strategy

- **Phase 1 dev:** 100% (low traffic, debug cần full trace).
- **Phase 1.5 prod:** head-based sampling — 100% errors + 10% successful (SAD Phần 5.4).
- **Per-tenant override:** tenant flag `debug_full_trace=true` ép 100% cho tenant đó (CSM debug tool).

## Custom metrics (Phase 1)

Theo `docs/BACKLOG_V4.md` OBS-007..011:
- `workflow_executions_total` (counter, label workflow_id + tenant_id + status)
- `ai_calls_total` (counter, label provider + model + tenant_id)
- `tokens_total` (counter, label provider + model + tenant_id + direction[input/output])
- `tenant_quota_usage` (gauge, label tenant_id + resource[customers/storage/llm_tokens])
- `nov_per_workflow` (gauge, Phase 1.5+)
- `adoption_score_per_workflow` (gauge, Phase 1.5+)

## References

- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.4 (Observability Stack) + Phần 31
- CLAUDE.md K-19 + §13 tenet 11
- ADR-0013 — `tenant_id` mandatory across stores including OTel
- `docs/BACKLOG_V4.md` P1-S2 (OBS-001..016)
- `docs/_v4_extract/observability.json`
