# `infrastructure/minio/` — MinIO object storage (P1-S3)

> **Status:** skeleton folder. **Sprint P1-S3** (Phase 1 Sprint 3) deploys.
> **Used by:** `services/data-pipeline/data_plane/bronze/` (Bronze tier) + exports + backups + model artifacts.

## Phase 1 dev (P1-S3)

```
infrastructure/minio/
├── README.md                     ← this file
├── docker-compose.yml            (P1-S3) — single-node MinIO + Console
├── policies/                     (P1-S3) — IAM-style policies per tenant
│   └── tenant-readwrite.template.json
└── helm/                         (P15-S9) — distributed mode 4-node FPT Cloud
```

## Bucket layout (ADR-0013)

```
s3://kaori-bronze/
  └── tenant_{tenant_id}/
      ├── files/
      │   └── {pipeline_run_id}/
      │       ├── original.{xlsx,csv,json}    ← raw upload, immutable (K-2)
      │       └── manifest.json               ← SHA-256 + metadata
      └── ingestion/
          └── {connector}/
              └── {date}/                     ← per-day partition
                  └── *.parquet               ← normalized event log

s3://kaori-exports/
  └── tenant_{tenant_id}/
      └── reports/                            ← PDF/PPT exports

s3://kaori-backups/
  └── postgres/, clickhouse/, vault/          ← daily backup destination
```

**Tenant isolation:** bucket prefix `tenant_{id}/`. SDK wrapper `kaori_storage.get_object(tenant_id, key)` ép prefix — không cho code application gọi raw S3 client.

## Operational notes

- **Encryption:** SSE-S3 enabled (server-side, AES-256). Per-tenant KMS Phase 2 nếu cần.
- **Versioning:** ON cho `kaori-bronze` (K-2 immutability — version cũ giữ lại cho replay).
- **Retention:** Bronze giữ 1 năm; export 90 ngày; backup 30 ngày.
- **Access logs:** ON, ship sang Loki.

## Phase 1 fallback

Nếu Phase 1 chưa kịp deploy MinIO (sprint slip), bronze tạm dùng filesystem local trong volume Docker — không tách bucket. Acceptable cho pilot Olist (10K row Olist không lớn).

## References

- `docs/strategic/PIPELINE_UNIFIED.md` Stage 1 (Upload + Bronze)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.2 (Persistence — MinIO)
- ADR-0013 (`docs/adr/0013-rls-multi-tenancy-formalize-v4.md`) — bucket prefix isolation
- ADR-0012 (`docs/adr/0012-postgres-clickhouse-polyglot-persistence.md`)
- `docs/BACKLOG_V4.md` P1-S3 (P2-M25-001..009, P2-M26-001..006)
