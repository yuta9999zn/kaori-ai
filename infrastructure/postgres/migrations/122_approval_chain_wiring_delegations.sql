-- =====================================================================
-- 122_approval_chain_wiring_delegations.sql — Tier-3 Phase 2 (ADR-0037)
--
-- Wire workflow_approvals to a chain + level, and add delegation (an approver
-- who is OOO reassigns a pending approval to a colleague). Additive nullable
-- columns + one new table.
-- =====================================================================

BEGIN;

ALTER TABLE workflow_approvals
    ADD COLUMN IF NOT EXISTS chain_id            UUID REFERENCES approval_chains(chain_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS level_no            INTEGER,                 -- which chain level this row is
    ADD COLUMN IF NOT EXISTS escalated_from      UUID REFERENCES workflow_approvals(approval_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS delegated_to_user_id UUID;                   -- effective approver after delegation

-- Widen the status CHECK to add 'escalated' (a level rolled up on SLA timeout).
DO $$
BEGIN
    ALTER TABLE workflow_approvals DROP CONSTRAINT IF EXISTS workflow_approvals_status_check;
    ALTER TABLE workflow_approvals
        ADD CONSTRAINT workflow_approvals_status_check
        CHECK (status IN ('pending','approved','rejected','expired','cancelled','escalated'));
END $$;

CREATE INDEX IF NOT EXISTS idx_workflow_approvals_chain ON workflow_approvals(chain_id, level_no);
-- Escalation sweep finds pending rows past their SLA.
CREATE INDEX IF NOT EXISTS idx_workflow_approvals_sla
    ON workflow_approvals(enterprise_id, status, created_at)
    WHERE status = 'pending';

-- ─── delegations ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approval_delegations (
    delegation_id UUID        PRIMARY KEY DEFAULT gen_uuid_v7(),
    enterprise_id UUID        NOT NULL,
    from_user_id  UUID        NOT NULL,                  -- delegator (OOO)
    to_user_id    UUID        NOT NULL,                  -- delegate (covers)
    reason        TEXT,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ,                           -- NULL = until revoked
    CONSTRAINT chk_deleg_distinct CHECK (from_user_id <> to_user_id)
);
CREATE INDEX IF NOT EXISTS idx_approval_delegations_active
    ON approval_delegations(enterprise_id, from_user_id) WHERE is_active;

ALTER TABLE approval_delegations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS isolation_approval_delegations ON approval_delegations;
CREATE POLICY isolation_approval_delegations ON approval_delegations
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON approval_delegations TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE approval_delegations IS 'ADR-0037 Phase 2 — an OOO approver delegates pending approvals to a colleague.';

COMMIT;
