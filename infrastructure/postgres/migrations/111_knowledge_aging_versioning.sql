-- =====================================================================
-- 111_knowledge_aging_versioning.sql
--
-- ADR-0033 — evolve knowledge_documents (mig 106/107) from a static
-- authority-tiered store into one that MATURES and EXPLAINS ITSELF.
--
-- Additive, mostly-nullable columns (no data move, low lock cost on the
-- lean pilot). Two capabilities:
--
--   Aging   — confidence climbs on validated citation (reinforce), use_count
--             tracks repetition, last_reinforced_at resets the clock. Effective
--             weight = confidence * decay(age) with a per-tier half-life
--             (foundational ~never decays; volatile tier-3 decays on cadence) —
--             computed in the app layer (KnowledgeStore), mirrors ADR-0032.
--   History — supersede-not-overwrite: a changed doc inserts a NEW row with
--             supersedes=<old>, and the old row gets status='archived' +
--             superseded_by=<new> + the change_reason. The chain stays
--             queryable so the system answers "vì sao lại vậy".
--
-- K-1: RLS already on knowledge_documents (mig 106) — no policy change.
-- =====================================================================

BEGIN;

ALTER TABLE knowledge_documents
    -- Aging / maturation (ADR-0033, ported from ADR-0032 memory trust).
    ADD COLUMN IF NOT EXISTS confidence        NUMERIC(3,2) NOT NULL DEFAULT 0.70,
    ADD COLUMN IF NOT EXISTS use_count         INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_reinforced_at TIMESTAMPTZ,
    -- Volatile-tier freshness hint (tier 3 market data); NULL = no expiry
    -- (foundational tiers 1/2). Past valid_until the row is flagged
    -- "cần cập nhật" by the app, never auto-deleted.
    ADD COLUMN IF NOT EXISTS valid_until       TIMESTAMPTZ,
    -- Version chain for explainability ("vì sao lại vậy").
    ADD COLUMN IF NOT EXISTS supersedes        UUID
        REFERENCES knowledge_documents(document_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS superseded_by     UUID
        REFERENCES knowledge_documents(document_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS change_reason     TEXT;

-- Walk a version chain fast (newest row points back via supersedes).
CREATE INDEX IF NOT EXISTS idx_knowledge_supersedes
    ON knowledge_documents (supersedes) WHERE supersedes IS NOT NULL;

COMMENT ON COLUMN knowledge_documents.confidence IS
    'ADR-0033 — maturity 0..1, climbs on validated citation (reinforce); per-tier ceiling. Effective weight = confidence * age-decay (app layer).';
COMMENT ON COLUMN knowledge_documents.supersedes IS
    'ADR-0033 — this (active) row replaced that (archived) row. Walk backward for version history.';
COMMENT ON COLUMN knowledge_documents.superseded_by IS
    'ADR-0033 — this (archived) row was replaced by that (active) row.';
COMMENT ON COLUMN knowledge_documents.change_reason IS
    'ADR-0033 — why this version replaced the previous one (answers "vì sao lại vậy").';

COMMIT;
