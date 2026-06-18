# Event Backbone (ADR-0017)

> Tách từ `CLAUDE.md` §7 ngày 2026-05-22. Đọc khi cần biết topic/stream cụ thể, partition count, retention.

Phase 1 hybrid: Kafka cho topic v3 legacy, Redis Streams cho event v4 mới. Migrate khi cần Phase 2.

## Kafka topics (giữ Phase 1)

| Topic | Key | Partitions | Retention | Consumers |
|---|---|---|---|---|
| `kaori.ingest.bronze` | tenant_id | 24 | 7d | medallion-engine |
| `kaori.pipeline.events` | pipeline_id | 12 | 7d | analysis, kg-builder, audit |
| `kaori.decisions.log` | tenant_id | 24 | 90d | audit, explainability |
| `kaori.feedback.actions` | tenant_id | 12 | 30d | feature-store-updater, retrain |
| `kaori.billing.events` | tenant_id | 12 | 90d | billing-aggregator, invoice |
| `kaori.alerts.fire` | tenant_id | 6 | 7d | notification-dispatcher, audit |
| `kaori.dlq.*` | origin key | varies | 30d | manual replay, alerting |
| `kaori.audit.internal` | tenant_id | 12 | 2y | audit, compliance-exporter |

## Redis Streams (Phase 1 v4 mới)

Workflow execution events, adoption signals raw, NOV time-series export, OTel trace bridging.

**Naming convention:**
- `s:{tenant_id}:{event_type}` per-tenant
- `g:{event_type}` global

## Dead Letter Queue (DLQ)

5 retries with exponential backoff (1s → 2s → 4s → 8s → 16s) → `kaori.dlq.{topic}` hoặc `dlq:{stream_id}`.

**Alerting:**
- PagerDuty nếu depth >100
- Escalate >1000

**Recovery console:** `GET /admin/dlq` + `POST /admin/dlq/{source}/{id}/{retry,replay,requeue,discard}` (5-source unified — Kafka DLQ + Redis stream DLQ + workflow_run failed + workflow_idempotency_records expired + workflow_compensation logs). Shipped Phase 2.7 (`011965b`).
