-- =====================================================================
-- 142_llm_routing_narrative_tasks.sql — route pipeline narrative tasks
--
-- Demo AABW 11/07: user bật "AI bên ngoài" ở Bước 4 nhưng "tóm tắt phân
-- tích" Bước 5 vẫn là Qwen — vì llm_task_routing THIẾU rule cho
-- template_narrative / overview_narrative nên gateway rơi về default
-- nội bộ bất kể consent (routing.py no_rule_using_default).
--
-- Fix: khai báo rule như analysis_summary. K-4 vẫn nguyên: routing.py
-- hạ về Qwen khi consent_external=false, nên default external ở đây
-- CHỈ có hiệu lực khi user/tenant đã đồng ý gửi dữ liệu ra ngoài.
-- =====================================================================

BEGIN;

INSERT INTO llm_task_routing (task_type, default_model_id, fallback_model_id, max_tokens, notes)
VALUES
    ('template_narrative', 'claude-sonnet-4-6', 'qwen2.5:14b', 2000,
     'Bước 5 — nhận xét per-template; external khi consent, Qwen khi không'),
    ('overview_narrative', 'claude-sonnet-4-6', 'qwen2.5:14b', 2000,
     'Bước 5 — tóm tắt tổng quan run; external khi consent, Qwen khi không')
ON CONFLICT (task_type) DO NOTHING;

COMMIT;
