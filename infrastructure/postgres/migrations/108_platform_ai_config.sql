-- =====================================================================
-- 108_platform_ai_config.sql — Platform AI tuning knobs (CR-0019 / FR-PLT-08)
--
-- Today the AI tunables (RAG top-k, memory promote/forget thresholds, grounding
-- tolerance, embedding model) are source CONSTANTS — changing one needs an edit
-- + redeploy. This table makes them platform-admin editable at runtime.
--
-- GLOBAL (platform-level), like llm_providers (mig 075): one row per knob, no
-- enterprise_id, no per-tenant RLS — these are platform defaults a SUPER_ADMIN
-- tunes. Validation bounds (min/max) live in the row (NOT hard-coded in the
-- endpoint) so adding a knob = a seed row, no code change to validate it.
--
-- `applied` = a runtime path already reads this knob via shared/ai_config.py.
-- Knobs with applied=false are surfaced (so the admin sees the full surface +
-- real current default) but not yet wired — wired incrementally; the UI shows
-- their status honestly.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS platform_ai_config (
    config_key   VARCHAR(64)  PRIMARY KEY,
    config_value TEXT         NOT NULL,
    value_type   VARCHAR(16)  NOT NULL,
    min_value    DOUBLE PRECISION,            -- numeric lower bound (NULL = n/a)
    max_value    DOUBLE PRECISION,            -- numeric upper bound (NULL = n/a)
    description  TEXT,
    applied      BOOLEAN      NOT NULL DEFAULT FALSE,
    updated_by   UUID,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_paic_type  CHECK (value_type IN ('int', 'float', 'string'))
);

-- Seed the knobs with their current source defaults. applied=true only where a
-- runtime path reads it via ai_config (this commit wires grounding_tolerance).
INSERT INTO platform_ai_config
    (config_key, config_value, value_type, min_value, max_value, description, applied)
VALUES
    ('grounding_tolerance',          '0.02', 'float',  0,    1,    'Dung sai khớp số khi grounding self-verify insight (CR-0018). Càng nhỏ càng nghiêm.', TRUE),
    ('rag_max_citations',            '5',    'int',    1,    50,   'Số trích dẫn tối đa trả về cho 1 truy vấn RAG.',                                    FALSE),
    ('rag_max_corpus_docs',          '50',   'int',    1,    500,  'Trần số tài liệu nạp vào corpus mỗi truy vấn pgvector.',                            FALSE),
    ('memory_promotion_threshold',   '0.7',  'float',  0,    1,    'Điểm importance ≥ ngưỡng → thăng ký ức L3 lên L4.',                                 FALSE),
    ('memory_forget_threshold',      '0.3',  'float',  0,    1,    'Ký ức L3 quá hạn + điểm < ngưỡng → xoá.',                                           FALSE),
    ('memory_forget_age_days',       '90',   'int',    1,    3650, 'Tuổi (ngày) ký ức L3 mới đủ điều kiện xét quên.',                                   FALSE),
    ('embedding_model',              'bge-m3','string', NULL, NULL, 'Model embedding (K-20 — đổi sẽ làm vector cũ lệch tới khi re-embed).',              FALSE)
ON CONFLICT (config_key) DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON platform_ai_config TO kaori_app;

COMMIT;
