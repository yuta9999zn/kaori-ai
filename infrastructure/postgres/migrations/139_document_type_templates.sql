-- =====================================================================
-- 139_document_type_templates.sql — ADR-0042: Confluence-style document
-- structure for the DMS (doc-type templates + folder-as-page + typed
-- metadata + labels + collection insights).
--
-- Confluence mechanics adopted:
--   * blueprint per doc type      → document_type_template (metadata_schema
--     = the Page Properties table; section_outline = the page skeleton)
--   * folder = nghiệp vụ page     → document_folder gains body_md +
--     default_template_id + sample_file_id (file upload mẫu) + page_version
--   * page version history        → document_folder_version (append-only
--     snapshots, mirror mig 111 pattern; restore = new version, K-2 spirit)
--   * labels                      → TEXT[] + GIN on files
--   * Page Properties Report      → metadata JSONB + GIN (index endpoint is
--     generic; no table needed)
--   * insight doc/nhóm/folder     → document_collection_insight (async job)
--
-- K-21 (gen_uuid_v7 PK + gen_ulid external) + RLS K-1 (app.current_
-- enterprise_id, mirror mig 132; template table adds the mig-106 global-
-- NULL-row visibility + admin-bypass pattern). All additive/nullable.
-- Max migration was 138.
-- =====================================================================

BEGIN;

