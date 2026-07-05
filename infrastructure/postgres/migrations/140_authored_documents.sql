-- =====================================================================
-- 140_authored_documents.sql — ADR-0042 Phase 2: tài liệu SOẠN trong Kaori
-- (authored documents) theo bộ khung xương của template.
--
-- Reference: "Message Definition.pdf" (BA-standard doc, 2026-07-05) — a
-- document is a SKELETON: metadata header (Page Properties, mig 139) +
-- numbered sections, each an intro paragraph + a fixed-column BILINGUAL
-- table (+ link attachments). History Changes is NOT authored — it renders
-- from the existing version chain (supersedes/superseded_by).
--
-- Additive:
--   * document_repository_file.content  JSONB — the authored body:
--       {"sections":[{"key","heading_vi"?,"heading_en"?,"body_md",
--                     "rows":[{col:val}],"links":[{"text","url"}]}]}
--     body_md supports headings/sub/bold/lists/checklist/==highlight==.
--   * document_repository_file.doc_kind — 'file' (uploaded bytes) |
--     'authored' (content JSONB, file_id NULL).
--   * section_outline CONVENTION (data, no DDL): table sections carry
--     "columns":[{key,label_vi,label_en?,kind}] — kind reuses the
--     metadata field vocabulary + 'link'. label_en everywhere is the
--     bilingual axis ("nhớ làm cả ngôn ngữ") — FE falls back to _vi.
--   * global seed 'message_definition' mirroring the PDF skeleton.
--
-- Max migration was 139.
-- =====================================================================

BEGIN;

ALTER TABLE document_repository_file
    ADD COLUMN IF NOT EXISTS content  JSONB,
    ADD COLUMN IF NOT EXISTS doc_kind VARCHAR(12) NOT NULL DEFAULT 'file';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_drf_doc_kind') THEN
        ALTER TABLE document_repository_file
            ADD CONSTRAINT chk_drf_doc_kind CHECK (doc_kind IN ('file', 'authored'));
    END IF;
END $$;

COMMENT ON COLUMN document_repository_file.content IS
    'ADR-0042 P2 authored body: {"sections":[{key,heading_vi?,heading_en?,'
    'body_md,rows[],links[]}]}. NULL for uploaded files. Edits stack a new '
    'version (Confluence page semantics) — History Changes renders from the chain.';
COMMENT ON COLUMN document_repository_file.doc_kind IS
    'file = uploaded bytes (bronze) · authored = soạn trong Kaori (content JSONB).';


-- ─── Global seed: Message Definition (song ngữ, mirror PDF skeleton) ──
INSERT INTO document_type_template
    (enterprise_id, type_key, name_vi, icon, description, metadata_schema, section_outline, default_labels)
