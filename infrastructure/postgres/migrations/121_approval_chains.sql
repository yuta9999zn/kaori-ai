-- =====================================================================
-- 121_approval_chains.sql — Tier-3 Phase 2 (ADR-0037): multi-level approval chains
--
-- A reusable chain = an ordered list of levels (Level 1 Trưởng nhóm → Level 2
-- Trưởng phòng → Level 3 Giám đốc). Each level has a mode (one / all / majority)
-- and an SLA + escalation behavior. A workflow approval_gate node references a
-- chain via config.approval_chain_id; the run walks the levels in order.
-- Dynamic value-based routing (>100M → +CFO) stays in policy_rules (mig 099).
--
-- Additive: new tables, RLS K-1 + ABAC dept per mig 053.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS approval_chains (
    chain_id      UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),
    enterprise_id UUID         NOT NULL,
    department_id UUID         NOT NULL,
    name          VARCHAR(160) NOT NULL,
    name_vi       VARCHAR(160),
    description   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_approval_chain UNIQUE (enterprise_id, department_id, name)
);

CREATE TABLE IF NOT EXISTS approval_levels (
    level_id         UUID        PRIMARY KEY DEFAULT gen_uuid_v7(),
    chain_id         UUID        NOT NULL REFERENCES approval_chains(chain_id) ON DELETE CASCADE,
    enterprise_id    UUID        NOT NULL,
    level_no         INTEGER     NOT NULL,                 -- 1, 2, 3 …
    approver_roles   TEXT[]      NOT NULL,                 -- roles that may decide this level
    mode             VARCHAR(16) NOT NULL DEFAULT 'one',   -- one | all | majority
    required_count   INTEGER,                              -- explicit N (overrides mode count)
    sla_minutes      INTEGER     NOT NULL DEFAULT 1440,    -- 24h
    on_timeout       VARCHAR(16) NOT NULL DEFAULT 'escalate',  -- escalate | skip | alert
    escalate_to_role VARCHAR(40),                          -- role to escalate to (NULL = next level)
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_level_mode    CHECK (mode IN ('one', 'all', 'majority')),
    CONSTRAINT chk_level_timeout CHECK (on_timeout IN ('escalate', 'skip', 'alert')),
    CONSTRAINT uq_approval_level UNIQUE (chain_id, level_no)
);

CREATE INDEX IF NOT EXISTS idx_approval_chains_dept ON approval_chains(enterprise_id, department_id);
CREATE INDEX IF NOT EXISTS idx_approval_levels_chain ON approval_levels(chain_id, level_no);

ALTER TABLE approval_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_levels ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_approval_chains ON approval_chains;
CREATE POLICY isolation_approval_chains ON approval_chains
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));
DROP POLICY IF EXISTS abac_dept_scope_approval_chains ON approval_chains;
CREATE POLICY abac_dept_scope_approval_chains ON approval_chains
    USING (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
        AND (
            current_setting('app.current_department_id', true) = ''
            OR current_setting('app.current_department_id', true) IS NULL
            OR department_id::text = current_setting('app.current_department_id', true)
        )
    );

DROP POLICY IF EXISTS isolation_approval_levels ON approval_levels;
CREATE POLICY isolation_approval_levels ON approval_levels
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON approval_chains TO kaori_app';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON approval_levels TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE approval_chains IS 'ADR-0037 Phase 2 — reusable multi-level approval chain (ordered levels).';

COMMIT;
