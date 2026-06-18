-- =====================================================================
-- 068_node_type_catalog.sql
--
-- P2-S15 D1 — node_type_catalog table + 45-row seed per
-- docs/strategic/WORKFLOW_SYSTEM.md §2.2-2.7.
--
-- This is the CATALOG of available node types (a dictionary), separate
-- from `workflow_nodes` (instances inside workflows). A workflow_node row
-- references a catalog entry via `node_type_catalog_key` (string FK by
-- key, no integer FK to keep migration self-contained + readable in seed
-- scripts).
--
-- Schema design
-- -------------
-- side_effect_class: K-17 5-value enum (CHECK-enforced).
-- is_irreversible / requires_saga: capture spec's richer subclasses
--   (external_irreversible, configurable, approximate_idempotent) without
--   breaking K-17 invariant.
-- default_retry_policy: derived from side_effect_class per workflow_runtime
--   conventions (pure/read_only retry; non_idempotent does not).
-- cost_band: drives token-budget gating in pricing (PLAYBOOK §9 quotas).
-- pricing_tier_required: NULL = available on all tiers (PILOT through MAX).
--
-- 6 categories (8 + 10 + 5 + 8 + 8 + 6 = 45):
--   1. data_input    (8)  — all read_only
--   2. processing    (10) — mostly pure, 1 read_only (enrich)
--   3. decision      (5)  — pure + 1 write_idempotent (approval_gate)
--   4. ai            (8)  — all read_only (LLM stochastic but idempotent-ish)
--   5. action        (8)  — mix of write_idempotent + external (irreversible)
--   6. output        (6)  — all write_idempotent
--
-- K-17 invariant: every catalog row declares side_effect_class.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS node_type_catalog (
    id                          SERIAL PRIMARY KEY,
    node_type_key               VARCHAR(64) UNIQUE NOT NULL,
    category                    VARCHAR(32) NOT NULL,
    side_effect_class           VARCHAR(32) NOT NULL,
    is_irreversible             BOOLEAN     NOT NULL DEFAULT FALSE,
    requires_saga               BOOLEAN     NOT NULL DEFAULT FALSE,
    default_retry_policy        JSONB       NOT NULL,
    config_schema_json          JSONB       NOT NULL,
    cost_band                   VARCHAR(16) NOT NULL,
    pricing_tier_required       VARCHAR(16),
    rate_limit_json             JSONB,
    compensating_action         VARCHAR(64),
    description_vi              TEXT        NOT NULL,
    sort_order                  INTEGER     NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_nt_category CHECK (category IN (
        'data_input', 'processing', 'decision', 'ai', 'action', 'output'
    )),
    CONSTRAINT chk_nt_side_effect CHECK (side_effect_class IN (
        'pure', 'read_only', 'write_idempotent', 'write_non_idempotent', 'external'
    )),
    CONSTRAINT chk_nt_cost_band CHECK (cost_band IN (
        'low', 'medium', 'high', 'very_high'
    )),
    CONSTRAINT chk_nt_pricing CHECK (
        pricing_tier_required IS NULL
        OR pricing_tier_required IN ('PILOT', 'BASIC', 'MID', 'MAX')
    )
);

CREATE INDEX IF NOT EXISTS idx_node_type_catalog_category
    ON node_type_catalog(category, sort_order);

COMMENT ON TABLE node_type_catalog IS
    'P2-S15 — 45-row catalog of workflow node types (WORKFLOW_SYSTEM §2.2-2.7). '
    'Dictionary table; workflow_nodes references rows via node_type_catalog_key.';
COMMENT ON COLUMN node_type_catalog.side_effect_class IS
    'K-17: pure / read_only / write_idempotent / write_non_idempotent / external.';
COMMENT ON COLUMN node_type_catalog.is_irreversible IS
    'TRUE for spec.external_irreversible (send_email/sms/chat). Used by Saga planner.';
COMMENT ON COLUMN node_type_catalog.requires_saga IS
    'TRUE if compensating_action is set (deletable on rollback).';

-- =====================================================================
-- Seed — 45 rows
-- =====================================================================

-- ─── Category 1: data_input (8) — all read_only, cost low-medium ─────
INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, pricing_tier_required,
    description_vi, sort_order
) VALUES
('read_table', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["table"], "properties": {"table": {"type": "string"}, "columns": {"type": "array", "items": {"type": "string"}}, "filters": {"type": "object"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100000}}}'::jsonb,
 'low', NULL,
 'Đọc bảng Postgres/ClickHouse với cột + filter + limit. Output là list records.', 11),

