-- =====================================================================
-- 132_document_repository.sql — Enterprise Document Repository / DMS (ADR-0039)
--
-- Enterprise-wide hierarchical document store (Năm → Quý → Loại hồ sơ),
-- independent of any workflow, for ~10 years of records. REUSES the byte
-- store: files point at bronze_files (K-8 SHA-256 dedup + blob_store). Adds
-- only a folder hierarchy + a repository-file table.
--
-- Folder tree: adjacency-list (parent_id) + materialized slug `path` TEXT
-- (NOT ltree — ADR-0039 decision: no new extension; LIKE 'slug/%' +
-- text_pattern_ops serves subtree queries, parent_id serves lazy-load).
--
-- K-21 (gen_uuid_v7 PK + gen_ulid external) + RLS K-1 + ABAC dept-scope
-- (RESTRICTIVE, mirror mig 126). Soft-delete only (legal/audit, K-2 spirit).
-- =====================================================================

BEGIN;

-- ─── document_folder — enterprise-wide hierarchical folders ──────────
CREATE TABLE IF NOT EXISTS document_folder (
    folder_id     UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),     -- K-21
    external_ref  TEXT         NOT NULL DEFAULT gen_ulid(),           -- URL-friendly external id
    enterprise_id UUID         NOT NULL,
    department_id UUID         NOT NULL,
    parent_id     UUID         REFERENCES document_folder(folder_id) ON DELETE CASCADE,
    path          TEXT         NOT NULL,                              -- materialized slug e.g. 'tai_chinh/2024/q1'
    name_vi       VARCHAR(200) NOT NULL,
    sort_order    INTEGER      NOT NULL DEFAULT 0,
    archive_after TIMESTAMPTZ,                                        -- lifecycle hint
    deleted_at    TIMESTAMPTZ,                                        -- soft delete only
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docfolder_children
    ON document_folder(enterprise_id, parent_id, sort_order);
-- subtree prefix scans: WHERE path LIKE 'tai_chinh/2024/%'
CREATE INDEX IF NOT EXISTS idx_docfolder_path
    ON document_folder(enterprise_id, path text_pattern_ops);
-- sibling name uniqueness among non-deleted (NULL parent = root via nil uuid)
CREATE UNIQUE INDEX IF NOT EXISTS uq_docfolder_sibling
    ON document_folder(enterprise_id,
                       COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'::uuid),
                       name_vi)
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_docfolder_external ON document_folder(external_ref);


-- ─── document_repository_file — file instances in the repository ─────
CREATE TABLE IF NOT EXISTS document_repository_file (
    doc_id        UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),     -- K-21
    external_ref  TEXT         NOT NULL DEFAULT gen_ulid(),
    enterprise_id UUID         NOT NULL,
    department_id UUID         NOT NULL,
    folder_id     UUID         NOT NULL REFERENCES document_folder(folder_id) ON DELETE CASCADE,
    -- REUSE Bronze byte store + SHA-256 dedup (K-8) + blob_store; no parallel store.
    file_id       UUID         REFERENCES bronze_files(file_id) ON DELETE SET NULL,

    name_vi       VARCHAR(300) NOT NULL,
    doc_type      VARCHAR(40),                                        -- hop_dong/hoa_don/bao_cao/...
    status        VARCHAR(24)  NOT NULL DEFAULT 'active',

    -- version chain (mirror mig 111/120 supersedes pattern)
    version       INTEGER      NOT NULL DEFAULT 1,
    supersedes    UUID         REFERENCES document_repository_file(doc_id) ON DELETE SET NULL,
    superseded_by UUID,
    is_current    BOOLEAN      NOT NULL DEFAULT TRUE,
    change_reason TEXT,

    valid_until   TIMESTAMPTZ,
    storage_tier  VARCHAR(8)   NOT NULL DEFAULT 'hot',                -- hot/warm/cold (lifecycle)
    sha256        CHAR(64),                                          -- denorm for dedup/search
    uploaded_by   UUID,
    uploaded_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ,

    CONSTRAINT chk_drf_tier CHECK (storage_tier IN ('hot', 'warm', 'cold'))
);

CREATE INDEX IF NOT EXISTS idx_drf_folder
    ON document_repository_file(enterprise_id, folder_id, is_current);
CREATE INDEX IF NOT EXISTS idx_drf_sha ON document_repository_file(sha256);
CREATE INDEX IF NOT EXISTS idx_drf_name
    ON document_repository_file(enterprise_id, name_vi text_pattern_ops);


-- ─── RLS K-1 + ABAC dept-scope (RESTRICTIVE — mirror mig 126) ────────
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['document_folder', 'document_repository_file'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);

    EXECUTE format('DROP POLICY IF EXISTS isolation_%1$s ON %1$s', t);
    EXECUTE format($p$
      CREATE POLICY isolation_%1$s ON %1$s
        USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
        WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    $p$, t);

    -- RESTRICTIVE so it ANDs with isolation (a PERMISSIVE dept policy would OR
    -- and never actually filter — the mig 126 lesson). Empty dept GUC = full
    -- enterprise visibility (repository browse); set = scoped.
    EXECUTE format('DROP POLICY IF EXISTS abac_dept_%1$s ON %1$s', t);
    EXECUTE format($p$
      CREATE POLICY abac_dept_%1$s ON %1$s AS RESTRICTIVE
        USING (
          current_setting('app.current_department_id', true) = ''
          OR current_setting('app.current_department_id', true) IS NULL
          OR department_id::text = current_setting('app.current_department_id', true)
        )
    $p$, t);

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO kaori_app', t);
    END IF;
  END LOOP;
END $$;

COMMENT ON TABLE document_folder IS
    'ADR-0039 enterprise Document Repository — hierarchical folders (adjacency '
    '+ materialized path TEXT slug, NOT ltree). RLS K-1 + ABAC dept RESTRICTIVE.';
COMMENT ON TABLE document_repository_file IS
    'ADR-0039 repository file instances — reuse bronze_files byte store (K-8) + '
    'version chain. Separate from workflow_step_documents (kho ≠ đính bước).';

COMMIT;
