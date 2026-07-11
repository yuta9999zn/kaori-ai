-- =====================================================================
-- 143_workflow_timeline_deadlines.sql — thước timeline + deadline (11/07)
--
-- Lớp THEO DÕI phủ lên workflow, không đụng nghiệp vụ/tài liệu/BPMN:
--   * workflows.duration_days  — quy trình dự kiến chạy trong bao nhiêu ngày
--   * workflows.timeline_start — ngày bắt đầu chu kỳ hiện tại (mở workflow
--     lên biết đang ở "ngày thứ mấy / tổng số ngày")
--   * workflow_nodes.deadline_date — hạn cuối của từng card (bước), để
--     theo dõi realtime + phát sinh trễ hạn nhìn thấy ngay
-- Tất cả nullable + additive — workflow cũ không khai báo thì UI ẩn thước.
-- =====================================================================

BEGIN;

ALTER TABLE workflows      ADD COLUMN IF NOT EXISTS duration_days  INTEGER;
ALTER TABLE workflows      ADD COLUMN IF NOT EXISTS timeline_start DATE;
ALTER TABLE workflow_nodes ADD COLUMN IF NOT EXISTS deadline_date  DATE;

COMMENT ON COLUMN workflows.duration_days IS
    'Số ngày dự kiến thực hiện trọn quy trình (thước timeline) — nullable, chỉ để theo dõi';
COMMENT ON COLUMN workflows.timeline_start IS
    'Ngày bắt đầu chu kỳ hiện tại của quy trình — mốc tính "đang ở ngày thứ mấy"';
COMMENT ON COLUMN workflow_nodes.deadline_date IS
    'Hạn cuối của bước (card) trong chu kỳ — nullable, để theo dõi trễ hạn';

COMMIT;
