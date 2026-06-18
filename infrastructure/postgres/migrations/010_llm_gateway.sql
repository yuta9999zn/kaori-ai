-- Migration 010: LLM Gateway tables (Phase 1 P-1 scaffold).
--
-- Two small lookup tables backing services/llm-gateway/:
--   llm_models         — registry of available models + cost / capability
--   llm_task_routing   — task_type → default_model_id (+ optional fallback)
--
-- Both are global (no enterprise_id, no RLS) — they're catalog data
-- shared by every tenant. Per-tenant overrides (e.g. enterprise X
-- always uses internal models) come in a follow-up table when token
-- budget enforcement lands.
--
-- Reversibility:
--   DROP TABLE llm_task_routing;
--   DROP TABLE llm_models;

CREATE TABLE IF NOT EXISTS llm_models (
    model_id              VARCHAR(100) PRIMARY KEY,
    provider              VARCHAR(30)  NOT NULL,
    display_name          VARCHAR(200) NOT NULL,
    max_tokens            INTEGER      NOT NULL DEFAULT 2000,
    cost_per_1k_prompt    NUMERIC(10,6),
    cost_per_1k_completion NUMERIC(10,6),
    status                VARCHAR(20)  NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','deprecated','disabled')),
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_llm_models_provider
        CHECK (provider IN ('ollama','anthropic','openai','google','internal'))
);

CREATE TABLE IF NOT EXISTS llm_task_routing (
    task_type           VARCHAR(100) PRIMARY KEY,
    default_model_id    VARCHAR(100) NOT NULL REFERENCES llm_models(model_id),
    fallback_model_id   VARCHAR(100)          REFERENCES llm_models(model_id),
    max_tokens          INTEGER      NOT NULL DEFAULT 2000,
    notes               TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE ON llm_models       TO kaori_app;
GRANT SELECT, INSERT, UPDATE ON llm_task_routing TO kaori_app;

-- Seed a usable default so the gateway has something to route to on
-- a fresh init. ON CONFLICT DO NOTHING keeps the migration re-runnable
-- if anyone customizes these in dev.
INSERT INTO llm_models (model_id, provider, display_name, max_tokens, cost_per_1k_prompt, cost_per_1k_completion)
VALUES
    ('qwen2.5:14b',              'ollama',    'Qwen 2.5 14B (local)',         8192, 0,        0       ),
    ('claude-sonnet-4-6',        'anthropic', 'Claude Sonnet 4.6',           200000, 0.003,   0.015   ),
    ('claude-haiku-4-5-20251001','anthropic', 'Claude Haiku 4.5',            200000, 0.00025, 0.00125 ),
    ('gpt-4o',                   'openai',    'GPT-4o',                      128000, 0.0025,  0.01    )
ON CONFLICT (model_id) DO NOTHING;

INSERT INTO llm_task_routing (task_type, default_model_id, fallback_model_id, max_tokens, notes)
VALUES
    ('schema_mapping',     'qwen2.5:14b', 'claude-sonnet-4-6',        2000, 'Bronze→Canonical column inference'),
    ('cleaning_rule',      'qwen2.5:14b', NULL,                       1000, 'Silver-layer rule selection'),
    ('analysis_summary',   'qwen2.5:14b', 'claude-sonnet-4-6',        4000, 'Gold-layer analysis prose'),
    ('strategy_framework', 'qwen2.5:14b', 'claude-haiku-4-5-20251001',2000, 'K-10 deterministic framework pick')
ON CONFLICT (task_type) DO NOTHING;
