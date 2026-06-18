-- 041_idempotency_records.sql
-- P1-S6 (REL-005, K-17 + ADR-0014) — workflow node idempotency framework.
--
-- Two layers of idempotency live in the system:
--   1. K-13 — Idempotency-Key HTTP header on POST mutations, Redis 24h TTL.
--      Already exists, untouched by this migration.
--   2. K-17 (P1-S6 NEW) — per-workflow-node idempotency. When a workflow
--      retries a node with side_effect_class='write_idempotent' or
--      'write_non_idempotent', the action runtime computes a deterministic
--      idempotency_key from (workflow_id + node_id + run_id + input_hash)
--      and looks it up here BEFORE running the side effect. Cache hit =
--      return prior result; miss = execute + write the result here.
--
-- Why Postgres + 7-day TTL (not Redis):
--   * Saga compensation may fire days after the original side effect.
--     Redis TTL would expire too soon. Postgres + scheduled cleanup
--     gives ops control.
--   * Long-running workflows (the 90-day testing harness in Workflow
--     System Phần 8) reference earlier nodes' results; need persistence
--     beyond a single Redis flush.
--
-- Layout:
--   * idempotency_key       — sha256 hex (deterministic per node+run+input)
--   * tenant_id             — RLS scope (K-1)
--   * workflow_id, node_id, run_id — full provenance for ops debugging
--   * side_effect_class     — one of REL-001's 5 classes (audit trail)
--   * result_json           — what the side effect returned (replay payload)
--   * created_at            — for TTL purge
--   * expires_at            — generated column (created_at + 7 days)
--
-- Cleanup: pg_cron job purges WHERE expires_at < NOW() weekly. Phase 1
-- can rely on a manual cron / one-off DELETE; Phase 1.5 wires pg_cron.

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key   TEXT            NOT NULL,
    tenant_id         UUID            NOT NULL,

    workflow_id       TEXT            NOT NULL,
    node_id           TEXT            NOT NULL,
    run_id            UUID            NOT NULL,

    side_effect_class VARCHAR(32)     NOT NULL,
    result_json       JSONB           NOT NULL,

    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    -- expires_at filled at INSERT time. Originally written as a STORED
    -- generated column `created_at + INTERVAL '7 days'` but Postgres
    -- rejects with ERROR: generation expression is not immutable
    -- (TIMESTAMPTZ + INTERVAL is STABLE, not IMMUTABLE — depends on
    -- session timezone). Cleaner to compute the +7-day default in the
    -- column DEFAULT, which is allowed.
    expires_at        TIMESTAMPTZ     NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),

    PRIMARY KEY (idempotency_key, tenant_id),
    CONSTRAINT chk_side_effect_class CHECK (
        side_effect_class IN ('pure', 'read_only', 'write_idempotent', 'write_non_idempotent', 'external')
    )
);

CREATE INDEX IF NOT EXISTS idx_idem_expires_at  ON idempotency_records(expires_at);
CREATE INDEX IF NOT EXISTS idx_idem_workflow_id ON idempotency_records(tenant_id, workflow_id);
CREATE INDEX IF NOT EXISTS idx_idem_run_id      ON idempotency_records(tenant_id, run_id);

COMMENT ON TABLE idempotency_records IS
    'P1-S6 (REL-005, K-17, ADR-0014) — per-workflow-node idempotency cache. 7-day TTL.';

ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'idempotency_records' AND policyname = 'tenant_idem_records') THEN
        CREATE POLICY tenant_idem_records ON idempotency_records
            USING (tenant_id::text = current_setting('app.enterprise_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.enterprise_id', true));
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON idempotency_records TO kaori_app;
