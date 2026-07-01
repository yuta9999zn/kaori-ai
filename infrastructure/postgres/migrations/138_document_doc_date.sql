-- =====================================================================
-- 138_document_doc_date.sql — Kho tài liệu: business date + period kind
--
-- A daily report dated 30/06 can be uploaded on 02/07 — filtering by
-- uploaded_at is business-wrong. `doc_date` carries the document's
-- BUSINESS date; `period_kind` its reporting period (day/week/month/
-- quarter/year). Time lives as METADATA, not as physical tree depth:
-- the FE renders a virtual Năm→Quý→Tháng→Ngày view by grouping on
-- COALESCE(doc_date, uploaded_at::date) — no folder explosion, and
-- weekly reports (which straddle months) stay filterable.
--
-- Additive: two nullable columns + one index. Max migration was 137.
-- =====================================================================

BEGIN;

ALTER TABLE document_repository_file
    ADD COLUMN IF NOT EXISTS doc_date     DATE,
    ADD COLUMN IF NOT EXISTS period_kind  VARCHAR(8);

-- Nullable CHECK — NULL passes; only constrain non-null values.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_docrepo_period_kind'
    ) THEN
        ALTER TABLE document_repository_file
            ADD CONSTRAINT chk_docrepo_period_kind
            CHECK (period_kind IS NULL OR
                   period_kind IN ('day','week','month','quarter','year'));
    END IF;
END $$;

-- Range filters hit (enterprise, doc_date). NOTE: an expression index on
-- COALESCE(doc_date, uploaded_at::date) is not possible — timestamptz::date
-- is STABLE (timezone-dependent), not IMMUTABLE. A plain index + the
-- existing uploaded_at ordering is enough at SME document volumes.
CREATE INDEX IF NOT EXISTS idx_docrepo_doc_date
    ON document_repository_file (enterprise_id, doc_date)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN document_repository_file.doc_date IS
    'Business date of the document (báo cáo ngày 30/06 uploaded 02/07 → 2026-06-30). '
    'NULL → filters/timeline fall back to uploaded_at::date.';
COMMENT ON COLUMN document_repository_file.period_kind IS
    'Reporting period of the document: day|week|month|quarter|year. Metadata, '
    'not tree structure — weekly reports straddle months so a physical tree cannot hold them.';

COMMIT;
