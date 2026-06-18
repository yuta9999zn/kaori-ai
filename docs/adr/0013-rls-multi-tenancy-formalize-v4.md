# ADR-0013 — Multi-tenancy via RLS + tenant_id everywhere (v4 formalize)

> **Status:** accepted
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0003 (Postgres RLS tenant isolation) · `docs/strategic/SAD_SKELETON_V2.md` Phần 29 (Multi-Tenancy Architecture) · `docs/BACKLOG_V4.md` P1-MTNT-001/002 · K-1 / K-12

## Context

ADR-0003 đã chốt RLS làm primitive isolation. v4 mở rộng phạm vi: **mọi layer** (L0 → L5) đều phải mang `tenant_id`. Phase 1 v3 đã RLS cutover (Sprint 0.5 PR #66) trên Postgres. v4 cần formalize cho:

- **ClickHouse** (Phase 1.5+) — tenant_id partition key + WHERE filter trong mọi query.
- **MinIO** — bucket prefix `s3://kaori-bronze/tenant_{id}/...`.
- **Redis** — key prefix `t:{tenant_id}:...` cho cache + lock + stream.
- **Vault** — secret path `/tenant/{tenant_id}/...`.
- **OTel span** — attribute `tenant_id` mandatory (OBS-003, K-19 mới).
- **Loki log** — label `tenant_id`.
- **Temporal** — workflow_id chứa tenant_id prefix; namespace per environment, không per tenant (chi phí).
- **K8s NetworkPolicy** — Calico CNI deny cross-tenant pod traffic Phase 2.

Threat model (Phase 1 v4 đã land 2 mới): `P1-MTNT-001` cross-tenant access attempt monitoring + `P1-MTNT-002` continuous RLS leak testing in CI/CD.

## Decision

Chúng ta giữ RLS làm primitive isolation và **mở rộng tenant_id propagation cho mọi layer mới**:

1. **Postgres RLS** (đã có) — `acquire_for_tenant(tenant_id)` GUC + `BYPASSRLS` chỉ cho migration role + repository module có `# tenant-filter-lint: allow` annotation.
2. **ClickHouse** — `ORDER BY (tenant_id, ts)` + `PARTITION BY tenant_id, toYYYYMM(ts)` + query rewriter trong service layer thêm `WHERE tenant_id = $1` (ClickHouse không có RLS native trước v23+).
3. **MinIO** — IAM policy per-tenant bucket prefix; SDK wrapper `kaori_storage.get_object(tenant_id, key)` ép prefix.
4. **Redis** — wrapper `kaori_redis.get(tenant_id, key)` ép prefix `t:{tid}:`.
5. **Vault** — Vault policy template per-tenant `/tenant/{tenant_id}/*`; auth role bind to JWT claim `tenant_id`.
6. **OTel** — middleware FastAPI/Spring inject `tenant_id` attribute vào every span; Jaeger search by tenant.
7. **Temporal** — workflow_id `t-{tenant_id}-{run_id}`; signal/query require tenant_id match.
8. **K8s** — Phase 2 Calico NetworkPolicy deny pod-to-pod cross-tenant; Phase 1 dựa vào application-layer check.
9. **CI gate** — `P1-MTNT-002` test suite chạy mỗi PR: insert row tenant A, query với tenant B context, expect 0 row.

JWT claim `tenant_id` (cho enterprise) hoặc `enterprise_id` là **single source of truth**; tenant_id KHÔNG được nhận từ query string / header / body (K-12 giữ nguyên).

## Consequences

### Positive

- 1 model isolation thống nhất. Engineer mới onboard học 1 lần áp dụng mọi nơi.
- CI test (`P1-MTNT-002`) bắt regression ngay tại PR — không phải pen-test sau prod.
- Vault policy templating + Postgres RLS + bucket prefix chồng nhau → defense in depth.
- Audit log "cross-tenant access attempt" (`P1-MTNT-001`) dễ implement vì tenant_id ở mọi span.

### Negative / accepted trade-offs

- Mỗi storage backend có cách enforce khác nhau (RLS vs query rewrite vs bucket prefix vs key prefix). Code phải có wrapper layer `kaori_*` cho mỗi backend → boilerplate.
- ClickHouse không native RLS (v23.4+ có experimental) → phụ thuộc query rewriter trong service. Bug rewriter = leak. Mitigation: `P1-MTNT-002` test cover ClickHouse.
- Performance overhead RLS đo được ~5-15% trên Postgres. Chấp nhận.
- Tenant_id partitioning ClickHouse — nếu N tenant lớn (>10000), partition count cao. Phase 3 cần re-evaluate (multi-tenant bucketing).

### Neutral / follow-ups

- Phase 1.5 implement query rewriter ClickHouse + smoke test.
- Phase 2 enable Calico NetworkPolicy.
- Phase 3 xem xét ClickHouse v23.4+ RLS experimental.

## Alternatives considered

- **Schema per tenant (Postgres).** Rejected ADR-0003: schema migration khi 1000+ tenant = unmanageable.
- **Database per tenant.** Rejected: chi phí + ops gấp N.
- **Application-layer-only filter (no RLS).** Rejected: 1 missing WHERE = leak. RLS là safety net.

## References

- ADR-0003 (Postgres RLS tenant isolation)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 29
- K-1 + K-12 trong `CLAUDE.md`
- Memory `feedback_medallion_separation.md` (Bronze/Silver/Gold separation reinforces this)
