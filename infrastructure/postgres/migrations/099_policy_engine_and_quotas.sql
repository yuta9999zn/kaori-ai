-- =====================================================================
-- 099_policy_engine_and_quotas.sql
--
-- P3 Policy engine + P2 Tenant quotas, batched (both need governance
-- read path with shared cache pattern).
--
-- Tables:
--   policy_rules           declarative governance rules (P3)
--   tenant_quotas          per-tenant resource limits (P2)
--   tenant_quota_usage     rolling counters for enforcement (P2)
-- =====================================================================

BEGIN;

-- ─── policy_rules ────────────────────────────────────────────────────
-- Declarative rule registry. Evaluator walks rules in priority order +
-- applies the first match. Scopes:
--   global    — applies to all tenants
--   tenant    — applies to specific enterprise_id (rule.metadata.enterprise_id)
--   role      — applies when actor.role matches rule.metadata.required_role
--
-- condition_json is a small DSL: {field, op, value} or compound
-- {and/or: [...]} — same shape as workflow if_else condition.

CREATE TABLE IF NOT EXISTS policy_rules (
    rule_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_key          VARCHAR(128)    UNIQUE NOT NULL,
    description       TEXT            NOT NULL DEFAULT '',
    scope             VARCHAR(32)     NOT NULL
                        CHECK (scope IN ('global','tenant','role')),
    priority          INT             NOT NULL DEFAULT 100,
    condition_json    JSONB           NOT NULL,
    action            VARCHAR(32)     NOT NULL
                        CHECK (action IN ('allow','deny','require_approval',
                                            'rate_limit','audit')),
    action_params     JSONB           NOT NULL DEFAULT '{}'::jsonb,
    metadata          JSONB           NOT NULL DEFAULT '{}'::jsonb,
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_policy_rules_active
    ON policy_rules(scope, priority, enabled)
    WHERE enabled = TRUE;

-- Seed: 3 K-rules converted into policy rows (replaces hardcoded K-checks)
INSERT INTO policy_rules
    (rule_key, description, scope, priority, condition_json, action, action_params)
VALUES
    ('k4_consent_external_required',
     'K-4: external LLM call requires tenant consent_external=true',
     'global', 10,
     '{"field": "consent_external", "op": "==", "value": false}'::jsonb,
     'deny',
     '{"reason": "K-4: tenant has not enabled consent_external"}'::jsonb),
    ('finance_invoice_cfo_threshold',
     'Invoices > 100M VND require CFO approval (auto + manager + director not enough)',
     'global', 50,
     '{"and": [
        {"field": "department_type", "op": "==", "value": "finance"},
        {"field": "node_type_key", "op": "==", "value": "approval_gate"},
        {"field": "amount_vnd", "op": ">", "value": 100000000}
      ]}'::jsonb,
     'require_approval',
     '{"required_role": "CFO", "sla_minutes": 1440}'::jsonb),
    ('mfa_required_super_admin',
     'SUPER_ADMIN role requires MFA enabled per K-rules',
     'role', 5,
     '{"and": [
        {"field": "role", "op": "==", "value": "SUPER_ADMIN"},
        {"field": "mfa_enabled", "op": "==", "value": false}
      ]}'::jsonb,
     'deny',
     '{"reason": "SUPER_ADMIN must have MFA enabled — enroll first"}'::jsonb)
ON CONFLICT (rule_key) DO NOTHING;


-- ─── tenant_quotas ───────────────────────────────────────────────────
-- Per-tenant resource limits beyond billing quotas (mig 001
-- enterprise_monthly_billing covers customer count; this table covers
-- AI tokens / workflow concurrency / API rate / storage).

CREATE TABLE IF NOT EXISTS tenant_quotas (
    quota_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    quota_type        VARCHAR(48)     NOT NULL,
    period            VARCHAR(16)     NOT NULL
                        CHECK (period IN ('per_minute','per_hour','per_day','per_month','rolling')),
    max_value         BIGINT          NOT NULL,
    description       TEXT            NOT NULL DEFAULT '',
    enabled           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, quota_type, period)
);

CREATE INDEX IF NOT EXISTS idx_tenant_quotas_lookup
    ON tenant_quotas(enterprise_id, quota_type)
    WHERE enabled = TRUE;


-- ─── tenant_quota_usage ──────────────────────────────────────────────
-- Rolling counter — incremented on each quota'd operation, reset by
-- a background job at period boundaries. UNIQUE (tenant, quota_type,
-- window_start) so concurrent increments serialize via UPSERT.

CREATE TABLE IF NOT EXISTS tenant_quota_usage (
    usage_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    quota_type        VARCHAR(48)     NOT NULL,
    window_start      TIMESTAMPTZ     NOT NULL,
    window_end        TIMESTAMPTZ     NOT NULL,
    current_value     BIGINT          NOT NULL DEFAULT 0,
    last_inc_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, quota_type, window_start)
);

-- Active windows index — partial WHERE window_end > NOW() rejected by PG
-- ERROR 42P17 (NOW() is STABLE, not IMMUTABLE). Full B-tree on
-- (enterprise_id, quota_type, window_end DESC) covers active-window
-- scans equally well; query planner uses window_end ordering directly.
CREATE INDEX IF NOT EXISTS idx_quota_usage_active
    ON tenant_quota_usage(enterprise_id, quota_type, window_end DESC);

-- Seed default quotas for new tenants. Per-tenant overrides via UPDATE.
INSERT INTO tenant_quotas (enterprise_id, quota_type, period, max_value, description)
SELECT
    e.enterprise_id, q.quota_type, q.period, q.max_value, q.description
FROM enterprises e
CROSS JOIN (VALUES
    ('llm_tokens_external', 'per_day',  1000000, 'External LLM token spend cap per day'),
    ('llm_tokens_local',    'per_day',  10000000, 'Local Qwen token spend cap (loose — local is free)'),
    ('workflow_concurrent', 'rolling',  20,      'Concurrent workflow_runs in running/awaiting_approval'),
    ('api_calls',           'per_minute', 1000,  'Generic API rate limit per tenant'),
    ('export_files',        'per_day',  100,     'Export file render requests per day')
) AS q(quota_type, period, max_value, description)
WHERE NOT EXISTS (
    SELECT 1 FROM tenant_quotas tq
    WHERE tq.enterprise_id = e.enterprise_id AND tq.quota_type = q.quota_type AND tq.period = q.period
);


-- RLS
ALTER TABLE policy_rules        ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_quotas       ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_quota_usage  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_rules_global       ON policy_rules;
DROP POLICY IF EXISTS tenant_quotas_isolation   ON tenant_quotas;
DROP POLICY IF EXISTS tenant_quota_usage_isolation ON tenant_quota_usage;

-- policy_rules: global scope visible to all tenants; tenant scope filtered
-- by metadata.enterprise_id (handled at app layer for now, RLS lets all
-- through since rules are platform config not tenant data).
CREATE POLICY policy_rules_global ON policy_rules USING (TRUE);

CREATE POLICY tenant_quotas_isolation ON tenant_quotas
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));
CREATE POLICY tenant_quota_usage_isolation ON tenant_quota_usage
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
