-- =====================================================================
-- 078_guardrail_violations.sql
--
-- P2-S23 SH-M56a — guardrail violations storage for llm-gateway.
-- Closes BACKLOG SH-M56a-021 (partitioned monthly) + SH-M56a-024
-- (180-day retention via DROP PARTITION).
--
-- Partition strategy
-- ------------------
-- Native PostgreSQL declarative partitioning by RANGE on created_at,
-- monthly partitions. Why monthly: retention cron drops whole
-- partitions (instant; no row-level DELETE pressure on a guardrail
-- hot table that may see 100K+ violations/day at 100-customer scale).
--
-- Initial partitions created for current + next 6 months. Beyond
-- that, the SH-M56a-024 retention cron creates new partitions as
-- the calendar advances and drops partitions older than 180 days.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on the partitioned parent (auto-propagates).
-- K-13: violation_id surrogate key — caller's idempotency_key (if any)
--      stored in raw_payload->>'idempotency_key' for audit.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS guardrail_violations (
    violation_id      UUID         NOT NULL DEFAULT gen_random_uuid(),
    enterprise_id     UUID         NOT NULL,
    -- Optional — null for system-level rules (rate-limit-not-yet-bound)
    user_id           UUID,
    -- Rule identity: name plus layer (input | output) plus engine version
    rule_name         VARCHAR(80)  NOT NULL,
    layer             VARCHAR(16)  NOT NULL,        -- 'input' | 'output'
    severity          VARCHAR(16)  NOT NULL,        -- 'low' | 'medium' | 'high' | 'critical'
    on_fail_action    VARCHAR(16)  NOT NULL,        -- 'exception' | 'reask' | 'fix' | 'noop'
    -- Context
    request_id        UUID,
    model_id          VARCHAR(64),
    -- Truncated snippet of the offending text (max 500 chars for storage)
    offending_excerpt TEXT,
    -- Free-form details (PII patterns matched / scores / repaired token map …)
    rule_metadata     JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- PK must include the partition key
    PRIMARY KEY (violation_id, created_at),

    CONSTRAINT chk_gv_layer       CHECK (layer       IN ('input', 'output')),
    CONSTRAINT chk_gv_severity    CHECK (severity    IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_gv_on_fail     CHECK (on_fail_action IN ('exception', 'reask', 'fix', 'noop')),
    CONSTRAINT chk_gv_excerpt_len CHECK (offending_excerpt IS NULL OR char_length(offending_excerpt) <= 500)
) PARTITION BY RANGE (created_at);


-- Initial partitions — current month + next 6 months. Retention cron
-- (SH-M56a-024) bumps partitions forward + drops anything > 180 days.

DO $$
DECLARE
    start_month DATE;
    next_month  DATE;
    part_name   TEXT;
    i           INTEGER;
BEGIN
    start_month := date_trunc('month', NOW())::DATE;
    FOR i IN 0..6 LOOP
        next_month := (start_month + (i || ' month')::INTERVAL)::DATE;
        part_name  := 'guardrail_violations_' || to_char(next_month, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF guardrail_violations
             FOR VALUES FROM (%L) TO (%L)',
            part_name,
            next_month,
            (next_month + INTERVAL '1 month')::DATE
        );
    END LOOP;
END $$;


-- Indexes on parent → auto-propagate to all partitions.
CREATE INDEX IF NOT EXISTS idx_gv_enterprise_created
    ON guardrail_violations(enterprise_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gv_rule_layer
    ON guardrail_violations(rule_name, layer, created_at DESC);


COMMENT ON TABLE guardrail_violations IS
    'P2-S23 SH-M56a-021 — partitioned monthly. Every llm-gateway '
    'guardrail rule failure writes one row here. Retention 180d '
    '(SH-M56a-024) via DROP PARTITION — never UPDATE/DELETE rows.';
COMMENT ON COLUMN guardrail_violations.rule_metadata IS
    'JSONB free-form: per-rule details (matched_patterns, score, '
    'repair_diff, citation_count, etc). Caller decides shape — keep '
    'redaction in mind, do NOT dump full prompt/completion here.';
COMMENT ON COLUMN guardrail_violations.offending_excerpt IS
    'Up to 500 chars of the offending text. Already PII-redacted '
    'before write (defense-in-depth — the gateway itself is the '
    'first line of redaction). NULL if rule is content-agnostic '
    '(rate-limit, length).';

COMMIT;
