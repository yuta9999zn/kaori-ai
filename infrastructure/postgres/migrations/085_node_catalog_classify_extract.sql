-- =====================================================================
-- 085_node_catalog_classify_extract.sql
--
-- Phase 2.5 rollout — extend mig 068 node_type_catalog with 2 new AI
-- node types that consume Stage 6 Block lists (from Pattern 1+3):
--
--   classify_document         — single LLM classification call,
--                                category + confidence + reasoning
--   extract_structured_data   — per-TABLE LLM extraction call mapping
--                                table cells to a caller-supplied
--                                target column schema; emits typed rows
--                                with provenance (page + block_id)
--
-- Both side_effect_class = read_only per K-17 (no DB writes inside
-- the node; caller persists results into Silver per-domain tables).
--
-- Required pricing tier
-- ---------------------
-- BASIC for classify_document (1 LLM call per upload, ≤300 tokens)
-- MID for extract_structured_data (N LLM calls = N tables per doc,
--     up to 2000 tokens each — bigger envelope)
--
-- Per WORKFLOW_USE_CASES.md analysis:
--   classify_document covers 8/20 use cases
--   extract_structured_data covers 10/20 use cases
--
-- Implementation lives at:
--   services/ai-orchestrator/reasoning/document_classifier.py
--   services/ai-orchestrator/reasoning/structured_extractor.py
-- =====================================================================

BEGIN;

INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, pricing_tier_required, rate_limit_json,
    description_vi, sort_order
) VALUES

('classify_document', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["llm_pinned_version"], "properties": {"candidates": {"type": "array", "items": {"type": "string"}, "description": "Tập category candidate; mặc định DEFAULT_CATEGORIES (12 loại tài liệu phổ thông VN)"}, "min_confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.7, "description": "Ngưỡng confidence để chấp nhận; thấp hơn = uncertain"}, "llm_pinned_version": {"type": "string", "description": "K-20 model pinning, vd qwen2.5-14b-2026-01-01"}, "consent_external": {"type": "boolean", "default": false, "description": "K-4: opt-in cho external LLM provider; default Qwen local"}}}'::jsonb,
 'low', 'BASIC',
 '{"per_user_per_minute": 30, "per_enterprise_per_hour": 500}'::jsonb,
 'Phân loại tài liệu (Block list từ Stage 6) vào 1 category + confidence + reasoning. 8/20 use cases: hợp đồng, hóa đơn, sao kê, đơn từ, CV, thông tư.', 233),

('extract_structured_data', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["target_schema", "llm_pinned_version"], "properties": {"target_schema": {"type": "array", "items": {"type": "object", "required": ["name", "type", "description"], "properties": {"name": {"type": "string", "description": "snake_case key"}, "type": {"enum": ["string", "number", "integer", "date", "boolean"]}, "description": {"type": "string", "description": "Hint tiếng Việt cho LLM"}, "required": {"type": "boolean", "default": true}, "enum": {"type": "array", "items": {"type": "string"}, "description": "Tuỳ chọn — finite-value column"}}}}, "min_mapping_confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.6, "description": "Confidence floor; dưới ngưỡng emit warning nhưng vẫn trả rows"}, "llm_pinned_version": {"type": "string"}, "consent_external": {"type": "boolean", "default": false}}}'::jsonb,
 'high', 'MID',
 '{"per_user_per_minute": 10, "per_enterprise_per_hour": 200}'::jsonb,
 'Trích xuất rows có cấu trúc từ TABLE blocks (Pattern 3 pdfplumber) theo target_schema do caller cung cấp. Mỗi TABLE = 1 LLM call. Emit rows + warnings + provenance (page + block_id). 10/20 use cases: hóa đơn line items, sao kê, PO, financial report rows.', 234)

ON CONFLICT (node_type_key) DO UPDATE SET
    side_effect_class    = EXCLUDED.side_effect_class,
    default_retry_policy = EXCLUDED.default_retry_policy,
    config_schema_json   = EXCLUDED.config_schema_json,
    cost_band            = EXCLUDED.cost_band,
    pricing_tier_required = EXCLUDED.pricing_tier_required,
    rate_limit_json      = EXCLUDED.rate_limit_json,
    description_vi       = EXCLUDED.description_vi,
    sort_order           = EXCLUDED.sort_order;

COMMENT ON COLUMN node_type_catalog.config_schema_json IS
    'JSON Schema for node config. classify_document + extract_structured_data '
    '(mig 085) add 2 new ai-category entries using this column to drive '
    'node-builder UI validation per K-17.';

COMMIT;
