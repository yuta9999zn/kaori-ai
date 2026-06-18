# ADR-0012 — Postgres + ClickHouse polyglot persistence

> **Status:** proposed
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** `docs/strategic/SAD_SKELETON_V2.md` Phần 5.2 (Persistence Layer) · Phần 9 (Bronze/Silver/Gold) · ADR-0002 (medallion) · `docs/BACKLOG_V4.md` P1-S4

## Context

v4 đẩy 4 loại workload lên cùng 1 cluster:

1. **Transactional** — workflows, configs, ACLs, idempotency_records, audit_log, billing (Postgres-style ACID).
2. **Analytical / time-series** — OpenTelemetry traces, workflow execution metrics, adoption signals events, NOV time-series (columnar OLAP).
3. **Object storage** — bronze parquet, exports, model artifacts (blob).
4. **Cache + locks + streams** — session, rate limiting, distributed lock, Redis Streams event bus (in-memory).

Hiện tại codebase dùng:
- **Postgres 15 + pgvector** cho mọi thứ (transactional + Gold materialized views + vector embedding).
- **Redis 7** cho cache + idempotency 24h + rate limit.
- **Kafka 7.5** cho event bus.
- **Filesystem cục bộ** cho file upload (chưa MinIO).

Nếu shoehorn workload analytical vào Postgres, vài vấn đề rõ:
- Span trace 100M-row/tháng làm bloat WAL + vacuum cost (TOAST).
- Workflow execution metrics theo phút × per tenant × per workflow = dễ vào nhiều tỷ row Phase 2.
- Aggregation query `SUM(...)/GROUP BY tenant_id, hour` trên row-store = full scan; OLAP đòi columnar.

## Decision

Chúng ta tách persistence theo workload (polyglot), nhưng **incremental rollout**:

- **Postgres 15 (đã có)** — transactional + RLS multi-tenant (ADR-0013) + pgvector tạm thời cho RAG cho đến khi Pinecone/Qdrant Phase 1.5. Schema riêng `temporal` cho Temporal workflow persistence (ADR-0011). Schema chính `kaori` cho business.
- **ClickHouse 3-node (Phase 1.5 sprint P15-S10 hoặc sớm hơn nếu cần)** — Silver tier columnar storage; OTel trace storage (90 days warm); workflow execution metrics; adoption signal events; NOV time-series. 3 node sharded + replicated.
- **MinIO distributed (Phase 1 sprint P1-S3)** — Bronze tier object storage; PDF/Excel export; backup destination. Bucket prefix per tenant.
- **Redis 7 (đã có)** — cache, distributed lock, idempotency_records short-TTL (long-term: Postgres `idempotency_records` table — REL-005), Redis Streams event bus Phase 1.
- **Pinecone (managed, Phase 1.5+)** — vector RAG; Qdrant fallback cho khách data-residency strict; pgvector retire dần.

Phase 1 vẫn chỉ Postgres + Redis + MinIO mới. ClickHouse + Pinecone bật ở Phase 1.5. Kafka giữ song song Redis Streams Phase 1 để pilot Olist không bị break.

## Consequences

### Positive

- Mỗi workload chạy trên engine tối ưu cho nó. Span trace ClickHouse = 10x throughput vs Postgres TOAST.
- ClickHouse có TTL native cho retention policy (90 days warm + 1 year cold downsampled) → không cần cron purge.
- pgvector retire = giải phóng Postgres khỏi vector index lớn (1M-vector index = ~4 GB RAM).
- Bronze trên MinIO = immutable + S3-compatible → backup + replay đơn giản.

### Negative / accepted trade-offs

- 4 storage system cần ops khác nhau (Postgres replica, ClickHouse keeper, MinIO erasure coding, Redis cluster). 1 dev khó vận hành solo → Phase 1 vẫn chỉ Postgres + Redis + MinIO; ClickHouse + Pinecone Phase 1.5 mới onboard.
- Đồng bộ Postgres ↔ ClickHouse cần Debezium hoặc dual-write code → bug surface mới.
- Cost: ClickHouse 3-node + Pinecone managed thêm chi phí infra ~$200-500/tháng (Phase 1.5+).
- Transactional consistency cross-store không có (saga compensation phải dùng — ADR-0011).

### Neutral / follow-ups

- Phase 1.5 quyết định: ClickHouse self-hosted (Altinity Operator) hay managed (ClickHouse Cloud)? Self-hosted ưu tiên cho VN data residency.
- Phase 2 đánh giá: pgvector có còn cần không? Nếu Pinecone OK thì retire. Nếu khách strict data residency thì Qdrant self-hosted.
- ClickHouse migration script: kế thừa từ Pipeline Unified Phần 3.6 (Apache Parquet schema → ClickHouse table).

## Alternatives considered

- **All-Postgres + TimescaleDB extension.** Rejected: pgvector + Timescale + business schema cùng cluster = single point of failure; Timescale + ClickHouse không đối thủ cho compression ratio.
- **All-ClickHouse (transactional + analytical).** Rejected: ClickHouse không tốt cho transactional workload (no UPDATE chuẩn, no FK, no row-level lock).
- **AWS Aurora + Redshift.** Rejected: vendor lock-in, không deploy được trên FPT Cloud.
- **Trino + Iceberg + S3.** Rejected: query engine + table format, vẫn cần OLAP engine cho hot trace; complexity gấp 3 lần ClickHouse cho 1 dev.

## References

- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.2 + Phần 9
- `docs/strategic/PIPELINE_UNIFIED.md` Phần 3.6 (Silver storage Apache Parquet) + Stage 8 (Gold layer)
- ADR-0002 (medallion architecture)
