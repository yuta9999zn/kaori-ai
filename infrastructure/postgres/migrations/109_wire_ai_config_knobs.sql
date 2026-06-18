-- =====================================================================
-- 109_wire_ai_config_knobs.sql — flip applied=true for wired knobs (CR-0019)
--
-- These platform_ai_config knobs now have a runtime read path (this commit):
--   rag_max_corpus_docs        → reasoning/rag/engines/pgvector_real.py _load_corpus
--   memory_promotion_threshold → reasoning/memory/service.py promote()
--   memory_forget_threshold    → reasoning/memory/service.py forget()
--   memory_forget_age_days     → reasoning/memory/service.py forget()
--
-- Still applied=false (intentionally): rag_max_citations (a per-request body
-- param, not a global default) and embedding_model (K-20 — changing the model
-- must go via env + re-embed, not a silent runtime flip).
-- =====================================================================

BEGIN;

UPDATE platform_ai_config
   SET applied = TRUE, updated_at = NOW()
 WHERE config_key IN (
    'rag_max_corpus_docs',
    'memory_promotion_threshold',
    'memory_forget_threshold',
    'memory_forget_age_days'
 );

COMMIT;
