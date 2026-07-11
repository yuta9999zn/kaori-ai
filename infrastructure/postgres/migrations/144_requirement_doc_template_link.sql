-- =====================================================================
-- 144_requirement_doc_template_link.sql — slot tài liệu ở bước workflow
-- tham chiếu MẪU TÀI LIỆU của Kho (ADR-0042) — yêu cầu 11/07.
--
-- Slot (workflow_step_document_requirements) gắn được document_type_template:
--   * cây tài liệu hiển thị "giấy này theo mẫu nào" ngay tại bước;
--   * khi nộp file chọn "Lưu vào Kho", bridge ƯU TIÊN folder đang gắn đúng
--     mẫu đó (document_folder.default_template_id), rồi mới rơi về folder
--     trùng tên workflow như cũ.
-- Nullable + additive; ON DELETE SET NULL — xóa mẫu không gãy cấu hình bước.
-- =====================================================================

BEGIN;

ALTER TABLE workflow_step_document_requirements
    ADD COLUMN IF NOT EXISTS doc_template_id UUID
        REFERENCES document_type_template(template_id) ON DELETE SET NULL;

COMMENT ON COLUMN workflow_step_document_requirements.doc_template_id IS
    'Mẫu tài liệu (document_type_template) mà slot này tham chiếu — hiển thị ở bước + định tuyến lưu Kho';

COMMIT;
