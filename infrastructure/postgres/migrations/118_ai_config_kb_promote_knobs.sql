-- =====================================================================
-- 118_ai_config_kb_promote_knobs.sql — memory→KB promotion gate knobs (ADR-0036)
--
-- The "kho tự nâng cấp" loop (MemoryService.promote_to_knowledge, wired into the
-- daily memory_maintenance cron) lifts a MATURE, validated procedural/semantic
-- memory into the tenant's OWN tier-4 KB so it feeds the coverage gate
-- ("học 1 hiểu 10", ADR-0033). Its maturity bar was a source constant; expose it
-- as two platform knobs so a SUPER_ADMIN can tune how cautious promotion is
-- without a redeploy. applied=true — service.py promote_to_knowledge reads both
-- via ai_config with these as the const fallback.
-- =====================================================================

BEGIN;

INSERT INTO platform_ai_config
    (config_key, config_value, value_type, min_value, max_value, description, applied)
VALUES
    ('memory_kb_promote_min_trust',        '0.8', 'float', 0, 1,    'Độ tin (trust) tối thiểu của ký ức để được nâng vào KB nền của tenant (ADR-0036). Càng cao càng dè dặt.', TRUE),
    ('memory_kb_promote_min_appearances',  '2',   'int',   1, 100,  'Số lần ký ức được dùng/xác nhận tối thiểu trước khi nâng vào KB nền (ADR-0036).',                        TRUE)
ON CONFLICT (config_key) DO NOTHING;

COMMIT;
