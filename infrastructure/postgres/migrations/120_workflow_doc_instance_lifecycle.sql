-- =====================================================================
-- 120_workflow_doc_instance_lifecycle.sql — Tier-3 Document Tree, Phase 1 (ADR-0037)
--
-- Promote workflow_step_documents from a flat attach-link into a versioned,
-- status-tracked document INSTANCE:
--   • doc_class       — input/output/reference (mirrors mig 119 requirement)
--   • requirement_id  — which requirement this fulfils (nullable for ad-hoc)
--   • status          — 7-state document machine (chờ nộp → … → đã duyệt / từ chối)
--   • version chain   — version / supersedes / superseded_by / change_reason /
--                       is_current (mirrors knowledge_documents mig 111)
--   • review + expiry — reviewed_by / reviewed_at / review_note / valid_until
--
-- Additive: nullable columns + a CHECK + indexes. The existing
-- UNIQUE(workflow_id, node_id, file_id) survives — a new version uploads a NEW
-- file_id (new bytes → new bronze row), so versions chain via supersedes
-- without colliding. K-2 spirit: old versions are retained (superseded), not
-- overwritten.
-- =====================================================================

BEGIN;

ALTER TABLE workflow_step_documents
    ADD COLUMN IF NOT EXISTS requirement_id  UUID
        REFERENCES workflow_step_document_requirements(requirement_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS doc_class       VARCHAR(16),
    ADD COLUMN IF NOT EXISTS status          VARCHAR(24)  NOT NULL DEFAULT 'da_nop',
    ADD COLUMN IF NOT EXISTS version         INTEGER      NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS supersedes      UUID         REFERENCES workflow_step_documents(attachment_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS superseded_by   UUID         REFERENCES workflow_step_documents(attachment_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS change_reason   TEXT,
    ADD COLUMN IF NOT EXISTS is_current      BOOLEAN      NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS reviewed_by     UUID,
    ADD COLUMN IF NOT EXISTS reviewed_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_note     TEXT,
    ADD COLUMN IF NOT EXISTS valid_until     TIMESTAMPTZ;

-- 7-state document machine. Defaults to 'da_nop' so existing rows (already
-- uploaded files) read as "đã nộp" — a sane backfill, no data migration needed.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_wsd_status'
    ) THEN
        ALTER TABLE workflow_step_documents
            ADD CONSTRAINT chk_wsd_status CHECK (status IN (
                'cho_nop',          -- 🔘 required, not yet uploaded
                'da_nop',           -- 📄 uploaded, awaiting review
                'dang_xem_xet',     -- 👀 under review
                'da_duyet',         -- ✅ approved
                'tu_choi',          -- ❌ rejected (review_note carries the reason)
                'yeu_cau_bo_sung',  -- 🔄 needs more info
                'het_han'           -- ⚠️ past valid_until
            ));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_wsd_class'
    ) THEN
        ALTER TABLE workflow_step_documents
            ADD CONSTRAINT chk_wsd_class CHECK (doc_class IS NULL OR doc_class IN ('input', 'output', 'reference'));
    END IF;
END $$;

-- Fast "current docs for this step" + version-chain walk.
CREATE INDEX IF NOT EXISTS idx_wsd_node_current ON workflow_step_documents(node_id, is_current);
CREATE INDEX IF NOT EXISTS idx_wsd_requirement  ON workflow_step_documents(requirement_id);
CREATE INDEX IF NOT EXISTS idx_wsd_supersedes   ON workflow_step_documents(supersedes);
CREATE INDEX IF NOT EXISTS idx_wsd_status       ON workflow_step_documents(enterprise_id, status);

COMMENT ON COLUMN workflow_step_documents.status IS
    'ADR-0037 7-state document machine: cho_nop|da_nop|dang_xem_xet|da_duyet|'
    'tu_choi|yeu_cau_bo_sung|het_han';
COMMENT ON COLUMN workflow_step_documents.is_current IS
    'ADR-0037 — TRUE for the latest version in a supersedes chain; an upload of a '
    'new version flips the prior row FALSE + sets superseded_by.';

COMMIT;
