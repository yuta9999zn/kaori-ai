-- Migration 034: F-039 follow-up — risk_items.category.
--
-- Why this exists
-- ===============
-- Migration 033 shipped risk_items without a category column. The FE
-- template (file 56-risks-hub.tsx) needs a six-bucket dropdown so
-- analysts can filter the register by domain (operational vs.
-- regulatory vs. reputational, etc). Adding it as a follow-up keeps
-- the original migration immutable and the audit trail clean.
--
-- Six buckets match the template UI labels (Vận hành / Tài chính /
-- Pháp lý / Thương hiệu / Chiến lược / Kỹ thuật):
--
--     operational   — vận hành (process, supplier, delivery)
--     financial     — tài chính (cashflow, FX, credit)
--     regulatory    — pháp lý / compliance
--     reputational  — thương hiệu (PR, social, brand)
--     strategic     — chiến lược (market shift, competitor)
--     technical     — kỹ thuật (infra, security, model)
--
-- Default 'operational' so any rows from migration 033 (none in prod
-- yet, but possible in dev databases that pre-applied it) inherit a
-- catch-all bucket without violating NOT NULL. New writes must pick
-- explicitly — service-layer validation rejects unknown values before
-- the CHECK fires.
--
-- Idempotency
-- ===========
-- ``ADD COLUMN IF NOT EXISTS`` keeps this safe to re-run on databases
-- where another path (e.g. the IT Postgres docker-entrypoint-initdb.d
-- pre-load) already applied it once before Flyway claims the migration
-- in flyway_schema_history. Postgres 9.6+ supports the IF NOT EXISTS
-- form for ALTER TABLE ADD COLUMN; the inline CHECK is part of the
-- column definition so it's only added when the column is.
--
-- Reversibility
-- =============
--   ALTER TABLE risk_items DROP COLUMN category;
-- ============================================================

BEGIN;

ALTER TABLE risk_items
    ADD COLUMN IF NOT EXISTS category VARCHAR(20) NOT NULL DEFAULT 'operational'
        CHECK (category IN (
            'operational',
            'financial',
            'regulatory',
            'reputational',
            'strategic',
            'technical'
        ));

-- Filter index: list endpoint queries `WHERE enterprise_id = ? AND
-- category = ?` whenever the FE dropdown is anything other than
-- "all". Partial on deleted_at IS NULL to match the other risk_items
-- indexes from migration 033.
CREATE INDEX IF NOT EXISTS idx_risk_items_category
    ON risk_items(enterprise_id, category)
    WHERE deleted_at IS NULL;

COMMIT;
