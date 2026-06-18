-- =====================================================================
-- 060_enterprise_node_taxonomy.sql
--
-- Path B (anh 2026-05-15 quyết định) — mở rộng workflow_nodes.node_type
-- thành 10 giá trị enterprise-grade + thêm CHECK constraint DB-level.
--
-- Lý do
-- -----
-- 4 node type (step / decision_if_else / decision_switch / approval_gate)
-- không đủ cho enterprise workflow thật. Camunda có 38 node types; ServiceNow
-- có hơn 100. Path B ship 6 node mới phủ ~80% use case của Vingroup:
--
--   wait_event       — "Chờ khách ký", "Chờ thanh toán"
--   sla_timer        — "48h, quá hạn thì escalate"
--   parallel_split   — "Pháp chế + Tài chính cùng review" (split point)
--   parallel_join    — đợi N nhánh xong (sync point)
--   subworkflow      — gọi workflow khác (gọi quy trình KYC từ quy trình
--                      mở tài khoản — quy trình con)
--   notification     — gửi email / Zalo / Teams cho stakeholder
--
-- + nâng category enum cộng 3 mã: 'wait', 'orchestration', 'communication'
--
-- Hành vi
-- -------
--  - DROP CHECK constraint cũ trên `category` (chưa có CHECK trên
--    node_type — mig 053 chỉ có VARCHAR + DEFAULT).
--  - ADD CHECK trên `node_type` (10 giá trị) → DB-level enforce.
--  - RE-ADD CHECK trên `category` (9 giá trị).
--  - K-17 invariant đã enforce qua side_effect_class — không touch lại.
--
-- Backward-compat
-- ---------------
-- Tất cả node hiện hữu (step / decision_if_else / decision_switch /
-- approval_gate) đều nằm trong list mới → không reject row nào sẵn có.
-- =====================================================================

BEGIN;

-- node_type — bổ sung CHECK constraint mới (chưa từng có).
ALTER TABLE workflow_nodes
    ADD CONSTRAINT chk_node_type CHECK (node_type IN (
        'step',
        'decision_if_else',
        'decision_switch',
        'approval_gate',
        'wait_event',
        'sla_timer',
        'parallel_split',
        'parallel_join',
        'subworkflow',
        'notification'
    ));

-- category — thay constraint cũ (6 giá trị) bằng list mới 9 giá trị.
ALTER TABLE workflow_nodes
    DROP CONSTRAINT IF EXISTS chk_node_category;

ALTER TABLE workflow_nodes
    ADD CONSTRAINT chk_node_category CHECK (category IN (
        'data_input',
        'processing',
        'decision',
        'ai',
        'action',
        'output',
        'wait',            -- NEW: wait_event sits here
        'orchestration',   -- NEW: parallel_split/join + subworkflow
        'communication'    -- NEW: notification
    ));

COMMENT ON COLUMN workflow_nodes.node_type IS
    'Path B (mig 060): 10 enterprise node types — step / decision_if_else / '
    'decision_switch / approval_gate / wait_event / sla_timer / parallel_split / '
    'parallel_join / subworkflow / notification.';

COMMENT ON COLUMN workflow_nodes.category IS
    'Path B (mig 060): 9 categories — data_input / processing / decision / ai / '
    'action / output / wait / orchestration / communication.';

COMMIT;