('read_file_upload', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["file_path"], "properties": {"file_path": {"type": "string"}, "format": {"enum": ["csv", "xlsx", "parquet", "pdf", "docx"]}, "sheet_name": {"type": "string"}}}'::jsonb,
 'low', NULL,
 'Đọc file vừa upload từ Bronze (MinIO). Hỗ trợ CSV/Excel/Parquet + PDF/DOCX qua Stage 6.', 12),

('read_api', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["url"], "properties": {"url": {"type": "string", "format": "uri"}, "method": {"enum": ["GET"]}, "headers": {"type": "object"}, "auth_ref": {"type": "string", "description": "Vault path"}}}'::jsonb,
 'medium', NULL,
 'Gọi API ngoài (GET only). Auth qua Vault ref. Circuit breaker bật mặc định.', 13),

('read_webhook', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["webhook_path"], "properties": {"webhook_path": {"type": "string"}, "auth": {"type": "object"}}}'::jsonb,
 'low', NULL,
 'Lấy payload từ webhook đã đăng ký (Stage 1 ingestion bronze).', 14),

('read_form_submission', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["form_id"], "properties": {"form_id": {"type": "string"}}}'::jsonb,
 'low', NULL,
 'Đọc submission từ form do P2-M2-* tạo (manual form / approval form).', 15),

('read_email', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["email_account_ref"], "properties": {"email_account_ref": {"type": "string"}, "filter": {"type": "object"}}}'::jsonb,
 'medium', NULL,
 'Đọc email từ Gmail/Outlook connector (PM-EVT-004). Cần consent_external_email.', 16),

('read_calendar', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["calendar_id"], "properties": {"calendar_id": {"type": "string"}, "time_range": {"type": "object", "properties": {"start": {"type": "string", "format": "date-time"}, "end": {"type": "string", "format": "date-time"}}}}}'::jsonb,
 'low', NULL,
 'Đọc lịch họp + attendees từ Calendar connector (PM-EVT-005).', 17),

('read_chat', 'data_input', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["channel"], "properties": {"channel": {"type": "string"}, "filter": {"type": "object"}}}'::jsonb,
 'medium', NULL,
 'Đọc tin nhắn từ Slack/Teams/Zalo (PM-EVT-006 + future Zalo).', 18);

-- ─── Category 2: processing (10) — mostly pure ────────────────────────
INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, description_vi, sort_order
) VALUES
('filter', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["condition"], "properties": {"condition": {"type": "string", "description": "SQL WHERE or DSL expression"}}}'::jsonb,
 'low', 'Lọc records theo điều kiện. Pure — retry an toàn.', 21),

('aggregate', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["group_by", "aggregations"], "properties": {"group_by": {"type": "array", "items": {"type": "string"}}, "aggregations": {"type": "array", "items": {"type": "object", "required": ["field", "op"]}}}}'::jsonb,
 'medium', 'Group by + agg (sum/avg/count/min/max/p95). NUMERIC(14,4) cho money K-9.', 22),

('join', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["join_type", "on"], "properties": {"join_type": {"enum": ["inner", "left", "right", "full"]}, "on": {"type": "array", "items": {"type": "object"}}}}'::jsonb,
 'high', 'Join 2 streams. Cost high vì shuffle. Cảnh báo nếu cardinality > 1M.', 23),

('transform', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["transformations"], "properties": {"transformations": {"type": "array", "items": {"type": "object"}}}}'::jsonb,
 'low', 'Field transformations (cast, rename, derive). Pure compute.', 24),

('validate', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["schema"], "properties": {"schema": {"type": "object"}, "on_invalid": {"enum": ["fail", "drop", "quarantine"]}}}'::jsonb,
 'low', 'Validate row vs JSON Schema. on_invalid quyết định behavior khi sai.', 25),

('enrich', 'processing', 'read_only',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["lookup_source", "key", "fields"], "properties": {"lookup_source": {"type": "string"}, "key": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}}}}'::jsonb,
 'medium', 'Lookup từ master table (customers/vendors). read_only vì cần đọc external.', 26),

('sort', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["fields"], "properties": {"fields": {"type": "array", "items": {"type": "object"}}}}'::jsonb,
 'low', 'Sort records. Pure.', 27),

