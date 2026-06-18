-- =====================================================================
-- 075_llm_ops.sql
--
-- P2-S22 D1 — LLM operations tables for MAX-tier features:
--   llm_providers           — global catalog of supported providers
--   tenant_llm_api_keys     — per-tenant encrypted API keys (AES-GCM)
--   llm_token_usage_daily   — per-tenant per-day token + cost rollup
--   llm_upgrade_tests       — 90-day shadow-mode upgrade test runs
--
-- Design choices
-- --------------
-- - llm_providers is GLOBAL (no enterprise_id) — same provider list
--   across tenants. Tenant decides which providers to enable via the
--   `enabled` flag on tenant_llm_api_keys.
-- - tenant_llm_api_keys.api_key_enc uses shared/crypto.py AES-256-GCM
--   format (base64(version(1B) || IV(12B) || GCM_ct+tag)). The key
--   that encrypts the API key is the TENANT field-key from
--   tenant_field_keys (mig 074) — dogfood our own encryption.
-- - llm_token_usage_daily is upsert-only by (enterprise_id, provider_id,
--   period_day) — recomputable from kaori.billing.events stream.
-- - llm_upgrade_tests captures (current_model, candidate_model) pairs
--   running shadow side-by-side for 90 days per P1-LLM-006.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on the 3 per-tenant tables.
-- K-2 append-only: llm_token_usage_daily uses upsert (delete only via
--     90-day forget cron); llm_upgrade_tests append-only.
-- K-5: api_key_enc encrypted at rest with TENANT key (not platform
--     master) — defense-in-depth.
-- K-20: llm_upgrade_tests records pinned_version on both sides of the
--     A/B; promotion only fires on 90-day stat-significant win.
-- =====================================================================

BEGIN;

-- ─── Provider catalog (global) ───────────────────────────────────────


CREATE TABLE IF NOT EXISTS llm_providers (
    provider_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key       VARCHAR(32)  UNIQUE NOT NULL,
    display_name       VARCHAR(100) NOT NULL,
    base_url           TEXT         NOT NULL,
    requires_api_key   BOOLEAN      NOT NULL DEFAULT TRUE,
    supports_streaming BOOLEAN      NOT NULL DEFAULT FALSE,
    is_external        BOOLEAN      NOT NULL DEFAULT TRUE,
    default_models     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    cost_per_1k_input  NUMERIC(10,6) NOT NULL DEFAULT 0,
    cost_per_1k_output NUMERIC(10,6) NOT NULL DEFAULT 0,
    is_active          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_llm_provider_key CHECK (provider_key IN (
        'qwen_local', 'anthropic', 'openai', 'google', 'cohere', 'mistral'
    ))
);

CREATE INDEX IF NOT EXISTS idx_llm_providers_active
    ON llm_providers(provider_key) WHERE is_active = TRUE;

-- Seed: 3 providers Kaori supports today (Qwen local + Anthropic + OpenAI per ADR-0015)
INSERT INTO llm_providers (provider_key, display_name, base_url,
                            requires_api_key, supports_streaming, is_external,
                            default_models, cost_per_1k_input, cost_per_1k_output)
VALUES
('qwen_local', 'Qwen 2.5 14B (local Ollama)', 'http://ollama:11434',
 FALSE, TRUE, FALSE,
 '["qwen2.5:14b", "qwen2.5:7b", "bge-m3"]'::jsonb,
 0.0, 0.0),
('anthropic', 'Anthropic Claude', 'https://api.anthropic.com',
 TRUE, TRUE, TRUE,
 '["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"]'::jsonb,
 0.003, 0.015),
('openai', 'OpenAI GPT', 'https://api.openai.com',
 TRUE, TRUE, TRUE,
 '["gpt-5", "gpt-5-mini", "gpt-4o-mini"]'::jsonb,
 0.0025, 0.010)
ON CONFLICT (provider_key) DO NOTHING;


-- ─── Per-tenant API keys (encrypted) ─────────────────────────────────


