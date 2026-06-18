-- =====================================================================
-- 110_memory_trust_columns.sql  (106-109 taken: knowledge_documents,
--   knowledge_seed_retail_sme, platform_ai_config, wire_ai_config_knobs)
--
-- ADR-0030 — Memory trust layer. Adds the believability dimension on top
-- of the existing importance (retention) model, ported from NNL-Harness
-- harness/memory.py.
--
-- Three additive, NULLABLE columns on memory_l3 (no data move, no lock
-- pain on the lean pilot). Trust is computed in the app layer
-- (reasoning/memory/types.py compute_trust) from these + occurred_at:
--
--   trust = confidence * 0.5 ^ (age_days / half_life_for(memory_type))
--   age_days = now - COALESCE(last_verified_at, created_at)
--
-- K-1: memory_l3 already has RLS (mig 067) — no policy change needed.
-- K-21: columns on an existing UUIDv4 table → untouched id strategy.
-- =====================================================================

BEGIN;

ALTER TABLE memory_l3
    -- 0..1 self-scored at write/consolidation ("không bịa độ tin cao").
    ADD COLUMN IF NOT EXISTS confidence       NUMERIC(3,2) NOT NULL DEFAULT 0.70,
    -- Provenance of the memory: 'user' | 'consolidate' | 'rag' | 'derived' | ...
    ADD COLUMN IF NOT EXISTS trust_source     VARCHAR(32),
    -- Last time the memory was re-confirmed (verify()/reinforce); NULL = never.
    -- Resets the decay clock when set.
    ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;

COMMENT ON COLUMN memory_l3.confidence IS
    'ADR-0030 — believability 0..1, self-scored at write/consolidation. Feeds trust = confidence * 0.5^(age/half_life).';
COMMENT ON COLUMN memory_l3.trust_source IS
    'ADR-0030 — provenance: user / consolidate / rag / derived / ...';
COMMENT ON COLUMN memory_l3.last_verified_at IS
    'ADR-0030 — last re-confirmation (verify/reinforce). NULL = never verified. Resets decay clock.';

COMMIT;
