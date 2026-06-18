# ADR-0017 — Redis Streams as event backbone Phase 1, Kafka Phase 2+

> **Status:** proposed
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** `docs/strategic/SAD_SKELETON_V2.md` Phần 5.2 + Phần 36 (Event Schemas) · ADR-0011 (Temporal) · CLAUDE.md §7 Kafka Topics · `docs/BACKLOG_V4.md` P1-S2

## Context

v3 hiện dùng **Kafka 7.5 (Confluent)** làm event bus với 8 topics (`kaori.ingest.bronze`, `kaori.pipeline.events`, `kaori.decisions.log`, ...). v4 SAD Phần 5.2 mention **Redis Streams Phase 1 backbone** — nhẹ hơn, ops đơn giản hơn cho 10-15 khách đầu.

Forces:

1. **Throughput Phase 1 thực tế.** 10-15 khách × ~10K events/ngày = ~150K events/ngày tổng. Kafka quá overkill — Redis Streams handle dễ.
2. **Operational complexity.** Kafka cần Zookeeper (đã có) + broker tuning + topic partition planning + consumer group monitoring. 1 dev khó vận hành solo.
3. **Phase 2 thực sự cần Kafka.** P2-S13/S14 Process Mining 8 sources × 100K customers = ~10M events/ngày. Kafka throughput đáng tiền.
4. **Pilot Olist đang dùng Kafka.** Migrate ngay = phá pilot.

## Decision

Chúng ta giữ **Kafka chạy song song Redis Streams** trong Phase 1; **Redis Streams cho event mới**, **Kafka giữ cho topic v3 đã có**:

1. **Phase 1 — Hybrid:**
   - Topic v3 hiện tại (`kaori.ingest.bronze`, `kaori.pipeline.events`, ...) **giữ nguyên Kafka** — không migrate, không break pilot Olist.
   - Topic v4 mới (workflow execution events, adoption signals raw stream, NOV time-series cho ClickHouse, OTel trace export) **dùng Redis Streams**.
   - Naming convention: Redis stream `s:{tenant_id}:{event_type}` (per-tenant) hoặc `g:{event_type}` (global).
2. **Phase 1.5:** đánh giá throughput thực tế. Nếu Redis Streams OK → tiếp tục. Nếu pressure → migrate v3 topic sang Redis hoặc upgrade Kafka cluster.
3. **Phase 2 — Kafka tuyệt đại đa số:**
   - P2-S13/S14 Process Mining ingestion sang Kafka (throughput cao).
   - Migrate Redis Streams Phase 1 sang Kafka khi consumer group >= 5.
   - Schema registry (Confluent Schema Registry hoặc Apicurio) bật cho Avro/Protobuf.
4. **Schema:** v4 dùng JSON Schema cho Redis Streams (nhẹ); Phase 2 chuyển Avro/Protobuf khi schema registry bật.
5. **Replay:** Redis Streams consumer group tracking offset; XADD/XREAD/XACK pattern. DLQ riêng `dlq:{stream_id}`.

## Consequences

### Positive

- Phase 1 ops đơn giản: Redis cluster đã có; thêm Kafka chỉ cho topic legacy.
- Pilot Olist không gián đoạn.
- Redis Streams latency < Kafka cho payload nhỏ (~1ms vs ~10ms).
- Migrate path rõ ràng: Phase 2 onboard Kafka đầy đủ khi cần.

### Negative / accepted trade-offs

- 2 event bus song song = 2 model debug, 2 client lib, 2 monitoring dashboard.
- Redis Streams retention policy in-memory — TTL cố định (ví dụ 7 ngày) không như Kafka log retention. Mất event nếu Redis OOM.
- Replay history dài hạn (>30 ngày) Kafka tốt hơn — Phase 1 không có nhu cầu này.
- Cross-stream transaction không có (cũng không có Kafka).

### Neutral / follow-ups

- Phase 1.5 Sprint P15-S10 evaluate: nên consolidate về 1 bus chưa? Tiêu chí: ops time on Kafka > 4h/tuần → migrate v3 topic sang Redis Streams; hoặc tổng throughput > 1M event/ngày → migrate sang Kafka đầy đủ.
- Schema versioning: bắt đầu Phase 1 với JSON Schema versioned trong `infrastructure/schemas/`; Phase 2 promote sang Schema Registry.

## Alternatives considered

- **Kafka-only Phase 1.** Rejected: ops cost cho 1 dev cao, throughput thấp Phase 1 không cần.
- **Redis Streams-only, migrate Kafka topic ngay.** Rejected: phá pilot Olist + risk regression.
- **NATS JetStream.** Considered: tốt cho streaming nhẹ, nhưng team không quen, thêm 1 stack mới = chi phí học. Đợi Phase 3 evaluate.
- **AWS SNS/SQS.** Rejected: vendor lock + không deploy được FPT Cloud (ADR-0016).

## References

- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.2 (Redis Phase 1 backbone) + Phần 36
- CLAUDE.md §7 Kafka Topics (giữ nguyên Phase 1)
- ADR-0011 (Temporal — Temporal có internal queue, không phụ thuộc Kafka/Redis cho workflow)
