-- =====================================================================
-- 135_workflow_approval_gate_kind.sql — EU AI Act Layer 3 (ADR-0041, K-23)
--
-- Discriminate an EU-AI-Act human-oversight pause from an author-placed
-- approval_gate. Additive: one nullable-safe column with a default; all
-- existing rows become 'approval_gate' (their actual meaning). No backfill.
-- =====================================================================

BEGIN;

ALTER TABLE workflow_approvals
    ADD COLUMN IF NOT EXISTS gate_kind VARCHAR(24) NOT NULL DEFAULT 'approval_gate';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_wfappr_gate_kind'
    ) THEN
        ALTER TABLE workflow_approvals
            ADD CONSTRAINT chk_wfappr_gate_kind
            CHECK (gate_kind IN ('approval_gate', 'eu_ai_act_oversight'));
    END IF;
END $$;

COMMENT ON COLUMN workflow_approvals.gate_kind IS
    'ADR-0041 K-23 — approval_gate (author-placed) | eu_ai_act_oversight '
    '(auto high-risk oversight). Runner replay keys on node_type, so this is '
    'for audit + the oversight already-granted query.';

COMMIT;
