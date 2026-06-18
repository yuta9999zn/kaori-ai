# `postgres_cdc/` — Postgres CDC connector (PM-EVT-001)

> **Status:** skeleton (P1-S3). Full impl P1-S7.

Reads logical-replication slots to capture INSERT/UPDATE/DELETE events
from a tenant's operational Postgres. Process Mining v1 uses these
events to reconstruct workflow sequences without instrumenting the
tenant's app code.

## Why CDC vs polling SELECT

- **Real-time:** WAL stream gives sub-second freshness; polling has TTL.
- **No app changes:** customer doesn't add audit triggers / hooks.
- **Captures DELETEs** which polling misses entirely.

## Phase 1 v4 P1-S3 scope

Skeleton class + interface only. Extract logic raises NotImplementedError.

## Phase 1 v4 P1-S7 scope (PM-EVT-001 + PM-PII-010..012)

- psycopg `LogicalReplicationConnection` + wal2json output plugin
- Per-table publication + slot management
- PII redaction (Vietnamese-aware) before publish
- Resume-from-LSN bookkeeping in Postgres `cdc_offsets` table
- DLQ on parse failure

## References

- `services/data-pipeline/ingestion/base.py` — Connector ABC
- `docs/strategic/WORKFLOW_SYSTEM.md` PART IV Phần 11 (Event Log Sources)
- `docs/BACKLOG_V4.md` — PM-EVT-001 (P1-S7)
