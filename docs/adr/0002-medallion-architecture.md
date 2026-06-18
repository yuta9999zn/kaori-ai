# ADR-0002 — Medallion (Bronze / Silver / Gold) data architecture

> **Status:** accepted
> **Date:** 2026-04-29 (originally landed Sprint 4-5, PR #80)
> **Deciders:** Nguyen Truong An
> **Related:** `docs/specs/MEDALLION_CONTRACT.md` · `infrastructure/postgres/migrations/018_gold_layer.sql` · `CLAUDE.md` §5 Data Flow · K-2

## Context

Kaori ingests CSVs from non-technical users who upload data with inconsistent column names, mixed encoding, dirty rows, and 5+ languages. We need to:

1. Preserve the **exact bytes the user uploaded** for replay/audit (regulatory + debugging).
2. Run **rule-based + ML cleaning** without losing the original.
3. Compute **per-customer features** (`revenue_at_risk`, churn signals) for the dashboard tile and the North Star metric.

Classic Lakehouse pattern (Databricks) describes Bronze → Silver → Gold as three stages with distinct contracts. The alternative — a single "cleaned table" with cleanup metadata columns — was attempted in early prototypes and broke down: when a cleaning rule had a bug, we had no ground truth to re-run from.

## Decision

We adopt the **Medallion architecture** with three strict layers:

| Layer  | Engine                          | Contract                                           |
|--------|---------------------------------|----------------------------------------------------|
| Bronze | Postgres (`bronze_files`, `bronze_rows`) | **Append-only (K-2)**, raw bytes, SHA-256 dedup. Rules in migration 001/002 prevent UPDATE/DELETE. |
| Silver | Postgres (`silver_rows`)        | Cleaned + typed + PII-masked. Per-tenant + per-month partition. Idempotent re-derivation from Bronze. |
| Gold   | Postgres (`gold_features`, `gold_aggregates`) | Per-customer features + tenant rollups. Strict canonical schema; aggregator skips tenants without `customer_external_id` mapping. |

Each layer **owns one job**:
- Bronze answers "what did the user upload?"
- Silver answers "what does the data mean after cleaning?"
- Gold answers "what does the business need to act on?"

A layer is **never allowed to fix a problem from an upstream layer**. If Gold needs a column Silver doesn't expose, the fix is to add it to Silver's canonical schema, not to special-case Gold.

## Consequences

### Positive

- **Replay-from-source** is always possible. Bronze never changes; we re-run Silver derivation when a cleaning rule is fixed.
- **Audit lineage is provable.** Every `decision_audit_log` row references the layer it was made at; column-mapping decisions live at Bronze→Silver, cleaning at Silver, feature engineering at Silver→Gold.
- **K-2 (append-only) is enforceable at the DB layer**, not just by convention.

### Negative / accepted trade-offs

- **Storage cost ~3× a single-table approach.** Same row exists in Bronze + Silver + Gold. Acceptable while pilot tenants are small.
- **Strict canonical schema in Gold means tenants with poorly mapped data get skipped silently** (logged as `gold.aggregate.skip.no_customer_id`). The trade-off is intentional: better to skip a tenant than emit a wrong North Star value.

### Neutral / follow-ups

- When pilot tenant count exceeds 20, evaluate moving Silver to ClickHouse (columnar) for query speed. Current Postgres setup OK at <5M rows.
- F-060 (Phase 2) wires `gold_features.is_actioned` into the dashboard tile. Until then `decision_actions` side-table (migration 019) carries the toggle.

## Alternatives considered

- **Single "cleaned" table with cleanup metadata columns** — Tried and rejected in pre-Phase-1 prototypes. When a rule was buggy, recovery required hand-editing the table; no auditable replay path.
- **Two layers (raw + cleaned)** — Rejected. Conflates "schema-mapping decision" (Bronze→Silver) with "cleaning rule" (within Silver). They have different audit needs and different failure modes.
- **Materialized views instead of tables for Gold** — Rejected. MV refresh blocks reads, and we need per-customer Gold rows queryable in <100ms for the dashboard tile.

## References

- `docs/specs/MEDALLION_CONTRACT.md` (canonical Silver schema)
- `infrastructure/postgres/migrations/001_init.sql` (Bronze append-only rules)
- `infrastructure/postgres/migrations/018_gold_layer.sql` (Gold tables + RLS)
- Memory: `feedback_medallion_separation.md` ("Bronze/Silver/Gold each own ONE thing")