('deduplicate', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["keys"], "properties": {"keys": {"type": "array", "items": {"type": "string"}}, "keep": {"enum": ["first", "last", "highest_quality"]}}}'::jsonb,
 'low', 'Khử duplicate theo composite keys. Tùy chọn keep first/last/quality.', 28),

('split', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["partition_by"], "properties": {"partition_by": {"type": "string"}, "max_partitions": {"type": "integer"}}}'::jsonb,
 'low', 'Tách stream thành N partitions theo field value.', 29),

('merge', 'processing', 'pure',
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "properties": {"strategy": {"enum": ["concat", "interleave"]}}}'::jsonb,
 'low', 'Gộp N streams thành 1. Strategy chọn concat hoặc interleave.', 30);

-- ─── Category 3: decision (5) — pure + 1 write_idempotent ─────────────
INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, requires_saga,
    default_retry_policy, config_schema_json, cost_band,
    compensating_action, description_vi, sort_order
) VALUES
('if_else', 'decision', 'pure', FALSE,
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["condition"], "properties": {"condition": {"type": "string"}}}'::jsonb,
 'low', NULL, 'Branch 2 nhánh (true/false). Pure evaluation.', 31),

('switch', 'decision', 'pure', FALSE,
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["switch_field", "cases"], "properties": {"switch_field": {"type": "string"}, "cases": {"type": "array"}}}'::jsonb,
 'low', NULL, 'Multi-branch theo enum field. Default case bắt buộc.', 32),

('wait_for_condition', 'decision', 'pure', FALSE,
 '{"max_attempts": 1, "backoff_seconds": 0, "backoff_factor": 1.0, "jitter": false}'::jsonb,
 '{"type": "object", "required": ["condition", "timeout"], "properties": {"condition": {"type": "string"}, "timeout": {"type": "string", "description": "ISO 8601 duration"}, "poll_interval": {"type": "string"}}}'::jsonb,
 'low', NULL, 'Đợi điều kiện đúng (polling). Timeout bắt buộc để tránh deadlock.', 33),

('scheduled_trigger', 'decision', 'pure', FALSE,
 '{"max_attempts": 1, "backoff_seconds": 0, "backoff_factor": 1.0, "jitter": false}'::jsonb,
 '{"type": "object", "required": ["schedule_cron"], "properties": {"schedule_cron": {"type": "string"}, "timezone": {"type": "string", "default": "Asia/Ho_Chi_Minh"}}}'::jsonb,
 'low', NULL, 'Trigger workflow theo cron. Mặc định TZ Asia/Ho_Chi_Minh.', 34),

('approval_gate', 'decision', 'write_idempotent', TRUE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["approver_role", "timeout_action"], "properties": {"approver_role": {"type": "string"}, "message": {"type": "string"}, "timeout_action": {"enum": ["approve", "reject", "escalate"]}}}'::jsonb,
 'low', 'cancel_approval_request', 'Cổng duyệt — chờ approver_role bấm Approve/Reject. Idempotent: cùng decision = cùng outcome.', 35);

-- ─── Category 4: ai (8) — all read_only, BASIC+ or MID+ ───────────────
INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, pricing_tier_required, rate_limit_json,
    description_vi, sort_order
) VALUES
('call_insight_engine', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["insight_type", "focus_metric", "llm_pinned_version"], "properties": {"insight_type": {"type": "string"}, "focus_metric": {"type": "string"}, "methods": {"type": "array"}, "severity_threshold": {"type": "number"}, "llm_pinned_version": {"type": "string", "description": "K-20 pinned model version"}}}'::jsonb,
 'high', 'BASIC',
 '{"PILOT": 0, "BASIC": 100, "MID": 1000, "MAX": null}'::jsonb,
 'Gọi Reasoning Layer L3 sinh insight. K-20 phải pin LLM version.', 41),

('call_recommendation_engine', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["action_type", "llm_pinned_version"], "properties": {"action_type": {"type": "string"}, "constraint_check": {"type": "boolean"}, "llm_pinned_version": {"type": "string"}}}'::jsonb,
 'high', 'BASIC',
 '{"PILOT": 0, "BASIC": 50, "MID": 500, "MAX": null}'::jsonb,
 'Đề xuất action (Constraint Engine check). K-20 pin model.', 42),

