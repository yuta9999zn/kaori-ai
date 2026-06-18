# ADR-0014 — At-least-once delivery + idempotency, not exactly-once

> **Status:** proposed
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** `docs/strategic/SAD_SKELETON_V2.md` Phần 32 (Reliability) · `docs/strategic/WORKFLOW_SYSTEM.md` Phần 2.1 (5 side-effect classes) · `docs/BACKLOG_V4.md` P1-S6 REL-001..REL-023 · K-13 / K-17

## Context

v4 cần giải quyết: **một event được consume đúng một lần** (exactly-once) là illusion trong distributed system. Network retry, pod restart, partial failure đều dẫn tới duplicate delivery. Hai cách approach:

1. **Exactly-once messaging** — Kafka EOS (transactional producer + consumer). Phức tạp, throughput thấp, không cover saga compensation, vendor lock-in nặng (Kafka EOS riêng).
2. **At-least-once + idempotency at consumer** — accept duplicate, design consumer để xử lý duplicate an toàn. Workflow engine (Temporal) + idempotency_records table + side-effect class taxonomy = đủ.

Vấn đề Phase 1 v3 hiện tại:
- Idempotency-Key ở API layer (Redis 24h) — chỉ cover REST mutation, không cover workflow step.
- Kafka consumer có retry policy nhưng không có dedupe ở consumer level → một message replay = side-effect chạy 2 lần.
- Workflow node hiện không khai báo side-effect class → cùng 1 retry policy cho mọi loại (gửi email retry = spam khách).

v4 (Workflow System Phần 2.1) định nghĩa **5 side-effect class**:

| Class | Ví dụ | Retry policy |
|---|---|---|
| `pure` | tính toán, parse | retry tự do, no dedup cần |
| `read_only` | SELECT, GET | retry tự do, có thể cache |
| `write_idempotent` | UPSERT theo natural key, set field giá trị tuyệt đối | retry với same idempotency_key |
| `write_non_idempotent` | INSERT auto-id, increment counter | distributed lock + idempotency_records dedup |
| `external` | gửi email, charge thẻ, gọi 3rd-party API | provider-side dedup key + saga compensation |

## Decision

Chúng ta áp dụng **at-least-once delivery + per-class idempotency strategy**:

1. **Mọi node trong workflow YAML phải khai báo `side_effect_class`** (REL-002 — K-17 mới). Workflow validator reject nếu thiếu.
2. **`write_idempotent`**: Activity tự sinh `idempotency_key = sha256(workflow_id + node_id + run_id + input_hash)` và pass xuống storage layer.
3. **`write_non_idempotent`**: Distributed lock Redis (`SET NX EX`) + `idempotency_records` Postgres table (REL-005, TTL 7 days) + check-before-act pattern.
4. **`external`**: Provider-side dedup khi có (SendGrid `X-MC-Unique-Email`, Twilio idempotency-key, Stripe idempotency-key). Nếu provider không support → saga compensation declared in YAML (REL-012).
5. **Retry policy** per node (REL-008): `max_attempts`, `initial_backoff`, `max_backoff`, `multiplier`. Respect `Retry-After` header (REL-009). Per-tenant rate limit retries (REL-010).
6. **DLQ** sau exhausted retries: workflow vào `kaori.dlq.{topic}`, admin UI review/reprocess/discard (REL-015/016).
7. **Saga orchestrator** chạy trên Temporal (REL-013); compensation chain tự động khi 1 step fail.
8. **Idempotency-Key API layer** (K-13 hiện tại) giữ nguyên — chỉ cover REST entry point.

## Consequences

### Positive

- Mỗi node có policy đúng cho loại side-effect của nó. Không spam email do retry.
- Compensation rõ ràng → khi external API fail, các step trước rollback an toàn.
- DLQ admin UI giúp ops xử lý workflow stuck.
- 5-class taxonomy là "code review checklist" — reviewer hỏi "class gì?" → tác giả phải nghĩ.

### Negative / accepted trade-offs

- Mỗi node tăng boilerplate (decorator class, retry policy, optional compensation).
- `idempotency_records` Postgres table phình to (Phase 1 estimate ~10K records/ngày/tenant). TTL 7 days → manual purge cron.
- Provider-side dedup không phải nơi nào cũng có — saga compensation phải code thủ công.
- Distributed lock Redis có failure mode (network partition → 2 lock holders). Acceptable, mitigation: monitor + alert.

### Neutral / follow-ups

- Phase 1.5 audit toàn bộ Phase 1 node → đảm bảo 100% có `side_effect_class`.
- Phase 2 đánh giá distributed lock → có cần Redlock multi-node hay không (hiện single Redis Cluster đủ).
- Phase 3 đánh giá Temporal Activity Cache vs Postgres `idempotency_records` (Temporal có built-in idempotency cho activity start, nhưng không cho external side-effect).

## Alternatives considered

- **Kafka EOS (transactional).** Rejected: chỉ cover Kafka chain, không cover external side-effect; throughput drop ~30%; complexity cao.
- **Bypass idempotency, "good enough" duplicate.** Rejected: gửi 2 email = customer complain; charge 2 lần = legal issue.
- **Outbox pattern only.** Used as supplement: outbox + idempotency_records + saga đều dùng. Outbox solo không cover saga compensation.

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` Phần 2.1 + PART IX (Reliability)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 32
- `docs/BACKLOG_V4.md` P1-S6 (REL-001..REL-023)
- K-13 (Idempotency-Key API), K-17 mới (side-effect class declaration)
