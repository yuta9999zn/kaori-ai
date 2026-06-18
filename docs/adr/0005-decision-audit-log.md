# ADR-0005 — Append-only audit trail in `decision_audit_log`

> **Status:** accepted
> **Date:** 2026-04-29 (originally landed migration 001/002, hardened Sprint 0.5 PR #67)
> **Deciders:** Nguyen Truong An
> **Related:** `infrastructure/postgres/migrations/001_init.sql` (table) · `infrastructure/postgres/migrations/002_pipeline.sql` (no-update / no-delete RULEs) · `CLAUDE.md` K-6, K-15

## Context

Kaori is a B2B AI platform. Every automated decision the system makes — column mapping, cleaning rule application, analysis template choice, LLM call, chat tool dispatch — must be:

1. **Inspectable by the customer**, who answers "why did the system do that?" to their own users.
2. **Replayable for compliance** (GDPR / SOC2 trail; Phase 2 will need this for B2B sales).
3. **Tamper-evident.** A bug that silently overwrites an audit row is worse than a bug that doesn't write one.

We need one table the whole platform writes to — not per-feature audit tables that drift in shape.

## Decision

We use a single append-only table `decision_audit_log` with a generic `decision_type` field. Every component that makes an automated decision writes one row per decision. Append-only is enforced **at the DB layer** by Postgres RULEs:

```sql
CREATE RULE decision_audit_no_update AS ON UPDATE TO decision_audit_log DO INSTEAD NOTHING;
CREATE RULE decision_audit_no_delete AS ON DELETE TO decision_audit_log DO INSTEAD NOTHING;
```

Schema highlights:

- `enterprise_id NOT NULL` (FK to enterprises) — every audit row tied to a tenant.
- `decision_type` — open string (e.g., `column_map`, `cleaning_rule`, `llm_call`, `chat.tool_call`).
- `chosen_value` / `alternatives` / `confidence` / `reasoning` — narrative payload.
- `run_id` (nullable) — links to a `pipeline_runs` row when applicable, for end-to-end trace.
- `method` — `internal` / `external` / `chat.{enterprise,platform}` etc., indicating *how* the decision was reached.

Writes are **best-effort**: `services/*/shared/audit.py` swallows DB errors and logs them. The primary path (LLM response, cleaning result) must never fail because we couldn't write the audit.

## Consequences

### Positive

- **K-2 (Bronze append-only) generalises** — same RULE pattern applies; reviewing immutability = reading 5 lines of SQL.
- **One table to query for a customer trail** — `/decisions` endpoint (F-029) is a single SELECT with cursor pagination.
- **Sprint 8 K-15 chat tool audit** ships as `decision_type='chat.tool_call'` rows in the same table — no new schema, no new endpoint, no new export pipeline.

### Negative / accepted trade-offs

- **No mutable status field.** When a decision needs an "actioned" flag (e.g., F-NEW4 dashboard checkbox), we can't `UPDATE` the audit row. Sprint 7 PR D introduced `decision_actions` as a side-table specifically because of this constraint.
- **Platform-scope decisions (cross-tenant) can't write here** — `enterprise_id NOT NULL` blocks them. Sprint 8 chat platform tools log via structlog only; Phase 2 adds a `platform_audit_log` mirror.
- **Storage growth is unbounded.** Hot retention 90 d (per `docs/archive/architecture-v3/TARGET_ARCHITECTURE_1M.md`); cold archive to S3 in Phase 2.

### Neutral / follow-ups

- When B2B sales need a SOC2 attestation, we'll likely dump weekly audit snapshots to immutable S3 (object lock). The DB table is still source of truth for live queries.
- F-NEW5 conversation persistence (Phase 2) writes turn-by-turn chat history; `decision_audit_log` keeps tool dispatch records, separation by purpose.

## Alternatives considered

- **Per-feature audit tables** (one for column_map, one for LLM, one for cleaning) — Rejected. Schema drift inevitable; cross-feature queries (e.g., "all decisions for run X") become a 5-table UNION.
- **Event sourcing on Kafka, no DB table** — Rejected for Phase 1. Customers want a SQL endpoint; rebuilding state from Kafka topics for every customer query is overkill at this scale.
- **Mutable rows with `superseded_at` column** — Rejected. The whole point of audit is "can't change history". A mutable column invites a UPDATE that bypasses intent.

## References

- `infrastructure/postgres/migrations/001_init.sql` (table definition)
- `infrastructure/postgres/migrations/002_pipeline.sql` (RULES)
- `services/ai-orchestrator/shared/audit.py` + `services/data-pipeline/shared/audit.py`
- `services/ai-orchestrator/routers/decisions.py` (F-029 read API)