('call_risk_detection', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["risk_categories"], "properties": {"risk_categories": {"type": "array"}, "severity_threshold": {"type": "number"}}}'::jsonb,
 'high', 'MID',
 '{"PILOT": 0, "BASIC": 0, "MID": 200, "MAX": null}'::jsonb,
 'Phát hiện churn/fraud/anomaly. MID+ tier (cần training data đủ).', 43),

('call_forecasting', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["target_metric", "horizon_days"], "properties": {"target_metric": {"type": "string"}, "horizon_days": {"type": "integer", "minimum": 1, "maximum": 365}, "method": {"enum": ["prophet", "arima", "ml"]}}}'::jsonb,
 'very_high', 'MID',
 '{"PILOT": 0, "BASIC": 0, "MID": 50, "MAX": null}'::jsonb,
 'Forecast metric N ngày tới. very_high cost vì retrain.', 44),

('generate_narrative', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "properties": {"style": {"enum": ["executive", "operational", "detailed"]}, "language": {"enum": ["vi", "en"]}, "llm_pinned_version": {"type": "string"}}}'::jsonb,
 'medium', 'BASIC',
 '{"PILOT": 0, "BASIC": 200, "MID": 2000, "MAX": null}'::jsonb,
 'Sinh narrative text từ data. Vietnamese business language preferred (tenet #7).', 45),

('classify_text', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["categories"], "properties": {"categories": {"type": "array", "items": {"type": "string"}}, "multi_label": {"type": "boolean"}, "model_pinned_version": {"type": "string"}}}'::jsonb,
 'medium', 'BASIC',
 '{"PILOT": 0, "BASIC": 500, "MID": 5000, "MAX": null}'::jsonb,
 'Phân loại text vào categories. Multi-label optional.', 46),

('extract_entities', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["entity_types"], "properties": {"entity_types": {"type": "array", "items": {"type": "string"}}, "model_pinned_version": {"type": "string"}}}'::jsonb,
 'medium', 'MID',
 '{"PILOT": 0, "BASIC": 0, "MID": 1000, "MAX": null}'::jsonb,
 'NER (person/org/money/date). Vietnamese-aware per K-5.', 47),

('rag_query', 'ai', 'read_only',
 '{"max_attempts": 2, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true}'::jsonb,
 '{"type": "object", "required": ["knowledge_namespace"], "properties": {"knowledge_namespace": {"type": "string"}, "max_results": {"type": "integer", "default": 5}}}'::jsonb,
 'medium', 'MID',
 '{"PILOT": 0, "BASIC": 0, "MID": 500, "MAX": null}'::jsonb,
 'Query knowledge base qua RAG router (ADR-0019: pgvector/pageindex/docsage).', 48);

