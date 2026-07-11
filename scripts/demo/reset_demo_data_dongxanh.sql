-- =====================================================================
-- reset_demo_data_dongxanh.sql — dọn DATA demo của tenant Đồng Xanh
-- để tập lại demo AABW bằng tay từ đầu (yêu cầu 11/07/2026).
--
-- XÓA: Kho tài liệu (folder + file + note + insight + version) ·
--      tài liệu đã nộp vào cây workflow · workflow RUNS (+ node states,
--      approvals, insights, hợp đồng e-sign sinh từ run) ·
--      pipeline runs + Bronze/Silver + analysis runs/results + embeddings.
-- GIỮ: workflows + nodes/edges + BPMN + cây yêu cầu tài liệu (cấu hình) ·
--      phòng ban/cơ cấu tổ chức · KB (knowledge_documents) · mẫu tài liệu
--      (document_type_template) · form submissions (input node Nhận Form —
--      xóa thì workflow không chạy; muốn nạp lại dùng scripts/demo/
--      p5_thu_mua_htx/seed.py) · ai_decision_audit (K-6, không đụng) ·
--      users/quota/settings.
--
-- Chạy: docker cp file vào kaori-postgres-1 rồi
--   docker exec kaori-postgres-1 psql -U kaori -d kaori -f /tmp/reset.sql
-- =====================================================================

BEGIN;

DO $$
DECLARE ent UUID := '3d1c1a53-f924-41fa-a4ce-defade00e898';
BEGIN
  -- ── Kho tài liệu (DMS) ────────────────────────────────────────────
  DELETE FROM document_note                WHERE enterprise_id = ent;
  DELETE FROM document_collection_insight  WHERE enterprise_id = ent;
  DELETE FROM document_folder_version      WHERE enterprise_id = ent;
  DELETE FROM document_repository_file     WHERE enterprise_id = ent;
  DELETE FROM document_folder              WHERE enterprise_id = ent;

  -- ── Tài liệu đã nộp vào cây workflow (giữ requirements = cấu hình) ─
  DELETE FROM document_analysis            WHERE enterprise_id = ent;
  DELETE FROM workflow_step_documents      WHERE enterprise_id = ent;

  -- ── Workflow runs + phụ trợ (giữ workflow definitions + BPMN) ─────
  DELETE FROM contract_signatures          WHERE enterprise_id = ent;
  DELETE FROM contract_parties             WHERE enterprise_id = ent;
  DELETE FROM contracts                    WHERE enterprise_id = ent AND workflow_run_id IS NOT NULL;
  DELETE FROM bot_approval_callbacks       WHERE enterprise_id = ent;
  DELETE FROM workflow_approvals           WHERE enterprise_id = ent;
  DELETE FROM workflow_insights            WHERE enterprise_id = ent;
  DELETE FROM workflow_run_nodes           WHERE enterprise_id = ent;
  DELETE FROM workflow_runs                WHERE enterprise_id = ent;

  -- ── Phân tích ─────────────────────────────────────────────────────
  DELETE FROM analysis_results             WHERE enterprise_id = ent;
  DELETE FROM analysis_results_v1          WHERE enterprise_id = ent;
  DELETE FROM analysis_runs                WHERE enterprise_id = ent;
  DELETE FROM analysis_runs_v1             WHERE enterprise_id = ent;

  -- ── Pipeline + Medallion (reset môi trường demo) ──────────────────
  DELETE FROM bronze_file_embeddings       WHERE enterprise_id = ent;
  DELETE FROM silver_rows                  WHERE enterprise_id = ent;
  DELETE FROM silver_orders                WHERE enterprise_id = ent;
  DELETE FROM silver_customers             WHERE enterprise_id = ent;
  DELETE FROM silver_inventory             WHERE enterprise_id = ent;
  DELETE FROM silver_tickets               WHERE enterprise_id = ent;
  DELETE FROM silver_employees             WHERE enterprise_id = ent;
  DELETE FROM silver_finance_periods       WHERE enterprise_id = ent;
  DELETE FROM bronze_rows                  WHERE enterprise_id = ent;
  DELETE FROM bronze_files                 WHERE enterprise_id = ent;
  DELETE FROM pipeline_runs                WHERE enterprise_id = ent;
END $$;

COMMIT;

-- Kiểm nhanh sau reset
SELECT 'pipeline_runs' t, COUNT(*) FROM pipeline_runs WHERE enterprise_id='3d1c1a53-f924-41fa-a4ce-defade00e898'
UNION ALL SELECT 'document_folder', COUNT(*) FROM document_folder WHERE enterprise_id='3d1c1a53-f924-41fa-a4ce-defade00e898'
UNION ALL SELECT 'workflow_step_documents', COUNT(*) FROM workflow_step_documents WHERE enterprise_id='3d1c1a53-f924-41fa-a4ce-defade00e898'
UNION ALL SELECT 'workflow_runs', COUNT(*) FROM workflow_runs WHERE enterprise_id='3d1c1a53-f924-41fa-a4ce-defade00e898'
UNION ALL SELECT 'workflows (GIỮ)', COUNT(*) FROM workflows WHERE enterprise_id='3d1c1a53-f924-41fa-a4ce-defade00e898'
UNION ALL SELECT 'form_submissions (GIỮ)', COUNT(*) FROM workflow_form_submissions WHERE enterprise_id='3d1c1a53-f924-41fa-a4ce-defade00e898';