SELECT NULL, 'message_definition', 'Định nghĩa thông báo (Message Definition)', '💬',
       'Chuẩn BA cho thông báo hệ thống: lỗi hệ thống / lỗi người dùng / lỗi nghiệp vụ + '
       'glossary + tài liệu đính kèm. Lịch sử chỉnh sửa (History Changes) tự sinh từ '
       'chuỗi phiên bản — không phải gõ tay.',
       '[
         {"key":"nguoi_thuc_hien","label_vi":"Người thực hiện","label_en":"Document Owner","kind":"user","required":true},
         {"key":"nguoi_xem_xet","label_vi":"Người xem xét","label_en":"Document Reviewer","kind":"user","required":false},
         {"key":"nguoi_duyet","label_vi":"Người duyệt","label_en":"Document Approver","kind":"user","required":true},
         {"key":"phien_ban","label_vi":"Phiên bản","label_en":"Version","kind":"text","required":false},
         {"key":"trang_thai","label_vi":"Trạng thái","label_en":"Status","kind":"status","required":true,
          "options":["du_thao","dang_xem_xet","chinh_thuc"],"default":"du_thao"}
       ]'::jsonb,
       '[
         {"key":"glossary","heading_vi":"Giải thích thuật ngữ","heading_en":"Business Glossary","icon":"📖",
          "hint_vi":"Các thuật ngữ dùng trong phạm vi tài liệu.","body_kind":"table",
          "columns":[
            {"key":"acronym","label_vi":"Thuật ngữ viết tắt","label_en":"Acronym","kind":"text"},
            {"key":"item","label_vi":"Thuật ngữ đầy đủ","label_en":"Item","kind":"text"},
            {"key":"description","label_vi":"Giải thích chi tiết","label_en":"Description","kind":"long_text"}]},
         {"key":"attachments","heading_vi":"Tài liệu đính kèm","heading_en":"Reference Attachments","icon":"📎",
          "hint_vi":"Tài liệu tham chiếu dùng để phân tích nghiệp vụ.","body_kind":"table",
          "columns":[
            {"key":"mo_ta","label_vi":"Mô tả","label_en":"Description","kind":"text"},
            {"key":"link","label_vi":"Link tài liệu","label_en":"Attachment Link","kind":"link"}]},
         {"key":"sys_error","heading_vi":"Lỗi hệ thống","heading_en":"System Error","icon":"🛠",
          "hint_vi":"Lỗi kỹ thuật phát sinh bên trong hệ thống — không do người dùng.","body_kind":"table",
          "columns":[
            {"key":"error_code","label_vi":"Mã lỗi","label_en":"Error Code","kind":"text"},
            {"key":"error_type","label_vi":"Loại lỗi","label_en":"Error Type","kind":"text"},
            {"key":"error_info","label_vi":"Thông tin lỗi","label_en":"Error Information","kind":"text"},
            {"key":"error_message","label_vi":"Thông báo lỗi","label_en":"Error Message","kind":"long_text"},
            {"key":"error_desc","label_vi":"Mô tả lỗi","label_en":"Error Description","kind":"long_text"},
            {"key":"action","label_vi":"Hướng xử lý","label_en":"Action","kind":"text"},
            {"key":"be_code","label_vi":"Mã lỗi Back End","label_en":"BackEnd Error Code","kind":"text"},
            {"key":"note","label_vi":"Ghi chú","label_en":"Note","kind":"text"}]},
         {"key":"usr_error","heading_vi":"Lỗi người dùng","heading_en":"User Error","icon":"👤",
          "hint_vi":"Lỗi do thao tác/nhập liệu của người dùng (xác thực, thiếu trường, sai định dạng, min/max, trùng…).","body_kind":"table",
          "columns":[
            {"key":"error_code","label_vi":"Mã lỗi","label_en":"Error Code","kind":"text"},
            {"key":"error_type","label_vi":"Loại lỗi","label_en":"Error Type","kind":"text"},
            {"key":"error_info","label_vi":"Thông tin lỗi","label_en":"Error Information","kind":"text"},
            {"key":"error_message","label_vi":"Thông báo lỗi","label_en":"Error Message","kind":"long_text"},
            {"key":"error_desc","label_vi":"Mô tả lỗi","label_en":"Error Description","kind":"long_text"},
            {"key":"action","label_vi":"Hướng xử lý","label_en":"Action","kind":"text"},
            {"key":"be_code","label_vi":"Mã lỗi Back End","label_en":"BackEnd Error Code","kind":"text"},
            {"key":"note","label_vi":"Ghi chú","label_en":"Note","kind":"text"}]},
         {"key":"biz_error","heading_vi":"Lỗi thao tác nghiệp vụ","heading_en":"Business Logic Error","icon":"⚖️",
          "hint_vi":"Vi phạm quy tắc/luồng/trạng thái nghiệp vụ.","body_kind":"table",
          "columns":[
            {"key":"error_code","label_vi":"Mã lỗi","label_en":"Error Code","kind":"text"},
            {"key":"error_type","label_vi":"Loại lỗi","label_en":"Error Type","kind":"text"},
            {"key":"error_info","label_vi":"Thông tin lỗi","label_en":"Error Information","kind":"text"},
            {"key":"error_message","label_vi":"Thông báo lỗi","label_en":"Error Message","kind":"long_text"},
            {"key":"error_desc","label_vi":"Mô tả lỗi","label_en":"Error Description","kind":"long_text"},
            {"key":"action","label_vi":"Hướng xử lý","label_en":"Action","kind":"text"},
            {"key":"be_code","label_vi":"Mã lỗi Back End","label_en":"BackEnd Error Code","kind":"text"},
            {"key":"note","label_vi":"Ghi chú","label_en":"Note","kind":"text"}]},
         {"key":"other_msg","heading_vi":"Thông báo khác","heading_en":"Other Messages","icon":"🔔",
          "hint_vi":"Warning / Success / Information / Confirmation / Input Helper.","body_kind":"table",
          "columns":[
            {"key":"loai","label_vi":"Loại","label_en":"Type","kind":"select",
             "options":["warning","success","information","confirmation","input_helper"]},
            {"key":"message","label_vi":"Nội dung thông báo","label_en":"Message","kind":"long_text"},
            {"key":"mo_ta","label_vi":"Mô tả","label_en":"Description","kind":"long_text"},
            {"key":"action","label_vi":"Cách hiển thị","label_en":"Action","kind":"text"}]}
       ]'::jsonb,
       ARRAY['loai:message-definition']
WHERE NOT EXISTS (SELECT 1 FROM document_type_template
                  WHERE enterprise_id IS NULL AND type_key = 'message_definition');

COMMIT;