-- ─── Category 5: action (8) — irreversible + saga ─────────────────────
INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, is_irreversible, requires_saga,
    default_retry_policy, config_schema_json, cost_band, pricing_tier_required,
    compensating_action, description_vi, sort_order
) VALUES
('send_email', 'action', 'external', TRUE, TRUE,
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["provider", "to", "subject", "content", "idempotency_key"], "properties": {"provider": {"enum": ["smtp", "sendgrid", "ses"]}, "template": {"type": "string"}, "to": {"type": "array"}, "subject": {"type": "string"}, "content": {"type": "string"}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'low', NULL, 'send_retraction_email',
 'Gửi email. external_irreversible (không un-send được). Saga compensation = retraction email.', 51),

('send_sms', 'action', 'external', TRUE, FALSE,
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["to", "content", "idempotency_key"], "properties": {"to": {"type": "string"}, "content": {"type": "string", "maxLength": 160}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'medium', 'BASIC', NULL,
 'Gửi SMS. Không có compensation (SMS không retract được). Sạch K-9 cho phí.', 52),

('send_chat_message', 'action', 'external', TRUE, TRUE,
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["channel", "content", "idempotency_key"], "properties": {"channel": {"type": "string"}, "content": {"type": "string"}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'low', NULL, 'delete_message',
 'Gửi chat (Slack/Telegram/Zalo via bot adapter ADR-0018). Compensation nếu provider cho phép.', 53),

('create_task', 'action', 'write_idempotent', FALSE, TRUE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["title", "assignee", "idempotency_key"], "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "assignee": {"type": "string"}, "due_date": {"type": "string", "format": "date"}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'low', NULL, 'delete_task',
 'Tạo task trong system. Idempotent qua idempotency_key (K-13).', 54),

('call_api', 'action', 'external', FALSE, TRUE,
 '{"max_attempts": 3, "backoff_seconds": 2, "backoff_factor": 2.0, "jitter": true, "circuit_breaker": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["url", "method", "idempotency_key"], "properties": {"url": {"type": "string", "format": "uri"}, "method": {"enum": ["POST", "PUT", "PATCH", "DELETE"]}, "auth_ref": {"type": "string"}, "idempotency_key": {"type": "string"}, "compensating_url": {"type": "string"}}}'::jsonb,
 'medium', NULL, 'configurable',
 'Gọi API mutating. configurable subclass — saga comp do user định nghĩa qua compensating_url.', 55),

('trigger_workflow', 'action', 'write_idempotent', FALSE, TRUE,
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["workflow_id", "idempotency_key"], "properties": {"workflow_id": {"type": "string", "format": "uuid"}, "trigger_data": {"type": "object"}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'low', NULL, 'cancel_workflow_run',
 'Trigger workflow khác (subworkflow style, async). Compensation = cancel.', 56),

('export_file', 'action', 'write_idempotent', FALSE, TRUE,
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["destination", "format"], "properties": {"destination": {"type": "string", "description": "S3 path or local"}, "format": {"enum": ["csv", "xlsx", "parquet", "pdf"]}}}'::jsonb,
 'low', NULL, 'delete_file',
 'Export file ra storage. Compensation = delete file.', 57),

('generate_report', 'action', 'write_idempotent', FALSE, TRUE,
 '{"max_attempts": 3, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["template_id"], "properties": {"template_id": {"type": "string"}, "params": {"type": "object"}, "output_format": {"enum": ["pdf", "html", "xlsx"]}}}'::jsonb,
 'medium', NULL, 'delete_report',
 'Sinh report (Stage 10 composition). Idempotent qua template+params hash.', 58);

-- ─── Category 6: output (6) — all write_idempotent ────────────────────
INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, requires_saga,
    default_retry_policy, config_schema_json, cost_band,
    compensating_action, description_vi, sort_order
) VALUES
('save_to_database', 'output', 'write_idempotent', TRUE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["table", "mode", "idempotency_key"], "properties": {"table": {"type": "string"}, "mode": {"enum": ["insert", "upsert", "replace"]}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'low', 'delete_records',
 'Persist rows. Mode upsert là idempotent; mode insert cần idempotency_key tránh duplicate.', 61),

('update_record', 'output', 'write_idempotent', TRUE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true, "requires_idempotency_key": true}'::jsonb,
 '{"type": "object", "required": ["table", "key_field", "idempotency_key"], "properties": {"table": {"type": "string"}, "key_field": {"type": "string"}, "values": {"type": "object"}, "idempotency_key": {"type": "string"}}}'::jsonb,
 'low', 'revert_with_snapshot',
 'Update row. Compensation cần snapshot trước update (lưu vào idempotency_records).', 62),

('publish_alert', 'output', 'write_idempotent', TRUE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["severity", "message"], "properties": {"severity": {"enum": ["info", "warn", "critical"]}, "message": {"type": "string"}, "channels": {"type": "array"}}}'::jsonb,
 'low', 'retract_alert',
 'Publish alert ra notification + Grafana. Compensation = retract (mark dismissed).', 63),

('publish_insight', 'output', 'write_idempotent', TRUE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["insight_payload"], "properties": {"insight_payload": {"type": "object"}, "audience": {"type": "array"}}}'::jsonb,
 'low', 'retract_insight',
 'Publish insight vào Insight Hub (decision_audit_log K-6).', 64),

('display_dashboard', 'output', 'write_idempotent', FALSE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["dashboard_id"], "properties": {"dashboard_id": {"type": "string"}, "data": {"type": "object"}}}'::jsonb,
 'low', NULL,
 'Render data vào dashboard tile (Gold layer view).', 65),

('log', 'output', 'write_idempotent', FALSE,
 '{"max_attempts": 5, "backoff_seconds": 1, "backoff_factor": 2.0, "jitter": true}'::jsonb,
 '{"type": "object", "required": ["level", "message"], "properties": {"level": {"enum": ["debug", "info", "warn", "error"]}, "message": {"type": "string"}, "context": {"type": "object"}}}'::jsonb,
 'low', NULL,
 'Write structured log (OBS-012). tenant_id auto-attach per K-19.', 66);

COMMIT;
