# ADR-0003 — Postgres RLS for tenant isolation

> **Status:** accepted
> **Date:** 2026-04-29 (originally landed Sprint 0.5, PR #66)
> **Deciders:** Nguyen Truong An
> **Related:** `infrastructure/postgres/migrations/005_rls.sql` · `CLAUDE.md` K-1, K-12 · `services/ai-orchestrator/shared/db.py:acquire_for_tenant`

## Context

Kaori is multi-tenant. Every SELECT must filter by the calling tenant — that's invariant K-1, and a violation means cross-tenant data leak. There are three places we can enforce that filter:

1. **Application code** — every `WHERE enterprise_id = $1` written by hand. One missed `WHERE` = leak.
2. **Filtered views** — one view per (table, tenant) or use `current_setting()`-aware views. Doubles the schema surface.
3. **Postgres Row-Level Security (RLS)** — policies declared on the table, applied automatically to every query the role runs.

The architecture review (P0 #4) called application-level filtering "one bug away from a CVE." Filtered views worked in prototype but generated absurd join graphs when adding feature columns.

## Decision

We enable **Postgres RLS** on every tenant-scoped table. Each service connects via a tenant-scoped helper:

```python
# services/ai-orchestrator/shared/db.py
async with acquire_for_tenant(enterprise_id) as conn:
    await conn.execute("SELECT set_config('app.enterprise_id', $1, true)", eid_str)
    # All SELECTs inside this transaction are filtered by RLS
```

RLS policies (declared in `005_rls.sql`, `018_gold_layer.sql`) read `current_setting('app.enterprise_id')` and apply `USING (enterprise_id = ...::UUID)`.

## Consequences

### Positive

- **Defense in depth.** Even if a developer forgets `WHERE enterprise_id = $1`, RLS still filters. Many of the chat tools (Sprint 8) deliberately omit the explicit clause and rely on RLS.
- **JWT-only tenant scoping enforceable.** `acquire_for_tenant` takes `enterprise_id` from the gateway-trusted X-Enterprise-ID header (K-7, K-12). No way to override from the LLM args (K-16).
- **One audit point** — RLS policies live in migrations, tracked in git; reviewing tenant boundary is reading 1 SQL file.

### Negative / accepted trade-offs

- **Pool roles must be non-superuser**, otherwise RLS is bypassed. Auth-service runs Flyway as user `kaori` (DDL) but app traffic uses `kaori_app` (DML, BYPASSRLS dropped). Sprint 0.5 PR #66 wired this; G4b (drop BYPASSRLS) is in main today.
- **Performance overhead ~5%** on simple SELECTs (Postgres has to add the predicate). Acceptable; we pay it for safety.
- **Cross-tenant queries (platform admins) require a different connection path** that bypasses `acquire_for_tenant`. Used today by F-008 + F-011 platform endpoints; protected by JWT role gate at the gateway and audit row per call.

### Neutral / follow-ups

- When ClickHouse comes in (Phase 2 Silver layer), we lose Postgres RLS. Plan: replicate the predicate at the SQL builder level + audit query plans.
- Background workers (cron, Kafka consumers) need a tenant context too. Today they iterate per-tenant + call `acquire_for_tenant` — pattern documented in the cron jobs.

## Alternatives considered

- **App-level filtering only** — Rejected. One missing `WHERE` clause = silent cross-tenant leak. The cost of RLS overhead is much smaller than the cost of one such incident.
- **Filtered views** — Rejected. Schema surface doubles, ALTER TABLE becomes a 3-step dance, and JOIN plans get hairy when 10 views participate.
- **Schema-per-tenant** — Rejected. Doesn't scale past ~50 tenants in Postgres (catalog bloat); migration becomes 50× the work.

## References

- `infrastructure/postgres/migrations/005_rls.sql` (RLS policies)
- `infrastructure/postgres/migrations/008_kaori_app_grants.sql` (non-superuser role)
- `services/ai-orchestrator/shared/db.py` + `services/data-pipeline/shared/db.py` (`acquire_for_tenant`)
- Architecture review P0 #4 (closed by PR #66)
