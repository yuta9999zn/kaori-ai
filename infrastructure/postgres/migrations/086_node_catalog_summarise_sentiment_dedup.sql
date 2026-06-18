-- =====================================================================
-- 086_node_catalog_summarise_sentiment_dedup.sql
--
-- Phase 2.5 rollout — extend mig 068 node_type_catalog with 3 more
-- nodes from the WORKFLOW_USE_CASES.md "light AI nodes" batch:
--
--   summarise_document    — single LLM call returning executive
--                            summary + bullets + next-action hint
--                            (read_only)
--   sentiment_analysis    — overall + per-aspect sentiment scoring
--                            for VOC / support tickets / reviews
--                            (read_only)
--   dedup_records         — pure-Python dedup of ExtractedRow lists
--                            (e.g. CRM imports, transaction merge)
--                            (PURE — no LLM, no DB)
--
-- Implementation lives at:
--   services/ai-orchestrator/reasoning/document_summariser.py
--   services/ai-orchestrator/reasoning/sentiment_analyser.py
--   services/ai-orchestrator/reasoning/record_dedup.py
--
-- Pricing tiers
-- -------------
-- summarise_document   BASIC (one bounded LLM call, ≤900 tokens)
-- sentiment_analysis   BASIC (one bounded LLM call, ≤600 tokens)
-- dedup_records        BASIC (pure compute, zero LLM cost; tier
--                       only set so the palette can sort consistently)
--
-- Per WORKFLOW_USE_CASES.md analysis:
--   summarise_document   covers 4 use cases (regulation digest,
--                         meeting minutes, proposal review, CFO digest)
--   sentiment_analysis   covers 4 use cases (support triage, VOC,
--                         sales-call tone, NPS clustering)
--   dedup_records        covers 4 use cases (CRM master, bank-stmt
--                         reconcile, resume dedup, invoice line merge)
-- =====================================================================

BEGIN;

INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, pricing_tier_required, rate_limit_json,
    description_vi, sort_order
) VALUES

('summarise_document', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["llm_pinned_version"], "properties": {"max_bullets": {"type": "integer", "minimum": 1, "maximum": 7, "default": 5, "description": "Số bullet tối đa trong tóm tắt"}, "target_lang": {"type": "string", "enum": ["vi", "en"], "default": "vi"}, "llm_pinned_version": {"type": "string", "description": "K-20 model pinning, vd qwen2.5-14b-2026-01-01"}, "consent_external": {"type": "boolean", "default": false}}}'::jsonb,
 'low', 'BASIC',
 '{"per_user_per_minute": 20, "per_enterprise_per_hour": 400}'::jsonb,
 'Tóm tắt tài liệu (Block list từ Stage 6) thành 2-4 câu + bullets + gợi ý hành động. 4 use case: digest thông tư, biên bản họp → action items, đánh giá proposal vendor, CFO digest hằng quý.', 235),

('sentiment_analysis', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["llm_pinned_version"], "properties": {"aspects": {"type": "array", "items": {"type": "object", "required": ["name", "description"], "properties": {"name": {"type": "string", "description": "snake_case key, vd delivery_speed"}, "description": {"type": "string"}}}, "description": "Khía cạnh muốn chấm riêng (rỗng = chỉ overall)"}, "min_aspect_confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5}, "llm_pinned_version": {"type": "string"}, "consent_external": {"type": "boolean", "default": false}}}'::jsonb,
 'low', 'BASIC',
 '{"per_user_per_minute": 30, "per_enterprise_per_hour": 600}'::jsonb,
 'Phân tích cảm xúc 5 mức (very_negative..very_positive) overall + per-aspect cho VOC, support ticket, review, NPS comments. 4 use case: triage ticket negative, score VOC theo aspect, theo dõi tone khách hàng trong sales call, cluster NPS negative themes.', 236),

('dedup_records', 'processing', 'pure',
 '{"max_attempts": 1, "backoff_seconds": 0, "backoff_factor": 1.0, "jitter": false, "circuit_breaker": false}'::jsonb,
 '{"type": "object", "required": ["keys"], "properties": {"keys": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["column"], "properties": {"column": {"type": "string"}, "normaliser": {"type": "string", "enum": ["lower", "vn_phone", "vn_name", "email", "raw"], "default": "lower"}}}}, "conflict_policy": {"type": "string", "enum": ["first", "last", "longest_non_empty"], "default": "first"}, "fuzzy_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0, "description": "1.0 = exact only; <1.0 = fuzzy collapse (chỉ active khi keys có vn_name)"}}}'::jsonb,
 'low', 'BASIC',
 '{"per_user_per_minute": 100, "per_enterprise_per_hour": 5000}'::jsonb,
 'Dedup deterministic ExtractedRow list theo composite key + normaliser (vn_phone, vn_name, email, lower, raw). Conflict policy first/last/longest_non_empty hoặc merge_fn caller-supplied. 4 use case: CRM master import gộp KH, reconcile sao kê, dedup CV ứng viên, gộp line items hóa đơn cùng SKU.', 237)

ON CONFLICT (node_type_key) DO UPDATE SET
    side_effect_class    = EXCLUDED.side_effect_class,
    default_retry_policy = EXCLUDED.default_retry_policy,
    config_schema_json   = EXCLUDED.config_schema_json,
    cost_band            = EXCLUDED.cost_band,
    pricing_tier_required = EXCLUDED.pricing_tier_required,
    rate_limit_json      = EXCLUDED.rate_limit_json,
    description_vi       = EXCLUDED.description_vi,
    sort_order           = EXCLUDED.sort_order;

COMMIT;
