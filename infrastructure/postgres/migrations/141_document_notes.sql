-- =====================================================================
-- 141_document_notes.sql — Ghi chú/bình luận trên tài liệu (ADR-0042 P2)
--
-- Confluence page comments cho DMS: mỗi tài liệu (file upload hoặc soạn
-- trong Kaori) có dải ghi chú — ai, lúc nào, nội dung Markdown. Soft
-- delete (K-2 spirit). K-21 + RLS mirror mig 132. Max migration was 140.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS document_note (
    note_id       UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    enterprise_id UUID         NOT NULL,
    doc_id        UUID         NOT NULL REFERENCES document_repository_file(doc_id) ON DELETE CASCADE,

    body_md       TEXT         NOT NULL,
    author_id     UUID,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_docnote_doc
    ON document_note(enterprise_id, doc_id, created_at)
    WHERE deleted_at IS NULL;

ALTER TABLE document_note ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS isolation_document_note ON document_note;
CREATE POLICY isolation_document_note ON document_note
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON document_note TO kaori_app;
  END IF;
END $$;

COMMENT ON TABLE document_note IS
    'ADR-0042 P2 — ghi chú/bình luận trên tài liệu DMS (Confluence page comments). '
    'Soft delete; body Markdown.';

COMMIT;
