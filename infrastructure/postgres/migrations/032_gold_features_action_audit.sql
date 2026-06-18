-- Migration 032: F-060 — gold_features action audit column.
--
-- Why this exists
-- ===============
-- Migration 018 (F-032 Gold Layer, Phase 1) pre-baked ``is_actioned`` +
-- ``actioned_at`` on ``gold_features`` so F-060 wouldn't need to ALTER
-- the table. The CLAUDE.md §14 North Star formula
--
--   SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)
--
-- now lands in canonical form: tile reads ``gold_features.is_actioned``
-- directly, replacing the side-table workflow Sprint 7 PR D introduced.
-- The remaining gap was *audit* — who flipped the flag — so this
-- migration adds ``actioned_by_user``. Sprint 7 PR D's ``decision_actions``
-- side table stays in place for the per-decision toggle (different
-- product surface), but the dashboard tile + ROI rollup now key off the
-- canonical column.
--
-- Why no ``churn_risk_label`` column
-- ====================================
-- The aggregator (services/data-pipeline/.../gold/aggregator.py) only
-- writes ``revenue_at_risk > 0`` for customers the model flags as
-- HIGH risk. Idle customers stay at 0. So the partial index
-- ``idx_gold_features_at_risk WHERE revenue_at_risk > 0`` is the v0
-- proxy for "churn_risk_label='HIGH'". Adding a label column would
-- duplicate the signal until F-051 explicit churn classifier ships;
-- defer to that migration.
--
-- Reversibility
-- =============
--   ALTER TABLE gold_features DROP COLUMN actioned_by_user;
-- Service rollback: removing the action endpoint reverts to read-only
-- gold_features (Phase 1 behaviour); existing decision_actions side
-- table stays functional independently.
-- ============================================================

BEGIN;

-- IF NOT EXISTS keeps the migration idempotent (re-applying a
-- migrated DB is a no-op). Sprint 7 PR D's decision_actions added
-- ``actioned_by`` not ``actioned_by_user`` — we don't reuse the name
-- because that one is an admin user_id while this is the enterprise
-- user who owns the at-risk customer relationship.
ALTER TABLE gold_features
    ADD COLUMN IF NOT EXISTS actioned_by_user UUID;

-- Action history is append-only at the row level (we don't keep a
-- separate audit table — the canonical column stores "currently
-- effective" actor + timestamp, and kaori.feedback.actions Kafka
-- topic has the full event stream). For "who actioned the most
-- customers in the last week" support queries:
CREATE INDEX IF NOT EXISTS idx_gold_features_actioned
    ON gold_features(enterprise_id, actioned_at DESC)
    WHERE is_actioned = TRUE;

COMMIT;
