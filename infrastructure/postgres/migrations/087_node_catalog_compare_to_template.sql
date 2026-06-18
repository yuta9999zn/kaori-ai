-- =====================================================================
-- 087_node_catalog_compare_to_template.sql
--
-- Phase 2.5 rollout item 9 (final RAG-backed AI node before Pattern 5
-- bbox citation lands with FE) — extend mig 068 node_type_catalog with
-- one row for compare_to_template.
--
-- Implementation: services/ai-orchestrator/reasoning/template_comparator.py
--
-- Pipeline: clause extraction (TITLE-based grouping) → BGE-M3 embed
-- both docs via llm-gateway /v1/embed → cosine match per candidate
-- clause → per-pair LLM diff with output_schema {status, risk_level,
-- explanation} → status/risk aggregation with caller-supplied risk
-- keyword bump.
--
-- Cost band: MID (N embed calls + N LLM diff calls where N ≈ clauses;
-- typical 10-30 clauses per contract). BASIC tier explicitly excluded
-- because vendor NDA reviews drive most demand and we want them on
-- MID where unit margin supports the embed+LLM round trips.
--
-- Per WORKFLOW_USE_CASES.md analysis:
--   compare_to_template covers 4 use cases:
--     vendor NDA review, standard service-contract comparison, PO
--     payment-terms drift detection, regulatory filing completeness.
-- =====================================================================

BEGIN;

INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, pricing_tier_required, rate_limit_json,
    description_vi, sort_order
) VALUES

('compare_to_template', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["template_source", "llm_pinned_version"], "properties": {"template_source": {"type": "string", "description": "Pointer tới template doc (file_id Bronze, hoặc preset ID trong template_library)"}, "similarity_threshold": {"type": "number", "minimum": 0.3, "maximum": 1.0, "default": 0.65, "description": "Cosine cutoff — candidate clause dưới ngưỡng coi như added; template clause không có peer coi như missing"}, "risk_keywords": {"type": "array", "items": {"type": "string"}, "description": "Caller-supplied risk markers; clause chứa keyword được bump risk 1 nấc. Default 17 VN/EN business risk terms (trách nhiệm, bồi thường, sở hữu trí tuệ, liability, indemnity, arbitration...)."}, "llm_pinned_version": {"type": "string", "description": "K-20 model pinning"}, "consent_external": {"type": "boolean", "default": false, "description": "K-4 opt-in. Embedding luôn local; chỉ LLM diff phase mới đi external."}}}'::jsonb,
 'high', 'MID',
 '{"per_user_per_minute": 5, "per_enterprise_per_hour": 100}'::jsonb,
 'So sánh tài liệu candidate với template đã phê duyệt. Trích clause theo TITLE, embed BGE-M3, match cosine, LLM diff per pair. Trả về matches[] với status (match/modified/missing/added) + risk_level + explanation + overall risk score 0..1. 4 use case: review NDA vendor, so service contract drift, kiểm payment-terms PO, kiểm filing pháp lý đủ điều khoản.', 238)

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