-- ─── document_type_template — blueprint per loại tài liệu ─────────────
CREATE TABLE IF NOT EXISTS document_type_template (
    template_id       UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    external_ref      TEXT         NOT NULL DEFAULT gen_ulid(),
    -- NULL = global Kaori-curated seed (readable by every tenant, mirror
    -- mig 106 semantics) · non-NULL = tenant-custom template.
    enterprise_id     UUID,
    department_id     UUID,

    type_key          VARCHAR(40)  NOT NULL,                            -- ke_hoach_du_an/hop_dong/...
    name_vi           VARCHAR(200) NOT NULL,
    icon              VARCHAR(16),                                      -- emoji
    description       TEXT,

    -- Ordered field defs — the Confluence Page Properties table:
    -- [{key,label_vi,kind,required,options?,default?}]
    -- kind ∈ text|long_text|number|money|date|user|department|select|status
    metadata_schema   JSONB        NOT NULL DEFAULT '[]'::jsonb,
    -- Ordered section skeleton: [{heading_vi,icon,hint_vi,body_kind}]
    section_outline   JSONB        NOT NULL DEFAULT '[]'::jsonb,
    default_labels    TEXT[]       NOT NULL DEFAULT '{}',

    requires_approval BOOLEAN      NOT NULL DEFAULT FALSE,
    approval_chain_id UUID         REFERENCES approval_chains(chain_id) ON DELETE SET NULL,

    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by        UUID,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- type_key unique per scope (global scope shares one namespace via nil uuid)
CREATE UNIQUE INDEX IF NOT EXISTS uq_doctpl_scope_key
    ON document_type_template(
        COALESCE(enterprise_id, '00000000-0000-0000-0000-000000000000'::uuid),
        type_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_doctpl_external ON document_type_template(external_ref);
CREATE INDEX IF NOT EXISTS idx_doctpl_enterprise
    ON document_type_template(enterprise_id, is_active);


-- ─── folder = nghiệp vụ page (Confluence: every tree node is a page) ──
ALTER TABLE document_folder
    ADD COLUMN IF NOT EXISTS body_md             TEXT,
    ADD COLUMN IF NOT EXISTS default_template_id UUID REFERENCES document_type_template(template_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS sample_file_id      UUID REFERENCES bronze_files(file_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS default_labels      TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS page_version        INTEGER NOT NULL DEFAULT 1;


-- ─── document_folder_version — page-version history (mirror mig 111) ──
CREATE TABLE IF NOT EXISTS document_folder_version (
    version_id        UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    folder_id         UUID         NOT NULL REFERENCES document_folder(folder_id) ON DELETE CASCADE,
    enterprise_id     UUID         NOT NULL,
    version_no        INTEGER      NOT NULL,

    -- snapshot of the page definition at this version
    body_md           TEXT,
    template_snapshot JSONB,                                            -- bound template's schema+outline
    sample_file_id    UUID         REFERENCES bronze_files(file_id) ON DELETE SET NULL,

    edited_by         UUID,
    edited_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    change_note       TEXT,

    CONSTRAINT uq_dfv_folder_version UNIQUE (folder_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_dfv_folder
    ON document_folder_version(enterprise_id, folder_id, version_no DESC);


-- ─── typed metadata + labels on repository files ──────────────────────
ALTER TABLE document_repository_file
    ADD COLUMN IF NOT EXISTS template_id            UUID REFERENCES document_type_template(template_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS metadata               JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS labels                 TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS metadata_completeness  NUMERIC(5,4),        -- K-9; K-25 completeness pattern
    ADD COLUMN IF NOT EXISTS validated_page_version INTEGER;             -- page_version the doc was validated against

CREATE INDEX IF NOT EXISTS idx_drf_metadata_gin
    ON document_repository_file USING gin (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_drf_labels_gin
    ON document_repository_file USING gin (labels);
CREATE INDEX IF NOT EXISTS idx_drf_template
    ON document_repository_file(enterprise_id, template_id)
    WHERE is_current AND deleted_at IS NULL;


-- ─── document_collection_insight — insight nhóm/folder (async job) ────
CREATE TABLE IF NOT EXISTS document_collection_insight (
    insight_id    UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),        -- K-21
    external_ref  TEXT         NOT NULL DEFAULT gen_ulid(),
    enterprise_id UUID         NOT NULL,
    department_id UUID,

    scope_kind    VARCHAR(8)   NOT NULL,                                 -- group | folder
    scope         JSONB        NOT NULL,                                 -- slice descriptor (re-runnable)
    doc_count     INTEGER,

    status        VARCHAR(12)  NOT NULL DEFAULT 'pending',
    model         VARCHAR(40),
    stats         JSONB        NOT NULL DEFAULT '{}'::jsonb,             -- deterministic aggregates
    summary       TEXT,                                                  -- grounded Qwen synthesis
    findings      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    error         TEXT,

    requested_by  UUID,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,

    CONSTRAINT chk_dci_scope_kind CHECK (scope_kind IN ('group', 'folder')),
    CONSTRAINT chk_dci_status CHECK (status IN ('pending', 'running', 'complete', 'failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dci_external ON document_collection_insight(external_ref);
CREATE INDEX IF NOT EXISTS idx_dci_latest
    ON document_collection_insight(enterprise_id, created_at DESC);


-- ─── RLS (K-1) ────────────────────────────────────────────────────────
-- Plain tenant isolation for version + insight tables (mirror mig 132).
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['document_folder_version', 'document_collection_insight'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS isolation_%1$s ON %1$s', t);
    EXECUTE format($p$
      CREATE POLICY isolation_%1$s ON %1$s
        USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
        WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    $p$, t);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO kaori_app', t);
    END IF;
  END LOOP;
END $$;

-- Template table: tenants SEE global rows (enterprise_id IS NULL) + their own,
-- WRITE only their own (mig 106 semantics, on the DMS-family GUC). Platform
-- admin curates globals via app.is_admin (mig 105/025 pattern).
ALTER TABLE document_type_template ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_document_type_template ON document_type_template;
CREATE POLICY tenant_document_type_template ON document_type_template
    USING (
        enterprise_id IS NULL
        OR enterprise_id::text = current_setting('app.current_enterprise_id', true)
    )
    WITH CHECK (
        enterprise_id::text = current_setting('app.current_enterprise_id', true)
    );

DROP POLICY IF EXISTS admin_bypass_document_type_template ON document_type_template;
CREATE POLICY admin_bypass_document_type_template ON document_type_template
    USING      (current_setting('app.is_admin', true) = 'true')
    WITH CHECK (current_setting('app.is_admin', true) = 'true');

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON document_type_template TO kaori_app;
  END IF;
END $$;


-- ─── Global seed templates (enterprise_id NULL — Kaori curated) ───────
-- WHERE NOT EXISTS guards keep the migration idempotent.
INSERT INTO document_type_template
    (enterprise_id, type_key, name_vi, icon, description, metadata_schema, section_outline, default_labels)
SELECT NULL, 'ke_hoach_du_an', 'Kế hoạch dự án', '📋',
       'Kế hoạch triển khai một dự án/sáng kiến — theo khung Project plan.',
       '[
         {"key":"nguoi_phu_trach","label_vi":"Người phụ trách","kind":"user","required":true},
         {"key":"nguoi_duyet","label_vi":"Người duyệt","kind":"user","required":true},
         {"key":"muc_tieu","label_vi":"Mục tiêu","kind":"text","required":true},
         {"key":"han_chot","label_vi":"Hạn chót","kind":"date","required":true},
         {"key":"ket_qua_ky_vong","label_vi":"Kết quả kỳ vọng","kind":"long_text","required":false},
         {"key":"trang_thai","label_vi":"Trạng thái","kind":"status","required":true,
          "options":["chua_bat_dau","dang_thuc_hien","hoan_thanh"],"default":"chua_bat_dau"}
       ]'::jsonb,
       '[
         {"heading_vi":"Vấn đề","icon":"🤔","hint_vi":"Mô tả vấn đề và tác động; giả thuyết dẫn dắt.","body_kind":"prose"},
         {"heading_vi":"Phạm vi","icon":"🎯","hint_vi":"Bắt buộc có / Nên có / Ngoài phạm vi.","body_kind":"table"},
         {"heading_vi":"Timeline","icon":"🗓","hint_vi":"Các mốc thời gian chính.","body_kind":"prose"},
         {"heading_vi":"Cột mốc","icon":"🚩","hint_vi":"Cột mốc · Người phụ trách · Hạn · Trạng thái.","body_kind":"table"},
         {"heading_vi":"Liên kết","icon":"🗂","hint_vi":"Tài liệu/nghiên cứu liên quan.","body_kind":"checklist"}
       ]'::jsonb,
       ARRAY['loai:ke-hoach-du-an']
WHERE NOT EXISTS (SELECT 1 FROM document_type_template
                  WHERE enterprise_id IS NULL AND type_key = 'ke_hoach_du_an');

INSERT INTO document_type_template
    (enterprise_id, type_key, name_vi, icon, description, metadata_schema, section_outline, default_labels)
SELECT NULL, 'bien_ban_hop', 'Biên bản họp', '📝',
       'Biên bản cuộc họp — quyết định và việc cần làm có chủ.',
       '[
         {"key":"ngay_hop","label_vi":"Ngày họp","kind":"date","required":true},
         {"key":"chu_tri","label_vi":"Chủ trì","kind":"user","required":true},
         {"key":"thu_ky","label_vi":"Thư ký","kind":"user","required":false},
         {"key":"thanh_phan","label_vi":"Thành phần","kind":"text","required":false},
         {"key":"trang_thai","label_vi":"Trạng thái","kind":"status","required":true,
          "options":["du_thao","da_chot"],"default":"du_thao"}
       ]'::jsonb,
       '[
         {"heading_vi":"Mục tiêu cuộc họp","icon":"🎯","hint_vi":"Họp để quyết định điều gì.","body_kind":"prose"},
         {"heading_vi":"Nội dung thảo luận","icon":"💬","hint_vi":"Các điểm chính đã bàn.","body_kind":"prose"},
         {"heading_vi":"Quyết định","icon":"✅","hint_vi":"Quyết định đã chốt.","body_kind":"checklist"},
         {"heading_vi":"Việc cần làm","icon":"📌","hint_vi":"Việc · Người làm · Hạn.","body_kind":"table"}
       ]'::jsonb,
       ARRAY['loai:bien-ban-hop']
WHERE NOT EXISTS (SELECT 1 FROM document_type_template
                  WHERE enterprise_id IS NULL AND type_key = 'bien_ban_hop');

INSERT INTO document_type_template
    (enterprise_id, type_key, name_vi, icon, description, metadata_schema, section_outline, default_labels)
SELECT NULL, 'hop_dong', 'Hợp đồng', '📄',
       'Hợp đồng với đối tác — giá trị, hiệu lực, người phụ trách.',
       '[
         {"key":"doi_tac","label_vi":"Đối tác","kind":"text","required":true},
         {"key":"gia_tri","label_vi":"Giá trị","kind":"money","required":true},
         {"key":"ngay_ky","label_vi":"Ngày ký","kind":"date","required":true},
         {"key":"ngay_het_han","label_vi":"Ngày hết hạn","kind":"date","required":false},
         {"key":"nguoi_phu_trach","label_vi":"Người phụ trách","kind":"user","required":true},
         {"key":"trang_thai","label_vi":"Trạng thái","kind":"status","required":true,
          "options":["soan_thao","cho_ky","hieu_luc","het_hieu_luc","thanh_ly"],"default":"soan_thao"}
       ]'::jsonb,
       '[
         {"heading_vi":"Điều khoản chính","icon":"⚖️","hint_vi":"Phạm vi, thanh toán, phạt, chấm dứt.","body_kind":"prose"},
         {"heading_vi":"Phụ lục","icon":"📎","hint_vi":"Bảng giá/khối lượng đính kèm.","body_kind":"checklist"}
       ]'::jsonb,
       ARRAY['loai:hop-dong']
WHERE NOT EXISTS (SELECT 1 FROM document_type_template
                  WHERE enterprise_id IS NULL AND type_key = 'hop_dong');

INSERT INTO document_type_template
    (enterprise_id, type_key, name_vi, icon, description, metadata_schema, section_outline, default_labels)
SELECT NULL, 'bao_cao_ngay', 'Báo cáo định kỳ', '📊',
       'Báo cáo ngày/tuần/tháng — kỳ báo cáo khai ở doc_date/period_kind (mig 138).',
       '[
         {"key":"nguoi_lap","label_vi":"Người lập","kind":"user","required":true},
         {"key":"phong_ban","label_vi":"Phòng ban","kind":"department","required":false},
         {"key":"trang_thai","label_vi":"Trạng thái","kind":"status","required":true,
          "options":["nhap","da_nop","da_duyet"],"default":"nhap"}
       ]'::jsonb,
       '[
         {"heading_vi":"Kết quả chính","icon":"📈","hint_vi":"Số liệu nổi bật trong kỳ.","body_kind":"prose"},
         {"heading_vi":"Vấn đề tồn đọng","icon":"⚠️","hint_vi":"Rủi ro/vướng mắc cần xử lý.","body_kind":"checklist"},
         {"heading_vi":"Kế hoạch tiếp theo","icon":"➡️","hint_vi":"Việc kỳ tới.","body_kind":"checklist"}
       ]'::jsonb,
       ARRAY['loai:bao-cao']
WHERE NOT EXISTS (SELECT 1 FROM document_type_template
                  WHERE enterprise_id IS NULL AND type_key = 'bao_cao_ngay');

INSERT INTO document_type_template
    (enterprise_id, type_key, name_vi, icon, description, metadata_schema, section_outline, default_labels)
SELECT NULL, 'sop', 'Quy trình chuẩn (SOP)', '📐',
       'Quy trình vận hành chuẩn của một nghiệp vụ.',
       '[
         {"key":"quy_trinh","label_vi":"Quy trình áp dụng","kind":"text","required":true},
         {"key":"nguoi_ban_hanh","label_vi":"Người ban hành","kind":"user","required":true},
         {"key":"ngay_hieu_luc","label_vi":"Ngày hiệu lực","kind":"date","required":true},
         {"key":"trang_thai","label_vi":"Trạng thái","kind":"status","required":true,
          "options":["du_thao","hieu_luc","thay_the"],"default":"du_thao"}
       ]'::jsonb,
       '[
         {"heading_vi":"Phạm vi áp dụng","icon":"🎯","hint_vi":"Áp dụng cho ai, khi nào.","body_kind":"prose"},
         {"heading_vi":"Các bước thực hiện","icon":"🪜","hint_vi":"Từng bước, ai làm, đầu ra.","body_kind":"table"},
         {"heading_vi":"Biểu mẫu liên quan","icon":"📎","hint_vi":"File mẫu đính kèm.","body_kind":"checklist"}
       ]'::jsonb,
       ARRAY['loai:sop']
WHERE NOT EXISTS (SELECT 1 FROM document_type_template
                  WHERE enterprise_id IS NULL AND type_key = 'sop');


COMMENT ON TABLE document_type_template IS
    'ADR-0042 doc-type blueprints (Confluence-style). metadata_schema = Page '
    'Properties fields; section_outline = page skeleton. enterprise_id NULL = '
    'global Kaori seed (mig 106 visibility semantics).';
COMMENT ON TABLE document_folder_version IS
    'ADR-0042 page-version history of a folder''s nghiệp vụ-page definition '
    '(body_md + template snapshot + sample file). Append-only; restore = new version.';
COMMENT ON TABLE document_collection_insight IS
    'ADR-0042 insight over a doc slice (group/folder). scope JSONB is the '
    're-runnable slice descriptor; stats deterministic-first, summary = grounded '
    'Qwen synthesis over per-doc summaries. Async job — never in request path.';
COMMENT ON COLUMN document_folder.body_md IS
    'ADR-0042 folder-as-page: Markdown body describing the nghiệp vụ (Confluence page body).';
COMMENT ON COLUMN document_repository_file.metadata IS
    'ADR-0042 filled Page Properties, keyed by template metadata_schema[].key. '
    'Unknown keys preserved under _extra.';
COMMENT ON COLUMN document_repository_file.metadata_completeness IS
    'K-25-style completeness (0..1) vs the template schema — flagged, never blocking.';

COMMIT;
