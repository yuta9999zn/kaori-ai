# `infrastructure/loki/` — Loki log aggregation (P1-S2)

> **Status:** skeleton folder. **Sprint P1-S2** deploys.
> **Invariant:** K-19 — every log line MUST carry label `tenant_id` (OBS-014/015).

## Phase 1

```
infrastructure/loki/
├── README.md                     ← this file
├── docker-compose.yml            (P1-S2) — Loki single-node + Promtail collector
├── loki-config.yaml              (P1-S2)
└── promtail-config.yaml          (P1-S2) — pod log scraper + label injection
```

## Log shipping

- **Source:** structured JSON logs từ mỗi service (OBS-012 — chuẩn hóa logger Phase 1 P1-S1).
- **Collector:** Promtail DaemonSet (Phase 1.5+ on K8s) hoặc Promtail container Phase 1.
- **Aggregation:** Loki cluster Phase 1.5+; single-node Phase 1.
- **Retention:** 14 days hot in Loki, 90 days cold trong S3-compatible (MinIO Phase 1, FPT S3 Phase 2).

## Mandatory labels

- `tenant_id` (K-19)
- `service.name`
- `level` (`info` / `warn` / `error` / `debug`)
- `trace_id` + `span_id` (OBS-014) — link sang Jaeger trace
- `workflow_id` (nếu workflow context)
- `pipeline_run_id` (nếu pipeline context)

## Querying

LogQL example (xem error logs của tenant X trong 1 giờ qua):

```logql
{tenant_id="t_001", service_name=~"data-pipeline|ai-orchestrator", level="error"}
  |= "kafka"
  | json
  | line_format "{{.timestamp}} {{.message}}"
```

## Vault audit

`vault-audit` stream tách riêng trong Loki (retention 2 years per ADR-0010). Không trộn với app logs.

## References

- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.4 (Observability Stack)
- CLAUDE.md K-19
- `docs/BACKLOG_V4.md` P1-S2 (OBS-013..015)