CREATE TABLE IF NOT EXISTS tenant_llm_api_keys (
    key_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    provider_id   UUID         NOT NULL REFERENCES llm_providers(provider_id),
    api_key_enc   TEXT         NOT NULL,
    label         VARCHAR(100),
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_used_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    rotated_at    TIMESTAMPTZ,

    CONSTRAINT uq_tenant_provider UNIQUE (enterprise_id, provider_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_llm_keys_enabled
    ON tenant_llm_api_keys(enterprise_id) WHERE enabled = TRUE;


-- ─── Token usage rollup (per-tenant, per-provider, per-day) ──────────


CREATE TABLE IF NOT EXISTS llm_token_usage_daily (
    enterprise_id    UUID          NOT NULL REFERENCES enterprises(enterprise_id),
    provider_id      UUID          NOT NULL REFERENCES llm_providers(provider_id),
    period_day       DATE          NOT NULL,
    input_tokens     BIGINT        NOT NULL DEFAULT 0,
    output_tokens    BIGINT        NOT NULL DEFAULT 0,
    cost_usd         NUMERIC(14,4) NOT NULL DEFAULT 0,
    cost_vnd         NUMERIC(14,4) NOT NULL DEFAULT 0,
    call_count       INTEGER       NOT NULL DEFAULT 0,
    cache_hit_count  INTEGER       NOT NULL DEFAULT 0,
    error_count      INTEGER       NOT NULL DEFAULT 0,
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    PRIMARY KEY (enterprise_id, provider_id, period_day),
    CONSTRAINT chk_llm_tokens_nonneg CHECK (
        input_tokens >= 0 AND output_tokens >= 0 AND cost_usd >= 0
        AND cost_vnd >= 0 AND call_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_llm_token_usage_period
    ON llm_token_usage_daily(enterprise_id, period_day DESC);


-- ─── 90-day shadow upgrade tests (P1-LLM-006) ────────────────────────


CREATE TABLE IF NOT EXISTS llm_upgrade_tests (
    test_id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID          NOT NULL REFERENCES enterprises(enterprise_id),
    provider_id          UUID          NOT NULL REFERENCES llm_providers(provider_id),
    current_model        VARCHAR(100)  NOT NULL,
    current_version      VARCHAR(64)   NOT NULL,
    candidate_model      VARCHAR(100)  NOT NULL,
    candidate_version    VARCHAR(64)   NOT NULL,
    started_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    ends_at              TIMESTAMPTZ   NOT NULL,
    status               VARCHAR(16)   NOT NULL DEFAULT 'RUNNING',
    shadow_call_count    INTEGER       NOT NULL DEFAULT 0,
    agreement_rate       NUMERIC(5,4),
    avg_cost_delta_usd   NUMERIC(14,4),
    promoted_at          TIMESTAMPTZ,
    promoted_by          UUID,
    notes                TEXT,

    CONSTRAINT chk_upgrade_test_status CHECK (status IN (
        'RUNNING', 'PROMOTED', 'REJECTED', 'CANCELLED'
    )),
    CONSTRAINT chk_upgrade_test_period CHECK (ends_at > started_at),
    CONSTRAINT chk_agreement_range CHECK (
        agreement_rate IS NULL OR (agreement_rate >= 0 AND agreement_rate <= 1)
    )
);

CREATE INDEX IF NOT EXISTS idx_llm_upgrade_tests_running
    ON llm_upgrade_tests(enterprise_id)
    WHERE status = 'RUNNING';


COMMENT ON TABLE llm_providers IS
    'P2-S22 P1-LLM-001 — global catalog. Phase 1.5 + 2 ship 3: qwen_local '
    '(default per K-4), anthropic, openai.';
COMMENT ON TABLE tenant_llm_api_keys IS
    'P2-S22 P1-LLM-002 — api_key_enc encrypted with TENANT field-key '
    '(shared/crypto.py). Dogfoods P2-S25 encryption infrastructure.';
COMMENT ON TABLE llm_token_usage_daily IS
    'P2-S22 P1-LLM-003 — per-tenant per-provider per-day token + cost '
    'rollup. Upsert pattern; rebuildable from kaori.billing.events stream.';
COMMENT ON TABLE llm_upgrade_tests IS
    'P2-S22 P1-LLM-006 — 90-day shadow-mode A/B test pairing '
    '(current_model, candidate_model). K-20 pinning preserved on both sides.';

COMMIT;
