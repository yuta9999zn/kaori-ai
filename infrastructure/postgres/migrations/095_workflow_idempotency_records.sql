-- =====================================================================
-- 095_workflow_idempotency_records.sql
--
-- P0.3 of operational-correctness hardening (per anh's 2026-05-19 review).
-- Persistent idempotency ledger replaces the in-process Dict cache that
-- call_api used in wave 3. After a worker crash + restart, retries no
-- longer double-fire external side effects.
--
-- Schema
-- ------
-- One row per (enterprise_id, idempotency_key). Key is derived by the
-- caller per K-13 invariant: sha256(tenant + run + node + attempt) or
-- the caller-supplied Idempotency-Key header.
--
-- response_payload stores the cached output_data so retries return the
-- same result without re-invoking the side effect.
--
-- expires_at sweeps stale rows — call_api caches for 24h, send_email
-- for 30d (long enough that DLQ replays still hit), etc. Caller decides
-- the TTL per-class.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_idempotency_records (
    record_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    idempotency_key  VARCHAR(200)    NOT NULL,
    run_id           UUID,
    node_id          UUID,
    side_effect_class VARCHAR(32)    NOT NULL,
    response_payload JSONB           NOT NULL DEFAULT '{}'::jsonb,
    response_status  VARCHAR(32)     NOT NULL DEFAULT 'completed',
    error_message    TEXT,
    attempt_count    INT             NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_seen_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ     NOT NULL,
    UNIQUE (enterprise_id, idempotency_key)
);

-- Fast lookup by key (the hot path on every external call retry)
CREATE INDEX IF NOT EXISTS idx_workflow_idempotency_lookup
    ON workflow_idempotency_records(enterprise_id, idempotency_key);

-- Sweep stale rows (background poller). Full B-tree on expires_at —
-- partial WHERE expires_at < NOW() rejected by PG ERROR 42P17 (NOW() is
-- STABLE, not IMMUTABLE → not allowed in index predicate). Full index
-- covers the same scan: poller reads ascending and stops at NOW().
CREATE INDEX IF NOT EXISTS idx_workflow_idempotency_expired
    ON workflow_idempotency_records(expires_at);

-- Per-run drilldown (admin UI: which side effects fired in this run?)
CREATE INDEX IF NOT EXISTS idx_workflow_idempotency_run
    ON workflow_idempotency_records(run_id, created_at DESC)
    WHERE run_id IS NOT NULL;

-- RLS
ALTER TABLE workflow_idempotency_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workflow_idempotency_isolation ON workflow_idempotency_records;
CREATE POLICY workflow_idempotency_isolation ON workflow_idempotency_records
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
