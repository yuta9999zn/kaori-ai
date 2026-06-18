-- =====================================================================
-- 125_node_catalog_contract.sql — Tier-3 Phase 3 (ADR-0037): contract node type
--
-- A new builder node "📑 Hợp đồng": on activate it instantiates a contract from
-- a template + parties, then pauses like an approval gate until the required
-- signatures land (sign_mode all/threshold) → contract 'hieu_luc' resumes the
-- run. side_effect_class write_idempotent (re-run with same config = same
-- contract). Additive seed; executor wired in app (ContractNodeExecutor).
-- =====================================================================

BEGIN;

INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, is_irreversible,
    default_retry_policy, config_schema_json, cost_band, compensating_action,
    description_vi, sort_order
) VALUES
('contract', 'decision', 'write_idempotent', FALSE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["title", "parties"], "properties": {"title": {"type": "string"}, "contract_type": {"type": "string"}, "template_file_id": {"type": "string"}, "value_vnd": {"type": "number"}, "sign_mode": {"enum": ["all", "threshold"]}, "required_signatures": {"type": "integer"}, "parties": {"type": "array", "items": {"type": "object", "properties": {"party_role": {"type": "string"}, "internal_user_id": {"type": "string"}, "external_name": {"type": "string"}, "external_email": {"type": "string"}, "sign_order": {"type": "integer"}}}}}}'::jsonb,
 'low', 'cancel_contract', 'Hợp đồng — tạo HĐ từ template + các bên ký (tuần tự/song song). Hiệu lực khi đủ chữ ký → tiếp bước sau.', 36)
ON CONFLICT (node_type_key) DO NOTHING;

COMMIT;
