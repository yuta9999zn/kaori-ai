# ADR-0011 — Temporal.io for workflow orchestration

> **Status:** proposed
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** `docs/strategic/SAD_SKELETON_V2.md` Phần 18 (Workflow Engine Architecture) · `docs/strategic/WORKFLOW_SYSTEM.md` PART V (45 nodes, saga, idempotency) · `docs/BACKLOG_V4.md` P1-S6

## Context

v4 yêu cầu workflow execution engine support: **45 node types**, **5 side-effect classes** (`pure / read_only / write_idempotent / write_non_idempotent / external`), **saga pattern** cho irreversible action, **idempotency-key per node + per run**, **retry với exponential backoff**, **DLQ admin UI**, **circuit breaker per external service**, **per-node timeout**, **heartbeat for long-running activities**, **per-tenant connection + thread pool isolation**, **Workflow as Code** (YAML import/export).

Phase 1 hiện không có workflow engine. Pipeline DAG hiện tại là Kafka topic chain — không có:
- Idempotency framework (chỉ Idempotency-Key Redis 24h ở API layer, không ở workflow node level).
- Saga compensation (rollback chain).
- Persistent retry state (Kafka consumer crash = retry counter mất).
- Long-running activity heartbeat (>5 phút = timeout → coi như fail, không có cơ chế "still alive").

Các option có sẵn:
- **Temporal.io** — open-source, Go core, official SDK Python/Java/TS, native saga, native idempotency, stateful workflow, exactly-once-effective.
- **Apache Airflow** — DAG scheduler, không native saga, idempotency phải tự làm.
- **Cadence** (predecessor Temporal) — community fork, ít maintained.
- **AWS Step Functions** — vendor lock-in, không phù hợp FPT Cloud VN.
- **Tự build trên Postgres + Redis** — đã có vài startup làm; effort 3-6 tháng cho 1 dev → blocker Phase 1.
- **Celery + custom orchestration** — Python-only, không có saga, retry phức tạp.

## Decision

Chúng ta dùng **Temporal.io** làm workflow orchestration engine cho L4. Sprint P1-S6 deploy Temporal cluster (3-node Raft cho dev pilot, sau scale lên FPT Cloud K8s Phase 1.5):

- **Phase 1 dev:** Temporal docker-compose 1-node (development cluster) trong `infrastructure/temporal/docker-compose.yml`.
- **Phase 1.5+:** Temporal Helm chart trên K8s cluster, Postgres làm persistence, ElasticSearch cho visibility (hoặc tắt visibility để giảm chi phí Phase 1.5).
- **Worker:** `services/ai-orchestrator/workflow_runtime/` chạy embedded worker process (Phase 1 modular monolith). Phase 2 extract sang `services/workflow-engine/`.
- **SDK:** Python SDK cho ai-orchestrator worker. TypeScript SDK cân nhắc Phase 2 nếu frontend cần invoke trực tiếp.
- **Workflow definitions:** Python decorator-based (`@workflow.defn`), 1 file per workflow type. Activity functions trong `activities/`.

## Consequences

### Positive

- Tất cả 12 yêu cầu reliability (saga, idempotency, retry, DLQ, circuit breaker, heartbeat, per-tenant pool, timeout) đã có native trong Temporal.
- Workflow state persistent trong Postgres → restart worker không mất state.
- Visibility UI built-in (Temporal Web) → debug workflow execution trực quan.
- Replay history khi fix bug → re-run từ failure point thay vì re-execute toàn bộ.
- Cộng đồng + docs lớn, Vietnamese SaaS đang dùng (vài startup VN đã production).

### Negative / accepted trade-offs

- Thêm 1 stateful service (Temporal frontend + history + matching + worker) trong stack — operational complexity tăng.
- Postgres persistence của Temporal có thể conflict naming với Postgres business data → dùng schema riêng `temporal` hoặc DB instance riêng.
- Learning curve cho 1 dev: tuần đầu code workflow signature kiểu mới.
- Anh tốn ~1-2 tuần Sprint P1-S6 để học + implement 25 node types đầu tiên. Backlog P1-S6 đã reserve cho việc này.

### Neutral / follow-ups

- Phase 1.5 cân nhắc bật Visibility (ES) vs giữ tắt (chi phí ES cao). Chấp nhận chỉ search workflow theo workflow_id Phase 1.
- Phase 2 extract `services/workflow-engine/` riêng, run thread pool dedicated.
- Phase 3 đánh giá multi-region active-active Temporal (hiện chỉ Phase 3 mới cần).

## Alternatives considered

- **Apache Airflow** — Rejected: DAG-based, không native saga, retry counter trong DB nhưng compensation phải tự code. Không fit 5 side-effect class taxonomy.
- **Tự build Postgres + Redis** — Rejected: 1 dev không đủ thời gian; saga + idempotency framework nặng.
- **AWS Step Functions** — Rejected: vendor lock-in, không deploy được trên FPT Cloud (ADR-0016 VN hosting).
- **Celery + Flower** — Rejected: distributed task queue không phải workflow orchestrator; thiếu state persistence + saga.

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` PART V Phần 18-21
- `docs/strategic/SAD_SKELETON_V2.md` Phần 18-21
- Temporal docs: https://docs.temporal.io
- Backlog v4 P1-S6: 23 reliability features (`REL-001..REL-023`)
